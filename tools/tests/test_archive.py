from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.archive import (
    ArchiveError,
    ArchiveManifest,
    object_path,
    store_file,
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


def test_archive_verify_rejects_a_size_mismatch(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    archive = tmp_path / "archive"
    manifest = write_fixture(corpus, archive, b"first payload")
    digest_line = next(
        line
        for line in manifest.read_text().splitlines()
        if line.startswith("sha256 = ")
    )
    digest = digest_line.split('"')[1]
    object_path(archive, digest).write_bytes(b"different length")
    with pytest.raises(ArchiveError, match="size mismatch"):
        verify_archive(corpus, archive)


def test_archive_verify_rejects_a_missing_object(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    archive = tmp_path / "archive"
    manifest = write_fixture(corpus, archive, b"payload")
    digest_line = next(
        line
        for line in manifest.read_text().splitlines()
        if line.startswith("sha256 = ")
    )
    digest = digest_line.split('"')[1]
    object_path(archive, digest).unlink()
    with pytest.raises(ArchiveError, match="object missing"):
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


def test_store_file_streams_content_and_reuses_the_same_object(tmp_path: Path) -> None:
    source = tmp_path / "large.sql"
    source.write_bytes((b"COPY data\n" * 200_000) + b"\\.\n")
    first = store_file(tmp_path / "archive", source)
    second = store_file(tmp_path / "archive", source)
    assert first == second
    assert first.bytes == source.stat().st_size
    assert first.path.read_bytes() == source.read_bytes()
    assert first.path.stat().st_mode & 0o222 == 0


def test_store_file_rejects_symlink_inputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"payload")
    link = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(ArchiveError, match="regular file"):
        store_file(tmp_path / "archive", link)


def test_manifest_round_trip_uses_deterministic_toml(tmp_path: Path) -> None:
    obj = store_object(tmp_path / "archive", b"payload")
    manifest = ArchiveManifest(
        source="wiki",
        kind="mediawiki-export",
        origin="https://example.invalid/export",
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
        sha256=obj.sha256,
        bytes=obj.bytes,
        coverage={
            "from": "2000-01-01",
            "to": "2026-08-27",
            "counts": {"revisions": 1},
            "refs": {"refs/tags/example": "a" * 40},
        },
        notes="fixture",
    )
    path = tmp_path / "manifest.toml"
    manifest.write(path)
    assert ArchiveManifest.load(path) == manifest
    assert '[coverage.refs]\n"refs/tags/example" = ' in path.read_text()
    with pytest.raises(ArchiveError, match="refusing to replace"):
        manifest.write(path)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing-key", "is missing: notes"),
        ("bad-sha", "invalid sha256"),
        ("naive-fetched-at", "invalid fetched_at"),
        ("negative-bytes", "invalid bytes"),
    ],
)
def test_manifest_load_rejects_invalid_fields(
    tmp_path: Path, case: str, message: str
) -> None:
    corpus = tmp_path / "corpus"
    archive = tmp_path / "archive"
    manifest = write_fixture(corpus, archive, b"payload")
    text = manifest.read_text()
    if case == "missing-key":
        text = text.replace('notes = "test object"\n', "")
    elif case == "bad-sha":
        digest_line = next(
            line for line in text.splitlines() if line.startswith("sha256 = ")
        )
        text = text.replace(digest_line, 'sha256 = "bad"')
    elif case == "naive-fetched-at":
        text = text.replace("2026-08-27T00:00:00Z", "2026-08-27T00:00:00")
    elif case == "negative-bytes":
        text = text.replace("bytes = 7", "bytes = -1")
    manifest.write_text(text)
    with pytest.raises(ArchiveError, match=message):
        ArchiveManifest.load(manifest)
