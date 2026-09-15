"""Validate and ingest the sanitized MediaWiki operator export."""

from __future__ import annotations

import gzip
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .manifest import ArchiveError, ArchiveManifest, store_file

WIKI_SQL_TABLES = frozenset(
    {
        "actor",
        "archive",
        "category",
        "categorylinks",
        "change_tag",
        "change_tag_def",
        "comment",
        "content",
        "content_models",
        "image",
        "interwiki",
        "log_search",
        "logging",
        "oldimage",
        "page",
        "page_props",
        "page_restrictions",
        "redirect",
        "revision",
        "revision_actor_temp",
        "revision_comment_temp",
        "site_stats",
        "slot_roles",
        "slots",
        "text",
    }
)
FORBIDDEN_WIKI_TABLES = frozenset(
    {
        "bot_passwords",
        "filearchive",
        "ip_changes",
        "ipblocks",
        "ipblocks_restrictions",
        "objectcache",
        "recentchanges",
        "uploadstash",
        "user",
        "user_former_groups",
        "user_newtalk",
        "user_properties",
        "watchlist",
        "watchlist_expiry",
    }
)
WIKI_USER_COLUMNS = (
    "user_id",
    "user_name",
    "user_real_name",
    "user_registration",
    "user_editcount",
)
_CREATE = re.compile(rb"^CREATE TABLE `([A-Za-z0-9_]+)` \($")
_INSERT = re.compile(rb"^INSERT INTO `([A-Za-z0-9_]+)` VALUES \(.*\);$")
_MAX_SQL_LINE = 128 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class WikiSqlInventory:
    table_rows: dict[str, int]
    users: int


@dataclass(frozen=True, slots=True)
class WikiSqlIngestReport:
    manifests: tuple[Path, ...]
    inventory: WikiSqlInventory


def _sql_inventory(path: Path) -> dict[str, int]:
    tables: set[str] = set()
    rows: Counter[str] = Counter()
    try:
        with gzip.open(path, "rb") as stream:
            while True:
                line = stream.readline(_MAX_SQL_LINE + 1)
                if not line:
                    break
                if len(line) > _MAX_SQL_LINE:
                    raise ArchiveError(
                        f"MediaWiki SQL statement exceeds {_MAX_SQL_LINE} bytes"
                    )
                if not line.endswith(b"\n"):
                    raise ArchiveError(
                        "MediaWiki SQL dump has an unterminated final line"
                    )
                raw = line.removesuffix(b"\n")
                created = _CREATE.fullmatch(raw)
                inserted = _INSERT.fullmatch(raw)
                matched = created or inserted
                if matched is None:
                    continue
                table = matched.group(1).decode("ascii")
                if table in FORBIDDEN_WIKI_TABLES or table.startswith("cu_"):
                    raise ArchiveError(
                        f"MediaWiki SQL dump contains forbidden private table {table}"
                    )
                if table not in WIKI_SQL_TABLES:
                    raise ArchiveError(
                        f"MediaWiki SQL dump contains unexpected table {table}"
                    )
                if created is not None:
                    tables.add(table)
                else:
                    rows[table] += 1
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise ArchiveError(f"cannot read MediaWiki SQL dump {path}: {exc}") from exc
    missing = sorted(WIKI_SQL_TABLES - tables)
    if missing:
        raise ArchiveError(
            f"MediaWiki SQL dump is missing tables: {', '.join(missing)}"
        )
    empty = sorted(table for table in WIKI_SQL_TABLES if rows[table] == 0)
    if empty:
        raise ArchiveError(f"MediaWiki SQL dump has no rows for: {', '.join(empty)}")
    return {table: rows[table] for table in sorted(WIKI_SQL_TABLES)}


def _users_inventory(path: Path) -> int:
    try:
        with gzip.open(path, "rb") as stream:
            header = stream.readline().removesuffix(b"\n").removesuffix(b"\r")
            try:
                columns = tuple(value.decode("ascii") for value in header.split(b"\t"))
            except UnicodeDecodeError as exc:
                raise ArchiveError("MediaWiki users TSV header is not ASCII") from exc
            if columns != WIKI_USER_COLUMNS:
                raise ArchiveError(
                    "MediaWiki users TSV has unexpected columns: " + ", ".join(columns)
                )
            seen: set[int] = set()
            for row_number, line in enumerate(stream, 2):
                raw = line.removesuffix(b"\n").removesuffix(b"\r")
                values = raw.split(b"\t")
                if len(values) != len(WIKI_USER_COLUMNS):
                    raise ArchiveError(
                        f"MediaWiki users TSV row {row_number} has {len(values)} fields"
                    )
                try:
                    user_id = int(values[0])
                    values[1].decode("utf-8")
                    values[2].decode("utf-8")
                    registration = values[3].decode("ascii")
                    editcount = values[4].decode("ascii")
                except (UnicodeDecodeError, ValueError) as exc:
                    raise ArchiveError(
                        f"MediaWiki users TSV row {row_number} is malformed"
                    ) from exc
                if (
                    user_id < 1
                    or user_id in seen
                    or not values[1]
                    or (
                        registration != "NULL"
                        and not re.fullmatch(r"[0-9]{14}", registration)
                    )
                    or not re.fullmatch(r"[0-9]+", editcount)
                    or b"\0" in raw
                ):
                    raise ArchiveError(
                        f"MediaWiki users TSV row {row_number} is malformed"
                    )
                seen.add(user_id)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise ArchiveError(f"cannot read MediaWiki users TSV {path}: {exc}") from exc
    if not seen:
        raise ArchiveError("MediaWiki users TSV has no data rows")
    return len(seen)


def inspect_wiki_sql_export(export_directory: Path) -> WikiSqlInventory:
    content = export_directory / "wiki-content.sql.gz"
    users = export_directory / "wiki-users.tsv.gz"
    missing = [path.name for path in (content, users) if not path.is_file()]
    if missing:
        raise ArchiveError(
            f"MediaWiki export directory is missing: {', '.join(missing)}"
        )
    return WikiSqlInventory(_sql_inventory(content), _users_inventory(users))


def ingest_wiki_sql_export(
    archive: Path, export_directory: Path, export_date: str
) -> WikiSqlIngestReport:
    """Validate then archive the two sanitized MediaWiki export components."""

    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", export_date):
        raise ArchiveError("MediaWiki export date must be YYYY-MM-DD")
    try:
        export_day = datetime.fromisoformat(export_date).replace(tzinfo=UTC)
    except ValueError as exc:
        raise ArchiveError("MediaWiki export date must be YYYY-MM-DD") from exc
    inventory = inspect_wiki_sql_export(export_directory)
    components = (
        ("wiki-content.sql.gz", inventory.table_rows),
        ("wiki-users.tsv.gz", {"users": inventory.users}),
    )
    manifests: list[Path] = []
    for name, counts in components:
        stored = store_file(archive, export_directory / name)
        manifest = ArchiveManifest(
            source="wiki",
            kind="db-export",
            origin=f"operator export {export_date}",
            fetched_at=export_day,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={"from": export_date, "to": export_date, "counts": counts},
            notes=(
                f"Sanitized MediaWiki operator export component {name}; "
                "temporary transfer location intentionally omitted."
            ),
        )
        path = (
            archive
            / "manifests"
            / "wiki"
            / "db-export"
            / f"{name}-{stored.sha256[:12]}.toml"
        )
        if path.exists():
            if ArchiveManifest.load(path) != manifest:
                raise ArchiveError(
                    f"existing MediaWiki export manifest disagrees: {path}"
                )
        else:
            manifest.write(path)
        manifests.append(path)
    return WikiSqlIngestReport(tuple(manifests), inventory)
