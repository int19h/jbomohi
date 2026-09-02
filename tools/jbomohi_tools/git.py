"""Deterministic git operations for the corpus projection."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
SOURCES = {
    "wiki",
    "tiki",
    "dict",
    "cll",
    "loglan",
    "llg",
    "grammars",
    "meta",
    "notes",
    "who",
}
EVENTS = {
    "created",
    "edited",
    "deleted",
    "moved",
    "comment",
    "vote-batch",
    "import",
    "render",
    "refresh",
    "contributed",
}
TIME_CONFIDENCE = {"exact", "tz-unknown", "window", "pre-epoch"}
RESERVED_TRAILERS = {
    "Source",
    "Source-Id",
    "Event",
    "Time-Confidence",
    "Source-Date",
    "Event-Window",
}
TRAILER_NAME = re.compile(r"^[A-Z][A-Za-z0-9-]*$")
HEX_ESCAPE_SAFE = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$&'*+-/=?^_`{|}~."
)


class GitError(RuntimeError):
    """A git operation failed."""


class EventError(ValueError):
    """An event violates the corpus commit contract."""


def run_git(
    cwd: Path,
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    process_env = dict(os.environ)
    process_env.update({"LC_ALL": "C", "TZ": "UTC"})
    if env:
        process_env.update(env)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=process_env,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise GitError(f"{' '.join(command)}: {detail}")
    return result


def git_output(cwd: Path, args: Sequence[str]) -> str:
    return run_git(cwd, args).stdout.strip()


def _clean_text(label: str, value: str) -> str:
    if not value or value.strip() != value or any(char in value for char in "\r\n\0"):
        raise EventError(f"{label} must be a non-empty single-line value")
    return value


def _encoded_local_part(value: str) -> str:
    return quote(value, safe=HEX_ESCAPE_SAFE, encoding="utf-8", errors="strict")


@dataclass(frozen=True, slots=True)
class Identity:
    """A source-scoped identity rendered into a git name and email."""

    name: str
    email: str
    namespace: str

    def __post_init__(self) -> None:
        _clean_text("identity name", self.name)
        _clean_text("identity email", self.email)
        _clean_text("identity namespace", self.namespace)
        if "@" not in self.email or any(char.isspace() for char in self.email):
            raise EventError("identity email must contain @ and no whitespace")
        if self.namespace in {"mail", "contributed"}:
            return
        fixed = {
            "jbomohi": ("jbomohi", "tools@jbomohi.invalid"),
            "irc.lojban.org": ("irclogs", "irclogs@irc.lojban.org"),
        }
        if self.namespace in fixed:
            if (self.name, self.email) != fixed[self.namespace]:
                raise EventError(f"invalid identity for namespace {self.namespace!r}")
            return
        if self.namespace.startswith("anonymous:"):
            host = self.namespace.removeprefix("anonymous:")
            if (
                not host
                or any(char.isspace() for char in host)
                or "@" in host
                or (self.name, self.email)
                != (
                    "anonymous",
                    f"anonymous@{host}",
                )
            ):
                raise EventError("invalid anonymous identity")
            return
        if any(char.isspace() for char in self.namespace) or "@" in self.namespace:
            raise EventError("identity namespace must be an email host")
        expected = f"{_encoded_local_part(self.name)}@{self.namespace}"
        if self.email != expected:
            raise EventError(
                f"namespaced identity email must be {expected!r}, got {self.email!r}"
            )

    @classmethod
    def namespaced(cls, namespace: str, username: str) -> Identity:
        host = _clean_text("identity namespace", namespace)
        user = _clean_text("username", username)
        if any(char.isspace() for char in host) or "@" in host:
            raise EventError("identity namespace must be an email host")
        if host in {
            "mail",
            "contributed",
            "jbomohi",
            "irc.lojban.org",
        } or host.startswith("anonymous:"):
            raise EventError(f"reserved identity namespace: {host!r}")
        return cls(user, f"{_encoded_local_part(user)}@{host}", host)

    @classmethod
    def mail(cls, address: str, display_name: str | None = None) -> Identity:
        email = _clean_text("mail address", address)
        if "@" not in email or any(char.isspace() for char in email):
            raise EventError("mail address must contain @ and no whitespace")
        local_part = email.rsplit("@", 1)[0]
        return cls(display_name or local_part, email, "mail")

    @classmethod
    def anonymous(cls, host: str) -> Identity:
        clean_host = _clean_text("anonymous host", host)
        if any(char.isspace() for char in clean_host) or "@" in clean_host:
            raise EventError("anonymous host must be an email host")
        return cls("anonymous", f"anonymous@{clean_host}", f"anonymous:{clean_host}")

    @classmethod
    def irc(cls) -> Identity:
        return cls("irclogs", "irclogs@irc.lojban.org", "irc.lojban.org")

    @classmethod
    def tool(cls) -> Identity:
        return cls("jbomohi", "tools@jbomohi.invalid", "jbomohi")

    @classmethod
    def contributed(cls, name: str, email: str) -> Identity:
        return cls(name, email, "contributed")


def _valid_source(source: str) -> bool:
    return source in SOURCES or source.startswith(("mail/", "irc/"))


def _safe_repo_path(value: str) -> PurePosixPath:
    if "\\" in value:
        raise EventError(f"corpus path must use / separators: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", "..", ".git"} for part in path.parts)
    ):
        raise EventError(f"unsafe corpus path: {value!r}")
    return path


@dataclass(frozen=True, slots=True)
class Event:
    """One source event and the complete file changes it contributes."""

    source: str
    source_id: str
    event: str
    time_confidence: str
    source_time: datetime
    summary: str
    author: Identity
    changes: Mapping[str, str | bytes] = field(default_factory=dict)
    deletions: tuple[str, ...] = ()
    body: str = ""
    source_date: str | None = None
    event_window: str | None = None
    trailers: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        source = _clean_text("source", self.source)
        if not _valid_source(source) or source.endswith("/"):
            raise EventError(f"unsupported source: {source!r}")
        _clean_text("source id", self.source_id)
        summary = _clean_text("summary", self.summary)
        subject = f"{source}: {summary}"
        if len(subject) > 72:
            raise EventError(
                f"commit subject is {len(subject)} characters; maximum is 72"
            )
        if self.event not in EVENTS:
            raise EventError(f"unsupported event: {self.event!r}")
        if self.time_confidence not in TIME_CONFIDENCE:
            raise EventError(f"unsupported time confidence: {self.time_confidence!r}")
        if self.source_time.tzinfo is None or self.source_time.utcoffset() is None:
            raise EventError("source time must include a UTC offset")
        if self.source_time.microsecond:
            raise EventError("source time must have whole-second precision for git")
        if self.time_confidence == "pre-epoch":
            if not self.source_date:
                raise EventError("pre-epoch events require Source-Date")
            if self.source_time >= EPOCH:
                raise EventError("pre-epoch confidence requires a date before 1970")
        elif self.source_date is not None:
            raise EventError("Source-Date is only valid for pre-epoch events")
        if self.time_confidence == "window":
            if not self.event_window or ".." not in self.event_window:
                raise EventError("window events require Event-Window as <from>..<to>")
        elif self.event_window is not None:
            raise EventError("Event-Window is only valid for window events")
        if self.source_time < EPOCH and self.time_confidence != "pre-epoch":
            raise EventError(
                "dates before the epoch require Time-Confidence: pre-epoch"
            )
        if self.event == "refresh" and self.author != Identity.tool():
            raise EventError("refresh commits must use the jbomohi tool identity")
        changed = {_safe_repo_path(path).as_posix() for path in self.changes}
        deleted = {_safe_repo_path(path).as_posix() for path in self.deletions}
        if changed & deleted:
            raise EventError("an event cannot both write and delete the same path")
        for key, value in self.trailers.items():
            if key in RESERVED_TRAILERS or not TRAILER_NAME.fullmatch(key):
                raise EventError(f"invalid or reserved event trailer: {key!r}")
            _clean_text(f"trailer {key}", value)
        if self.body and ("\0" in self.body or "\r" in self.body):
            raise EventError("commit body must be LF text without NUL bytes")

    @property
    def subject(self) -> str:
        return f"{self.source}: {self.summary}"


def _git_date(event: Event) -> str:
    value = EPOCH if event.time_confidence == "pre-epoch" else event.source_time
    return value.isoformat(timespec="seconds")


def _commit_message(event: Event) -> str:
    trailers: list[tuple[str, str]] = [
        ("Source", event.source),
        ("Source-Id", event.source_id),
        ("Event", event.event),
        ("Time-Confidence", event.time_confidence),
    ]
    if event.source_date:
        trailers.append(("Source-Date", event.source_date))
    if event.event_window:
        trailers.append(("Event-Window", event.event_window))
    trailers.extend(sorted(event.trailers.items()))
    parts = [event.subject]
    if event.body:
        parts.extend(["", event.body.rstrip("\n")])
    parts.extend(["", *(f"{key}: {value}" for key, value in trailers)])
    return "\n".join(parts) + "\n"


def _target(corpus: Path, relative: PurePosixPath) -> Path:
    current = corpus
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise EventError(f"refusing to traverse symlink in corpus path: {relative}")
    target = corpus.joinpath(*relative.parts)
    if target.is_symlink():
        raise EventError(f"refusing to replace symlink in corpus path: {relative}")
    return target


def _head(corpus: Path) -> str | None:
    result = run_git(corpus, ["rev-parse", "--verify", "HEAD"], check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def commit_event(event: Event, corpus: Path | None = None) -> str:
    """Commit one validated event without consulting the clock.

    The worktree must be clean so that an event can neither absorb nor erase
    unrelated state. Only the event's declared paths are staged.
    """

    event.validate()
    actual_corpus = corpus or Path(os.environ.get("JBOMOHI_CORPUS", "./corpus"))
    corpus = actual_corpus.expanduser().resolve()
    if not (corpus / ".git").exists():
        raise GitError(f"not a corpus worktree: {corpus}")
    dirty = git_output(corpus, ["status", "--porcelain=v1", "--untracked-files=all"])
    if dirty:
        raise GitError("corpus worktree is not clean; refusing to commit an event")

    old_head = _head(corpus)
    if old_head:
        run_git(corpus, ["read-tree", old_head])
    else:
        run_git(corpus, ["read-tree", "--empty"])

    paths: list[str] = []
    for raw_path in sorted(event.changes):
        relative = _safe_repo_path(raw_path)
        target = _target(corpus, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        value = event.changes[raw_path]
        data = value.encode("utf-8") if isinstance(value, str) else value
        target.write_bytes(data)
        target.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        paths.append(relative.as_posix())
    for raw_path in sorted(event.deletions):
        relative = _safe_repo_path(raw_path)
        target = _target(corpus, relative)
        if target.exists():
            if target.is_dir():
                raise EventError(f"event deletions must name files: {raw_path!r}")
            target.unlink()
        paths.append(relative.as_posix())
    if paths:
        run_git(corpus, ["add", "-A", "--", *paths])

    tree = git_output(corpus, ["write-tree"])
    commit_args = ["-c", "i18n.commitEncoding=UTF-8", "commit-tree", tree]
    if old_head:
        commit_args.extend(["-p", old_head])
    date = _git_date(event)
    identity_env = {
        "GIT_AUTHOR_NAME": event.author.name,
        "GIT_AUTHOR_EMAIL": event.author.email,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_NAME": event.author.name,
        "GIT_COMMITTER_EMAIL": event.author.email,
        "GIT_COMMITTER_DATE": date,
    }
    commit = git_output_with_input(
        corpus, commit_args, _commit_message(event), identity_env
    )
    update_args = ["update-ref", "HEAD", commit]
    if old_head:
        update_args.append(old_head)
    else:
        update_args.append("0" * len(commit))
    run_git(corpus, update_args)
    return commit


def git_output_with_input(
    cwd: Path, args: Sequence[str], input_text: str, env: Mapping[str, str]
) -> str:
    return run_git(cwd, args, env=env, input_text=input_text).stdout.strip()
