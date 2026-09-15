"""Decode the MediaWiki 1.38 SQL export into the neutral wiki model.

SPEC.md section 3.2 gives the wiki two inputs: this one-time operator export and
the incremental `api.php` crawl, and requires that the projector produce the
same events from either for every revision and log entry both can see. The
export additionally holds material the API structurally cannot serve, and this
module is where that asymmetry is made explicit rather than silently absorbed:

* MediaWiki 1.38 runs `$wgActorTableSchemaMigrationStage = SCHEMA_COMPAT_TEMP`,
  so `RevisionStore` inner-joins `revision_actor_temp`. A revision with no row
  there is invisible to `api.php` however well-formed it is, and `list=logevents`
  hides a log entry whose `log_actor` names no `actor` row the same way. Both
  happen in this database, so the export is a strict superset in the shared
  range, never a disagreement with it.
* `archive` holds revisions of deleted pages that the public API refuses.

Every such row is projected where the SPEC allows and recorded in
`_meta/wiki/gaps.csv` where it does not. Nothing is guessed: an unresolvable
join produces a gap, not an invented value.
"""

from __future__ import annotations

import hashlib
import re
import zlib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..archive.manifest import ArchiveManifest, object_path
from . import sqldump
from .wiki import (
    NAMESPACE_DIRS,
    WikiLogEvent,
    WikiPageFragment,
    WikiRevision,
)

_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"
_ANONYMOUS_AUTHOR_REASON = "imported revision; author not recorded in the export"
# MediaWiki's own rendering of an actor row with no usable name.
UNKNOWN_USER = "Unknown user"

SQL_COLUMNS: dict[str, tuple[str, ...]] = {
    "actor": ("actor_id", "actor_user", "actor_name"),
    "archive": (
        "ar_id",
        "ar_namespace",
        "ar_title",
        "ar_comment_id",
        "ar_actor",
        "ar_timestamp",
        "ar_minor_edit",
        "ar_rev_id",
        "ar_deleted",
        "ar_len",
        "ar_page_id",
        "ar_parent_id",
        "ar_sha1",
    ),
    "comment": ("comment_id", "comment_hash", "comment_text", "comment_data"),
    "content": (
        "content_id",
        "content_size",
        "content_sha1",
        "content_model",
        "content_address",
    ),
    "content_models": ("model_id", "model_name"),
    "logging": (
        "log_id",
        "log_type",
        "log_action",
        "log_timestamp",
        "log_actor",
        "log_namespace",
        "log_title",
        "log_page",
        "log_comment_id",
        "log_params",
        "log_deleted",
    ),
    "page": (
        "page_id",
        "page_namespace",
        "page_title",
        "page_restrictions",
        "page_is_redirect",
        "page_is_new",
        "page_random",
        "page_touched",
        "page_latest",
        "page_len",
        "page_content_model",
        "page_links_updated",
        "page_lang",
    ),
    "revision": (
        "rev_id",
        "rev_page",
        "rev_comment_id",
        "rev_actor",
        "rev_timestamp",
        "rev_minor_edit",
        "rev_deleted",
        "rev_len",
        "rev_parent_id",
        "rev_sha1",
    ),
    "revision_actor_temp": (
        "revactor_rev",
        "revactor_actor",
        "revactor_timestamp",
        "revactor_page",
    ),
    "revision_comment_temp": ("revcomment_rev", "revcomment_comment_id"),
    "slot_roles": ("role_id", "role_name"),
    "slots": ("slot_revision_id", "slot_role_id", "slot_content_id", "slot_origin"),
    "text": ("old_id", "old_text", "old_flags"),
}

# Canonical namespace prefixes exactly as the live `siteinfo` reports them
# (SPEC.md section 3.2 projects the same set). A page or log row in any other
# namespace belongs to an extension this wiki no longer loads: MediaWiki cannot
# name such a title and renders it `Special:Badtitle/NS<id>:<text>`, which is
# what the archived API responses contain, so the dump path says the same.
NAMESPACE_PREFIXES: dict[int, str] = {
    -2: "Media",
    -1: "Special",
    0: "",
    1: "Talk",
    2: "User",
    3: "User talk",
    4: "Lojban",
    5: "Lojban talk",
    6: "File",
    7: "File talk",
    8: "MediaWiki",
    9: "MediaWiki talk",
    10: "Template",
    11: "Template talk",
    12: "Help",
    13: "Help talk",
    14: "Category",
    15: "Category talk",
    200: "UserWiki",
    201: "UserWiki talk",
    202: "User profile",
    203: "User profile talk",
    828: "Module",
    829: "Module talk",
}
# Local names differ from canonical ones for the project namespace, and the
# file namespace keeps its historical alias; both are accepted title prefixes.
NAMESPACE_ALIASES = {
    "Project": 4,
    "Project talk": 5,
    "Image": 6,
    "Image talk": 7,
}
# `siprop=namespaces` reports `case` per namespace: this wiki runs
# `$wgCapitalLinks = false` with first-letter overrides for exactly these,
# so a title elsewhere keeps the case it was typed in.
FIRST_LETTER_NAMESPACES = frozenset({-1, 2, 3, 8, 9, 10, 11, 828, 829})
# MediaWiki matches a namespace prefix case-insensitively, so `user talk:foo`
# names the same namespace as `User talk:Foo`.
PREFIX_NAMESPACES = {
    prefix.lower(): namespace
    for namespace, prefix in NAMESPACE_PREFIXES.items()
    if prefix
} | {alias.lower(): namespace for alias, namespace in NAMESPACE_ALIASES.items()}


# `rev_deleted` / `ar_deleted` bits, includes/Revision/RevisionRecord.php:53-58.
DELETED_TEXT = 1
DELETED_COMMENT = 2
DELETED_USER = 4
DELETED_RESTRICTED = 8


class WikiSqlParseError(ValueError):
    """The sanitized SQL export cannot be decoded without guessing."""


class WikiSqlTextMissing(WikiSqlParseError):
    """A historical text pointer is dangling in the source database."""


@dataclass(frozen=True, slots=True)
class PhpObject:
    name: bytes
    properties: Mapping[bytes | int, object]


@dataclass(frozen=True, slots=True)
class WikiSqlGap:
    """One row the export could not project, destined for `gaps.csv`."""

    revid: int | None
    logid: int | None
    pageid: int | None
    title: str
    timestamp: datetime | None
    reason: str

    def as_row(self) -> dict[str, object]:
        return {
            "revid": "" if self.revid is None else self.revid,
            "logid": "" if self.logid is None else self.logid,
            "pageid": "" if self.pageid is None else self.pageid,
            "title": self.title,
            "timestamp": (
                ""
                if self.timestamp is None
                else self.timestamp.isoformat().replace("+00:00", "Z")
            ),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class WikiArchivedRevision:
    """One `archive` row: a revision of a page the wiki has since deleted."""

    archive_id: int
    pageid: int | None
    namespace: int
    title: str
    revision: WikiRevision


@dataclass(frozen=True, slots=True)
class WikiSqlDump:
    fragments: tuple[WikiPageFragment, ...]
    logs: tuple[WikiLogEvent, ...]
    archived: tuple[WikiArchivedRevision, ...]
    gaps: tuple[WikiSqlGap, ...]
    counts: Mapping[str, int]
    # `logging.log_page` names the page a deletion removed, which is the only
    # unambiguous link from a deleted lineage to the log entry that ended it:
    # several lineages can share one title over time. It is kept apart from
    # `logs` because `WikiLogEvent.pageid` carries what the API reports there,
    # which is the page holding that title now.
    deleted_page_logs: Mapping[int, tuple[datetime, int]] = field(default_factory=dict)


class _PhpParser:
    """Strict reader for the subset of `serialize()` HistoryBlobs use."""

    def __init__(self, payload: bytes, context: str) -> None:
        self.payload = payload
        self.context = context
        self.offset = 0

    def _take(self, length: int) -> bytes:
        if length < 0 or self.offset + length > len(self.payload):
            raise WikiSqlParseError(f"{self.context}: truncated PHP serialization")
        value = self.payload[self.offset : self.offset + length]
        self.offset += length
        return value

    def _until(self, delimiter: bytes) -> bytes:
        try:
            end = self.payload.index(delimiter, self.offset)
        except ValueError as exc:
            raise WikiSqlParseError(
                f"{self.context}: unterminated PHP serialization token"
            ) from exc
        value = self.payload[self.offset : end]
        self.offset = end + len(delimiter)
        return value

    def value(self, depth: int = 0) -> object:
        if depth > 64:
            raise WikiSqlParseError(f"{self.context}: PHP serialization is too deep")
        prefix = self._take(2)
        tag = prefix[:1]
        if prefix == b"N;":
            return None
        if prefix[1:] != b":":
            raise WikiSqlParseError(
                f"{self.context}: unsupported PHP serialization tag {tag!r}"
            )
        if tag == b"b":
            token = self._until(b";")
            if token not in {b"0", b"1"}:
                raise WikiSqlParseError(f"{self.context}: invalid PHP boolean")
            return token == b"1"
        if tag == b"i":
            token = self._until(b";")
            if not re.fullmatch(rb"-?[0-9]+", token):
                raise WikiSqlParseError(f"{self.context}: invalid PHP integer")
            return int(token)
        if tag == b"d":
            token = self._until(b";")
            try:
                return float(token)
            except ValueError as exc:
                raise WikiSqlParseError(f"{self.context}: invalid PHP float") from exc
        if tag == b"s":
            length_token = self._until(b":")
            if not length_token.isdigit():
                raise WikiSqlParseError(f"{self.context}: invalid PHP string length")
            if self._take(1) != b'"':
                raise WikiSqlParseError(f"{self.context}: invalid PHP string opener")
            value = self._take(int(length_token))
            if self._take(2) != b'";':
                raise WikiSqlParseError(
                    f"{self.context}: invalid PHP string terminator"
                )
            return value
        if tag not in {b"a", b"O"}:
            raise WikiSqlParseError(
                f"{self.context}: unsupported PHP serialization tag {tag!r}"
            )
        class_name: bytes | None = None
        if tag == b"O":
            length_token = self._until(b":")
            if not length_token.isdigit() or self._take(1) != b'"':
                raise WikiSqlParseError(f"{self.context}: invalid PHP object name")
            class_name = self._take(int(length_token))
            if self._take(2) != b'":':
                raise WikiSqlParseError(f"{self.context}: invalid PHP object header")
        count_token = self._until(b":")
        if not count_token.isdigit() or int(count_token) > 1_000_000:
            raise WikiSqlParseError(f"{self.context}: invalid PHP item count")
        if self._take(1) != b"{":
            raise WikiSqlParseError(f"{self.context}: invalid PHP container opener")
        values: dict[bytes | int, object] = {}
        for _index in range(int(count_token)):
            key = self.value(depth + 1)
            if not isinstance(key, (bytes, int)) or key in values:
                raise WikiSqlParseError(
                    f"{self.context}: invalid or duplicate PHP container key"
                )
            values[key] = self.value(depth + 1)
        if self._take(1) != b"}":
            raise WikiSqlParseError(f"{self.context}: invalid PHP container terminator")
        return PhpObject(class_name, values) if class_name is not None else values


def php_unserialize(payload: bytes, context: str = "PHP serialization") -> object:
    parser = _PhpParser(payload, context)
    value = parser.value()
    if parser.offset != len(payload):
        raise WikiSqlParseError(f"{context}: trailing PHP serialization data")
    return value


def _integer(
    value: bytes | None, context: str, *, optional: bool = False
) -> int | None:
    if value is None and optional:
        return None
    if value is None or not re.fullmatch(rb"[0-9]+", value):
        raise WikiSqlParseError(f"{context}: expected an unsigned integer")
    return int(value)


def _required_integer(value: bytes | None, context: str) -> int:
    result = _integer(value, context)
    assert result is not None
    return result


def _revision_length(value: bytes | None, context: str) -> int:
    """Read `rev_len`/`ar_len`, which is NULL for 247 rows in this database.

    `api.php` serializes a NULL length as 0, so the dump path reports 0 too and
    the two inputs agree on `_meta/wiki/revisions.csv`.
    """

    length = _integer(value, context, optional=True)
    return 0 if length is None else length


def _text(value: bytes | None, context: str) -> str:
    if value is None:
        raise WikiSqlParseError(f"{context}: unexpected NULL text")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WikiSqlParseError(f"{context}: text is not UTF-8") from exc


def _timestamp(value: bytes | None, context: str) -> datetime:
    text = _text(value, context)
    if not re.fullmatch(r"[0-9]{14}", text):
        raise WikiSqlParseError(f"{context}: invalid MediaWiki timestamp")
    try:
        return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError as exc:
        raise WikiSqlParseError(f"{context}: invalid MediaWiki timestamp") from exc


def _base36_to_sha1(value: bytes | None, context: str) -> str | None:
    if value in {None, b""}:
        return None
    assert value is not None
    try:
        number = int(value.decode("ascii"), 36)
    except (UnicodeDecodeError, ValueError) as exc:
        raise WikiSqlParseError(f"{context}: invalid base-36 SHA-1") from exc
    if number >= 1 << 160:
        raise WikiSqlParseError(f"{context}: base-36 SHA-1 exceeds 160 bits")
    return f"{number:040x}"


def sha1_base36(payload: bytes) -> str:
    """Render a SHA-1 the way `content_sha1` stores it (31 base-36 digits)."""

    number = int(hashlib.sha1(payload).hexdigest(), 16)
    digits: list[str] = []
    while number:
        number, digit = divmod(number, 36)
        digits.append(_BASE36[digit])
    return "".join(reversed(digits or ["0"])).rjust(31, "0")


def _ucfirst(namespace: int, value: str) -> str:
    """Capitalize as Language::ucfirst, but only in a first-letter namespace."""

    if namespace not in FIRST_LETTER_NAMESPACES:
        return value
    if not value or ord(value[0]) < 96:
        return value
    return value[0].upper() + value[1:]


def render_title(namespace: int, text: str) -> str:
    """Render a namespace and title text as Title::getPrefixedText would."""

    prefix = NAMESPACE_PREFIXES.get(namespace)
    if prefix is None:
        return f"Special:Badtitle/NS{namespace}:{text}"
    return text if not prefix else f"{prefix}:{text}"


def full_title(namespace: int, db_key: bytes | None, context: str) -> str:
    """Render `ns` + DB key the way `api.php` renders a full page title."""

    return render_title(namespace, _text(db_key, context).replace("_", " "))


def parse_title(value: str, context: str) -> tuple[int, str]:
    """Resolve a free-text move target as Title::newFromText would.

    `log_params['4::target']` holds the target as the mover typed it, so the
    namespace prefix has to be recognized and the remainder capitalized before
    it can be compared with what the API reports. A prefix the wiki no longer
    registers is not a namespace at all: the whole string stays a main-namespace
    title, which is what the archived responses show.
    """

    text = " ".join(value.replace("_", " ").split())
    if not text:
        raise WikiSqlParseError(f"{context}: move target is empty")
    prefix, separator, remainder = text.partition(":")
    namespace = PREFIX_NAMESPACES.get(prefix.strip().lower())
    if separator and namespace is not None and remainder.strip():
        if namespace < 0:
            raise WikiSqlParseError(
                f"{context}: move target names virtual namespace {namespace}"
            )
        return namespace, render_title(
            namespace, _ucfirst(namespace, remainder.strip())
        )
    return 0, _ucfirst(0, text)


class _TextStore:
    """Resolve `content_address` -> `text` -> decoded bytes, per SPEC 3.2."""

    def __init__(self, rows: Iterable[tuple[bytes | None, ...]]) -> None:
        self.rows: dict[int, tuple[bytes, frozenset[str]]] = {}
        self.cache: dict[tuple[int, bytes | None], bytes] = {}
        for row in rows:
            old_id = _required_integer(row[0], "text.old_id")
            if old_id in self.rows or row[1] is None or row[2] is None:
                raise WikiSqlParseError(f"duplicate or incomplete text row {old_id}")
            try:
                flags = frozenset(
                    part for part in row[2].decode("ascii").split(",") if part
                )
            except UnicodeDecodeError as exc:
                raise WikiSqlParseError(
                    f"text row {old_id}: flags are not ASCII"
                ) from exc
            if "error" in flags:
                raise WikiSqlParseError(f"text row {old_id}: poisoned by `error` flag")
            if "external" in flags:
                raise WikiSqlParseError(
                    f"text row {old_id}: external store is absent from this export"
                )
            if not flags <= {"utf-8", "utf8", "gzip", "object"}:
                raise WikiSqlParseError(
                    f"text row {old_id}: unsupported flags {sorted(flags)!r}"
                )
            self.rows[old_id] = (row[1], flags)

    def _inflate(self, payload: bytes, context: str) -> bytes:
        try:
            return zlib.decompress(payload, -zlib.MAX_WBITS)
        except zlib.error as exc:
            raise WikiSqlParseError(f"{context}: invalid raw DEFLATE") from exc

    def _concatenated(
        self, old_id: int, blob: PhpObject
    ) -> tuple[Mapping[object, object], bytes]:
        expected = {b"mVersion", b"mCompressed", b"mItems", b"mDefaultHash"}
        if set(blob.properties) != expected:
            raise WikiSqlParseError(
                f"text row {old_id}: invalid ConcatenatedGzipHistoryBlob"
            )
        items_payload = blob.properties[b"mItems"]
        compressed = blob.properties[b"mCompressed"]
        default_hash = blob.properties[b"mDefaultHash"]
        if (
            not isinstance(items_payload, bytes)
            or not isinstance(compressed, bool)
            or not isinstance(default_hash, bytes)
        ):
            raise WikiSqlParseError(
                f"text row {old_id}: invalid ConcatenatedGzipHistoryBlob"
            )
        if compressed:
            items_payload = self._inflate(items_payload, f"text row {old_id} items")
        items = php_unserialize(items_payload, f"text row {old_id} items")
        if not isinstance(items, dict):
            raise WikiSqlParseError(
                f"text row {old_id}: concatenated items are not a map"
            )
        return items, default_hash

    def resolve(self, old_id: int, wanted_hash: bytes | None = None) -> bytes:
        key = (old_id, wanted_hash)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        try:
            payload, flags = self.rows[old_id]
        except KeyError as exc:
            raise WikiSqlTextMissing(
                f"content references absent text row {old_id}"
            ) from exc
        if "gzip" in flags:
            payload = self._inflate(payload, f"text row {old_id}")
        if "object" not in flags:
            if wanted_hash is not None:
                raise WikiSqlParseError(
                    f"text row {old_id}: hash-selecting stub targets plain text"
                )
            self.cache[key] = payload
            return payload
        blob = php_unserialize(payload, f"text row {old_id}")
        if not isinstance(blob, PhpObject):
            raise WikiSqlParseError(f"text row {old_id}: history blob is not an object")
        if blob.name == b"HistoryBlobStub":
            if set(blob.properties) != {b"mOldId", b"mHash", b"mRef"}:
                raise WikiSqlParseError(f"text row {old_id}: invalid HistoryBlobStub")
            target = blob.properties[b"mOldId"]
            selected = blob.properties[b"mHash"]
            if (
                not isinstance(target, bytes)
                or not target.isdigit()
                or not isinstance(selected, bytes)
            ):
                raise WikiSqlParseError(f"text row {old_id}: invalid HistoryBlobStub")
            result = self.resolve(int(target), selected)
            self.cache[key] = result
            return result
        if blob.name != b"ConcatenatedGzipHistoryBlob":
            raise WikiSqlParseError(
                f"text row {old_id}: unsupported history blob {blob.name!r}"
            )
        items, default_hash = self._concatenated(old_id, blob)
        selected_hash = default_hash if wanted_hash is None else wanted_hash
        result = items.get(selected_hash)
        if not isinstance(result, bytes):
            raise WikiSqlTextMissing(
                f"text row {old_id}: concatenated item {selected_hash!r} is absent"
            )
        self.cache[key] = result
        return result


def _load_tables(
    path: Path, expected: Mapping[str, Sequence[str]] = SQL_COLUMNS
) -> dict[str, list[tuple[bytes | None, ...]]]:
    """Stream the export once, keeping only the tables the projector needs."""

    wanted = {name: tuple(columns) for name, columns in expected.items()}
    rows: dict[str, list[tuple[bytes | None, ...]]] = {name: [] for name in wanted}
    schemas: set[str] = set()
    for statement in sqldump.statements(path, WikiSqlParseError):
        columns = wanted.get(statement.table)
        if columns is None:
            continue
        if statement.values is None:
            assert statement.columns is not None
            sqldump.require_columns(
                statement.table, statement.columns, columns, WikiSqlParseError
            )
            schemas.add(statement.table)
            continue
        if statement.table not in schemas:
            raise WikiSqlParseError(
                f"MediaWiki SQL dump inserts into {statement.table} before its schema"
            )
        values = sqldump.parse_insert_values(
            statement.values, f"MediaWiki SQL {statement.table}", WikiSqlParseError
        )
        if len(values) != len(columns):
            raise WikiSqlParseError(
                f"MediaWiki SQL has {len(values)} values for {statement.table}; "
                f"expected {len(columns)}"
            )
        rows[statement.table].append(values)
    missing = sorted(wanted.keys() - schemas)
    if missing:
        raise WikiSqlParseError(
            f"MediaWiki SQL dump is missing schemas for: {', '.join(missing)}"
        )
    return rows


def _unique_map(
    rows: Iterable[tuple[bytes | None, ...]],
    key_index: int,
    value_index: int,
    label: str,
) -> dict[int, int]:
    result: dict[int, int] = {}
    for row in rows:
        key = _required_integer(row[key_index], f"{label} key")
        value = _required_integer(row[value_index], f"{label} value")
        if key in result:
            raise WikiSqlParseError(f"{label} has a duplicate row for {key}")
        result[key] = value
    return result


def _log_params(payload: bytes | None, context: str) -> dict[bytes | int, object]:
    """Decode `log_params`, tolerating the pre-1.21 positional form."""

    if payload is None or payload == b"":
        return {}
    if not payload.startswith(b"a:"):
        # DatabaseLogEntry.php:182-194: a pre-1.21 entry is a newline-separated
        # positional list. Anything that claims to be a serialized array must
        # parse as one; silently reinterpreting a broken array would make its
        # first line the move target.
        return {
            index: part
            for index, part in enumerate(payload.split(b"\n"))
            if part != b""
        }
    value = php_unserialize(payload, context)
    if not isinstance(value, dict):
        raise WikiSqlParseError(f"{context}: log parameters are not an array")
    return value


def _php_flag(value: object, context: str) -> bool:
    """Read a MediaWiki log flag, which serializes as "0"/"1" or an integer."""

    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, bytes):
        return value not in {b"", b"0"}
    raise WikiSqlParseError(f"{context}: unsupported flag value")


def load_wiki_sql_dump(path: Path) -> WikiSqlDump:
    """Decode live pages, move/delete logs and deleted revisions from the export."""

    rows = _load_tables(path)
    gaps: list[WikiSqlGap] = []
    counts: dict[str, int] = {}

    actors: dict[int, str] = {}
    for row in rows["actor"]:
        actor_id = _required_integer(row[0], "actor.actor_id")
        if actor_id in actors:
            raise WikiSqlParseError(f"duplicate actor {actor_id}")
        actors[actor_id] = _text(row[2], f"actor {actor_id}")
    comments: dict[int, str] = {}
    for row in rows["comment"]:
        comment_id = _required_integer(row[0], "comment.comment_id")
        if comment_id in comments:
            raise WikiSqlParseError(f"duplicate comment {comment_id}")
        comments[comment_id] = _text(row[2], f"comment {comment_id}")
    actor_temp = _unique_map(rows["revision_actor_temp"], 0, 1, "revision_actor_temp")
    comment_temp = _unique_map(
        rows["revision_comment_temp"], 0, 1, "revision_comment_temp"
    )

    roles = {
        _required_integer(row[0], "slot_roles.role_id"): _text(row[1], "slot role")
        for row in rows["slot_roles"]
    }
    main_roles = [role_id for role_id, name in roles.items() if name == "main"]
    if len(main_roles) != 1:
        raise WikiSqlParseError("MediaWiki SQL dump has no unique main slot role")
    main_role = main_roles[0]
    slot_content: dict[int, int] = {}
    for row in rows["slots"]:
        revision_id = _required_integer(row[0], "slots.slot_revision_id")
        if _integer(row[1], "slots.slot_role_id") != main_role:
            continue
        if revision_id in slot_content:
            raise WikiSqlParseError(f"revision {revision_id} has duplicate main slots")
        slot_content[revision_id] = _required_integer(row[2], "slots.slot_content_id")

    models = {
        _required_integer(row[0], "content_models.model_id"): _text(
            row[1], "content model"
        )
        for row in rows["content_models"]
    }
    contents: dict[int, tuple[int, bytes, str, int]] = {}
    for row in rows["content"]:
        content_id = _required_integer(row[0], "content.content_id")
        size = _required_integer(row[1], "content.content_size")
        model_id = _required_integer(row[3], "content.content_model")
        if content_id in contents or row[2] is None or row[4] is None:
            raise WikiSqlParseError(f"duplicate or incomplete content {content_id}")
        if model_id not in models:
            raise WikiSqlParseError(
                f"content {content_id} has unknown model {model_id}"
            )
        # SqlBlobStore.php:699-722: 1.38 writes only `tt:<old_id>`, optionally
        # with a query part. `bad:` and external-store addresses fail closed.
        matched = re.fullmatch(rb"tt:([0-9]+)(?:\?[^\s]*)?", row[4])
        if matched is None:
            raise WikiSqlParseError(
                f"content {content_id} has unsupported address {row[4]!r}"
            )
        contents[content_id] = (size, row[2], models[model_id], int(matched.group(1)))
    text_store = _TextStore(rows["text"])

    unresolved_authors = 0
    integrity_failures = 0

    def build_revision(
        *,
        revid: int,
        parentid: int,
        timestamp: datetime,
        actor_id: int,
        comment_id: int,
        deleted: int,
        size: int | None,
        sha1: bytes | None,
        pageid: int | None,
        title: str,
    ) -> WikiRevision | None:
        nonlocal unresolved_authors, integrity_failures
        if deleted & DELETED_RESTRICTED:
            # SPEC.md 3.2: oversighted material is never written, but the event
            # still exists. Bit 8 masks text, comment and user together, which
            # is what the API path does with the same revision, so the two
            # paths agree by construction rather than by absence.
            deleted |= DELETED_TEXT | DELETED_COMMENT | DELETED_USER
            gaps.append(WikiSqlGap(revid, None, pageid, title, timestamp, "suppressed"))
        user = actors.get(actor_id)
        unrecorded_author = False
        if user == "":
            # One actor row in this database has an empty `actor_name` and a
            # NULL `actor_user`. MediaWiki publishes that as `Unknown user`, so
            # the dump path says what the API path has already written into the
            # corpus rather than inventing a second spelling for one broken row.
            user = UNKNOWN_USER
        if user is None:
            # 1.38 hides these from api.php entirely (module docstring); the
            # export keeps the content but records no recoverable author, which
            # SPEC.md 2.5 attributes to `unrecorded@`, never `anonymous@`.
            unrecorded_author = True
            unresolved_authors += 1
            gaps.append(
                WikiSqlGap(
                    revid, None, pageid, title, timestamp, _ANONYMOUS_AUTHOR_REASON
                )
            )
        comment = comments.get(comment_id)
        if comment is None:
            raise WikiSqlParseError(f"revision {revid} references absent comment")
        content_id = slot_content.get(revid)
        if content_id is None:
            raise WikiSqlParseError(f"revision {revid} has no main content slot")
        try:
            content_size, content_sha1, _model, old_id = contents[content_id]
        except KeyError as exc:
            raise WikiSqlParseError(
                f"revision {revid} references absent content {content_id}"
            ) from exc
        content: str | None = None
        text_missing = False
        text_cause = ""
        if not deleted & DELETED_TEXT:
            try:
                payload = text_store.resolve(old_id)
            except WikiSqlTextMissing as exc:
                text_missing = True
                text_cause = str(exc)
            else:
                if (
                    sha1_base36(payload).encode("ascii") != content_sha1
                    or len(payload) != content_size
                ):
                    # The stored digest is the authority (dump-schemas.md 3.4);
                    # a row that disagrees with it is evidence of corruption,
                    # not text to publish.
                    integrity_failures += 1
                    text_missing = True
                    text_cause = (
                        f"content {content_id} disagrees with its declared size "
                        "or SHA-1"
                    )
                else:
                    content = _text(payload, f"revision {revid} content")
        if text_missing:
            gaps.append(
                WikiSqlGap(
                    revid,
                    None,
                    pageid,
                    title,
                    timestamp,
                    f"text unresolvable: {text_cause}",
                )
            )
        return WikiRevision(
            revid=revid,
            parentid=parentid,
            timestamp=timestamp,
            user=None if deleted & DELETED_USER else user,
            comment="" if deleted & DELETED_COMMENT else comment,
            size=size,
            sha1=_base36_to_sha1(sha1, f"revision {revid}"),
            content=content,
            text_hidden=bool(deleted & DELETED_TEXT),
            text_missing=text_missing,
            user_hidden=bool(deleted & DELETED_USER),
            comment_hidden=bool(deleted & DELETED_COMMENT),
            author_unrecorded=unrecorded_author,
            text_cause=text_cause,
        )

    pages: dict[int, tuple[int, str, bool]] = {}
    # ApiQueryLogEvents LEFT JOINs `page` on (log_namespace, log_title) and
    # reports that current id, never the historical `log_page`, so the dump
    # needs the same index to agree with the archived responses.
    page_ids: dict[tuple[int, bytes], int] = {}
    for row in rows["page"]:
        pageid = _required_integer(row[0], "page.page_id")
        namespace = _required_integer(row[1], "page.page_namespace")
        if pageid in pages:
            raise WikiSqlParseError(f"duplicate page {pageid}")
        assert row[2] is not None
        key = (namespace, row[2])
        if key in page_ids:
            raise WikiSqlParseError(f"duplicate page title in namespace {namespace}")
        page_ids[key] = pageid
        pages[pageid] = (
            namespace,
            full_title(namespace, row[2], f"page {pageid}"),
            bool(_required_integer(row[4], "page.page_is_redirect")),
        )
    projected_pages = {
        pageid
        for pageid, (namespace, _title, _redirect) in pages.items()
        if namespace in NAMESPACE_DIRS
    }
    counts["pages"] = len(pages)
    counts["pages_projected"] = len(projected_pages)
    for pageid in sorted(set(pages) - projected_pages):
        namespace, title, _redirect = pages[pageid]
        gaps.append(
            WikiSqlGap(
                None,
                None,
                pageid,
                title,
                None,
                f"namespace {namespace} is outside the projected set",
            )
        )

    revisions_by_page: dict[int, list[WikiRevision]] = defaultdict(list)
    orphan_revisions = 0
    for row in rows["revision"]:
        revid = _required_integer(row[0], "revision.rev_id")
        pageid = _required_integer(row[1], "revision.rev_page")
        identity = pages.get(pageid)
        if identity is None:
            # A revision whose page row is gone: unplaceable, and invisible to
            # api.php as well, so it is recorded and dropped.
            orphan_revisions += 1
            gaps.append(
                WikiSqlGap(
                    revid,
                    None,
                    pageid,
                    "",
                    _timestamp(row[4], f"revision {revid}"),
                    f"revision references absent page {pageid}",
                )
            )
            continue
        if pageid not in projected_pages:
            continue
        actor_id = actor_temp.get(
            revid, _required_integer(row[3], "revision.rev_actor")
        )
        comment_id = comment_temp.get(
            revid, _required_integer(row[2], "revision.rev_comment_id")
        )
        revision = build_revision(
            revid=revid,
            parentid=_integer(row[8], "revision.rev_parent_id", optional=True) or 0,
            timestamp=_timestamp(row[4], f"revision {revid}"),
            actor_id=actor_id,
            comment_id=comment_id,
            deleted=_required_integer(row[6], "revision.rev_deleted"),
            size=_revision_length(row[7], f"revision {revid}"),
            sha1=row[9],
            pageid=pageid,
            title=identity[1],
        )
        if revision is not None:
            revisions_by_page[pageid].append(revision)
    counts["revisions"] = len(rows["revision"])
    counts["revisions_orphaned"] = orphan_revisions
    counts["revisions_projected"] = sum(
        len(values) for values in revisions_by_page.values()
    )
    counts["revisions_without_author"] = unresolved_authors

    fragments = tuple(
        WikiPageFragment(
            pageid,
            pages[pageid][0],
            pages[pageid][1],
            pages[pageid][2],
            tuple(
                sorted(revisions_by_page.get(pageid, ()), key=lambda item: item.revid)
            ),
        )
        for pageid in sorted(projected_pages)
    )

    logs: list[WikiLogEvent] = []
    deleted_page_logs: dict[int, tuple[datetime, int]] = {}
    hidden_log_actors = 0
    for row in rows["logging"]:
        logid = _required_integer(row[0], "logging.log_id")
        log_type = _text(row[1], f"log event {logid} type")
        action = _text(row[2], f"log event {logid} action")
        # project.wiki.parse_log_response accepts exactly these three pairs, so
        # the dump path must select exactly the same set.
        if (log_type, action) not in {
            ("move", "move"),
            ("move", "move_redir"),
            ("delete", "delete"),
        }:
            continue
        namespace = _required_integer(row[5], "logging.log_namespace")
        timestamp = _timestamp(row[3], f"log event {logid}")
        title = full_title(namespace, row[6], f"log event {logid}")
        assert row[6] is not None
        current_pageid = page_ids.get((namespace, row[6]), 0)
        deleted = _required_integer(row[10], "logging.log_deleted")
        if deleted:
            # LogPage.php:39-42 reuses the revision-deletion bits; a hidden log
            # entry is recorded, never reconstructed.
            gaps.append(
                WikiSqlGap(
                    None,
                    logid,
                    current_pageid,
                    title,
                    timestamp,
                    f"{log_type}; log entry has deletion bits {deleted}",
                )
            )
            continue
        actor_id = _required_integer(row[4], "logging.log_actor")
        user = actors.get(actor_id)
        log_author_unrecorded = False
        if user == "":
            user = UNKNOWN_USER
        if user is None:
            # Same "the source records nobody" case as an actor-less revision:
            # SPEC.md 2.5 attributes it to `unrecorded@`, never `anonymous@`.
            log_author_unrecorded = True
            hidden_log_actors += 1
            gaps.append(
                WikiSqlGap(
                    None,
                    logid,
                    current_pageid,
                    title,
                    timestamp,
                    f"{log_type}; actor not recorded in the export",
                )
            )
        comment_id = _required_integer(row[8], "logging.log_comment_id")
        comment = comments.get(comment_id)
        if comment is None:
            raise WikiSqlParseError(f"log event {logid} references absent comment")
        logged_page = _integer(row[7], "logging.log_page", optional=True) or 0
        if log_type == "delete" and logged_page:
            # A page deleted, restored and deleted again has `archive` rows up
            # to the *last* deletion, so that is when its title stopped being
            # its own. Bounding at the first would hide a move made in between.
            previous = deleted_page_logs.get(logged_page)
            entry = (timestamp, logid)
            if previous is None or entry > previous:
                deleted_page_logs[logged_page] = entry
        target_namespace: int | None = None
        target_title: str | None = None
        suppress_redirect = False
        if log_type == "move":
            params = _log_params(row[9], f"log event {logid} params")
            raw_target = params.get(b"4::target", params.get(0))
            if not isinstance(raw_target, bytes) or not raw_target:
                raise WikiSqlParseError(f"log event {logid}: move target is missing")
            target_namespace, target_title = parse_title(
                _text(raw_target, f"log event {logid} target"),
                f"log event {logid}",
            )
            suppress_redirect = _php_flag(
                params.get(b"5::noredir", params.get(1)),
                f"log event {logid} suppressredirect",
            )
        logs.append(
            WikiLogEvent(
                logid=logid,
                log_type=log_type,
                pageid=current_pageid,
                namespace=namespace,
                title=title,
                timestamp=timestamp,
                user=user,
                comment=comment,
                target_namespace=target_namespace,
                target_title=target_title,
                suppress_redirect=suppress_redirect,
                move_redir=action == "move_redir",
                author_unrecorded=log_author_unrecorded,
            )
        )
    counts["log_events"] = len(logs)
    counts["log_events_without_actor"] = hidden_log_actors

    archived: list[WikiArchivedRevision] = []
    for row in rows["archive"]:
        archive_id = _required_integer(row[0], "archive.ar_id")
        namespace = _required_integer(row[1], "archive.ar_namespace")
        title = full_title(namespace, row[2], f"archive row {archive_id}")
        revid = _required_integer(row[7], "archive.ar_rev_id")
        pageid = _integer(row[10], "archive.ar_page_id", optional=True) or None
        if namespace not in NAMESPACE_DIRS:
            gaps.append(
                WikiSqlGap(
                    revid,
                    None,
                    pageid,
                    title,
                    _timestamp(row[5], f"archive revision {revid}"),
                    f"deleted revision in namespace {namespace} outside the projected set",
                )
            )
            continue
        revision = build_revision(
            revid=revid,
            parentid=_integer(row[11], "archive.ar_parent_id", optional=True) or 0,
            timestamp=_timestamp(row[5], f"archive revision {revid}"),
            actor_id=_required_integer(row[4], "archive.ar_actor"),
            comment_id=_required_integer(row[3], "archive.ar_comment_id"),
            deleted=_required_integer(row[8], "archive.ar_deleted"),
            size=_revision_length(row[9], f"archive revision {revid}"),
            sha1=row[12],
            pageid=pageid,
            title=title,
        )
        if revision is None:
            continue
        archived.append(
            WikiArchivedRevision(archive_id, pageid, namespace, title, revision)
        )
    counts["archived_revisions"] = len(rows["archive"])
    counts["archived_revisions_projected"] = len(archived)
    counts["integrity_failures"] = integrity_failures

    return WikiSqlDump(
        fragments,
        tuple(sorted(logs, key=lambda item: (item.timestamp, item.logid))),
        tuple(archived),
        tuple(gaps),
        counts,
        deleted_page_logs,
    )


def load_dump_archive(archive: Path) -> WikiSqlDump | None:
    """Load the ingested operator export, or None when none was ingested."""

    root = archive / "manifests" / "wiki" / "db-export"
    if not root.exists():
        return None
    selected: ArchiveManifest | None = None
    for path in sorted(root.glob("wiki-content.sql.gz-*.toml")):
        if path.is_symlink():
            raise WikiSqlParseError(
                f"wiki export manifest must not be a symlink: {path}"
            )
        manifest = ArchiveManifest.load(path)
        if selected is None or (manifest.fetched_at, manifest.sha256) > (
            selected.fetched_at,
            selected.sha256,
        ):
            selected = manifest
    if selected is None:
        return None
    obj = object_path(archive, selected.sha256)
    if obj.is_symlink():
        raise WikiSqlParseError(f"wiki export object must not be a symlink: {obj}")
    if not obj.is_file() or obj.stat().st_size != selected.bytes:
        raise WikiSqlParseError(f"wiki export object is missing or wrong-sized: {obj}")
    digest = hashlib.sha256()
    with obj.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != selected.sha256:
        raise WikiSqlParseError(f"wiki export object does not match manifest: {obj}")
    return load_wiki_sql_dump(obj)


def archived_fragments(
    dump: WikiSqlDump, live: Iterable[int] = ()
) -> tuple[list[WikiPageFragment], dict[int, tuple[datetime, int]], list[WikiSqlGap]]:
    """Rebuild the deleted lineages `archive` holds, one fragment per page id.

    SPEC.md 3.2 lets a deletion be projected only for a page whose history the
    projection already holds, so this backfill is what turns a `deleted; history
    not API-accessible` gap into a real `Event: deleted`. Each lineage must be
    matched to the single log entry that ended it, because one title can belong
    to several lineages in turn and a lineage the corpus never removes would
    still hold its path when the next page claims it:

    1. `logging.log_page` names the deleted page outright; that link wins.
    2. Otherwise the remaining entries for the title, deletions and the
       `move_redir` moves that overwrite it, are assigned to the remaining
       lineages in time order, each entry used once.
    3. A lineage left without an entry is still projected, with no bound on
       when it stopped holding its title: SPEC.md 3.2 rule 3 says it yields its
       path to the next page that claims it rather than being refused.

    MediaWiki keeps `ar_page_id` when it archives revisions and reuses that id
    for a later page, so a lineage whose id a live page now owns cannot be told
    apart from it by page id alone and is recorded as well.
    """

    live_ids = set(live)
    grouped: dict[int, list[WikiArchivedRevision]] = defaultdict(list)
    gaps: list[WikiSqlGap] = []
    for archived in dump.archived:
        if archived.pageid is None:
            gaps.append(
                WikiSqlGap(
                    archived.revision.revid,
                    None,
                    None,
                    archived.title,
                    archived.revision.timestamp,
                    "deleted revision records no page id; not projected",
                )
            )
            continue
        grouped[archived.pageid].append(archived)

    def record(pageid: int, rows: list[WikiArchivedRevision], reason: str) -> None:
        gaps.extend(
            WikiSqlGap(
                row.revision.revid,
                None,
                pageid,
                row.title,
                row.revision.timestamp,
                reason,
            )
            for row in rows
        )

    # Candidate lineages, and the entries that could have ended each title.
    lineages: dict[int, tuple[int, str, tuple[WikiRevision, ...]]] = {}
    for pageid in sorted(grouped):
        rows = grouped[pageid]
        identities = {(row.namespace, row.title) for row in rows}
        if pageid in live_ids:
            record(
                pageid,
                rows,
                f"deleted lineage; page id reused by {pageid}",
            )
            continue
        if len(identities) != 1:
            record(
                pageid,
                rows,
                f"deleted page id {pageid} has more than one title; "
                "deleted history not projected",
            )
            continue
        namespace, title = identities.pop()
        lineages[pageid] = (
            namespace,
            title,
            tuple(sorted((row.revision for row in rows), key=lambda r: r.revid)),
        )

    endings: dict[tuple[int, str], list[tuple[datetime, int]]] = defaultdict(list)
    for event in dump.logs:
        if event.log_type == "delete":
            key = (event.namespace, event.title)
        elif event.move_redir and event.target_namespace is not None:
            assert event.target_title is not None
            key = (event.target_namespace, event.target_title)
        else:
            continue
        endings[key].append((event.timestamp, event.logid))
    for entries in endings.values():
        entries.sort()

    ended_at: dict[int, tuple[datetime, int]] = {}
    claimed: set[int] = set()
    for pageid in lineages:
        bound = dump.deleted_page_logs.get(pageid)
        if bound is not None:
            ended_at[pageid] = bound
            claimed.add(bound[1])
    by_title: dict[tuple[int, str], list[int]] = defaultdict(list)
    for pageid, (namespace, title, revisions) in lineages.items():
        if pageid not in ended_at:
            by_title[(namespace, title)].append(pageid)
    for key, pageids in by_title.items():
        pageids.sort(key=lambda value: lineages[value][2][-1].timestamp)
        available = [entry for entry in endings.get(key, ()) if entry[1] not in claimed]
        for pageid in pageids:
            last = lineages[pageid][2][-1].timestamp
            match = next(
                (entry for entry in available if entry[0] >= last),
                None,
            )
            if match is None:
                continue
            available.remove(match)
            claimed.add(match[1])
            ended_at[pageid] = match

    fragments: list[WikiPageFragment] = []
    unaccounted: set[int] = set()
    for pageid, (namespace, title, revisions) in lineages.items():
        if pageid not in ended_at:
            unaccounted.add(pageid)
        final = revisions[-1].content or ""
        fragments.append(
            WikiPageFragment(
                pageid,
                namespace,
                title,
                final.lstrip().upper().startswith("#REDIRECT"),
                revisions,
            )
        )
    return fragments, ended_at, unaccounted, gaps


@dataclass(frozen=True, slots=True)
class WikiProjectorInputs:
    """Everything `project.wiki.project` needs, from both inputs at once."""

    fragments: list[WikiPageFragment]
    logs: list[WikiLogEvent]
    extra_gaps: list[dict[str, object]]
    ended_at: dict[int, tuple[datetime, int]]
    unaccounted: set[int]
    additive: list[tuple[str, int, str]]


def combine_inputs(
    dump: WikiSqlDump | None,
    fragments: Sequence[WikiPageFragment],
    logs: Sequence[WikiLogEvent],
    *,
    backfill_deleted: bool = True,
) -> WikiProjectorInputs:
    """Union the export with the API crawl, refusing any real disagreement.

    Both inputs describe one wiki, so a revision or log entry they share must be
    identical; `merge_fragments` already enforces that for revisions, and this
    does it for log entries, which are keyed by `logid` rather than merged.

    `backfill_deleted` adds the `archive` lineages, which is what turns a
    `deleted; history not API-accessible` gap into a real `Event: deleted`.
    """

    if dump is None:
        return WikiProjectorInputs(list(fragments), list(logs), [], {}, set(), [])
    combined_logs: dict[int, WikiLogEvent] = {}
    for event in (*dump.logs, *logs):
        previous = combined_logs.get(event.logid)
        if previous is not None and previous != event:
            raise WikiSqlParseError(
                f"log event {event.logid} differs between the export and the API"
            )
        combined_logs[event.logid] = event
    deleted: list[WikiPageFragment] = []
    ended_at: dict[int, tuple[datetime, int]] = {}
    unaccounted: set[int] = set()
    gaps = list(dump.gaps)
    if backfill_deleted:
        live = {fragment.pageid for fragment in (*dump.fragments, *fragments)}
        deleted, ended_at, unaccounted, deleted_gaps = archived_fragments(dump, live)
        gaps.extend(deleted_gaps)
    api_revisions = {
        revision.revid for fragment in fragments for revision in fragment.revisions
    }
    dump_revisions = {
        revision.revid for fragment in dump.fragments for revision in fragment.revisions
    }
    counts = dump.counts
    return WikiProjectorInputs(
        [*dump.fragments, *fragments, *deleted],
        [combined_logs[logid] for logid in sorted(combined_logs)],
        [gap.as_row() for gap in gaps],
        ended_at,
        unaccounted,
        [
            (
                "export_revisions_without_actor_row",
                counts.get("revisions_without_author", 0),
                (
                    "no revision_actor_temp row and rev_actor = 0: the foreign "
                    "half of a transwiki import, which MediaWiki 1.38 hides "
                    "from api.php because RevisionStore inner-joins the temp "
                    "table under SCHEMA_COMPAT_READ_TEMP"
                ),
            ),
            (
                "export_move_logs_without_actor_row",
                counts.get("log_events_without_actor", 0),
                (
                    "log_actor names no actor row, so list=logevents hides the "
                    "entry; all are from the 2013-2014 Move page script run"
                ),
            ),
            (
                "pages_outside_the_projected_namespaces",
                counts.get("pages", 0) - counts.get("pages_projected", 0),
                (
                    "namespaces 274 Widget, 275 Widget talk and 1198 "
                    "Translations are extension machinery SPEC.md 3.2 does "
                    "not project"
                ),
            ),
            (
                "revisions_naming_no_page_row",
                counts.get("revisions_orphaned", 0),
                (
                    "rev_page names no row in page, so the revision cannot be "
                    "placed and api.php cannot serve it either"
                ),
            ),
            (
                "deleted_revisions_rebuilt_from_archive",
                counts.get("archived_revisions_projected", 0),
                "archive rows: revisions of deleted pages the public API refuses",
            ),
            (
                "api_revisions_newer_than_the_export",
                len(api_revisions - dump_revisions),
                (
                    "edits made after the operator took the snapshot; the API "
                    "path covers them"
                ),
            ),
        ],
    )
