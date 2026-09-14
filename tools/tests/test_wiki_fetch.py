from __future__ import annotations

import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from urllib.error import URLError

import pytest
from jbomohi_tools.archive import verify_manifests
from jbomohi_tools.archive.wiki import (
    ApiResponse,
    WikiApiClient,
    fetch,
    query_url,
)
from jbomohi_tools.project.wiki import load_archive, load_media_archive, project


def revision(revid: int, parentid: int, content: str) -> dict[str, object]:
    return {
        "revid": revid,
        "parentid": parentid,
        "timestamp": f"2014-01-0{revid}T00:00:00Z",
        "user": "Gleki",
        "comment": "",
        "size": len(content),
        "sha1": f"{revid:040x}",
        "slots": {"main": {"content": content}},
    }


class FakeWikiClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def query(self, params):
        params = dict(params)
        self.calls.append(params)
        if params.get("meta") == "siteinfo":
            document = {"query": {"statistics": {"pages": 1}, "namespaces": []}}
        elif params.get("prop") == "revisions|info":
            if "rvcontinue" not in params:
                document = {
                    "continue": {"rvcontinue": "next", "continue": "||info"},
                    "query": {
                        "pages": [
                            {
                                "pageid": 1,
                                "ns": 0,
                                "title": "Page",
                                "revisions": [revision(1, 0, "first\n")],
                            }
                        ]
                    },
                }
            else:
                document = {
                    "query": {
                        "pages": [
                            {
                                "pageid": 1,
                                "ns": 0,
                                "title": "Page",
                                "revisions": [revision(2, 1, "second\n")],
                            }
                        ]
                    }
                }
        elif params.get("list") == "logevents":
            document = {"query": {"logevents": []}}
        elif params.get("list") == "allimages":
            document = {
                "query": {
                    "allimages": [
                        {
                            "name": "Example.png",
                            "timestamp": "2014-01-01T00:00:00Z",
                            "user": "Gleki",
                            "size": 123,
                            "url": "https://mw.lojban.org/images/a/ab/Example.png",
                            "descriptionshorturl": "https://mw.lojban.org/index.php?curid=7",
                            "sha1": "a" * 40,
                            "mime": "image/png",
                            "ns": 6,
                            "title": "File:Example.png",
                        }
                    ]
                }
            }
        elif params.get("list") == "allpages":
            document = {
                "query": {"allpages": [{"pageid": 1, "ns": 0, "title": "Page"}]}
            }
        else:
            raise AssertionError(params)
        return ApiResponse(
            query_url(params),
            json.dumps(document, separators=(",", ":")).encode(),
            Message(),
        )


def test_fetch_archives_paginated_revisions_and_resumes_from_manifests(
    tmp_path: Path,
) -> None:
    client = FakeWikiClient()
    first = fetch(
        tmp_path,
        titles=("Page",),
        client=client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert first.pages == 1
    assert first.revision_batches == 2
    assert first.log_batches == 2
    assert first.media_batches == 1
    assert first.reused_responses == 0
    assert len(first.manifests) == 6
    assert len(verify_manifests(tmp_path / "manifests", tmp_path)) == 6
    fragments = load_archive(tmp_path)
    media = load_media_archive(tmp_path)
    assert len(fragments) == 2
    assert len(media) == 1
    events = list(project(fragments, media=media))
    assert [event.source_id for event in events] == ["revid=1", "revid=2"]

    resumed_client = FakeWikiClient()
    second = fetch(
        tmp_path,
        titles=("Page",),
        client=resumed_client,
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert second.reused_responses == 6
    assert resumed_client.calls == []


def test_fetch_discovers_pages_from_selected_namespaces(tmp_path: Path) -> None:
    client = FakeWikiClient()
    report = fetch(
        tmp_path,
        namespaces=(0,),
        max_pages=1,
        client=client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert report.pages == 1
    assert any(call.get("list") == "allpages" for call in client.calls)


@pytest.mark.parametrize("failure", [TimeoutError("slow"), URLError("network")])
def test_wiki_client_retries_transport_and_maxlag_failures(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    class Response:
        headers = Message()

        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def geturl(self) -> str:
            return query_url({"action": "query", "meta": "siteinfo"})

        def read(self, _size: int = -1) -> bytes:
            return self.body

    calls = 0

    def flaky(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise failure
        if calls == 2:
            return Response(b'{"error":{"code":"maxlag","info":"busy"}}')
        return Response(b'{"query":{"statistics":{"pages":1}}}')

    monkeypatch.setattr("jbomohi_tools.archive.wiki.urlopen", flaky)
    sleeps: list[float] = []
    response = WikiApiClient(
        min_interval=0,
        attempts=3,
        sleep=sleeps.append,
        monotonic=lambda: 0.0,
    ).query({"action": "query", "meta": "siteinfo"})
    assert json.loads(response.body)["query"]["statistics"]["pages"] == 1
    assert calls == 3
    assert sleeps == [1, 2]
