from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jbomohi_tools.archive.cll import CllFetchError, fetch
from jbomohi_tools.archive.manifest import ArchiveManifest, object_path


def git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit(source: Path, text: str, timestamp: str) -> str:
    (source / "chapter.xml").write_text(text)
    git(source, "add", "chapter.xml")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": timestamp,
    }
    subprocess.run(
        ["git", "commit", "-m", text],
        cwd=source,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return git(source, "rev-parse", "HEAD")


def source_repo(tmp_path: Path) -> tuple[Path, str, str]:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "--initial-branch=main")
    first = commit(source, "first\n", "2016-08-26T00:00:00+00:00")
    git(source, "tag", "v1.1-test")
    second = commit(source, "second\n", "2020-01-02T00:00:00+00:00")
    git(source, "tag", "geklojban-1.2.1")
    git(source, "tag", "v1.3.2")
    return source, first, second


def test_fetch_cll_mirrors_scoped_refs_and_archives_the_ref_record(
    tmp_path: Path,
) -> None:
    source, first, second = source_repo(tmp_path)
    archive = tmp_path / "archive"
    patterns = (
        re.compile(r"^refs/tags/geklojban-1\.2\.[0-9]+$"),
        re.compile(r"^refs/tags/v1\.3\.[0-9]+$"),
    )
    report = fetch(
        archive,
        url=str(source.resolve()),
        frozen_refs={"refs/tags/v1.1-test": first},
        dynamic_tags=patterns,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert report.refs == {
        "refs/tags/geklojban-1.2.1": second,
        "refs/tags/v1.1-test": first,
        "refs/tags/v1.3.2": second,
    }
    assert git(report.mirror, "rev-parse", "--is-bare-repository") == "true"
    manifest = ArchiveManifest.load(report.manifest)
    assert manifest.kind == "git-mirror"
    assert manifest.coverage["refs"] == report.refs
    payload = json.loads(object_path(archive, manifest.sha256).read_text())
    assert payload == {"origin": str(source.resolve()), "refs": report.refs}

    repeated = fetch(
        archive,
        url=str(source.resolve()),
        frozen_refs={"refs/tags/v1.1-test": first},
        dynamic_tags=patterns,
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert repeated.manifest == report.manifest
    assert repeated.reused_manifest

    third = commit(source, "third\n", "2026-01-02T00:00:00+00:00")
    git(source, "tag", "v1.3.3")
    updated = fetch(
        archive,
        url=str(source.resolve()),
        frozen_refs={"refs/tags/v1.1-test": first},
        dynamic_tags=patterns,
        now=lambda: datetime(2026, 9, 16, tzinfo=UTC),
    )
    assert updated.refs["refs/tags/v1.3.3"] == third
    assert updated.manifest != report.manifest
    assert not updated.reused_manifest


def test_fetch_cll_rejects_a_changed_frozen_ref(tmp_path: Path) -> None:
    source, _first, second = source_repo(tmp_path)
    with pytest.raises(CllFetchError, match="frozen CLL ref"):
        fetch(
            tmp_path / "archive",
            url=str(source.resolve()),
            frozen_refs={"refs/tags/v1.1-test": second},
            dynamic_tags=(),
        )


def test_fetch_cll_rejects_a_rewritten_dynamic_tag(tmp_path: Path) -> None:
    source, first, _second = source_repo(tmp_path)
    archive = tmp_path / "archive"
    pattern = (re.compile(r"^refs/tags/geklojban-1\.2\.[0-9]+$"),)
    fetch(
        archive,
        url=str(source.resolve()),
        frozen_refs={},
        dynamic_tags=pattern,
    )
    git(source, "tag", "--force", "geklojban-1.2.1", first)
    with pytest.raises(CllFetchError, match="removed or rewritten"):
        fetch(
            archive,
            url=str(source.resolve()),
            frozen_refs={},
            dynamic_tags=pattern,
        )


def test_fetch_cll_rejects_an_existing_mirror_with_another_origin(
    tmp_path: Path,
) -> None:
    source, first, _second = source_repo(tmp_path)
    archive = tmp_path / "archive"
    fetch(
        archive,
        url=str(source.resolve()),
        frozen_refs={"refs/tags/v1.1-test": first},
        dynamic_tags=(),
    )
    with pytest.raises(CllFetchError, match="origin does not match"):
        fetch(
            archive,
            url=str(tmp_path / "other"),
            frozen_refs={"refs/tags/v1.1-test": first},
            dynamic_tags=(),
        )
