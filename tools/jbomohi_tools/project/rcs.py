"""Strict in-process reader for the trunk history of an RCS archive."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime


class RcsParseError(ValueError):
    """An RCS archive cannot be replayed without guessing."""


@dataclass(frozen=True, slots=True)
class RcsRevision:
    revision: str
    timestamp: datetime
    author: str
    log: str
    content: bytes


@dataclass(frozen=True, slots=True)
class _Metadata:
    timestamp: datetime
    author: str
    following: str | None


class _Scanner:
    def __init__(self, payload: bytes, offset: int) -> None:
        self.payload = payload
        self.offset = offset

    def _space(self) -> None:
        while (
            self.offset < len(self.payload) and self.payload[self.offset] in b" \t\r\n"
        ):
            self.offset += 1

    def word(self) -> bytes | None:
        self._space()
        if self.offset == len(self.payload):
            return None
        start = self.offset
        while (
            self.offset < len(self.payload)
            and self.payload[self.offset] not in b" \t\r\n;"
        ):
            self.offset += 1
        if start == self.offset:
            raise RcsParseError(f"unexpected RCS syntax at byte {self.offset}")
        return self.payload[start : self.offset]

    def at_string(self) -> bytes:
        self._space()
        if self.offset >= len(self.payload) or self.payload[self.offset] != ord("@"):
            raise RcsParseError(f"expected RCS @ string at byte {self.offset}")
        self.offset += 1
        result = bytearray()
        while self.offset < len(self.payload):
            byte = self.payload[self.offset]
            self.offset += 1
            if byte != ord("@"):
                result.append(byte)
                continue
            if self.offset < len(self.payload) and self.payload[self.offset] == ord(
                "@"
            ):
                result.append(ord("@"))
                self.offset += 1
                continue
            return bytes(result)
        raise RcsParseError("unterminated RCS @ string")


def _timestamp(value: bytes) -> datetime:
    try:
        text = value.decode("ascii")
        parsed = datetime.strptime(text, "%Y.%m.%d.%H.%M.%S").replace(tzinfo=UTC)
    except (UnicodeDecodeError, ValueError) as exc:
        raise RcsParseError(f"invalid RCS timestamp: {value!r}") from exc
    return parsed


def _metadata(header: bytes) -> tuple[str, dict[str, _Metadata]]:
    head_match = re.search(rb"(?m)^head\s+([0-9]+\.[0-9]+);$", header)
    if head_match is None:
        raise RcsParseError("RCS archive has no trunk head")
    head = head_match.group(1).decode("ascii")
    pattern = re.compile(
        rb"(?m)^(?P<revision>[0-9]+\.[0-9]+)\n"
        rb"date\s+(?P<date>[0-9.]+);\s+author\s+(?P<author>[^;\r\n]+);[^\n]*\n"
        rb"branches;\nnext\s*(?P<next>[0-9.]*)\s*;$"
    )
    result: dict[str, _Metadata] = {}
    for matched in pattern.finditer(header):
        revision = matched["revision"].decode("ascii")
        if revision in result:
            raise RcsParseError(f"duplicate RCS metadata revision {revision}")
        try:
            author = matched["author"].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RcsParseError(f"RCS revision {revision} has invalid author") from exc
        following = matched["next"].decode("ascii") or None
        result[revision] = _Metadata(_timestamp(matched["date"]), author, following)
    if head not in result:
        raise RcsParseError("RCS head has no metadata block")
    return head, result


def _apply_reverse_delta(content: bytes, delta: bytes, revision: str) -> bytes:
    lines = content.splitlines(keepends=True)
    commands = delta.splitlines(keepends=True)
    offset = 0
    index = 0
    while index < len(commands):
        command = commands[index]
        matched = re.fullmatch(rb"([ad])([0-9]+) ([0-9]+)\n", command)
        if matched is None:
            raise RcsParseError(f"RCS revision {revision} has invalid delta command")
        operation = matched.group(1)
        line = int(matched.group(2))
        count = int(matched.group(3))
        if count < 1:
            raise RcsParseError(f"RCS revision {revision} has an empty delta command")
        if operation == b"d":
            start = line - 1 + offset
            if start < 0 or start + count > len(lines):
                raise RcsParseError(f"RCS revision {revision} deletes outside the file")
            del lines[start : start + count]
            offset -= count
            index += 1
            continue
        inserted = commands[index + 1 : index + 1 + count]
        if len(inserted) != count:
            raise RcsParseError(f"RCS revision {revision} has a short add command")
        start = line + offset
        if start < 0 or start > len(lines):
            raise RcsParseError(f"RCS revision {revision} adds outside the file")
        lines[start:start] = inserted
        offset += count
        index += count + 1
    return b"".join(lines)


def parse(payload: bytes) -> list[RcsRevision]:
    """Return a validated trunk from oldest to newest."""

    if b"\0" in payload or b"\r" in payload:
        raise RcsParseError("RCS archive must be LF text without NUL bytes")
    desc = re.search(rb"(?m)^desc\s*$", payload)
    if desc is None:
        raise RcsParseError("RCS archive has no desc section")
    head, metadata = _metadata(payload[: desc.start()])
    scanner = _Scanner(payload, desc.end())
    scanner.at_string()
    delta_text: dict[str, tuple[str, bytes]] = {}
    while (raw_revision := scanner.word()) is not None:
        try:
            revision = raw_revision.decode("ascii")
        except UnicodeDecodeError as exc:
            raise RcsParseError("RCS deltatext revision is not ASCII") from exc
        if revision not in metadata or revision in delta_text:
            raise RcsParseError(f"unexpected RCS deltatext revision {revision}")
        if scanner.word() != b"log":
            raise RcsParseError(f"RCS revision {revision} lacks log")
        try:
            log = scanner.at_string().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RcsParseError(
                f"RCS revision {revision} has invalid log text"
            ) from exc
        if scanner.word() != b"text":
            raise RcsParseError(f"RCS revision {revision} lacks text")
        delta_text[revision] = (log, scanner.at_string())
    if set(delta_text) != set(metadata):
        raise RcsParseError("RCS metadata and deltatext revisions disagree")

    newest = delta_text[head][1]
    content_by_revision = {head: newest}
    chain = [head]
    current = head
    while metadata[current].following is not None:
        following = metadata[current].following
        assert following is not None
        if following in content_by_revision:
            raise RcsParseError("RCS trunk next links contain a cycle")
        if following not in metadata:
            raise RcsParseError(f"RCS trunk links to missing revision {following}")
        content_by_revision[following] = _apply_reverse_delta(
            content_by_revision[current], delta_text[following][1], following
        )
        chain.append(following)
        current = following
    if set(chain) != set(metadata):
        raise RcsParseError(
            "RCS archive contains unsupported branches or detached revisions"
        )
    result = []
    for revision in reversed(chain):
        info = metadata[revision]
        result.append(
            RcsRevision(
                revision,
                info.timestamp,
                info.author,
                delta_text[revision][0],
                content_by_revision[revision],
            )
        )
    return result
