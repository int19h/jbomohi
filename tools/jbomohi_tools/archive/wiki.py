"""Rate-limited, resumable MediaWiki API acquisition."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .manifest import ArchiveError, ArchiveManifest, object_path, store_object

API_URL = "https://mw.lojban.org/api.php"
NAMESPACES = tuple(range(16)) + (200, 201, 202, 203, 828, 829)
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


class WikiFetchError(ArchiveError):
    """MediaWiki acquisition failed or returned an unsafe response."""


@dataclass(frozen=True, slots=True)
class ApiResponse:
    url: str
    body: bytes
    headers: Message


class ResponseClient(Protocol):
    def query(self, params: Mapping[str, str]) -> ApiResponse: ...


@dataclass(frozen=True, slots=True)
class FetchReport:
    manifests: tuple[Path, ...]
    pages: int
    revision_batches: int
    log_batches: int
    media_batches: int
    reused_responses: int


def query_url(params: Mapping[str, str]) -> str:
    complete = {
        "format": "json",
        "formatversion": "2",
        "maxlag": "5",
        **params,
    }
    return API_URL + "?" + urlencode(sorted(complete.items()))


class WikiApiClient:
    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        attempts: int = 4,
        timeout: float = 30.0,
        max_bytes: int = 64 * 1024 * 1024,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_interval < 0 or attempts < 1 or timeout <= 0 or max_bytes < 1:
            raise ValueError("invalid MediaWiki HTTP client limits")
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
            delay = self.min_interval - (now - self._last_request)
            if delay > 0:
                self.sleep(delay)
        self._last_request = self.monotonic()

    def query(self, params: Mapping[str, str]) -> ApiResponse:
        url = query_url(params)
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            self._pace()
            request = Request(url, headers={"User-Agent": "jbomohi/0.1 wiki archiver"})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl()
                    parsed = urlsplit(final_url)
                    if (
                        parsed.scheme != "https"
                        or parsed.hostname != "mw.lojban.org"
                        or parsed.path != "/api.php"
                    ):
                        raise WikiFetchError(
                            f"MediaWiki response escaped the API origin: {final_url}"
                        )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise WikiFetchError(
                            f"MediaWiki response exceeds {self.max_bytes} bytes"
                        )
                    try:
                        document = json.loads(body)
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise WikiFetchError("MediaWiki returned invalid JSON") from exc
                    if isinstance(document, dict) and "error" in document:
                        error = document["error"]
                        code = error.get("code") if isinstance(error, dict) else None
                        if code == "maxlag":
                            last_error = WikiFetchError(f"MediaWiki maxlag: {error!r}")
                            delay = min(2**attempt, 60)
                        else:
                            raise WikiFetchError(f"MediaWiki API error: {error!r}")
                    else:
                        return ApiResponse(final_url, body, response.headers)
            except HTTPError as exc:
                last_error = exc
                if exc.code not in TRANSIENT_HTTP:
                    break
                delay = min(2**attempt, 60)
            except (URLError, OSError) as exc:
                last_error = exc
                delay = min(2**attempt, 60)
            if attempt + 1 < self.attempts:
                self.sleep(delay)
        raise WikiFetchError(f"failed to query MediaWiki: {last_error}")


def _manifest_path(archive: Path, kind: str, url: str, digest: str) -> Path:
    request_key = hashlib.sha256(url.encode()).hexdigest()[:20]
    return archive / "manifests" / "wiki" / kind / f"{request_key}-{digest}.toml"


def _coverage(document: object) -> dict[str, object]:
    timestamps: list[str] = []
    counts: dict[str, int] = {}
    if isinstance(document, dict) and isinstance(document.get("query"), dict):
        query = document["query"]
        pages = query.get("pages")
        if isinstance(pages, list):
            counts["pages"] = len(pages)
            revisions = [
                revision
                for page in pages
                if isinstance(page, dict) and isinstance(page.get("revisions"), list)
                for revision in page["revisions"]
                if isinstance(revision, dict)
            ]
            counts["revisions"] = len(revisions)
            timestamps.extend(
                item["timestamp"]
                for item in revisions
                if isinstance(item.get("timestamp"), str)
            )
        allpages = query.get("allpages")
        if isinstance(allpages, list):
            counts["pages"] = len(allpages)
        logs = query.get("logevents")
        if isinstance(logs, list):
            counts["logevents"] = len(logs)
            timestamps.extend(
                item["timestamp"]
                for item in logs
                if isinstance(item, dict) and isinstance(item.get("timestamp"), str)
            )
        statistics = query.get("statistics")
        if isinstance(statistics, dict) and isinstance(statistics.get("pages"), int):
            counts["pages"] = statistics["pages"]
    if not counts:
        counts["responses"] = 1
    return {
        "from": min(timestamps) if timestamps else "unknown",
        "to": max(timestamps) if timestamps else "unknown",
        "counts": counts,
    }


def _archive_response(
    archive: Path, kind: str, response: ApiResponse, fetched_at: datetime
) -> Path:
    parsed = urlsplit(response.url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "mw.lojban.org"
        or parsed.path != "/api.php"
    ):
        raise WikiFetchError(f"invalid MediaWiki response origin: {response.url}")
    try:
        document = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WikiFetchError("cannot archive invalid MediaWiki JSON") from exc
    stored = store_object(archive, response.body)
    manifest = ArchiveManifest(
        source="wiki",
        kind=kind,
        origin=response.url,
        fetched_at=fetched_at,
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage=_coverage(document),
        notes="MediaWiki API formatversion=2",
    )
    path = _manifest_path(archive, kind, response.url, stored.sha256)
    if not path.exists():
        manifest.write(path)
    return path


def _known(archive: Path) -> dict[str, tuple[ArchiveManifest, Path]]:
    known: dict[str, tuple[ArchiveManifest, Path]] = {}
    root = archive / "manifests" / "wiki"
    if not root.exists():
        return known
    for path in sorted(root.rglob("*.toml")):
        manifest = ArchiveManifest.load(path)
        previous = known.get(manifest.origin)
        if previous is None or (manifest.fetched_at, manifest.sha256) > (
            previous[0].fetched_at,
            previous[0].sha256,
        ):
            known[manifest.origin] = (manifest, path)
    return known


def _cached(
    archive: Path, known: Mapping[str, tuple[ArchiveManifest, Path]], url: str
) -> ApiResponse | None:
    entry = known.get(url)
    if entry is None:
        return None
    manifest, _path = entry
    obj = object_path(archive, manifest.sha256)
    try:
        body = obj.read_bytes()
    except OSError as exc:
        raise WikiFetchError(f"cached MediaWiki object is unreadable: {obj}") from exc
    if (
        len(body) != manifest.bytes
        or hashlib.sha256(body).hexdigest() != manifest.sha256
    ):
        raise WikiFetchError(f"cached MediaWiki object does not match manifest: {obj}")
    return ApiResponse(url, body, Message())


def _document(response: ApiResponse) -> dict[str, object]:
    document = json.loads(response.body)
    if not isinstance(document, dict):
        raise WikiFetchError("MediaWiki response must be an object")
    return document


def fetch(
    archive: Path,
    since: str | None = None,
    *,
    namespaces: Iterable[int] = NAMESPACES,
    titles: Iterable[str] | None = None,
    retry_titles: Iterable[str] = (),
    max_pages: int | None = None,
    include_logs: bool = True,
    include_media: bool = True,
    client: ResponseClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FetchReport:
    """Fetch site metadata, page histories, and move/delete logs."""

    if since is not None:
        try:
            parsed_since = datetime.fromisoformat(since)
        except ValueError as exc:
            raise WikiFetchError("--since must be an ISO timestamp") from exc
        if parsed_since.tzinfo is None:
            raise WikiFetchError("--since must include a UTC offset")
    if max_pages is not None and max_pages < 1:
        raise WikiFetchError("max_pages must be positive")
    http = client or WikiApiClient()
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise WikiFetchError("fetch time must include a UTC offset")
    known = _known(archive)
    manifests: list[Path] = []
    reused = 0

    def request(
        kind: str, params: dict[str, str], *, refresh: bool = False
    ) -> dict[str, object]:
        nonlocal reused
        url = query_url(params)
        response = None if refresh else _cached(archive, known, url)
        if response is None:
            response = http.query(params)
        else:
            reused += 1
        manifests.append(_archive_response(archive, kind, response, fetched_at))
        return _document(response)

    request(
        "siteinfo",
        {
            "action": "query",
            "meta": "siteinfo",
            "siprop": "statistics|namespaces|namespacealiases",
        },
        refresh=since is not None,
    )

    pages: dict[int, str] = {}
    if titles is None:
        for namespace in namespaces:
            continuation: str | None = None
            while True:
                params = {
                    "action": "query",
                    "list": "allpages",
                    "apnamespace": str(namespace),
                    "aplimit": "max",
                }
                if continuation:
                    params["apcontinue"] = continuation
                document = request("allpages", params, refresh=since is not None)
                query = document.get("query")
                batch = query.get("allpages") if isinstance(query, dict) else None
                if not isinstance(batch, list):
                    raise WikiFetchError("allpages response is missing query.allpages")
                for page in batch:
                    if not isinstance(page, dict):
                        raise WikiFetchError("allpages entry must be an object")
                    pageid = page.get("pageid")
                    title = page.get("title")
                    if not isinstance(pageid, int) or not isinstance(title, str):
                        raise WikiFetchError("allpages entry lacks pageid/title")
                    pages[pageid] = title
                    if max_pages is not None and len(pages) >= max_pages:
                        break
                if max_pages is not None and len(pages) >= max_pages:
                    break
                continued = document.get("continue")
                continuation = (
                    continued.get("apcontinue")
                    if isinstance(continued, dict)
                    and isinstance(continued.get("apcontinue"), str)
                    else None
                )
                if continuation is None:
                    break
            if max_pages is not None and len(pages) >= max_pages:
                break
        selected_titles = list(pages.values())
    else:
        selected_titles = list(titles)
    selected_titles.extend(retry_titles)
    selected_titles = sorted(set(selected_titles))

    media_batches = 0
    if include_media:
        continuation = None
        while True:
            params = {
                "action": "query",
                "list": "allimages",
                "ailimit": "max",
                "aiprop": "timestamp|user|url|size|sha1|mime",
                "aidir": "ascending",
            }
            if since:
                params["aistart"] = since
            if continuation:
                params["aicontinue"] = continuation
            document = request("media", params)
            media_batches += 1
            continued = document.get("continue")
            continuation = (
                continued.get("aicontinue")
                if isinstance(continued, dict)
                and isinstance(continued.get("aicontinue"), str)
                else None
            )
            if continuation is None:
                break

    revision_batches = 0
    for title in selected_titles:
        continuation = None
        while True:
            params = {
                "action": "query",
                "prop": "revisions|info",
                "titles": title,
                "rvprop": "ids|timestamp|user|userid|comment|size|sha1|content|flags",
                "rvslots": "main",
                "rvlimit": "max",
                "rvdir": "newer",
            }
            if since:
                params["rvstart"] = since
            if continuation:
                params["rvcontinue"] = continuation
            document = request("revisions", params)
            revision_batches += 1
            continued = document.get("continue")
            continuation = (
                continued.get("rvcontinue")
                if isinstance(continued, dict)
                and isinstance(continued.get("rvcontinue"), str)
                else None
            )
            if continuation is None:
                break

    log_batches = 0
    for log_type in ("move", "delete") if include_logs else ():
        continuation = None
        while True:
            params = {
                "action": "query",
                "list": "logevents",
                "letype": log_type,
                "leprop": "ids|title|type|user|timestamp|comment|details",
                "lelimit": "max",
                "ledir": "newer",
            }
            if since:
                params["lestart"] = since
            if continuation:
                params["lecontinue"] = continuation
            document = request("logevents", params)
            log_batches += 1
            continued = document.get("continue")
            continuation = (
                continued.get("lecontinue")
                if isinstance(continued, dict)
                and isinstance(continued.get("lecontinue"), str)
                else None
            )
            if continuation is None:
                break
    return FetchReport(
        tuple(manifests),
        len(selected_titles),
        revision_batches,
        log_batches,
        media_batches,
        reused,
    )
