"""Ingest sanitized dictionary database exports into the raw archive tier."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from ..project.dictionary import (
    RawDictionaryDump,
    load_dictionary_dump,
    load_jbovlaste_dump,
    validate_integer_shapes,
)
from .manifest import ArchiveError, ArchiveManifest, store_file, store_object

CHANGES_URL = "https://lensisku.lojban.org/api/jbovlaste/changes"
CHANGE_TYPES = "valsi,definition,comment,wiki"
_TRANSIENT_HTTP = {429, 500, 502, 503, 504}


class DictionaryFetchError(ArchiveError):
    """The public Lensisku changes feed failed or returned invalid data."""


@dataclass(frozen=True, slots=True)
class FeedResponse:
    url: str
    body: bytes
    headers: Message


class FeedClient(Protocol):
    def query(self, params: Mapping[str, str]) -> FeedResponse: ...


@dataclass(frozen=True, slots=True)
class DictionaryFetchReport:
    manifests: tuple[Path, ...]
    pages: int
    changes: int
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class DictionaryIngestReport:
    manifests: tuple[Path, ...]
    lensisku: RawDictionaryDump
    jbovlaste: RawDictionaryDump


def _query_url(params: Mapping[str, str]) -> str:
    return CHANGES_URL + "?" + urlencode(sorted(params.items()))


class DictionaryFeedClient:
    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        attempts: int = 4,
        timeout: float = 30.0,
        max_bytes: int = 32 * 1024 * 1024,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_interval < 0 or attempts < 1 or timeout <= 0 or max_bytes < 1:
            raise ValueError("invalid dictionary feed HTTP limits")
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

    def query(self, params: Mapping[str, str]) -> FeedResponse:
        url = _query_url(params)
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            self._pace()
            request = Request(
                url, headers={"User-Agent": "jbomohi/0.1 dictionary archiver"}
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl()
                    parsed = urlsplit(final_url)
                    if (
                        parsed.scheme != "https"
                        or parsed.hostname != "lensisku.lojban.org"
                        or parsed.path != "/api/jbovlaste/changes"
                    ):
                        raise DictionaryFetchError(
                            f"dictionary feed escaped its origin: {final_url}"
                        )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise DictionaryFetchError(
                            f"dictionary feed response exceeds {self.max_bytes} bytes"
                        )
                    return FeedResponse(final_url, body, response.headers)
            except HTTPError as exc:
                last_error = exc
                if exc.code not in _TRANSIENT_HTTP:
                    break
            except (URLError, OSError) as exc:
                last_error = exc
            if attempt + 1 < self.attempts:
                self.sleep(min(2**attempt, 60))
        raise DictionaryFetchError(f"failed to query dictionary feed: {last_error}")


def _feed_document(response: FeedResponse) -> tuple[dict[str, object], list[object]]:
    parsed_url = urlsplit(response.url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "lensisku.lojban.org"
        or parsed_url.path != "/api/jbovlaste/changes"
    ):
        raise DictionaryFetchError(
            f"dictionary feed response escaped its origin: {response.url}"
        )
    try:
        document = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DictionaryFetchError("dictionary feed returned invalid JSON") from exc
    if not isinstance(document, dict):
        raise DictionaryFetchError("dictionary feed response must be an object")
    changes = document.get("changes")
    cursor = document.get("next_cursor")
    if not isinstance(changes, list) or (
        cursor is not None and not isinstance(cursor, str)
    ):
        raise DictionaryFetchError(
            "dictionary feed response has invalid changes/cursor"
        )
    for index, item in enumerate(changes):
        if not isinstance(item, dict):
            raise DictionaryFetchError(
                f"dictionary feed change {index} is not an object"
            )
        change_type = item.get("change_type")
        timestamp = item.get("time")
        if change_type not in {"valsi", "definition", "comment", "wiki"}:
            raise DictionaryFetchError(
                f"dictionary feed change {index} has invalid change_type"
            )
        if (
            not isinstance(timestamp, int)
            or isinstance(timestamp, bool)
            or timestamp < 0
        ):
            raise DictionaryFetchError(
                f"dictionary feed change {index} has invalid time"
            )
    return document, changes


def fetch_changes(
    archive: Path,
    since: str | None = None,
    *,
    max_pages: int | None = None,
    client: FeedClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> DictionaryFetchReport:
    """Archive cursor-paginated public dictionary changes without authentication."""

    if since is not None and (not since or any(char.isspace() for char in since)):
        raise DictionaryFetchError("dictionary feed cursor must be non-empty text")
    if max_pages is not None and max_pages < 1:
        raise DictionaryFetchError("max_pages must be positive")
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise DictionaryFetchError("fetch time must include a UTC offset")
    http = client or DictionaryFeedClient()
    cursor = since
    seen_cursors: set[str] = set()
    manifests: list[Path] = []
    total_changes = 0
    while max_pages is None or len(manifests) < max_pages:
        params = {"limit": "100", "types": CHANGE_TYPES}
        if cursor is not None:
            params["after"] = cursor
        response = http.query(params)
        document, changes = _feed_document(response)
        types = Counter(
            item["change_type"] for item in changes if isinstance(item, dict)
        )
        times = [item["time"] for item in changes if isinstance(item, dict)]
        stored = store_object(archive, response.body)
        manifest = ArchiveManifest(
            source="dict",
            kind="changes-feed",
            origin=response.url,
            fetched_at=fetched_at,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": (
                    datetime.fromtimestamp(min(times), UTC).isoformat()
                    if times
                    else "unknown"
                ),
                "to": (
                    datetime.fromtimestamp(max(times), UTC).isoformat()
                    if times
                    else "unknown"
                ),
                "counts": {"changes": len(changes), **types},
            },
            notes="Unauthenticated Lensisku jbovlaste changes cursor page.",
        )
        request_key = hashlib.sha256(response.url.encode()).hexdigest()[:20]
        path = (
            archive
            / "manifests"
            / "dict"
            / "changes-feed"
            / f"{request_key}-{stored.sha256}.toml"
        )
        if path.exists():
            existing = ArchiveManifest.load(path)
            stable_existing = (
                existing.source,
                existing.kind,
                existing.origin,
                existing.sha256,
                existing.bytes,
                existing.coverage,
                existing.notes,
            )
            stable_new = (
                manifest.source,
                manifest.kind,
                manifest.origin,
                manifest.sha256,
                manifest.bytes,
                manifest.coverage,
                manifest.notes,
            )
            if stable_existing != stable_new:
                raise DictionaryFetchError(
                    f"existing dictionary feed manifest disagrees: {path}"
                )
        else:
            manifest.write(path)
        manifests.append(path)
        total_changes += len(changes)
        next_cursor = document.get("next_cursor")
        if not changes or next_cursor is None:
            cursor = next_cursor if isinstance(next_cursor, str) else None
            break
        assert isinstance(next_cursor, str)
        if not next_cursor or next_cursor == cursor or next_cursor in seen_cursors:
            raise DictionaryFetchError("dictionary feed cursor did not advance")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    return DictionaryFetchReport(
        tuple(manifests), len(manifests), total_changes, cursor
    )


_FILES = (
    "lensisku-schema.sql",
    "lensisku-public-data.sanitized-v3.sql",
    "lensisku-users-public.csv",
    "lensisku-definition-scores.csv",
    "jbovlaste-public.sanitized.sql.gz",
    "jbovlaste-users-public.csv",
    "jbovlaste-definition-scores.csv",
)


def _counts(
    name: str, lensisku: RawDictionaryDump, jbovlaste: RawDictionaryDump
) -> dict[str, int]:
    if name == "lensisku-public-data.sanitized-v3.sql":
        return {table: len(rows) for table, rows in lensisku.tables.items()}
    if name == "lensisku-users-public.csv":
        return {"users": len(lensisku.users)}
    if name == "lensisku-definition-scores.csv":
        return {"definition_scores": len(lensisku.scores)}
    if name == "jbovlaste-public.sanitized.sql.gz":
        return {table: len(rows) for table, rows in jbovlaste.tables.items()}
    if name == "jbovlaste-users-public.csv":
        return {"users": len(jbovlaste.users)}
    if name == "jbovlaste-definition-scores.csv":
        return {"definition_scores": len(jbovlaste.scores)}
    return {"schema_files": 1}


def _notes(name: str) -> str:
    notes = [
        f"Dictionary export component {name}.",
        "Operator supplied an export date only; fetched_at is normalized to midnight UTC.",
    ]
    if name == "lensisku-public-data.sanitized-v3.sql":
        notes.append(
            "Locally sanitized per-user COPY blocks and repaired the single transfer-corrupted "
            "valsi key s44094 plus definition langids l2/h2 to their independently evidenced "
            "integers 44094/2/2. Text fields remain unverifiable."
        )
    elif name == "jbovlaste-public.sanitized.sql.gz":
        notes.append(
            "Locally sanitized by removing the users_view COPY block with votesize."
        )
    elif name == "lensisku-schema.sql":
        notes.append("Schema only; private table definitions contain no rows.")
    return " ".join(notes)


def ingest_dictionary_exports(
    archive: Path, export_directory: Path, export_date: str
) -> DictionaryIngestReport:
    """Validate and archive the exact seven public/diff-only export components."""

    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", export_date):
        raise ArchiveError("dictionary export date must be YYYY-MM-DD")
    try:
        export_day = datetime.fromisoformat(export_date).replace(tzinfo=UTC)
    except ValueError as exc:
        raise ArchiveError("dictionary export date must be YYYY-MM-DD") from exc
    paths = {name: export_directory / name for name in _FILES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ArchiveError(
            f"dictionary export directory is missing: {', '.join(missing)}"
        )

    lensisku = load_dictionary_dump(
        paths["lensisku-public-data.sanitized-v3.sql"],
        paths["lensisku-users-public.csv"],
        paths["lensisku-definition-scores.csv"],
    )
    jbovlaste = load_jbovlaste_dump(
        paths["jbovlaste-public.sanitized.sql.gz"],
        paths["jbovlaste-users-public.csv"],
        paths["jbovlaste-definition-scores.csv"],
    )
    validate_integer_shapes(lensisku)
    validate_integer_shapes(jbovlaste)

    manifests: list[Path] = []
    for name in _FILES:
        stored = store_file(archive, paths[name])
        manifest = ArchiveManifest(
            source="dict",
            kind="db-export",
            origin=f"operator export {export_date}",
            fetched_at=export_day,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": export_date,
                "to": export_date,
                "counts": _counts(name, lensisku, jbovlaste),
            },
            notes=_notes(name),
        )
        manifest_path = (
            archive
            / "manifests"
            / "dict"
            / "db-export"
            / f"{name}-{stored.sha256[:12]}.toml"
        )
        if manifest_path.exists():
            if ArchiveManifest.load(manifest_path) != manifest:
                raise ArchiveError(
                    f"existing dictionary manifest disagrees: {manifest_path}"
                )
        else:
            manifest.write(manifest_path)
        manifests.append(manifest_path)
    return DictionaryIngestReport(tuple(manifests), lensisku, jbovlaste)
