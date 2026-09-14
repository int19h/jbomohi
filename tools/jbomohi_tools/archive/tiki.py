"""Ingest the sanitized Tiki export into the raw archive tier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..project.tiki import (
    CharacterEncoding,
    RawTikiDump,
    TikiUsers,
    load_tiki_dump,
    load_tiki_users,
    project,
)
from .manifest import ArchiveError, ArchiveManifest, store_file


@dataclass(frozen=True, slots=True)
class TikiIngestReport:
    manifests: tuple[Path, ...]
    data: RawTikiDump
    users: TikiUsers
    events: int


_FILES = (
    "tiki-content.sanitized.sql.gz",
    "tiki-users.tsv.gz",
    "tiki-user-preferences.tsv.gz",
)


def ingest_tiki_export(
    archive: Path,
    export_directory: Path,
    export_date: str,
    *,
    character_encoding: CharacterEncoding = "latin1-transcoded",
) -> TikiIngestReport:
    """Validate, project, and archive the three sanitized Tiki components."""

    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", export_date):
        raise ArchiveError("Tiki export date must be YYYY-MM-DD")
    try:
        export_day = datetime.fromisoformat(export_date).replace(tzinfo=UTC)
    except ValueError as exc:
        raise ArchiveError("Tiki export date must be YYYY-MM-DD") from exc
    paths = {name: export_directory / name for name in _FILES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ArchiveError(f"Tiki export directory is missing: {', '.join(missing)}")

    data = load_tiki_dump(paths["tiki-content.sanitized.sql.gz"])
    users = load_tiki_users(
        paths["tiki-users.tsv.gz"],
        paths["tiki-user-preferences.tsv.gz"],
        character_encoding=character_encoding,
    )
    events = sum(
        1 for _event in project(data, users, character_encoding=character_encoding)
    )

    counts = {
        "tiki-content.sanitized.sql.gz": {
            table: len(rows) for table, rows in data.tables.items()
        },
        "tiki-users.tsv.gz": {"users": len(users.logins)},
        "tiki-user-preferences.tsv.gz": {
            "public_display_names": len(users.display_names)
        },
    }
    manifests: list[Path] = []
    for name in _FILES:
        stored = store_file(archive, paths[name])
        notes = [
            f"Tiki export component {name}.",
            "Operator supplied an export date only; fetched_at is normalized to midnight UTC.",
        ]
        if name == "tiki-content.sanitized.sql.gz":
            notes.append(
                "Locally sanitized by removing all tiki_forums INSERT rows; this latin1-client "
                "export is projected with explicit byte-preserving fidelity caveats."
            )
        manifest = ArchiveManifest(
            source="tiki",
            kind="db-export",
            origin=f"operator export {export_date}",
            fetched_at=export_day,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": export_date,
                "to": export_date,
                "counts": counts[name],
            },
            notes=" ".join(notes),
        )
        path = (
            archive
            / "manifests"
            / "tiki"
            / "db-export"
            / f"{name}-{stored.sha256[:12]}.toml"
        )
        if path.exists():
            if ArchiveManifest.load(path) != manifest:
                raise ArchiveError(f"existing Tiki manifest disagrees: {path}")
        else:
            manifest.write(path)
        manifests.append(path)
    return TikiIngestReport(tuple(manifests), data, users, events)
