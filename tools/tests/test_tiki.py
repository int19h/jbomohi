from __future__ import annotations

import gzip
from pathlib import Path

import pytest
from jbomohi_tools.archive.manifest import ArchiveManifest, object_path
from jbomohi_tools.archive.tiki import ingest_tiki_export
from jbomohi_tools.project.tiki import (
    RawTikiDump,
    TikiParseError,
    TikiUsers,
    decode_character_text,
    decode_history_blob,
    is_anonymous_tiki_user,
    is_ip_tiki_user,
    load_tiki_dump,
    load_tiki_users,
    migrated_title_map,
    page_text,
    parse_insert_values,
    project,
)


def test_parse_insert_values_keeps_bytes_hex_null_and_mysql_escapes() -> None:
    assert parse_insert_values(
        b"(1,'line\\nquote\\' slash\\\\',NULL,0x636F69,-1.25)"
    ) == (b"1", b"line\nquote' slash\\", None, b"coi", b"-1.25")


def test_load_tiki_dump_checks_field_count_and_forbidden_tables(tmp_path: Path) -> None:
    path = tmp_path / "dump.sql.gz"
    path.write_bytes(
        gzip.compress(
            b"-- header\n\n"
            b"CREATE TABLE `sample` (\n"
            b"  `id` int NOT NULL,\n"
            b"  `text` text\n"
            b") ENGINE=MyISAM;\n"
            b"INSERT INTO `sample` VALUES (1,'text');\n"
        )
    )
    loaded = load_tiki_dump(
        path,
        {"sample": ("id", "text")},
        forbidden=frozenset(),
    )
    assert loaded.tables["sample"][0] == {"id": b"1", "text": b"text"}

    bad = tmp_path / "private.sql.gz"
    bad.write_bytes(gzip.compress(b"INSERT INTO `tiki_forums` VALUES (1,'secret');\n"))
    with pytest.raises(TikiParseError, match="forbidden private table tiki_forums"):
        load_tiki_dump(bad, {})


def test_tiki_text_decoders_take_every_byte_preserving_branch() -> None:
    assert decode_character_text(b"caf\xe9", "test", "latin1-transcoded") == (
        "café",
        "cp1252",
    )
    assert decode_character_text(b"control \x8d", "test", "latin1-transcoded") == (
        "control \x8d",
        "iso-8859-1-c1",
    )
    assert decode_character_text("coi café".encode(), "test", "utf8") == (
        "coi café",
        "utf-8",
    )
    assert decode_history_blob("coi café".encode(), "test") == ("coi café", "utf-8")
    assert decode_history_blob(b"caf\xe9", "test") == ("café", "cp1252")
    assert decode_history_blob(b"control \x8d", "test") == (
        "control \x8d",
        "iso-8859-1-c1",
    )
    assert page_text(b"a &amp; b", "test", "latin1-transcoded") == (
        "a & b",
        "cp1252",
    )


def test_tiki_anonymous_user_forms() -> None:
    assert is_anonymous_tiki_user("")
    assert is_anonymous_tiki_user("Anonymous")
    assert not is_anonymous_tiki_user("192.0.2.1")
    assert is_ip_tiki_user("192.0.2.1")
    assert not is_anonymous_tiki_user("xorxes")


def test_tiki_users_honor_private_real_name_preference(tmp_path: Path) -> None:
    users = tmp_path / "users.tsv.gz"
    users.write_bytes(gzip.compress(b"userId\tlogin\n1\talice\n2\tbob\n"))
    preferences = tmp_path / "preferences.tsv.gz"
    preferences.write_bytes(
        gzip.compress(
            b"user\tprefName\tvalue\n"
            b"alice\trealName\tAlice Public\n"
            b"bob\trealName\tBob Private\n"
            b"bob\tuser_information\tprivate\n"
        )
    )
    loaded = load_tiki_users(users, preferences, character_encoding="latin1-transcoded")
    assert loaded.logins == {"alice", "bob"}
    assert loaded.display_names == {"alice": "Alice Public"}


def test_migrated_title_map_uses_exact_title_and_import_template() -> None:
    mapping = migrated_title_map(
        ("Same", "Old BPFK", "Unmapped"),
        {
            "Same": "current text",
            "New BPFK": "{{BPFK Section from tiki| Old BPFK |19}}\nbody",
        },
    )
    assert mapping == {"Same": "Same", "Old BPFK": "New BPFK"}


def _row(**values: bytes | None) -> dict[str, bytes | None]:
    return values


def test_project_keeps_history_only_and_colliding_current_as_forced_final() -> None:
    data = RawTikiDump(
        {
            "tiki_pages": (
                _row(
                    page_id=b"10",
                    pageName=b"Page",
                    data=b"new &amp; current",
                    lastModif=b"150",
                    comment=b"rollback",
                    version=b"1",
                    user=b"alice",
                    is_html=b"0",
                ),
                _row(
                    page_id=b"11",
                    pageName=b"Binary",
                    data=b"gif\0payload",
                    lastModif=b"300",
                    comment=b"binary",
                    version=b"1",
                    user=b"alice",
                    is_html=b"0",
                ),
            ),
            "tiki_history": (
                _row(
                    historyId=b"1",
                    pageName=b"Old",
                    version=b"1",
                    lastModif=b"100",
                    user=b"bob",
                    comment=b"create",
                    data=b"history only",
                    is_html=b"0",
                ),
                _row(
                    historyId=b"3",
                    pageName=b"Binary",
                    version=b"1",
                    lastModif=b"290",
                    user=b"alice",
                    comment=b"binary",
                    data=b"gif\0payload",
                    is_html=b"0",
                ),
                _row(
                    historyId=b"2",
                    pageName=b"Page",
                    version=b"1",
                    lastModif=b"200",
                    user=b"bob",
                    comment=b"previous state",
                    data=b"old state",
                    is_html=b"0",
                ),
                _row(
                    historyId=b"4",
                    pageName=b"Line\r\nBreak",
                    version=b"1",
                    lastModif=b"110",
                    user=b"bob",
                    comment=b"control title",
                    data=b"control-title body",
                    is_html=b"0",
                ),
            ),
            "tiki_comments": (
                _row(
                    threadId=b"100",
                    object=b"1",
                    objectType=b"forum",
                    parentId=b"0",
                    userName=b"alice",
                    commentDate=b"250",
                    title=b"Topic",
                    data=b"forum body",
                    message_id=b"topic@example.invalid",
                    in_reply_to=b"",
                    approved=b"y",
                ),
                _row(
                    threadId=b"101",
                    object=b"Page",
                    objectType=b"wiki page",
                    parentId=b"0",
                    userName=b"Anonymous",
                    commentDate=b"260",
                    title=b"Comment",
                    data=b"page comment",
                    message_id=b"",
                    in_reply_to=b"",
                    approved=b"y",
                ),
            ),
            "tiki_actionlog": (),
        }
    )
    users = TikiUsers(
        frozenset({"alice", "bob"}),
        {"alice": "Alice Public", "bob": "Bob Public"},
    )
    events = list(project(data, users, character_encoding="latin1-transcoded"))
    source_ids = [event.source_id for event in events]
    history = events[source_ids.index("tiki=Page@1")]
    current = events[source_ids.index("tiki=Page@current")]
    assert events.index(history) < events.index(current)
    assert history.changes["tiki/Page.tiki"] == "old state"
    assert current.changes["tiki/Page.tiki"] == "new & current"
    assert current.trailers["Ordering"] == "forced-final"
    forum = events[source_ids.index("tiki=forum/100")]
    assert "Alice Public" in forum.changes["tiki/forums/WikiDiscuss/100.txt"]
    comment = events[source_ids.index("tiki=comment/101")]
    assert "page comment" in comment.changes["tiki/talk/Page.txt"]
    gaps = events[-1].changes["_meta/tiki/gaps.csv"]
    assert "Old,tiki/Old.tiki,no current row; rename/deletion undocumented" in gaps
    assert "tiki=Binary@1,Binary,tiki/Binary.tiki,non-text page content" in gaps
    assert "tiki=Binary@current,Binary,tiki/Binary.tiki,non-text page content" in gaps
    assert all("tiki/Binary.tiki" not in event.changes for event in events)
    control = next(
        event for event in events if event.source_id == "tiki=Line%0D%0ABreak@1"
    )
    assert "tiki/Line%0D%0ABreak.tiki" in control.changes
    versions = events[-1].changes["_meta/tiki/versions.csv"]
    assert '"Line\r\nBreak",tiki=Line%0D%0ABreak@1' in versions
    coverage = events[-1].changes["_meta/tiki/coverage.toml"]
    assert "history_only_pages = 2" in coverage
    assert "current_history_version_collisions = 2" in coverage
    assert "ascii_content_different_collisions = 1" in coverage
    assert "forced_final_current_rows = 1" in coverage
    assert "binary_page_versions_skipped = 2" in coverage


def test_ingest_tiki_export_writes_three_operator_export_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export = tmp_path / "export"
    export.mkdir()
    for name in (
        "tiki-content.sanitized.sql.gz",
        "tiki-users.tsv.gz",
        "tiki-user-preferences.tsv.gz",
    ):
        (export / name).write_bytes(name.encode())
    data = RawTikiDump(
        {
            "tiki_pages": (_row(page_id=b"1"),),
            "tiki_history": (),
            "tiki_comments": (),
            "tiki_actionlog": (),
        }
    )
    users = TikiUsers(frozenset({"alice"}), {"alice": "Alice"})
    monkeypatch.setattr("jbomohi_tools.archive.tiki.load_tiki_dump", lambda _path: data)
    monkeypatch.setattr(
        "jbomohi_tools.archive.tiki.load_tiki_users",
        lambda *_args, **_kwargs: users,
    )
    monkeypatch.setattr(
        "jbomohi_tools.archive.tiki.project",
        lambda *_args, **_kwargs: iter((object(), object())),
    )
    archive = tmp_path / "archive"
    report = ingest_tiki_export(archive, export, "2026-09-13")
    assert report.events == 2
    assert len(report.manifests) == 3
    for path in report.manifests:
        manifest = ArchiveManifest.load(path)
        assert manifest.source == "tiki"
        assert manifest.kind == "db-export"
        assert manifest.origin == "operator export 2026-09-13"
        assert object_path(archive, manifest.sha256).is_file()
