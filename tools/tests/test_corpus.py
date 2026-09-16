from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jbomohi_tools.config import Config
from jbomohi_tools.corpus import CorpusError, corpus_status, init_corpus
from jbomohi_tools.render import RenderContext, commit_instruction_refresh

HERE = Path(__file__).resolve()
WORKSPACE = HERE.parents[2]
TEMPLATES = WORKSPACE / "tools" / "templates" / "main"


def run(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    actual_env = dict(os.environ)
    if env:
        actual_env.update(env)
    result = subprocess.run(
        list(args), cwd=cwd, env=actual_env, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def git(cwd: Path, *args: str) -> str:
    return run(cwd, "git", *args)


def seed_tools_repo(path: Path) -> str:
    path.mkdir()
    git(path, "init", "--initial-branch=tools")
    shutil.copytree(TEMPLATES, path / "tools/templates/main")
    (path / "README.md").write_text("seed tools checkout\n")
    git(path, "add", ".")
    env = {
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    }
    run(path, "git", "commit", "-m", "seed", env=env)
    return git(path, "rev-parse", "HEAD")


def clone_and_init(seed: Path, clone: Path) -> tuple[Config, str]:
    run(seed.parent, "git", "clone", "--branch", "tools", str(seed), str(clone))
    config = Config(repo_root=clone, corpus=clone / "corpus", archive=clone / "archive")
    status, created = init_corpus(config)
    assert created
    assert status.branch == "main"
    assert status.commits == 1
    assert status.head
    return config, status.head


def test_clean_clone_gets_one_rendered_epoch_root(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    tools_commit = seed_tools_repo(seed)
    config, head = clone_and_init(seed, tmp_path / "clone")

    status = corpus_status(config.corpus)
    assert status == corpus_status(config.corpus)
    assert status.head == head
    assert git(config.corpus, "rev-list", "--count", "HEAD") == "1"
    assert git(config.corpus, "show", "-s", "--format=%aI") == "1970-01-01T00:00:00Z"
    assert git(config.corpus, "show", "-s", "--format=%cI") == "1970-01-01T00:00:00Z"
    assert (
        git(config.corpus, "show", "-s", "--format=%an <%ae>")
        == "jbomohi <tools@jbomohi.invalid>"
    )
    message = git(config.corpus, "show", "-s", "--format=%B")
    assert "Source: meta" in message
    assert "Source-Id: root" in message
    assert "Event: refresh" in message
    assert "Time-Confidence: exact" in message

    files = set(git(config.corpus, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    assert files == {
        ".agents/rules/jbomohi.md",
        ".gitignore",
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        "README.md",
        "_meta/schema.toml",
    }
    readme = (config.corpus / "README.md").read_text()
    assert "{{" not in readme
    assert tools_commit in readme
    assert (
        f'tools_commit = "{tools_commit}"'
        in (config.corpus / "_meta/schema.toml").read_text()
    )


def test_root_commit_is_deterministic_across_two_clean_clones(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed_tools_repo(seed)
    _first_config, first = clone_and_init(seed, tmp_path / "clone-one")
    _second_config, second = clone_and_init(seed, tmp_path / "clone-two")
    assert first == second


def test_corpus_init_is_idempotent(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed_tools_repo(seed)
    config, head = clone_and_init(seed, tmp_path / "clone")
    status, created = init_corpus(config)
    assert not created
    assert status.head == head
    assert status.commits == 1


def test_corpus_init_rejects_an_unrelated_main_repository(tmp_path: Path) -> None:
    tools = tmp_path / "tools-repo"
    seed_tools_repo(tools)
    unrelated = tmp_path / "corpus"
    unrelated.mkdir()
    git(unrelated, "init", "--initial-branch=main")
    config = Config(repo_root=tools, corpus=unrelated, archive=tmp_path / "archive")
    with pytest.raises(CorpusError, match="not a worktree of the tools repository"):
        init_corpus(config)


def test_instruction_refresh_is_one_source_event(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    tools_commit = seed_tools_repo(seed)
    config, root = clone_and_init(seed, tmp_path / "clone")
    event_time = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
    context = RenderContext(
        snapshot="snapshot/20200102T030405Z",
        tools_commit=tools_commit,
        coverage_tables="Wiki: 10 revisions.",
    )
    refreshed = commit_instruction_refresh(
        config.repo_root,
        config.corpus,
        source_time=event_time,
        source_id="refresh@20200102T030405Z",
        context=context,
    )
    assert refreshed != root
    assert git(config.corpus, "rev-list", "--count", "HEAD") == "2"
    assert git(config.corpus, "show", "-s", "--format=%aI") == "2020-01-02T03:04:05Z"
    message = git(config.corpus, "show", "-s", "--format=%B")
    assert "Event: refresh" in message
    assert "Source-Id: refresh@20200102T030405Z" in message
    assert "Wiki: 10 revisions." in (config.corpus / "README.md").read_text()
