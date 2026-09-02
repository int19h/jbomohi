from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.git import Event, EventError, GitError, Identity, commit_event


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def unborn_worktree(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    return repo


def base_event(**changes: object) -> Event:
    fields: dict[str, object] = {
        "source": "wiki",
        "source_id": "revid=1",
        "event": "created",
        "time_confidence": "exact",
        "source_time": datetime(2004, 1, 2, 3, 4, 5, tzinfo=UTC),
        "summary": "create Test (rev 1)",
        "author": Identity.namespaced("mw.lojban.org", "test user"),
        "changes": {"wiki/main/Test.wiki": "first\n"},
        "trailers": {"Page-Id": "7"},
    }
    fields.update(changes)
    return Event(**fields)  # type: ignore[arg-type]


def test_commit_event_sets_source_identity_date_message_and_tree(
    tmp_path: Path,
) -> None:
    corpus = unborn_worktree(tmp_path)
    commit = commit_event(corpus, base_event())
    assert commit == git(corpus, "rev-parse", "HEAD")
    assert (corpus / "wiki/main/Test.wiki").read_text() == "first\n"
    assert git(corpus, "status", "--porcelain") == ""
    metadata = git(corpus, "show", "-s", "--format=%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B")
    lines = metadata.splitlines()
    assert lines[:6] == [
        "test user",
        "test%20user@mw.lojban.org",
        "2004-01-02T03:04:05Z",
        "test user",
        "test%20user@mw.lojban.org",
        "2004-01-02T03:04:05Z",
    ]
    assert "wiki: create Test (rev 1)" in metadata
    assert "Source: wiki" in metadata
    assert "Source-Id: revid=1" in metadata
    assert "Event: created" in metadata
    assert "Time-Confidence: exact" in metadata
    assert "Page-Id: 7" in metadata


def test_pre_epoch_event_clamps_git_date_and_keeps_source_date(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    event = base_event(
        source="llg",
        source_id="llg=paper-1960",
        event="import",
        time_confidence="pre-epoch",
        source_time=datetime(1960, 5, 1, tzinfo=UTC),
        source_date="1960-05-01",
        summary="import paper-1960",
        author=Identity.tool(),
        changes={"llg/paper.txt": "historical text\n"},
    )
    commit_event(corpus, event)
    assert git(corpus, "show", "-s", "--format=%aI") == "1970-01-01T00:00:00Z"
    assert "Source-Date: 1960-05-01" in git(corpus, "show", "-s", "--format=%B")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"summary": "x" * 80}, "maximum is 72"),
        ({"source_time": datetime(2000, 1, 1)}, "UTC offset"),  # noqa: DTZ001
        (
            {"source_time": datetime(2000, 1, 1, 0, 0, 0, 1, tzinfo=UTC)},
            "whole-second precision",
        ),
        ({"time_confidence": "window"}, "require Event-Window"),
        ({"changes": {"../escape": "bad"}}, "unsafe corpus path"),
        ({"trailers": {"Source": "other"}}, "reserved event trailer"),
    ],
)
def test_invalid_events_are_rejected(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    corpus = unborn_worktree(tmp_path)
    with pytest.raises(EventError, match=message):
        commit_event(corpus, base_event(**change))


def test_commit_refuses_to_absorb_unrelated_worktree_changes(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    (corpus / "unrelated.txt").write_text("human work\n")
    with pytest.raises(GitError, match="not clean"):
        commit_event(corpus, base_event())


def test_identity_constructor_enforces_the_namespace_email() -> None:
    with pytest.raises(EventError, match="namespaced identity email"):
        Identity("user", "user@wrong.invalid", "mw.lojban.org")


def test_commit_refuses_to_traverse_a_tracked_symlink(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    outside = tmp_path / "outside"
    (corpus / "wiki").symlink_to(outside, target_is_directory=True)
    git(corpus, "add", "wiki")
    git(
        corpus,
        "-c",
        "user.name=fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "fixture symlink",
    )
    with pytest.raises(EventError, match="refusing to traverse symlink"):
        commit_event(corpus, base_event())
    assert not outside.exists()
