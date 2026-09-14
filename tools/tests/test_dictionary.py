from __future__ import annotations

import base64
import gzip
import json
import zlib
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path

import pytest
from jbomohi_tools.archive.dictionary import (
    DictionaryFetchError,
    FeedResponse,
    fetch_changes,
    ingest_dictionary_exports,
)
from jbomohi_tools.archive.manifest import ArchiveManifest, object_path
from jbomohi_tools.project.dictionary import (
    JBOVLASTE_COPY_COLUMNS,
    DictionaryParseError,
    RawDictionaryDump,
    _page_content,
    jbovlaste_diff,
    load_copy_tables,
    load_dictionary_dump,
    load_jbovlaste_dump,
    project,
)


def _dump(
    columns: dict[str, tuple[str, ...]], rows: dict[str, list[tuple[str, ...]]]
) -> str:
    parts = ["-- synthetic pg_dump fixture\n"]
    for table, names in columns.items():
        rendered = ", ".join(f'"{name}"' if name == "time" else name for name in names)
        parts.append(f"COPY public.{table} ({rendered}) FROM stdin;\n")
        parts.extend("\t".join(row) + "\n" for row in rows.get(table, []))
        parts.append("\\.\n")
    return "".join(parts)


def test_copy_loader_decodes_pg_text_and_ignores_public_extra_tables(
    tmp_path: Path,
) -> None:
    columns = {
        "sample": ("id", "text", "optional"),
    }
    path = tmp_path / "dump.sql"
    path.write_bytes(
        b"COPY public.extra (id) FROM stdin;\r\n1\r\n\\.\r\n"
        b"COPY public.sample (id, text, optional) FROM stdin;\r\n"
        b"1\tline\\nwith\\ttab and \\\\ slash \\141 \\x62\t\\N\r\n\\.\r\n"
    )
    tables = load_copy_tables(path, columns, forbidden=frozenset())
    assert tables == {
        "sample": (
            {
                "id": "1",
                "text": "line\nwith\ttab and \\ slash a b",
                "optional": None,
            },
        )
    }


def test_copy_loader_detects_gzip_without_a_filename_suffix(tmp_path: Path) -> None:
    path = tmp_path / "content-addressed-object"
    path.write_bytes(
        gzip.compress(
            b"COPY public.sample (id, text) FROM stdin;\n1\tvalue\n\\.\n",
            mtime=0,
        )
    )
    assert load_copy_tables(
        path,
        {"sample": ("id", "text")},
        forbidden=frozenset(),
    )["sample"] == ({"id": "1", "text": "value"},)


def test_copy_loader_recovers_literal_newline_in_exported_field(tmp_path: Path) -> None:
    path = tmp_path / "dump.sql"
    path.write_bytes(
        b"COPY public.sample (id, text, tail) FROM stdin;\r\n"
        b"1\tfirst line\r\nsecond line\tdone\r\n\\.\r\n"
    )
    tables = load_copy_tables(
        path,
        {"sample": ("id", "text", "tail")},
        forbidden=frozenset(),
    )
    assert tables["sample"][0] == {
        "id": "1",
        "text": "first line\nsecond line",
        "tail": "done",
    }


def test_copy_loader_rejects_mixed_transfer_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "dump.sql"
    path.write_bytes(b"COPY public.sample (id, text) FROM stdin;\r\n1\tvalue\n\\.\r\n")
    with pytest.raises(DictionaryParseError, match="mixes LF and CRLF"):
        load_copy_tables(
            path,
            {"sample": ("id", "text")},
            forbidden=frozenset(),
        )


def test_copy_loader_rejects_private_table_before_reading_its_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dump.sql"
    path.write_text(
        "COPY public.users_view (userid, username, votesize) FROM stdin;\n"
        "1\tname\t1.0\n\\.\n",
        encoding="utf-8",
    )
    with pytest.raises(
        DictionaryParseError, match="forbidden private table users_view"
    ):
        load_copy_tables(path, {})


def test_copy_loader_rejects_schema_drift_and_missing_tables(tmp_path: Path) -> None:
    path = tmp_path / "dump.sql"
    path.write_text(
        "COPY public.sample (id, changed) FROM stdin;\n1\tx\n\\.\n",
        encoding="utf-8",
    )
    with pytest.raises(DictionaryParseError, match="unexpected columns"):
        load_copy_tables(path, {"sample": ("id", "text")}, forbidden=frozenset())
    with pytest.raises(DictionaryParseError, match="missing COPY tables: absent"):
        load_copy_tables(path, {"absent": ("id",)}, forbidden=frozenset())


def test_dictionary_dump_loads_synthetic_known_schema(tmp_path: Path) -> None:
    from jbomohi_tools.project.dictionary import LENSISKU_COPY_COLUMNS

    dump = tmp_path / "lensisku.sql"
    dump.write_text(_dump(LENSISKU_COPY_COLUMNS, {}), encoding="utf-8")
    users = tmp_path / "users.csv"
    users.write_text(
        "userid,username,realname,url,personal,created_at,role,disabled\n"
        "1,test,Test User,https://example.invalid,,2024-01-01T00:00:00Z,user,false\n",
        encoding="utf-8",
    )
    scores = tmp_path / "scores.csv"
    scores.write_text(
        "definitionid,valsiid,langid,score,votes,last_vote_time\n"
        "10,20,1,3,2,1704067200\n",
        encoding="utf-8",
    )
    loaded = load_dictionary_dump(dump, users, scores)
    assert loaded.users[0]["username"] == "test"
    assert loaded.scores[0]["score"] == "3"
    assert set(loaded.tables) == set(LENSISKU_COPY_COLUMNS)


def test_jbovlaste_dump_uses_older_schema_and_public_user_columns(
    tmp_path: Path,
) -> None:
    dump = tmp_path / "jbovlaste.sql"
    dump.write_text(_dump(JBOVLASTE_COPY_COLUMNS, {}), encoding="utf-8")
    users = tmp_path / "users.csv"
    users.write_text(
        "userid,username,realname,url,personal\n1,test,Test User,,\n",
        encoding="utf-8",
    )
    scores = tmp_path / "scores.csv"
    scores.write_text(
        "definitionid,valsiid,langid,score,votes,last_vote_time\n"
        "10,20,1,3,2,1704067200\n",
        encoding="utf-8",
    )
    loaded = load_jbovlaste_dump(dump, users, scores)
    assert set(loaded.tables) == set(JBOVLASTE_COPY_COLUMNS)


def _row(**values: str | None) -> dict[str, str | None]:
    return values


def _snapshot() -> RawDictionaryDump:
    tables: dict[str, tuple[dict[str, str | None], ...]] = {
        "languages": (_row(langid="1", tag="en"),),
        "valsitypes": (_row(typeid="1", descriptor="gismu"),),
        "valsi": (
            _row(
                valsiid="20",
                word="broda",
                typeid="1",
                userid="1",
                time="100",
                rafsi="bro",
            ),
        ),
        "definitions": (
            _row(
                langid="1",
                valsiid="20",
                definitionid="10",
                definition="final text",
                notes="final notes",
                userid="1",
                time="300",
                created_at="1970-01-01 00:03:20+00",
                selmaho="BRIVLA",
                jargon=None,
                etymology=None,
                rafsi=None,
            ),
            _row(
                langid="1",
                valsiid="20",
                definitionid="11",
                definition="native definition",
                notes=None,
                userid="2",
                time="400",
                created_at="1970-01-01 00:06:40+00",
                selmaho=None,
                jargon=None,
                etymology=None,
                rafsi=None,
            ),
        ),
        "definition_versions": (
            _row(
                version_id="100",
                definition_id="10",
                langid="1",
                valsiid="20",
                definition="baseline text",
                notes="baseline notes",
                selmaho="BRIVLA",
                jargon=None,
                gloss_keywords="[]",
                place_keywords="[]",
                user_id="1",
                created_at="1970-01-01 00:03:20+00",
                message="Initial version",
                etymology=None,
                rafsi=None,
                mw_revid=None,
            ),
            _row(
                version_id="101",
                definition_id="10",
                langid="1",
                valsiid="20",
                definition="final text",
                notes="final notes",
                selmaho="BRIVLA",
                jargon=None,
                gloss_keywords="[]",
                place_keywords="[]",
                user_id="2",
                created_at="1970-01-01 00:05:00.123456+00",
                message="Improve wording",
                etymology=None,
                rafsi=None,
                mw_revid=None,
            ),
            _row(
                version_id="102",
                definition_id="11",
                langid="1",
                valsiid="20",
                definition="native definition",
                notes=None,
                selmaho=None,
                jargon=None,
                gloss_keywords="[]",
                place_keywords="[]",
                user_id="2",
                created_at="1970-01-01 00:06:40+00",
                message="Updated version",
                etymology=None,
                rafsi=None,
                mw_revid=None,
            ),
        ),
        "natlangwords": (),
        "keywordmapping": (),
        "etymology": (),
        "example": (
            _row(
                exampleid="200",
                valsiid="20",
                definitionid="0",
                content="word-level example",
                time="250",
                userid="1",
            ),
            _row(
                exampleid="201",
                valsiid="20",
                definitionid="10",
                content="definition example",
                time="250",
                userid="2",
            ),
        ),
        "threads": (),
        "comments": (),
        "pages": (),
    }
    return RawDictionaryDump(
        tables=tables,
        users=(
            {"userid": "1", "username": "alice"},
            {"userid": "2", "username": "bob"},
        ),
        scores=(
            {
                "definitionid": "10",
                "valsiid": "20",
                "langid": "1",
                "score": "3",
            },
        ),
    )


def test_project_uses_baseline_then_edits_and_both_example_scopes() -> None:
    events = list(project(_snapshot(), export_date="2026-09-13"))
    source_ids = [event.source_id for event in events]
    assert "definition=10 version=0" in source_ids
    assert "definition=10 version=100" not in source_ids
    assert "definition=10 version=101" in source_ids
    baseline = events[source_ids.index("definition=10 version=0")]
    assert baseline.time_confidence == "window"
    assert baseline.event_window == "1970-01-01..1970-01-01"
    assert "baseline text" in baseline.changes["dict/broda/en-10.md"]
    edit = events[source_ids.index("definition=10 version=101")]
    assert edit.source_time.isoformat() == "1970-01-01T00:05:00+00:00"
    assert (
        'updated = "1970-01-01T00:05:00.123456Z"' in edit.changes["dict/broda/en-10.md"]
    )
    word_example = events[source_ids.index("example=200")]
    assert "word-level example" in word_example.changes["dict/broda/examples.md"]
    definition_example = events[source_ids.index("example=201")]
    assert "definition example" in definition_example.changes["dict/broda/en-10.md"]
    definitions_index = events[-1].changes["_meta/dict/definitions.csv"]
    assert (
        "10,broda,en,bob,1970-01-01T00:05:00.123456Z,2,3,2026-09-13,current"
        in definitions_index
    )
    assert 'score_as_of = "2026-09-13"' in edit.changes["dict/broda/en-10.md"]
    assert all(len(event.subject) <= 72 for event in events)


def test_project_rejects_a_nonbaseline_first_direct_version() -> None:
    snapshot = _snapshot()
    rows = list(snapshot.tables["definition_versions"])
    rows[0] = {**rows[0], "created_at": "1970-01-01 00:03:21+00"}
    broken = RawDictionaryDump(
        tables={**snapshot.tables, "definition_versions": tuple(rows)},
        users=snapshot.users,
        scores=snapshot.scores,
    )
    with pytest.raises(DictionaryParseError, match="earliest direct version"):
        list(project(broken, export_date="2026-09-13"))


def test_word_rafsi_follow_definition_state_at_each_event() -> None:
    snapshot = _snapshot()
    definitions = list(snapshot.tables["definitions"])
    definitions[0] = {**definitions[0], "rafsi": "new"}
    versions = list(snapshot.tables["definition_versions"])
    versions[0] = {**versions[0], "rafsi": "old"}
    versions[1] = {**versions[1], "rafsi": "new"}
    historical = RawDictionaryDump(
        tables={
            **snapshot.tables,
            "definitions": tuple(definitions),
            "definition_versions": tuple(versions),
        },
        users=snapshot.users,
        scores=snapshot.scores,
    )
    events = list(project(historical, export_date="2026-09-13"))
    baseline = next(
        event for event in events if event.source_id == "definition=10 version=0"
    )
    edit = next(
        event for event in events if event.source_id == "definition=10 version=101"
    )
    assert 'rafsi = ["bro", "old"]' in baseline.changes["dict/broda/word.toml"]
    assert 'rafsi = ["bro", "new"]' in edit.changes["dict/broda/word.toml"]


def test_compressed_jbovlaste_page_decodes_and_corruption_fails_closed() -> None:
    encoded = base64.b64encode(zlib.compress(b"coi ro do")).decode()
    assert _page_content(encoded, "t", "page") == "coi ro do"
    with pytest.raises(DictionaryParseError, match="invalid compressed page content"):
        _page_content("not-base64", "t", "page")


def test_project_accepts_stale_legacy_definition_time_when_state_matches() -> None:
    snapshot = _snapshot()
    definitions = list(snapshot.tables["definitions"])
    definitions[0] = {**definitions[0], "time": "301"}
    stale = RawDictionaryDump(
        tables={**snapshot.tables, "definitions": tuple(definitions)},
        users=snapshot.users,
        scores=snapshot.scores,
    )
    events = list(project(stale, export_date="2026-09-13"))
    coverage = events[-1].changes["_meta/dict/coverage.toml"]
    assert "latest_legacy_time_mismatches = 1" in coverage
    assert "latest_legacy_time_delta_min = 1" in coverage
    assert "latest_legacy_time_delta_max = 1" in coverage


def test_project_places_v0_before_early_example_but_keeps_state_timestamp() -> None:
    snapshot = _snapshot()
    definitions = list(snapshot.tables["definitions"])
    definitions[0] = {
        **definitions[0],
        "created_at": "1970-01-01 00:04:40+00",
    }
    versions = list(snapshot.tables["definition_versions"])
    versions[0] = {
        **versions[0],
        "created_at": "1970-01-01 00:04:40+00",
    }
    early = RawDictionaryDump(
        tables={
            **snapshot.tables,
            "definitions": tuple(definitions),
            "definition_versions": tuple(versions),
        },
        users=snapshot.users,
        scores=snapshot.scores,
    )
    events = list(project(early, export_date="2026-09-13"))
    baseline = next(
        event for event in events if event.source_id == "definition=10 version=0"
    )
    example = next(event for event in events if event.source_id == "example=200")
    assert baseline.source_time.isoformat() == "1970-01-01T00:04:10+00:00"
    assert events.index(baseline) < events.index(example)
    assert baseline.trailers["State-As-Of"] == "1970-01-01T00:04:40Z"
    assert 'updated = "1970-01-01T00:04:40Z"' in baseline.changes["dict/broda/en-10.md"]
    coverage = events[-1].changes["_meta/dict/coverage.toml"]
    assert "baseline_dependency_clamps = 1" in coverage


def test_project_clamps_bounded_word_definition_clock_skew_and_counts_it() -> None:
    snapshot = _snapshot()
    definitions = list(snapshot.tables["definitions"])
    definitions[0] = {**definitions[0], "created_at": "1970-01-01 00:01:37+00"}
    versions = list(snapshot.tables["definition_versions"])
    versions[0] = {**versions[0], "created_at": "1970-01-01 00:01:37+00"}
    skewed = RawDictionaryDump(
        tables={
            **snapshot.tables,
            "definitions": tuple(definitions),
            "definition_versions": tuple(versions),
        },
        users=snapshot.users,
        scores=snapshot.scores,
    )
    events = list(project(skewed, export_date="2026-09-13"))
    baseline = next(
        event for event in events if event.source_id == "definition=10 version=0"
    )
    assert baseline.source_time.isoformat() == "1970-01-01T00:01:40+00:00"
    coverage = events[-1].changes["_meta/dict/coverage.toml"]
    assert "baseline_time_clamps = 1" in coverage


def test_project_rejects_word_definition_clock_skew_over_ten_seconds() -> None:
    snapshot = _snapshot()
    definitions = list(snapshot.tables["definitions"])
    definitions[0] = {**definitions[0], "created_at": "1970-01-01 00:01:29+00"}
    versions = list(snapshot.tables["definition_versions"])
    versions[0] = {**versions[0], "created_at": "1970-01-01 00:01:29+00"}
    skewed = RawDictionaryDump(
        tables={
            **snapshot.tables,
            "definitions": tuple(definitions),
            "definition_versions": tuple(versions),
        },
        users=snapshot.users,
        scores=snapshot.scores,
    )
    with pytest.raises(DictionaryParseError, match="predates its valsi by 11 seconds"):
        list(project(skewed, export_date="2026-09-13"))


def test_project_excludes_mw_mirror_whole_but_keeps_native_type16() -> None:
    snapshot = _snapshot()
    tables = dict(snapshot.tables)
    tables["valsitypes"] = (
        *tables["valsitypes"],
        _row(typeid="16", descriptor="wiki"),
    )
    tables["valsi"] = (
        *tables["valsi"],
        _row(
            valsiid="30",
            word="Mirrored page",
            typeid="16",
            userid="1",
            time="500",
            rafsi=None,
        ),
        _row(
            valsiid="31",
            word="Native page",
            typeid="16",
            userid="1",
            time="600",
            rafsi=None,
        ),
    )
    tables["definitions"] = (
        *tables["definitions"],
        _row(
            langid="-1",
            valsiid="30",
            definitionid="12",
            definition="mirror current",
            notes=None,
            userid="1",
            time="500",
            created_at="1970-01-01 00:08:20+00",
            selmaho=None,
            jargon=None,
            etymology=None,
            rafsi=None,
        ),
        _row(
            langid="1",
            valsiid="31",
            definitionid="13",
            definition="native current",
            notes=None,
            userid="1",
            time="600",
            created_at="1970-01-01 00:10:00+00",
            selmaho=None,
            jargon=None,
            etymology=None,
            rafsi=None,
        ),
    )
    tables["definition_versions"] = (
        *tables["definition_versions"],
        _row(
            version_id="103",
            definition_id="12",
            langid="1",
            valsiid="30",
            definition="mirror revision",
            notes=None,
            selmaho=None,
            jargon=None,
            gloss_keywords="[]",
            place_keywords="[]",
            user_id="1",
            created_at="1970-01-01 00:08:20+00",
            message="MediaWiki import",
            etymology=None,
            rafsi=None,
            mw_revid="900",
        ),
        _row(
            version_id="104",
            definition_id="13",
            langid="1",
            valsiid="31",
            definition="native current",
            notes=None,
            selmaho=None,
            jargon=None,
            gloss_keywords="[]",
            place_keywords="[]",
            user_id="1",
            created_at="1970-01-01 00:10:00+00",
            message="Initial version",
            etymology=None,
            rafsi=None,
            mw_revid=None,
        ),
    )
    data = RawDictionaryDump(
        tables=tables, users=snapshot.users, scores=snapshot.scores
    )
    events = list(project(data, export_date="2026-09-13"))
    source_ids = {event.source_id for event in events}
    assert "valsi=30" not in source_ids
    assert "definition=12 version=0" not in source_ids
    assert "definition=12 version=103" not in source_ids
    assert "valsi=31" in source_ids
    assert "definition=13 version=0" in source_ids
    coverage = events[-1].changes["_meta/dict/coverage.toml"]
    assert "mirror_definitions_excluded = 1" in coverage
    assert "mirror_versions_excluded = 1" in coverage


def test_project_moves_definition_from_baseline_language_to_current_language() -> None:
    snapshot = _snapshot()
    tables = dict(snapshot.tables)
    tables["languages"] = (
        *tables["languages"],
        _row(langid="2", tag="fr"),
    )
    definitions = list(tables["definitions"])
    definitions[0] = {**definitions[0], "langid": "2"}
    tables["definitions"] = tuple(definitions)
    versions = list(tables["definition_versions"])
    versions[1] = {**versions[1], "langid": "2"}
    tables["definition_versions"] = tuple(versions)
    scores = ({**snapshot.scores[0], "langid": "2"},)
    data = RawDictionaryDump(tables=tables, users=snapshot.users, scores=scores)
    events = list(project(data, export_date="2026-09-13"))
    baseline = next(
        event for event in events if event.source_id == "definition=10 version=0"
    )
    edit = next(
        event for event in events if event.source_id == "definition=10 version=101"
    )
    assert "dict/broda/en-10.md" in baseline.changes
    assert "dict/broda/fr-10.md" in edit.changes
    assert edit.deletions == ("dict/broda/en-10.md",)
    assert edit.trailers["Moved-From"] == "dict/broda/en-10.md"


def test_project_keeps_intermediate_language_until_later_move() -> None:
    snapshot = _snapshot()
    tables = dict(snapshot.tables)
    tables["languages"] = (
        *tables["languages"],
        _row(langid="2", tag="fr"),
    )
    versions = list(tables["definition_versions"])
    versions[0] = {**versions[0], "langid": "2"}
    versions.insert(
        1,
        {
            **versions[1],
            "version_id": "105",
            "langid": "2",
            "definition": "intermediate text",
            "notes": "intermediate notes",
            "created_at": "1970-01-01 00:04:10+00",
        },
    )
    tables["definition_versions"] = tuple(versions)
    data = RawDictionaryDump(
        tables=tables, users=snapshot.users, scores=snapshot.scores
    )
    events = list(project(data, export_date="2026-09-13"))
    intermediate = next(
        event for event in events if event.source_id == "definition=10 version=105"
    )
    final = next(
        event for event in events if event.source_id == "definition=10 version=101"
    )
    assert "dict/broda/fr-10.md" in intermediate.changes
    assert intermediate.deletions == ()
    assert final.deletions == ("dict/broda/fr-10.md",)
    assert final.trailers["Moved-From"] == "dict/broda/fr-10.md"


def test_project_accepts_a_null_text_block_as_empty_comment_content() -> None:
    snapshot = _snapshot()
    tables = dict(snapshot.tables)
    tables["threads"] = (
        _row(threadid="1", valsiid="20", natlangwordid=None, definitionid="10"),
    )
    tables["comments"] = (
        _row(
            commentid="1",
            threadid="1",
            parentid=None,
            userid="1",
            commentnum="1",
            time="350",
            subject="Empty",
            content='[{"type":"text","data":null}]',
            plain_content="",
        ),
    )
    data = RawDictionaryDump(
        tables=tables, users=snapshot.users, scores=snapshot.scores
    )
    events = list(project(data, export_date="2026-09-13"))
    comment = next(event for event in events if event.source_id == "comment=1")
    assert "Empty" in comment.changes["dict/broda/comments.md"]


def test_jbovlaste_diff_reports_old_only_and_text_changes_without_merging() -> None:
    current = _snapshot()
    old_tables = {
        name: ()
        for name in (
            "languages",
            "valsitypes",
            "valsi",
            "definitions",
            "comments",
            "etymology",
            "example",
            "natlangwords",
            "pages",
            "threads",
            "keywordmapping",
        )
    }
    old_tables["valsi"] = (_row(valsiid="20", word="changed", time="100", rafsi="bro"),)
    old_tables["definitions"] = (
        _row(
            definitionid="9",
            definition="old only",
            notes=None,
            time="90",
            selmaho=None,
            jargon=None,
        ),
    )
    older = RawDictionaryDump(tables=old_tables, users=(), scores=())
    rendered = jbovlaste_diff(current, older)
    assert "valsi,20,different,word" in rendered
    assert "definitions,9,only-jbovlaste," in rendered


def test_ingest_dictionary_exports_writes_seven_internal_digest_manifests(
    tmp_path: Path,
) -> None:
    from jbomohi_tools.project.dictionary import LENSISKU_COPY_COLUMNS

    export = tmp_path / "export"
    export.mkdir()
    (export / "lensisku-schema.sql").write_text("-- schema only\n", encoding="utf-8")
    (export / "lensisku-public-data.sanitized-v3.sql").write_text(
        _dump(LENSISKU_COPY_COLUMNS, {}), encoding="utf-8"
    )
    (export / "lensisku-users-public.csv").write_text(
        "userid,username,realname,url,personal,created_at,role,disabled\n",
        encoding="utf-8",
    )
    (export / "lensisku-definition-scores.csv").write_text(
        "definitionid,valsiid,langid,score,votes,last_vote_time\n",
        encoding="utf-8",
    )
    (export / "jbovlaste-public.sanitized.sql.gz").write_bytes(
        gzip.compress(_dump(JBOVLASTE_COPY_COLUMNS, {}).encode())
    )
    (export / "jbovlaste-users-public.csv").write_text(
        "userid,username,realname,url,personal\n", encoding="utf-8"
    )
    (export / "jbovlaste-definition-scores.csv").write_text(
        "definitionid,valsiid,langid,score,votes,last_vote_time\n",
        encoding="utf-8",
    )
    archive = tmp_path / "archive"
    report = ingest_dictionary_exports(archive, export, "2026-09-13")
    assert len(report.manifests) == 7
    for path in report.manifests:
        manifest = ArchiveManifest.load(path)
        assert manifest.kind == "db-export"
        assert manifest.origin == "operator export 2026-09-13"
        assert object_path(archive, manifest.sha256).is_file()


class _FeedClient:
    def __init__(self, documents: list[dict[str, object]]) -> None:
        self.documents = documents
        self.params: list[dict[str, str]] = []

    def query(self, params: dict[str, str]) -> FeedResponse:
        self.params.append(dict(params))
        document = self.documents.pop(0)
        suffix = f"&after={params['after']}" if "after" in params else ""
        return FeedResponse(
            f"https://lensisku.lojban.org/api/jbovlaste/changes?limit=100{suffix}",
            json.dumps(document, separators=(",", ":")).encode(),
            Message(),
        )


def test_changes_feed_archives_cursor_pages_and_returns_resume_cursor(
    tmp_path: Path,
) -> None:
    client = _FeedClient(
        [
            {
                "changes": [
                    {"change_type": "definition", "time": 200, "definition_id": 3}
                ],
                "next_cursor": "cursor-1",
                "total": 0,
            },
            {"changes": [], "next_cursor": None, "total": 0},
        ]
    )
    report = fetch_changes(
        tmp_path,
        client=client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert report.pages == 2
    assert report.changes == 1
    assert report.next_cursor is None
    assert client.params[1]["after"] == "cursor-1"
    assert all(
        ArchiveManifest.load(path).kind == "changes-feed" for path in report.manifests
    )


def test_changes_feed_rejects_a_stalled_cursor(tmp_path: Path) -> None:
    client = _FeedClient(
        [
            {
                "changes": [{"change_type": "valsi", "time": 200}],
                "next_cursor": "same",
                "total": 0,
            }
        ]
    )
    with pytest.raises(DictionaryFetchError, match="did not advance"):
        fetch_changes(
            tmp_path,
            since="same",
            client=client,
            now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
        )


def test_changes_feed_rejects_an_injected_off_origin_response(tmp_path: Path) -> None:
    class OffOrigin:
        def query(self, params):
            return FeedResponse(
                "https://example.invalid/api/jbovlaste/changes",
                b'{"changes":[],"next_cursor":null}',
                Message(),
            )

    with pytest.raises(DictionaryFetchError, match="escaped its origin"):
        fetch_changes(
            tmp_path,
            client=OffOrigin(),
            now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
        )
