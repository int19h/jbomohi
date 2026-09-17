"""Pure IRC archive normalization and projection into source events."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from ..archive.manifest import ArchiveManifest, object_path
from ..git import Event, Identity


class IrcParseError(ValueError):
    """An IRC archive line cannot be normalized without guessing."""


ISO_LINE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) "
    r"(?P<clock>\d{2}:\d{2}:\d{2}) "
    r"(?P<zone>[^/\s]+)/(?P<offset>[+-]\d{4}) "
    r"(?P<body>.*)$"
)
LEGACY_LINE = re.compile(
    r"^(?P<day>\d{1,2}) (?P<month>[A-Z][a-z]{2}) (?P<year>\d{4}) "
    r"(?P<clock>\d{2}:\d{2}(?::\d{2})?) (?P<body>.*)$"
)
BRACKET_LINE = re.compile(r"^\[(?P<clock>\d{2}:\d{2})\] (?P<body>.*)$")
IRSSI_LINE = re.compile(r"^(?P<clock>\d{2}:\d{2})\s+(?P<body>.*)$")
IRSSI_OPEN = re.compile(
    r"^--- Log opened [A-Z][a-z]{2} (?P<month>[A-Z][a-z]{2}) "
    r"(?P<day>\d{2}) \d{2}:\d{2}:\d{2} (?P<year>\d{4})$"
)
IRSSI_DAY = re.compile(
    r"^--- Day changed [A-Z][a-z]{2} (?P<month>[A-Z][a-z]{2}) "
    r"(?P<day>\d{2}) (?P<year>\d{4})$"
)
BRACKET_RANGE = re.compile(
    r"(?P<start>\d{4}_\d{2}_\d{2})--(?P<end>\d{4}_\d{2}_\d{2})\.txt$"
)
OUTPUT_LINE = re.compile(
    r"^(?:(?:\d{2}:\d{2}:\d{2}|--:--:--) "
    r"(?:<[^>]+> .*|\* \S+ .*|-- .*)|-- day boundary \d+)$"
)
NORMAL_MESSAGE = re.compile(r"^(?:\d{2}:\d{2}:\d{2}|--:--:--) <([^>]+)> ")
NORMAL_ACTION = re.compile(r"^(?:\d{2}:\d{2}:\d{2}|--:--:--) \* (\S+) ")
DATED_FILENAME = re.compile(r"(?P<date>\d{4}_\d{2}_\d{2})(?:-\d{2}_\d{2})?\.txt$")
# SPEC.md 3.4: a wholly undated file "becomes the day its file name names".
# #jbosnu holds one hand-saved log that names its day the other way round,
# `jbosnu-robins_history_04_Apr_2004.txt`. The day is named; only the spelling
# differs, so reading it is following the rule rather than widening it.
NAMED_MONTH_FILENAME = re.compile(
    r"(?P<day>\d{1,2})_(?P<month>[A-Za-z]{3})_(?P<year>\d{4})\.txt$"
)
MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
MIRC_COLOR = re.compile(r"\x03(?:\d{1,2}(?:,\d{1,2})?)?")
MIRC_HEX_COLOR = re.compile(r"\x04(?:[0-9A-Fa-f]{6}(?:,[0-9A-Fa-f]{6})?)?")
ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~])?")
C0_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DAY_COLUMNS = (
    "date",
    "lines",
    "messages",
    "nicks",
    "tz",
    "format",
    "source",
    "days_observed",
    "days_in_range",
    "undated_lines",
    "fragments",
)


@dataclass(frozen=True, slots=True)
class ChannelArchive:
    """What the archive proves about one channel's fetch, beyond the logs.

    The month index pages are archived alongside the logs, and each records how
    many files the server listed in that directory. Comparing that with what
    was taken turns "the tail is missing" from an assertion into something the
    archive can show, without trusting anything outside it.

    That comparison is only as complete as the walk that produced it. An
    interrupted fetch archives indexes for the directories it reached and none
    for the rest, so `listed` counts what those directories held and the
    difference from `held` looks small however much is absent — the count of
    what exists is itself partial, and the arithmetic is self-consistent and
    wrong. The channel index records how many directories the server lists, so
    holding that against how many were walked says whether the comparison can
    be read as a gap at all.
    """

    listed: int = 0
    held: int = 0
    fetched_on: str = ""
    directories_listed: int | None = None
    directories_walked: int = 0

    @property
    def unfetched(self) -> int:
        return max(self.listed - self.held, 0)

    @property
    def walk_complete(self) -> bool | None:
        """Whether every directory the channel index lists was walked.

        `None` when the channel index itself is not archived, which is not the
        same as a complete walk and must not be reported as one.
        """

        if self.directories_listed is None:
            return None
        return self.directories_walked >= self.directories_listed


@dataclass(frozen=True, slots=True)
class SourceObject:
    """One immutable IRC source object selected from the archive."""

    channel: str
    path: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class IrcAmendment:
    """Update-mode identity for a changed archived day manifestation."""

    sha256: str
    supersedes_sha256: str | None

    def validate(self) -> None:
        if not SHA256.fullmatch(self.sha256):
            raise IrcParseError("IRC amendment sha256 must be 64 lowercase hex digits")
        if self.supersedes_sha256 is not None and not SHA256.fullmatch(
            self.supersedes_sha256
        ):
            raise IrcParseError(
                "IRC superseded sha256 must be 64 lowercase hex digits or none"
            )


@dataclass(frozen=True, slots=True)
class ParsedLine:
    clock: str
    rendered: str
    nick: str | None


@dataclass(frozen=True, slots=True)
class IrcUnit:
    channel: str
    date_key: str
    format: str
    tz: str
    source: str
    body: tuple[str, ...]
    source_lines: int
    messages: int
    nicks: int
    source_time: datetime
    time_confidence: str
    event_window: str | None = None
    days_observed: int | None = None
    days_in_range: int | None = None
    undated_lines: int = 0
    fragments: int = 1

    @property
    def output_path(self) -> str:
        filename = self.date_key.replace("..", "--") + ".txt"
        return f"irc/{self.channel}/{self.date_key[:4]}/{filename}"

    @property
    def header(self) -> str:
        suffix = " days=unknown" if self.days_observed is not None else ""
        return (
            f"# irc #{self.channel} {self.date_key} tz={self.tz} "
            f"source={self.source} format={self.format}{suffix}"
        )

    def render(self) -> str:
        return "\n".join((self.header, *self.body)) + "\n"

    def day_row(self) -> dict[str, str | int]:
        return {
            "date": self.date_key,
            "lines": self.source_lines,
            "messages": self.messages,
            "nicks": self.nicks,
            "tz": self.tz,
            "format": self.format,
            "source": self.source,
            "days_observed": self.days_observed or "",
            "days_in_range": self.days_in_range or "",
            "undated_lines": self.undated_lines or "",
            "fragments": self.fragments,
        }


def _clean_controls(text: str) -> str:
    without_colors = MIRC_HEX_COLOR.sub("", MIRC_COLOR.sub("", text))
    return C0_CONTROL.sub("", ANSI_ESCAPE.sub("", without_colors))


def _clock(value: str, *, seconds: bool) -> str:
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise IrcParseError(f"invalid IRC clock {value!r}") from exc
    if (
        parsed.microsecond
        or (seconds and len(value) != 8)
        or (not seconds and len(value) != 5)
    ):
        raise IrcParseError(f"invalid IRC clock {value!r}")
    return parsed.isoformat(timespec="seconds")


def _calendar_date(year: str, month: str, day: str) -> date:
    try:
        return date(int(year), MONTHS[month], int(day))
    except (KeyError, ValueError) as exc:
        raise IrcParseError(f"invalid IRC date: {day} {month} {year}") from exc


def _normalize_body(
    clock: str, raw_body: str, *, strip_nick_status: bool = False
) -> ParsedLine:
    body = _clean_controls(raw_body)
    if body.startswith("<") and ">" in body:
        marker = body.index(">")
        nick = body[1:marker].strip()
        if strip_nick_status:
            nick = nick.lstrip("@%+&~")
        if not nick:
            raise IrcParseError("IRC message has an empty nick")
        text = body[marker + 1 :]
        text = text.removeprefix(" ")
        return ParsedLine(clock, f"{clock} <{nick}> {text}", nick)
    if body.startswith("* "):
        action = body[2:]
        nick, separator, text = action.partition(" ")
        if not nick:
            raise IrcParseError("IRC action has an empty nick")
        if not separator:
            text = ""
        return ParsedLine(clock, f"{clock} * {nick} {text}", nick)
    for prefix in ("*** ", "-!- ", "-- "):
        if body.startswith(prefix):
            body = body[len(prefix) :]
            break
    return ParsedLine(clock, f"{clock} -- {body}", None)


def _decode(source: SourceObject) -> list[str]:
    # The logger archive mixes valid UTF-8 with isolated ISO-8859-1 bytes.
    # Preserve valid UTF-8 sequences and map each otherwise-invalid byte to
    # its same-valued Unicode code point; this is byte-total and deterministic.
    decoded = source.payload.decode("utf-8", errors="surrogateescape")
    text = "".join(
        chr(ord(char) - 0xDC00) if "\udc80" <= char <= "\udcff" else char
        for char in decoded
    )
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [_clean_controls(line.removesuffix("\r")) for line in lines]


def _zone(offset: str) -> timezone:
    sign = 1 if offset[0] == "+" else -1
    hours = int(offset[1:3])
    minutes = int(offset[3:5])
    if hours > 23 or minutes > 59:
        raise IrcParseError(f"invalid IRC UTC offset {offset!r}")
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def _unit_from_lines(
    source: SourceObject,
    day: date,
    source_format: str,
    tz_text: str,
    tzinfo: timezone,
    lines: Sequence[ParsedLine],
    *,
    time_confidence: str | None = None,
    event_window: str | None = None,
) -> IrcUnit:
    if not lines:
        raise IrcParseError(f"{source.path}: empty IRC day {day.isoformat()}")
    dated_clocks = [line.clock for line in lines if line.clock != "--:--:--"]
    latest = time.fromisoformat(dated_clocks[-1]) if dated_clocks else time(23, 59, 59)
    source_time = datetime.combine(day, latest, tzinfo=tzinfo)
    nicks = {line.nick for line in lines if line.nick is not None}
    return IrcUnit(
        channel=source.channel,
        date_key=day.isoformat(),
        format=source_format,
        tz=tz_text,
        source=source.path,
        body=tuple(line.rendered for line in lines),
        source_lines=len(lines),
        messages=sum(line.nick is not None for line in lines),
        nicks=len(nicks),
        source_time=source_time,
        time_confidence=time_confidence
        or ("exact" if tz_text != "unknown" else "tz-unknown"),
        event_window=event_window,
        undated_lines=sum(line.clock == "--:--:--" for line in lines),
    )


def _parse_iso(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    grouped: dict[date, list[ParsedLine]] = defaultdict(list)
    offsets: dict[date, list[str]] = defaultdict(list)
    last_offset: dict[date, str] = {}
    for number, raw in enumerate(raw_lines, 1):
        match = ISO_LINE.fullmatch(raw)
        if not match:
            raise IrcParseError(
                f"{source.path}:{number}: invalid ISO IRC line: {raw!r}"
            )
        try:
            day = date.fromisoformat(match["date"])
        except ValueError as exc:
            raise IrcParseError(f"{source.path}:{number}: invalid ISO date") from exc
        clock = _clock(match["clock"], seconds=True)
        offset = match["offset"]
        if offset not in offsets[day]:
            offsets[day].append(offset)
        last_offset[day] = offset
        grouped[day].append(_normalize_body(clock, match["body"]))
    units: list[IrcUnit] = []
    for day in sorted(grouped):
        tz_text = "/".join(offsets[day])
        units.append(
            _unit_from_lines(
                source,
                day,
                "iso",
                tz_text,
                _zone(last_offset[day]),
                grouped[day],
                time_confidence="exact",
            )
        )
    return units


def _parse_legacy(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    grouped: dict[date, list[ParsedLine]] = defaultdict(list)
    current_day: date | None = None
    undated_days: set[date] = set()
    kinds: dict[date, set[str]] = defaultdict(set)
    offsets: dict[date, list[str]] = defaultdict(list)
    last_offset: dict[date, str] = {}
    for number, raw in enumerate(raw_lines, 1):
        match = LEGACY_LINE.fullmatch(raw)
        if match:
            day = _calendar_date(match["year"], match["month"], match["day"])
            current_day = day
            kinds[day].add("legacy")
            clock = _clock(match["clock"], seconds=len(match["clock"]) == 8)
            grouped[day].append(_normalize_body(clock, match["body"]))
            continue
        iso = ISO_LINE.fullmatch(raw)
        if iso:
            try:
                day = date.fromisoformat(iso["date"])
            except ValueError as exc:
                raise IrcParseError(
                    f"{source.path}:{number}: invalid ISO date"
                ) from exc
            current_day = day
            kinds[day].add("iso")
            offset = iso["offset"]
            if offset not in offsets[day]:
                offsets[day].append(offset)
            last_offset[day] = offset
            clock = _clock(iso["clock"], seconds=True)
            grouped[day].append(_normalize_body(clock, iso["body"]))
            continue
        if current_day is None:
            raise IrcParseError(
                f"{source.path}:{number}: undated line precedes every dated line"
            )
        grouped[current_day].append(_normalize_body("--:--:--", raw))
        undated_days.add(current_day)
    units: list[IrcUnit] = []
    for day in sorted(grouped):
        day_kinds = kinds[day]
        has_undated = day in undated_days
        if day_kinds == {"iso"}:
            source_format = "iso+undated" if has_undated else "iso"
        elif "iso" in day_kinds:
            source_format = "legacy+iso+undated" if has_undated else "legacy+iso"
        else:
            source_format = "legacy+undated" if has_undated else "legacy"
        if offsets[day]:
            tz_text = "/".join(offsets[day])
            tzinfo = _zone(last_offset[day])
            confidence = "window" if has_undated else "exact"
        else:
            tz_text = "unknown"
            tzinfo = UTC
            confidence = "window" if has_undated else "tz-unknown"
        event_window = f"{day.isoformat()}..{day.isoformat()}" if has_undated else None
        units.append(
            _unit_from_lines(
                source,
                day,
                source_format,
                tz_text,
                tzinfo,
                grouped[day],
                time_confidence=confidence,
                event_window=event_window,
            )
        )
    return units


def _parse_irssi(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    grouped: dict[date, list[ParsedLine]] = defaultdict(list)
    current: date | None = None
    for number, raw in enumerate(raw_lines, 1):
        opened = IRSSI_OPEN.fullmatch(raw)
        changed = IRSSI_DAY.fullmatch(raw)
        if opened or changed:
            marker = opened or changed
            assert marker is not None
            current = _calendar_date(marker["year"], marker["month"], marker["day"])
            continue
        if raw.startswith("--- Log closed "):
            continue
        match = IRSSI_LINE.fullmatch(raw)
        if not match or current is None:
            raise IrcParseError(
                f"{source.path}:{number}: invalid irssi IRC line: {raw!r}"
            )
        clock = _clock(match["clock"], seconds=False)
        grouped[current].append(
            _normalize_body(clock, match["body"], strip_nick_status=True)
        )
    return [
        _unit_from_lines(source, day, "irssi", "unknown", UTC, grouped[day])
        for day in sorted(grouped)
        if grouped[day]
    ]


def _parse_bracket(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    match = BRACKET_RANGE.search(PurePosixPath(source.path).name)
    if not match:
        raise IrcParseError(
            f"{source.path}: bracket source lacks a date-range filename"
        )
    start = date.fromisoformat(match["start"].replace("_", "-"))
    end = date.fromisoformat(match["end"].replace("_", "-"))
    if start > end:
        raise IrcParseError(f"{source.path}: bracket date range is reversed")
    body: list[str] = []
    nicks: set[str] = set()
    messages = 0
    previous: time | None = None
    boundaries = 0
    for number, raw in enumerate(raw_lines, 1):
        line_match = BRACKET_LINE.fullmatch(raw)
        if not line_match:
            raise IrcParseError(
                f"{source.path}:{number}: invalid bracket IRC line: {raw!r}"
            )
        clock = _clock(line_match["clock"], seconds=False)
        current = time.fromisoformat(clock)
        if previous is not None and current < previous:
            boundaries += 1
            body.append(f"-- day boundary {boundaries}")
        parsed = _normalize_body(clock, line_match["body"])
        body.append(parsed.rendered)
        if parsed.nick is not None:
            nicks.add(parsed.nick)
            messages += 1
        previous = current
    if not raw_lines:
        raise IrcParseError(f"{source.path}: empty bracket IRC source")
    days_in_range = (end - start).days + 1
    return [
        IrcUnit(
            channel=source.channel,
            date_key=f"{start.isoformat()}..{end.isoformat()}",
            format="bracket",
            tz="unknown",
            source=source.path,
            body=tuple(body),
            source_lines=len(raw_lines),
            messages=messages,
            nicks=len(nicks),
            source_time=datetime.combine(end, time(23, 59, 59), tzinfo=UTC),
            time_confidence="window",
            event_window=f"{start.isoformat()}..{end.isoformat()}",
            days_observed=boundaries + 1,
            days_in_range=days_in_range,
        )
    ]


def _day_from_filename(name: str) -> date | None:
    """The day a file name names, in either spelling the logs use."""

    match = DATED_FILENAME.search(name)
    if match:
        return date.fromisoformat(match["date"].replace("_", "-"))
    named = NAMED_MONTH_FILENAME.search(name)
    if named:
        month = MONTHS.get(named["month"].capitalize())
        if month is not None:
            try:
                return date(int(named["year"]), month, int(named["day"]))
            except ValueError:
                return None
    return None


def _parse_undated(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    day = _day_from_filename(PurePosixPath(source.path).name)
    if day is None:
        raise IrcParseError(f"{source.path}: undated source lacks a dated filename")
    lines = [_normalize_body("--:--:--", raw) for raw in raw_lines]
    nicks = {line.nick for line in lines if line.nick is not None}
    return [
        IrcUnit(
            channel=source.channel,
            date_key=day.isoformat(),
            format="undated",
            tz="unknown",
            source=source.path,
            body=tuple(line.rendered for line in lines),
            source_lines=len(lines),
            messages=sum(line.nick is not None for line in lines),
            nicks=len(nicks),
            source_time=datetime.combine(day, time(23, 59, 59), tzinfo=UTC),
            time_confidence="window",
            event_window=f"{day.isoformat()}..{day.isoformat()}",
            undated_lines=len(lines),
        )
    ]


def parse_source(source: SourceObject) -> list[IrcUnit]:
    """Normalize one source object without network or clock access."""

    if not re.fullmatch(r"[a-z][a-z0-9_-]*", source.channel):
        raise IrcParseError(f"invalid IRC channel slug: {source.channel!r}")
    if not source.path or any(char.isspace() for char in source.path):
        raise IrcParseError(
            "IRC archive path must be non-empty and contain no whitespace"
        )
    raw_lines = _decode(source)
    first = next((line for line in raw_lines if line), "")
    if not first:
        return []
    if first.startswith("["):
        return _parse_bracket(source, raw_lines)
    if first.startswith("--- Log opened "):
        return _parse_irssi(source, raw_lines)
    if ISO_LINE.fullmatch(first):
        return _parse_iso(source, raw_lines)
    if LEGACY_LINE.fullmatch(first):
        return _parse_legacy(source, raw_lines)
    return _parse_undated(source, raw_lines)


def load_channel_archives(archive: Path) -> dict[str, ChannelArchive]:
    """What the archived month indexes prove about each channel's fetch.

    Every directory index the fetch walked is archived beside the logs, with
    the number of files the server listed there. Held against what was taken,
    that is the difference between "the record ends here" and "our copy of it
    does", and it needs nothing outside the archive to establish.
    """

    root = archive / "manifests" / "irc"
    if not root.exists():
        return {}
    # One URL can have several manifests: a directory index changes whenever a
    # day is added to that month, and every version is kept. Counting them all
    # would count that month's files once per fetch, so each URL contributes
    # only its newest manifest, as load_archive selects log objects.
    newest: dict[str, ArchiveManifest] = {}
    for path in sorted(root.rglob("*.toml")):
        manifest = ArchiveManifest.load(path)
        if not manifest.source.startswith("irc/"):
            continue
        previous = newest.get(manifest.origin)
        if previous is None or (manifest.fetched_at, manifest.sha256) > (
            previous.fetched_at,
            previous.sha256,
        ):
            newest[manifest.origin] = manifest

    listed: dict[str, int] = defaultdict(int)
    held: dict[str, int] = defaultdict(int)
    walked: dict[str, int] = defaultdict(int)
    directories: dict[str, int] = {}
    fetched: dict[str, str] = {}
    for manifest in newest.values():
        channel = manifest.source.removeprefix("irc/")
        day = manifest.fetched_at.date().isoformat()
        fetched[channel] = max(fetched.get(channel, day), day)
        counts = manifest.coverage.get("counts", {})
        if manifest.kind == "apache-index":
            files = counts.get("files")
            if isinstance(files, int):
                # A directory index: it lists log files.
                listed[channel] += files
                walked[channel] += 1
            listing = counts.get("directories")
            if isinstance(listing, int):
                # The channel index: it lists the directories that exist.
                directories[channel] = listing
        elif manifest.kind == "irc-log":
            held[channel] += 1
    return {
        channel: ChannelArchive(
            listed=listed.get(channel, 0),
            held=held.get(channel, 0),
            fetched_on=fetched.get(channel, ""),
            directories_listed=directories.get(channel),
            directories_walked=walked.get(channel, 0),
        )
        for channel in sorted(set(listed) | set(held) | set(directories))
    }


def load_archive(archive: Path) -> list[SourceObject]:
    """Load the newest immutable manifestation of each fetched IRC URL."""

    root = archive / "manifests" / "irc"
    if not root.exists():
        return []
    selected: dict[str, ArchiveManifest] = {}
    for path in sorted(root.rglob("*.toml")):
        if path.is_symlink():
            raise IrcParseError(f"IRC manifest must not be a symlink: {path}")
        manifest = ArchiveManifest.load(path)
        if manifest.kind != "irc-log":
            continue
        previous = selected.get(manifest.origin)
        if previous is None or (manifest.fetched_at, manifest.sha256) > (
            previous.fetched_at,
            previous.sha256,
        ):
            selected[manifest.origin] = manifest
    sources: list[SourceObject] = []
    for origin, manifest in sorted(selected.items()):
        if not manifest.source.startswith("irc/"):
            raise IrcParseError(f"IRC manifest has invalid source: {manifest.source!r}")
        channel = manifest.source.removeprefix("irc/")
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"lojban.org", "www.lojban.org"}
            or not parsed.path.startswith("/irclogs/")
        ):
            raise IrcParseError(f"IRC manifest has invalid origin: {origin!r}")
        obj = object_path(archive, manifest.sha256)
        if obj.is_symlink():
            raise IrcParseError(f"IRC archive object must not be a symlink: {obj}")
        try:
            payload = obj.read_bytes()
        except OSError as exc:
            raise IrcParseError(f"IRC archive object is unreadable: {obj}") from exc
        if (
            len(payload) != manifest.bytes
            or hashlib.sha256(payload).hexdigest() != manifest.sha256
        ):
            raise IrcParseError(f"IRC archive object does not match manifest: {obj}")
        relative = parsed.path.removeprefix("/irclogs/")
        sources.append(SourceObject(channel=channel, path=relative, payload=payload))
    return sources


def validate_rendered(unit: IrcUnit) -> None:
    """Check that a unit obeys the normalized line grammar."""

    expected_prefix = f"# irc #{unit.channel} {unit.date_key} "
    if not unit.header.startswith(expected_prefix):
        raise IrcParseError(f"invalid IRC header: {unit.header!r}")
    for number, line in enumerate(unit.body, 2):
        if not OUTPUT_LINE.fullmatch(line):
            raise IrcParseError(
                f"{unit.output_path}:{number}: invalid normalized line {line!r}"
            )


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _coverage_toml(
    channel: str,
    units: Sequence[IrcUnit],
    missing: Sequence[date],
    archive: ChannelArchive,
) -> str:
    """What this channel's projection covers, and what it demonstrably lacks.

    SPEC.md 3.4 gives IRC a day index and a gaps file, which between them say
    what was projected and what was recorded as absent. Neither says how far
    the archive itself reaches, so a reader could not tell a channel that ends
    in 2022 because the conversation stopped from one that ends in 2022 because
    a fetch did.
    """

    # A range block's key is `<from>..<to>`, so a field called first_day must
    # read the endpoints out of it rather than store the key. Naming a range as
    # though it were a day tells the reader something false and breaks anything
    # that parses this file as dates.
    days: set[str] = set()
    for unit in units:
        if unit.date_key == "unknown":
            continue
        days.update(unit.date_key.split(".."))
    ordered = sorted(days)
    lines = [
        "# What this channel's projection covers (SPEC.md 3.4).",
        "# Written by jbomohi build; do not edit.",
        "",
        f"channel = {_toml_string(channel)}",
        # One row per projected file, which is what days.csv holds. A range
        # block is one file covering many days, so calling this "days" was the
        # other half of the same inaccuracy.
        f"files = {len(units)}",
    ]
    ranges = sum(1 for unit in units if ".." in unit.date_key)
    if ranges:
        lines.append(f"range_files = {ranges}")
    if ordered:
        lines.append(f"first_day = {_toml_string(ordered[0])}")
        lines.append(f"last_day = {_toml_string(ordered[-1])}")
    if not units:
        lines.append(
            "note = "
            + _toml_string(
                "this channel is configured but nothing is archived for it, so "
                "the repository holds none of it; a negative answer about it "
                "says only that it was never fetched"
            )
        )
        return "\n".join(lines).rstrip("\n") + "\n"
    lines.append(f"days_recorded_absent = {len(missing)}")
    undated = sum(1 for unit in units if unit.date_key == "unknown")
    if undated:
        lines.append(f"undated_sources = {undated}")
    if archive.fetched_on:
        lines.append(f"fetched_on = {_toml_string(archive.fetched_on)}")
    if archive.listed or archive.directories_walked:
        complete = archive.walk_complete
        lines.append("")
        lines.append("[archive]")
        if archive.directories_listed is not None:
            lines.append(
                f"directories_the_server_listed = {archive.directories_listed}"
            )
        lines.append(f"directories_walked = {archive.directories_walked}")
        lines.append("index_walk_complete = " + ("true" if complete else "false"))
        lines.append(f"files_the_server_listed = {archive.listed}")
        lines.append(f"files_archived = {archive.held}")
        lines.append(f"files_listed_but_not_archived = {archive.unfetched}")
        note = _archive_note(archive, complete)
        if note:
            lines.append("note = " + _toml_string(note))
    return "\n".join(lines).rstrip("\n") + "\n"


def _archive_note(archive: ChannelArchive, complete: bool | None) -> str:
    """What the file counts above may and may not be read as.

    When the walk did not finish, the difference between listed and archived is
    a lower bound and nothing more: the directories never visited contribute to
    neither side. Reporting it as the gap is how a channel thirteen years and
    1,775 files short of the record read as ten files short.
    """

    if complete is None:
        return (
            "the channel index is not in this archive, so how many directories "
            "the server lists is unknown and the counts above cover only the "
            "directories that were walked; the difference is a lower bound on "
            "what is missing, not its size"
        )
    if not complete:
        return (
            f"the index walk did not finish: {archive.directories_walked} of "
            f"{archive.directories_listed} directories were visited, so the "
            "counts above cover only those; the fetch is incomplete and the "
            "difference is a lower bound on what is missing, not its size"
        )
    if archive.unfetched:
        return (
            "the server listed files this archive does not hold, so the gap is "
            "in the fetch rather than in the record; refetching closes it"
        )
    return ""


def _render_days(rows: Sequence[dict[str, str | int]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=DAY_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _covered_dates(unit: IrcUnit) -> set[date]:
    if ".." not in unit.date_key:
        return {date.fromisoformat(unit.date_key)}
    start_text, end_text = unit.date_key.split("..")
    start = date.fromisoformat(start_text)
    end = date.fromisoformat(end_text)
    return {start + timedelta(days=offset) for offset in range((end - start).days + 1)}


def _missing_dates(units: Sequence[IrcUnit]) -> list[date]:
    covered: set[date] = set()
    for unit in units:
        covered.update(_covered_dates(unit))
    if not covered:
        return []
    first = min(covered)
    last = max(covered)
    return [
        first + timedelta(days=offset)
        for offset in range((last - first).days + 1)
        if first + timedelta(days=offset) not in covered
    ]


def _render_gaps(days: Sequence[date]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("date", "reason"))
    writer.writerows((day.isoformat(), "no source file") for day in days)
    return stream.getvalue()


def _line_stats(body: Sequence[str]) -> tuple[int, int]:
    nicks: set[str] = set()
    messages = 0
    for line in body:
        match = NORMAL_MESSAGE.match(line)
        if match:
            nicks.add(match[1])
            messages += 1
            continue
        action = NORMAL_ACTION.match(line)
        if action:
            nicks.add(action[1])
            messages += 1
    return messages, len(nicks)


def _clock_sort(body: Sequence[str]) -> tuple[str, ...]:
    indexed = enumerate(body)
    return tuple(
        line
        for _, line in sorted(
            indexed,
            key=lambda item: (
                item[1][:8]
                if re.match(r"^\d{2}:\d{2}:\d{2} ", item[1])
                else "99:99:99",
                item[0],
            ),
        )
    )


def _merge_same_format(units: Sequence[IrcUnit]) -> tuple[str, ...]:
    multiplicity: Counter[str] = Counter()
    for unit in units:
        counts = Counter(unit.body)
        for line, count in counts.items():
            multiplicity[line] = max(multiplicity[line], count)
    used: Counter[str] = Counter()
    merged: list[str] = []
    for unit in sorted(units, key=lambda item: item.source):
        for line in unit.body:
            if used[line] < multiplicity[line]:
                merged.append(line)
                used[line] += 1
    return _clock_sort(merged)


def _minute_body_key(line: str) -> str:
    return line[:5] + line[8:]


def _merge_iso_irssi(units: Sequence[IrcUnit]) -> tuple[tuple[str, ...], int]:
    iso = [unit for unit in units if unit.format == "iso"]
    irssi = [unit for unit in units if unit.format == "irssi"]
    base = list(_merge_same_format(irssi))
    positions: dict[str, deque[int]] = defaultdict(deque)
    for index, line in enumerate(base):
        positions[_minute_body_key(line)].append(index)
    matched = 0
    for line in _merge_same_format(iso):
        matches = positions[_minute_body_key(line)]
        if matches:
            base[matches.popleft()] = line
            matched += 1
        else:
            base.append(line)
    return _clock_sort(base), matched


def _merge_units(units: Sequence[IrcUnit]) -> IrcUnit:
    if len(units) == 1:
        return units[0]
    formats = {unit.format for unit in units}
    legacy_family = formats <= {
        "legacy",
        "legacy+undated",
        "legacy+iso",
        "legacy+iso+undated",
        "iso",
        "iso+undated",
        "undated",
    }
    if len(formats) == 1 and not legacy_family:
        body = _merge_same_format(units)
        source_format = units[0].format
        tz_values = {unit.tz for unit in units}
        tz_text = next(iter(tz_values)) if len(tz_values) == 1 else "unknown"
        confidence = units[0].time_confidence if len(tz_values) == 1 else "tz-unknown"
        source_time = max(unit.source_time for unit in units)
    elif legacy_family:
        body = _merge_same_format(units)
        has_legacy = any("legacy" in name for name in formats)
        has_iso = any("iso" in name for name in formats)
        has_undated = any(unit.undated_lines for unit in units)
        if has_legacy and has_iso:
            source_format = "legacy+iso+undated" if has_undated else "legacy+iso"
        elif has_iso:
            source_format = "iso+undated" if has_undated else "iso"
        elif has_legacy:
            source_format = "legacy+undated" if has_undated else "legacy"
        else:
            source_format = "undated"
        known_offsets: list[str] = []
        for unit in sorted(units, key=lambda item: item.source):
            if unit.tz == "unknown":
                continue
            for offset in unit.tz.split("/"):
                if offset not in known_offsets:
                    known_offsets.append(offset)
        tz_text = "/".join(known_offsets) if known_offsets else "unknown"
        if has_undated:
            confidence = "window"
        elif known_offsets:
            confidence = "exact"
        else:
            confidence = "tz-unknown"
        dated = [line for line in body if not line.startswith("--:--:-- ")]
        latest = (
            max(time.fromisoformat(line[:8]) for line in dated)
            if dated
            else time(23, 59, 59)
        )
        tzinfo = _zone(known_offsets[-1]) if known_offsets else UTC
        source_time = datetime.combine(
            date.fromisoformat(units[0].date_key), latest, tzinfo=tzinfo
        )
    elif formats == {"iso", "irssi"}:
        body, matched = _merge_iso_irssi(units)
        iso_offsets: list[str] = []
        for unit in sorted(units, key=lambda item: item.source):
            if unit.format != "iso" or unit.tz == "unknown":
                continue
            for offset in unit.tz.split("/"):
                if offset not in iso_offsets:
                    iso_offsets.append(offset)
        if matched and iso_offsets:
            source_format = "iso+irssi"
            tz_text = "/".join(iso_offsets)
            confidence = "exact"
            tzinfo = _zone(iso_offsets[-1])
        else:
            source_format = "irssi"
            tz_text = "unknown"
            confidence = "tz-unknown"
            tzinfo = UTC
        day = date.fromisoformat(units[0].date_key)
        latest = max(time.fromisoformat(line[:8]) for line in body)
        source_time = datetime.combine(day, latest, tzinfo=tzinfo)
    else:
        names = ",".join(sorted(formats))
        raise IrcParseError(
            f"unsupported source-format overlap for {units[0].output_path}: {names}"
        )
    messages, nicks = _line_stats(body)
    sources = ",".join(sorted(unit.source for unit in units))
    exemplar = units[0]
    event_window = exemplar.event_window
    if confidence == "window" and event_window is None:
        event_window = f"{exemplar.date_key}..{exemplar.date_key}"
    return IrcUnit(
        channel=exemplar.channel,
        date_key=exemplar.date_key,
        format=source_format,
        tz=tz_text,
        source=sources,
        body=body,
        source_lines=len(body),
        messages=messages,
        nicks=nicks,
        source_time=source_time,
        time_confidence=confidence,
        event_window=event_window,
        days_observed=exemplar.days_observed,
        days_in_range=exemplar.days_in_range,
        undated_lines=sum(line.startswith("--:--:-- ") for line in body),
        fragments=sum(unit.fragments for unit in units),
    )


def project(
    sources: Iterable[SourceObject],
    *,
    amendments: Mapping[str, IrcAmendment] | None = None,
    archives: Mapping[str, ChannelArchive] | None = None,
    channels: Iterable[str] | None = None,
) -> Iterator[Event]:
    """Project source objects to chronologically ordered IRC events.

    Initial builds omit ``amendments`` and receive stable date source IDs.
    Update orchestration supplies changed output paths and archive digests;
    the projector remains pure and emits the spec-defined unique edit IDs.
    """

    parsed: list[IrcUnit] = []
    for source in sources:
        parsed.extend(parse_source(source))
    # A channel nobody fetched has no source objects, so the projector would
    # never mention it and a reader could not tell it apart from a channel that
    # does not exist. SPEC.md 3.4's gaps files say what is absent; a whole
    # absent channel deserves the same treatment, and only the caller knows
    # which channels were configured.
    configured = sorted(set(channels or ()) - {unit.channel for unit in parsed})
    grouped: dict[str, list[IrcUnit]] = defaultdict(list)
    for unit in parsed:
        grouped[unit.output_path].append(unit)
    unknown_amendments = set(amendments or {}) - set(grouped)
    if unknown_amendments:
        names = ", ".join(sorted(unknown_amendments))
        raise IrcParseError(f"IRC amendments name unprojected paths: {names}")
    units = [_merge_units(group) for group in grouped.values()]
    units.sort(
        key=lambda unit: (unit.source_time, unit.channel, unit.date_key, unit.source)
    )
    rows: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    channel_units: dict[str, list[IrcUnit]] = defaultdict(list)
    for unit in units:
        rows[unit.channel].append(unit.day_row())
        channel_units[unit.channel].append(unit)
    for channel_rows in rows.values():
        channel_rows.sort(key=lambda row: str(row["date"]))

    # Every channel's index and coverage ride the stream's final event, not the
    # final event of their own channel. A file that describes a whole channel
    # must not depend on whether one of that channel's days happened to be new:
    # #lojban was complete, so its last event was already in the corpus and was
    # skipped, and its coverage.toml kept a shape two releases old while the
    # channels that gained days got the current one. SPEC.md 4.2 already treats
    # a source's _meta as riding its stream's final event; this makes IRC do
    # that rather than fan it across channels.
    stream_meta: dict[str, str | bytes] = {}
    for channel in sorted({*channel_units, *configured}):
        held = channel_units.get(channel, [])
        missing = _missing_dates(held)
        if held:
            stream_meta[f"_meta/irc/{channel}/days.csv"] = _render_days(rows[channel])
            if missing:
                stream_meta[f"_meta/irc/{channel}/gaps.csv"] = _render_gaps(missing)
        stream_meta[f"_meta/irc/{channel}/coverage.toml"] = _coverage_toml(
            channel,
            held,
            missing,
            (archives or {}).get(channel, ChannelArchive()),
        )

    for index, unit in enumerate(units):
        validate_rendered(unit)
        changes: dict[str, str | bytes] = {unit.output_path: unit.render()}
        if index == len(units) - 1:
            changes.update(stream_meta)
        amendment = (amendments or {}).get(unit.output_path)
        event_kind = "import"
        source_id = unit.date_key
        trailers: dict[str, str] = {}
        if amendment is not None:
            amendment.validate()
            event_kind = "edited"
            source_id = f"{unit.date_key}@{amendment.sha256[:12]}"
            previous = (
                amendment.supersedes_sha256[:12]
                if amendment.supersedes_sha256 is not None
                else "none"
            )
            trailers["Supersedes-Manifestation"] = previous
        yield Event(
            source=f"irc/{unit.channel}",
            source_id=source_id,
            event=event_kind,
            time_confidence=unit.time_confidence,
            source_time=unit.source_time,
            summary=f"{unit.date_key} ({unit.source_lines} lines)",
            author=Identity.irc(),
            changes=changes,
            event_window=unit.event_window,
            trailers=trailers,
        )
