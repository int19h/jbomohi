from __future__ import annotations

from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

import pytest
from jbomohi_tools.archive import verify_manifests
from jbomohi_tools.archive.irc import (
    FetchReport,
    HttpClient,
    HttpResponse,
    IrcFetchError,
    fetch,
)
from jbomohi_tools.cli import main
from jbomohi_tools.project.irc import load_archive


def index(*hrefs: str) -> bytes:
    links = "".join(f'<a href="{href}">{href}</a>' for href in hrefs)
    return f"<html><body>{links}</body></html>".encode()


class FakeClient:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> HttpResponse:
        self.calls.append(url)
        return HttpResponse(url=url, body=self.responses[url], headers=Message())


def fixture_responses(log: bytes) -> dict[str, bytes]:
    return {
        "https://lojban.org/irclogs/lojban/": index("../", "2014_03/", "?C=N;O=D"),
        "https://lojban.org/irclogs/lojban/2014_03/": index(
            "../", "2014_03_01.txt", "image.png"
        ),
        "https://lojban.org/irclogs/lojban/2014_03/2014_03_01.txt": log,
    }


def test_fetch_archives_indexes_and_logs_then_reuses_unchanged_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    log = b"2014-03-01 04:07:13 PST/-0800 <gleki> coi\n"
    first_client = FakeClient(fixture_responses(log))
    first = fetch(
        tmp_path,
        channels=("lojban",),
        client=first_client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert first.downloaded_logs == 1
    assert first.reused_logs == 0
    assert len(first.manifests) == 3
    assert len(first_client.calls) == 3
    [archived] = load_archive(tmp_path)
    assert archived.channel == "lojban"
    assert archived.path == "lojban/2014_03/2014_03_01.txt"
    assert archived.payload == log
    assert len(verify_manifests(tmp_path / "manifests", tmp_path)) == 3
    monkeypatch.setattr(
        "jbomohi_tools.cli.Config.from_env",
        lambda: SimpleNamespace(archive=tmp_path, corpus=tmp_path / "corpus"),
    )
    assert main(["archive", "verify"]) == 0
    assert "archive verify: ok (3 manifests)" in capsys.readouterr().out

    second_client = FakeClient(fixture_responses(log))
    second = fetch(
        tmp_path,
        channels=("lojban",),
        client=second_client,
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert second.downloaded_logs == 0
    assert second.reused_logs == 1
    assert len(second.manifests) == 2
    assert second_client.calls == [
        "https://lojban.org/irclogs/lojban/",
        "https://lojban.org/irclogs/lojban/2014_03/",
    ]


def test_changed_directory_index_fetches_a_new_immutable_log_version(
    tmp_path: Path,
) -> None:
    first_log = b"2014-03-01 04:07:13 PST/-0800 <gleki> first\n"
    fetch(
        tmp_path,
        channels=("lojban",),
        client=FakeClient(fixture_responses(first_log)),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    responses = fixture_responses(b"2014-03-01 04:07:13 PST/-0800 <gleki> corrected\n")
    responses["https://lojban.org/irclogs/lojban/2014_03/"] += b"<!-- changed -->"
    report = fetch(
        tmp_path,
        channels=("lojban",),
        client=FakeClient(responses),
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert report.downloaded_logs == 1
    [archived] = load_archive(tmp_path)
    assert b"corrected" in archived.payload
    assert len(list((tmp_path / "manifests/irc/lojban").glob("*.toml"))) == 5


def test_since_skips_directories_whose_range_ends_before_cutoff(tmp_path: Path) -> None:
    responses = {
        "https://lojban.org/irclogs/lojban/": index("2000_all/", "2026_08/"),
        "https://lojban.org/irclogs/lojban/2026_08/": index(
            "2026_08_01.txt", "2026_08_16.txt"
        ),
        "https://lojban.org/irclogs/lojban/2026_08/2026_08_16.txt": (
            b"2026-08-16 10:00:00 PDT/-0700 <a> retained\n"
        ),
    }
    client = FakeClient(responses)
    report = fetch(
        tmp_path,
        since="2026-08-15",
        channels=("lojban",),
        client=client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert report == FetchReport(report.manifests, 1, 0)
    assert "https://lojban.org/irclogs/lojban/2000_all/" not in client.calls
    assert (
        "https://lojban.org/irclogs/lojban/2026_08/2026_08_01.txt" not in client.calls
    )


def test_http_client_paces_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def geturl(self) -> str:
            return "https://lojban.org/irclogs/lojban/"

        def read(self, _size: int = -1) -> bytes:
            return b"index"

    monkeypatch.setattr(
        "jbomohi_tools.archive.irc.urlopen", lambda *_args, **_kw: Response()
    )
    ticks = iter((0.0, 0.0, 0.25, 1.0))
    sleeps: list[float] = []
    client = HttpClient(sleep=sleeps.append, monotonic=lambda: next(ticks))
    client.get("https://lojban.org/irclogs/lojban/")
    client.get("https://lojban.org/irclogs/lojban/")
    assert sleeps == [0.75]


def test_http_client_bounds_response_bytes_and_redirect_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        headers = Message()

        def __init__(self, url: str) -> None:
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def geturl(self) -> str:
            return self.url

        def read(self, _size: int = -1) -> bytes:
            return b"12345"

    monkeypatch.setattr(
        "jbomohi_tools.archive.irc.urlopen",
        lambda *_args, **_kw: Response("https://lojban.org/irclogs/x"),
    )
    with pytest.raises(IrcFetchError, match="exceeds 4 bytes"):
        HttpClient(max_bytes=4).get("https://lojban.org/irclogs/x")

    monkeypatch.setattr(
        "jbomohi_tools.archive.irc.urlopen",
        lambda *_args, **_kw: Response("https://example.org/escape"),
    )
    with pytest.raises(IrcFetchError, match="escaped the source origin"):
        HttpClient().get("https://lojban.org/irclogs/x")


@pytest.mark.parametrize(
    "failure", [URLError("temporary"), TimeoutError("temporary"), OSError("temporary")]
)
def test_http_client_retries_transient_errors_with_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    class Response:
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def geturl(self) -> str:
            return "https://lojban.org/irclogs/lojban/"

        def read(self, _size: int = -1) -> bytes:
            return b"ok"

    calls = 0

    def flaky(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise failure
        return Response()

    monkeypatch.setattr("jbomohi_tools.archive.irc.urlopen", flaky)
    sleeps: list[float] = []
    response = HttpClient(
        min_interval=0,
        attempts=2,
        sleep=sleeps.append,
        monotonic=lambda: 0.0,
    ).get("https://lojban.org/irclogs/lojban/")
    assert response.body == b"ok"
    assert calls == 2
    assert sleeps == [1]
