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
        environ={
            "JBOMOHI_CORPUS": "../../projection",
            "JBOMOHI_ARCHIVE": "../../objects",
            "JBOMOHI_TMP": "../../scratch",
        },
    )
    assert config.corpus == (root.parent / "projection").resolve()
    assert config.archive == (root.parent / "objects").resolve()
    assert config.tmp == (root.parent / "scratch").resolve()


def test_default_bulk_paths_live_under_the_home_lojban_directory(
    tmp_path: Path,
) -> None:
    config = Config.from_env(cwd=tmp_path, repo_root=tmp_path, environ={})
    assert config.corpus == Path.home() / "lojban/corpus"
    assert config.archive == Path.home() / "lojban/archive"
    assert config.tmp == Path.home() / "lojban/tmp"


@pytest.mark.parametrize(
    "variable", ("JBOMOHI_CORPUS", "JBOMOHI_ARCHIVE", "JBOMOHI_TMP")
)
@pytest.mark.parametrize("suffix", ("", "bulk"))
def test_bulk_paths_must_be_outside_the_tools_checkout(
    tmp_path: Path, variable: str, suffix: str
) -> None:
    target = tmp_path / suffix if suffix else tmp_path
    with pytest.raises(ConfigError, match="must be outside the tools checkout"):
        Config.from_env(
            cwd=tmp_path,
            repo_root=tmp_path,
            environ={variable: str(target)},
        )
