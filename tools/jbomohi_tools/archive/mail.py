"""Bounded acquisition and extraction for public Maildir zip archives."""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import shutil
import stat
import tempfile
import time
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from ..project.mail import (
    MailManifestation,
    RawMessage,
    load_mh_zip,
    mbox_manifestations,
    numbered_rfc822,
    parse_mail,
    reconstruct_mhonarc,
)
from .manifest import (
    ArchiveError,
    ArchiveManifest,
    object_path,
    store_file,
    store_object,
)

MAIL_HOST = "mail.lojban.org"
MAILDIR_LISTS = (
    "lojban-list",
    "lojban-beginners",
    "bpfk",
    "jbovlaste",
    "lojban-de",
    "lojban-es",
    "lojban-fr",
    "lbck",
    "lojban-announcements",
    "wikichanges",
    "wikidiscuss",
    "wikineurotic",
)
MHONARC_LISTS = (
    "announce",
    "bpfk-announce",
    "dracyselkei",
    "jbofongri",
    "jboske",
    "jbosnu",
    "lojban_story",
    "pod",
)
_TRANSIENT_HTTP = {429, 500, 502, 503, 504}
_MAX_ZIP_BYTES = 1024 * 1024 * 1024
_MAX_MEMBERS = 250_000
_MAX_MEMBER_BYTES = 32 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 6 * 1024 * 1024 * 1024


class MailFetchError(ArchiveError):
    """A public mail archive could not be acquired or validated safely."""


@dataclass(frozen=True, slots=True)
class MaildirZipInventory:
    cur: int
    new: int
    message_bytes: int

    @property
    def messages(self) -> int:
        return self.cur + self.new


@dataclass(frozen=True, slots=True)
class MailFetchReport:
    manifest: Path
    inventory: MaildirZipInventory


@dataclass(frozen=True, slots=True)
class MhonarcFetchReport:
    manifests: tuple[Path, ...]
    downloaded: int
    reused: int
    next_missing: int | None


@dataclass(frozen=True, slots=True)
class MhFetchReport:
    manifest: Path
    messages: int


@dataclass(frozen=True, slots=True)
class NumberedFetchReport:
    manifests: tuple[Path, ...]
    downloaded: int
    reused: int
    next_missing: int | None


@dataclass(frozen=True, slots=True)
class MboxFetchReport:
    manifests: tuple[Path, ...]
    downloaded: int
    reused: int
    messages: int


class DownloadClient(Protocol):
    def download(self, url: str, destination: BinaryIO) -> None: ...


class PageClient(Protocol):
    def get(self, url: str) -> bytes | None: ...


def maildir_zip_url(list_name: str) -> str:
    if list_name not in MAILDIR_LISTS:
        raise MailFetchError(f"unsupported lists-plain list: {list_name!r}")
    return f"https://{MAIL_HOST}/lists-plain/{list_name}/{list_name}.maildir.zip"


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != MAIL_HOST:
        raise MailFetchError(f"mail archive URL escaped its origin: {url}")
    if not re_fullmatch_mail_path(parsed.path):
        raise MailFetchError(f"mail archive URL has an unexpected path: {url}")


def re_fullmatch_mail_path(path: str) -> bool:
    return path == "/lists/jbosnu_raw.zip" or any(
        path == f"/lists-plain/{name}/{name}.maildir.zip" for name in MAILDIR_LISTS
    )


class MailHttpClient:
    def __init__(
        self,
        *,
        attempts: int = 4,
        timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1 or timeout <= 0:
            raise ValueError("invalid mail HTTP client limits")
        self.attempts = attempts
        self.timeout = timeout
        self.sleep = sleep

    def download(self, url: str, destination: BinaryIO) -> None:
        _validate_url(url)
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                request = Request(
                    url, headers={"User-Agent": "jbomohi/0.1 mail archiver"}
                )
                with urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl()
                    _validate_url(final_url)
                    destination.seek(0)
                    destination.truncate()
                    size = 0
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > _MAX_ZIP_BYTES:
                            raise MailFetchError(
                                f"mail archive exceeds {_MAX_ZIP_BYTES} bytes"
                            )
                        destination.write(chunk)
                    destination.flush()
                    os.fsync(destination.fileno())
                    return
            except HTTPError as exc:
                last_error = exc
                if exc.code not in _TRANSIENT_HTTP:
                    break
            except (URLError, OSError) as exc:
                last_error = exc
            if attempt + 1 < self.attempts:
                self.sleep(min(2**attempt, 60))
        raise MailFetchError(f"failed to download mail archive: {last_error}")


class MhonarcHttpClient:
    def __init__(
        self,
        *,
        min_interval: float = 0.5,
        attempts: int = 4,
        timeout: float = 30.0,
        max_bytes: int = 8 * 1024 * 1024,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_interval < 0 or attempts < 1 or timeout <= 0 or max_bytes < 1:
            raise ValueError("invalid MHonArc HTTP client limits")
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

    def get(self, url: str) -> bytes | None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != MAIL_HOST
            or not any(
                parsed.path.startswith(f"/lists/{name}/msg")
                and parsed.path.endswith(".html")
                for name in MHONARC_LISTS
            )
        ):
            raise MailFetchError(f"invalid MHonArc URL: {url}")
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            self._pace()
            request = Request(url, headers={"User-Agent": "jbomohi/0.1 mail archiver"})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    if response.geturl() != url:
                        raise MailFetchError(
                            f"MHonArc response escaped its exact URL: {response.geturl()}"
                        )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise MailFetchError(
                            f"MHonArc response exceeds {self.max_bytes} bytes"
                        )
                    return body
            except HTTPError as exc:
                if exc.code == 404:
                    return None
                last_error = exc
                if exc.code not in _TRANSIENT_HTTP:
                    break
            except (URLError, OSError) as exc:
                last_error = exc
            if attempt + 1 < self.attempts:
                self.sleep(min(2**attempt, 60))
        raise MailFetchError(f"failed to fetch MHonArc page: {last_error}")


class NumberedRawHttpClient:
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
            raise ValueError("invalid numbered-mail HTTP client limits")
        self.min_interval = min_interval
        self.attempts = attempts
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request: float | None = None

    def get(self, url: str) -> bytes | None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != MAIL_HOST
            or not re.fullmatch(r"/lists/old_lojban-list/[1-9][0-9]*", parsed.path)
        ):
            raise MailFetchError(f"invalid numbered raw-mail URL: {url}")
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            now = self.monotonic()
            if self._last_request is not None:
                delay = self.min_interval - (now - self._last_request)
                if delay > 0:
                    self.sleep(delay)
            self._last_request = self.monotonic()
            try:
                request = Request(
                    url, headers={"User-Agent": "jbomohi/0.1 mail archiver"}
                )
                with urlopen(request, timeout=self.timeout) as response:
                    if response.geturl() != url:
                        raise MailFetchError(
                            f"numbered raw-mail response escaped its URL: {response.geturl()}"
                        )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise MailFetchError(
                            f"numbered raw-mail response exceeds {self.max_bytes} bytes"
                        )
                    return body
            except HTTPError as exc:
                if exc.code == 404:
                    return None
                last_error = exc
                if exc.code not in _TRANSIENT_HTTP:
                    break
            except (URLError, OSError) as exc:
                last_error = exc
            if attempt + 1 < self.attempts:
                self.sleep(min(2**attempt, 60))
        raise MailFetchError(f"failed to fetch numbered raw mail: {last_error}")


class FilesHttpClient:
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
            raise ValueError("invalid files-mail HTTP client limits")
        self.min_interval = min_interval
        self.attempts = attempts
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request: float | None = None

    def get(self, url: str) -> bytes | None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "www.lojban.org"
            or not (
                parsed.path == "/files/lojban-list/"
                or re.fullmatch(r"/files/lojban-list/lojban-[0-9]{4}\.gz", parsed.path)
            )
        ):
            raise MailFetchError(f"invalid files-mail URL: {url}")
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            now = self.monotonic()
            if self._last_request is not None:
                delay = self.min_interval - (now - self._last_request)
                if delay > 0:
                    self.sleep(delay)
            self._last_request = self.monotonic()
            try:
                request = Request(
                    url, headers={"User-Agent": "jbomohi/0.1 mail archiver"}
                )
                with urlopen(request, timeout=self.timeout) as response:
                    if response.geturl() != url:
                        raise MailFetchError(
                            f"files-mail response escaped its URL: {response.geturl()}"
                        )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise MailFetchError(
                            f"files-mail response exceeds {self.max_bytes} bytes"
                        )
                    return body
            except HTTPError as exc:
                if exc.code == 404:
                    return None
                last_error = exc
                if exc.code not in _TRANSIENT_HTTP:
                    break
            except (URLError, OSError) as exc:
                last_error = exc
            if attempt + 1 < self.attempts:
                self.sleep(min(2**attempt, 60))
        raise MailFetchError(f"failed to fetch files mail archive: {last_error}")


def _member_path(info: zipfile.ZipInfo) -> PurePosixPath:
    path = PurePosixPath(info.filename)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in info.filename
    ):
        raise MailFetchError(f"unsafe maildir zip member: {info.filename!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise MailFetchError(f"maildir zip member is a symlink: {info.filename!r}")
    return path


def inspect_maildir_zip(path: Path) -> MaildirZipInventory:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > _MAX_MEMBERS:
                raise MailFetchError(
                    f"maildir zip has {len(infos)} members; maximum is {_MAX_MEMBERS}"
                )
            cur = 0
            new = 0
            total = 0
            for info in infos:
                member = _member_path(info)
                if info.is_dir():
                    continue
                if info.flag_bits & 0x1:
                    raise MailFetchError(
                        f"maildir zip member is encrypted: {info.filename!r}"
                    )
                if info.file_size > _MAX_MEMBER_BYTES:
                    raise MailFetchError(
                        f"maildir zip member exceeds {_MAX_MEMBER_BYTES} bytes: "
                        f"{info.filename!r}"
                    )
                total += info.file_size
                if total > _MAX_UNCOMPRESSED_BYTES:
                    raise MailFetchError("maildir zip uncompressed size exceeds limit")
                if len(member.parts) != 3 or member.parts[0] != "maildir":
                    raise MailFetchError(
                        f"maildir zip has unexpected file: {info.filename!r}"
                    )
                if member.parts[1] == "cur":
                    cur += 1
                elif member.parts[1] == "new":
                    new += 1
                elif member.parts[1] != "tmp":
                    raise MailFetchError(
                        f"maildir zip has unexpected directory: {info.filename!r}"
                    )
            if cur + new == 0:
                raise MailFetchError("maildir zip contains no messages")
            return MaildirZipInventory(cur, new, total)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise MailFetchError(f"cannot inspect maildir zip {path}: {exc}") from exc


def extract_maildir_zip(path: Path, destination: Path) -> MaildirZipInventory:
    inventory = inspect_maildir_zip(path)
    if destination.exists() and any(destination.iterdir()):
        raise MailFetchError(
            f"maildir extraction destination is not empty: {destination}"
        )
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                member = _member_path(info)
                target = destination.joinpath(*member.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise MailFetchError(f"cannot extract maildir zip {path}: {exc}") from exc
    return inventory


def fetch_maildir_zip(
    archive: Path,
    list_name: str,
    *,
    client: DownloadClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MailFetchReport:
    """Download, validate, and content-address one public lists-plain zip."""

    url = maildir_zip_url(list_name)
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise MailFetchError("mail fetch time must include a UTC offset")
    temporary_dir = archive / "objects" / ".incoming"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix="maildir-", suffix=".zip", dir=temporary_dir
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w+b") as output:
            (client or MailHttpClient()).download(url, output)
        inventory = inspect_maildir_zip(temporary)
        stored = store_file(archive, temporary)
        manifest = ArchiveManifest(
            source=f"mail/{list_name}",
            kind="maildir-zip",
            origin=url,
            fetched_at=fetched_at,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": "unknown",
                "to": "unknown",
                "counts": {
                    "messages": inventory.messages,
                    "cur": inventory.cur,
                    "new": inventory.new,
                    "message_bytes": inventory.message_bytes,
                },
            },
            notes="Public lists-plain Maildir zip; raw RFC 822 messages.",
        )
        request_key = hashlib.sha256(url.encode()).hexdigest()[:20]
        path = (
            archive
            / "manifests"
            / "mail"
            / list_name
            / "maildir-zip"
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
                raise MailFetchError(f"existing mail manifest disagrees: {path}")
        else:
            manifest.write(path)
        return MailFetchReport(path, inventory)
    finally:
        temporary.unlink(missing_ok=True)


def _known_mhonarc(archive: Path, list_name: str) -> dict[int, Path]:
    known: dict[int, Path] = {}
    root = archive / "manifests" / "mail" / list_name / "mhonarc"
    if not root.exists():
        return known
    for path in sorted(root.glob("msg*.toml")):
        matched = re.match(r"msg([0-9]{5})-", path.name)
        if matched:
            known[int(matched.group(1))] = path
    return known


def fetch_mhonarc(
    archive: Path,
    list_name: str,
    *,
    max_pages: int | None = None,
    client: PageClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MhonarcFetchReport:
    """Crawl dense MHonArc message numbers until the first HTTP 404."""

    if list_name not in MHONARC_LISTS:
        raise MailFetchError(f"unsupported MHonArc-only list: {list_name!r}")
    if max_pages is not None and max_pages < 1:
        raise MailFetchError("max_pages must be positive")
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise MailFetchError("MHonArc fetch time must include a UTC offset")
    http = client or MhonarcHttpClient()
    known = _known_mhonarc(archive, list_name)
    manifests: list[Path] = []
    downloaded = 0
    reused = 0
    index = 0
    while max_pages is None or len(manifests) < max_pages:
        url = f"https://{MAIL_HOST}/lists/{list_name}/msg{index:05d}.html"
        existing_path = known.get(index)
        if existing_path is not None:
            existing = ArchiveManifest.load(existing_path)
            obj = object_path(archive, existing.sha256)
            if not obj.is_file() or obj.stat().st_size != existing.bytes:
                raise MailFetchError(
                    f"cached MHonArc object is missing or wrong-sized: {obj}"
                )
            reconstruct_mhonarc(obj.read_bytes())
            manifests.append(existing_path)
            reused += 1
            index += 1
            continue
        body = http.get(url)
        if body is None:
            return MhonarcFetchReport(tuple(manifests), downloaded, reused, index)
        reconstruct_mhonarc(body)
        stored = store_object(archive, body)
        manifest = ArchiveManifest(
            source=f"mail/{list_name}",
            kind="mhonarc-page",
            origin=url,
            fetched_at=fetched_at,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": "unknown",
                "to": "unknown",
                "counts": {"messages": 1},
            },
            notes="Public MHonArc message page; reconstructed RFC 822 is derived evidence.",
        )
        path = (
            archive
            / "manifests"
            / "mail"
            / list_name
            / "mhonarc"
            / f"msg{index:05d}-{stored.sha256}.toml"
        )
        manifest.write(path)
        manifests.append(path)
        downloaded += 1
        index += 1
    return MhonarcFetchReport(tuple(manifests), downloaded, reused, None)


def fetch_jbosnu_raw(
    archive: Path,
    *,
    client: DownloadClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MhFetchReport:
    """Download and archive the public raw jbosnu MH-folder zip."""

    url = f"https://{MAIL_HOST}/lists/jbosnu_raw.zip"
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise MailFetchError("mail fetch time must include a UTC offset")
    temporary_dir = archive / "objects" / ".incoming"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix="jbosnu-", suffix=".zip", dir=temporary_dir
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w+b") as output:
            (client or MailHttpClient()).download(url, output)
        messages = sum(1 for _item in load_mh_zip(temporary))
        stored = store_file(archive, temporary)
        manifest = ArchiveManifest(
            source="mail/jbosnu",
            kind="mh-folder-zip",
            origin=url,
            fetched_at=fetched_at,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": "unknown",
                "to": "unknown",
                "counts": {"messages": messages},
            },
            notes="Public raw jbosnu MH folder; raw RFC 822 messages.",
        )
        path = (
            archive
            / "manifests"
            / "mail"
            / "jbosnu"
            / "mh-folder-zip"
            / f"{stored.sha256}.toml"
        )
        if path.exists():
            existing = ArchiveManifest.load(path)
            if (
                existing.source,
                existing.kind,
                existing.origin,
                existing.sha256,
                existing.bytes,
                existing.coverage,
                existing.notes,
            ) != (
                manifest.source,
                manifest.kind,
                manifest.origin,
                manifest.sha256,
                manifest.bytes,
                manifest.coverage,
                manifest.notes,
            ):
                raise MailFetchError(f"existing jbosnu manifest disagrees: {path}")
        else:
            manifest.write(path)
        return MhFetchReport(path, messages)
    finally:
        temporary.unlink(missing_ok=True)


def load_mhonarc_manifestations(
    archive: Path, list_name: str
) -> Iterator[MailManifestation]:
    """Load reconstructed RFC 822 manifestations from archived MHonArc pages."""

    known = _known_mhonarc(archive, list_name)
    for index, path in sorted(known.items()):
        manifest = ArchiveManifest.load(path)
        if manifest.source != f"mail/{list_name}" or manifest.kind != "mhonarc-page":
            raise MailFetchError(f"unexpected MHonArc manifest identity: {path}")
        obj = object_path(archive, manifest.sha256)
        if not obj.is_file() or obj.stat().st_size != manifest.bytes:
            raise MailFetchError(f"MHonArc object missing or wrong-sized: {obj}")
        yield MailManifestation(
            list_name=list_name,
            raw=RawMessage(payload=reconstruct_mhonarc(obj.read_bytes())),
            manifestation="mhonarc",
            provenance=manifest.origin,
            archive_order=index,
            archive_time=manifest.fetched_at,
        )


def _known_numbered(archive: Path) -> dict[int, Path]:
    known: dict[int, Path] = {}
    root = archive / "manifests" / "mail" / "lojban-list" / "old-lojban-list"
    if not root.exists():
        return known
    for path in sorted(root.glob("msg*.toml")):
        matched = re.match(r"msg([0-9]{5})-", path.name)
        if matched:
            known[int(matched.group(1))] = path
    return known


def fetch_old_lojban_list(
    archive: Path,
    *,
    max_pages: int | None = None,
    client: PageClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> NumberedFetchReport:
    """Fetch numbered raw old_lojban-list messages from 1 through first 404."""

    if max_pages is not None and max_pages < 1:
        raise MailFetchError("max_pages must be positive")
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise MailFetchError("mail fetch time must include a UTC offset")
    http = client or NumberedRawHttpClient()
    known = _known_numbered(archive)
    manifests: list[Path] = []
    downloaded = 0
    reused = 0
    index = 1
    while max_pages is None or len(manifests) < max_pages:
        url = f"https://{MAIL_HOST}/lists/old_lojban-list/{index}"
        existing_path = known.get(index)
        if existing_path is not None:
            manifest = ArchiveManifest.load(existing_path)
            obj = object_path(archive, manifest.sha256)
            if not obj.is_file() or obj.stat().st_size != manifest.bytes:
                raise MailFetchError(f"numbered raw-mail object missing: {obj}")
            raw = obj.read_bytes()
            reused += 1
            path = existing_path
        else:
            raw = http.get(url)
            if raw is None:
                return NumberedFetchReport(tuple(manifests), downloaded, reused, index)
            parsed_source = MailManifestation(
                list_name="lojban-list",
                raw=RawMessage(payload=numbered_rfc822(raw)),
                manifestation="old-lojban-list",
                provenance=url,
                archive_order=index,
                archive_time=fetched_at,
            )
            parse_mail(parsed_source)
            stored = store_object(archive, raw)
            manifest = ArchiveManifest(
                source="mail/lojban-list",
                kind="numbered-rfc822",
                origin=url,
                fetched_at=fetched_at,
                sha256=stored.sha256,
                bytes=stored.bytes,
                coverage={
                    "from": "unknown",
                    "to": "unknown",
                    "counts": {"messages": 1},
                },
                notes="Public old_lojban-list numbered raw RFC 822 with mbox envelope.",
            )
            path = (
                archive
                / "manifests"
                / "mail"
                / "lojban-list"
                / "old-lojban-list"
                / f"msg{index:05d}-{stored.sha256}.toml"
            )
            manifest.write(path)
            downloaded += 1
        manifests.append(path)
        index += 1
    return NumberedFetchReport(tuple(manifests), downloaded, reused, None)


def load_old_lojban_manifestations(archive: Path) -> Iterator[MailManifestation]:
    """Load archived old_lojban-list numbered raw messages for deduplication."""

    for index, path in sorted(_known_numbered(archive).items()):
        manifest = ArchiveManifest.load(path)
        obj = object_path(archive, manifest.sha256)
        if not obj.is_file() or obj.stat().st_size != manifest.bytes:
            raise MailFetchError(f"numbered raw-mail object missing: {obj}")
        yield MailManifestation(
            list_name="lojban-list",
            raw=RawMessage(payload=numbered_rfc822(obj.read_bytes())),
            manifestation="old-lojban-list",
            provenance=manifest.origin,
            archive_order=index,
            archive_time=manifest.fetched_at,
        )


def _known_mboxes(archive: Path) -> dict[str, Path]:
    known: dict[str, Path] = {}
    root = archive / "manifests" / "mail" / "lojban-list" / "files-mbox"
    if not root.exists():
        return known
    for path in sorted(root.glob("lojban-*.toml")):
        matched = re.match(r"(lojban-[0-9]{4}\.gz)-", path.name)
        if matched:
            known[matched.group(1)] = path
    return known


def fetch_mail_mboxes(
    archive: Path,
    *,
    client: PageClient | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> MboxFetchReport:
    """Discover and archive the native gzip-compressed 1990s mboxes."""

    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise MailFetchError("mail fetch time must include a UTC offset")
    http = client or FilesHttpClient()
    index_url = "https://www.lojban.org/files/lojban-list/"
    index = http.get(index_url)
    if index is None:
        raise MailFetchError("files-mail directory listing returned 404")
    names = sorted(
        {
            matched.decode("ascii")
            for matched in re.findall(rb'href="(lojban-[0-9]{4}\.gz)"', index)
        }
    )
    if not names:
        raise MailFetchError("files-mail directory lists no native mbox gzip files")
    known = _known_mboxes(archive)
    manifests: list[Path] = []
    downloaded = 0
    reused = 0
    total_messages = 0
    for name in names:
        url = index_url + name
        existing_path = known.get(name)
        if existing_path is not None:
            manifest = ArchiveManifest.load(existing_path)
            obj = object_path(archive, manifest.sha256)
            if not obj.is_file() or obj.stat().st_size != manifest.bytes:
                raise MailFetchError(f"mbox gzip object missing: {obj}")
            compressed = obj.read_bytes()
            reused += 1
            path = existing_path
        else:
            compressed = http.get(url)
            if compressed is None:
                raise MailFetchError(f"files-mail listed object returned 404: {url}")
        try:
            raw = gzip.decompress(compressed)
        except (OSError, EOFError) as exc:
            raise MailFetchError(f"invalid gzip mbox {name}: {exc}") from exc
        messages = list(
            mbox_manifestations(
                raw,
                list_name="lojban-list",
                provenance_prefix=url,
            )
        )
        for message in messages:
            parse_mail(message)
        total_messages += len(messages)
        if existing_path is not None and manifest.coverage["counts"].get(
            "messages"
        ) != len(messages):
            raise MailFetchError(
                f"archived mbox message count disagrees after validation: {existing_path}"
            )
        if existing_path is None:
            stored = store_object(archive, compressed)
            manifest = ArchiveManifest(
                source="mail/lojban-list",
                kind="mbox-gzip",
                origin=url,
                fetched_at=fetched_at,
                sha256=stored.sha256,
                bytes=stored.bytes,
                coverage={
                    "from": "unknown",
                    "to": "unknown",
                    "counts": {"messages": len(messages)},
                },
                notes="Public native gzip-compressed lojban-list mbox.",
            )
            path = (
                archive
                / "manifests"
                / "mail"
                / "lojban-list"
                / "files-mbox"
                / f"{name}-{stored.sha256}.toml"
            )
            manifest.write(path)
            downloaded += 1
        manifests.append(path)
    return MboxFetchReport(tuple(manifests), downloaded, reused, total_messages)


def load_mbox_manifestations(archive: Path) -> Iterator[MailManifestation]:
    """Load all archived native 1990s mboxes in filename/message order."""

    order = 0
    for name, path in sorted(_known_mboxes(archive).items()):
        manifest = ArchiveManifest.load(path)
        obj = object_path(archive, manifest.sha256)
        if not obj.is_file() or obj.stat().st_size != manifest.bytes:
            raise MailFetchError(f"mbox gzip object missing: {obj}")
        try:
            raw = gzip.decompress(obj.read_bytes())
        except (OSError, EOFError) as exc:
            raise MailFetchError(f"invalid archived gzip mbox {name}: {exc}") from exc
        for manifestation in mbox_manifestations(
            raw, list_name="lojban-list", provenance_prefix=manifest.origin
        ):
            yield MailManifestation(
                list_name=manifestation.list_name,
                raw=manifestation.raw,
                manifestation=manifestation.manifestation,
                provenance=manifestation.provenance,
                archive_order=order,
                archive_time=manifest.fetched_at,
            )
            order += 1
