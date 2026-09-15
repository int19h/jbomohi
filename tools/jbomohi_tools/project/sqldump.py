"""Shared strict reader for `mysqldump --skip-extended-insert` exports.

Both operator exports the corpus ingests (Tiki and MediaWiki) are MySQL dumps
written one row per ``INSERT`` statement. The primitives here read such a dump
as bytes and never decode text: every source decides its own character policy
(SPEC.md sections 3.2 and 3.2.5), so a shared reader that guessed an encoding
would corrupt one of them. Callers pass the exception type they want raised so
each source keeps its own fail-closed error class.
"""

from __future__ import annotations

import gzip
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

INSERT = re.compile(rb"^INSERT INTO `([A-Za-z0-9_]+)` VALUES (.*);$")
CREATE = re.compile(rb"^CREATE TABLE `([A-Za-z0-9_]+)` \($")
COLUMN = re.compile(rb"^  `([^`]+)` ")
ENGINE = b") ENGINE="
MAX_SQL_LINE = 128 * 1024 * 1024

_ESCAPES = {
    ord("0"): 0,
    ord("b"): 8,
    ord("n"): 10,
    ord("r"): 13,
    ord("t"): 9,
    ord("Z"): 26,
}


class SqlDumpError(ValueError):
    """A SQL export violates the shape this reader is willing to accept."""


@dataclass(frozen=True, slots=True)
class SqlStatement:
    """One statement of interest: a table schema or a single inserted row."""

    table: str
    columns: tuple[str, ...] | None
    values: bytes | None


@contextmanager
def open_sql(path: Path, error: type[Exception] = SqlDumpError) -> Iterator[BinaryIO]:
    """Open a plain or gzipped dump, failing closed on any read error."""

    try:
        with path.open("rb") as probe:
            compressed = probe.read(2) == b"\x1f\x8b"
        with gzip.open(path, "rb") if compressed else path.open("rb") as stream:
            yield stream
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise error(f"cannot read SQL dump {path}: {exc}") from exc


def read_line(
    stream: BinaryIO, path: Path, error: type[Exception] = SqlDumpError
) -> bytes | None:
    """Read one bounded, newline-terminated statement line."""

    raw = stream.readline(MAX_SQL_LINE + 1)
    if not raw:
        return None
    if len(raw) > MAX_SQL_LINE:
        raise error(f"SQL dump {path} contains a statement over {MAX_SQL_LINE} bytes")
    if not raw.endswith(b"\n"):
        raise error(f"SQL dump {path} has an unterminated final line")
    return raw.removesuffix(b"\n")


def statements(
    path: Path, error: type[Exception] = SqlDumpError
) -> Iterator[SqlStatement]:
    """Stream every `CREATE TABLE` column list and every inserted row.

    A schema is reported once its closing ``) ENGINE=`` line is reached, so a
    caller can check the column list before trusting the rows that follow.
    """

    schema_table: str | None = None
    schema_columns: list[str] = []
    with open_sql(path, error) as stream:
        while True:
            raw = read_line(stream, path, error)
            if raw is None:
                break
            created = CREATE.fullmatch(raw)
            if created is not None:
                if schema_table is not None:
                    raise error(f"SQL dump {path} has a nested CREATE TABLE")
                schema_table = created.group(1).decode("ascii")
                schema_columns = []
                continue
            if schema_table is not None:
                column = COLUMN.match(raw)
                if column is not None:
                    schema_columns.append(column.group(1).decode("ascii"))
                if raw.startswith(ENGINE):
                    yield SqlStatement(schema_table, tuple(schema_columns), None)
                    schema_table = None
                    schema_columns = []
                continue
            inserted = INSERT.fullmatch(raw)
            if inserted is not None:
                yield SqlStatement(
                    inserted.group(1).decode("ascii"), None, inserted.group(2)
                )
    if schema_table is not None:
        raise error(f"SQL dump {path} ends inside the schema of {schema_table}")


def _quoted(
    body: bytes, start: int, context: str, error: type[Exception]
) -> tuple[bytes, int]:
    value = bytearray()
    index = start + 1
    while index < len(body):
        byte = body[index]
        if byte == 39:
            return bytes(value), index + 1
        if byte != 92:
            value.append(byte)
            index += 1
            continue
        index += 1
        if index == len(body):
            raise error(f"{context}: trailing string escape")
        escaped = body[index]
        value.append(_ESCAPES.get(escaped, escaped))
        index += 1
    raise error(f"{context}: unterminated SQL string")


def parse_insert_values(
    body: bytes, context: str = "INSERT", error: type[Exception] = SqlDumpError
) -> tuple[bytes | None, ...]:
    """Parse one `--skip-extended-insert` VALUES tuple without decoding text."""

    if not body.startswith(b"(") or not body.endswith(b")"):
        raise error(f"{context}: expected one VALUES tuple")
    values: list[bytes | None] = []
    index = 1
    limit = len(body) - 1
    while index < limit:
        if body[index] == 39:
            value, index = _quoted(body, index, context, error)
        else:
            end = index
            while end < limit and body[end] != 44:
                end += 1
            token = body[index:end]
            if token == b"NULL":
                value = None
            elif token.startswith(b"0x"):
                hexadecimal = token[2:]
                if (
                    not hexadecimal
                    or len(hexadecimal) % 2
                    or not re.fullmatch(rb"[0-9A-F]+", hexadecimal)
                ):
                    raise error(f"{context}: invalid hexadecimal value")
                value = bytes.fromhex(hexadecimal.decode("ascii"))
            elif re.fullmatch(rb"-?[0-9]+(?:\.[0-9]+)?", token):
                value = token
            else:
                raise error(f"{context}: unsupported bare SQL value")
            index = end
        values.append(value)
        if index == limit:
            break
        if body[index] != 44:
            raise error(f"{context}: expected a comma between values")
        index += 1
    if index != limit:
        raise error(f"{context}: trailing data after VALUES tuple")
    return tuple(values)


def require_columns(
    table: str,
    actual: Sequence[str],
    expected: Sequence[str],
    error: type[Exception] = SqlDumpError,
) -> None:
    """Refuse a table whose column list is not exactly what the loader expects."""

    if tuple(actual) != tuple(expected):
        raise error(f"SQL dump has unexpected schema for {table}: {', '.join(actual)}")
