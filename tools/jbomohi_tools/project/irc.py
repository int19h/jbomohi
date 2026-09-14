"""Pure IRC archive normalization and projection into source events."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Iterator, Sequence
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
class SourceObject:
    """One immutable IRC source object selected from the archive."""

    channel: str
    path: str
    payload: bytes


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
        time_confidence="exact" if tz_text != "unknown" else "tz-unknown",
        undated_lines=sum(line.clock == "--:--:--" for line in lines),
    )


def _parse_iso(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    grouped: dict[date, list[ParsedLine]] = defaultdict(list)
    offsets: dict[date, set[str]] = defaultdict(set)
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
        offsets[day].add(match["offset"])
        grouped[day].append(_normalize_body(clock, match["body"]))
    units: list[IrcUnit] = []
    for day in sorted(grouped):
        if len(offsets[day]) == 1:
            offset = next(iter(offsets[day]))
            units.append(
                _unit_from_lines(
                    source, day, "iso", offset, _zone(offset), grouped[day]
                )
            )
        else:
            units.append(
                _unit_from_lines(source, day, "iso", "unknown", UTC, grouped[day])
            )
    return units


def _parse_legacy(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    grouped: dict[date, list[ParsedLine]] = defaultdict(list)
    current_day: date | None = None
    undated_days: set[date] = set()
    for number, raw in enumerate(raw_lines, 1):
        match = LEGACY_LINE.fullmatch(raw)
        if match:
            day = _calendar_date(match["year"], match["month"], match["day"])
            current_day = day
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
            clock = _clock(iso["clock"], seconds=True)
            grouped[day].append(_normalize_body(clock, iso["body"]))
            continue
        if current_day is None:
            raise IrcParseError(
                f"{source.path}:{number}: undated line precedes every dated line"
            )
        grouped[current_day].append(_normalize_body("--:--:--", raw))
        undated_days.add(current_day)
    return [
        _unit_from_lines(
            source,
            day,
            "legacy+undated" if day in undated_days else "legacy",
            "unknown",
            UTC,
            grouped[day],
        )
        for day in sorted(grouped)
    ]


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


def _parse_undated(source: SourceObject, raw_lines: Sequence[str]) -> list[IrcUnit]:
    match = DATED_FILENAME.search(PurePosixPath(source.path).name)
    if not match:
        raise IrcParseError(f"{source.path}: undated source lacks a dated filename")
    day = date.fromisoformat(match["date"].replace("_", "-"))
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
    legacy_family = formats <= {"legacy", "legacy+undated", "undated"}
    if len(formats) == 1 or legacy_family:
        body = _merge_same_format(units)
        source_format = (
            "legacy+undated"
            if formats & {"legacy+undated", "undated"} and len(formats) > 1
            else units[0].format
        )
        tz_values = {unit.tz for unit in units}
        tz_text = next(iter(tz_values)) if len(tz_values) == 1 else "unknown"
        if any(unit.undated_lines for unit in units):
            confidence = "window"
        else:
            confidence = (
                units[0].time_confidence if len(tz_values) == 1 else "tz-unknown"
            )
        latest_unit = max(units, key=lambda unit: unit.source_time)
        source_time = latest_unit.source_time
        if confidence in {"tz-unknown", "window"}:
            source_time = source_time.replace(tzinfo=UTC)
    elif formats == {"iso", "irssi"}:
        body, matched = _merge_iso_irssi(units)
        iso_zones = {
            unit.tz for unit in units if unit.format == "iso" and unit.tz != "unknown"
        }
        if matched and len(iso_zones) == 1:
            source_format = "iso+irssi"
            tz_text = next(iter(iso_zones))
            confidence = "exact"
            tzinfo = _zone(tz_text)
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


def project(sources: Iterable[SourceObject]) -> Iterator[Event]:
    """Project source objects to chronologically ordered IRC events."""

    parsed: list[IrcUnit] = []
    for source in sources:
        parsed.extend(parse_source(source))
    grouped: dict[str, list[IrcUnit]] = defaultdict(list)
    for unit in parsed:
        grouped[unit.output_path].append(unit)
    units = [_merge_units(group) for group in grouped.values()]
    units.sort(
        key=lambda unit: (unit.source_time, unit.channel, unit.date_key, unit.source)
    )
    rows: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    channel_units: dict[str, list[IrcUnit]] = defaultdict(list)
    last_for_channel: dict[str, int] = {}
    for index, unit in enumerate(units):
        rows[unit.channel].append(unit.day_row())
        channel_units[unit.channel].append(unit)
        last_for_channel[unit.channel] = index
    for channel_rows in rows.values():
        channel_rows.sort(key=lambda row: str(row["date"]))

    for index, unit in enumerate(units):
        validate_rendered(unit)
        changes = {unit.output_path: unit.render()}
        if last_for_channel[unit.channel] == index:
            index_path = f"_meta/irc/{unit.channel}/days.csv"
            changes[index_path] = _render_days(rows[unit.channel])
            missing = _missing_dates(channel_units[unit.channel])
            if missing:
                gap_path = f"_meta/irc/{unit.channel}/gaps.csv"
                changes[gap_path] = _render_gaps(missing)
        yield Event(
            source=f"irc/{unit.channel}",
            source_id=unit.date_key,
            event="import",
            time_confidence=unit.time_confidence,
            source_time=unit.source_time,
            summary=f"{unit.date_key} ({unit.source_lines} lines)",
            author=Identity.irc(),
            changes=changes,
            event_window=unit.event_window,
        )
