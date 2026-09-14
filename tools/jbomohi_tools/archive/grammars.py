"""Bare-mirror acquisition for required grammar and parser repositories."""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from ..git import git_output, run_git
from ..project.rcs import parse as parse_rcs
from .manifest import (
    ArchiveError,
    ArchiveManifest,
    object_path,
    store_file,
    store_object,
)

GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_VENDOR_HOSTS = {"lojban.org", "www.lojban.org", "web.archive.org"}


@dataclass(frozen=True, slots=True)
class GitGrammar:
    key: str
    path: str
    url: str
    default_branch: str
    name: str
    author: str
    language: str
    formalism: str
    dialect: str
    years: str
    licence: str

    @property
    def branch_ref(self) -> str:
        return f"refs/heads/{self.default_branch}"


GIT_GRAMMARS = (
    GitGrammar(
        "cll-parser",
        "grammars/official/parser/cll-parser",
        "https://github.com/lojban/cll-parser",
        "master",
        "Official LLG parser 3.0.00",
        "John Cowan",
        "K&R C + YACC",
        "YACC + lexer pre-pass",
        "3rd baseline",
        "2001-2003",
        "AFL-2.0",
    ),
    GitGrammar(
        "jbofihe",
        "grammars/jbofihe/src",
        "https://github.com/lojban/jbofihe",
        "master",
        "jbofihe",
        "Richard Curnow; LLG contributors",
        "C",
        "Bison + generated morphology DFA",
        "3rd baseline",
        "1999-present",
        "GPL-2.0",
    ),
    GitGrammar(
        "camxes-js",
        "grammars/camxes-js/src",
        "https://github.com/mhagiwara/camxes.js",
        "master",
        "camxes.js",
        "Masato Hagiwara",
        "JavaScript",
        "PEG.js",
        "camxes standard",
        "2013-2014",
        "MIT",
    ),
    GitGrammar(
        "ilmentufa-original",
        "grammars/ilmentufa/original",
        "https://github.com/Ntsekees/ilmentufa",
        "master",
        "ilmentufa (original)",
        "Ilmen; lagleki",
        "JavaScript / PEG.js",
        "PEG.js",
        "standard + experimental",
        "2014-2015",
        "MIT",
    ),
    GitGrammar(
        "ilmentufa",
        "grammars/ilmentufa/src",
        "https://github.com/lojban/ilmentufa",
        "master",
        "ilmentufa (canonical)",
        "Ilmen; LLG contributors",
        "PEG.js",
        "PEG.js",
        "standard / beta / experimental / morphology",
        "2016-present",
        "MIT",
    ),
    GitGrammar(
        "gerna-cipra",
        "grammars/zantufa/src",
        "https://github.com/guskant/gerna_cipra",
        "master",
        "gerna_cipra",
        "guskant",
        "JavaScript / PEG",
        "PEG.js variants",
        "zantufa / maftufa / maltufa",
        "2015-2019",
        "GPL-2.0",
    ),
    GitGrammar(
        "zasni-gerna",
        "grammars/zasni-gerna/haskell",
        "https://github.com/YoshikuniJujo/zasni-gerna",
        "master",
        "zasni-gerna (iocixes)",
        "Yoshikuni Jujo",
        "Haskell",
        "Papillon PEG",
        "zasni gerna",
        "2013-2019",
        "BSD-3-Clause",
    ),
    GitGrammar(
        "tersmu-upstream",
        "grammars/tersmu/src",
        "https://gitlab.com/zugz/tersmu",
        "master",
        "tersmu (upstream)",
        "Martin Bays",
        "Haskell",
        "Pappy packrat + semantic backend",
        "CLL + xorlo",
        "2011-2023",
        "GPL-3.0",
    ),
    GitGrammar(
        "tersmu-llg",
        "grammars/tersmu/llg",
        "https://github.com/lojban/tersmu",
        "master",
        "tersmu (LLG continuation)",
        "Martin Bays; LLG contributors",
        "Haskell / Rust",
        "Pappy packrat + semantic backend",
        "CLL + xorlo",
        "2011-present",
        "GPL-3.0",
    ),
    GitGrammar(
        "jbogenturfahi",
        "grammars/jbogenturfahi/src",
        "https://github.com/alanpost/jbogenturfahi",
        "master",
        "jbogenturfa'i",
        "Alan Post",
        "Scheme",
        "PEG",
        "camxes standard",
        "2010-2013",
        "ISC",
    ),
    GitGrammar(
        "genturfahi",
        "grammars/jbogenturfahi/engine",
        "https://github.com/alanpost/genturfahi",
        "master",
        "genturfahi",
        "Alan Post",
        "Scheme",
        "packrat engine",
        "generic",
        "2010-2012",
        "ISC",
    ),
    GitGrammar(
        "camxes-py",
        "grammars/ports/camxes-py/src",
        "https://github.com/lojban/camxes-py",
        "master",
        "camxes-py",
        "Riley Martinez-Lynch; LLG contributors",
        "Python",
        "Parsimonious PEG",
        "ilmentufa standard",
        "2014-2021",
        "MIT",
    ),
    GitGrammar(
        "johaus",
        "grammars/ports/johaus/src",
        "https://github.com/eaburns/johaus",
        "master",
        "johaus",
        "Ethan Burns",
        "Go",
        "generated PEG parsers",
        "camxes / ilmentufa / maftufa / zantufa",
        "2017-2019",
        "MIT",
    ),
    GitGrammar(
        "valfendi",
        "grammars/ports/valfendi/src",
        "https://github.com/phma/valfendi",
        "master",
        "valfendi",
        "Pierre Abbat",
        "C++",
        "hand-written lexer",
        "morphology only",
        "2014",
        "no licence",
    ),
    GitGrammar(
        "jbotci",
        "grammars/jbotci/src",
        "https://github.com/int19h/jbotci",
        "main",
        "jbotci",
        "Pavel Minaev",
        "Rust",
        "hand-written generated recursive descent",
        "CLL baseline + gated camxes-exp / zantufa",
        "2026-present",
        "MIT",
    ),
)


@dataclass(frozen=True, slots=True)
class GrammarFile:
    key: str
    url: str
    source_date: str
    note: str


VENDOR_FILES = (
    *(
        GrammarFile(
            f"history-{name.lower()}",
            f"https://lojban.org/files/history/{name}",
            source_date,
            "Official LLG grammar history file; date comes from its own header.",
        )
        for name, source_date in (
            ("GRAMMAR.B17", "1990-07-20"),
            ("GRAMMAR.NEW", "1990-07-20"),
            ("GRAMMAR.E25", "1989-02-25"),
            ("GRAMMAR.L23", "1989-09-23"),
            ("GRAMMAR.506", "1990-05-06"),
            ("GRAMMAR.28", "1990-07-20"),
            ("BNF.28", "1990-07-20"),
            ("techfix.28", "1990-07-20"),
        )
    ),
    GrammarFile(
        "second-bnf-28",
        "https://web.archive.org/web/19991104095552id_/http://www.lojban.org/files/machine-grammars/bnf.28",
        "1991-06-23",
        "Wayback capture of the restamped second-baseline BNF.",
    ),
    GrammarFile(
        "second-bnf-235",
        "https://web.archive.org/web/19991104072233id_/http://www.lojban.org/files/machine-grammars/bnf.235",
        "1994-03-29",
        "Wayback capture; file header supplies the source date.",
    ),
    GrammarFile(
        "second-techfix-235",
        "https://web.archive.org/web/19991009221736id_/http://www.lojban.org/files/machine-grammars/techfix.235",
        "1994-03-29",
        "Wayback capture; file header supplies the source date.",
    ),
    GrammarFile(
        "second-bnf-246",
        "https://web.archive.org/web/19991009145051id_/http://www.lojban.org/files/machine-grammars/bnf.246",
        "1996-03-20",
        "Wayback capture; file header supplies the source date.",
    ),
    GrammarFile(
        "second-bnf-247",
        "https://web.archive.org/web/19991009171117id_/http://www.lojban.org/files/machine-grammars/bnf.247",
        "1996-12-20",
        "Wayback capture; file header supplies the source date.",
    ),
    *(
        GrammarFile(
            f"third-{name.lower()}",
            f"https://lojban.org/publications/formal-grammars/{name}",
            "1997-01-10",
            "Official third-baseline companion file; grammar.300 stays in cll/src.",
        )
        for name in ("bnf.300", "techfix.300", "xref.300", "PD")
    ),
    GrammarFile(
        "parser-shar",
        "https://www.lojban.org/files/software/parser/parser.shar.gz",
        "1993-10-19",
        "Official LLG parser source archive and 2.33 grammar generation.",
    ),
    GrammarFile(
        "parser-zip",
        "https://www.lojban.org/files/software/parser/parser.zip",
        "1993-10-19",
        "Duplicate packaging retained as provenance only.",
    ),
    GrammarFile(
        "parser3-zip",
        "https://www.lojban.org/files/software/parser/PARSER3.ZIP",
        "1998-10-09",
        "DOS binary build retained in the archive as provenance only.",
    ),
    GrammarFile(
        "analyser",
        "https://lojban.org/files/software/analyser",
        "1993-08-07",
        "Nick Nicholas NU-Prolog semantic analyser; date is in the first line.",
    ),
    GrammarFile(
        "analyser-parser-paper",
        "https://lojban.org/files/papers/lojban_parser_paper",
        "1993-08-07",
        "Companion paper for the semantic analyser.",
    ),
    GrammarFile(
        "analyser-semantics-paper",
        "https://lojban.org/files/papers/nsn_semantics_paper",
        "1993-08-07",
        "Companion semantics paper for the analyser.",
    ),
    GrammarFile(
        "parser-3.0.00-tarball",
        "https://web.archive.org/web/20130116042930id_/http://ccil.org/~cowan/parser-3.0.00.tar.gz",
        "2003-11-13",
        "Wayback release tarball; contents duplicate the cll-parser submodule.",
    ),
)


class GrammarFetchError(ArchiveError):
    """A required grammar mirror could not be updated safely."""


@dataclass(frozen=True, slots=True)
class GrammarMirrorReport:
    source: GitGrammar
    mirror: Path
    manifest: Path
    refs: dict[str, str]
    reused_manifest: bool


@dataclass(frozen=True, slots=True)
class GrammarFetchReport:
    mirrors: tuple[GrammarMirrorReport, ...]
    vendor_manifests: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class HttpResponse:
    url: str
    body: bytes
    headers: Message


class VendorClient(Protocol):
    def get(self, url: str) -> HttpResponse: ...


class GrammarHttpClient:
    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        attempts: int = 4,
        timeout: float = 30.0,
        max_bytes: int = 128 * 1024 * 1024,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_interval < 0 or attempts < 1 or timeout <= 0 or max_bytes < 1:
            raise ValueError("invalid grammar HTTP client limits")
        self.min_interval = min_interval
        self.attempts = attempts
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request: float | None = None

    def _pace(self) -> None:
        current = self.monotonic()
        if self._last_request is not None:
            delay = self.min_interval - (current - self._last_request)
            if delay > 0:
                self.sleep(delay)
        self._last_request = self.monotonic()

    def get(self, url: str) -> HttpResponse:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            self._pace()
            request = Request(
                url, headers={"User-Agent": "jbomohi/0.1 grammar archiver"}
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    final_url = response.geturl()
                    parsed = urlsplit(final_url)
                    if (
                        parsed.scheme != "https"
                        or parsed.hostname not in ALLOWED_VENDOR_HOSTS
                    ):
                        raise GrammarFetchError(
                            f"grammar response escaped allowed origins: {final_url}"
                        )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise GrammarFetchError(
                            f"grammar response exceeds {self.max_bytes} bytes: {final_url}"
                        )
                    return HttpResponse(final_url, body, response.headers)
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504, 520, 521, 522, 523, 524}:
                    break
                delay = min(2**attempt, 60)
            except (URLError, OSError) as exc:
                last_error = exc
                delay = min(2**attempt, 60)
            if attempt + 1 < self.attempts:
                self.sleep(delay)
        raise GrammarFetchError(f"failed to fetch grammar source {url}: {last_error}")


CAMXES_ARCHIVE_URL = (
    "http://teddyb.org/~rlpowell/hobbies/lojban/grammar/hlg_backup__2011-01-11.tgz"
)


def ingest_camxes_backup(
    archive: Path,
    source: Path,
    *,
    fetched_at: datetime,
) -> Path:
    """Validate and content-address the locally mirrored camxes RCS backup."""

    if source.is_symlink() or not source.is_file():
        raise GrammarFetchError(f"camxes backup is not a regular file: {source}")
    try:
        with tarfile.open(source, "r:gz") as bundle:
            members = bundle.getmembers()
            by_name = {member.name: member for member in members}
            rcs_member = by_name.get("./RCS/lojban.peg,v")
            head_member = by_name.get("./lojban.peg")
            if (
                rcs_member is None
                or head_member is None
                or not rcs_member.isfile()
                or not head_member.isfile()
            ):
                raise GrammarFetchError(
                    "camxes backup lacks its RCS archive or head file"
                )
            rcs_stream = bundle.extractfile(rcs_member)
            head_stream = bundle.extractfile(head_member)
            if rcs_stream is None or head_stream is None:
                raise GrammarFetchError("camxes backup members are unreadable")
            revisions = parse_rcs(rcs_stream.read())
            if not revisions or revisions[-1].content != head_stream.read():
                raise GrammarFetchError("camxes RCS head disagrees with lojban.peg")
    except (OSError, tarfile.TarError) as exc:
        raise GrammarFetchError(f"cannot read camxes backup {source}: {exc}") from exc
    if len(revisions) != 39:
        raise GrammarFetchError(
            f"camxes lojban.peg RCS has {len(revisions)} revisions, expected 39"
        )
    stored = store_file(archive, source)
    manifest = ArchiveManifest(
        source="grammars/camxes",
        kind="rcs-archive",
        origin=CAMXES_ARCHIVE_URL,
        fetched_at=fetched_at,
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage={
            "from": revisions[0].timestamp.isoformat(timespec="seconds"),
            "to": revisions[-1].timestamp.isoformat(timespec="seconds"),
            "counts": {"files": len(members), "rcs_revisions": len(revisions)},
        },
        notes=(
            "Complete historical grammar backup mirrored from teddyb.org; "
            "RCS/lojban.peg,v replays internally and its head equals lojban.peg."
        ),
    )
    path = (
        archive
        / "manifests"
        / "grammars"
        / "vendor"
        / "camxes"
        / f"hlg_backup__2011-01-11-{stored.sha256}.toml"
    )
    if path.exists():
        existing = ArchiveManifest.load(path)
        if (
            existing.source != manifest.source
            or existing.kind != manifest.kind
            or existing.origin != manifest.origin
            or existing.sha256 != manifest.sha256
            or existing.bytes != manifest.bytes
            or existing.coverage != manifest.coverage
            or existing.notes != manifest.notes
        ):
            raise GrammarFetchError(f"existing camxes manifest disagrees: {path}")
    else:
        manifest.write(path)
    return path


def fetch_vendor_files(
    archive: Path,
    sources: Sequence[GrammarFile],
    *,
    fetched_at: datetime,
    client: VendorClient | None = None,
) -> tuple[Path, ...]:
    """Fetch immutable official, Wayback, and provenance-only grammar files."""

    http = client or GrammarHttpClient()
    manifests: list[Path] = []
    for source in sources:
        root = archive / "manifests" / "grammars" / "vendor" / source.key
        existing = sorted(root.glob("*.toml"))
        if len(existing) > 1:
            raise GrammarFetchError(
                f"grammar vendor source has multiple active manifests: {source.key}"
            )
        if existing:
            manifest = ArchiveManifest.load(existing[0])
            obj = object_path(archive, manifest.sha256)
            try:
                payload = obj.read_bytes()
            except OSError as exc:
                raise GrammarFetchError(
                    f"cached grammar vendor object is unreadable: {source.key}"
                ) from exc
            if (
                manifest.source != f"grammars/{source.key}"
                or manifest.kind != "grammar-file"
                or (
                    manifest.origin != source.url
                    and f"Requested URL: {source.url}." not in manifest.notes
                )
                or manifest.coverage["from"] != source.source_date
                or manifest.coverage["to"] != source.source_date
                or len(payload) != manifest.bytes
                or hashlib.sha256(payload).hexdigest() != manifest.sha256
            ):
                raise GrammarFetchError(
                    f"cached grammar vendor source is invalid: {source.key}"
                )
            manifests.append(existing[0])
            continue
        response = http.get(source.url)
        if not response.body:
            raise GrammarFetchError(f"grammar vendor source is empty: {source.url}")
        stored = store_object(archive, response.body)
        notes = source.note
        if response.url != source.url:
            notes += f" Requested URL: {source.url}."
        manifest = ArchiveManifest(
            source=f"grammars/{source.key}",
            kind="grammar-file",
            origin=response.url,
            fetched_at=fetched_at,
            sha256=stored.sha256,
            bytes=stored.bytes,
            coverage={
                "from": source.source_date,
                "to": source.source_date,
                "counts": {"files": 1},
            },
            notes=notes,
        )
        path = root / f"source-{stored.sha256}.toml"
        manifest.write(path)
        manifests.append(path)
    return tuple(manifests)


def _peel(mirror: Path, ref: str) -> str:
    result = run_git(
        mirror, ["rev-parse", "--verify", f"{ref}^{{commit}}"], check=False
    )
    object_id = result.stdout.strip()
    if result.returncode != 0 or not GIT_OBJECT_ID.fullmatch(object_id):
        raise GrammarFetchError(f"grammar mirror lacks commit ref {ref!r}")
    return object_id


def _commit_date(mirror: Path, object_id: str) -> datetime:
    raw = git_output(mirror, ["show", "-s", "--format=%cI", object_id])
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise GrammarFetchError(
            f"grammar commit has invalid date: {object_id}"
        ) from exc
    if value.tzinfo is None or value.microsecond:
        raise GrammarFetchError(f"grammar commit has invalid date: {object_id}")
    return value


def _previous_manifests(archive: Path, source: GitGrammar) -> list[ArchiveManifest]:
    root = archive / "manifests" / "grammars" / "git" / source.key
    result: list[ArchiveManifest] = []
    for path in sorted(root.glob("*.toml")):
        manifest = ArchiveManifest.load(path)
        if (
            manifest.source != f"grammars/{source.key}"
            or manifest.kind != "git-mirror"
            or manifest.origin != source.url
        ):
            raise GrammarFetchError(f"grammar manifest identity mismatch: {path}")
        result.append(manifest)
    return result


def _fetch_one(
    archive: Path,
    source: GitGrammar,
    fetched_at: datetime,
) -> GrammarMirrorReport:
    mirror = archive / "git" / "grammars" / f"{source.key}.git"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    if mirror.is_symlink():
        raise GrammarFetchError(f"grammar mirror must not be a symlink: {mirror}")
    if mirror.exists():
        if (
            not mirror.is_dir()
            or git_output(mirror, ["rev-parse", "--is-bare-repository"]) != "true"
        ):
            raise GrammarFetchError(f"grammar mirror is not bare: {mirror}")
        if git_output(mirror, ["remote", "get-url", "origin"]) != source.url:
            raise GrammarFetchError(f"grammar mirror origin mismatch: {source.key}")
        run_git(mirror, ["remote", "update", "--prune"])
    else:
        run_git(mirror.parent, ["clone", "--mirror", source.url, str(mirror)])

    ref_names = {source.branch_ref}
    ref_names.update(
        git_output(mirror, ["for-each-ref", "--format=%(refname)", "refs/tags"])
        .strip()
        .splitlines()
    )
    refs = {ref: _peel(mirror, ref) for ref in sorted(ref_names) if ref}
    previous = _previous_manifests(archive, source)
    for manifest in previous:
        old_refs = manifest.coverage.get("refs")
        if not isinstance(old_refs, dict):
            raise GrammarFetchError("prior grammar mirror manifest has no refs")
        for ref, old_object in old_refs.items():
            new_object = refs.get(ref)
            if new_object is None:
                raise GrammarFetchError(f"grammar ref was removed: {source.key} {ref}")
            if ref.startswith("refs/tags/") and new_object != old_object:
                raise GrammarFetchError(
                    f"grammar tag was rewritten: {source.key} {ref}"
                )
        old_branch = old_refs.get(source.branch_ref)
        new_branch = refs[source.branch_ref]
        if (
            old_branch is not None
            and old_branch != new_branch
            and run_git(
                mirror,
                ["merge-base", "--is-ancestor", old_branch, new_branch],
                check=False,
            ).returncode
            != 0
        ):
            raise GrammarFetchError(
                f"grammar default branch was not fast-forwarded: {source.key}"
            )

    payload = (
        json.dumps(
            {"origin": source.url, "refs": refs},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    stored = store_object(archive, payload)
    head = refs[source.branch_ref]
    first = git_output(
        mirror, ["rev-list", "--max-parents=0", "--reverse", head]
    ).splitlines()
    if not first:
        raise GrammarFetchError(f"grammar branch has no root commit: {source.key}")
    first_date = min(_commit_date(mirror, object_id) for object_id in first)
    head_date = _commit_date(mirror, head)
    manifest = ArchiveManifest(
        source=f"grammars/{source.key}",
        kind="git-mirror",
        origin=source.url,
        fetched_at=fetched_at,
        sha256=stored.sha256,
        bytes=stored.bytes,
        coverage={
            "from": first_date.isoformat(timespec="seconds"),
            "to": head_date.isoformat(timespec="seconds"),
            "counts": {
                "commits": int(git_output(mirror, ["rev-list", "--count", head])),
                "refs": len(refs),
                "tags": sum(ref.startswith("refs/tags/") for ref in refs),
            },
            "refs": refs,
        },
        notes="Bare upstream mirror scoped to the default branch and published tags.",
    )
    path = (
        archive
        / "manifests"
        / "grammars"
        / "git"
        / source.key
        / f"refs-{stored.sha256}.toml"
    )
    reused = path.exists()
    if not reused:
        manifest.write(path)
    return GrammarMirrorReport(source, mirror, path, refs, reused)


def fetch(
    archive: Path,
    *,
    sources: Sequence[GitGrammar] = GIT_GRAMMARS,
    vendor_sources: Sequence[GrammarFile] = (),
    camxes_backup: Path | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> GrammarFetchReport:
    """Refresh every required grammar mirror and archive its current refs."""

    fetched_at = now()
    if fetched_at.tzinfo is None:
        raise GrammarFetchError("grammar fetch time must include a UTC offset")
    mirrors = tuple(_fetch_one(archive, source, fetched_at) for source in sources)
    vendor_manifests = fetch_vendor_files(
        archive, vendor_sources, fetched_at=fetched_at
    )
    if camxes_backup is not None:
        vendor_manifests += (
            ingest_camxes_backup(archive, camxes_backup, fetched_at=fetched_at),
        )
    return GrammarFetchReport(mirrors, vendor_manifests)
