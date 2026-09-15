"""Strict byte-level loading and projection for the historical Tiki export."""

from __future__ import annotations

import csv
import gzip
import heapq
import html
import io
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Literal

from ..git import Event, Identity
from . import sqldump
from .dictionary import slug


class TikiParseError(ValueError):
    """The Tiki export violates its public schema or SQL encoding."""


TIKI_INSERT_COLUMNS: dict[str, tuple[str, ...]] = {
    "tiki_pages": (
        "page_id",
        "pageName",
        "pageSlug",
        "hits",
        "data",
        "description",
        "lastModif",
        "comment",
        "version",
        "user",
        "ip",
        "flag",
        "points",
        "votes",
        "cache",
        "wiki_cache",
        "cache_timestamp",
        "pageRank",
        "creator",
        "page_size",
        "lang",
        "lockedby",
        "is_html",
        "created",
        "wysiwyg",
        "wiki_authors_style",
        "version_minor",
        "comments_enabled",
        "keywords",
    ),
    "tiki_history": (
        "historyId",
        "pageName",
        "version",
        "version_minor",
        "lastModif",
        "description",
        "user",
        "ip",
        "comment",
        "data",
        "type",
        "is_html",
    ),
    "tiki_comments": (
        "threadId",
        "object",
        "objectType",
        "parentId",
        "userName",
        "commentDate",
        "hits",
        "type",
        "points",
        "votes",
        "average",
        "title",
        "data",
        "hash",
        "email",
        "website",
        "user_ip",
        "summary",
        "smiley",
        "message_id",
        "in_reply_to",
        "comment_rating",
        "archived",
        "approved",
        "locked",
    ),
    "tiki_actionlog": (
        "actionId",
        "action",
        "lastModif",
        "object",
        "objectType",
        "user",
        "ip",
        "comment",
        "categId",
        "client",
        "log",
    ),
}

FORBIDDEN_TIKI_TABLES = frozenset(
    {
        "tiki_forums",
        "users_users",
        "tiki_user_preferences",
        "tiki_page_footnotes",
        "tiki_comments_queue",
        "tiki_forums_queue",
        "tiki_semaphores",
    }
)

_INSERT = re.compile(rb"^INSERT INTO `([A-Za-z0-9_]+)` VALUES (.*);$")
_CREATE = re.compile(rb"^CREATE TABLE `([A-Za-z0-9_]+)` \($")
_COLUMN = re.compile(rb"^  `([^`]+)` ")
_MAX_SQL_LINE = 128 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RawTikiDump:
    tables: Mapping[str, tuple[Mapping[str, bytes | None], ...]]


@dataclass(frozen=True, slots=True)
class TikiUsers:
    logins: frozenset[str]
    display_names: Mapping[str, str]


CharacterEncoding = Literal["latin1-transcoded", "utf8"]


@dataclass(frozen=True, slots=True)
class _PageVersion:
    title: str
    version: int
    timestamp: datetime
    user: str
    comment: str
    content: str
    is_html: bool
    encoding: str
    current: bool
    source_id: str
    stable_id: int


@dataclass(frozen=True, slots=True)
class _Comment:
    thread_id: int
    object_name: str
    object_type: str
    parent_id: int
    username: str
    timestamp: datetime
    title: str
    content: str
    message_id: str
    in_reply_to: str
    encoding: str


@dataclass(frozen=True, slots=True)
class _Operation:
    timestamp: datetime
    stable_key: str
    kind: str
    value: _PageVersion | _Comment


@contextmanager
def _stream(path: Path) -> Iterator[BinaryIO]:
    try:
        with path.open("rb") as probe:
            compressed = probe.read(2) == b"\x1f\x8b"
        with gzip.open(path, "rb") if compressed else path.open("rb") as stream:
            yield stream
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise TikiParseError(f"cannot read Tiki SQL dump {path}: {exc}") from exc


def _line(stream: BinaryIO, path: Path) -> bytes | None:
    raw = stream.readline(_MAX_SQL_LINE + 1)
    if not raw:
        return None
    if len(raw) > _MAX_SQL_LINE:
        raise TikiParseError(
            f"Tiki SQL dump {path} contains a statement over {_MAX_SQL_LINE} bytes"
        )
    if raw and not raw.endswith(b"\n"):
        raise TikiParseError(f"Tiki SQL dump {path} has an unterminated final line")
    return raw.removesuffix(b"\n")


def parse_insert_values(
    body: bytes, context: str = "Tiki INSERT"
) -> tuple[bytes | None, ...]:
    """Parse one --skip-extended-insert VALUES tuple without decoding text."""

    return sqldump.parse_insert_values(body, context, TikiParseError)


def load_tiki_dump(
    path: Path,
    expected: Mapping[str, Sequence[str]] = TIKI_INSERT_COLUMNS,
    *,
    forbidden: frozenset[str] = FORBIDDEN_TIKI_TABLES,
) -> RawTikiDump:
    """Load selected one-row MySQL INSERT statements and reject private tables."""

    wanted = {name: tuple(columns) for name, columns in expected.items()}
    rows: dict[str, list[Mapping[str, bytes | None]]] = {name: [] for name in wanted}
    schemas: dict[str, tuple[str, ...]] = {}
    schema_table: str | None = None
    schema_columns: list[str] = []
    with _stream(path) as stream:
        while True:
            raw = _line(stream, path)
            if raw is None:
                break
            created = _CREATE.fullmatch(raw)
            if created is not None:
                schema_table = created.group(1).decode("ascii")
                schema_columns = []
                continue
            if schema_table is not None:
                column = _COLUMN.match(raw)
                if column is not None:
                    schema_columns.append(column.group(1).decode("ascii"))
                if raw.startswith(b") ENGINE="):
                    if schema_table in wanted:
                        actual = tuple(schema_columns)
                        if actual != wanted[schema_table]:
                            raise TikiParseError(
                                f"Tiki SQL dump {path} has unexpected schema for "
                                f"{schema_table}: {', '.join(actual)}"
                            )
                        schemas[schema_table] = actual
                    schema_table = None
                    schema_columns = []
                continue
            matched = _INSERT.fullmatch(raw)
            if matched is None:
                continue
            table = matched.group(1).decode("ascii")
            if table in forbidden:
                raise TikiParseError(
                    f"Tiki SQL dump {path} contains forbidden private table {table}"
                )
            columns = wanted.get(table)
            if columns is None:
                continue
            values = parse_insert_values(matched.group(2), f"{path}: {table}")
            if len(values) != len(columns):
                raise TikiParseError(
                    f"Tiki SQL dump {path} has {len(values)} values for {table}; "
                    f"expected {len(columns)}"
                )
            rows[table].append(dict(zip(columns, values, strict=True)))
    missing_schemas = sorted(wanted.keys() - schemas.keys())
    if missing_schemas:
        raise TikiParseError(
            f"Tiki SQL dump {path} is missing schemas for: {', '.join(missing_schemas)}"
        )
    missing = sorted(name for name, items in rows.items() if not items)
    if missing:
        raise TikiParseError(
            f"Tiki SQL dump {path} has no rows for: {', '.join(missing)}"
        )
    return RawTikiDump({name: tuple(items) for name, items in rows.items()})


def decode_character_text(
    value: bytes,
    context: str,
    mode: CharacterEncoding,
    *,
    allow_nul: bool = False,
) -> tuple[str, str]:
    """Decode a character column under the selected export connection mode."""

    if mode == "utf8":
        try:
            decoded = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TikiParseError(f"{context}: character column is not UTF-8") from exc
        encoding = "utf-8"
    elif mode == "latin1-transcoded":
        try:
            decoded = value.decode("cp1252")
            encoding = "cp1252"
        except UnicodeDecodeError:
            decoded = value.decode("iso-8859-1")
            encoding = "iso-8859-1-c1"
    else:
        raise TikiParseError(f"{context}: unknown character decoding mode {mode!r}")
    if "\0" in decoded and not allow_nul:
        raise TikiParseError(f"{context}: decoded text contains a NUL")
    return decoded, encoding


def decode_history_blob(
    value: bytes, context: str, *, allow_nul: bool = False
) -> tuple[str, str]:
    """Decode raw historical blobs without replacing any byte."""

    try:
        decoded = value.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        try:
            decoded = value.decode("cp1252")
            encoding = "cp1252"
        except UnicodeDecodeError:
            decoded = value.decode("iso-8859-1")
            encoding = "iso-8859-1-c1"
    if "\0" in decoded and not allow_nul:
        raise TikiParseError(f"{context}: decoded blob contains a NUL")
    return decoded, encoding


def page_text(
    value: bytes,
    context: str,
    mode: CharacterEncoding,
    *,
    allow_nul: bool = False,
) -> tuple[str, str]:
    text, encoding = decode_character_text(value, context, mode, allow_nul=allow_nul)
    return html.unescape(text), encoding


def is_anonymous_tiki_user(value: str) -> bool:
    return not value or value == "Anonymous"


def _load_tsv(
    path: Path, columns: Sequence[str]
) -> tuple[Mapping[str, bytes | None], ...]:
    rows: list[Mapping[str, bytes | None]] = []
    with _stream(path) as stream:
        header = _line(stream, path)
        if header is None or header.split(b"\t") != [item.encode() for item in columns]:
            raise TikiParseError(f"Tiki TSV {path} has unexpected columns")
        line_number = 1
        while True:
            raw = _line(stream, path)
            if raw is None:
                break
            line_number += 1
            fields = raw.split(b"\t")
            if len(fields) != len(columns):
                raise TikiParseError(
                    f"Tiki TSV {path}:{line_number} has {len(fields)} fields; "
                    f"expected {len(columns)}"
                )
            rows.append(
                {
                    name: None if value == b"NULL" else value
                    for name, value in zip(columns, fields, strict=True)
                }
            )
    return tuple(rows)


def load_tiki_users(
    users_path: Path,
    preferences_path: Path,
    *,
    character_encoding: CharacterEncoding,
) -> TikiUsers:
    """Load public login and consent-filtered real-name metadata."""

    users = _load_tsv(users_path, ("userId", "login"))
    preferences = _load_tsv(preferences_path, ("user", "prefName", "value"))
    logins: set[str] = set()
    for row_number, row in enumerate(users, 1):
        raw_login = row["login"]
        if raw_login is None:
            raise TikiParseError(f"Tiki users row {row_number} has a null login")
        login, _encoding = decode_character_text(
            raw_login, f"Tiki users row {row_number}", character_encoding
        )
        if login in logins:
            raise TikiParseError(f"duplicate Tiki login {login!r}")
        logins.add(login)

    by_user: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(preferences, 1):
        if row["user"] is None or row["prefName"] is None or row["value"] is None:
            continue
        user, _ = decode_character_text(
            row["user"], f"Tiki preference row {row_number} user", character_encoding
        )
        name, _ = decode_character_text(
            row["prefName"],
            f"Tiki preference row {row_number} name",
            character_encoding,
        )
        value, _ = decode_character_text(
            row["value"],
            f"Tiki preference row {row_number} value",
            character_encoding,
        )
        previous = by_user.setdefault(user, {}).get(name)
        if previous is not None and previous != value:
            raise TikiParseError(f"conflicting Tiki preference {name!r} for {user!r}")
        by_user[user][name] = value
    display_names = {
        user: values["realName"]
        for user, values in by_user.items()
        if values.get("realName")
        and values.get("user_information", "public") != "private"
    }
    return TikiUsers(frozenset(logins), display_names)


def _required(row: Mapping[str, bytes | None], name: str, context: str) -> bytes:
    value = row.get(name)
    if value is None:
        raise TikiParseError(f"{context}: {name} must not be null")
    return value


def _integer(
    row: Mapping[str, bytes | None], name: str, context: str, *, minimum: int = 0
) -> int:
    value = _required(row, name, context)
    if not re.fullmatch(rb"-?[0-9]+", value):
        raise TikiParseError(f"{context}: {name} is not an integer")
    parsed = int(value)
    if parsed < minimum:
        raise TikiParseError(f"{context}: {name} must be at least {minimum}")
    return parsed


def _optional_integer(
    row: Mapping[str, bytes | None], name: str, context: str
) -> int | None:
    if row.get(name) is None:
        return None
    return _integer(row, name, context)


def _time(row: Mapping[str, bytes | None], name: str, context: str) -> datetime:
    seconds = _integer(row, name, context)
    try:
        return datetime.fromtimestamp(seconds, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise TikiParseError(f"{context}: {name} is outside the UTC range") from exc


def _character(
    row: Mapping[str, bytes | None],
    name: str,
    context: str,
    mode: CharacterEncoding,
    *,
    nullable: bool = True,
) -> tuple[str, str]:
    value = row.get(name)
    if value is None:
        if nullable:
            return "", "null"
        raise TikiParseError(f"{context}: {name} must not be null")
    return decode_character_text(value, f"{context}: {name}", mode)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _identity(username: str) -> Identity:
    if is_anonymous_tiki_user(username):
        return Identity.anonymous("tiki.lojban.org")
    return Identity.namespaced("tiki.lojban.org", username)


def _display(username: str, users: TikiUsers) -> str:
    if is_anonymous_tiki_user(username):
        return "anonymous"
    return users.display_names.get(username, username)


def _one_line(value: str, context: str) -> str:
    if any(character in value for character in "\r\n\0"):
        raise TikiParseError(f"{context} must be one line")
    return value


def _summary(label: str, suffix: str) -> str:
    clean = " ".join(label.split())
    tail = f" {suffix}"
    budget = 72 - len("tiki: ") - len(tail)
    shown = clean if len(clean) <= budget else clean[: max(1, budget - 1)] + "…"
    return f"{shown}{tail}"


def _csv_text(columns: Sequence[str], rows: Sequence[Mapping[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


_CHARACTER_FIELDS: dict[str, tuple[str, ...]] = {
    "tiki_pages": (
        "pageName",
        "pageSlug",
        "data",
        "description",
        "comment",
        "user",
        "ip",
        "flag",
        "creator",
        "lang",
        "lockedby",
        "wysiwyg",
        "wiki_authors_style",
        "comments_enabled",
        "keywords",
    ),
    "tiki_history": ("pageName", "description", "user", "ip", "comment", "type"),
    "tiki_comments": (
        "object",
        "objectType",
        "userName",
        "type",
        "title",
        "data",
        "hash",
        "email",
        "website",
        "user_ip",
        "summary",
        "smiley",
        "message_id",
        "in_reply_to",
        "archived",
        "approved",
        "locked",
    ),
    "tiki_actionlog": (
        "action",
        "object",
        "objectType",
        "user",
        "ip",
        "comment",
        "client",
        "log",
    ),
}


def looks_like_stored_mojibake(text: str) -> bool:
    """True when the text is a latin-1 reading of UTF-8 bytes.

    The 2026-09-15 utf8mb4 re-export shows that some rows hold mojibake in the
    database itself, from an earlier bad migration rather than from the export
    client. SPEC.md 3.2.5(c) never repairs characters, so this only counts
    them, and it counts them by definition rather than by looking for `Ã©`:
    text that re-reads as different, valid UTF-8 when taken as latin-1 bytes
    is exactly what a latin-1 reading of UTF-8 is.
    """

    try:
        candidate = text.encode("latin-1")
    except UnicodeEncodeError:
        return False
    try:
        repaired = candidate.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return repaired != text


def _fidelity(
    data: RawTikiDump, mode: CharacterEncoding
) -> tuple[dict[str, dict[str, int]], dict[str, Counter[str]]]:
    row_counts: dict[str, dict[str, int]] = {}
    branch_counts: dict[str, Counter[str]] = {}
    for table, fields in _CHARACTER_FIELDS.items():
        questions = 0
        high_bytes = 0
        mojibake = 0
        branches: Counter[str] = Counter()
        for row_number, row in enumerate(data.tables[table], 1):
            values = [row[field] for field in fields if row.get(field) is not None]
            if any(b"?" in value for value in values if value is not None):
                questions += 1
            if any(
                any(byte >= 128 for byte in value)
                for value in values
                if value is not None
            ):
                high_bytes += 1
            row_is_mojibake = False
            for field in fields:
                value = row.get(field)
                if value is None:
                    continue
                text, encoding = decode_character_text(
                    value,
                    f"{table} row {row_number}: {field}",
                    mode,
                    allow_nul=True,
                )
                branches[encoding] += 1
                row_is_mojibake = row_is_mojibake or looks_like_stored_mojibake(text)
            if row_is_mojibake:
                mojibake += 1
            if table == "tiki_history" and row.get("data") is not None:
                _text, encoding = decode_history_blob(
                    _required(row, "data", f"{table} row {row_number}"),
                    f"{table} row {row_number}: data",
                    allow_nul=True,
                )
                branches[f"blob-{encoding}"] += 1
        row_counts[table] = {
            "question_rows": questions,
            "high_byte_rows": high_bytes,
            "stored_mojibake_rows": mojibake,
        }
        branch_counts[table] = branches
    return row_counts, branch_counts


def _page_version(
    row: Mapping[str, bytes | None],
    *,
    current: bool,
    mode: CharacterEncoding,
) -> _PageVersion:
    kind = "current page" if current else "history row"
    stable_field = "page_id" if current else "historyId"
    stable_id = _integer(row, stable_field, kind, minimum=1)
    context = f"Tiki {kind} {stable_id}"
    title, _ = _character(row, "pageName", context, mode, nullable=False)
    user, _ = _character(row, "user", context, mode)
    comment, _ = _character(row, "comment", context, mode)
    raw_content = row.get("data") or b""
    if current:
        content, encoding = page_text(
            raw_content, f"{context}: data", mode, allow_nul=True
        )
        source_id = f"tiki={slug(title)}@current"
    else:
        content, encoding = decode_history_blob(
            raw_content, f"{context}: data", allow_nul=True
        )
        content = html.unescape(content)
        source_id = f"tiki={slug(title)}@{_integer(row, 'version', context)}"
    return _PageVersion(
        title=title,
        version=_integer(row, "version", context),
        timestamp=_time(row, "lastModif", context),
        user=user,
        comment=comment,
        content=content,
        is_html=bool(_integer(row, "is_html", context)),
        encoding=encoding,
        current=current,
        source_id=source_id,
        stable_id=stable_id,
    )


def _comment(row: Mapping[str, bytes | None], mode: CharacterEncoding) -> _Comment:
    thread_id = _integer(row, "threadId", "Tiki comment", minimum=1)
    context = f"Tiki comment {thread_id}"
    object_name, _ = _character(row, "object", context, mode, nullable=False)
    object_type, _ = _character(row, "objectType", context, mode, nullable=False)
    username, _ = _character(row, "userName", context, mode)
    title, _ = _character(row, "title", context, mode)
    content, encoding = _character(row, "data", context, mode)
    message_id, _ = _character(row, "message_id", context, mode)
    in_reply_to, _ = _character(row, "in_reply_to", context, mode)
    for label, value in (
        ("object", object_name),
        ("objectType", object_type),
        ("message_id", message_id),
        ("in_reply_to", in_reply_to),
        ("title", title),
    ):
        _one_line(value, f"{context} {label}")
    return _Comment(
        thread_id=thread_id,
        object_name=object_name,
        object_type=object_type,
        parent_id=_optional_integer(row, "parentId", context) or 0,
        username=username,
        timestamp=_time(row, "commentDate", context),
        title=title,
        content=content,
        message_id=message_id,
        in_reply_to=in_reply_to,
        encoding=encoding,
    )


def _render_comment_file(comments: Sequence[_Comment], users: TikiUsers) -> str:
    parts: list[str] = []
    for item in comments:
        display = _display(item.username, users)
        login = "anonymous" if is_anonymous_tiki_user(item.username) else item.username
        parts.extend(
            [
                f"## {_iso(item.timestamp)} — {display} (@{login}) (post {item.thread_id})",
                "",
                f"Title: {item.title}",
            ]
        )
        if item.message_id:
            parts.append(f"Message-Id: {item.message_id}")
        if item.in_reply_to:
            parts.append(f"In-Reply-To: {item.in_reply_to}")
        parts.extend(["", item.content, ""])
    return "\n".join(parts)


def _forum_topic(
    item: _Comment, comments: Mapping[int, _Comment]
) -> tuple[int, int | None]:
    """Walk parentId to the topic root, retaining evidence for missing parents."""

    current = item
    seen = {item.thread_id}
    while current.parent_id:
        parent_id = current.parent_id
        if parent_id in seen:
            raise TikiParseError(
                f"Tiki forum parent cycle at post {item.thread_id}: {parent_id}"
            )
        seen.add(parent_id)
        parent = comments.get(parent_id)
        if parent is None:
            return current.thread_id, parent_id
        if parent.object_type != "forum" or parent.object_name != item.object_name:
            raise TikiParseError(
                f"Tiki forum post {item.thread_id} crosses object at parent {parent_id}"
            )
        current = parent
    return current.thread_id, None


def _toml_key(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


_TIKI_IMPORT_TEMPLATE = re.compile(
    r"\{\{\s*BPFK\s+Section\s+from\s+tiki\s*\|\s*([^|}]+)",
    re.IGNORECASE,
)


def migrated_title_map(
    tiki_titles: Sequence[str], mediawiki_pages: Mapping[str, str]
) -> dict[str, str]:
    """Map Tiki titles to MediaWiki by exact title or an import template."""

    available = set(tiki_titles)
    result = {title: title for title in available if title in mediawiki_pages}
    for mediawiki_title, content in mediawiki_pages.items():
        for matched in _TIKI_IMPORT_TEMPLATE.finditer(content):
            tiki_title = matched.group(1).strip()
            if tiki_title not in available:
                continue
            previous = result.get(tiki_title)
            if previous is not None and previous != mediawiki_title:
                raise TikiParseError(
                    f"Tiki title {tiki_title!r} maps to both {previous!r} "
                    f"and {mediawiki_title!r}"
                )
            result[tiki_title] = mediawiki_title
    return result


def project(
    data: RawTikiDump,
    users: TikiUsers,
    *,
    character_encoding: CharacterEncoding,
    migrated_titles: Mapping[str, str] | None = None,
) -> Iterator[Event]:
    """Project pages, WikiDiscuss posts, and page comments from one Tiki dump."""

    migrated = migrated_titles or {}
    fidelity_rows, fidelity_branches = _fidelity(data, character_encoding)

    all_histories = [
        _page_version(row, current=False, mode=character_encoding)
        for row in data.tables["tiki_history"]
    ]
    all_current_pages = [
        _page_version(row, current=True, mode=character_encoding)
        for row in data.tables["tiki_pages"]
    ]
    binary_versions = [
        item for item in (*all_histories, *all_current_pages) if "\0" in item.content
    ]
    histories = [item for item in all_histories if "\0" not in item.content]
    current_pages = [item for item in all_current_pages if "\0" not in item.content]
    current_by_title: dict[str, _PageVersion] = {}
    for item in current_pages:
        if item.title in current_by_title:
            raise TikiParseError(f"duplicate current Tiki page {item.title!r}")
        current_by_title[item.title] = item

    history_by_title: dict[str, list[_PageVersion]] = defaultdict(list)
    history_source_ids: set[str] = set()
    for item in histories:
        if item.source_id in history_source_ids:
            raise TikiParseError(f"duplicate Tiki history Source-Id {item.source_id!r}")
        history_source_ids.add(item.source_id)
        history_by_title[item.title].append(item)

    path_owner: dict[str, str] = {}
    for title in {*history_by_title, *current_by_title}:
        path = f"tiki/{slug(title)}.tiki"
        previous = path_owner.get(path)
        if previous is not None and previous != title:
            raise TikiParseError(
                f"Tiki page slug collision: {previous!r} and {title!r} -> {path}"
            )
        path_owner[path] = title

    comments = [
        _comment(row, character_encoding) for row in data.tables["tiki_comments"]
    ]
    included_comments: list[_Comment] = []
    wiki_discuss_posts = 0
    skipped_forum_posts: Counter[str] = Counter()
    page_comments = 0
    skipped_other_comments = 0
    unapproved_comments = 0
    null_parent_topics = 0
    raw_comments_by_id = {
        _integer(row, "threadId", "Tiki comment", minimum=1): row
        for row in data.tables["tiki_comments"]
    }
    for item in comments:
        raw = raw_comments_by_id[item.thread_id]
        approved, _ = _character(
            raw, "approved", f"Tiki comment {item.thread_id}", character_encoding
        )
        if approved and approved != "y":
            unapproved_comments += 1
            continue
        if item.object_type == "forum":
            if item.object_name == "1":
                if raw.get("parentId") is None:
                    null_parent_topics += 1
                wiki_discuss_posts += 1
                included_comments.append(item)
            else:
                skipped_forum_posts[item.object_name] += 1
        elif item.object_type == "wiki page":
            page_comments += 1
            included_comments.append(item)
        else:
            skipped_other_comments += 1

    # Forum 1 is the only projected forum (WikiDiscuss); ids 4 and 5 are the
    # test forum and mailing-list mirror respectively.
    forum_comments = {
        item.thread_id: item for item in comments if item.object_type == "forum"
    }
    forum_topics: dict[int, int] = {}
    dangling_forum: dict[int, int] = {}
    for item in included_comments:
        if item.object_type != "forum":
            continue
        topic_id, missing_parent = _forum_topic(item, forum_comments)
        forum_topics[item.thread_id] = topic_id
        if missing_parent is not None:
            dangling_forum[item.thread_id] = missing_parent

    remaining_history = {title: len(items) for title, items in history_by_title.items()}
    heap: list[tuple[datetime, str, int, _Operation]] = []
    sequence = 0

    def push(operation: _Operation) -> None:
        nonlocal sequence
        heapq.heappush(
            heap,
            (operation.timestamp, operation.stable_key, sequence, operation),
        )
        sequence += 1

    for item in histories:
        push(_Operation(item.timestamp, item.source_id, "page", item))
    for item in current_pages:
        if not history_by_title.get(item.title):
            push(_Operation(item.timestamp, item.source_id, "page", item))
    for item in included_comments:
        source_id = (
            f"tiki=forum/{item.thread_id}"
            if item.object_type == "forum"
            else f"tiki=comment/{item.thread_id}"
        )
        push(_Operation(item.timestamp, source_id, "comment", item))

    events: list[Event] = []
    seen_pages: set[str] = set()
    emitted_current: set[str] = set()
    thread_state: dict[str, list[_Comment]] = defaultdict(list)
    forced_final = 0
    while heap:
        _timestamp, _stable_key, _sequence, operation = heapq.heappop(heap)
        if operation.kind == "page":
            assert isinstance(operation.value, _PageVersion)
            item = operation.value
            path = f"tiki/{slug(item.title)}.tiki"
            trailers = {
                "Version": str(item.version),
            }
            if item.current:
                if item.title in emitted_current:
                    raise TikiParseError(
                        f"current Tiki page emitted twice: {item.title!r}"
                    )
                emitted_current.add(item.title)
                trailers["Page-Id"] = str(item.stable_id)
                history_times = [
                    history.timestamp
                    for history in history_by_title.get(item.title, ())
                ]
                if history_times and item.timestamp < max(history_times):
                    trailers["Ordering"] = "forced-final"
                    forced_final += 1
            else:
                trailers["History-Id"] = str(item.stable_id)
            events.append(
                Event(
                    source="tiki",
                    source_id=item.source_id,
                    event="created" if item.title not in seen_pages else "edited",
                    time_confidence="exact",
                    source_time=item.timestamp,
                    summary=_summary(
                        item.title, "current" if item.current else f"v{item.version}"
                    ),
                    author=_identity(item.user),
                    changes={path: item.content},
                    trailers=trailers,
                )
            )
            seen_pages.add(item.title)
            if not item.current:
                remaining_history[item.title] -= 1
                if remaining_history[item.title] == 0:
                    current = current_by_title.get(item.title)
                    if current is not None:
                        push(
                            _Operation(
                                current.timestamp, current.source_id, "page", current
                            )
                        )
            continue

        assert operation.kind == "comment" and isinstance(operation.value, _Comment)
        item = operation.value
        if item.object_type == "forum":
            topic_id = forum_topics[item.thread_id]
            path = f"tiki/forums/WikiDiscuss/{topic_id}.txt"
            source_id = f"tiki=forum/{item.thread_id}"
            suffix = f"forum post {item.thread_id}"
        else:
            topic_id = item.thread_id
            path = f"tiki/talk/{slug(item.object_name)}.txt"
            source_id = f"tiki=comment/{item.thread_id}"
            suffix = f"comment {item.thread_id}"
        thread_state[path].append(item)
        trailers = {"Thread-Id": str(item.thread_id)}
        if item.object_type == "forum":
            trailers["Topic-Id"] = str(topic_id)
        if item.message_id:
            trailers["Message-Id"] = item.message_id
        if item.in_reply_to:
            trailers["In-Reply-To"] = item.in_reply_to
        events.append(
            Event(
                source="tiki",
                source_id=source_id,
                event="comment",
                time_confidence="exact",
                source_time=item.timestamp,
                summary=_summary(item.object_name, suffix),
                author=_identity(item.username),
                changes={path: _render_comment_file(thread_state[path], users)},
                trailers=trailers,
            )
        )

    if len(emitted_current) != len(current_pages):
        missing = sorted(set(current_by_title) - emitted_current)
        raise TikiParseError(f"current Tiki pages were not emitted: {missing[:5]!r}")
    if not events:
        return

    all_history_by_title: dict[str, list[_PageVersion]] = defaultdict(list)
    for item in all_histories:
        all_history_by_title[item.title].append(item)
    all_current_by_title = {item.title: item for item in all_current_pages}
    all_titles = sorted({*all_history_by_title, *all_current_by_title})
    gaps = [
        {
            "source_id": "",
            "title": title,
            "path": f"tiki/{slug(title)}.tiki",
            "reason": "no current row; rename/deletion undocumented",
        }
        for title in all_titles
        if title not in all_current_by_title
    ]
    gaps.extend(
        {
            "source_id": item.source_id,
            "title": item.title,
            "path": f"tiki/{slug(item.title)}.tiki",
            "reason": "non-text page content (NUL bytes); preserved in archive object",
        }
        for item in sorted(binary_versions, key=lambda value: value.source_id)
    )
    gaps.extend(
        {
            "source_id": f"tiki=forum/{thread_id}",
            "title": f"WikiDiscuss post {thread_id}",
            "path": f"tiki/forums/WikiDiscuss/{forum_topics[thread_id]}.txt",
            "reason": f"forum parent {parent_id} absent from export",
        }
        for thread_id, parent_id in sorted(dangling_forum.items())
    )
    page_rows = []
    for title in all_titles:
        current = all_current_by_title.get(title)
        versions = all_history_by_title.get(title, ())
        page_rows.append(
            {
                "title": title,
                "path": f"tiki/{slug(title)}.tiki",
                "current_version": current.version if current else "",
                "current_source_id": current.source_id if current else "",
                "versions": len(versions) + (1 if current else 0),
                "migrated_to": migrated.get(title, ""),
            }
        )
    version_rows = [
        {
            "title": item.title,
            "source_id": item.source_id,
            "version": item.version,
            "time": _iso(item.timestamp),
            "user": "anonymous" if is_anonymous_tiki_user(item.user) else item.user,
            "display_name": _display(item.user, users),
            "is_html": str(item.is_html).lower(),
            "encoding": item.encoding,
            "current": str(item.current).lower(),
            "path": f"tiki/{slug(item.title)}.tiki",
        }
        for item in sorted(
            (*all_histories, *all_current_pages),
            key=lambda value: (value.title, value.timestamp, value.source_id),
        )
    ]

    history_by_key = {(item.title, item.version): item for item in all_histories}
    raw_current_by_id = {
        _integer(row, "page_id", "Tiki page", minimum=1): row
        for row in data.tables["tiki_pages"]
    }
    raw_history_by_id = {
        _integer(row, "historyId", "Tiki history", minimum=1): row
        for row in data.tables["tiki_history"]
    }
    current_collisions = 0
    ascii_content_differences = 0
    for current in all_current_pages:
        history = history_by_key.get((current.title, current.version))
        if history is None:
            continue
        current_collisions += 1
        raw_current = raw_current_by_id[current.stable_id].get("data") or b""
        raw_history = raw_history_by_id[history.stable_id].get("data") or b""
        if (
            all(byte < 128 for byte in raw_current + raw_history)
            and raw_current != raw_history
        ):
            ascii_content_differences += 1

    fidelity_note = (
        "latin1-transcoded export: non-latin1 characters in tiki_pages.data, "
        "tiki_comments, tiki_actionlog may be lost as '?'; tiki_history blobs exact "
        "where decoded as UTF-8; no characters repaired"
        if character_encoding == "latin1-transcoded"
        else (
            "utf8mb4 export: character columns decoded strictly as UTF-8; no "
            "characters repaired. The '?' in question_rows are stored in the "
            "database, not lost by an export client: the count is the same in "
            "the latin1-transcoded and utf8mb4 exports. stored_mojibake_rows "
            "counts rows whose text is a latin-1 reading of UTF-8 from an "
            "earlier migration; those bytes are published as the database "
            "holds them"
        )
    )
    coverage_lines = [
        'rename_delete_log = "unavailable"',
        f"tiki_text_fidelity = {json.dumps(fidelity_note)}",
        f"pages = {len(all_titles)}",
        f"migrated_titles = {sum(title in migrated for title in all_titles)}",
        f"history_rows = {len(all_histories)}",
        f"current_rows = {len(all_current_pages)}",
        f"history_only_pages = {sum(not row['source_id'] for row in gaps)}",
        f"binary_page_versions_skipped = {len(binary_versions)}",
        f"current_history_version_collisions = {current_collisions}",
        f"ascii_content_different_collisions = {ascii_content_differences}",
        f"forced_final_current_rows = {forced_final}",
        f"wiki_discuss_posts = {wiki_discuss_posts}",
        f"page_comments = {page_comments}",
        f"dangling_forum_parents = {len(dangling_forum)}",
        f"skipped_forum_posts_total = {sum(skipped_forum_posts.values())}",
        f"skipped_other_comments = {skipped_other_comments}",
        f"unapproved_comments_skipped = {unapproved_comments}",
        f"null_parent_topics = {null_parent_topics}",
    ]
    coverage_lines.extend(
        [
            "",
            "[skipped_forum_posts]",
            *(
                f"{_toml_key(forum_id)} = {count}"
                for forum_id, count in sorted(skipped_forum_posts.items())
            ),
        ]
    )
    for table in sorted(fidelity_rows):
        coverage_lines.extend(
            [
                "",
                f"[fidelity.{table}]",
                f"question_rows = {fidelity_rows[table]['question_rows']}",
                f"high_byte_rows = {fidelity_rows[table]['high_byte_rows']}",
                (
                    "stored_mojibake_rows = "
                    f"{fidelity_rows[table]['stored_mojibake_rows']}"
                ),
            ]
        )
        coverage_lines.extend(
            f"{_toml_key(encoding + '_fields')} = {count}"
            for encoding, count in sorted(fidelity_branches[table].items())
        )
    coverage = "\n".join(coverage_lines) + "\n"

    final_changes = dict(events[-1].changes)
    final_changes["_meta/tiki/pages.csv"] = _csv_text(
        (
            "title",
            "path",
            "current_version",
            "current_source_id",
            "versions",
            "migrated_to",
        ),
        page_rows,
    )
    final_changes["_meta/tiki/versions.csv"] = _csv_text(
        (
            "title",
            "source_id",
            "version",
            "time",
            "user",
            "display_name",
            "is_html",
            "encoding",
            "current",
            "path",
        ),
        version_rows,
    )
    final_changes["_meta/tiki/gaps.csv"] = _csv_text(
        ("source_id", "title", "path", "reason"), gaps
    )
    final_changes["_meta/tiki/coverage.toml"] = coverage
    last = events[-1]
    events[-1] = Event(
        source=last.source,
        source_id=last.source_id,
        event=last.event,
        time_confidence=last.time_confidence,
        source_time=last.source_time,
        summary=last.summary,
        author=last.author,
        changes=final_changes,
        deletions=last.deletions,
        source_date=last.source_date,
        event_window=last.event_window,
        trailers=last.trailers,
    )
    yield from events
