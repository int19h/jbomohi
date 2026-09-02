"""Create and inspect the main-branch corpus worktree."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .git import GitError, git_output, run_git
from .render import commit_root


class CorpusError(RuntimeError):
    """The requested corpus worktree state is unsafe or invalid."""


@dataclass(frozen=True, slots=True)
class CorpusStatus:
    path: Path
    exists: bool
    branch: str | None = None
    head: str | None = None
    commits: int = 0


def corpus_status(path: Path) -> CorpusStatus:
    resolved = path.resolve()
    if not resolved.exists():
        return CorpusStatus(path=resolved, exists=False)
    if not (resolved / ".git").exists():
        raise CorpusError(f"corpus path exists but is not a git worktree: {resolved}")
    branch_result = run_git(
        resolved, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False
    )
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    head_result = run_git(resolved, ["rev-parse", "--verify", "HEAD"], check=False)
    head = head_result.stdout.strip() if head_result.returncode == 0 else None
    commits = int(git_output(resolved, ["rev-list", "--count", "HEAD"])) if head else 0
    return CorpusStatus(
        path=resolved, exists=True, branch=branch, head=head, commits=commits
    )


def _ref_exists(repo_root: Path, ref: str) -> bool:
    return (
        run_git(
            repo_root, ["show-ref", "--verify", "--quiet", ref], check=False
        ).returncode
        == 0
    )


def _common_git_dir(worktree: Path) -> Path:
    value = Path(git_output(worktree, ["rev-parse", "--git-common-dir"]))
    return (value if value.is_absolute() else worktree / value).resolve()


def init_corpus(config: Config) -> tuple[CorpusStatus, bool]:
    """Create the configured corpus worktree, idempotently.

    Existing local ``main`` is checked out unchanged. If only ``origin/main``
    exists, a local tracking branch is created. If neither exists, an unborn
    orphan ``main`` is created and populated with the deterministic root.
    """

    current = corpus_status(config.corpus)
    if current.exists:
        if _common_git_dir(config.corpus) != _common_git_dir(config.repo_root):
            raise CorpusError(
                f"existing corpus is not a worktree of the tools repository: {config.corpus}"
            )
        if current.branch != "main":
            raise CorpusError(
                f"existing corpus worktree is on {current.branch or 'detached HEAD'}, expected main"
            )
        return current, False
    if config.corpus.parent.exists() and config.corpus.is_symlink():
        raise CorpusError(f"refusing symlink corpus path: {config.corpus}")

    local_main = _ref_exists(config.repo_root, "refs/heads/main")
    remote_main = _ref_exists(config.repo_root, "refs/remotes/origin/main")
    if local_main:
        run_git(config.repo_root, ["worktree", "add", str(config.corpus), "main"])
    elif remote_main:
        run_git(
            config.repo_root,
            ["worktree", "add", "-b", "main", str(config.corpus), "origin/main"],
        )
    else:
        run_git(
            config.repo_root,
            ["worktree", "add", "--orphan", "-b", "main", str(config.corpus)],
        )
        try:
            commit_root(config.repo_root, config.corpus)
        except Exception:
            run_git(
                config.repo_root,
                ["worktree", "remove", "--force", str(config.corpus)],
                check=False,
            )
            run_git(config.repo_root, ["branch", "-D", "main"], check=False)
            raise
    status = corpus_status(config.corpus)
    if status.branch != "main":
        raise GitError("corpus init did not produce a main worktree")
    return status, True
