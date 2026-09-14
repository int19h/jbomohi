"""Strict PostgreSQL COPY loading for dictionary projection inputs."""

from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import io
import json
import re
import unicodedata
import zlib
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, TextIO

from ..git import Event, Identity


class DictionaryParseError(ValueError):
    """A dictionary export violates the expected public schema."""


LENSISKU_COPY_COLUMNS: dict[str, tuple[str, ...]] = {
    "languages": (
        "langid",
        "tag",
        "englishname",
        "lojbanname",
        "realname",
        "forlojban",
        "url",
    ),
    "valsitypes": ("typeid", "descriptor"),
    "valsi": (
        "valsiid",
        "word",
        "typeid",
        "userid",
        "time",
        "rafsi",
        "source_langid",
        "cached_decomposition",
        "canonical_word",
    ),
    "definitions": (
        "langid",
        "valsiid",
        "definitionnum",
        "definitionid",
        "definition",
        "notes",
        "userid",
        "time",
        "selmaho",
        "jargon",
        "owner_only",
        "etymology",
        "created_at",
        "embedding",
        "metadata",
        "cached_username",
        "cached_langrealname",
        "cached_type_name",
        "cached_search_text",
        "cached_valsiword",
        "cached_rafsi",
        "cached_source_langid",
        "cached_typeid",
        "cached_glosswords",
        "cached_decomposition",
        "rafsi",
        "cached_canonical_word",
    ),
    "comments": (
        "commentid",
        "threadid",
        "parentid",
        "userid",
        "commentnum",
        "time",
        "subject",
        "content",
        "plain_content",
        "import_source",
        "import_ref",
    ),
    "definition_versions": (
        "version_id",
        "definition_id",
        "langid",
        "valsiid",
        "definition",
        "notes",
        "selmaho",
        "jargon",
        "gloss_keywords",
        "place_keywords",
        "user_id",
        "created_at",
        "message",
        "owner_only",
        "etymology",
        "rafsi",
        "mw_revid",
    ),
    "etymology": ("etymologyid", "valsiid", "langid", "content", "time", "userid"),
    "example": (
        "exampleid",
        "valsiid",
        "definitionid",
        "examplenum",
        "content",
        "time",
        "userid",
    ),
    "natlangwords": (
        "wordid",
        "langid",
        "word",
        "meaning",
        "meaningnum",
        "userid",
        "time",
        "notes",
    ),
    "keywordmapping": ("natlangwordid", "definitionid", "place"),
    "pages": (
        "pagename",
        "version",
        "time",
        "userid",
        "langid",
        "content",
        "compressed",
        "latest",
    ),
    "threads": (
        "threadid",
        "valsiid",
        "natlangwordid",
        "definitionid",
        "last_comment_id",
        "last_comment_user_id",
        "last_comment_time",
        "last_comment_subject",
        "last_comment_content",
        "total_comments",
        "creator_user_id",
        "creator_username",
        "first_comment_subject",
        "first_comment_content",
        "target_user_id",
        "definition_link_id",
        "import_source",
        "import_ref",
        "collection_id",
    ),
}

LENSISKU_USER_COLUMNS = (
    "userid",
    "username",
    "realname",
    "url",
    "personal",
    "created_at",
    "role",
    "disabled",
)
JBOVLASTE_COPY_COLUMNS: dict[str, tuple[str, ...]] = {
    "comments": (
        "commentid",
        "threadid",
        "parentid",
        "userid",
        "commentnum",
        "time",
        "subject",
        "content",
    ),
    "definitions": (
        "langid",
        "valsiid",
        "definitionnum",
        "definitionid",
        "definition",
        "notes",
        "userid",
        "time",
        "selmaho",
        "jargon",
    ),
    "etymology": ("etymologyid", "valsiid", "langid", "content", "time", "userid"),
    "example": (
        "exampleid",
        "valsiid",
        "definitionid",
        "examplenum",
        "content",
        "time",
        "userid",
    ),
    "keywordmapping": ("natlangwordid", "definitionid", "place"),
    "languages": LENSISKU_COPY_COLUMNS["languages"],
    "natlangwords": LENSISKU_COPY_COLUMNS["natlangwords"],
    "pages": LENSISKU_COPY_COLUMNS["pages"],
    "threads": ("threadid", "valsiid", "natlangwordid", "definitionid"),
    "valsi": ("valsiid", "word", "typeid", "userid", "time", "rafsi"),
    "valsitypes": LENSISKU_COPY_COLUMNS["valsitypes"],
}
JBOVLASTE_USER_COLUMNS = ("userid", "username", "realname", "url", "personal")
SCORE_COLUMNS = (
    "definitionid",
    "valsiid",
    "langid",
    "score",
    "votes",
    "last_vote_time",
)

FORBIDDEN_DATA_TABLES = frozenset(
    {
        "users",
        "users_view",
        "definitionvotes",
        "natlangwordvotes",
        "user_sessions",
        "user_session_events",
        "password_reset_requests",
        "password_change_verifications",
        "oauth_accounts",
        "private_messages",
        "message_threads",
        "thread_participants",
        "user_message_blocks",
        "message_encryption_keys",
        "message_notifications",
        "webrtc_signaling",
        "payments",
        "balance_transactions",
        "paypal_subscriptions",
        "payment_audit_log",
        "user_balances",
        "user_search_history",
        "assistant_chats",
        "user_notifications",
        "user_settings",
        "user_profile_images",
        "valsi_subscriptions",
        "follows",
        "comment_bookmarks",
        "comment_opinion_votes",
        "comment_reactions",
        "flashcards",
        "flashcard_levels",
        "flashcard_level_items",
        "flashcard_quiz_options",
        "flashcard_review_history",
        "user_flashcard_progress",
        "user_level_progress",
        "user_quiz_answer_history",
        "level_prerequisites",
        "collections",
        "collection_items",
        "collection_images",
        "collection_item_images",
        "collection_item_sounds",
    }
)

_COPY_HEADER = re.compile(rb"^COPY public\.([a-z_][a-z0-9_]*) \((.*)\) FROM stdin;$")
_MAX_DUMP_LINE = 128 * 1024 * 1024
_MAX_CSV_FIELD = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RawDictionaryDump:
    tables: Mapping[str, tuple[Mapping[str, str | None], ...]]
    users: tuple[Mapping[str, str], ...]
    scores: tuple[Mapping[str, str], ...]


@dataclass(frozen=True, slots=True)
class Keyword:
    word: str
    sense: str
    place: int


@dataclass(frozen=True, slots=True)
class _Word:
    valsiid: int
    word: str
    typeid: int
    userid: int
    created: datetime
    rafsi: str


@dataclass(frozen=True, slots=True)
class _Definition:
    definitionid: int
    valsiid: int
    langid: int
    definition: str
    notes: str
    userid: int
    modified: datetime
    created_at: datetime
    selmaho: str
    jargon: str
    etymology: str
    rafsi: str


@dataclass(frozen=True, slots=True)
class _Version:
    version_id: int
    definition_id: int
    valsiid: int
    langid: int
    definition: str
    notes: str
    selmaho: str
    jargon: str
    keywords: tuple[Keyword, ...]
    user_id: int
    created_at: datetime
    message: str
    etymology: str
    rafsi: str
    mw_revid: int | None


@dataclass(slots=True)
class _DefinitionState:
    definition: _Definition | _Version
    author: str
    updated: datetime
    version: int
    keywords: tuple[Keyword, ...]
    examples: list[tuple[int, str]]


@dataclass(slots=True)
class _WordState:
    word: _Word
    type_name: str
    creator: str
    definitions: dict[int, _DefinitionState]
    current_definition_rafsi: tuple[str, ...]
    etymologies: list[tuple[int, str, str, datetime, str]]
    word_examples: list[tuple[int, str, datetime, str]]
    comments: list[tuple[int, datetime, str, str, str, int | None, int | None]]


@contextmanager
def _binary_stream(path: Path) -> Iterator[BinaryIO]:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as stream:
                yield stream
        else:
            with path.open("rb") as stream:
                yield stream
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise DictionaryParseError(
            f"cannot read dictionary dump {path}: {exc}"
        ) from exc


def _line(stream: BinaryIO, path: Path) -> bytes:
    raw = stream.readline(_MAX_DUMP_LINE + 1)
    if len(raw) > _MAX_DUMP_LINE:
        raise DictionaryParseError(
            f"dictionary dump {path} contains a row over {_MAX_DUMP_LINE} bytes"
        )
    return raw


def _line_body(raw: bytes) -> bytes:
    if raw.endswith(b"\n"):
        raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]
    return raw


def _columns(raw: bytes, path: Path, table: str) -> tuple[str, ...]:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DictionaryParseError(
            f"dictionary dump {path} has non-ASCII COPY columns for {table}"
        ) from exc
    columns: list[str] = []
    for item in text.split(", "):
        if item.startswith('"') and item.endswith('"'):
            item = item[1:-1].replace('""', '"')
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", item):
            raise DictionaryParseError(
                f"dictionary dump {path} has unsafe COPY column {item!r} for {table}"
            )
        columns.append(item)
    return tuple(columns)


def _copy_value(raw: bytes, *, path: Path, table: str) -> str | None:
    if raw == b"\\N":
        return None
    decoded = bytearray()
    index = 0
    escapes = {
        ord("b"): 8,
        ord("f"): 12,
        ord("n"): 10,
        ord("r"): 13,
        ord("t"): 9,
        ord("v"): 11,
    }
    while index < len(raw):
        byte = raw[index]
        if byte != 92:
            decoded.append(byte)
            index += 1
            continue
        index += 1
        if index == len(raw):
            raise DictionaryParseError(
                f"dictionary dump {path} has a trailing COPY escape in {table}"
            )
        escaped = raw[index]
        if escaped in escapes:
            decoded.append(escapes[escaped])
            index += 1
        elif 48 <= escaped <= 55:
            end = index + 1
            while end < min(index + 3, len(raw)) and 48 <= raw[end] <= 55:
                end += 1
            decoded.append(int(raw[index:end], 8))
            index = end
        elif escaped == ord("x"):
            end = index + 1
            while (
                end < min(index + 3, len(raw)) and raw[end] in b"0123456789abcdefABCDEF"
            ):
                end += 1
            if end == index + 1:
                raise DictionaryParseError(
                    f"dictionary dump {path} has an invalid hex COPY escape in {table}"
                )
            decoded.append(int(raw[index + 1 : end], 16))
            index = end
        else:
            decoded.append(escaped)
            index += 1
    try:
        value = decoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DictionaryParseError(
            f"dictionary dump {path} has invalid UTF-8 data in {table}"
        ) from exc
    if "\0" in value:
        raise DictionaryParseError(
            f"dictionary dump {path} has a NUL in public data table {table}"
        )
    return value


def load_copy_tables(
    path: Path,
    expected: Mapping[str, Sequence[str]] = LENSISKU_COPY_COLUMNS,
    *,
    forbidden: frozenset[str] = FORBIDDEN_DATA_TABLES,
) -> dict[str, tuple[Mapping[str, str | None], ...]]:
    """Load selected pg_dump COPY blocks, rejecting private tables before rows."""

    wanted = {name: tuple(columns) for name, columns in expected.items()}
    rows: dict[str, list[Mapping[str, str | None]]] = {name: [] for name in wanted}
    found: set[str] = set()
    with _binary_stream(path) as stream:
        crlf: bool | None = None

        def next_line() -> bytes:
            nonlocal crlf
            raw_line = _line(stream, path)
            if not raw_line:
                return raw_line
            if not raw_line.endswith(b"\n"):
                raise DictionaryParseError(
                    f"dictionary dump {path} has a final line without a newline"
                )
            line_is_crlf = raw_line.endswith(b"\r\n")
            if crlf is None:
                crlf = line_is_crlf
            elif line_is_crlf != crlf:
                raise DictionaryParseError(
                    f"dictionary dump {path} mixes LF and CRLF line endings"
                )
            return raw_line

        while raw := next_line():
            header = _COPY_HEADER.fullmatch(_line_body(raw))
            if header is None:
                continue
            table = header.group(1).decode("ascii")
            if table in forbidden:
                raise DictionaryParseError(
                    f"dictionary dump {path} contains forbidden private table {table}"
                )
            columns = _columns(header.group(2), path, table)
            selected = wanted.get(table)
            if selected is not None:
                if table in found:
                    raise DictionaryParseError(
                        f"dictionary dump {path} repeats COPY table {table}"
                    )
                if columns != selected:
                    raise DictionaryParseError(
                        f"dictionary dump {path} has unexpected columns for {table}: "
                        f"{', '.join(columns)}"
                    )
                found.add(table)
            while True:
                raw_row = next_line()
                if not raw_row:
                    raise DictionaryParseError(
                        f"dictionary dump {path} ends inside COPY table {table}"
                    )
                row_body = _line_body(raw_row)
                if row_body == b"\\.":
                    break
                if selected is None:
                    continue
                while row_body.count(b"\t") < len(selected) - 1:
                    continuation = next_line()
                    if not continuation or _line_body(continuation) == b"\\.":
                        raise DictionaryParseError(
                            f"dictionary dump {path} has an incomplete row in {table}"
                        )
                    row_body += b"\n" + _line_body(continuation)
                fields = row_body.split(b"\t")
                if len(fields) != len(selected):
                    raise DictionaryParseError(
                        f"dictionary dump {path} has {len(fields)} fields in {table}; "
                        f"expected {len(selected)}"
                    )
                rows[table].append(
                    {
                        name: _copy_value(value, path=path, table=table)
                        for name, value in zip(selected, fields, strict=True)
                    }
                )
    missing = sorted(wanted.keys() - found)
    if missing:
        raise DictionaryParseError(
            f"dictionary dump {path} is missing COPY tables: {', '.join(missing)}"
        )
    return {name: tuple(items) for name, items in rows.items()}


@contextmanager
def _text_stream(path: Path) -> Iterator[TextIO]:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
                yield stream
        else:
            with path.open("r", encoding="utf-8", newline="") as stream:
                yield stream
    except (OSError, EOFError, UnicodeError, gzip.BadGzipFile) as exc:
        raise DictionaryParseError(f"cannot read dictionary CSV {path}: {exc}") from exc


def _load_csv(path: Path, columns: Sequence[str]) -> tuple[Mapping[str, str], ...]:
    previous_limit = csv.field_size_limit()
    csv.field_size_limit(_MAX_CSV_FIELD)
    try:
        with _text_stream(path) as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(columns):
                raise DictionaryParseError(
                    f"dictionary CSV {path} has unexpected columns: "
                    f"{', '.join(reader.fieldnames or ())}"
                )
            rows: list[Mapping[str, str]] = []
            for line_number, row in enumerate(reader, 2):
                if None in row or any(value is None for value in row.values()):
                    raise DictionaryParseError(
                        f"dictionary CSV {path}:{line_number} has the wrong field count"
                    )
                clean = {name: value for name, value in row.items() if name is not None}
                if any("\0" in value for value in clean.values()):
                    raise DictionaryParseError(
                        f"dictionary CSV {path}:{line_number} contains a NUL"
                    )
                rows.append(clean)
            return tuple(rows)
    except csv.Error as exc:
        raise DictionaryParseError(
            f"cannot parse dictionary CSV {path}: {exc}"
        ) from exc
    finally:
        csv.field_size_limit(previous_limit)


def load_dictionary_dump(dump: Path, users: Path, scores: Path) -> RawDictionaryDump:
    """Load the three sanitized Lensisku export components."""

    return RawDictionaryDump(
        tables=load_copy_tables(dump),
        users=_load_csv(users, LENSISKU_USER_COLUMNS),
        scores=_load_csv(scores, SCORE_COLUMNS),
    )


def load_jbovlaste_dump(dump: Path, users: Path, scores: Path) -> RawDictionaryDump:
    """Load the sanitized older export for diff-only comparison."""

    return RawDictionaryDump(
        tables=load_copy_tables(dump, JBOVLASTE_COPY_COLUMNS),
        users=_load_csv(users, JBOVLASTE_USER_COLUMNS),
        scores=_load_csv(scores, SCORE_COLUMNS),
    )


def _required(row: Mapping[str, str | None], name: str, context: str) -> str:
    value = row.get(name)
    if value is None:
        raise DictionaryParseError(f"{context}: {name} must not be null")
    if "\0" in value:
        raise DictionaryParseError(f"{context}: {name} contains a NUL")
    return value


def _optional(row: Mapping[str, str | None], name: str) -> str:
    value = row.get(name)
    return "" if value is None else value


def _integer(
    row: Mapping[str, str | None], name: str, context: str, *, minimum: int = 0
) -> int:
    value = _required(row, name, context)
    if not re.fullmatch(r"-?[0-9]+", value):
        raise DictionaryParseError(f"{context}: {name} is not an integer")
    parsed = int(value)
    if parsed < minimum:
        raise DictionaryParseError(f"{context}: {name} must be at least {minimum}")
    return parsed


def _optional_integer(
    row: Mapping[str, str | None], name: str, context: str
) -> int | None:
    if row.get(name) is None:
        return None
    return _integer(row, name, context)


def _unix_time(row: Mapping[str, str | None], name: str, context: str) -> datetime:
    seconds = _integer(row, name, context)
    try:
        return datetime.fromtimestamp(seconds, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise DictionaryParseError(
            f"{context}: {name} is outside the UTC range"
        ) from exc


def _pg_time(row: Mapping[str, str | None], name: str, context: str) -> datetime:
    value = _required(row, name, context)
    try:
        parsed = datetime.fromisoformat(value.replace(" ", "T", 1))
    except ValueError as exc:
        raise DictionaryParseError(
            f"{context}: {name} is not an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise DictionaryParseError(f"{context}: {name} lacks a UTC offset")
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _git_time(value: datetime) -> datetime:
    return value.replace(microsecond=0)


def _identity(username: str) -> Identity:
    return Identity.namespaced("jbovlaste.lojban.org", username)


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


_SLUG_SAFE = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'_,-"
)


def slug(value: str) -> str:
    """Apply SPEC §3.1.5 to one dictionary word or page name."""

    if not value:
        raise DictionaryParseError("dictionary slug source must not be empty")
    normalized = unicodedata.normalize("NFC", value)
    tokens: list[str] = []
    for character in normalized:
        if character == " ":
            tokens.append("_")
        elif character in _SLUG_SAFE:
            tokens.append(character)
        else:
            tokens.extend(f"%{byte:02X}" for byte in character.encode("utf-8"))
    if normalized.startswith("-"):
        tokens[0] = "%2D"
    encoded = "".join(tokens)
    if len(encoded) <= 200:
        return encoded
    suffix = "-" + hashlib.sha1(normalized.encode()).hexdigest()[:8]
    kept: list[str] = []
    length = 0
    for token in tokens:
        if length + len(token) + len(suffix) > 200:
            break
        kept.append(token)
        length += len(token)
    return "".join(kept) + suffix


def _keywords_from_json(value: str, context: str) -> tuple[Keyword, ...]:
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DictionaryParseError(f"{context}: invalid keyword JSON") from exc
    if not isinstance(raw, list):
        raise DictionaryParseError(f"{context}: keywords must be a JSON array")
    keywords: list[Keyword] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DictionaryParseError(f"{context}: keyword {index} must be an object")
        word = item.get("word")
        meaning = item.get("meaning")
        place = item.get("place", 0)
        if not isinstance(word, str) or not word:
            raise DictionaryParseError(f"{context}: keyword {index} has no word")
        if meaning is not None and not isinstance(meaning, str):
            raise DictionaryParseError(
                f"{context}: keyword {index} has invalid meaning"
            )
        if not isinstance(place, int) or isinstance(place, bool) or place < 0:
            raise DictionaryParseError(f"{context}: keyword {index} has invalid place")
        keywords.append(Keyword(word, meaning or "", place))
    return tuple(sorted(keywords, key=lambda item: (item.place, item.word, item.sense)))


def _version(row: Mapping[str, str | None]) -> _Version:
    context = f"definition version {_required(row, 'version_id', 'definition version')}"
    gloss = _keywords_from_json(_required(row, "gloss_keywords", context), context)
    places = _keywords_from_json(_required(row, "place_keywords", context), context)
    if any(keyword.place != 0 for keyword in gloss):
        raise DictionaryParseError(f"{context}: gloss keyword has a nonzero place")
    return _Version(
        version_id=_integer(row, "version_id", context, minimum=1),
        definition_id=_integer(row, "definition_id", context, minimum=1),
        valsiid=_integer(row, "valsiid", context, minimum=1),
        langid=_integer(row, "langid", context),
        definition=_required(row, "definition", context),
        notes=_optional(row, "notes"),
        selmaho=_optional(row, "selmaho"),
        jargon=_optional(row, "jargon"),
        keywords=tuple(
            sorted(
                (*gloss, *places),
                key=lambda item: (item.place, item.word, item.sense),
            )
        ),
        user_id=_integer(row, "user_id", context, minimum=1),
        created_at=_pg_time(row, "created_at", context),
        message=_required(row, "message", context),
        etymology=_optional(row, "etymology"),
        rafsi=_optional(row, "rafsi"),
        mw_revid=_optional_integer(row, "mw_revid", context),
    )


def _definition_state_tuple(value: _Definition | _Version) -> tuple[str, ...]:
    return (
        value.definition,
        value.notes,
        value.selmaho,
        value.jargon,
    )


def _render_word(state: _WordState) -> str:
    definition_states = list(state.definitions.values())
    selmaho = sorted(
        {
            item.definition.selmaho
            for item in definition_states
            if item.definition.selmaho
        }
    )
    rafsi = sorted(
        {
            value
            for value in (
                *state.word.rafsi.split(),
                *state.current_definition_rafsi,
            )
            if value
        }
    )
    lines = [
        f"word = {_quote(state.word.word)}",
        f"type = {_quote(state.type_name)}",
        f"rafsi = [{', '.join(_quote(item) for item in rafsi)}]",
        f"selmaho = [{', '.join(_quote(item) for item in selmaho)}]",
        f"created = {_quote(_iso(state.word.created))}",
        f"creator = {_quote(state.creator)}",
        f"source_ids = [{_quote(f'valsi={state.word.valsiid}')}]",
    ]
    for etymology_id, language, author, updated, content in state.etymologies:
        lines.extend(
            [
                "",
                "[[etymology]]",
                f"id = {etymology_id}",
                f"lang = {_quote(language)}",
                f"author = {_quote(author)}",
                f"updated = {_quote(_iso(updated))}",
                f"content = {_quote(content)}",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_keywords(keywords: Sequence[Keyword]) -> str:
    values = [
        "{ "
        f"word = {_quote(item.word)}, sense = {_quote(item.sense)}, place = {item.place}"
        " }"
        for item in keywords
    ]
    return f"[{', '.join(values)}]"


def _definition_id(value: _Definition | _Version) -> int:
    return value.definition_id if isinstance(value, _Version) else value.definitionid


def _render_definition(
    state: _DefinitionState, word: _Word, language: str, score: int
) -> str:
    value = state.definition
    lines = [
        "+++",
        f"id = {_definition_id(value)}",
        f"word = {_quote(word.word)}",
        f"lang = {_quote(language)}",
        f"author = {_quote(state.author)}",
        f"updated = {_quote(_iso(state.updated))}",
        f"version = {state.version}",
        f"score = {score}",
        'status = "current"',
        f"jargon = {_quote(value.jargon)}",
        f"selmaho = {_quote(value.selmaho)}",
        f"keywords = {_render_keywords(state.keywords)}",
        "+++",
        "",
        value.definition,
        "",
        "## Notes",
        "",
        value.notes,
        "",
        "## Examples",
    ]
    for example_id, content in state.examples:
        lines.extend(["", f"### Example {example_id}", "", content])
    return "\n".join(lines) + "\n"


def _render_word_examples(state: _WordState) -> str:
    parts: list[str] = []
    for example_id, content, timestamp, author in state.word_examples:
        parts.extend(
            [
                f"## {_iso(timestamp)} — {author} (example {example_id})",
                "",
                content,
                "",
            ]
        )
    return "\n".join(parts)


def _render_comments(state: _WordState) -> str:
    parts: list[str] = []
    for (
        comment_id,
        timestamp,
        author,
        subject,
        content,
        parentid,
        definitionid,
    ) in state.comments:
        target = f", on definition {definitionid}" if definitionid else ""
        reply = f", in reply to {parentid}" if parentid else ""
        parts.extend(
            [
                f"## {_iso(timestamp)} — {author} (comment {comment_id}{target}{reply})",
                "",
                subject,
                "",
                content,
                "",
            ]
        )
    return "\n".join(parts)


def _summary(word: str, suffix: str, message: str = "") -> str:
    clean_message = " ".join(message.split())[:36]
    tail = f" {suffix}"
    message_tail = f" {clean_message}" if clean_message else ""
    budget = 72 - len("dict: ") - len(tail) - len(message_tail)
    if budget < 1:
        message_tail = ""
        budget = 72 - len("dict: ") - len(tail)
    shown = word if len(word) <= budget else word[: max(1, budget - 1)] + "…"
    return f"{shown}{tail}{message_tail}"


def _csv_text(columns: Sequence[str], rows: Sequence[Mapping[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _comment_text(value: str, context: str) -> str:
    try:
        blocks = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DictionaryParseError(f"{context}: content is invalid JSON") from exc
    if not isinstance(blocks, list):
        raise DictionaryParseError(f"{context}: content must be a JSON array")
    text: list[str] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise DictionaryParseError(f"{context}: block {index} must be an object")
        kind = block.get("type")
        data = block.get("data")
        if not isinstance(kind, str) or not isinstance(data, str):
            raise DictionaryParseError(
                f"{context}: block {index} lacks string type/data"
            )
        if kind == "text":
            text.append(data)
    return "\n".join(text)


def _page_content(content: str, compressed: str, context: str) -> str:
    if compressed == "f":
        return content
    if compressed != "t":
        raise DictionaryParseError(f"{context}: compressed must be t or f")
    try:
        packed = base64.b64decode(content, validate=True)
        return zlib.decompress(packed).decode("utf-8")
    except (ValueError, zlib.error, UnicodeDecodeError) as exc:
        raise DictionaryParseError(
            f"{context}: invalid compressed page content"
        ) from exc


def _indexed(
    rows: Sequence[Mapping[str, str | None]],
    key: str,
    label: str,
    *,
    minimum: int = 1,
) -> dict[int, Mapping[str, str | None]]:
    result: dict[int, Mapping[str, str | None]] = {}
    for row in rows:
        identifier = _integer(row, key, label, minimum=minimum)
        if identifier in result:
            raise DictionaryParseError(f"duplicate {label} id {identifier}")
        result[identifier] = row
    return result


_DIFF_FIELDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "languages": (
        ("langid",),
        ("tag", "englishname", "lojbanname", "realname", "forlojban", "url"),
    ),
    "valsitypes": (("typeid",), ("descriptor",)),
    "valsi": (("valsiid",), ("word", "time", "rafsi")),
    "definitions": (
        ("definitionid",),
        ("definition", "notes", "time", "selmaho", "jargon"),
    ),
    "comments": (("commentid",), ("time", "subject", "content")),
    "etymology": (("etymologyid",), ("content", "time")),
    "example": (("exampleid",), ("content", "time")),
    "natlangwords": (("wordid",), ("word", "meaning", "time", "notes")),
    "pages": (("langid", "pagename", "version"), ("time", "content")),
    "threads": (("threadid",), ()),
    "keywordmapping": (("natlangwordid", "definitionid", "place"), ()),
}

_INTEGER_COLUMNS: dict[str, tuple[str, ...]] = {
    "languages": ("langid",),
    "valsitypes": ("typeid",),
    "valsi": ("valsiid", "typeid", "userid", "time", "source_langid"),
    "definitions": (
        "langid",
        "valsiid",
        "definitionnum",
        "definitionid",
        "userid",
        "time",
    ),
    "comments": ("commentid", "threadid", "parentid", "userid", "commentnum", "time"),
    "definition_versions": (
        "version_id",
        "definition_id",
        "langid",
        "valsiid",
        "user_id",
        "mw_revid",
    ),
    "etymology": ("etymologyid", "valsiid", "langid", "time", "userid"),
    "example": (
        "exampleid",
        "valsiid",
        "definitionid",
        "examplenum",
        "time",
        "userid",
    ),
    "natlangwords": ("wordid", "langid", "meaningnum", "userid", "time"),
    "keywordmapping": ("natlangwordid", "definitionid", "place"),
    "pages": ("version", "time", "userid", "langid"),
    "threads": (
        "threadid",
        "valsiid",
        "natlangwordid",
        "definitionid",
        "last_comment_id",
        "last_comment_user_id",
        "last_comment_time",
        "total_comments",
        "creator_user_id",
        "target_user_id",
        "definition_link_id",
        "collection_id",
    ),
}


def validate_integer_shapes(data: RawDictionaryDump) -> None:
    malformed: list[str] = []
    for table, columns in _INTEGER_COLUMNS.items():
        for row_number, row in enumerate(data.tables.get(table, ()), 1):
            for column in columns:
                value = row.get(column)
                if value is not None and not re.fullmatch(r"-?[0-9]+", value):
                    malformed.append(f"{table}[{row_number}].{column}={value[:24]!r}")
    for label, rows, columns in (
        ("users", data.users, ("userid",)),
        (
            "scores",
            data.scores,
            ("definitionid", "valsiid", "langid", "score", "votes", "last_vote_time"),
        ),
    ):
        for row_number, row in enumerate(rows, 1):
            for column in columns:
                value = row.get(column)
                if value is not None and not re.fullmatch(r"-?[0-9]+", value):
                    malformed.append(f"{label}[{row_number}].{column}={value[:24]!r}")
    if malformed:
        shown = ", ".join(malformed[:20])
        suffix = f" (+{len(malformed) - 20} more)" if len(malformed) > 20 else ""
        raise DictionaryParseError(
            f"dictionary export has {len(malformed)} malformed integer field(s): "
            f"{shown}{suffix}"
        )


def _diff_key(
    row: Mapping[str, str | None], fields: Sequence[str], context: str
) -> tuple[str, ...]:
    return tuple(_required(row, name, context) for name in fields)


def _diff_value(
    table: str,
    row: Mapping[str, str | None],
    fields: Sequence[str],
    *,
    lensisku: bool,
) -> tuple[str, ...]:
    values: list[str] = []
    for field in fields:
        value = _optional(row, field)
        if table == "comments" and field == "content" and lensisku:
            value = _comment_text(value, "dictionary diff comment")
        elif table == "pages" and field == "content":
            value = _page_content(
                value,
                _required(row, "compressed", "dictionary diff page"),
                "dictionary diff page",
            )
        values.append(value)
    return tuple(values)


def jbovlaste_diff(data: RawDictionaryDump, older: RawDictionaryDump) -> str:
    """Render old-only or text/time-divergent rows without merging snapshots."""

    findings: list[Mapping[str, object]] = []
    for table, (key_fields, compared_fields) in _DIFF_FIELDS.items():
        current: dict[tuple[str, ...], Mapping[str, str | None]] = {}
        for row in data.tables[table]:
            key = _diff_key(row, key_fields, f"Lensisku {table}")
            if key in current:
                raise DictionaryParseError(f"duplicate Lensisku {table} row {key!r}")
            current[key] = row
        seen_old: set[tuple[str, ...]] = set()
        for row in older.tables[table]:
            key = _diff_key(row, key_fields, f"jbovlaste {table}")
            if key in seen_old:
                raise DictionaryParseError(f"duplicate jbovlaste {table} row {key!r}")
            seen_old.add(key)
            current_row = current.get(key)
            if current_row is None:
                findings.append(
                    {
                        "table": table,
                        "row_id": ";".join(key),
                        "status": "only-jbovlaste",
                        "fields": "",
                    }
                )
                continue
            old_values = _diff_value(table, row, compared_fields, lensisku=False)
            new_values = _diff_value(table, current_row, compared_fields, lensisku=True)
            changed = [
                name
                for name, old, new in zip(
                    compared_fields, old_values, new_values, strict=True
                )
                if old != new
            ]
            if changed:
                findings.append(
                    {
                        "table": table,
                        "row_id": ";".join(key),
                        "status": "different",
                        "fields": ";".join(changed),
                    }
                )
    findings.sort(key=lambda row: (str(row["table"]), str(row["row_id"])))
    return _csv_text(("table", "row_id", "status", "fields"), findings)


def project(
    data: RawDictionaryDump,
    *,
    export_date: str,
    older: RawDictionaryDump | None = None,
) -> Iterator[Event]:
    """Project one sanitized Lensisku snapshot into source events."""

    try:
        datetime.fromisoformat(export_date)
    except ValueError as exc:
        raise DictionaryParseError("dictionary export_date must be YYYY-MM-DD") from exc
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", export_date):
        raise DictionaryParseError("dictionary export_date must be YYYY-MM-DD")
    validate_integer_shapes(data)

    users: dict[int, str] = {}
    for row in data.users:
        context = f"user {row.get('userid', '<missing>')}"
        userid = _integer(row, "userid", context)
        username = _required(row, "username", context)
        if userid in users:
            raise DictionaryParseError(f"duplicate user id {userid}")
        users[userid] = username

    language_rows = _indexed(data.tables["languages"], "langid", "language", minimum=0)
    languages = {
        identifier: _required(row, "tag", f"language {identifier}")
        for identifier, row in language_rows.items()
    }
    type_rows = _indexed(data.tables["valsitypes"], "typeid", "valsi type", minimum=0)
    types = {
        identifier: _required(row, "descriptor", f"valsi type {identifier}")
        for identifier, row in type_rows.items()
    }

    all_versions: list[_Version] = []
    version_ids: set[int] = set()
    mirror_definition_ids: set[int] = set()
    for row in data.tables["definition_versions"]:
        value = _version(row)
        if value.version_id in version_ids:
            raise DictionaryParseError(
                f"duplicate definition version {value.version_id}"
            )
        version_ids.add(value.version_id)
        all_versions.append(value)
        if value.mw_revid is not None:
            mirror_definition_ids.add(value.definition_id)

    ordinary_definition_words: set[int] = set()
    mirror_definition_words: set[int] = set()
    for row in data.tables["definitions"]:
        context = f"definition {_required(row, 'definitionid', 'definition')}"
        definition_id = _integer(row, "definitionid", context)
        valsiid = _integer(row, "valsiid", context)
        if definition_id in mirror_definition_ids:
            mirror_definition_words.add(valsiid)
        elif definition_id != 0:
            ordinary_definition_words.add(valsiid)
    excluded_word_ids = mirror_definition_words - ordinary_definition_words

    words: dict[int, _Word] = {}
    paths: dict[str, str] = {}
    for row in data.tables["valsi"]:
        context = f"valsi {_required(row, 'valsiid', 'valsi')}"
        valsiid = _integer(row, "valsiid", context)
        if valsiid == 0:
            if _required(row, "word", context) or _integer(row, "userid", context) != 0:
                raise DictionaryParseError("valsi 0 is not the expected empty sentinel")
            continue
        if valsiid in excluded_word_ids:
            continue
        value = _Word(
            valsiid=valsiid,
            word=_required(row, "word", context),
            typeid=_integer(row, "typeid", context),
            userid=_integer(row, "userid", context, minimum=1),
            created=_unix_time(row, "time", context),
            rafsi=_optional(row, "rafsi"),
        )
        if value.valsiid in words:
            raise DictionaryParseError(f"duplicate valsi id {value.valsiid}")
        if value.typeid not in types:
            raise DictionaryParseError(f"{context}: unknown type id {value.typeid}")
        if value.userid not in users:
            raise DictionaryParseError(f"{context}: unknown user id {value.userid}")
        path = f"dict/{slug(value.word)}"
        previous = paths.get(path)
        if previous is not None and previous != value.word:
            raise DictionaryParseError(
                f"dictionary slug collision: {previous!r} and {value.word!r} -> {path}"
            )
        paths[path] = value.word
        words[value.valsiid] = value

    definitions: dict[int, _Definition] = {}
    baseline_event_times: dict[int, datetime] = {}
    baseline_time_clamps = 0
    for row in data.tables["definitions"]:
        context = f"definition {_required(row, 'definitionid', 'definition')}"
        definitionid = _integer(row, "definitionid", context)
        if definitionid == 0:
            if (
                _integer(row, "valsiid", context) != 0
                or _integer(row, "userid", context) != 0
                or _required(row, "definition", context)
            ):
                raise DictionaryParseError(
                    "definition 0 is not the expected empty sentinel"
                )
            continue
        if definitionid in mirror_definition_ids:
            continue
        value = _Definition(
            definitionid=definitionid,
            valsiid=_integer(row, "valsiid", context, minimum=1),
            langid=_integer(row, "langid", context),
            definition=_required(row, "definition", context),
            notes=_optional(row, "notes"),
            userid=_integer(row, "userid", context, minimum=1),
            modified=_unix_time(row, "time", context),
            created_at=_pg_time(row, "created_at", context),
            selmaho=_optional(row, "selmaho"),
            jargon=_optional(row, "jargon"),
            etymology=_optional(row, "etymology"),
            rafsi=_optional(row, "rafsi"),
        )
        if value.definitionid in definitions:
            raise DictionaryParseError(f"duplicate definition id {value.definitionid}")
        if value.valsiid not in words:
            raise DictionaryParseError(f"{context}: unknown valsi id {value.valsiid}")
        if value.langid not in languages:
            raise DictionaryParseError(f"{context}: unknown language id {value.langid}")
        if value.userid not in users:
            raise DictionaryParseError(f"{context}: unknown user id {value.userid}")
        floored_baseline = _git_time(value.created_at)
        word_time = words[value.valsiid].created
        if floored_baseline < word_time:
            skew = int((word_time - floored_baseline).total_seconds())
            if skew > 10:
                raise DictionaryParseError(
                    f"{context}: baseline predates its valsi by {skew} seconds"
                )
            baseline_time_clamps += 1
        baseline_event_times[value.definitionid] = max(floored_baseline, word_time)
        definitions[value.definitionid] = value

    natural_words = _indexed(
        data.tables["natlangwords"], "wordid", "natural word", minimum=0
    )
    current_keywords: dict[int, list[Keyword]] = defaultdict(list)
    cross_language_keywords = 0
    for row in data.tables["keywordmapping"]:
        context = "keyword mapping"
        definition_id = _integer(row, "definitionid", context, minimum=1)
        natural_id = _integer(row, "natlangwordid", context)
        place = _integer(row, "place", context)
        if definition_id in mirror_definition_ids:
            continue
        definition = definitions.get(definition_id)
        natural = natural_words.get(natural_id)
        if definition is None or natural is None:
            raise DictionaryParseError(
                f"keyword mapping references missing ids {definition_id}/{natural_id}"
            )
        if (
            _integer(natural, "langid", f"natural word {natural_id}")
            != definition.langid
        ):
            cross_language_keywords += 1
        current_keywords[definition_id].append(
            Keyword(
                _required(natural, "word", f"natural word {natural_id}"),
                _optional(natural, "meaning"),
                place,
            )
        )
    keyword_states = {
        identifier: tuple(
            sorted(items, key=lambda item: (item.place, item.word, item.sense))
        )
        for identifier, items in current_keywords.items()
    }

    scores: dict[int, int] = {}
    score_key_mismatches = 0
    score_rows_merged = 0
    sentinel_scores_skipped = 0
    for row in data.scores:
        context = f"definition score {row.get('definitionid', '<missing>')}"
        definition_id = _integer(row, "definitionid", context)
        if definition_id == 0:
            if (
                _integer(row, "valsiid", context) != 0
                or _integer(row, "langid", context) != 0
            ):
                raise DictionaryParseError(
                    "definition score 0 is not the expected sentinel"
                )
            sentinel_scores_skipped += 1
            continue
        if definition_id in mirror_definition_ids:
            continue
        definition = definitions.get(definition_id)
        if definition is None:
            raise DictionaryParseError(f"{context}: unknown definition")
        if (
            _integer(row, "valsiid", context, minimum=1) != definition.valsiid
            or _integer(row, "langid", context) != definition.langid
        ):
            score_key_mismatches += 1
        score = _integer(row, "score", context, minimum=-(2**63))
        if definition_id in scores:
            score_rows_merged += 1
        scores[definition_id] = scores.get(definition_id, 0) + score

    direct_versions: dict[int, list[_Version]] = defaultdict(list)
    mirror_versions_excluded = 0
    for value in all_versions:
        if value.definition_id in mirror_definition_ids:
            mirror_versions_excluded += 1
            continue
        definition = definitions.get(value.definition_id)
        if definition is None:
            raise DictionaryParseError(
                f"definition version {value.version_id}: unknown definition {value.definition_id}"
            )
        if value.valsiid != definition.valsiid:
            raise DictionaryParseError(
                f"definition version {value.version_id}: valsi id disagrees"
            )
        if value.langid not in languages:
            raise DictionaryParseError(
                f"definition version {value.version_id}: unknown language {value.langid}"
            )
        if value.user_id not in users:
            raise DictionaryParseError(
                f"definition version {value.version_id}: unknown user {value.user_id}"
            )
        if value.mw_revid is not None:
            raise DictionaryParseError(
                f"definition version {value.version_id}: incomplete mirror exclusion"
            )
        direct_versions[value.definition_id].append(value)

    baselines: dict[int, _Definition | _Version] = {}
    edits: list[_Version] = []
    version_counts: dict[int, int] = {}
    latest_legacy_time_deltas: list[int] = []
    latest_state_mismatches: list[tuple[int, tuple[str, ...]]] = []
    latest_auxiliary_mismatches: Counter[str] = Counter()
    for definition_id, definition in definitions.items():
        versions = sorted(
            direct_versions.get(definition_id, ()),
            key=lambda item: (item.created_at, item.version_id),
        )
        if not versions:
            baselines[definition_id] = definition
            version_counts[definition_id] = 1
            continue
        baseline = versions[0]
        if baseline.created_at != definition.created_at:
            raise DictionaryParseError(
                f"definition {definition_id}: earliest direct version is not the baseline"
            )
        baselines[definition_id] = baseline
        edits.extend(versions[1:])
        version_counts[definition_id] = len(versions)
        latest = versions[-1]
        changed = tuple(
            name
            for name, old, new in zip(
                ("definition", "notes", "selmaho", "jargon"),
                _definition_state_tuple(latest),
                _definition_state_tuple(definition),
                strict=True,
            )
            if old != new
        )
        if latest.langid != definition.langid:
            changed = (*changed, "langid")
        if latest.keywords != keyword_states.get(definition_id, ()):
            changed = (*changed, "keywords")
        if changed:
            latest_state_mismatches.append((definition_id, changed))
        if latest.etymology != definition.etymology:
            latest_auxiliary_mismatches["etymology"] += 1
        if latest.rafsi != definition.rafsi:
            latest_auxiliary_mismatches["rafsi"] += 1
        legacy_delta = int(
            (definition.modified - _git_time(latest.created_at)).total_seconds()
        )
        if legacy_delta:
            latest_legacy_time_deltas.append(legacy_delta)

    if latest_state_mismatches:
        field_counts = Counter(
            field
            for _definition_id, fields in latest_state_mismatches
            for field in fields
        )
        shown = ", ".join(
            f"{definition_id}({';'.join(fields)})"
            for definition_id, fields in latest_state_mismatches[:20]
        )
        suffix = (
            f" (+{len(latest_state_mismatches) - 20} more)"
            if len(latest_state_mismatches) > 20
            else ""
        )
        raise DictionaryParseError(
            f"{len(latest_state_mismatches)} latest definition version(s) disagree "
            f"with current state; fields={dict(sorted(field_counts.items()))}: "
            f"{shown}{suffix}"
        )

    current_definition_rafsi: dict[int, set[str]] = defaultdict(set)
    for definition in definitions.values():
        if definition.rafsi:
            current_definition_rafsi[definition.valsiid].add(definition.rafsi)
    word_states = {
        identifier: _WordState(
            word=value,
            type_name=types[value.typeid],
            creator=users[value.userid],
            definitions={},
            current_definition_rafsi=tuple(
                sorted(current_definition_rafsi.get(identifier, ()))
            ),
            etymologies=[],
            word_examples=[],
            comments=[],
        )
        for identifier, value in words.items()
    }

    threads = _indexed(data.tables["threads"], "threadid", "thread", minimum=0)
    earliest_exact_child: dict[int, datetime] = {}
    for row in data.tables["example"]:
        context = f"example {_required(row, 'exampleid', 'example')}"
        definition_id = _integer(row, "definitionid", context)
        if definition_id in definitions:
            child_time = _unix_time(row, "time", context)
            previous = earliest_exact_child.get(definition_id)
            if previous is None or child_time < previous:
                earliest_exact_child[definition_id] = child_time
    for row in data.tables["comments"]:
        context = f"comment {_required(row, 'commentid', 'comment')}"
        thread_id = _integer(row, "threadid", context)
        thread = threads.get(thread_id)
        if thread is None:
            raise DictionaryParseError(f"{context}: unknown thread {thread_id}")
        definition_id = _optional_integer(thread, "definitionid", f"thread {thread_id}")
        if definition_id in definitions:
            child_time = _unix_time(row, "time", context)
            previous = earliest_exact_child.get(definition_id)
            if previous is None or child_time < previous:
                earliest_exact_child[definition_id] = child_time

    baseline_window_ends = dict(baseline_event_times)
    baseline_dependency_clamps = 0
    for definition_id, child_time in earliest_exact_child.items():
        definition = definitions[definition_id]
        word_time = words[definition.valsiid].created
        if child_time < word_time:
            raise DictionaryParseError(
                f"definition {definition_id}: exact child predates its valsi"
            )
        if child_time < baseline_event_times[definition_id]:
            baseline_event_times[definition_id] = child_time
            baseline_dependency_clamps += 1

    operations: list[tuple[datetime, int, str, str, object]] = []
    for word in words.values():
        operations.append((word.created, 0, f"valsi={word.valsiid}", "word", word))
    for definition_id, baseline in baselines.items():
        definition = definitions[definition_id]
        operations.append(
            (
                baseline_event_times[definition_id],
                1,
                f"definition={definition_id} version=0",
                "definition",
                baseline,
            )
        )
    for version in edits:
        operations.append(
            (
                version.created_at,
                2,
                f"definition={version.definition_id} version={version.version_id}",
                "version",
                version,
            )
        )
    for row in data.tables["etymology"]:
        context = f"etymology {_required(row, 'etymologyid', 'etymology')}"
        identifier = _integer(row, "etymologyid", context, minimum=1)
        if _integer(row, "valsiid", context, minimum=1) in excluded_word_ids:
            continue
        operations.append(
            (
                _unix_time(row, "time", context),
                3,
                f"etymology={identifier}",
                "etymology",
                row,
            )
        )
    for row in data.tables["example"]:
        context = f"example {_required(row, 'exampleid', 'example')}"
        identifier = _integer(row, "exampleid", context, minimum=1)
        if (
            _integer(row, "valsiid", context, minimum=1) in excluded_word_ids
            or _integer(row, "definitionid", context) in mirror_definition_ids
        ):
            continue
        operations.append(
            (
                _unix_time(row, "time", context),
                4,
                f"example={identifier}",
                "example",
                row,
            )
        )

    ignored_comments = 0
    sentinel_comments_skipped = 0
    for row in data.tables["comments"]:
        context = f"comment {_required(row, 'commentid', 'comment')}"
        identifier = _integer(row, "commentid", context)
        thread_id = _integer(row, "threadid", context)
        if identifier == 0:
            if (
                thread_id != 0
                or _integer(row, "userid", context) != 0
                or _integer(row, "time", context) != 0
            ):
                raise DictionaryParseError(
                    "comment 0 is not the expected zero sentinel"
                )
            sentinel_comments_skipped += 1
            continue
        thread = threads.get(thread_id)
        if thread is None:
            raise DictionaryParseError(f"{context}: unknown thread {thread_id}")
        thread_valsiid = _optional_integer(thread, "valsiid", f"thread {thread_id}")
        thread_definitionid = _optional_integer(
            thread, "definitionid", f"thread {thread_id}"
        )
        if not thread_valsiid and not thread_definitionid:
            ignored_comments += 1
            continue
        if (
            thread_valsiid in excluded_word_ids
            or thread_definitionid in mirror_definition_ids
        ):
            ignored_comments += 1
            continue
        operations.append(
            (
                _unix_time(row, "time", context),
                5,
                f"comment={identifier}",
                "comment",
                row,
            )
        )
    for row in data.tables["pages"]:
        context = f"jbovlaste page {_required(row, 'pagename', 'jbovlaste page')}"
        version = _integer(row, "version", context, minimum=1)
        operations.append(
            (
                _unix_time(row, "time", context),
                6,
                f"jvspage={_required(row, 'pagename', context)}@{version}",
                "page",
                row,
            )
        )

    events: list[Event] = []
    page_paths: dict[str, tuple[int, str]] = {}
    for timestamp, _priority, source_id, kind, payload in sorted(
        operations, key=lambda item: (item[0], item[1], item[2])
    ):
        if kind == "word":
            assert isinstance(payload, _Word)
            state = word_states[payload.valsiid]
            path = f"dict/{slug(payload.word)}/word.toml"
            events.append(
                Event(
                    source="dict",
                    source_id=source_id,
                    event="created",
                    time_confidence="exact",
                    source_time=_git_time(timestamp),
                    summary=_summary(payload.word, "created"),
                    author=_identity(users[payload.userid]),
                    changes={path: _render_word(state)},
                    trailers={"Word": payload.word},
                )
            )
            continue

        if kind in {"definition", "version"}:
            assert isinstance(payload, (_Definition, _Version))
            definition_id = _definition_id(payload)
            definition = definitions[definition_id]
            word = words[definition.valsiid]
            state = word_states[word.valsiid]
            is_baseline = kind == "definition"
            author_id = definition.userid if is_baseline else payload.user_id
            version_number = 0 if is_baseline else payload.version_id
            event_language = payload.langid
            keywords = (
                payload.keywords
                if isinstance(payload, _Version)
                else keyword_states.get(definition_id, ())
            )
            previous = state.definitions.get(definition_id)
            updated = definition.created_at if is_baseline else timestamp
            state.definitions[definition_id] = _DefinitionState(
                definition=payload,
                author=users[author_id],
                updated=updated,
                version=version_number,
                keywords=keywords,
                examples=[] if previous is None else previous.examples,
            )
            definition_path = (
                f"dict/{slug(word.word)}/{languages[event_language]}-{definition_id}.md"
            )
            changes = {
                definition_path: _render_definition(
                    state.definitions[definition_id],
                    word,
                    languages[event_language],
                    scores.get(definition_id, 0),
                ),
                f"dict/{slug(word.word)}/word.toml": _render_word(state),
            }
            deletions: tuple[str, ...] = ()
            moved_from: str | None = None
            if previous is not None and previous.definition.langid != event_language:
                moved_from = (
                    f"dict/{slug(word.word)}/"
                    f"{languages[previous.definition.langid]}-{definition_id}.md"
                )
                deletions = (moved_from,)
            event_window = None
            if is_baseline:
                event_window = (
                    f"{word.created.date().isoformat()}.."
                    f"{baseline_window_ends[definition_id].date().isoformat()}"
                )
            message = payload.message if isinstance(payload, _Version) else ""
            trailers = {
                "Definition-Id": str(definition_id),
                "Version": str(version_number),
                "Word": word.word,
            }
            if moved_from is not None:
                trailers["Moved-From"] = moved_from
            if is_baseline:
                trailers["State-As-Of"] = _iso(definition.created_at)
            events.append(
                Event(
                    source="dict",
                    source_id=source_id,
                    event="created" if is_baseline else "edited",
                    time_confidence="window" if is_baseline else "exact",
                    source_time=_git_time(timestamp),
                    summary=_summary(
                        word.word,
                        f"{languages[event_language]}#{definition_id} v{version_number}",
                        message,
                    ),
                    author=_identity(users[author_id]),
                    changes=changes,
                    deletions=deletions,
                    event_window=event_window,
                    trailers=trailers,
                )
            )
            continue

        assert isinstance(payload, Mapping)
        if kind == "etymology":
            identifier = _integer(payload, "etymologyid", "etymology", minimum=1)
            valsiid = _integer(payload, "valsiid", f"etymology {identifier}", minimum=1)
            langid = _integer(payload, "langid", f"etymology {identifier}")
            userid = _integer(payload, "userid", f"etymology {identifier}", minimum=1)
            if valsiid not in words or langid not in languages or userid not in users:
                raise DictionaryParseError(
                    f"etymology {identifier}: unknown related id"
                )
            word = words[valsiid]
            state = word_states[valsiid]
            state.etymologies.append(
                (
                    identifier,
                    languages[langid],
                    users[userid],
                    timestamp,
                    _optional(payload, "content"),
                )
            )
            events.append(
                Event(
                    source="dict",
                    source_id=source_id,
                    event="edited",
                    time_confidence="window",
                    source_time=_git_time(timestamp),
                    summary=_summary(word.word, f"etymology {identifier}"),
                    author=_identity(users[userid]),
                    changes={f"dict/{slug(word.word)}/word.toml": _render_word(state)},
                    event_window=f"{word.created.date().isoformat()}..{timestamp.date().isoformat()}",
                    trailers={"Word": word.word},
                )
            )
            continue

        if kind == "example":
            identifier = _integer(payload, "exampleid", "example", minimum=1)
            valsiid = _integer(payload, "valsiid", f"example {identifier}", minimum=1)
            definition_id = _integer(payload, "definitionid", f"example {identifier}")
            userid = _integer(payload, "userid", f"example {identifier}", minimum=1)
            if valsiid not in words or userid not in users:
                raise DictionaryParseError(f"example {identifier}: unknown related id")
            word = words[valsiid]
            state = word_states[valsiid]
            content = _optional(payload, "content")
            if definition_id == 0:
                state.word_examples.append(
                    (identifier, content, timestamp, users[userid])
                )
                changes = {
                    f"dict/{slug(word.word)}/examples.md": _render_word_examples(state)
                }
            else:
                definition = definitions.get(definition_id)
                definition_state = state.definitions.get(definition_id)
                if (
                    definition is None
                    or definition.valsiid != valsiid
                    or definition_state is None
                ):
                    raise DictionaryParseError(
                        f"example {identifier}: definition is missing at event time"
                    )
                definition_state.examples.append((identifier, content))
                state_language = definition_state.definition.langid
                changes = {
                    f"dict/{slug(word.word)}/{languages[state_language]}-{definition_id}.md": _render_definition(
                        definition_state,
                        word,
                        languages[state_language],
                        scores.get(definition_id, 0),
                    )
                }
            events.append(
                Event(
                    source="dict",
                    source_id=source_id,
                    event="edited",
                    time_confidence="exact",
                    source_time=_git_time(timestamp),
                    summary=_summary(word.word, f"example {identifier}"),
                    author=_identity(users[userid]),
                    changes=changes,
                    trailers={"Word": word.word},
                )
            )
            continue

        if kind == "comment":
            identifier = _integer(payload, "commentid", "comment", minimum=1)
            thread_id = _integer(
                payload, "threadid", f"comment {identifier}", minimum=1
            )
            thread = threads[thread_id]
            valsiid = _optional_integer(thread, "valsiid", f"thread {thread_id}")
            definition_id = _optional_integer(
                thread, "definitionid", f"thread {thread_id}"
            )
            if valsiid is None and definition_id:
                definition = definitions.get(definition_id)
                valsiid = definition.valsiid if definition else None
            userid = _integer(payload, "userid", f"comment {identifier}", minimum=1)
            if valsiid not in words or userid not in users:
                raise DictionaryParseError(f"comment {identifier}: unknown related id")
            word = words[valsiid]
            state = word_states[valsiid]
            content_value = payload.get("content")
            content = (
                _comment_text(content_value, f"comment {identifier}")
                if content_value is not None
                else _optional(payload, "plain_content")
            )
            parentid = _optional_integer(payload, "parentid", f"comment {identifier}")
            state.comments.append(
                (
                    identifier,
                    timestamp,
                    users[userid],
                    _optional(payload, "subject"),
                    content,
                    parentid or None,
                    definition_id or None,
                )
            )
            events.append(
                Event(
                    source="dict",
                    source_id=source_id,
                    event="comment",
                    time_confidence="exact",
                    source_time=_git_time(timestamp),
                    summary=_summary(word.word, f"comment {identifier}"),
                    author=_identity(users[userid]),
                    changes={
                        f"dict/{slug(word.word)}/comments.md": _render_comments(state)
                    },
                    trailers={"Word": word.word},
                )
            )
            continue

        if kind == "page":
            page_name = _required(payload, "pagename", "jbovlaste page")
            version = _integer(
                payload, "version", f"jbovlaste page {page_name}", minimum=1
            )
            langid = _integer(payload, "langid", f"jbovlaste page {page_name}")
            userid = _integer(
                payload, "userid", f"jbovlaste page {page_name}", minimum=1
            )
            if langid not in languages or userid not in users:
                raise DictionaryParseError(
                    f"jbovlaste page {page_name}: unknown related id"
                )
            path = f"dict/_pages/{languages[langid]}/{slug(page_name)}.txt"
            page_key = (langid, page_name)
            previous = page_paths.get(path)
            if previous is not None and previous != page_key:
                raise DictionaryParseError(
                    f"jbovlaste page slug collision: {previous!r} and {page_key!r}"
                )
            page_paths[path] = page_key
            events.append(
                Event(
                    source="dict",
                    source_id=source_id,
                    event="created" if version == 1 else "edited",
                    time_confidence="exact",
                    source_time=_git_time(timestamp),
                    summary=_summary(page_name, f"page v{version}"),
                    author=_identity(users[userid]),
                    changes={
                        path: _page_content(
                            _optional(payload, "content"),
                            _required(
                                payload, "compressed", f"jbovlaste page {page_name}"
                            ),
                            f"jbovlaste page {page_name}",
                        )
                    },
                    trailers={"Version": str(version)},
                )
            )
            continue

        raise AssertionError(f"unknown dictionary operation: {kind}")

    if not events:
        return
    word_rows = [
        {
            "valsi_id": word.valsiid,
            "word": word.word,
            "type": types[word.typeid],
            "creator": users[word.userid],
            "created": _iso(word.created),
            "path": f"dict/{slug(word.word)}/word.toml",
        }
        for word in sorted(words.values(), key=lambda item: item.valsiid)
    ]
    definition_rows = []
    for definition_id, definition in sorted(definitions.items()):
        state = word_states[definition.valsiid].definitions.get(definition_id)
        if state is None:
            raise DictionaryParseError(
                f"definition {definition_id}: baseline was not emitted"
            )
        word = words[definition.valsiid]
        definition_rows.append(
            {
                "definition_id": definition_id,
                "word": word.word,
                "lang": languages[definition.langid],
                "author": state.author,
                "updated": _iso(state.updated),
                "versions": version_counts[definition_id],
                "score": scores.get(definition_id, 0),
                "status": "current",
                "path": f"dict/{slug(word.word)}/{languages[definition.langid]}-{definition_id}.md",
            }
        )
    coverage = "\n".join(
        [
            f"export_date = {_quote(export_date)}",
            'source = "Lensisku operator export"',
            'definition_initial_time_confidence = "window"',
            'definition_initial_window_end = "definitions.created_at"',
            'export_transfer_defects = "3 (integer fields repaired; text fields unverifiable)"',
            f"words = {len(words)}",
            f"definitions = {len(definitions)}",
            f"direct_definition_edits = {len(edits)}",
            f"mirror_definitions_excluded = {len(mirror_definition_ids)}",
            f"mirror_versions_excluded = {mirror_versions_excluded}",
            f"baseline_time_clamps = {baseline_time_clamps}",
            f"baseline_dependency_clamps = {baseline_dependency_clamps}",
            f"comments = {len(data.tables['comments']) - ignored_comments}",
            f"non_dictionary_comments_skipped = {ignored_comments}",
            f"sentinel_comments_skipped = {sentinel_comments_skipped}",
            f"examples = {len(data.tables['example'])}",
            f"etymologies = {len(data.tables['etymology'])}",
            f"jbovlaste_pages = {len(data.tables['pages'])}",
            f"cross_language_keywords = {cross_language_keywords}",
            f"score_key_mismatches = {score_key_mismatches}",
            f"score_rows_merged = {score_rows_merged}",
            f"sentinel_scores_skipped = {sentinel_scores_skipped}",
            f"latest_legacy_time_mismatches = {len(latest_legacy_time_deltas)}",
            f"latest_legacy_time_delta_min = {min(latest_legacy_time_deltas, default=0)}",
            f"latest_legacy_time_delta_max = {max(latest_legacy_time_deltas, default=0)}",
            f"latest_current_rafsi_mismatches = {latest_auxiliary_mismatches['rafsi']}",
            f"latest_current_etymology_mismatches = {latest_auxiliary_mismatches['etymology']}",
            "",
        ]
    )
    final_changes = dict(events[-1].changes)
    final_changes["_meta/dict/words.csv"] = _csv_text(
        ("valsi_id", "word", "type", "creator", "created", "path"), word_rows
    )
    final_changes["_meta/dict/definitions.csv"] = _csv_text(
        (
            "definition_id",
            "word",
            "lang",
            "author",
            "updated",
            "versions",
            "score",
            "status",
            "path",
        ),
        definition_rows,
    )
    final_changes["_meta/dict/coverage.toml"] = coverage
    if older is not None:
        final_changes["_meta/dict/jbovlaste-diff.csv"] = jbovlaste_diff(data, older)
    events[-1] = Event(
        source=events[-1].source,
        source_id=events[-1].source_id,
        event=events[-1].event,
        time_confidence=events[-1].time_confidence,
        source_time=events[-1].source_time,
        summary=events[-1].summary,
        author=events[-1].author,
        changes=final_changes,
        deletions=events[-1].deletions,
        source_date=events[-1].source_date,
        event_window=events[-1].event_window,
        trailers=events[-1].trailers,
    )
    yield from events
