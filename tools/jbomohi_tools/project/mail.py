"""Deterministic RFC 822 deduplication and Maildir/thread projection."""

from __future__ import annotations

import codecs
import csv
import hashlib
import html
import io
import json
import re
import stat
import unicodedata
import zipfile
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from email import policy
from email.message import Message
from email.parser import BytesHeaderParser, BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from ..git import EPOCH, Event, Identity
from .dictionary import slug

_MAX_MESSAGE_BYTES = 32 * 1024 * 1024
_REFERENCE = re.compile(r"<([^<>]+)>")
_MBOX_ENVELOPE = re.compile(
    rb"^From \S+\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Ukn)\s+"
    rb"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
)
_RE_PREFIX = re.compile(r"^(?:(?:re|fwd?|aw|sv)(?:\[[0-9]+\])?:\s*)+", re.IGNORECASE)
_LIST_PREFIX = re.compile(r"^(?:\[[^\]]+\]\s*)+")

SOURCE_RANKS = {
    "lists-plain": 5,
    "old-lojban-list": 4,
    "jbosnu-raw": 4,
    "files-mbox": 3,
    "mhonarc": 2,
    "files-zip": 1,
}

DEFAULT_ARCHIVE_GAPS: dict[str, dict[str, str]] = {
    "lojban-list": {
        "old_lojban_list": (
            "not fully populated; resume: jbomohi archive fetch old-lojban-list"
        ),
        "lojban_list_old": (
            "selective gap source not populated; resume only after absent Message-IDs are known: "
            "jbomohi archive fetch mhonarc --list lojban-list-old --start 1"
        ),
    },
    "lojban-beginners": {
        "mhonarc_union": (
            "not fully populated; resume: jbomohi archive fetch mhonarc "
            "--list lojban-beginners"
        )
    },
}


class MailParseError(ValueError):
    """A mail manifestation cannot satisfy the public corpus contract."""


@dataclass(frozen=True, slots=True)
class RawMessage:
    path: Path | None = None
    payload: bytes | None = None

    def read(self) -> bytes:
        if (self.path is None) == (self.payload is None):
            raise MailParseError("raw message must have exactly one backing source")
        if self.payload is not None:
            raw = self.payload
        else:
            assert self.path is not None
            try:
                if self.path.is_symlink() or not self.path.is_file():
                    raise MailParseError(
                        f"mail source must be a regular non-symlink file: {self.path}"
                    )
                size = self.path.stat().st_size
                if size > _MAX_MESSAGE_BYTES:
                    raise MailParseError(
                        f"mail source exceeds {_MAX_MESSAGE_BYTES} bytes: {self.path}"
                    )
                raw = self.path.read_bytes()
            except OSError as exc:
                raise MailParseError(
                    f"cannot read mail source {self.path}: {exc}"
                ) from exc
        if len(raw) > _MAX_MESSAGE_BYTES:
            raise MailParseError(f"mail message exceeds {_MAX_MESSAGE_BYTES} bytes")
        if not raw:
            raise MailParseError("mail message must not be empty")
        return raw


@dataclass(frozen=True, slots=True)
class MailManifestation:
    list_name: str
    raw: RawMessage
    manifestation: str
    provenance: str
    archive_order: int
    archive_time: datetime

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", self.list_name):
            raise MailParseError(f"unsafe mail list name: {self.list_name!r}")
        if self.archive_order < 0:
            raise MailParseError("mail archive order must not be negative")
        if self.archive_time.tzinfo is None:
            raise MailParseError("mail archive time must include a UTC offset")
        if not self.provenance or any(
            character in self.provenance for character in "\r\n\0"
        ):
            raise MailParseError("mail provenance must be one non-empty line")

    @property
    def source_rank(self) -> int:
        try:
            return SOURCE_RANKS[self.manifestation]
        except KeyError as exc:
            raise MailParseError(
                f"unknown mail manifestation rank: {self.manifestation!r}"
            ) from exc


@dataclass(frozen=True, slots=True)
class ParsedMail:
    manifestation: MailManifestation
    message_id: str
    had_message_id: bool
    subject: str
    normalized_subject: str
    from_header: str
    from_address: str
    from_name: str
    timestamp: datetime
    time_confidence: str
    event_window: str | None
    source_dated: bool
    references: tuple[str, ...]
    in_reply_to: str | None
    header_count: int
    spam_suspect: bool
    raw_8bit_headers: int
    raw_sha1: str
    file: str = ""
    thread_key: str = ""


@dataclass(frozen=True, slots=True)
class DuplicateMail:
    key: str
    winner: ParsedMail
    loser: ParsedMail


@dataclass(slots=True)
class _Container:
    identifier: str
    message: ParsedMail | None = None
    parent: _Container | None = None
    children: list[_Container] = field(default_factory=list)


class _TextHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = [line.rstrip() for line in "".join(self.parts).splitlines()]
        return "\n".join(lines).strip("\n")


class _MhonarcHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts).strip("\r\n")


def normalize_message_id(value: str) -> str:
    normalized = unicodedata.normalize("NFC", html.unescape(value)).strip()
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1].strip()
    return normalized.casefold()


def normalize_subject(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip()
    previous = None
    while previous != normalized:
        previous = normalized
        normalized = _LIST_PREFIX.sub("", normalized)
        normalized = _RE_PREFIX.sub("", normalized)
        normalized = normalized.strip()
    return " ".join(normalized.split()).casefold()


def _mhonarc_comment(document: str, name: str) -> list[str]:
    pattern = re.compile(
        rf"<!--X-{re.escape(name)}:\s*(.*?)\s*-->", re.IGNORECASE | re.DOTALL
    )
    return [
        html.unescape(" ".join(match.group(1).split()))
        for match in pattern.finditer(document)
    ]


def _mhonarc_rendered_header(document: str, name: str) -> str:
    pattern = re.compile(
        rf"<li><em>{re.escape(name)}</em>:\s*(.*?)</li>",
        re.IGNORECASE | re.DOTALL,
    )
    matched = pattern.search(document)
    if matched is None:
        return ""
    parser = _MhonarcHTML()
    parser.feed(matched.group(1))
    parser.close()
    return " ".join(parser.text().split())


def _mhonarc_from_r13(value: str) -> str:
    decoded = codecs.decode(value, "rot_13")
    return re.sub(r"([^\s<>]+)A([^\s<>]+)", r"\1@\2", decoded, count=1)


def reconstruct_mhonarc(payload: bytes) -> bytes:
    """Reconstruct deterministic RFC 822 from one MHonArc message page."""

    try:
        document = payload.decode("utf-8")
    except UnicodeDecodeError:
        document = payload.decode("cp1252")
    message_ids = _mhonarc_comment(document, "Message-Id")
    subjects = _mhonarc_comment(document, "Subject")
    dates = _mhonarc_comment(document, "Date")
    rendered_from = _mhonarc_rendered_header(document, "From")
    plain_from = _mhonarc_comment(document, "From")
    from_r13 = _mhonarc_comment(document, "From-R13")
    from_value = rendered_from or (plain_from[0] if plain_from else "")
    if not from_value and from_r13:
        from_value = _mhonarc_from_r13(from_r13[0])
    message_id = message_ids[0] if message_ids else ""
    subject = subjects[0] if subjects else _mhonarc_rendered_header(document, "Subject")
    date_value = dates[0] if dates else _mhonarc_rendered_header(document, "Date")
    to_value = _mhonarc_rendered_header(document, "To")
    references = _mhonarc_comment(document, "Reference")
    in_reply_to = _mhonarc_rendered_header(document, "In-reply-to")
    begin = document.find("<!--X-Body-of-Message-->")
    end = document.find("<!--X-Body-of-Message-End-->")
    if begin < 0 or end < begin:
        raise MailParseError("MHonArc page is missing its message body markers")
    body_html = document[begin + len("<!--X-Body-of-Message-->") : end]
    body_parser = _MhonarcHTML()
    body_parser.feed(body_html)
    body_parser.close()
    body = body_parser.text()
    headers = [
        ("From", from_value),
        ("Date", date_value),
        ("Subject", subject or "[no subject]"),
    ]
    if to_value:
        headers.append(("To", to_value))
    if message_id:
        headers.append(("Message-ID", f"<{normalize_message_id(message_id)}>"))
    if references:
        headers.append(
            (
                "References",
                " ".join(f"<{normalize_message_id(value)}>" for value in references),
            )
        )
    if in_reply_to:
        values = _references(in_reply_to)
        if values:
            headers.append(("In-Reply-To", f"<{values[-1]}>"))
    headers.extend(
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("X-Jbomohi-Manifestation", "mhonarc"),
        ]
    )
    for name, value in headers:
        if not value or any(character in value for character in "\r\n\0"):
            raise MailParseError(f"MHonArc reconstructed {name} is invalid")
    rendered_headers = "\r\n".join(f"{name}: {value}" for name, value in headers)
    return (
        rendered_headers
        + "\r\n\r\n"
        + body.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        + "\r\n"
    ).encode("utf-8")


def _references(value: str) -> tuple[str, ...]:
    found = [normalize_message_id(item) for item in _REFERENCE.findall(value)]
    if not found and value.strip():
        found = [normalize_message_id(value)]
    return tuple(item for item in found if item)


def _decoded_header(message: Message, name: str) -> str:
    value = message.get(name)
    return "" if value is None else str(value)


def _raw_header(raw: bytes, name: str) -> bytes | None:
    header = (
        raw.split(b"\r\n\r\n", 1)[0] if b"\r\n\r\n" in raw else raw.split(b"\n\n", 1)[0]
    )
    wanted = name.casefold().encode("ascii")
    current_name: bytes | None = None
    current_value = bytearray()
    for line in header.replace(b"\r\n", b"\n").split(b"\n"):
        if line.startswith((b" ", b"\t")) and current_name is not None:
            current_value.extend(b" " + line.lstrip())
            continue
        if current_name == wanted:
            return bytes(current_value)
        field, separator, value = line.partition(b":")
        if not separator:
            current_name = None
            current_value = bytearray()
            continue
        current_name = field.strip().lower()
        current_value = bytearray(value.lstrip())
    return bytes(current_value) if current_name == wanted else None


def _decode_raw_header(value: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "iso-8859-1"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AssertionError("ISO-8859-1 must decode every byte")


def _preserved_header(raw: bytes, message: Message, name: str) -> tuple[str, bool]:
    value = _raw_header(raw, name)
    decoded = _decoded_header(message, name)
    if value is not None and any(byte >= 128 for byte in value):
        return _decode_raw_header(value), True
    return decoded, False


def _naive_header_date(value: str | None) -> datetime | None:
    """Parse one RFC 822 date header, or None when it does not parse."""

    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed


def _message_date(
    message: Message, manifestation: MailManifestation
) -> tuple[datetime, str, str | None, bool]:
    parsed = _naive_header_date(_decoded_header(message, "Date"))
    if parsed is not None:
        aware = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        moment = aware.astimezone(UTC).replace(microsecond=0)
        if moment > EPOCH:
            if parsed.tzinfo is None:
                return moment, "tz-unknown", None, True
            return moment, "exact", None, True
    for received in message.get_all("Received", []):
        candidate = str(received).rsplit(";", 1)[-1].strip()
        parsed = _naive_header_date(candidate)
        if parsed is None:
            continue
        aware = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        moment = aware.astimezone(UTC).replace(microsecond=0)
        if moment > EPOCH:
            return moment, "tz-unknown", None, True
    timestamp = manifestation.archive_time.astimezone(UTC).replace(microsecond=0)
    day = timestamp.date().isoformat()
    return timestamp, "window", f"{day}..{day}", False


def _body_bytes(part: Message) -> bytes:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    value = part.get_payload()
    if isinstance(value, str):
        return value.encode("utf-8", errors="surrogateescape")
    return b""


def _decode_body_bytes(payload: bytes, charset: str | None) -> str:
    candidates = [charset, "utf-8", "cp1252", "iso-8859-1"]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return payload.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("iso-8859-1")


def decoded_body(raw: bytes) -> tuple[str, bool]:
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception as exc:
        raise MailParseError(f"cannot parse RFC 822 body: {exc}") from exc
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        if message.is_multipart():
            return "", False
        body = message
    payload = _body_bytes(body)
    text = _decode_body_bytes(payload, body.get_content_charset())
    if body.get_content_type() == "text/html":
        parser = _TextHTML()
        parser.feed(text)
        parser.close()
        return parser.text(), True
    return text, False


def parse_mail(manifestation: MailManifestation) -> ParsedMail:
    raw = manifestation.raw.read()
    try:
        message = BytesHeaderParser(policy=policy.default).parsebytes(raw)
    except Exception as exc:
        raise MailParseError(
            f"cannot parse RFC 822 headers from {manifestation.provenance}: {exc}"
        ) from exc
    raw_sha1 = hashlib.sha1(raw).hexdigest()
    raw_message_id = _decoded_header(message, "Message-ID")
    normalized_id = normalize_message_id(raw_message_id)
    had_message_id = bool(normalized_id)
    if not normalized_id:
        normalized_id = f"{raw_sha1}@jbomohi.invalid"
    subject, raw_subject = _preserved_header(raw, message, "Subject")
    if not subject.strip():
        subject = "[no subject]"
    from_header, raw_from = _preserved_header(raw, message, "From")
    if not from_header.strip():
        from_header = "unknown"
    from_name, from_address = parseaddr(from_header)
    if (
        not from_address
        or "@" not in from_address
        or any(character.isspace() for character in from_address)
    ):
        angle_addresses = re.findall(r"<([^<>\s]+@[^<>\s]+)>", from_header)
        if len(angle_addresses) == 1:
            from_address = angle_addresses[0]
            from_name = from_header.split("<", 1)[0].strip(" \"'")
    if not from_address or "@" not in from_address:
        from_address = f"unknown-{raw_sha1[:12]}@jbomohi.invalid"
        from_name = from_header
    timestamp, confidence, event_window, source_dated = _message_date(
        message, manifestation
    )
    references = tuple(
        reference
        for header in message.get_all("References", [])
        for reference in _references(str(header))
    )
    in_reply_values = _references(_decoded_header(message, "In-Reply-To"))
    in_reply_to = in_reply_values[-1] if in_reply_values else None
    spam_suspect = (
        _decoded_header(message, "X-Spam-Flag").strip().casefold() == "yes"
        or _decoded_header(message, "X-Spam-Status")
        .lstrip()
        .casefold()
        .startswith("yes")
        or _decoded_header(message, "X-Bogosity").lstrip().casefold().startswith("spam")
        or "*****spam*****" in subject.casefold()
    )
    return ParsedMail(
        manifestation=manifestation,
        message_id=normalized_id,
        had_message_id=had_message_id,
        subject=subject,
        normalized_subject=normalize_subject(subject),
        from_header=from_header,
        from_address=from_address,
        from_name=from_name,
        timestamp=timestamp,
        time_confidence=confidence,
        event_window=event_window,
        source_dated=source_dated,
        references=references,
        in_reply_to=in_reply_to,
        header_count=sum(1 for _name, _value in message.raw_items()),
        spam_suspect=spam_suspect,
        raw_8bit_headers=int(raw_subject) + int(raw_from),
        raw_sha1=raw_sha1,
    )


def _dedupe_key(message: ParsedMail) -> str:
    if message.had_message_id:
        return "id:" + message.message_id
    body, _html = decoded_body(message.manifestation.raw.read())
    local_part = message.from_address.rsplit("@", 1)[0].casefold()
    minute = (
        message.timestamp.replace(second=0, microsecond=0).isoformat()
        if message.source_dated
        else ""
    )
    material = "\0".join((message.normalized_subject, local_part, minute, body[:200]))
    return "fallback:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _assign_window_dates(messages: Sequence[ParsedMail]) -> list[ParsedMail]:
    groups: dict[tuple[str, str], list[tuple[int, ParsedMail]]] = defaultdict(list)
    for index, message in enumerate(messages):
        key = (
            message.manifestation.list_name,
            message.manifestation.manifestation,
        )
        groups[key].append((index, message))
    result = list(messages)
    for items in groups.values():
        ordered = sorted(
            items,
            key=lambda item: (
                item[1].manifestation.archive_order,
                item[1].manifestation.provenance,
            ),
        )
        previous: list[datetime | None] = []
        latest: datetime | None = None
        for _index, message in ordered:
            previous.append(latest)
            if message.source_dated:
                latest = message.timestamp
        following: list[datetime | None] = [None] * len(ordered)
        nearest: datetime | None = None
        for position in range(len(ordered) - 1, -1, -1):
            following[position] = nearest
            if ordered[position][1].source_dated:
                nearest = ordered[position][1].timestamp
        for position, (original_index, message) in enumerate(ordered):
            if message.source_dated:
                continue
            before = previous[position]
            after = following[position]
            if before is not None or after is not None:
                timestamp = before or after
                assert timestamp is not None
                first = (before or timestamp).date()
                last = (after or timestamp).date()
                start, end = sorted((first, last))
                event_window = f"{start.isoformat()}..{end.isoformat()}"
            else:
                timestamp = message.manifestation.archive_time.astimezone(UTC)
                day = timestamp.date().isoformat()
                event_window = f"{day}..{day}"
            result[original_index] = replace(
                message,
                timestamp=timestamp.replace(microsecond=0),
                event_window=event_window,
            )
    return result


def deduplicate(
    manifestations: Iterable[MailManifestation],
) -> tuple[list[ParsedMail], list[DuplicateMail]]:
    parsed_messages = _assign_window_dates(
        [parse_mail(manifestation) for manifestation in manifestations]
    )
    groups: dict[tuple[str, str], list[ParsedMail]] = defaultdict(list)
    keys: dict[tuple[str, str], str] = {}
    for parsed in parsed_messages:
        key = _dedupe_key(parsed)
        scoped_key = (parsed.manifestation.list_name, key)
        groups[scoped_key].append(parsed)
        keys[scoped_key] = key

    winners: list[ParsedMail] = []
    duplicates: list[DuplicateMail] = []
    for scoped_key, messages in groups.items():
        winner = max(
            messages,
            key=lambda item: (
                item.header_count,
                item.manifestation.source_rank,
                -item.manifestation.archive_order,
            ),
        )
        winners.append(winner)
        duplicates.extend(
            DuplicateMail(keys[scoped_key], winner, loser)
            for loser in messages
            if loser is not winner
        )
    return winners, duplicates


def load_maildir(
    root: Path,
    *,
    list_name: str,
    manifestation: str = "lists-plain",
    provenance_prefix: str | None = None,
) -> Iterator[MailManifestation]:
    """Yield lazy manifestations from an extracted Maildir cur/new tree."""

    order = 0
    for directory in ("cur", "new"):
        path = root / directory
        if not path.is_dir():
            raise MailParseError(f"Maildir is missing {path}")
        for message_path in sorted(path.iterdir(), key=lambda value: value.name):
            if message_path.is_symlink() or not message_path.is_file():
                raise MailParseError(f"unsafe Maildir entry: {message_path}")
            match = re.match(r"([0-9]+)\.", message_path.name)
            archive_time = (
                datetime.fromtimestamp(int(match.group(1)), UTC)
                if match
                else datetime(1970, 1, 1, tzinfo=UTC)
            )
            provenance = (
                f"{provenance_prefix}/{directory}/{message_path.name}"
                if provenance_prefix
                else str(message_path)
            )
            yield MailManifestation(
                list_name=list_name,
                raw=RawMessage(path=message_path),
                manifestation=manifestation,
                provenance=provenance,
                archive_order=order,
                archive_time=archive_time,
            )
            order += 1


def numbered_rfc822(raw: bytes) -> bytes:
    """Remove the transport mbox envelope from one numbered raw message."""

    first, separator, rest = raw.partition(b"\n")
    if _MBOX_ENVELOPE.match(first.rstrip(b"\r")) and separator:
        return rest
    return raw


def load_numbered_rfc822(
    root: Path,
    *,
    list_name: str,
    manifestation: str = "old-lojban-list",
    provenance_prefix: str | None = None,
) -> Iterator[MailManifestation]:
    """Load a directory of numeric raw messages, dropping mbox envelopes."""

    paths = sorted(
        (path for path in root.iterdir() if path.is_file() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )
    for order, path in enumerate(paths):
        raw = numbered_rfc822(RawMessage(path=path).read())
        yield MailManifestation(
            list_name=list_name,
            raw=RawMessage(payload=raw),
            manifestation=manifestation,
            provenance=(
                f"{provenance_prefix}/{path.name}" if provenance_prefix else str(path)
            ),
            archive_order=order,
            archive_time=datetime(1970, 1, 1, tzinfo=UTC),
        )


def load_mbox(
    path: Path,
    *,
    list_name: str,
    provenance_prefix: str | None = None,
) -> Iterator[MailManifestation]:
    """Split one mboxo file while preserving RFC 822 bytes."""

    raw = RawMessage(path=path).read()
    yield from mbox_manifestations(
        raw,
        list_name=list_name,
        provenance_prefix=provenance_prefix or str(path),
    )


def split_mbox(raw: bytes) -> list[bytes]:
    """Split mboxo bytes and unescape transport-escaped From lines."""

    messages: list[bytes] = []
    current: list[bytes] = []
    seen_envelope = False
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        next_is_header = index + 1 < len(lines) and bool(
            re.match(rb"^[!-9;-~]+:", lines[index + 1])
        )
        if _MBOX_ENVELOPE.match(line.rstrip(b"\r\n")) and (
            next_is_header or index == 0
        ):
            if seen_envelope and current:
                messages.append(b"".join(current))
            current = []
            seen_envelope = True
            continue
        if seen_envelope:
            current.append(line[1:] if line.startswith(b">From ") else line)
    if seen_envelope and current:
        messages.append(b"".join(current))
    if not messages:
        raise MailParseError("mbox contains no messages")
    return messages


def mbox_manifestations(
    raw: bytes,
    *,
    list_name: str,
    provenance_prefix: str,
) -> Iterator[MailManifestation]:
    """Yield manifestations from already decompressed mboxo bytes."""

    messages = split_mbox(raw)
    for order, payload in enumerate(messages):
        yield MailManifestation(
            list_name=list_name,
            raw=RawMessage(payload=payload),
            manifestation="files-mbox",
            provenance=(f"{provenance_prefix}#{order + 1}"),
            archive_order=order,
            archive_time=datetime(1970, 1, 1, tzinfo=UTC),
        )


def load_mh_zip(
    path: Path,
    *,
    list_name: str = "jbosnu",
    provenance_prefix: str = "jbosnu_raw.zip",
) -> Iterator[MailManifestation]:
    """Load numeric RFC 822 messages from the public jbosnu MH-folder zip."""

    try:
        with zipfile.ZipFile(path) as archive:
            members: list[tuple[int, zipfile.ZipInfo]] = []
            for info in archive.infolist():
                member = Path(info.filename)
                mode = info.external_attr >> 16
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or "\\" in info.filename
                    or stat.S_ISLNK(mode)
                ):
                    raise MailParseError(f"unsafe MH zip member: {info.filename!r}")
                if info.is_dir() or member.name == ".mh_sequences":
                    continue
                if (
                    len(member.parts) != 2
                    or member.parts[0] != "jbosnu_raw"
                    or not member.name.isdigit()
                ):
                    raise MailParseError(f"unexpected MH zip member: {info.filename!r}")
                if info.file_size > _MAX_MESSAGE_BYTES:
                    raise MailParseError(
                        f"MH zip message is too large: {info.filename!r}"
                    )
                members.append((int(member.name), info))
            if not members:
                raise MailParseError(f"MH zip contains no numeric messages: {path}")
            for order, (_number, info) in enumerate(sorted(members)):
                payload = archive.read(info)
                yield MailManifestation(
                    list_name=list_name,
                    raw=RawMessage(payload=payload),
                    manifestation="jbosnu-raw",
                    provenance=f"{provenance_prefix}/{info.filename}",
                    archive_order=order,
                    archive_time=datetime(1970, 1, 1, tzinfo=UTC),
                )
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise MailParseError(f"cannot load MH zip {path}: {exc}") from exc


def _link(parent: _Container, child: _Container) -> bool:
    ancestor: _Container | None = parent
    while ancestor is not None:
        if ancestor is child:
            return False
        ancestor = ancestor.parent
    if child.parent is not None:
        child.parent.children.remove(child)
    child.parent = parent
    if child not in parent.children:
        parent.children.append(child)
    return True


def _walk_thread(
    item: ParsedMail,
    children: Mapping[str | None, Sequence[ParsedMail]],
    result: list[ParsedMail],
) -> None:
    result.append(item)
    for child in children.get(item.message_id, ()):
        _walk_thread(child, children, result)


def _thread_order(
    messages: Sequence[ParsedMail],
) -> tuple[dict[str, str], dict[str, list[ParsedMail]]]:
    containers: dict[str, _Container] = {}

    def container(identifier: str) -> _Container:
        return containers.setdefault(identifier, _Container(identifier))

    for message in messages:
        node = container(message.message_id)
        if node.message is not None:
            raise MailParseError(
                f"duplicate message after dedupe: {message.message_id}"
            )
        node.message = message
        chain = list(message.references)
        if not chain and message.in_reply_to:
            chain.append(message.in_reply_to)
        previous: _Container | None = None
        for identifier in chain:
            reference = container(identifier)
            if previous is not None and reference.parent is None:
                _link(previous, reference)
            previous = reference
        if previous is not None:
            _link(previous, node)

    roots = [item for item in containers.values() if item.parent is None]

    def first_message(node: _Container) -> ParsedMail | None:
        candidates: list[ParsedMail] = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current.message is not None:
                candidates.append(current.message)
            stack.extend(current.children)
        return (
            min(candidates, key=lambda item: (item.timestamp, item.message_id))
            if candidates
            else None
        )

    node_root: dict[str, str] = {}
    base_grouped: dict[str, list[ParsedMail]] = defaultdict(list)
    for node in containers.values():
        if node.message is None:
            continue
        root = node
        while root.parent is not None:
            root = root.parent
        node_root[node.message.message_id] = root.identifier
        base_grouped[root.identifier].append(node.message)

    roots_by_subject: dict[tuple[str, str], list[str]] = defaultdict(list)
    root_times: dict[str, list[datetime]] = {}
    for root in roots:
        first = first_message(root)
        if first is None:
            continue
        key = (first.manifestation.list_name, first.normalized_subject)
        roots_by_subject[key].append(root.identifier)
        root_times[root.identifier] = sorted(
            message.timestamp for message in base_grouped[root.identifier]
        )

    canonical_root = {root.identifier: root.identifier for root in roots}

    def canonical(identifier: str) -> str:
        trail: list[str] = []
        while canonical_root[identifier] != identifier:
            trail.append(identifier)
            identifier = canonical_root[identifier]
        for item in trail:
            canonical_root[item] = identifier
        return identifier

    orphans = sorted(
        (
            message
            for message in messages
            if not message.references and message.in_reply_to is None
        ),
        key=lambda item: (item.timestamp, item.message_id),
    )
    for orphan in orphans:
        if not orphan.normalized_subject:
            continue
        own_root = node_root[orphan.message_id]
        candidates: list[tuple[datetime, str]] = []
        key = (orphan.manifestation.list_name, orphan.normalized_subject)
        for other_root in roots_by_subject.get(key, ()):
            if other_root == own_root:
                continue
            times = root_times[other_root]
            position = bisect_right(times, orphan.timestamp) - 1
            if position < 0:
                continue
            latest = times[position]
            if orphan.timestamp - latest <= timedelta(days=90):
                candidates.append((latest, canonical(other_root)))
        if candidates:
            _latest, target = max(candidates, key=lambda item: (item[0], item[1]))
            if canonical(own_root) != target:
                canonical_root[own_root] = target

    message_roots: dict[str, str] = {}
    grouped: dict[str, list[ParsedMail]] = defaultdict(list)
    for message in messages:
        root_id = canonical(node_root[message.message_id])
        message_roots[message.message_id] = root_id
        grouped[root_id].append(message)

    ordered: dict[str, list[ParsedMail]] = {}
    for root_id, items in grouped.items():
        item_ids = {item.message_id for item in items}
        children: dict[str | None, list[ParsedMail]] = defaultdict(list)
        for item in items:
            parent = item.references[-1] if item.references else item.in_reply_to
            children[parent if parent in item_ids else None].append(item)
        for values in children.values():
            values.sort(key=lambda item: (item.timestamp, item.message_id))
        result: list[ParsedMail] = []

        for item in children[None]:
            _walk_thread(item, children, result)
        if len(result) != len(items):
            missing = sorted(
                (item for item in items if item not in result),
                key=lambda item: (item.timestamp, item.message_id),
            )
            result.extend(missing)
        ordered[root_id] = result
    return message_roots, ordered


def _thread_key(root_id: str, subject: str) -> str:
    prefix = hashlib.sha1(root_id.encode("utf-8")).hexdigest()[:12]
    suffix = slug(subject or "no subject")
    budget = 60 - len(prefix) - 1
    return f"{prefix}-{suffix[:budget]}"


def _mail_filename(message: ParsedMail) -> str:
    timestamp = int(message.timestamp.timestamp())
    digest = hashlib.sha1(message.message_id.encode("utf-8")).hexdigest()[:16]
    return f"{timestamp}.{digest}.jbomohi:2,S"


def _identity(message: ParsedMail) -> Identity:
    return Identity.mail(message.from_address, message.from_name or None)


def _render_thread(
    list_name: str,
    thread_key: str,
    root_id: str,
    messages: Sequence[ParsedMail],
    emitted: set[str],
    renderer: str,
) -> str:
    visible = [message for message in messages if message.message_id in emitted]
    lines = [
        (
            f"# mail/{list_name} thread {thread_key} | root {root_id} | "
            f"{len(visible)} messages | rendered by jbomohi {renderer}"
        )
    ]
    for index, message in enumerate(visible, 1):
        body, html_only = decoded_body(message.manifestation.raw.read())
        marker = " [html]" if html_only else ""
        lines.extend(
            [
                "",
                (
                    f"=== {index} | {_iso(message.timestamp)} | {message.from_header} | "
                    f"{message.message_id} | {message.file}{marker}"
                ),
                body,
            ]
        )
    return "\n".join(lines) + "\n"


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _csv_text(columns: Sequence[str], rows: Sequence[Mapping[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _summary(subject: str, list_name: str) -> str:
    cleaned = " ".join(subject.split())
    budget = 72 - len(f"mail/{list_name}: ")
    return cleaned[: max(1, budget - 1)] + "…" if len(cleaned) > budget else cleaned


def project(
    manifestations: Iterable[MailManifestation],
    *,
    renderer: str = "mail-v1",
    archive_gaps: Mapping[str, Mapping[str, str]] | None = None,
) -> Iterator[Event]:
    """Deduplicate mail, build threads, and emit one event per unique message."""

    gaps_by_list = DEFAULT_ARCHIVE_GAPS if archive_gaps is None else archive_gaps
    winners, duplicates = deduplicate(manifestations)
    by_list: dict[str, list[ParsedMail]] = defaultdict(list)
    for message in winners:
        by_list[message.manifestation.list_name].append(message)

    all_events: list[tuple[ParsedMail, str, list[ParsedMail], str]] = []
    thread_index_rows: list[Mapping[str, object]] = []
    prepared: list[ParsedMail] = []
    for list_name, messages in sorted(by_list.items()):
        message_roots, threads = _thread_order(messages)
        thread_keys: dict[str, str] = {}
        thread_paths: dict[str, str] = {}
        for root_id, thread_messages in threads.items():
            first = min(
                thread_messages, key=lambda item: (item.timestamp, item.message_id)
            )
            key = _thread_key(root_id, first.normalized_subject)
            thread_keys[root_id] = key
            year = first.timestamp.year
            thread_paths[root_id] = f"mail/{list_name}/threads/{year:04d}/{key}.txt"
            thread_index_rows.append(
                {
                    "list": list_name,
                    "thread_key": key,
                    "root_message_id": root_id,
                    "messages": len(thread_messages),
                    "path": f"mail/{list_name}/threads/{year:04d}/{key}.txt",
                }
            )
        prepared_by_id: dict[str, ParsedMail] = {}
        for message in messages:
            root_id = message_roots[message.message_id]
            key = thread_keys[root_id]
            file = f"mail/{list_name}/cur/{_mail_filename(message)}"
            ready = replace(message, file=file, thread_key=key)
            prepared_by_id[message.message_id] = ready
            prepared.append(ready)
        for root_id, thread_messages in threads.items():
            ready_thread = [
                prepared_by_id[message.message_id] for message in thread_messages
            ]
            all_events.extend(
                (
                    message,
                    root_id,
                    ready_thread,
                    thread_paths[root_id],
                )
                for message in ready_thread
            )

    emitted_by_thread: dict[tuple[str, str], set[str]] = defaultdict(set)
    initialized_lists: set[str] = set()
    pending_event: Event | None = None
    for message, root_id, thread_messages, thread_path in sorted(
        all_events,
        key=lambda item: (
            item[0].timestamp,
            item[0].manifestation.list_name,
            item[0].message_id,
        ),
    ):
        list_name = message.manifestation.list_name
        emitted = emitted_by_thread[(list_name, root_id)]
        emitted.add(message.message_id)
        changes: dict[str, str | bytes] = {
            message.file: message.manifestation.raw.read(),
            thread_path: _render_thread(
                list_name,
                message.thread_key,
                root_id,
                thread_messages,
                emitted,
                renderer,
            ),
        }
        if list_name not in initialized_lists:
            changes[f"mail/{list_name}/new/.keep"] = ""
            changes[f"mail/{list_name}/tmp/.keep"] = ""
            initialized_lists.add(list_name)
        trailers = {
            "Message-Id": message.message_id,
            "Thread": message.thread_key,
        }
        if message.in_reply_to:
            trailers["In-Reply-To"] = message.in_reply_to
        event = Event(
            source=f"mail/{list_name}",
            source_id=message.message_id,
            event="created",
            time_confidence=message.time_confidence,
            source_time=message.timestamp,
            summary=_summary(message.subject, list_name),
            author=_identity(message),
            changes=changes,
            event_window=message.event_window,
            trailers=trailers,
        )
        if pending_event is not None:
            pending_event.validate()
            yield pending_event
        pending_event = event

    if pending_event is None:
        return
    message_rows = [
        {
            "list": message.manifestation.list_name,
            "message_id": message.message_id,
            "date": _iso(message.timestamp),
            "from": message.from_header,
            "subject": message.subject,
            "thread_key": message.thread_key,
            "file": message.file,
            "manifestation": message.manifestation.manifestation,
            "duplicate_of": "",
            "spam_suspect": str(message.spam_suspect).lower(),
        }
        for message in sorted(
            prepared,
            key=lambda item: (
                item.manifestation.list_name,
                item.timestamp,
                item.message_id,
            ),
        )
    ]
    duplicate_rows = [
        {
            "list": item.winner.manifestation.list_name,
            "key": item.key,
            "message_id": item.winner.message_id,
            "winner": item.winner.manifestation.provenance,
            "winner_manifestation": item.winner.manifestation.manifestation,
            "loser": item.loser.manifestation.provenance,
            "loser_manifestation": item.loser.manifestation.manifestation,
        }
        for item in sorted(
            duplicates,
            key=lambda item: (
                item.winner.manifestation.list_name,
                item.key,
                item.loser.manifestation.provenance,
            ),
        )
    ]
    final_changes = dict(pending_event.changes)
    for list_name in sorted(by_list):
        list_messages = [
            message
            for message in prepared
            if message.manifestation.list_name == list_name
        ]
        list_duplicates = [
            item
            for item in duplicates
            if item.winner.manifestation.list_name == list_name
        ]
        final_changes[f"_meta/mail/{list_name}/messages.csv"] = _csv_text(
            (
                "list",
                "message_id",
                "date",
                "from",
                "subject",
                "thread_key",
                "file",
                "manifestation",
                "duplicate_of",
                "spam_suspect",
            ),
            [row for row in message_rows if row["list"] == list_name],
        )
        final_changes[f"_meta/mail/{list_name}/threads.csv"] = _csv_text(
            ("list", "thread_key", "root_message_id", "messages", "path"),
            [row for row in thread_index_rows if row["list"] == list_name],
        )
        final_changes[f"_meta/mail/{list_name}/duplicates.csv"] = _csv_text(
            (
                "list",
                "key",
                "message_id",
                "winner",
                "winner_manifestation",
                "loser",
                "loser_manifestation",
            ),
            [row for row in duplicate_rows if row["list"] == list_name],
        )
        manifestation_counts: dict[str, int] = defaultdict(int)
        for message in list_messages:
            manifestation_counts[message.manifestation.manifestation] += 1
        for item in list_duplicates:
            manifestation_counts[item.loser.manifestation.manifestation] += 1
        confidence_counts: dict[str, int] = defaultdict(int)
        for message in list_messages:
            confidence_counts[message.time_confidence] += 1
        coverage = [
            f"list = {json.dumps(list_name)}",
            f"manifestations = {len(list_messages) + len(list_duplicates)}",
            f"unique_messages = {len(list_messages)}",
            f"duplicates = {len(list_duplicates)}",
            f"missing_message_id = {sum(not item.had_message_id for item in list_messages)}",
            f"raw_8bit_headers = {sum(item.raw_8bit_headers for item in list_messages)}",
            f"spam_suspect = {sum(item.spam_suspect for item in list_messages)}",
            'jbovlaste_admin = "excluded; machine-generated source available separately"',
            "",
            "[manifestation_counts]",
            *(
                f"{json.dumps(name)} = {count}"
                for name, count in sorted(manifestation_counts.items())
            ),
            "",
            "[time_confidence]",
            *(
                f"{json.dumps(name)} = {count}"
                for name, count in sorted(confidence_counts.items())
            ),
            "",
        ]
        gaps = gaps_by_list.get(list_name, {})
        if gaps:
            coverage.extend(
                [
                    "[archive_gaps]",
                    *(
                        f"{json.dumps(name)} = {json.dumps(value)}"
                        for name, value in sorted(gaps.items())
                    ),
                    "",
                ]
            )
        final_changes[f"_meta/mail/{list_name}/coverage.toml"] = "\n".join(coverage)
    final_event = replace(pending_event, changes=final_changes)
    final_event.validate()
    yield final_event
