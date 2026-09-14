"""Read and verify immutable archive objects from tracked manifests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ArchiveError(RuntimeError):
    """An archive manifest or object failed validation."""


def _manifest_text(path: Path, label: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(char in value for char in "\r\n\0")
    ):
        raise ArchiveError(f"manifest {path} has invalid {label}")
    return value


def _validate_coverage(path: Path, value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArchiveError(f"manifest {path} has invalid coverage")
    missing = {"from", "to", "counts"} - value.keys()
    if missing:
        raise ArchiveError(
            f"manifest {path} coverage is missing: {', '.join(sorted(missing))}"
        )
    start = _manifest_text(path, "coverage.from", value["from"])
    end = _manifest_text(path, "coverage.to", value["to"])
    counts = value["counts"]
    if not isinstance(counts, dict) or not counts:
        raise ArchiveError(f"manifest {path} has invalid coverage.counts")
    clean_counts: dict[str, int] = {}
    for key, count in counts.items():
        clean_key = _manifest_text(path, "coverage count name", key)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ArchiveError(
                f"manifest {path} has invalid coverage count {clean_key!r}"
            )
        clean_counts[clean_key] = count
    return {"from": start, "to": end, "counts": clean_counts}


@dataclass(frozen=True, slots=True)
class ArchiveManifest:
    source: str
    kind: str
    origin: str
    fetched_at: object
    sha256: str
    bytes: int
    coverage: Mapping[str, Any]
    notes: str

    @classmethod
    def load(cls, path: Path) -> ArchiveManifest:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise ArchiveError(f"cannot read manifest {path}: {exc}") from exc
        required = {
            "source",
            "kind",
            "origin",
            "fetched_at",
            "sha256",
            "bytes",
            "coverage",
            "notes",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise ArchiveError(f"manifest {path} is missing: {', '.join(missing)}")
        source = _manifest_text(path, "source", data["source"])
        kind = _manifest_text(path, "kind", data["kind"])
        origin = _manifest_text(path, "origin", data["origin"])
        fetched_at = data["fetched_at"]
        if not isinstance(fetched_at, datetime) or fetched_at.tzinfo is None:
            raise ArchiveError(f"manifest {path} has invalid fetched_at")
        digest = data["sha256"]
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ArchiveError(f"manifest {path} has an invalid sha256")
        size = data["bytes"]
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ArchiveError(f"manifest {path} has invalid bytes")
        coverage = _validate_coverage(path, data["coverage"])
        notes = data["notes"]
        if not isinstance(notes, str) or "\0" in notes:
            raise ArchiveError(f"manifest {path} has invalid notes")
        return cls(
            source=source,
            kind=kind,
            origin=origin,
            fetched_at=fetched_at,
            sha256=digest,
            bytes=size,
            coverage=coverage,
            notes=notes,
        )

    def to_toml(self) -> str:
        if not isinstance(self.fetched_at, datetime) or self.fetched_at.tzinfo is None:
            raise ArchiveError("manifest fetched_at must be a timezone-aware datetime")
        coverage = _validate_coverage(Path("<new manifest>"), self.coverage)
        source = _manifest_text(Path("<new manifest>"), "source", self.source)
        kind = _manifest_text(Path("<new manifest>"), "kind", self.kind)
        origin = _manifest_text(Path("<new manifest>"), "origin", self.origin)
        if not SHA256.fullmatch(self.sha256):
            raise ArchiveError("manifest has an invalid sha256")
        if (
            not isinstance(self.bytes, int)
            or isinstance(self.bytes, bool)
            or self.bytes < 0
        ):
            raise ArchiveError("manifest has invalid bytes")
        if not isinstance(self.notes, str) or "\0" in self.notes:
            raise ArchiveError("manifest has invalid notes")
        quote = lambda value: json.dumps(value, ensure_ascii=False)
        lines = [
            f"source = {quote(source)}",
            f"kind = {quote(kind)}",
            f"origin = {quote(origin)}",
            f"fetched_at = {self.fetched_at.isoformat(timespec='seconds')}",
            f'sha256 = "{self.sha256}"',
            f"bytes = {self.bytes}",
            f"notes = {quote(self.notes)}",
            "",
            "[coverage]",
            f"from = {quote(coverage['from'])}",
            f"to = {quote(coverage['to'])}",
            "",
            "[coverage.counts]",
        ]
        lines.extend(
            f"{quote(name)} = {count}"
            for name, count in sorted(coverage["counts"].items())
        )
        return "\n".join(lines) + "\n"

    def write(self, path: Path) -> None:
        if path.exists():
            raise ArchiveError(f"refusing to replace archive manifest: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(self.to_toml())
        except OSError as exc:
            raise ArchiveError(f"cannot write manifest {path}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class ArchiveObject:
    path: Path
    sha256: str
    bytes: int


def object_path(archive: Path, digest: str) -> Path:
    if not SHA256.fullmatch(digest):
        raise ArchiveError(f"invalid object digest: {digest!r}")
    return archive / "objects" / "sha256" / digest[:2] / digest[2:]


def store_object(archive: Path, payload: bytes) -> ArchiveObject:
    """Store bytes once under their digest, refusing mutable collisions."""

    digest = hashlib.sha256(payload).hexdigest()
    path = object_path(archive, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != payload:
            raise ArchiveError(f"archive object collision at {path}")
    except OSError as exc:
        if created:
            path.unlink(missing_ok=True)
        raise ArchiveError(f"cannot store archive object {path}: {exc}") from exc
    return ArchiveObject(path=path, sha256=digest, bytes=len(payload))


def _file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise ArchiveError(f"cannot read archive object {path}: {exc}") from exc
    return digest.hexdigest(), size


def store_file(archive: Path, source: Path) -> ArchiveObject:
    """Stream a regular file into the immutable content-addressed archive."""

    try:
        source_stat = source.lstat()
    except OSError as exc:
        raise ArchiveError(f"cannot inspect archive input {source}: {exc}") from exc
    if not stat.S_ISREG(source_stat.st_mode):
        raise ArchiveError(f"archive input must be a regular file: {source}")

    incoming = archive / "objects" / ".incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="ingest-", dir=incoming)
    temporary = Path(temporary_name)
    digest = hashlib.sha256()
    size = 0
    try:
        with (
            source.open("rb") as input_stream,
            os.fdopen(descriptor, "wb") as output_stream,
        ):
            while chunk := input_stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                output_stream.write(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        hexadecimal = digest.hexdigest()
        destination = object_path(archive, hexadecimal)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(temporary, destination)
            destination.chmod(0o444)
        except FileExistsError:
            actual_digest, actual_size = _file_digest(destination)
            if (actual_digest, actual_size) != (hexadecimal, size):
                raise ArchiveError(f"archive object collision at {destination}")
        return ArchiveObject(path=destination, sha256=hexadecimal, bytes=size)
    except OSError as exc:
        raise ArchiveError(f"cannot store archive input {source}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def verify_manifests(manifest_root: Path, archive: Path) -> list[Path]:
    """Verify every manifest below an explicit archive-manifest root."""

    if not manifest_root.exists():
        return []
    verified: list[Path] = []
    for path in sorted(manifest_root.rglob("*.toml")):
        if path.is_symlink():
            raise ArchiveError(f"archive manifest must not be a symlink: {path}")
        manifest = ArchiveManifest.load(path)
        obj = object_path(archive, manifest.sha256)
        if obj.is_symlink():
            raise ArchiveError(f"archive object must not be a symlink: {obj}")
        try:
            actual_size = obj.stat().st_size
        except OSError as exc:
            raise ArchiveError(f"archive object missing for {path}: {obj}") from exc
        if actual_size != manifest.bytes:
            raise ArchiveError(
                f"archive object size mismatch for {path}: expected {manifest.bytes}, got {actual_size}"
            )
        digest = hashlib.sha256()
        try:
            with obj.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise ArchiveError(f"cannot read archive object {obj}: {exc}") from exc
        if digest.hexdigest() != manifest.sha256:
            raise ArchiveError(f"archive object sha256 mismatch for {path}")
        verified.append(path)
    return verified


def verify_archive(corpus: Path, archive: Path) -> list[Path]:
    return verify_manifests(corpus / "_meta" / "archive", archive)
