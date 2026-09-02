from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.archive import (
    ArchiveError,
    ArchiveManifest,
    object_path,
    store_object,
    verify_archive,
)


def write_fixture(corpus: Path, archive: Path, payload: bytes) -> Path:
    digest = hashlib.sha256(payload).hexdigest()
    obj = object_path(archive, digest)
    obj.parent.mkdir(parents=True)
    obj.write_bytes(payload)
    manifests = corpus / "_meta/archive"
    manifests.mkdir(parents=True)
    manifest = manifests / "wiki.toml"
    manifest.write_text(
        'source = "wiki"\n'
        'kind = "mediawiki-export"\n'
        'origin = "https://example.invalid/wiki.xml"\n'
        "fetched_at = 2026-08-27T00:00:00Z\n"
        f'sha256 = "{digest}"\n'
        f"bytes = {len(payload)}\n"
        'notes = "test object"\n'
        'coverage = { from = "2000-01-01", to = "2026-08-27", counts = { revisions = 1 } }\n'
    )
    return manifest


def test_archive_verify_checks_size_and_digest(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    archive = tmp_path / "archive"
    manifest = write_fixture(corpus, archive, b"archived bytes\n")
    assert verify_archive(corpus, archive) == [manifest]


def test_archive_verify_rejects_corruption(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    archive = tmp_path / "archive"
    manifest = write_fixture(corpus, archive, b"first payload")
    digest_line = next(
        line
        for line in manifest.read_text().splitlines()
        if line.startswith("sha256 = ")
    )
    digest = digest_line.split('"')[1]
    object_path(archive, digest).write_bytes(b"other payload")
    with pytest.raises(ArchiveError, match="sha256 mismatch"):
        verify_archive(corpus, archive)


def test_archive_verify_accepts_an_empty_manifest_set(tmp_path: Path) -> None:
    assert verify_archive(tmp_path / "corpus", tmp_path / "archive") == []


def test_store_object_is_content_addressed_immutable_and_idempotent(
    tmp_path: Path,
) -> None:
    first = store_object(tmp_path, b"same bytes")
    second = store_object(tmp_path, b"same bytes")
    assert first == second
    assert first.path.read_bytes() == b"same bytes"
    assert first.path.stat().st_mode & 0o222 == 0


def test_manifest_round_trip_uses_deterministic_toml(tmp_path: Path) -> None:
    obj = store_object(tmp_path / "archive", b"payload")
    manifest = ArchiveManifest(
        source="wiki",
        kind="mediawiki-export",
        origin="https://example.invalid/export",
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
        sha256=obj.sha256,
        bytes=obj.bytes,
        coverage={"from": "2000-01-01", "to": "2026-08-27", "counts": {"revisions": 1}},
        notes="fixture",
    )
    path = tmp_path / "manifest.toml"
    manifest.write(path)
    assert ArchiveManifest.load(path) == manifest
    with pytest.raises(ArchiveError, match="refusing to replace"):
        manifest.write(path)
