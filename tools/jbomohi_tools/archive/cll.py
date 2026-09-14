"""Bare-mirror acquisition for the Complete Lojban Language sources."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..git import git_output, run_git
from .manifest import ArchiveError, ArchiveManifest, store_object

CLL_URL = "https://github.com/int19h/cll"
GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")
FROZEN_REFS: Mapping[str, str] = {
    "8048799de97b9826aa3c79346ac20f56b813b8e6": (
        "8048799de97b9826aa3c79346ac20f56b813b8e6"
    ),
    "dabe61540baa54f13c02ae098a2f78c3a66f7e4e": (
        "dabe61540baa54f13c02ae098a2f78c3a66f7e4e"
    ),
    "refs/tags/v1.1-2016-08-26-html": ("6c0556c7b17f96b3bf41e8123ba18ef4868e056a"),
    "refs/tags/v1.1-2018-05-21-html": ("5bda273e3740dea489b2b9ccb3e4d0f116dc01aa"),
    "refs/tags/v1.1-2019-11-14-html": ("efb2d7e47e6461278d634d9609f8b2cd14a7c9d2"),
}
DYNAMIC_TAGS = (
    re.compile(r"^refs/tags/geklojban-1\.2\.[0-9]+$"),
    re.compile(r"^refs/tags/v1\.3\.[0-9]+$"),
)


class CllFetchError(ArchiveError):
    """The CLL mirror could not be acquired without ambiguity."""


@dataclass(frozen=True, slots=True)
class CllFetchReport:
    mirror: Path
    manifest: Path
    refs: Mapping[str, str]
    reused_manifest: bool


def _peel(mirror: Path, ref: str) -> str:
    result = run_git(
        mirror,
        ["rev-parse", "--verify", f"{ref}^{{commit}}"],
        check=False,
    )
    object_id = result.stdout.strip()
    if result.returncode != 0 or not GIT_OBJECT_ID.fullmatch(object_id):
        raise CllFetchError(f"CLL mirror lacks commit ref {ref!r}")
    return object_id


def _commit_date(mirror: Path, object_id: str) -> datetime:
    raw = git_output(mirror, ["show", "-s", "--format=%cI", object_id])
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CllFetchError(
            f"CLL commit has invalid committer date: {object_id}"
        ) from exc
    if value.tzinfo is None or value.microsecond:
        raise CllFetchError(f"CLL commit has invalid committer date: {object_id}")
    return value


def fetch(
    archive: Path,
    *,
    url: str = CLL_URL,
    frozen_refs: Mapping[str, str] = FROZEN_REFS,
    dynamic_tags: Sequence[re.Pattern[str]] = DYNAMIC_TAGS,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CllFetchReport:
    """Clone or refresh the bare fork mirror and archive its scoped ref state."""

    mirror = archive / "git" / "cll.git"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    if mirror.is_symlink():
        raise CllFetchError(f"CLL mirror must not be a symlink: {mirror}")
    if mirror.exists():
        if (
            not mirror.is_dir()
            or git_output(mirror, ["rev-parse", "--is-bare-repository"]) != "true"
        ):
            raise CllFetchError(f"CLL mirror is not a bare repository: {mirror}")
        if git_output(mirror, ["remote", "get-url", "origin"]) != url:
            raise CllFetchError("CLL mirror origin does not match the configured fork")
        run_git(mirror, ["remote", "update", "--prune"])
    else:
        run_git(mirror.parent, ["clone", "--mirror", url, str(mirror)])

    tag_refs = git_output(
        mirror, ["for-each-ref", "--format=%(refname)", "refs/tags"]
    ).splitlines()
    selected = set(frozen_refs)
    for pattern in dynamic_tags:
        matches = {ref for ref in tag_refs if pattern.fullmatch(ref)}
        if not matches:
            raise CllFetchError(
                f"CLL mirror has no scoped tag matching {pattern.pattern!r}"
            )
        selected.update(matches)

    refs: dict[str, str] = {}
    for ref in sorted(selected):
        object_id = _peel(mirror, ref)
        expected = frozen_refs.get(ref)
        if expected is not None and object_id != expected:
            raise CllFetchError(
                f"frozen CLL ref {ref!r} peeled to {object_id}, expected {expected}"
            )
        refs[ref] = object_id
    history_root = archive / "manifests" / "cll" / "git-mirror"
    for previous_path in sorted(history_root.glob("*.toml")):
        previous = ArchiveManifest.load(previous_path)
        if (
            previous.source != "cll"
            or previous.kind != "git-mirror"
            or previous.origin != url
        ):
            continue
        previous_refs = previous.coverage.get("refs")
        if not isinstance(previous_refs, dict):
            raise CllFetchError(
                f"prior CLL manifest has no scoped refs: {previous_path}"
            )
        for ref, previous_object_id in previous_refs.items():
            if refs.get(ref) != previous_object_id:
                raise CllFetchError(f"CLL scoped ref was removed or rewritten: {ref!r}")
    dates = [_commit_date(mirror, object_id) for object_id in refs.values()]
    payload = (
        json.dumps(
            {"origin": url, "refs": refs},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    stored = store_object(archive, payload)
    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise CllFetchError("CLL fetch time must include a UTC offset")
    manifest = ArchiveManifest(
        source="cll",
        kind="git-mirror",
        origin=url,
        fetched_at=fetched_at,
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage={
            "from": min(dates).isoformat(timespec="seconds"),
            "to": max(dates).isoformat(timespec="seconds"),
            "counts": {"editions": len(refs)},
            "refs": refs,
        },
        notes=(
            "Canonical scoped-ref record for the bare CLL fork mirror at "
            "archive/git/cll.git; the mirror itself is verified by the projector."
        ),
    )
    path = archive / "manifests" / "cll" / "git-mirror" / f"refs-{stored.sha256}.toml"
    reused = path.exists()
    if reused:
        existing = ArchiveManifest.load(path)
        if (
            existing.source != manifest.source
            or existing.kind != manifest.kind
            or existing.origin != manifest.origin
            or existing.sha256 != manifest.sha256
            or existing.bytes != manifest.bytes
            or existing.coverage != manifest.coverage
            or existing.notes != manifest.notes
        ):
            raise CllFetchError(f"existing CLL manifest disagrees with mirror: {path}")
    else:
        manifest.write(path)
    return CllFetchReport(mirror, path, refs, reused)
