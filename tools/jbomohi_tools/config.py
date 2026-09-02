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


@dataclass(frozen=True, slots=True)
class Config:
    """Paths used by commands that are allowed to write local state."""

    repo_root: Path
    corpus: Path
    archive: Path

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
        corpus = _configured_path(env.get("JBOMOHI_CORPUS"), root / "corpus", current)
        archive = _configured_path(
            env.get("JBOMOHI_ARCHIVE"), Path.home() / "lojban" / "archive", current
        )
        if corpus == root:
            raise ConfigError("JBOMOHI_CORPUS must not be the tools checkout")
        if archive == root:
            raise ConfigError("JBOMOHI_ARCHIVE must not be the tools checkout")
        return cls(repo_root=root, corpus=corpus, archive=archive)
