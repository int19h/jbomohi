from __future__ import annotations

from pathlib import Path

import pytest

from jbomohi_tools.config import Config, ConfigError


def test_paths_resolve_from_environment(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    work = root / "nested"
    work.mkdir()
    config = Config.from_env(
        cwd=work,
        repo_root=root,
        environ={"JBOMOHI_CORPUS": "../projection", "JBOMOHI_ARCHIVE": "../objects"},
    )
    assert config.corpus == (root / "projection").resolve()
    assert config.archive == (root / "objects").resolve()


def test_tools_checkout_cannot_be_a_writable_target(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="must not be the tools checkout"):
        Config.from_env(
            cwd=tmp_path,
            repo_root=tmp_path,
            environ={"JBOMOHI_CORPUS": str(tmp_path)},
        )
