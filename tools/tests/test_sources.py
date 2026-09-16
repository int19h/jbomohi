from __future__ import annotations

import gc
import weakref
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from jbomohi_tools.archive.manifest import ArchiveManifest, store_object
from jbomohi_tools.config import Config
from jbomohi_tools.sources import (
    SourceWiringError,
    mail_events,
    mediawiki_pages_from_archive,
    source_factories,
    tiki_events,
)


def test_mediawiki_pages_from_archive_supplies_tiki_mapping_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    fragments = object()
    page = SimpleNamespace(
        title="New",
        revisions=(SimpleNamespace(content="{{BPFK Section from tiki|Old|1}}\n"),),
    )
    monkeypatch.setattr("jbomohi_tools.sources.load_wiki_archive", lambda _: fragments)
    monkeypatch.setattr(
        "jbomohi_tools.sources.merge_wiki_fragments",
        lambda value: [page] if value is fragments else (),
    )
    assert mediawiki_pages_from_archive(config) == {
        "New": "{{BPFK Section from tiki|Old|1}}\n"
    }


def test_source_factories_reads_each_wiki_input_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The archived crawl and the export are each loaded once and shared.

    Both are expensive — the export is a 448 MB stream — and SPEC.md 3.2 has
    the wiki projector and Tiki's migration map read the same wiki state, so a
    build must not parse either input twice.
    """

    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    fragments = [object()]
    loads: list[str] = []
    seen: list[object] = []
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_wiki_archive",
        lambda _archive: loads.append("api") or fragments,
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_dump_archive",
        lambda _archive: loads.append("export") or None,
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.mediawiki_pages_from_archive",
        lambda _config, value: seen.append(list(value)) or {},
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_wiki_log_archive", lambda _archive: ()
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_wiki_media_archive", lambda _archive: ()
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.wiki_events",
        lambda _config, *, inputs, media: seen.append(inputs.fragments) or (),
    )
    factories = source_factories(config, ("wiki", "tiki"))
    list(factories["wiki"]())
    assert loads == ["api", "export"]
    assert seen == [fragments, fragments]


def test_source_factories_unions_the_export_with_the_crawl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With an export ingested, the wiki projector sees both inputs."""

    from jbomohi_tools.project.wiki import WikiPageFragment
    from jbomohi_tools.project.wiki_sql import WikiSqlDump

    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    crawled = WikiPageFragment(1, 0, "From the crawl", False, ())
    exported = WikiPageFragment(2, 0, "From the export", False, ())
    dump = WikiSqlDump((exported,), (), (), (), {"revisions": 0})
    seen: list[object] = []
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_wiki_archive", lambda _archive: [crawled]
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_dump_archive", lambda _archive: dump
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_wiki_log_archive", lambda _archive: ()
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_wiki_media_archive", lambda _archive: ()
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.wiki_events",
        lambda _config, *, inputs, media: seen.append(inputs) or (),
    )
    list(source_factories(config, ("wiki",))["wiki"]())
    [inputs] = seen
    # The export comes first, so its explanation of an unresolvable text wins.
    assert [f.pageid for f in inputs.fragments] == [2, 1]
    assert [name for name, _count, _cause in inputs.additive]


def test_source_factories_includes_converged_projectors(tmp_path: Path) -> None:
    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    assert set(source_factories(config, ("wiki", "cll", "grammars"))) == {
        "wiki",
        "cll",
        "grammars",
    }
    with pytest.raises(SourceWiringError, match="unknown source projector: nope"):
        source_factories(config, ("nope",))
    assert set(source_factories(config, ("irc",))) == {"irc"}


def write_tiki_manifests(config: Config, encodings: tuple[str, str, str]) -> None:
    root = config.archive / "manifests/tiki/db-export"
    names = (
        "tiki-content.sanitized.sql.gz",
        "tiki-users.tsv.gz",
        "tiki-user-preferences.tsv.gz",
    )
    for name, encoding in zip(names, encodings, strict=True):
        stored = store_object(config.archive, name.encode())
        ArchiveManifest(
            source="tiki",
            kind="db-export",
            origin="operator export 2026-09-13",
            fetched_at=datetime(2026, 9, 13, tzinfo=UTC),
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": "2026-09-13",
                "to": "2026-09-13",
                "character_encoding": encoding,
                "counts": {"rows": 1},
            },
            notes="fixture",
        ).write(root / f"{name}-{stored.sha256[:12]}.toml")


def test_tiki_events_reads_the_agreed_manifest_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    write_tiki_manifests(
        config, ("latin1-transcoded", "latin1-transcoded", "latin1-transcoded")
    )
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_tiki_dump",
        lambda _path: SimpleNamespace(tables={"tiki_pages": (), "tiki_history": ()}),
    )

    def fake_users(_users, _preferences, *, character_encoding):
        seen.append(("users", character_encoding))
        return object()

    def fake_project(_data, _users, *, character_encoding, migrated_titles):
        assert migrated_titles == {}
        seen.append(("project", character_encoding))
        return iter(())

    monkeypatch.setattr("jbomohi_tools.sources.load_tiki_users", fake_users)
    monkeypatch.setattr("jbomohi_tools.sources.project_tiki", fake_project)
    assert list(tiki_events(config)) == []
    assert seen == [
        ("users", "latin1-transcoded"),
        ("project", "latin1-transcoded"),
    ]


def test_tiki_events_rejects_disagreeing_manifest_encodings(tmp_path: Path) -> None:
    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    write_tiki_manifests(config, ("latin1-transcoded", "utf8", "latin1-transcoded"))
    with pytest.raises(SourceWiringError, match="disagree on character_encoding"):
        tiki_events(config)


def test_mail_gap_markers_clear_only_at_named_inventory_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    old_root = config.archive / "manifests/mail/lojban-list/old-lojban-list"
    beginners_root = config.archive / "manifests/mail/lojban-beginners/mhonarc"
    old_root.mkdir(parents=True)
    beginners_root.mkdir(parents=True)
    for root in (old_root, beginners_root):
        for number in range(2):
            (root / f"msg{number:05d}.toml").write_text("fixture\n")

    monkeypatch.setattr("jbomohi_tools.sources.OLD_LOJBAN_LIST_PAGE_COUNT", 2)
    monkeypatch.setattr("jbomohi_tools.sources.LOJBAN_BEGINNERS_MHONARC_PAGE_COUNT", 2)
    monkeypatch.setattr(
        "jbomohi_tools.sources.LOJBAN_BEGINNERS_MHONARC_KNOWN_MISSING",
        frozenset(),
    )
    monkeypatch.setattr("jbomohi_tools.sources.MAILDIR_LISTS", ())
    monkeypatch.setattr("jbomohi_tools.sources.MHONARC_LISTS", ())
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_mhonarc_manifestations", lambda *_args: iter(())
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_old_lojban_manifestations", lambda *_args: iter(())
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_mbox_manifestations", lambda *_args: iter(())
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_jbosnu_manifestations", lambda *_args: iter(())
    )
    observed = {}

    def fake_project(sources, *, archive_gaps):
        tuple(sources)
        observed.update(archive_gaps)
        return iter(())

    monkeypatch.setattr("jbomohi_tools.sources.project_mail", fake_project)
    assert list(mail_events(config)) == []
    assert set(observed["lojban-list"]) == {"lojban_list_old"}
    assert "lojban-beginners" not in observed
    assert config.tmp.is_dir()
    assert not (config.repo_root / "tmp").exists()


def test_mail_gap_records_exact_unavailable_beginners_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(
        tmp_path / "repo",
        tmp_path / "state/corpus",
        tmp_path / "state/archive",
        tmp_path / "state/tmp",
    )
    old_root = config.archive / "manifests/mail/lojban-list/old-lojban-list"
    beginners_root = config.archive / "manifests/mail/lojban-beginners/mhonarc"
    old_root.mkdir(parents=True)
    beginners_root.mkdir(parents=True)
    for number in (0, 3):
        (beginners_root / f"msg{number:05d}.toml").write_text("fixture\n")

    monkeypatch.setattr("jbomohi_tools.sources.OLD_LOJBAN_LIST_PAGE_COUNT", 0)
    monkeypatch.setattr("jbomohi_tools.sources.LOJBAN_BEGINNERS_MHONARC_PAGE_COUNT", 4)
    monkeypatch.setattr(
        "jbomohi_tools.sources.LOJBAN_BEGINNERS_MHONARC_KNOWN_MISSING",
        frozenset({1, 2}),
    )
    monkeypatch.setattr("jbomohi_tools.sources.MAILDIR_LISTS", ())
    monkeypatch.setattr("jbomohi_tools.sources.MHONARC_LISTS", ())
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_mhonarc_manifestations", lambda *_args: iter(())
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_old_lojban_manifestations", lambda *_args: iter(())
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_mbox_manifestations", lambda *_args: iter(())
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_jbosnu_manifestations", lambda *_args: iter(())
    )
    observed = {}

    def fake_project(sources, *, archive_gaps):
        tuple(sources)
        observed.update(archive_gaps)
        return iter(())

    monkeypatch.setattr("jbomohi_tools.sources.project_mail", fake_project)
    assert list(mail_events(config)) == []
    assert observed["lojban-beginners"] == {
        "mhonarc_missing_pages": (
            "numbered pages unavailable (HTTP 404): msg00001.html, msg00002.html"
        )
    }


class _Inputs:
    """A stand-in for the multi-gigabyte wiki union, so a weakref can watch it."""


def test_wiki_inputs_are_released_when_the_wiki_stream_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC.md 2.4 does not care where inputs live; a shared machine does.

    The wiki pair were the only inputs a factory closed over, so they stayed
    resident for the whole build. On the 2026-09-16 corpus that meant 11.5 GiB
    held through a 41-minute install that needed none of it. Handing them to
    the projector makes the end of the stream the end of the memory.
    """

    # The loaders hand their result over and keep nothing, so that the only
    # references in play are the ones under test rather than the test's own.
    box = {"inputs": _Inputs(), "media": _Inputs()}
    watch_inputs = weakref.ref(box["inputs"])
    watch_media = weakref.ref(box["media"])

    def fake_wiki_events(_config, *, inputs, media):
        def stream():
            assert inputs is not None and media is not None
            yield from ()

        return stream()

    monkeypatch.setattr("jbomohi_tools.sources.load_wiki_archive", lambda _root: [])
    monkeypatch.setattr("jbomohi_tools.sources.load_dump_archive", lambda _root: None)
    monkeypatch.setattr("jbomohi_tools.sources.load_wiki_log_archive", lambda _root: [])
    monkeypatch.setattr(
        "jbomohi_tools.sources.load_wiki_media_archive",
        lambda _root: box.pop("media"),
    )
    monkeypatch.setattr(
        "jbomohi_tools.sources.wiki_inputs", lambda *_a, **_k: box.pop("inputs")
    )
    monkeypatch.setattr("jbomohi_tools.sources.wiki_events", fake_wiki_events)

    config = Config(
        repo_root=tmp_path,
        corpus=tmp_path / "corpus",
        archive=tmp_path / "archive",
        tmp=tmp_path / "tmp",
    )
    factories = source_factories(config, ["wiki"])
    assert not box, "the test itself must not hold the inputs"

    stream = factories["wiki"]()
    # While the projector is producing, its inputs are of course still alive.
    assert watch_inputs() is not None
    assert watch_media() is not None

    # Exhausting and dropping the stream is what a finished source looks like
    # to the merge, which pops it from the heap and keeps no reference.
    assert list(stream) == []
    del stream
    gc.collect()

    assert watch_inputs() is None, "wiki inputs outlived the stream that consumed them"
    assert watch_media() is None, "wiki media outlived the stream that consumed it"
