"""Rate-limited, resumable acquisition of the public IRC archive."""

from __future__ import annotations

import calendar
import hashlib
import re
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .manifest import ArchiveError, ArchiveManifest, store_object

BASE_URL = "https://lojban.org/irclogs/"
CHANNELS = ("lojban", "jbosnu", "ckule")
SPECIAL_DIRECTORIES = {
    "2000_all": date(2000, 10, 28),
    "2002_middle": date(2002, 11, 28),
    "2002_12": date(2002, 12, 31),
}


class IrcFetchError(ArchiveError):
    """IRC discovery or download failed after bounded retries."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    url: str
    body: bytes
    headers: Message


@dataclass(frozen=True, slots=True)
class FetchReport:
    manifests: tuple[Path, ...]
    downloaded_logs: int
    reused_logs: int


class ResponseClient(Protocol):
    def get(self, url: str) -> HttpResponse: ...


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        for name, value in attrs:
            if name.casefold() == "href" and value is not None:
                self.hrefs.append(value)


class HttpClient:
    """Small urllib client with source-wide pacing and bounded backoff."""

    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        attempts: int = 4,
        timeout: float = 30.0,
        max_bytes: int = 128 * 1024 * 1024,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_interval < 0 or attempts < 1 or timeout <= 0 or max_bytes < 1:
            raise ValueError("invalid IRC HTTP client limits")
        self.min_interval = min_interval
        self.attempts = attempts
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request: float | None = None

    def _pace(self) -> None:
        now = self.monotonic()
        if self._last_request is not None:
            remaining = self.min_interval - (now - self._last_request)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request = self.monotonic()

    def get(self, url: str) -> HttpResponse:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            self._pace()
            request = Request(url, headers={"User-Agent": "jbomohi/0.1 IRC archiver"})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl()
                    parsed = urlsplit(final_url)
                    if (
                        parsed.scheme != "https"
                        or parsed.hostname not in {"lojban.org", "www.lojban.org"}
                        or not parsed.path.startswith("/irclogs/")
                    ):
                        raise IrcFetchError(
                            f"IRC response escaped the source origin: {final_url}"
                        )
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        try:
                            declared_length = int(content_length)
                        except ValueError as exc:
                            raise IrcFetchError(
                                f"IRC response has invalid Content-Length: {final_url}"
                            ) from exc
                        if declared_length < 0 or declared_length > self.max_bytes:
                            raise IrcFetchError(
                                f"IRC response exceeds {self.max_bytes} bytes: {final_url}"
                            )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise IrcFetchError(
                            f"IRC response exceeds {self.max_bytes} bytes: {final_url}"
                        )
                    return HttpResponse(
                        url=final_url,
                        body=body,
                        headers=response.headers,
                    )
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
                retry_after = exc.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 2**attempt
                )
                delay = min(delay, 60.0)
            except URLError as exc:
                last_error = exc
                delay = 2**attempt
            if attempt + 1 < self.attempts:
                self.sleep(delay)
        raise IrcFetchError(f"failed to fetch {url}: {last_error}")


def _links(response: HttpResponse, *, directories: bool) -> list[str]:
    try:
        text = response.body.decode("iso-8859-1")
    except UnicodeDecodeError as exc:
        raise IrcFetchError(f"index is not ISO-8859-1: {response.url}") from exc
    parser = _LinkParser()
    parser.feed(text)
    matches: set[str] = set()
    for href in parser.hrefs:
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            continue
        name = parsed.path
        if "/" in name.rstrip("/") or name in {"", "../"}:
            continue
        if directories and name.endswith("/"):
            directory = name.removesuffix("/")
            if directory in SPECIAL_DIRECTORIES or _month_end(directory) is not None:
                matches.add(name)
        elif not directories and name.casefold().endswith((".txt", ".log")):
            matches.add(name)
    return sorted(matches)


def _month_end(directory: str) -> date | None:
    if len(directory) != 7 or directory[4] != "_":
        return None
    try:
        year = int(directory[:4])
        month = int(directory[5:])
        return date(year, month, calendar.monthrange(year, month)[1])
    except ValueError:
        return None


def _directory_end(directory: str) -> date | None:
    return SPECIAL_DIRECTORIES.get(directory) or _month_end(directory)


def _file_end(filename: str, directory: str) -> date | None:
    dates = [
        date.fromisoformat(match.replace("_", "-"))
        for match in re.findall(r"\d{4}_\d{2}_\d{2}", filename)
    ]
    return max(dates) if dates else _directory_end(directory)


def _parse_since(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise IrcFetchError("--since must be an ISO date (YYYY-MM-DD)") from exc
    if parsed.isoformat() != value:
        raise IrcFetchError("--since must be an ISO date (YYYY-MM-DD)")
    return parsed


def _coverage(url: str, payload: bytes) -> dict[str, object]:
    filename = Path(urlsplit(url).path).name
    dates = [
        date.fromisoformat(match.replace("_", "-"))
        for match in re.findall(r"\d{4}_\d{2}_\d{2}", filename)
    ]
    start = min(dates).isoformat() if dates else "unknown"
    end = max(dates).isoformat() if dates else "unknown"
    lines = payload.count(b"\n") + int(bool(payload) and not payload.endswith(b"\n"))
    return {"from": start, "to": end, "counts": {"lines": lines}}


def _manifest_path(archive: Path, channel: str, origin: str, digest: str) -> Path:
    origin_key = hashlib.sha256(origin.encode()).hexdigest()[:20]
    return archive / "manifests" / "irc" / channel / f"{origin_key}-{digest}.toml"


def _known_manifests(archive: Path) -> dict[str, list[ArchiveManifest]]:
    known: dict[str, list[ArchiveManifest]] = defaultdict(list)
    root = archive / "manifests" / "irc"
    if not root.exists():
        return known
    for path in sorted(root.rglob("*.toml")):
        manifest = ArchiveManifest.load(path)
        known[manifest.origin].append(manifest)
    return known


def _archive_response(
    archive: Path,
    channel: str,
    kind: str,
    response: HttpResponse,
    fetched_at: datetime,
    *,
    counts: dict[str, int] | None = None,
) -> Path:
    parsed_url = urlsplit(response.url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname not in {"lojban.org", "www.lojban.org"}
        or not parsed_url.path.startswith("/irclogs/")
    ):
        raise IrcFetchError(f"IRC response escaped the source origin: {response.url}")
    stored = store_object(archive, response.body)
    coverage = _coverage(response.url, response.body)
    if counts is not None:
        coverage = {"from": "unknown", "to": "unknown", "counts": counts}
    manifest = ArchiveManifest(
        source=f"irc/{channel}",
        kind=kind,
        origin=response.url,
        fetched_at=fetched_at,
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage=coverage,
        notes=urlsplit(response.url).path.removeprefix("/irclogs/"),
    )
    path = _manifest_path(archive, channel, response.url, stored.sha256)
    if not path.exists():
        manifest.write(path)
    return path


def fetch(
    archive: Path,
    since: str | None = None,
    *,
    channels: Iterable[str] = CHANNELS,
    client: ResponseClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FetchReport:
    """Fetch IRC indexes and logs into the immutable archive tier.

    An unchanged directory index lets an interrupted or repeated fetch reuse
    already-manifested log objects. A changed index refetches that directory's
    files so amended day logs produce new immutable objects and manifests.
    """

    cutoff = _parse_since(since)
    http = client or HttpClient()
    known = _known_manifests(archive)
    manifests: list[Path] = []
    downloaded = 0
    reused = 0
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise IrcFetchError("fetch time must include a UTC offset")

    for channel in channels:
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", channel):
            raise IrcFetchError(f"invalid IRC channel slug: {channel!r}")
        channel_url = urljoin(BASE_URL, f"{channel}/")
        channel_index = http.get(channel_url)
        directories = _links(channel_index, directories=True)
        manifests.append(
            _archive_response(
                archive,
                channel,
                "apache-index",
                channel_index,
                fetched_at,
                counts={"directories": len(directories)},
            )
        )
        for directory_link in directories:
            directory = directory_link.removesuffix("/")
            end = _directory_end(directory)
            if cutoff is not None and end is not None and end < cutoff:
                continue
            directory_url = urljoin(channel_index.url, directory_link)
            directory_index = http.get(directory_url)
            files = _links(directory_index, directories=False)
            prior_digests = {
                manifest.sha256 for manifest in known.get(directory_index.url, [])
            }
            index_digest = hashlib.sha256(directory_index.body).hexdigest()
            index_changed = index_digest not in prior_digests
            manifests.append(
                _archive_response(
                    archive,
                    channel,
                    "apache-index",
                    directory_index,
                    fetched_at,
                    counts={"files": len(files)},
                )
            )
            for filename in files:
                file_end = _file_end(filename, directory)
                if cutoff is not None and file_end is not None and file_end < cutoff:
                    continue
                url = urljoin(directory_index.url, filename)
                if not index_changed and known.get(url):
                    reused += 1
                    continue
                response = http.get(url)
                manifests.append(
                    _archive_response(
                        archive,
                        channel,
                        "irc-log",
                        response,
                        fetched_at,
                    )
                )
                downloaded += 1
    return FetchReport(tuple(manifests), downloaded, reused)
