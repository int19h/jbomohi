"""Transactional build, update, snapshot, and verification orchestration."""

from __future__ import annotations

import csv
import heapq
import re
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import Config
from .corpus import CorpusError, corpus_status, init_corpus
from .git import EPOCH, Event, GitError, Identity, commit_event, git_output, run_git
from .render import RenderContext, commit_instruction_refresh, commit_root

EventFactory = Callable[[], Iterable[Event]]
_TRAILER = re.compile(r"^([A-Z][A-Za-z0-9-]*): (.*)$")
_MAX_CORPUS_FILE = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class BuildReport:
    head: str
    commits: int
    events: int
    snapshot: str
    coverage: str


@dataclass(frozen=True, slots=True)
class VerifyReport:
    commits: int
    files: int
    sources: int
    csv_indexes: int
    mail_messages: int


@dataclass(frozen=True, slots=True)
class PushReport:
    main_updates: int
    snapshot: str


def require_clean_tools(repo_root: Path) -> str:
    """Freeze the exact clean tools commit used by rendered metadata."""

    dirty = git_output(repo_root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if dirty:
        raise CorpusError(
            "tools worktree is dirty; commit or remove changes before build/update"
        )
    return git_output(repo_root, ["rev-parse", "HEAD"])


def merge_events(
    sources: Mapping[str, EventFactory], *, until: datetime | None = None
) -> Iterator[Event]:
    """K-way merge source streams while retaining each stream's hard ordering."""

    heap: list[
        tuple[tuple[int, datetime, str, str], str, int, Event, Iterator[Event]]
    ] = []
    sequence = 0

    def key(event: Event) -> tuple[int, datetime, str, str]:
        return (
            0 if event.time_confidence == "pre-epoch" else 1,
            event.source_time,
            event.source,
            event.source_id,
        )

    for name, factory in sorted(sources.items()):
        iterator = iter(factory())
        try:
            event = next(iterator)
        except StopIteration:
            continue
        event.validate()
        heapq.heappush(heap, (key(event), name, sequence, event, iterator))
        sequence += 1
    while heap:
        _key, name, _sequence, event, iterator = heapq.heappop(heap)
        if until is None or event.source_time <= until:
            yield event
        try:
            following = next(iterator)
        except StopIteration:
            continue
        following.validate()
        heapq.heappush(heap, (key(following), name, sequence, following, iterator))
        sequence += 1


def _coverage_summary(corpus: Path) -> str:
    rows: list[str] = []
    root = corpus / "_meta"
    if root.exists():
        for path in sorted(root.rglob("coverage.toml")):
            relative = path.relative_to(corpus).as_posix()
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
                raise CorpusError(f"cannot summarize coverage {path}: {exc}") from exc
            counts = [
                f"{name}={value}"
                for name, value in sorted(data.items())
                if isinstance(value, int) and not isinstance(value, bool)
            ]
            rows.append(
                f"- `{relative}`" + (f": {', '.join(counts)}" if counts else "")
            )
    return "\n".join(rows) if rows else "No source coverage files were emitted."


def _archive_manifest_changes(archive: Path) -> dict[str, bytes]:
    changes: dict[str, bytes] = {}
    root = archive / "manifests"
    if not root.exists():
        return changes
    for path in sorted(root.rglob("*.toml")):
        if path.is_symlink() or not path.is_file():
            raise CorpusError(f"unsafe archive manifest path: {path}")
        relative = path.relative_to(root).as_posix()
        changes[f"_meta/archive/{relative}"] = path.read_bytes()
    return changes


def _snapshot_name(source_time: datetime) -> str:
    return "snapshot/" + source_time.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _tag_snapshot(
    repo_root: Path, head: str, name: str, source_time: datetime, message: str
) -> None:
    existing = run_git(
        repo_root, ["rev-parse", "--verify", f"refs/tags/{name}^{{}}"], check=False
    )
    if existing.returncode == 0:
        if existing.stdout.strip() != head:
            raise GitError(f"snapshot tag already names another commit: {name}")
        return
    date = source_time.astimezone(UTC).replace(microsecond=0).isoformat()
    run_git(
        repo_root,
        ["tag", "-a", name, head, "-m", message],
        env={
            "GIT_COMMITTER_NAME": Identity.tool().name,
            "GIT_COMMITTER_EMAIL": Identity.tool().email,
            "GIT_COMMITTER_DATE": date,
        },
    )


def _install_main(config: Config, scratch: Path, final_head: str) -> None:
    old = run_git(
        config.repo_root, ["rev-parse", "--verify", "refs/heads/main"], check=False
    )
    old_head = old.stdout.strip() if old.returncode == 0 else "0" * len(final_head)
    run_git(config.repo_root, ["fetch", "--no-tags", str(scratch), "main"])
    run_git(
        config.repo_root,
        ["update-ref", "refs/heads/main", final_head, old_head],
    )
    run_git(config.corpus, ["reset", "--hard", final_head])


def build_corpus(
    config: Config,
    sources: Mapping[str, EventFactory],
    *,
    until: datetime | None = None,
) -> BuildReport:
    """Build a new orphan main history, installing it only after full success."""

    tools_commit = require_clean_tools(config.repo_root)
    status, _created = init_corpus(config)
    if status.branch != "main":
        raise CorpusError("build requires the corpus worktree on main")
    dirty = git_output(
        config.corpus, ["status", "--porcelain=v1", "--untracked-files=all"]
    )
    if dirty:
        raise CorpusError("corpus worktree is dirty; refusing transactional build")

    with tempfile.TemporaryDirectory(
        prefix="jbomohi-build-", dir=config.repo_root.parent
    ) as temporary:
        scratch = Path(temporary) / "main"
        run_git(
            scratch.parent,
            ["init", "--initial-branch=main", str(scratch)],
        )
        commit_root(
            config.repo_root,
            scratch,
            RenderContext(tools_commit=tools_commit),
        )
        event_count = 0
        last_time = EPOCH
        for event in merge_events(sources, until=until):
            commit_event(event, scratch)
            event_count += 1
            last_time = event.source_time
        snapshot = _snapshot_name(last_time)
        coverage = _coverage_summary(scratch)
        refresh_id = "refresh@" + snapshot.removeprefix("snapshot/")
        commit_instruction_refresh(
            config.repo_root,
            scratch,
            source_time=last_time,
            source_id=refresh_id,
            context=RenderContext(
                snapshot=snapshot,
                tools_commit=tools_commit,
                coverage_tables=coverage,
            ),
            extra_changes=_archive_manifest_changes(config.archive),
        )
        final_head = git_output(scratch, ["rev-parse", "HEAD"])
        commits = int(git_output(scratch, ["rev-list", "--count", "HEAD"]))
        _install_main(config, scratch, final_head)
    _tag_snapshot(config.repo_root, final_head, snapshot, last_time, coverage)
    return BuildReport(final_head, commits, event_count, snapshot, coverage)


def _commit_trailers(corpus: Path, commit: str) -> dict[str, str]:
    body = git_output(corpus, ["show", "-s", "--format=%B", commit])
    trailers: dict[str, str] = {}
    for line in body.splitlines():
        matched = _TRAILER.fullmatch(line)
        if matched:
            trailers[matched.group(1)] = matched.group(2)
    return trailers


def existing_source_ids(corpus: Path) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    commits = git_output(corpus, ["rev-list", "HEAD"]).splitlines()
    for commit in commits:
        trailers = _commit_trailers(corpus, commit)
        source = trailers.get("Source")
        source_id = trailers.get("Source-Id")
        if source and source_id:
            result.add((source, source_id))
    return result


def update_corpus(
    config: Config,
    sources: Mapping[str, EventFactory],
) -> BuildReport | None:
    """Append source IDs not already present, then refresh and snapshot."""

    tools_commit = require_clean_tools(config.repo_root)
    status, _created = init_corpus(config)
    if status.branch != "main" or status.head is None:
        raise CorpusError("update requires an initialized main corpus")
    dirty = git_output(
        config.corpus, ["status", "--porcelain=v1", "--untracked-files=all"]
    )
    if dirty:
        raise CorpusError("corpus worktree is dirty; refusing update")
    known = existing_source_ids(config.corpus)
    event_count = 0
    last_time: datetime | None = None
    for event in merge_events(sources):
        if (event.source, event.source_id) in known:
            continue
        commit_event(event, config.corpus)
        known.add((event.source, event.source_id))
        event_count += 1
        last_time = event.source_time
    if last_time is None:
        return None
    snapshot = _snapshot_name(last_time)
    coverage = _coverage_summary(config.corpus)
    commit_instruction_refresh(
        config.repo_root,
        config.corpus,
        source_time=last_time,
        source_id="refresh@" + snapshot.removeprefix("snapshot/"),
        context=RenderContext(
            snapshot=snapshot,
            tools_commit=tools_commit,
            coverage_tables=coverage,
        ),
        extra_changes=_archive_manifest_changes(config.archive),
    )
    head = git_output(config.corpus, ["rev-parse", "HEAD"])
    _tag_snapshot(config.repo_root, head, snapshot, last_time, coverage)
    commits = int(git_output(config.corpus, ["rev-list", "--count", "HEAD"]))
    return BuildReport(head, commits, event_count, snapshot, coverage)


def verify_corpus(corpus: Path) -> VerifyReport:
    """Verify commit trailers, source IDs, file limits, CSV paths, and Maildirs."""

    status = corpus_status(corpus)
    if not status.exists or status.head is None:
        raise CorpusError("cannot verify a missing or unborn corpus")
    dirty = git_output(corpus, ["status", "--porcelain=v1", "--untracked-files=all"])
    if dirty:
        raise CorpusError("corpus worktree is dirty")
    seen: set[tuple[str, str, str]] = set()
    sources: set[str] = set()
    commits = git_output(corpus, ["rev-list", "--reverse", "HEAD"]).splitlines()
    required = {"Source", "Source-Id", "Event", "Time-Confidence"}
    for commit in commits:
        trailers = _commit_trailers(corpus, commit)
        missing = required - trailers.keys()
        if missing:
            raise CorpusError(
                f"commit {commit} is missing trailers: {', '.join(sorted(missing))}"
            )
        changed = git_output(
            corpus,
            ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit],
        ).splitlines()
        for path in changed:
            identity = (trailers["Source"], path, trailers["Source-Id"])
            if identity in seen:
                raise CorpusError(f"duplicate Source-Id for source/path: {identity!r}")
            seen.add(identity)
        sources.add(trailers["Source"])

    files = [
        path
        for path in corpus.rglob("*")
        if path.is_file() and ".git" not in path.parts
    ]
    for path in files:
        if path.stat().st_size > _MAX_CORPUS_FILE:
            raise CorpusError(f"corpus file exceeds 100 MiB: {path}")

    csv_indexes = 0
    for path in (
        sorted((corpus / "_meta").rglob("*.csv")) if (corpus / "_meta").exists() else ()
    ):
        csv_indexes += 1
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            for row_number, row in enumerate(reader, 2):
                referenced = row.get("path") or row.get("file")
                if referenced and not (corpus / referenced).is_file():
                    raise CorpusError(
                        f"CSV path missing at {path}:{row_number}: {referenced}"
                    )

    mail_messages = 0
    mail_root = corpus / "mail"
    if mail_root.exists():
        for list_dir in sorted(path for path in mail_root.iterdir() if path.is_dir()):
            for required_dir in ("cur", "new", "tmp", "threads"):
                if not (list_dir / required_dir).is_dir():
                    raise CorpusError(
                        f"mail list {list_dir.name} is missing {required_dir}/"
                    )
            for path in (list_dir / "new").iterdir():
                if path.name != ".keep":
                    raise CorpusError(f"Maildir new/ is not empty: {path}")
            for path in (list_dir / "tmp").iterdir():
                if path.name != ".keep":
                    raise CorpusError(f"Maildir tmp/ is not empty: {path}")
            for path in (list_dir / "cur").iterdir():
                if not re.fullmatch(r"[0-9]+\.[0-9a-f]{16}\.jbomohi:2,S", path.name):
                    raise CorpusError(f"invalid Maildir filename: {path}")
                mail_messages += 1
    return VerifyReport(
        len(commits), len(files), len(sources), csv_indexes, mail_messages
    )


def push_main_ranges(
    repo_root: Path,
    snapshot: str,
    *,
    remote: str = "origin",
    commits_per_push: int = 5_000,
) -> PushReport:
    """Fast-forward main in bounded commit ranges, then publish one snapshot tag."""

    if commits_per_push < 1:
        raise ValueError("commits_per_push must be positive")
    local_head = git_output(repo_root, ["rev-parse", "refs/heads/main"])
    advertised = run_git(
        repo_root,
        ["ls-remote", "--heads", remote, "refs/heads/main"],
    ).stdout.strip()
    remote_head = advertised.split()[0] if advertised else None
    if remote_head is not None:
        run_git(repo_root, ["fetch", "--no-tags", remote, "refs/heads/main"])
        if (
            run_git(
                repo_root,
                ["merge-base", "--is-ancestor", remote_head, local_head],
                check=False,
            ).returncode
            != 0
        ):
            raise GitError("remote main is not an ancestor of the built main")
        revset = f"{remote_head}..{local_head}"
    else:
        revset = local_head
    commits = git_output(repo_root, ["rev-list", "--reverse", revset]).splitlines()
    updates = 0
    for index in range(commits_per_push - 1, len(commits), commits_per_push):
        run_git(
            repo_root,
            ["push", remote, f"{commits[index]}:refs/heads/main"],
        )
        updates += 1
    if commits and (len(commits) - 1) % commits_per_push != commits_per_push - 1:
        run_git(repo_root, ["push", remote, f"{local_head}:refs/heads/main"])
        updates += 1
    run_git(repo_root, ["push", remote, f"refs/tags/{snapshot}"])
    return PushReport(updates, snapshot)
