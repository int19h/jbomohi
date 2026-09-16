from __future__ import annotations

import gzip
import hashlib
import zlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jbomohi_tools.project.wiki_sql import (
    SQL_COLUMNS,
    WikiSqlParseError,
    load_wiki_sql_dump,
    parse_title,
    php_unserialize,
    render_title,
    sha1_base36,
)


def _sql_value(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        value = value.encode()
    assert isinstance(value, bytes)
    if not value:
        return "''"
    return "0x" + value.hex().upper()


class DumpBuilder:
    """Assemble a minimal `mysqldump --skip-extended-insert` MediaWiki export."""

    def __init__(self) -> None:
        self.rows: dict[str, list[tuple[object, ...]]] = {
            table: [] for table in SQL_COLUMNS
        }
        self.next_text = 1
        self.next_content = 1

    def add(self, table: str, *values: object) -> None:
        assert len(values) == len(SQL_COLUMNS[table]), table
        self.rows[table].append(values)

    def text(self, payload: bytes, flags: str = "utf-8") -> int:
        old_id = self.next_text
        self.next_text += 1
        self.add("text", old_id, payload, flags)
        return old_id

    def content(
        self,
        old_id: int,
        *,
        size: int | None = None,
        sha1: str | None = None,
        payload: bytes = b"",
        model: int = 1,
    ) -> int:
        content_id = self.next_content
        self.next_content += 1
        self.add(
            "content",
            content_id,
            len(payload) if size is None else size,
            sha1_base36(payload) if sha1 is None else sha1,
            model,
            f"tt:{old_id}",
        )
        return content_id

    def revision_slot(self, revid: int, content_id: int) -> None:
        self.add("slots", revid, 1, content_id, revid)

    def render(self, path: Path, *, all_tables: bool = False) -> Path:
        body = bytearray(b"/*!40101 SET NAMES binary */;\n")
        if all_tables:
            # `archive.wiki_sql` checks the whole requested table list, which is
            # wider than the set the projector reads.
            from jbomohi_tools.archive.wiki_sql import WIKI_SQL_TABLES

            for table in sorted(WIKI_SQL_TABLES - set(SQL_COLUMNS)):
                body.extend(f"CREATE TABLE `{table}` (\n".encode())
                body.extend(b"  `id` int NOT NULL\n")
                body.extend(b") ENGINE=InnoDB DEFAULT CHARSET=binary;\n")
                body.extend(f"INSERT INTO `{table}` VALUES (1);\n".encode())
        for table, columns in SQL_COLUMNS.items():
            body.extend(f"CREATE TABLE `{table}` (\n".encode())
            for column in columns:
                body.extend(f"  `{column}` varbinary(255) NOT NULL,\n".encode())
            body.extend(b") ENGINE=InnoDB DEFAULT CHARSET=binary;\n")
            for values in self.rows[table]:
                rendered = ",".join(_sql_value(value) for value in values)
                body.extend(f"INSERT INTO `{table}` VALUES ({rendered});\n".encode())
        path.write_bytes(gzip.compress(bytes(body)))
        return path


def baseline() -> DumpBuilder:
    """One live page with a single plain-text revision, plus the shared rows."""

    builder = DumpBuilder()
    builder.add("slot_roles", 1, b"main")
    builder.add("content_models", 1, b"wikitext")
    builder.add("actor", 7, 3, b"Gleki")
    builder.add("comment", 11, 0, b"first edit", None)
    builder.add(
        "page",
        5,
        0,
        b"lo_nu_tavla",
        b"",
        0,
        0,
        0,
        b"20140101000000",
        100,
        6,
        b"wikitext",
        None,
        None,
    )
    old_id = builder.text(b"jbobau")
    builder.revision_slot(100, builder.content(old_id, payload=b"jbobau"))
    builder.add(
        "revision", 100, 5, 0, 0, b"20140101000000", 0, 0, 6, 0, sha1_base36(b"jbobau")
    )
    builder.add("revision_actor_temp", 100, 7, b"20140101000000", 5)
    builder.add("revision_comment_temp", 100, 11)
    return builder


def load(builder: DumpBuilder, tmp_path: Path):
    return load_wiki_sql_dump(builder.render(tmp_path / "wiki-content.sql.gz"))


def _text_gap_rows(dump, revid: int) -> list[str]:
    """Every `text unresolvable` reason the projector records for one revision."""

    from jbomohi_tools.project.wiki import project

    events = list(
        project(dump.fragments, dump.logs, (), [g.as_row() for g in dump.gaps])
    )
    rows = events[-1].changes.get("_meta/wiki/gaps.csv", "").splitlines()[1:]
    return [
        row.split(",", 5)[5]
        for row in rows
        if row.split(",")[0] == str(revid) and "text unresolvable" in row
    ]


def test_loads_a_plain_revision_with_its_joins(tmp_path: Path) -> None:
    dump = load(baseline(), tmp_path)
    assert len(dump.fragments) == 1
    page = dump.fragments[0]
    assert (page.pageid, page.namespace, page.title) == (5, 0, "lo nu tavla")
    assert page.is_redirect is False
    revision = page.revisions[0]
    assert revision.revid == 100
    assert revision.user == "Gleki"
    assert revision.comment == "first edit"
    assert revision.content == "jbobau"
    assert revision.size == 6
    assert revision.timestamp == datetime(2014, 1, 1, tzinfo=UTC)
    assert revision.sha1 == hashlib.sha1(b"jbobau").hexdigest()
    assert dump.gaps == ()
    assert dump.counts["revisions_projected"] == 1


def test_uncompresses_gzip_and_both_history_blob_classes(tmp_path: Path) -> None:
    builder = baseline()
    deflated = zlib.compress(b"gzipped body")[2:-4]
    builder.add("comment", 12, 0, b"", None)
    builder.revision_slot(
        101,
        builder.content(builder.text(deflated, "utf-8,gzip"), payload=b"gzipped body"),
    )
    builder.add(
        "revision",
        101,
        5,
        0,
        0,
        b"20140102000000",
        0,
        0,
        12,
        100,
        sha1_base36(b"gzipped body"),
    )
    builder.add("revision_actor_temp", 101, 7, b"20140102000000", 5)
    builder.add("revision_comment_temp", 101, 12)

    item = b"concatenated body"
    digest = hashlib.md5(item).hexdigest().encode()
    items = b'a:1:{s:32:"' + digest + b'";s:%d:"' % len(item) + item + b'";}'
    blob = (
        b'O:27:"ConcatenatedGzipHistoryBlob":4:'
        b'{s:8:"mVersion";i:0;s:11:"mCompressed";b:1;'
        b's:6:"mItems";s:%d:"'
        % len(zlib.compress(items)[2:-4])
        + zlib.compress(items)[2:-4]
        + b'";s:12:"mDefaultHash";s:32:"'
        + digest
        + b'";}'
    )
    concat_id = builder.text(blob, "object,utf-8")
    stub = (
        b'O:15:"HistoryBlobStub":3:{s:6:"mOldId";s:%d:"%d";'
        % (len(str(concat_id)), concat_id)
        + b's:5:"mHash";s:32:"'
        + digest
        + b'";s:4:"mRef";s:1:"9";}'
    )
    builder.add("comment", 13, 0, b"", None)
    builder.revision_slot(
        102, builder.content(builder.text(stub, "object,utf-8"), payload=item)
    )
    builder.add(
        "revision",
        102,
        5,
        0,
        0,
        b"20140103000000",
        0,
        0,
        len(item),
        101,
        sha1_base36(item),
    )
    builder.add("revision_actor_temp", 102, 7, b"20140103000000", 5)
    builder.add("revision_comment_temp", 102, 13)

    builder.add("comment", 14, 0, b"", None)
    builder.revision_slot(103, builder.content(concat_id, payload=item))
    builder.add(
        "revision",
        103,
        5,
        0,
        0,
        b"20140104000000",
        0,
        0,
        len(item),
        102,
        sha1_base36(item),
    )
    builder.add("revision_actor_temp", 103, 7, b"20140104000000", 5)
    builder.add("revision_comment_temp", 103, 14)

    revisions = {r.revid: r for r in load(builder, tmp_path).fragments[0].revisions}
    assert revisions[101].content == "gzipped body"
    assert revisions[102].content == "concatenated body"
    assert revisions[103].content == "concatenated body"


def test_content_that_fails_its_digest_is_a_gap_not_text(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 12, 0, b"", None)
    builder.revision_slot(
        101, builder.content(builder.text(b"[]"), size=1, sha1=sha1_base36(b"["))
    )
    builder.add(
        "revision", 101, 5, 0, 0, b"20140102000000", 0, 0, 1, 100, sha1_base36(b"[")
    )
    builder.add("revision_actor_temp", 101, 7, b"20140102000000", 5)
    builder.add("revision_comment_temp", 101, 12)
    dump = load(builder, tmp_path)
    revision = {r.revid: r for r in dump.fragments[0].revisions}[101]
    assert revision.content is None
    assert revision.text_missing is True
    assert revision.text_cause == "content 2 disagrees with its declared size or SHA-1"
    assert dump.counts["integrity_failures"] == 1
    # The row is written once, by the projector, from the revision itself.
    assert dump.gaps == ()
    assert _text_gap_rows(dump, 101) == [
        "text unresolvable: content 2 disagrees with its declared size or SHA-1"
    ]


def test_absent_text_row_is_a_gap(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 12, 0, b"", None)
    builder.revision_slot(101, builder.content(4242, size=3, sha1=sha1_base36(b"abc")))
    builder.add(
        "revision", 101, 5, 0, 0, b"20140102000000", 0, 0, 3, 100, sha1_base36(b"abc")
    )
    builder.add("revision_actor_temp", 101, 7, b"20140102000000", 5)
    builder.add("revision_comment_temp", 101, 12)
    dump = load(builder, tmp_path)
    revision = {r.revid: r for r in dump.fragments[0].revisions}[101]
    assert revision.content is None and revision.text_missing is True
    assert dump.gaps == ()
    assert _text_gap_rows(dump, 101) == [
        "text unresolvable: content references absent text row 4242"
    ]


def test_revision_deletion_bits_are_honoured(tmp_path: Path) -> None:
    builder = baseline()
    for index, (revid, bits) in enumerate(((101, 1), (102, 2), (103, 4), (104, 8)), 1):
        comment_id = 20 + index
        builder.add("comment", comment_id, 0, b"secret summary", None)
        builder.revision_slot(
            revid, builder.content(builder.text(b"hidden"), payload=b"hidden")
        )
        builder.add(
            "revision",
            revid,
            5,
            0,
            0,
            f"2014010{index + 1}000000".encode(),
            0,
            bits,
            6,
            100,
            sha1_base36(b"hidden"),
        )
        builder.add("revision_actor_temp", revid, 7, b"20140102000000", 5)
        builder.add("revision_comment_temp", revid, comment_id)
    dump = load(builder, tmp_path)
    revisions = {r.revid: r for r in dump.fragments[0].revisions}

    assert revisions[101].content is None and revisions[101].text_hidden is True
    assert revisions[102].comment == "" and revisions[102].comment_hidden is True
    assert revisions[103].user is None and revisions[103].user_hidden is True
    # Bit 8 masks text, comment and user together; the event still exists, so
    # the dump and API paths agree by construction rather than by absence.
    suppressed = revisions[104]
    assert suppressed.content is None and suppressed.text_hidden is True
    assert suppressed.comment == "" and suppressed.comment_hidden is True
    assert suppressed.user is None and suppressed.user_hidden is True
    assert any(gap.revid == 104 and gap.reason == "suppressed" for gap in dump.gaps)


def test_missing_actor_row_becomes_anonymous_with_a_gap(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 12, 0, b"imported", None)
    builder.revision_slot(
        101, builder.content(builder.text(b"import"), payload=b"import")
    )
    # No `revision_actor_temp` row and `rev_actor` 0: invisible to api.php.
    builder.add(
        "revision",
        101,
        5,
        0,
        0,
        b"20140102000000",
        0,
        0,
        6,
        100,
        sha1_base36(b"import"),
    )
    builder.add("revision_comment_temp", 101, 12)
    dump = load(builder, tmp_path)
    revision = {r.revid: r for r in dump.fragments[0].revisions}[101]
    assert revision.user is None
    assert revision.content == "import"
    assert dump.counts["revisions_without_author"] == 1
    assert dump.gaps[0].reason == (
        "imported revision; author not recorded in the export"
    )


def test_empty_actor_name_matches_the_api_spelling(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("actor", 8, None, b"")
    builder.add("comment", 12, 0, b"", None)
    builder.revision_slot(101, builder.content(builder.text(b"body"), payload=b"body"))
    builder.add(
        "revision", 101, 5, 0, 0, b"20140102000000", 0, 0, 4, 100, sha1_base36(b"body")
    )
    builder.add("revision_actor_temp", 101, 8, b"20140102000000", 5)
    builder.add("revision_comment_temp", 101, 12)
    revisions = {r.revid: r for r in load(builder, tmp_path).fragments[0].revisions}
    assert revisions[101].user == "Unknown user"


def test_null_revision_length_reports_zero(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 12, 0, b"", None)
    builder.revision_slot(101, builder.content(builder.text(b"body"), payload=b"body"))
    builder.add(
        "revision",
        101,
        5,
        0,
        0,
        b"20140102000000",
        0,
        0,
        None,
        100,
        sha1_base36(b"body"),
    )
    builder.add("revision_actor_temp", 101, 7, b"20140102000000", 5)
    builder.add("revision_comment_temp", 101, 12)
    revisions = {r.revid: r for r in load(builder, tmp_path).fragments[0].revisions}
    assert revisions[101].size == 0


def test_temp_tables_fall_back_to_the_direct_columns(tmp_path: Path) -> None:
    builder = DumpBuilder()
    builder.add("slot_roles", 1, b"main")
    builder.add("content_models", 1, b"wikitext")
    builder.add("actor", 7, 3, b"Gleki")
    builder.add("comment", 11, 0, b"migrated", None)
    builder.add(
        "page",
        5,
        0,
        b"x",
        b"",
        0,
        0,
        0,
        b"20140101000000",
        100,
        1,
        b"wikitext",
        None,
        None,
    )
    builder.revision_slot(100, builder.content(builder.text(b"y"), payload=b"y"))
    # A wiki that has run migrateActors.php/migrateComments.php writes here.
    builder.add(
        "revision", 100, 5, 11, 7, b"20140101000000", 0, 0, 1, 0, sha1_base36(b"y")
    )
    revision = load(builder, tmp_path).fragments[0].revisions[0]
    assert revision.user == "Gleki" and revision.comment == "migrated"


def test_pages_outside_the_projected_namespaces_are_recorded_not_projected(
    tmp_path: Path,
) -> None:
    builder = baseline()
    builder.add(
        "page",
        6,
        1198,
        b"ralju/1/en",
        b"",
        0,
        0,
        0,
        b"20140101000000",
        0,
        0,
        b"wikitext",
        None,
        None,
    )
    dump = load(builder, tmp_path)
    assert [page.pageid for page in dump.fragments] == [5]
    assert dump.counts["pages"] == 2 and dump.counts["pages_projected"] == 1
    gap = next(gap for gap in dump.gaps if gap.pageid == 6)
    assert gap.reason == "namespace 1198 is outside the projected set"
    assert gap.title == "Special:Badtitle/NS1198:ralju/1/en"


def test_revision_whose_page_row_is_gone_is_recorded_not_projected(
    tmp_path: Path,
) -> None:
    builder = baseline()
    builder.add("comment", 12, 0, b"", None)
    builder.revision_slot(101, builder.content(builder.text(b"body"), payload=b"body"))
    builder.add(
        "revision", 101, 9999, 0, 0, b"20140102000000", 0, 0, 4, 0, sha1_base36(b"body")
    )
    builder.add("revision_actor_temp", 101, 7, b"20140102000000", 5)
    builder.add("revision_comment_temp", 101, 12)
    dump = load(builder, tmp_path)
    assert dump.counts["revisions_orphaned"] == 1
    assert dump.gaps[0].reason == "revision references absent page 9999"
    assert [r.revid for r in dump.fragments[0].revisions] == [100]


def test_move_log_resolves_target_page_id_and_capitalization(tmp_path: Path) -> None:
    builder = baseline()
    builder.add(
        "page",
        6,
        828,
        b"Documentation",
        b"",
        0,
        0,
        0,
        b"20140101000000",
        0,
        0,
        b"wikitext",
        None,
        None,
    )
    builder.add("comment", 30, 0, b"renamed", None)
    builder.add(
        "logging",
        900,
        b"move",
        b"move",
        b"20140105000000",
        7,
        828,
        b"Documentation",
        0,
        30,
        b'a:2:{s:9:"4::target";s:20:"Module:documentation";s:10:"5::noredir";s:1:"1";}',
        0,
    )
    builder.add("comment", 31, 0, b"renamed too", None)
    builder.add(
        "logging",
        901,
        b"move",
        b"move",
        b"20140106000000",
        7,
        0,
        b"lo_nu_tavla",
        0,
        31,
        b'a:1:{s:9:"4::target";s:11:"lo nu ciska";}',
        0,
    )
    logs = {event.logid: event for event in load(builder, tmp_path).logs}

    module_move = logs[900]
    # ApiQueryLogEvents reports the page that holds the title now, not log_page.
    assert module_move.pageid == 6
    assert module_move.title == "Module:Documentation"
    # Module is a first-letter namespace, so the typed target is capitalized.
    assert (module_move.target_namespace, module_move.target_title) == (
        828,
        "Module:Documentation",
    )
    assert module_move.suppress_redirect is True

    main_move = logs[901]
    assert main_move.pageid == 5
    # The main namespace is case-sensitive on this wiki: no capitalization.
    assert (main_move.target_namespace, main_move.target_title) == (0, "lo nu ciska")
    assert main_move.suppress_redirect is False


def test_only_move_and_delete_log_entries_are_selected(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 30, 0, b"", None)
    for logid, log_type, action in (
        (900, b"delete", b"delete"),
        (901, b"move", b"move_redir"),
        (902, b"patrol", b"patrol"),
        (903, b"delete", b"restore"),
        (904, b"import", b"upload"),
    ):
        params = (
            b'a:1:{s:9:"4::target";s:3:"zoi";}' if log_type == b"move" else b"a:0:{}"
        )
        builder.add(
            "logging",
            logid,
            log_type,
            action,
            b"20140105000000",
            7,
            0,
            b"lo_nu_tavla",
            0,
            30,
            params,
            0,
        )
    logs = load(builder, tmp_path).logs
    assert [(event.logid, event.log_type, event.move_redir) for event in logs] == [
        (900, "delete", False),
        (901, "move", True),
    ]


def test_log_entry_without_an_actor_row_is_kept_with_a_gap(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 30, 0, b"", None)
    builder.add(
        "logging",
        900,
        b"move",
        b"move",
        b"20140105000000",
        4242,
        0,
        b"lo_nu_tavla",
        0,
        30,
        b'a:1:{s:9:"4::target";s:3:"zoi";}',
        0,
    )
    dump = load(builder, tmp_path)
    assert dump.logs[0].user is None
    assert dump.counts["log_events_without_actor"] == 1
    assert dump.gaps[0].reason == "move; actor not recorded in the export"


def test_log_entry_with_deletion_bits_is_recorded_not_projected(
    tmp_path: Path,
) -> None:
    builder = baseline()
    builder.add("comment", 30, 0, b"", None)
    builder.add(
        "logging",
        900,
        b"delete",
        b"delete",
        b"20140105000000",
        7,
        0,
        b"lo_nu_tavla",
        0,
        30,
        b"a:0:{}",
        3,
    )
    dump = load(builder, tmp_path)
    assert dump.logs == ()
    assert dump.gaps[0].reason == "delete; log entry has deletion bits 3"


def test_archive_rows_carry_deleted_revisions(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 40, 0, b"deleted page edit", None)
    builder.revision_slot(200, builder.content(builder.text(b"gone"), payload=b"gone"))
    builder.add(
        "archive",
        1,
        0,
        b"ka_nu_cilre",
        40,
        7,
        b"20140201000000",
        0,
        200,
        0,
        4,
        77,
        0,
        sha1_base36(b"gone"),
    )
    dump = load(builder, tmp_path)
    assert len(dump.archived) == 1
    archived = dump.archived[0]
    assert (archived.pageid, archived.namespace, archived.title) == (
        77,
        0,
        "ka nu cilre",
    )
    assert archived.revision.revid == 200
    assert archived.revision.content == "gone"
    assert archived.revision.user == "Gleki"


def test_export_without_external_store_support_fails_closed(tmp_path: Path) -> None:
    builder = baseline()
    builder.text(b"DB://cluster1/42", "external,utf-8")
    with pytest.raises(WikiSqlParseError, match="external store is absent"):
        load(builder, tmp_path)


def test_unexpected_schema_is_refused(tmp_path: Path) -> None:
    builder = baseline()
    path = tmp_path / "wiki-content.sql.gz"
    builder.render(path)
    body = gzip.decompress(path.read_bytes()).replace(
        b"  `rev_sha1` varbinary(255) NOT NULL,\n", b""
    )
    path.write_bytes(gzip.compress(body))
    with pytest.raises(WikiSqlParseError, match="unexpected schema for revision"):
        load_wiki_sql_dump(path)


def test_unsupported_content_address_is_refused(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("content", 99, 4, sha1_base36(b"body"), 1, b"bad:whatever")
    with pytest.raises(WikiSqlParseError, match="unsupported address"):
        load(builder, tmp_path)


@pytest.mark.parametrize(
    ("namespace", "text", "expected"),
    [
        (0, "lo nu tavla", "lo nu tavla"),
        (10, "Stub", "Template:Stub"),
        (1198, "ralju/1/en", "Special:Badtitle/NS1198:ralju/1/en"),
    ],
)
def test_render_title_matches_mediawiki(
    namespace: int, text: str, expected: str
) -> None:
    assert render_title(namespace, text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("lo nu tavla", (0, "lo nu tavla")),
        ("Module:documentation", (828, "Module:Documentation")),
        ("Template:stub", (10, "Template:Stub")),
        ("Category:cmavo", (14, "Category:cmavo")),
        ("Image:x.png", (6, "File:x.png")),
        ("Project:rules", (4, "Lojban:rules")),
        ("Translations:ralju/1/en", (0, "Translations:ralju/1/en")),
        ("lo_nu_tavla", (0, "lo nu tavla")),
    ],
)
def test_parse_title_matches_title_new_from_text(
    value: str, expected: tuple[int, str]
) -> None:
    assert parse_title(value, "test") == expected


def test_parse_title_refuses_a_virtual_namespace() -> None:
    with pytest.raises(WikiSqlParseError, match="virtual namespace"):
        parse_title("Special:Watchlist", "test")


@pytest.mark.parametrize(
    "payload",
    [
        b'O:8:"Whatever":1:{s:1:"a";s:1:"b";}x',
        b's:9:"short";',
        b'a:2:{s:1:"a";i:1;}',
        b"x:1;",
    ],
)
def test_php_unserialize_fails_closed(payload: bytes) -> None:
    with pytest.raises(WikiSqlParseError):
        php_unserialize(payload, "test")


def test_php_unserialize_reads_the_supported_types() -> None:
    value = php_unserialize(
        b'a:4:{s:1:"a";i:-3;s:1:"b";b:1;s:1:"c";N;s:1:"d";s:2:"hi";}', "test"
    )
    assert value == {b"a": -3, b"b": True, b"c": None, b"d": b"hi"}


def deleted_page_dump(tmp_path: Path) -> DumpBuilder:
    """A live page, plus a deleted lineage that a delete log accounts for."""

    builder = baseline()
    builder.add("comment", 40, 0, b"page text", None)
    builder.revision_slot(200, builder.content(builder.text(b"gone"), payload=b"gone"))
    builder.add(
        "archive",
        1,
        0,
        b"ka_nu_cilre",
        40,
        7,
        b"20140201000000",
        0,
        200,
        0,
        4,
        77,
        0,
        sha1_base36(b"gone"),
    )
    builder.add("comment", 41, 0, b"spam", None)
    builder.add(
        "logging",
        900,
        b"delete",
        b"delete",
        b"20140301000000",
        7,
        0,
        b"ka_nu_cilre",
        77,
        41,
        b"a:0:{}",
        0,
    )
    return builder


def test_backfill_rebuilds_a_deleted_lineage_and_its_end(tmp_path: Path) -> None:
    from jbomohi_tools.project.wiki_sql import archived_fragments

    dump = load(deleted_page_dump(tmp_path), tmp_path)
    fragments, ended_at, unaccounted, gaps = archived_fragments(dump, live={5})
    assert [(f.pageid, f.namespace, f.title) for f in fragments] == [
        (77, 0, "ka nu cilre")
    ]
    assert [r.revid for r in fragments[0].revisions] == [200]
    # The delete log names page 77 outright, so it bounds that lineage.
    assert ended_at == {77: (datetime(2014, 3, 1, tzinfo=UTC), 900)}
    assert unaccounted == set()
    assert gaps == []


def test_backfill_skips_a_lineage_whose_page_id_a_live_page_reuses(
    tmp_path: Path,
) -> None:
    from jbomohi_tools.project.wiki_sql import archived_fragments

    dump = load(deleted_page_dump(tmp_path), tmp_path)
    fragments, ended_at, unaccounted, gaps = archived_fragments(dump, live={5, 77})
    assert fragments == [] and ended_at == {} and unaccounted == set()
    assert [gap.reason for gap in gaps] == ["deleted lineage; page id reused by 77"]


def test_backfill_records_a_lineage_no_log_accounts_for(tmp_path: Path) -> None:
    from jbomohi_tools.project.wiki_sql import archived_fragments

    builder = deleted_page_dump(tmp_path)
    # A second lineage at the same title, with no further deletion to claim.
    builder.add("comment", 42, 0, b"earlier text", None)
    builder.revision_slot(
        201, builder.content(builder.text(b"earlier"), payload=b"earlier")
    )
    builder.add(
        "archive",
        2,
        0,
        b"ka_nu_cilre",
        42,
        7,
        b"20130101000000",
        0,
        201,
        0,
        7,
        78,
        0,
        sha1_base36(b"earlier"),
    )
    dump = load(builder, tmp_path)
    fragments, ended_at, unaccounted, gaps = archived_fragments(dump, live={5})
    # Both lineages are projected; the one no entry accounts for yields its
    # path to whoever claims it next (SPEC.md 3.2 rule 3).
    assert sorted(f.pageid for f in fragments) == [77, 78]
    assert set(ended_at) == {77}
    assert unaccounted == {78}
    assert gaps == []


def test_move_redir_can_end_a_lineage_without_a_delete_log(tmp_path: Path) -> None:
    from jbomohi_tools.project.wiki_sql import archived_fragments

    builder = baseline()
    builder.add("comment", 40, 0, b"redirect", None)
    builder.revision_slot(
        200,
        builder.content(builder.text(b"#REDIRECT [[x]]"), payload=b"#REDIRECT [[x]]"),
    )
    builder.add(
        "archive",
        1,
        0,
        b"ka_nu_cilre",
        40,
        7,
        b"20140201000000",
        0,
        200,
        0,
        15,
        77,
        0,
        sha1_base36(b"#REDIRECT [[x]]"),
    )
    builder.add("comment", 41, 0, b"over the redirect", None)
    builder.add(
        "logging",
        900,
        b"move",
        b"move_redir",
        b"20140301000000",
        7,
        0,
        b"lo_nu_tavla",
        0,
        41,
        b'a:1:{s:9:"4::target";s:11:"ka nu cilre";}',
        0,
    )
    dump = load(builder, tmp_path)
    fragments, ended_at, unaccounted, gaps = archived_fragments(dump, live={5})
    assert [f.pageid for f in fragments] == [77]
    assert fragments[0].is_redirect is True
    assert ended_at == {77: (datetime(2014, 3, 1, tzinfo=UTC), 900)}
    assert unaccounted == set() and gaps == []


def test_combine_inputs_unions_both_sources_and_refuses_disagreement(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from jbomohi_tools.project.wiki_sql import combine_inputs

    dump = load(deleted_page_dump(tmp_path), tmp_path)
    api_only = WikiPageFragmentStub(9, 0, "api only")
    combined = combine_inputs(dump, [api_only.fragment], list(dump.logs))
    assert [f.pageid for f in combined.fragments] == [5, 9, 77]
    assert [e.logid for e in combined.logs] == [900]
    assert set(combined.ended_at) == {77}
    assert combined.extra_gaps == []

    without = combine_inputs(
        dump, [api_only.fragment], list(dump.logs), backfill_deleted=False
    )
    assert [f.pageid for f in without.fragments] == [5, 9]
    assert without.ended_at == {}

    disagreeing = replace(dump.logs[0], comment="something else")
    with pytest.raises(WikiSqlParseError, match="differs between the export"):
        combine_inputs(dump, [], [disagreeing])


class WikiPageFragmentStub:
    def __init__(self, pageid: int, namespace: int, title: str) -> None:
        from jbomohi_tools.project.wiki import WikiPageFragment

        self.fragment = WikiPageFragment(pageid, namespace, title, False, ())


def test_load_dump_archive_verifies_the_archived_object(tmp_path: Path) -> None:
    from jbomohi_tools.archive.wiki_sql import ingest_wiki_sql_export
    from jbomohi_tools.project.wiki_sql import load_dump_archive

    archive = tmp_path / "archive"
    assert load_dump_archive(archive) is None

    export = tmp_path / "export"
    export.mkdir()
    deleted_page_dump(tmp_path).render(export / "wiki-content.sql.gz", all_tables=True)
    (export / "wiki-users.tsv.gz").write_bytes(
        gzip.compress(
            b"user_id\tuser_name\tuser_real_name\tuser_registration\tuser_editcount\n"
            b"1\tGleki\t\t20120927162528\t1\n"
        )
    )
    ingest_wiki_sql_export(archive, export, "2026-09-15")
    dump = load_dump_archive(archive)
    assert dump is not None
    assert [f.pageid for f in dump.fragments] == [5]
    assert [a.revision.revid for a in dump.archived] == [200]

    # A manifest whose object no longer hashes to it must not be trusted.
    obj = max(
        (
            path
            for path in (archive / "objects" / "sha256").rglob("*")
            if path.is_file()
        ),
        key=lambda path: path.stat().st_size,
    )
    obj.chmod(0o644)
    payload = obj.read_bytes()
    # Same length, different bytes: the size check passes and the digest fails.
    obj.write_bytes(payload[:-1] + bytes([payload[-1] ^ 0x01]))
    with pytest.raises(WikiSqlParseError, match="does not match manifest"):
        load_dump_archive(archive)

    obj.write_bytes(payload + b"\n")
    with pytest.raises(WikiSqlParseError, match="missing or wrong-sized"):
        load_dump_archive(archive)


def test_extra_gaps_reach_the_projected_metadata(tmp_path: Path) -> None:
    from jbomohi_tools.project.wiki import project

    dump = load(baseline(), tmp_path)
    events = list(
        project(dump.fragments, dump.logs, (), [{"revid": 1, "reason": "recorded"}])
    )
    gaps = events[-1].changes["_meta/wiki/gaps.csv"]
    assert gaps.splitlines()[0] == "revid,logid,pageid,title,timestamp,reason"
    assert gaps.splitlines()[-1] == "1,,,,,recorded"


def test_lineage_bound_is_the_last_deletion_of_a_page_id(tmp_path: Path) -> None:
    """A page deleted, restored and deleted again is bounded at the second.

    `archive` keeps rows up to the last deletion, so that is when the title
    stopped being this lineage's. Bounding at the first would hide any move
    made into the title between the two.
    """

    from jbomohi_tools.project.wiki_sql import archived_fragments

    builder = baseline()
    for index, (revid, when) in enumerate(
        ((200, b"20140201000000"), (201, b"20140401000000")), 1
    ):
        comment_id = 40 + index
        builder.add("comment", comment_id, 0, b"edit", None)
        builder.revision_slot(
            revid,
            builder.content(builder.text(b"body%d" % index), payload=b"body%d" % index),
        )
        builder.add(
            "archive",
            index,
            0,
            b"ka_nu_cilre",
            comment_id,
            7,
            when,
            0,
            revid,
            0,
            5,
            77,
            0,
            sha1_base36(b"body%d" % index),
        )
    builder.add("comment", 50, 0, b"first deletion", None)
    builder.add(
        "logging",
        900,
        b"delete",
        b"delete",
        b"20140301000000",
        7,
        0,
        b"ka_nu_cilre",
        77,
        50,
        b"a:0:{}",
        0,
    )
    builder.add("comment", 51, 0, b"restored", None)
    builder.add(
        "logging",
        901,
        b"delete",
        b"restore",
        b"20140315000000",
        7,
        0,
        b"ka_nu_cilre",
        77,
        51,
        b"a:0:{}",
        0,
    )
    builder.add("comment", 52, 0, b"second deletion", None)
    builder.add(
        "logging",
        902,
        b"delete",
        b"delete",
        b"20140501000000",
        7,
        0,
        b"ka_nu_cilre",
        77,
        52,
        b"a:0:{}",
        0,
    )
    dump = load(builder, tmp_path)
    # `restore` is not a projected log type, so only the two deletions are kept.
    assert [(e.logid, e.log_type) for e in dump.logs] == [
        (900, "delete"),
        (902, "delete"),
    ]
    fragments, ended_at, unaccounted, gaps = archived_fragments(dump, live={5})
    assert [f.pageid for f in fragments] == [77]
    assert [r.revid for r in fragments[0].revisions] == [200, 201]
    assert ended_at == {77: (datetime(2014, 5, 1, tzinfo=UTC), 902)}
    assert unaccounted == set() and gaps == []


def test_log_entry_without_an_actor_row_is_unrecorded_not_anonymous(
    tmp_path: Path,
) -> None:
    from jbomohi_tools.git import Identity
    from jbomohi_tools.project.wiki import project

    builder = baseline()
    # The page's current title is the move's target, so the title chain can
    # attribute the rename to it and the projector emits a moved event.
    original = builder.rows["page"][0]
    builder.rows["page"][0] = (*original[:2], b"lo_nu_ciska", *original[3:])
    builder.add("comment", 30, 0, b"", None)
    builder.add(
        "logging",
        900,
        b"move",
        b"move",
        b"20140105000000",
        4242,
        0,
        b"lo_nu_tavla",
        0,
        30,
        b'a:1:{s:9:"4::target";s:11:"lo nu ciska";}',
        0,
    )
    dump = load(builder, tmp_path)
    assert dump.logs[0].author_unrecorded is True
    assert dump.logs[0].user is None
    moved = [e for e in project(dump.fragments, dump.logs) if e.event == "moved"]
    assert [e.author for e in moved] == [Identity.unrecorded("mw.lojban.org")]


def test_namespace_prefixes_match_case_insensitively() -> None:
    assert parse_title("user talk:foo", "test") == (3, "User talk:Foo")
    assert parse_title("TEMPLATE:stub", "test") == (10, "Template:Stub")


def test_a_serialized_log_params_array_must_parse(tmp_path: Path) -> None:
    builder = baseline()
    builder.add("comment", 30, 0, b"", None)
    builder.add(
        "logging",
        900,
        b"move",
        b"move",
        b"20140105000000",
        7,
        0,
        b"lo_nu_tavla",
        0,
        30,
        b'a:1:{s:9:"4::target";s:99:"truncated";}',
        0,
    )
    with pytest.raises(WikiSqlParseError, match="PHP serialization"):
        load(builder, tmp_path)
