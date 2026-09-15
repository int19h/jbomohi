from __future__ import annotations

import gzip
import io
import json
import os
import subprocess
import tarfile
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path

import pytest
from jbomohi_tools.archive.grammars import (
    GitGrammar,
    GrammarFetchError,
    GrammarFile,
    HttpResponse,
    fetch,
    fetch_vendor_files,
    ingest_camxes_backup,
)
from jbomohi_tools.archive.manifest import ArchiveManifest, object_path, store_object
from jbomohi_tools.git import Identity, commit_event
from jbomohi_tools.project.grammars import (
    GrammarProjectError,
    _unshar,
    _vendor_day_event,
    _vendor_manifest,
    _zasni_event,
    escape_mixed_bytes,
    project,
    unescape_mixed_bytes,
)


def git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit(source: Path, text: str, timestamp: str) -> str:
    (source / "grammar.peg").write_text(text)
    git(source, "add", "grammar.peg")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": timestamp,
    }
    subprocess.run(
        ["git", "commit", "-m", text],
        cwd=source,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return git(source, "rev-parse", "HEAD")


def fixture(tmp_path: Path) -> tuple[Path, GitGrammar, str]:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "--initial-branch=main")
    head = commit(source, "first\n", "2020-01-01T00:00:00+00:00")
    git(source, "tag", "v1")
    grammar = GitGrammar(
        "fixture",
        "grammars/fixture/src",
        str(source.resolve()),
        "main",
        "fixture",
        "tester",
        "text",
        "PEG",
        "test",
        "2020-present",
        "MIT",
    )
    return source, grammar, head


def test_fetch_grammar_mirror_tracks_branch_and_immutable_tags(tmp_path: Path) -> None:
    source, grammar, first = fixture(tmp_path)
    archive = tmp_path / "archive"
    report = fetch(
        archive,
        sources=(grammar,),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    ).mirrors[0]
    assert report.refs == {"refs/heads/main": first, "refs/tags/v1": first}
    manifest = ArchiveManifest.load(report.manifest)
    assert manifest.coverage["counts"] == {"commits": 1, "refs": 2, "tags": 1}
    assert json.loads(object_path(archive, manifest.sha256).read_text()) == {
        "origin": str(source.resolve()),
        "refs": report.refs,
    }

    second = commit(source, "second\n", "2021-01-01T00:00:00+00:00")
    updated = fetch(
        archive,
        sources=(grammar,),
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    ).mirrors[0]
    assert updated.refs["refs/heads/main"] == second
    assert updated.manifest != report.manifest
    assert not updated.reused_manifest
    assert fetch(archive, sources=(grammar,)).mirrors[0].reused_manifest


def test_mixed_byte_rendering_preserves_valid_utf8_and_round_trips() -> None:
    original = b"caf\xe9 \\ literal caf\xc3\xa9\n"
    rendered = escape_mixed_bytes(original, "./test.txt")
    assert rendered.startswith(
        b"# grammar source bytes escaped by jbomohi grammar-bytes/1 | "
        b"original=./test.txt\n"
    )
    assert b"caf\\xE9 \\\\ literal caf\xc3\xa9" in rendered
    assert unescape_mixed_bytes(rendered) == original


def test_unshar_extracts_declared_files_without_executing_shell() -> None:
    shell = gzip.compress(
        b"# Contents: one two\n"
        b"# Wrapped by fixture\n"
        b"""sed "s/^X//" >'one' <<'END_OF_FILE'\n"""
        b"Xfirst\nEND_OF_FILE\n"
        b"""sed "s/^X//" >'two' <<'END_OF_FILE'\n"""
        b"Xsecond\nEND_OF_FILE\n",
        mtime=0,
    )
    assert _unshar(shell) == {"one": b"first\n", "two": b"second\n"}
    unsafe = gzip.compress(
        gzip.decompress(shell).replace(b">'two'", b">'../two'"), mtime=0
    )
    with pytest.raises(GrammarProjectError, match="unsafe path"):
        _unshar(unsafe)


def test_fetch_vendor_file_is_content_addressed_and_reused(tmp_path: Path) -> None:
    source = GrammarFile(
        "official",
        "https://lojban.org/source",
        "1997-01-10",
        "fixture",
    )
    calls = []

    class Client:
        def get(self, url: str) -> HttpResponse:
            calls.append(url)
            return HttpResponse(url, b"grammar text\n", Message())

    archive = tmp_path / "archive"
    first = fetch_vendor_files(
        archive,
        (source,),
        fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
        client=Client(),
    )
    second = fetch_vendor_files(
        archive,
        (source,),
        fetched_at=datetime(2026, 9, 15, tzinfo=UTC),
        client=Client(),
    )
    assert first == second
    assert calls == [source.url]
    manifest = ArchiveManifest.load(first[0])
    assert object_path(archive, manifest.sha256).read_bytes() == b"grammar text\n"
    assert manifest.coverage["from"] == "1997-01-10"


def test_ingest_camxes_backup_validates_all_39_rcs_revisions(tmp_path: Path) -> None:
    header = ["head 1.39;", "access;", "symbols;", "locks; strict;", ""]
    for number in range(39, 0, -1):
        following = f"1.{number - 1}" if number > 1 else ""
        timestamp = (
            datetime(2004, 1, 1, tzinfo=UTC) + timedelta(days=number - 1)
        ).strftime("%Y.%m.%d.%H.%M.%S")
        header.extend(
            [
                f"1.{number}",
                f"date {timestamp}; author tester; state Exp;",
                "branches;",
                f"next {following};",
                "",
            ]
        )
    body = [
        *header,
        "desc",
        "@fixture@",
        "",
        "1.39",
        "log",
        "@head@",
        "text",
        "@39",
        "@",
    ]
    for number in range(38, 0, -1):
        body.extend(
            [
                "",
                f"1.{number}",
                "log",
                f"@revision {number}@",
                "text",
                "@d1 1",
                "a1 1",
                str(number),
                "@",
            ]
        )
    rcs = ("\n".join(body) + "\n").encode()
    source = tmp_path / "backup.tgz"
    with tarfile.open(source, "w:gz") as bundle:
        for name, payload in (
            ("./RCS/lojban.peg,v", rcs),
            ("./lojban.peg", b"39\n"),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            bundle.addfile(member, io.BytesIO(payload))
    archive = tmp_path / "archive"
    path = ingest_camxes_backup(
        archive,
        source,
        fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
    )
    manifest = ArchiveManifest.load(path)
    assert manifest.coverage["counts"] == {"files": 2, "rcs_revisions": 39}
    events = list(
        project(
            archive,
            sources=(),
            include_camxes_support=False,
            include_vendor=False,
            include_zasni=False,
        )
    )
    assert len(events) == 39
    assert events[0].source_id == "grammars/camxes=lojban.peg@1.1"
    assert events[-1].source_id == "grammars/camxes=lojban.peg@1.39"
    assert events[-1].changes["grammars/camxes/rcs/lojban.peg"] == b"39\n"
    assert "camxes (RCS replay)" in events[-1].changes["_meta/grammars/index.csv"]


def test_project_extracts_the_frozen_zasni_gerna_wiki_revision(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    payload = json.dumps(
        {
            "query": {
                "pages": [
                    {
                        "pageid": 2535,
                        "title": "zasni gerna",
                        "revisions": [
                            {
                                "revid": 111176,
                                "timestamp": "2015-01-21T07:35:26Z",
                                "user": "xorxes",
                                "slots": {
                                    "main": {
                                        "content": "intro\n<pre>\ntext &lt;- word\n</pre>\noutro"
                                    }
                                },
                            }
                        ],
                    }
                ]
            }
        }
    ).encode()
    stored = store_object(archive, payload)
    manifest = ArchiveManifest(
        source="wiki",
        kind="revisions",
        origin=(
            "https://mw.lojban.org/api.php?action=query&prop=revisions&"
            "titles=zasni+gerna"
        ),
        fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage={
            "from": "2015-01-21",
            "to": "2015-01-21",
            "counts": {"revisions": 1},
        },
        notes="fixture",
    )
    manifest.write(archive / "manifests/wiki/revisions/fixture.toml")
    events = list(
        project(
            archive,
            sources=(),
            include_camxes=False,
            include_vendor=False,
        )
    )
    assert len(events) == 1
    assert events[0].source_id == "grammars/zasni-xorxes=revid=111176"
    assert (
        events[0].changes["grammars/zasni-gerna/xorxes/zasni-gerna.peg"]
        == "text <- word\n"
    )
    assert "zasni gerna (xorxes)" in events[0].changes["_meta/grammars/index.csv"]
    ArchiveManifest(
        source=manifest.source,
        kind=manifest.kind,
        origin=manifest.origin,
        fetched_at=datetime(2026, 9, 15, tzinfo=UTC),
        sha256=manifest.sha256,
        bytes=manifest.bytes,
        coverage=manifest.coverage,
        notes=manifest.notes,
    ).write(archive / "manifests/wiki/revisions/duplicate.toml")
    with pytest.raises(GrammarProjectError, match="found 2"):
        _zasni_event(archive)


def test_zasni_extractor_rejects_an_absent_revision(tmp_path: Path) -> None:
    with pytest.raises(GrammarProjectError, match="found 0"):
        _zasni_event(tmp_path / "archive")


def test_vendor_projector_rejects_a_mismatched_manifest_kind(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    stored = store_object(archive, b"source\n")
    ArchiveManifest(
        source="grammars/fixture",
        kind="wrong-kind",
        origin="https://lojban.org/source",
        fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage={
            "from": "1997-01-10",
            "to": "1997-01-10",
            "counts": {"files": 1},
        },
        notes="fixture",
    ).write(archive / "manifests/grammars/vendor/fixture/source.toml")
    with pytest.raises(GrammarProjectError, match="identity mismatch"):
        _vendor_manifest(archive, "fixture")


def test_vendor_date_only_event_records_a_one_day_window() -> None:
    event = _vendor_day_event(
        source_id="grammars/official-test",
        date_text="1997-01-10",
        summary="official test",
        author=Identity.document("lojban.org", "Logical Language Group", "llg"),
        changes={"grammars/official/test": b"text\n"},
        trailers={"Grammar": "official"},
    )
    assert event.time_confidence == "window"
    assert event.event_window == "1997-01-10..1997-01-10"
    assert event.source_time.isoformat() == "1997-01-10T23:59:59+00:00"


def test_fetch_grammar_mirror_rejects_rewritten_tags(tmp_path: Path) -> None:
    source, grammar, _first = fixture(tmp_path)
    archive = tmp_path / "archive"
    fetch(archive, sources=(grammar,))
    second = commit(source, "second\n", "2021-01-01T00:00:00+00:00")
    git(source, "tag", "--force", "v1", second)
    with pytest.raises(GrammarFetchError, match="tag was rewritten"):
        fetch(archive, sources=(grammar,))


def test_fetch_grammar_mirror_rejects_non_fast_forward_branch(tmp_path: Path) -> None:
    source, grammar, first = fixture(tmp_path)
    archive = tmp_path / "archive"
    fetch(archive, sources=(grammar,))
    git(source, "checkout", "--orphan", "replacement")
    git(source, "rm", "-f", "grammar.peg")
    replacement = commit(source, "replacement\n", "2022-01-01T00:00:00+00:00")
    git(source, "branch", "--force", "main", replacement)
    git(source, "checkout", "main")
    assert replacement != first
    with pytest.raises(GrammarFetchError, match="not fast-forwarded"):
        fetch(archive, sources=(grammar,))


def test_project_rejects_a_diverged_archived_pin_history(tmp_path: Path) -> None:
    source, grammar, first = fixture(tmp_path)
    archive = tmp_path / "archive"
    first_report = fetch(
        archive,
        sources=(grammar,),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    ).mirrors[0]
    git(source, "checkout", "--orphan", "replacement")
    git(source, "rm", "-f", "grammar.peg")
    replacement = commit(source, "replacement\n", "2022-01-01T00:00:00+00:00")
    git(source, "branch", "--force", "main", replacement)
    git(source, "checkout", "main")
    git(
        first_report.mirror,
        "fetch",
        "--force",
        "origin",
        "+refs/heads/main:refs/heads/main",
    )
    refs = {"refs/heads/main": replacement, "refs/tags/v1": first}
    payload = (
        json.dumps(
            {"origin": grammar.url, "refs": refs}, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode()
    stored = store_object(archive, payload)
    ArchiveManifest(
        source="grammars/fixture",
        kind="git-mirror",
        origin=grammar.url,
        fetched_at=datetime(2026, 9, 15, tzinfo=UTC),
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage={
            "from": "2020-01-01",
            "to": "2022-01-01",
            "counts": {"commits": 1, "refs": 2, "tags": 1},
            "refs": refs,
        },
        notes="fixture",
    ).write(archive / "manifests/grammars/git/fixture" / f"refs-{stored.sha256}.toml")
    with pytest.raises(GrammarProjectError, match="pin history diverges"):
        list(
            project(
                archive,
                sources=(grammar,),
                include_camxes=False,
                include_vendor=False,
                include_zasni=False,
            )
        )


def test_project_grammar_mirror_emits_gitlink_metadata_and_pin_bumps(
    tmp_path: Path,
) -> None:
    source, grammar, first = fixture(tmp_path)
    archive = tmp_path / "archive"
    fetch(
        archive,
        sources=(grammar,),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    first_event = next(
        iter(
            project(
                archive,
                sources=(grammar,),
                include_camxes=False,
                include_vendor=False,
                include_zasni=False,
            )
        )
    )
    assert first_event.source_id == f"grammars/fixture={first}"
    assert first_event.event == "created"
    assert first_event.author.name == "fixture"
    assert first_event.author.email == "fixture@example.invalid"
    assert first_event.gitlinks == {grammar.path: first}
    assert first_event.submodules == {grammar.path: grammar.url}
    assert 'pinned_at = "2026-09-14T00:00:00+00:00"' in next(
        value
        for path, value in first_event.changes.items()
        if path.endswith("upstream.toml")
    )
    assert (
        "fixture,tester,text,PEG,test,2020-present,submodule"
        in first_event.changes["_meta/grammars/index.csv"]
    )

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    git(corpus, "init", "--initial-branch=main")
    commit_event(first_event, corpus)
    assert git(corpus, "ls-tree", "HEAD", grammar.path) == (
        f"160000 commit {first}\t{grammar.path}"
    )
    assert grammar.url in (corpus / ".gitmodules").read_text()

    second = commit(source, "second\n", "2021-01-01T00:00:00+00:00")
    fetch(
        archive,
        sources=(grammar,),
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    events = list(
        project(
            archive,
            sources=(grammar,),
            include_camxes=False,
            include_vendor=False,
            include_zasni=False,
        )
    )
    assert [event.event for event in events] == ["created", "edited"]
    assert events[1].source_id == f"grammars/fixture={second}"
    commit_event(events[1], corpus)
    assert git(corpus, "ls-tree", "HEAD", grammar.path) == (
        f"160000 commit {second}\t{grammar.path}"
    )
