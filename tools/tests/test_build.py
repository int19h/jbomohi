from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.build import (
    build_corpus,
    push_main_ranges,
    update_corpus,
    verify_corpus,
)
from jbomohi_tools.config import Config
from jbomohi_tools.corpus import CorpusError
from jbomohi_tools.git import Event, Identity

HERE = Path(__file__).resolve()
WORKSPACE = HERE.parents[2]
TEMPLATES = WORKSPACE / "tools/templates/main"


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


def tools_repo(path: Path) -> tuple[Config, str]:
    path.mkdir()
    git(path, "init", "--initial-branch=tools")
    shutil.copytree(TEMPLATES, path / "tools/templates/main")
    (path / ".gitignore").write_text("corpus/\narchive/\n")
    (path / "README.md").write_text("tools\n")
    git(path, "add", ".")
    env = {
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    }
    run(path, "git", "commit", "-m", "tools", env=env)
    commit = git(path, "rev-parse", "HEAD")
    return Config(path, path / "corpus", path / "archive"), commit


def event(identifier: str, second: int, path: str) -> Event:
    return Event(
        source="wiki",
        source_id=identifier,
        event="created",
        time_confidence="exact",
        source_time=datetime(2000, 1, 1, 0, 0, second, tzinfo=UTC),
        summary=identifier,
        author=Identity.namespaced("mw.lojban.org", "tester"),
        changes={path: identifier + "\n"},
        trailers={"Page-Id": identifier.removeprefix("rev=")},
    )


def test_build_is_transactional_chronological_and_deterministic(tmp_path: Path) -> None:
    config, tools_commit = tools_repo(tmp_path / "repo")
    (config.archive / "manifests/wiki").mkdir(parents=True)
    (config.archive / "manifests/wiki/source.toml").write_text('source = "fixture"\n')
    sources = {
        "late": lambda: iter((event("rev=2", 2, "wiki/main/Two.wiki"),)),
        "early": lambda: iter((event("rev=1", 1, "wiki/main/One.wiki"),)),
    }
    first = build_corpus(config, sources)
    assert first.events == 2
    assert first.commits == 4
    assert first.snapshot == "snapshot/20000101T000002Z"
    messages = git(config.corpus, "log", "--reverse", "--format=%s").splitlines()
    assert messages[1:3] == ["wiki: rev=1", "wiki: rev=2"]
    assert git(config.corpus, "rev-parse", "HEAD") == first.head
    assert tools_commit in (config.corpus / "_meta/schema.toml").read_text()
    assert (config.corpus / "_meta/archive/wiki/source.toml").is_file()
    assert git(config.repo_root, "rev-parse", f"{first.snapshot}^{{}}") == first.head

    second = build_corpus(config, sources)
    assert second.head == first.head
    assert verify_corpus(config.corpus).commits == 4


def test_build_ignores_hostile_global_git_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    sources = {"one": lambda: iter((event("rev=1", 1, "wiki/main/One.wiki"),))}
    expected = build_corpus(config, sources).head
    hostile = tmp_path / "hostile.gitconfig"
    hostile.write_text(
        "[core]\n\tautocrlf = true\n\tsafecrlf = true\n\thooksPath = /nonexistent\n"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile))
    assert build_corpus(config, sources).head == expected


def test_build_rejects_dirty_tools_before_replacing_main(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    original = build_corpus(config, {}).head
    (config.repo_root / "dirty.txt").write_text("uncommitted\n")
    with pytest.raises(CorpusError, match="tools worktree is dirty"):
        build_corpus(config, {})
    assert git(config.corpus, "rev-parse", "HEAD") == original


def test_failed_scratch_projection_leaves_existing_main_unchanged(
    tmp_path: Path,
) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    original = build_corpus(
        config,
        {"wiki": lambda: iter((event("rev=1", 1, "wiki/main/One.wiki"),))},
    ).head

    def failing():
        yield event("rev=2", 2, "wiki/main/Two.wiki")
        raise RuntimeError("projector failed")

    with pytest.raises(RuntimeError, match="projector failed"):
        build_corpus(config, {"wiki": failing})
    assert git(config.corpus, "rev-parse", "HEAD") == original


def test_update_appends_only_new_source_ids_and_refreshes(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    first_event = event("rev=1", 1, "wiki/main/One.wiki")
    build_corpus(config, {"wiki": lambda: iter((first_event,))})
    before = int(git(config.corpus, "rev-list", "--count", "HEAD"))
    second_event = event("rev=2", 2, "wiki/main/Two.wiki")
    report = update_corpus(
        config,
        {"wiki": lambda: iter((first_event, second_event))},
    )
    assert report is not None
    assert report.events == 1
    assert int(git(config.corpus, "rev-list", "--count", "HEAD")) == before + 2
    assert (
        update_corpus(config, {"wiki": lambda: iter((first_event, second_event))})
        is None
    )


def test_push_main_uses_commit_ranges_then_snapshot_tag(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(config.repo_root, "remote", "add", "origin", str(remote))
    events = tuple(
        event(f"rev={number}", number, f"wiki/main/{number}.wiki")
        for number in range(1, 6)
    )
    report = build_corpus(config, {"wiki": lambda: iter(events)})
    pushed = push_main_ranges(config.repo_root, report.snapshot, commits_per_push=2)
    assert pushed.main_updates == 4
    assert git(remote, "rev-parse", "refs/heads/main") == report.head
    assert git(remote, "rev-parse", f"refs/tags/{report.snapshot}^{{}}") == report.head
