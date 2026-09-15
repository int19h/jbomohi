from __future__ import annotations

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
