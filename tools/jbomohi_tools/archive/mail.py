"""Bounded acquisition and extraction for public Maildir zip archives."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .manifest import ArchiveError, ArchiveManifest, store_file

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


class DownloadClient(Protocol):
    def download(self, url: str, destination: BinaryIO) -> None: ...


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
    return any(
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
