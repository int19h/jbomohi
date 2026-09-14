from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.archive.mail import (
    MailFetchError,
    extract_maildir_zip,
    fetch_maildir_zip,
    inspect_maildir_zip,
)
from jbomohi_tools.archive.manifest import ArchiveManifest, object_path


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return stream.getvalue()


def test_maildir_zip_inventory_and_safe_extraction(tmp_path: Path) -> None:
    archive = tmp_path / "maildir.zip"
    archive.write_bytes(
        zip_bytes(
            {
                "maildir/cur/1.example:2,S": b"From: a@example.org\r\n\r\nbody",
                "maildir/new/2.example": b"From: b@example.org\r\n\r\nbody",
                "maildir/tmp/.keep": b"",
            }
        )
    )
    inventory = inspect_maildir_zip(archive)
    assert (inventory.cur, inventory.new, inventory.messages) == (1, 1, 2)
    destination = tmp_path / "out"
    assert extract_maildir_zip(archive, destination) == inventory
    assert (destination / "maildir/cur/1.example:2,S").is_file()


def test_maildir_zip_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    archive.write_bytes(zip_bytes({"../escape": b"bad"}))
    with pytest.raises(MailFetchError, match="unsafe maildir zip member"):
        inspect_maildir_zip(archive)


def test_fetch_maildir_zip_writes_verified_manifest(tmp_path: Path) -> None:
    payload = zip_bytes(
        {"maildir/cur/1.example:2,S": b"From: a@example.org\r\n\r\nbody"}
    )

    class Client:
        def download(self, url: str, destination) -> None:
            assert url.endswith("/lojban-list.maildir.zip")
            destination.write(payload)

    report = fetch_maildir_zip(
        tmp_path,
        "lojban-list",
        client=Client(),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    manifest = ArchiveManifest.load(report.manifest)
    assert manifest.kind == "maildir-zip"
    assert manifest.coverage["counts"]["messages"] == 1
    assert object_path(tmp_path, manifest.sha256).is_file()
