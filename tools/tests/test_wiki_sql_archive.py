from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.archive.manifest import ArchiveError, ArchiveManifest, object_path
from jbomohi_tools.archive.wiki_sql import (
    WIKI_SQL_TABLES,
    ingest_wiki_sql_export,
    inspect_wiki_sql_export,
)


def write_export(root: Path) -> None:
    root.mkdir()
    sql = bytearray(b"/*!40101 SET NAMES binary */;\n")
    for table in sorted(WIKI_SQL_TABLES):
        sql.extend(f"CREATE TABLE `{table}` (\n".encode())
        sql.extend(b"  `id` int NOT NULL\n")
        sql.extend(b") ENGINE=InnoDB DEFAULT CHARSET=binary;\n")
        sql.extend(f"INSERT INTO `{table}` VALUES (1);\n".encode())
    (root / "wiki-content.sql.gz").write_bytes(gzip.compress(bytes(sql)))
    (root / "wiki-users.tsv.gz").write_bytes(
        gzip.compress(
            b"user_id\tuser_name\tuser_real_name\tuser_registration\tuser_editcount\n"
            b"1\tGleki\tGleki Arxokuna\t20120927162528\t38304\n"
        )
    )


def test_inspect_and_ingest_wiki_operator_export(tmp_path: Path) -> None:
    export = tmp_path / "export"
    archive = tmp_path / "archive"
    write_export(export)
    inventory = inspect_wiki_sql_export(export)
    assert inventory.table_rows == {table: 1 for table in sorted(WIKI_SQL_TABLES)}
    assert inventory.users == 1

    report = ingest_wiki_sql_export(archive, export, "2026-09-15")
    assert report.inventory == inventory
    assert len(report.manifests) == 2
    for path in report.manifests:
        manifest = ArchiveManifest.load(path)
        assert manifest.source == "wiki"
        assert manifest.kind == "db-export"
        assert manifest.origin == "operator export 2026-09-15"
        assert manifest.fetched_at == datetime(2026, 9, 15, tzinfo=UTC)
        assert object_path(archive, manifest.sha256).is_file()
        assert "temporary transfer location intentionally omitted" in manifest.notes
    assert ingest_wiki_sql_export(archive, export, "2026-09-15").manifests == (
        report.manifests
    )


def test_wiki_operator_export_rejects_private_or_missing_tables(
    tmp_path: Path,
) -> None:
    export = tmp_path / "private"
    write_export(export)
    content = gzip.decompress((export / "wiki-content.sql.gz").read_bytes())
    content += b"CREATE TABLE `user` (\n  `user_password` blob\n) ENGINE=InnoDB;\n"
    (export / "wiki-content.sql.gz").write_bytes(gzip.compress(content))
    with pytest.raises(ArchiveError, match="forbidden private table user"):
        inspect_wiki_sql_export(export)

    missing = tmp_path / "missing"
    write_export(missing)
    content = gzip.decompress((missing / "wiki-content.sql.gz").read_bytes())
    content = content.replace(b"CREATE TABLE `text` (", b"CREATE TABLE `absent` (")
    content = content.replace(b"INSERT INTO `text`", b"INSERT INTO `absent`")
    (missing / "wiki-content.sql.gz").write_bytes(gzip.compress(content))
    with pytest.raises(ArchiveError, match="unexpected table absent"):
        inspect_wiki_sql_export(missing)


def test_wiki_operator_export_rejects_private_user_columns(tmp_path: Path) -> None:
    export = tmp_path / "export"
    write_export(export)
    (export / "wiki-users.tsv.gz").write_bytes(
        gzip.compress(
            b"user_id\tuser_name\tuser_email\n1\tGleki\tprivate@example.org\n"
        )
    )
    with pytest.raises(ArchiveError, match="unexpected columns"):
        inspect_wiki_sql_export(export)
