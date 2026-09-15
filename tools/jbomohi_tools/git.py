"""Deterministic git operations for the corpus projection."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from collections.abc import Mapping, Sequence
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Self
from urllib.parse import quote, unquote

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# SPEC.md 3.1: a commit subject is always one non-empty line, and a source that
# offers no title, subject or comment gets a placeholder rather than an
# invented description. Mail keeps its own, older `[no subject]`.
UNTITLED = "[untitled]"
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
GITLINK_ID = re.compile(r"^[0-9a-f]{40}$")
HEX_ESCAPE_SAFE = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$&'*+-/=?^_`{|}~."
)
GIT_REPOSITORY_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_GLOB_PATHSPECS",
    "GIT_GRAFT_FILE",
    "GIT_ICASE_PATHSPECS",
    "GIT_NAMESPACE",
    "GIT_NOGLOB_PATHSPECS",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_QUARANTINE_PATH",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
}


class GitError(RuntimeError):
    """A git operation failed."""


class EventError(ValueError):
    """An event violates the corpus commit contract."""


def git_command(args: Sequence[str]) -> list[str]:
    """The git invocation the corpus uses, pinned against local configuration."""

    return [
        "git",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.safecrlf=false",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        f"core.hooksPath={os.devnull}",
        *args,
    ]


def git_environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment the corpus uses, with the caller's git config removed."""

    process_env = dict(os.environ)
    if env:
        process_env.update(env)
    for name in tuple(process_env):
        if name in GIT_REPOSITORY_ENV or name.startswith("GIT_CONFIG_"):
            process_env.pop(name)
    process_env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_LITERAL_PATHSPECS": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "LC_ALL": "C",
            "TZ": "UTC",
        }
    )
    return process_env


def run_git(
    cwd: Path,
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = git_command(args)
    process_env = git_environment(env)
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
    encoded = quote(value, safe=HEX_ESCAPE_SAFE, encoding="utf-8", errors="strict")
    return "".join(
        "%2E"
        if char == "."
        and (
            index == 0
            or index + 1 == len(encoded)
            or encoded[index - 1] == "."
            or encoded[index + 1] == "."
        )
        else char
        for index, char in enumerate(encoded)
    )


def _git_safe_name(value: str, *, label: str = "identity name") -> str:
    """Injectively encode source-name syntax that git cannot retain."""

    if (
        not isinstance(value, str)
        or not value
        or any(character in value for character in "\r\n\0")
    ):
        raise EventError(f"{label} must be non-empty text without line breaks or NUL")
    name = value
    name = name.replace("%", "%25").replace("<", "%3C").replace(">", "%3E")
    name = "".join(
        f"%{ord(character):02X}" if ord(character) < 32 else character
        for character in name
    )
    while name and name[0].isspace():
        encoded = "".join(f"%{byte:02X}" for byte in name[0].encode("utf-8"))
        name = encoded + name[1:]
    while name and name[-1].isspace():
        encoded = "".join(f"%{byte:02X}" for byte in name[-1].encode("utf-8"))
        name = name[:-1] + encoded
    if name.startswith("."):
        name = "%2E" + name[1:]
    if name.endswith("."):
        name = name[:-1] + "%2E"
    return _clean_text(label, name)


def _iso_date(label: str, value: str) -> date:
    clean = _clean_text(label, value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", clean):
        raise EventError(f"{label} must be an ISO date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(clean)
    except ValueError as exc:
        raise EventError(f"{label} must be an ISO date (YYYY-MM-DD)") from exc


def _source_date(value: str) -> None:
    if re.fullmatch(r"[0-9]{4}", value):
        if int(value) == 0:
            raise EventError("Source-Date must be YYYY, YYYY-MM, or YYYY-MM-DD")
        return
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        year, month = (int(item) for item in value.split("-"))
        if year == 0 or not 1 <= month <= 12:
            raise EventError("Source-Date must be YYYY, YYYY-MM, or YYYY-MM-DD")
        return
    try:
        _iso_date("Source-Date", value)
    except EventError as exc:
        raise EventError("Source-Date must be YYYY, YYYY-MM, or YYYY-MM-DD") from exc


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
        if "<" in self.email or ">" in self.email:
            raise EventError("identity email must not contain < or >")
        if (
            "<" in self.name
            or ">" in self.name
            or self.name.startswith(".")
            or self.name.endswith(".")
        ):
            raise EventError("identity name contains characters git cannot preserve")
        if self.namespace in {"mail", "contributed", "upstream", "document"}:
            return
        fixed = {
            "jbomohi": ("jbomohi", "tools@jbomohi.invalid"),
            "irc.lojban.org": ("irclogs", "irclogs@irc.lojban.org"),
        }
        if self.namespace in fixed:
            if (self.name, self.email) != fixed[self.namespace]:
                raise EventError(f"invalid identity for namespace {self.namespace!r}")
            return
        for label in ("anonymous", "unrecorded"):
            if not self.namespace.startswith(f"{label}:"):
                continue
            host = self.namespace.removeprefix(f"{label}:")
            if (
                not host
                or any(char.isspace() for char in host)
                or "@" in host
                or (self.name, self.email) != (label, f"{label}@{host}")
            ):
                raise EventError(f"invalid {label} identity")
            return
        if any(char.isspace() for char in self.namespace) or "@" in self.namespace:
            raise EventError("identity namespace must be an email host")
        local_part, email_namespace = self.email.rsplit("@", 1)
        if email_namespace != self.namespace:
            raise EventError(
                f"namespaced identity email must end in @{self.namespace}, got {self.email!r}"
            )
        try:
            source_name = unquote(local_part, encoding="utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise EventError(
                "namespaced identity email has invalid UTF-8 escaping"
            ) from exc
        expected_name = _git_safe_name(source_name)
        expected_email = f"{_encoded_local_part(source_name)}@{self.namespace}"
        if self.name != expected_name or self.email != expected_email:
            raise EventError(
                "namespaced identity name/email are not the canonical source-name encoding"
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
        } or host.startswith(("anonymous:", "unrecorded:")):
            raise EventError(f"reserved identity namespace: {host!r}")
        return cls(
            _git_safe_name(user, label="username"),
            f"{_encoded_local_part(user)}@{host}",
            host,
        )

    @classmethod
    def mail(cls, address: str, display_name: str | None = None) -> Identity:
        """Create a mail identity, explicitly escaping git-unsafe name syntax.

        Git strips angle brackets and leading/trailing dots from author names.
        Percent signs are escaped too, keeping this normalisation injective.
        """

        source_email = _clean_text("mail address", address)
        if "@" not in source_email:
            raise EventError("mail address must contain @")
        email = source_email.replace("%", "%25")
        email = "".join(
            "".join(f"%{byte:02X}" for byte in character.encode("utf-8"))
            if character.isspace()
            else character
            for character in email
        )
        local_part = source_email.rsplit("@", 1)[0]
        return cls(
            _git_safe_name(display_name or local_part, label="mail display name"),
            email,
            "mail",
        )

    @classmethod
    def upstream(cls, name: str, email: str) -> Identity:
        """Retain the public author identity stored in an upstream git commit."""

        return cls(name, email, "upstream")

    @classmethod
    def document(cls, host: str, name: str, author_slug: str) -> Identity:
        """Create a source-stated document author with an attested email slug."""

        clean_host = _clean_text("document author host", host)
        clean_name = _clean_text("document author name", name)
        clean_slug = _clean_text("document author slug", author_slug)
        if (
            any(char.isspace() for char in clean_host)
            or "@" in clean_host
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", clean_slug)
        ):
            raise EventError("invalid document author host or slug")
        return cls(clean_name, f"{clean_slug}@{clean_host}", "document")

    @classmethod
    def anonymous(cls, host: str) -> Identity:
        clean_host = _clean_text("anonymous host", host)
        if any(char.isspace() for char in clean_host) or "@" in clean_host:
            raise EventError("anonymous host must be an email host")
        return cls("anonymous", f"anonymous@{clean_host}", f"anonymous:{clean_host}")

    @classmethod
    def unrecorded(cls, host: str) -> Identity:
        """The source keeps no author at all, which is not suppression.

        SPEC.md 2.5 keeps this distinct from `anonymous@`: a MediaWiki
        transwiki import with no actor row records nobody, while `anonymous`
        means the wiki deliberately withheld a name it holds.
        """

        clean_host = _clean_text("unrecorded host", host)
        if any(char.isspace() for char in clean_host) or "@" in clean_host:
            raise EventError("unrecorded host must be an email host")
        return cls("unrecorded", f"unrecorded@{clean_host}", f"unrecorded:{clean_host}")

    @classmethod
    def irc(cls) -> Identity:
        return cls("irclogs", "irclogs@irc.lojban.org", "irc.lojban.org")

    @classmethod
    def tool(cls) -> Identity:
        return cls("jbomohi", "tools@jbomohi.invalid", "jbomohi")

    @classmethod
    def contributed(cls, name: str, email: str) -> Identity:
        return cls(_git_safe_name(name), email, "contributed")


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
    gitlinks: Mapping[str, str] = field(default_factory=dict)
    submodules: Mapping[str, str] = field(default_factory=dict)
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
            _iso_date("Source-Date", self.source_date)
            if self.source_time >= EPOCH:
                raise EventError("pre-epoch confidence requires a date before 1970")
        elif self.source_date is not None:
            if self.time_confidence != "exact":
                raise EventError(
                    "Source-Date is only valid for pre-epoch or exact events"
                )
            _source_date(self.source_date)
        if self.time_confidence == "window":
            if not self.event_window:
                raise EventError("window events require Event-Window as <from>..<to>")
            parts = self.event_window.split("..")
            if len(parts) != 2:
                raise EventError("Event-Window must be <iso-date>..<iso-date>")
            start = _iso_date("Event-Window start", parts[0])
            end = _iso_date("Event-Window end", parts[1])
            if start > end:
                raise EventError("Event-Window start must not be after its end")
        elif self.event_window is not None:
            raise EventError("Event-Window is only valid for window events")
        if self.source_time < EPOCH and self.time_confidence != "pre-epoch":
            raise EventError(
                "dates before the epoch require Time-Confidence: pre-epoch"
            )
        if self.event == "refresh" and self.author != Identity.tool():
            raise EventError("refresh commits must use the jbomohi tool identity")
        changed = {_safe_repo_path(path).as_posix() for path in self.changes}
        if ".gitmodules" in changed:
            raise EventError(
                "projectors must declare submodules, not write .gitmodules"
            )
        if any(not isinstance(value, (str, bytes)) for value in self.changes.values()):
            raise EventError("event changes must contain only text or bytes")
        gitlinks = {_safe_repo_path(path).as_posix() for path in self.gitlinks}
        for path, object_id in self.gitlinks.items():
            if not isinstance(object_id, str) or not GITLINK_ID.fullmatch(object_id):
                raise EventError(f"gitlink {path!r} must name a 40-digit object id")
        submodules = {_safe_repo_path(path).as_posix() for path in self.submodules}
        if gitlinks != submodules:
            raise EventError("gitlinks and submodules must declare the same paths")
        for path, url in self.submodules.items():
            if '"' in path or "\\" in path:
                raise EventError(f"submodule path is unsafe for .gitmodules: {path!r}")
            clean_url = _clean_text(f"submodule URL for {path}", url)
            if any(char.isspace() for char in clean_url):
                raise EventError(f"submodule URL contains whitespace: {path!r}")
        deleted = {_safe_repo_path(path).as_posix() for path in self.deletions}
        if changed & deleted or changed & gitlinks or deleted & gitlinks:
            raise EventError("an event cannot write, link, and delete the same path")
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


def _target(
    corpus: Path, relative: PurePosixPath, *, allow_final_symlink: bool = False
) -> Path:
    current = corpus
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise EventError(f"refusing to traverse symlink in corpus path: {relative}")
    target = corpus.joinpath(*relative.parts)
    if target.is_symlink() and not allow_final_symlink:
        raise EventError(f"refusing to replace symlink in corpus path: {relative}")
    return target


def _head(corpus: Path) -> str | None:
    result = run_git(corpus, ["rev-parse", "--verify", "HEAD"], check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _tracked_at(corpus: Path, head: str | None, relative: PurePosixPath) -> bool:
    if not head:
        return False
    result = run_git(
        corpus,
        ["cat-file", "-e", f"{head}:{relative.as_posix()}"],
        check=False,
    )
    return result.returncode == 0


def _submodules_at(corpus: Path, head: str | None) -> dict[str, str]:
    if head is None:
        return {}
    result = run_git(corpus, ["show", f"{head}:.gitmodules"], check=False)
    if result.returncode != 0:
        return {}
    parser = ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string(result.stdout)
    except ConfigParserError as exc:
        raise EventError("parent .gitmodules is invalid") from exc
    submodules: dict[str, str] = {}
    for section in parser.sections():
        matched = re.fullmatch(r'submodule "([^"]+)"', section)
        if matched is None or set(parser[section]) != {"path", "url"}:
            raise EventError("parent .gitmodules has an unsupported section")
        path = _safe_repo_path(parser[section]["path"]).as_posix()
        if matched.group(1) != path or path in submodules:
            raise EventError("parent .gitmodules has an inconsistent path")
        url = _clean_text(f"parent submodule URL for {path}", parser[section]["url"])
        if any(char.isspace() for char in url):
            raise EventError("parent .gitmodules has an invalid URL")
        submodules[path] = url
    return submodules


def _render_submodules(submodules: Mapping[str, str]) -> bytes:
    lines: list[str] = []
    for path, url in sorted(submodules.items()):
        lines.extend(
            [
                f'[submodule "{path}"]',
                f"\tpath = {path}",
                f"\turl = {url}",
            ]
        )
    return ("\n".join(lines) + "\n").encode()


def _resolve_corpus(corpus: Path | None) -> Path:
    actual_corpus = corpus or Path(
        os.environ.get("JBOMOHI_CORPUS", Path.home() / "lojban" / "corpus")
    )
    resolved = actual_corpus.expanduser().resolve()
    if not (resolved / ".git").exists():
        raise GitError(f"not a corpus repository: {resolved}")
    return resolved


def commit_event(event: Event, corpus: Path | None = None) -> str:
    """Commit one validated event without consulting the clock.

    The working tree must be clean so that an event can neither absorb nor
    erase unrelated state. Only the event's declared paths are staged.
    """

    resolved = _resolve_corpus(corpus)
    dirty = git_output(resolved, ["status", "--porcelain=v1", "--untracked-files=all"])
    if dirty:
        raise GitError("corpus working tree is not clean; refusing to commit an event")
    old_head = _head(resolved)
    if old_head:
        run_git(resolved, ["read-tree", old_head])
    else:
        run_git(resolved, ["read-tree", "--empty"])
    return _commit_event_into(event, resolved, old_head)


def _commit_event_into(
    event: Event,
    corpus: Path,
    old_head: str | None,
    *,
    move_head: bool = True,
) -> str:
    """Stage and commit one event into an index the caller has prepared.

    With `move_head` false the commit is written but `HEAD` is left where it
    was: a build chains commits by parent and only has to move the ref once,
    at the end, which is one process fewer per event.
    """

    event.validate()
    writes: list[tuple[str, Path, bytes]] = []
    for raw_path in sorted(event.changes):
        relative = _safe_repo_path(raw_path)
        target = _target(corpus, relative)
        value = event.changes[raw_path]
        data = value.encode("utf-8") if isinstance(value, str) else value
        writes.append((relative.as_posix(), target, data))
    if event.submodules:
        submodules = _submodules_at(corpus, old_head)
        submodules.update(event.submodules)
        relative = _safe_repo_path(".gitmodules")
        writes.append(
            (
                relative.as_posix(),
                _target(corpus, relative),
                _render_submodules(submodules),
            )
        )

    deletions: list[tuple[str, Path]] = []
    for raw_path in sorted(event.deletions):
        relative = _safe_repo_path(raw_path)
        if not _tracked_at(corpus, old_head, relative):
            raise EventError(f"deletion names an untracked path: {raw_path!r}")
        target = _target(corpus, relative, allow_final_symlink=True)
        if target.is_dir() and not target.is_symlink():
            raise EventError(f"event deletions must name files: {raw_path!r}")
        deletions.append((relative.as_posix(), target))

    gitlinks: list[tuple[str, Path, str]] = []
    for raw_path, object_id in sorted(event.gitlinks.items()):
        relative = _safe_repo_path(raw_path)
        target = _target(corpus, relative)
        if target.exists() and not target.is_dir():
            raise EventError(f"gitlink path is not a directory: {raw_path!r}")
        gitlinks.append((relative.as_posix(), target, object_id))

    paths: list[str] = []
    for relative, target, data in writes:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        mode = (
            stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
            if re.fullmatch(r"mail/[^/]+/cur/[^/]+:2,S", relative)
            else stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
        )
        target.chmod(mode)
        paths.append(relative)
    for relative, target in deletions:
        if target.exists() or target.is_symlink():
            target.unlink()
        paths.append(relative)
    if paths:
        run_git(corpus, ["add", "-A", "--", *paths])
    for relative, target, object_id in gitlinks:
        target.mkdir(parents=True, exist_ok=True)
        run_git(
            corpus,
            ["update-index", "--add", "--cacheinfo", f"160000,{object_id},{relative}"],
        )

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
    if move_head:
        _move_head(corpus, commit, old_head)
    return commit


def _move_head(corpus: Path, commit: str, old_head: str | None) -> None:
    update_args = ["update-ref", "HEAD", commit]
    update_args.append(old_head if old_head else "0" * len(commit))
    run_git(corpus, update_args)


class BuildCommitSession:
    """Commit a whole build into a scratch repository the tools own.

    `commit_event` proves the worktree clean and rebuilds the index from HEAD
    before every event. Both are O(files in the corpus), so the cost per commit
    climbs as the corpus grows and the full build takes hours. A build owns its
    scratch repository outright — nothing else writes to it — so the clean
    check is answered once at the start and the index is kept alive across
    events instead. `write-tree` then rewrites only the subtrees the event
    touched, because the index keeps its cache-tree, and the commits are
    byte-identical to the ones the per-event path produces.

    `update` keeps the careful path: it writes into a corpus contributors share.
    """

    def __init__(self, corpus: Path) -> None:
        self.corpus = _resolve_corpus(corpus)
        self.started: str | None = None
        dirty = git_output(
            self.corpus, ["status", "--porcelain=v1", "--untracked-files=all"]
        )
        if dirty:
            raise GitError("corpus worktree is not clean; refusing to build into it")
        self.head = _head(self.corpus)
        self.started = self.head
        if self.head:
            run_git(self.corpus, ["read-tree", self.head])
        else:
            run_git(self.corpus, ["read-tree", "--empty"])

    def commit(self, event: Event) -> str:
        self.head = _commit_event_into(event, self.corpus, self.head, move_head=False)
        return self.head

    def flush(self) -> None:
        """Point HEAD at the last commit written, once."""

        if self.head is not None and self.head != self.started:
            _move_head(self.corpus, self.head, self.started)
            self.started = self.head

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        if exc[0] is None:
            self.flush()


def _fast_import_path(relative: str) -> bytes:
    """Quote a path for fast-import, which reads one path per line.

    Always quoting removes any question about spaces, quotes or the leading
    double quote fast-import would otherwise read as the start of a quoted
    path, and C-style escaping is what it expects inside the quotes.
    """

    escaped = relative.encode("utf-8").decode("latin-1")
    body = escaped.translate(
        {
            0x22: '\\"',
            0x5C: "\\\\",
            0x0A: "\\n",
            0x0D: "\\r",
            0x09: "\\t",
        }
    )
    return f'"{body}"'.encode("latin-1")


class FastImportSession:
    """Build a whole history through one `git fast-import` process.

    The plumbing path spends its time on work proportional to the corpus
    rather than to the event: it rebuilds and rewrites the index for every
    commit, so a build slows down as it goes — the first production build ran
    at 244 commits a minute in its first hour and 57 in its seventh. Feeding
    one stream to fast-import makes a commit cost what the event costs, and
    nothing more.

    The commits are byte-identical to the plumbing path's: the same author and
    committer, date, message, trailers and tree, including gitlinks and the
    accumulated `.gitmodules`. Identical heads are the acceptance, not a
    resemblance. The worktree is not touched until the end, because
    fast-import writes objects and refs only; `__exit__` checks it out once.

    `update` keeps the plumbing path: it writes into a corpus contributors
    share, where the careful per-event checks are the point.
    """

    def __init__(self, corpus: Path, branch: str = "refs/heads/main") -> None:
        self.corpus = _resolve_corpus(corpus)
        dirty = git_output(
            self.corpus, ["status", "--porcelain=v1", "--untracked-files=all"]
        )
        if dirty:
            raise GitError("corpus worktree is not clean; refusing to build into it")
        self.branch = branch
        self.head = _head(self.corpus)
        self.started = self.head
        self.count = 0
        self.submodules = _submodules_at(self.corpus, self.head)
        self.tracked: set[str] = set()
        if self.head:
            listing = git_output(
                self.corpus, ["ls-tree", "-r", "--name-only", self.head]
            )
            self.tracked = {line for line in listing.splitlines() if line}
        self.process = subprocess.Popen(
            git_command(["fast-import", "--quiet", "--done", "--date-format=raw"]),
            cwd=self.corpus,
            env=git_environment(),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def _write(self, payload: bytes) -> None:
        assert self.process.stdin is not None
        try:
            self.process.stdin.write(payload)
        except BrokenPipeError as exc:  # pragma: no cover - fast-import died
            raise GitError(
                f"git fast-import closed its input: {self._stderr()}"
            ) from exc

    def _stderr(self) -> str:
        if self.process.stderr is None:
            return "unknown fast-import error"
        return self.process.stderr.read().decode("utf-8", "replace").strip()

    @staticmethod
    def _blob(payload: bytes) -> bytes:
        return b"data " + str(len(payload)).encode("ascii") + b"\n" + payload + b"\n"

    def commit(self, event: Event) -> str:
        event.validate()
        writes: list[tuple[str, bytes]] = []
        for raw_path in sorted(event.changes):
            relative = _safe_repo_path(raw_path).as_posix()
            value = event.changes[raw_path]
            writes.append(
                (relative, value.encode("utf-8") if isinstance(value, str) else value)
            )
        if event.submodules:
            self.submodules.update(event.submodules)
            writes.append(
                (
                    _safe_repo_path(".gitmodules").as_posix(),
                    _render_submodules(self.submodules),
                )
            )
        removals: list[str] = []
        for raw_path in sorted(event.deletions):
            relative = _safe_repo_path(raw_path).as_posix()
            if relative not in self.tracked:
                raise EventError(f"deletion names an untracked path: {raw_path!r}")
            removals.append(relative)
        gitlinks: list[tuple[str, str]] = []
        for raw_path, object_id in sorted(event.gitlinks.items()):
            gitlinks.append((_safe_repo_path(raw_path).as_posix(), object_id))

        self.count += 1
        mark = self.count
        moment = EPOCH if event.time_confidence == "pre-epoch" else event.source_time
        stamp = f"{int(moment.timestamp())} +0000"
        identity = f"{event.author.name} <{event.author.email}> {stamp}"
        message = _commit_message(event).encode("utf-8")
        lines = [
            b"commit " + self.branch.encode("ascii"),
            b"mark :" + str(mark).encode("ascii"),
            b"author " + identity.encode("utf-8"),
            b"committer " + identity.encode("utf-8"),
        ]
        self._write(b"\n".join(lines) + b"\n" + self._blob(message))
        if mark == 1 and self.head:
            # Continue the branch the deterministic root commit started; an
            # unborn branch has no parent to name.
            self._write(b"from " + self.head.encode("ascii") + b"\n")
        for relative, payload in writes:
            self._write(b"M 100644 inline " + _fast_import_path(relative) + b"\n")
            self._write(self._blob(payload))
            self.tracked.add(relative)
        for relative, object_id in gitlinks:
            self._write(
                b"M 160000 "
                + object_id.encode("ascii")
                + b" "
                + _fast_import_path(relative)
                + b"\n"
            )
            self.tracked.add(relative)
        for relative in removals:
            self._write(b"D " + _fast_import_path(relative) + b"\n")
            self.tracked.discard(relative)
        self._write(b"\n")
        return f":{mark}"

    def finish(self) -> str | None:
        """Close the stream, then make the worktree match what was written."""

        assert self.process.stdin is not None
        # `--done` makes the terminator mandatory, including for a build that
        # produced no events at all.
        self._write(b"done\n")
        self.process.stdin.close()
        if self.process.wait() != 0:
            raise GitError(f"git fast-import failed: {self._stderr()}")
        if self.process.stderr is not None:
            self.process.stderr.close()
        if self.count:
            run_git(self.corpus, ["reset", "--hard", self.branch])
        self.head = _head(self.corpus)
        return self.head

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        if exc[0] is None:
            self.finish()
            return
        # The build failed: abandon the stream without letting a broken pipe
        # or a stuck child hide the error that actually matters.
        self.abandon()

    def abandon(self) -> None:
        for stream in (self.process.stdin, self.process.stderr):
            if stream is None:
                continue
            with suppress(OSError):
                stream.close()
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()


def git_output_with_input(
    cwd: Path, args: Sequence[str], input_text: str, env: Mapping[str, str]
) -> str:
    return run_git(cwd, args, env=env, input_text=input_text).stdout.strip()
