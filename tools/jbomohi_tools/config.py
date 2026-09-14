"""Runtime configuration resolved from the environment."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Configuration could not be resolved safely."""


def _repo_root(cwd: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "not inside a git worktree"
        raise ConfigError(f"cannot locate the tools checkout: {detail}")
    return Path(result.stdout.strip()).resolve()


def _configured_path(value: str | None, default: Path, cwd: Path) -> Path:
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def _require_outside_checkout(path: Path, root: Path, variable: str) -> None:
    if path == root or root in path.parents:
        raise ConfigError(f"{variable} must be outside the tools checkout")


@dataclass(frozen=True, slots=True)
class Config:
    """Paths used by commands that are allowed to write local state."""

    repo_root: Path
    corpus: Path
    archive: Path
    tmp: Path

    @classmethod
    def from_env(
        cls,
        *,
        cwd: Path | None = None,
        environ: Mapping[str, str] | None = None,
        repo_root: Path | None = None,
    ) -> Config:
        current = (cwd or Path.cwd()).resolve()
        env = os.environ if environ is None else environ
        root = repo_root.resolve() if repo_root else _repo_root(current)
        local_root = Path.home() / "lojban"
        corpus = _configured_path(
            env.get("JBOMOHI_CORPUS"), local_root / "corpus", current
        )
        archive = _configured_path(
            env.get("JBOMOHI_ARCHIVE"), local_root / "archive", current
        )
        temporary = _configured_path(
            env.get("JBOMOHI_TMP"), local_root / "tmp", current
        )
        _require_outside_checkout(corpus, root, "JBOMOHI_CORPUS")
        _require_outside_checkout(archive, root, "JBOMOHI_ARCHIVE")
        _require_outside_checkout(temporary, root, "JBOMOHI_TMP")
        return cls(repo_root=root, corpus=corpus, archive=archive, tmp=temporary)
