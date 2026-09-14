"""Pure projection of archived grammar repository pins."""

from __future__ import annotations

import csv
import gzip
import hashlib
import html
import io
import json
import re
import tarfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time
from itertools import pairwise
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ..archive.grammars import GIT_GRAMMARS, VENDOR_FILES, GitGrammar
from ..archive.manifest import ArchiveManifest, object_path
from ..git import Event, Identity, git_output, run_git
from .rcs import RcsRevision
from .rcs import parse as parse_rcs

INDEX_COLUMNS = (
    "name",
    "author",
    "language",
    "formalism",
    "dialect",
    "years",
    "mechanism",
    "upstream",
    "licence",
)
GAP_COLUMNS = ("name", "date", "reason", "evidence")
DUPLICATE_COLUMNS = ("duplicate", "canonical", "relation", "note")


class GrammarProjectError(ValueError):
    """Archived grammar source state cannot be projected unambiguously."""


@dataclass(frozen=True, slots=True)
class GrammarPin:
    source: GitGrammar
    object_id: str
    pinned_at: datetime
    commit_date: datetime
    author: Identity
    first_commit_date: datetime


CAMXES_INDEX_ROW = {
    "name": "camxes (RCS replay)",
    "author": "Robin Lee Powell",
    "language": "PEG",
    "formalism": "Parsing Expression Grammar",
    "dialect": "camxes standard",
    "years": "2004-2011",
    "mechanism": "replayed",
    "upstream": (
        "http://teddyb.org/~rlpowell/hobbies/lojban/grammar/hlg_backup__2011-01-11.tgz"
    ),
    "licence": "no licence",
}
ZASNI_INDEX_ROW = {
    "name": "zasni gerna (xorxes)",
    "author": "Jorge Llambías (xorxes)",
    "language": "PEG",
    "formalism": "Parsing Expression Grammar",
    "dialect": "zasni gerna; unofficial",
    "years": "2015",
    "mechanism": "vendor",
    "upstream": "wiki:zasni gerna@revid=111176",
    "licence": "Lojban wiki terms",
}
VENDOR_INDEX_ROWS = (
    {
        "name": "Official LLG grammar lineage",
        "author": "Logical Language Group",
        "language": "YACC / BNF",
        "formalism": "YACC and EBNF generations",
        "dialect": "official baselines 1-3",
        "years": "1989-1997",
        "mechanism": "vendor",
        "upstream": "https://lojban.org/files/history/",
        "licence": "LLG permission grant; 3rd baseline public domain",
    },
    {
        "name": "Official LLG parser (2nd baseline)",
        "author": "John Cowan for LLG",
        "language": "K&R C + YACC",
        "formalism": "YACC + lexer pre-pass",
        "dialect": "2nd baseline",
        "years": "1989-1993",
        "mechanism": "vendor",
        "upstream": "https://www.lojban.org/files/software/parser/parser.shar.gz",
        "licence": "LLG permission grant",
    },
    {
        "name": "Lojban semantic analyser",
        "author": "Nick Nicholas",
        "language": "NU-Prolog + lex",
        "formalism": "semantic analyser over official parser output",
        "dialect": "2nd baseline",
        "years": "1993",
        "mechanism": "vendor",
        "upstream": "https://lojban.org/files/software/analyser",
        "licence": "LLG permission grant",
    },
)
CATALOGUE_ROWS = (
    (
        "camxes git snapshot",
        "Robin Lee Powell",
        "PEG",
        "PEG",
        "camxes standard",
        "2011",
        "cite",
        "https://github.com/lojban/camxes",
        "no licence",
    ),
    (
        "gentufa",
        "mezohe",
        "JavaScript",
        "PEG.js",
        "standard",
        "2014-2021",
        "cite",
        "https://github.com/mezohe/gentufa",
        "MIT",
    ),
    (
        "lojbanParser",
        "Yoshikuni Jujo",
        "Haskell",
        "parser",
        "pre-zasni",
        "2012-2014",
        "cite",
        "https://github.com/YoshikuniJujo/lojban_parser",
        "no licence in repo",
    ),
    (
        "lojysamban",
        "Yoshikuni Jujo",
        "Haskell",
        "parser consumer",
        "lojbanParser",
        "2012-2014",
        "cite",
        "https://github.com/YoshikuniJujo/lojysamban",
        "BSD-3-Clause",
    ),
    (
        "cakyrespa",
        "Yoshikuni Jujo",
        "Haskell",
        "parser consumer",
        "lojbanParser",
        "2012",
        "cite",
        "https://github.com/YoshikuniJujo/cakyrespa",
        "BSD-3-Clause",
    ),
    (
        "python-camxes",
        "LLG contributors",
        "Python",
        "JVM bridge",
        "camxes standard",
        "2011-2014",
        "cite",
        "https://github.com/lojban/python-camxes",
        "BSD-2-Clause",
    ),
    (
        "visual-camxes",
        "dag; LLG contributors",
        "JavaScript",
        "front-end",
        "camxes standard",
        "2011-2021",
        "cite",
        "https://github.com/lojban/visual-camxes",
        "MIT",
    ),
    (
        "zirsam",
        "purpleposeidon",
        "Python",
        "hand-written",
        "camxes-era",
        "2009-2011",
        "cite",
        "https://github.com/lojban/zirsam",
        "no licence",
    ),
    (
        "sneturfahi",
        "Matt F. Bacon",
        "Rust",
        "hand-written",
        "standard",
        "2022-2023",
        "cite",
        "https://github.com/mattfbacon/sneturfahi",
        "AGPL-3.0",
    ),
    (
        "nei",
        "lynn",
        "TypeScript",
        "modern parser",
        "standard",
        "2025",
        "cite",
        "https://github.com/lynn/nei",
        "no licence",
    ),
    (
        "sotygeha",
        "IGJoshua",
        "PEG",
        "zantufa-derived",
        "sotygeha",
        "2019-2020",
        "cite",
        "https://github.com/IGJoshua/sotygeha",
        "no licence",
    ),
    (
        "typed-lojban",
        "himikof",
        "Haskell",
        "parser",
        "experimental",
        "unknown",
        "cite",
        "https://github.com/himikof/typed-lojban",
        "not verified",
    ),
    (
        "genrei",
        "zhuangzi",
        "Haskell",
        "parser",
        "experimental",
        "unknown",
        "cite",
        "https://github.com/zhuangzi/genrei",
        "not verified",
    ),
    (
        "camxes-rs",
        "unknown",
        "Rust",
        "generic PEG generator",
        "not a Lojban parser",
        "2024-2026",
        "skip",
        "https://github.com/lojban/camxes-rs",
        "no licence",
    ),
)
GAP_ROWS = (
    {
        "name": "grammar.a27",
        "date": "before 1989-02-25",
        "reason": "referenced by surviving drafts but never published",
        "evidence": "GRAMMAR.B17 and GRAMMAR.NEW headers",
    },
    {
        "name": "grammar.235",
        "date": "1994-03-29",
        "reason": "YACC form never published; BNF form survives",
        "evidence": "1999-2000 Wayback machine-grammars listings and 404 captures",
    },
    {
        "name": "grammar.247",
        "date": "1996-12-20",
        "reason": "YACC form never published; BNF form survives",
        "evidence": "1999-2000 Wayback machine-grammars listings and 404 captures",
    },
    {
        "name": "jbominji",
        "date": "unknown",
        "reason": "source host no longer resolves; grammar not recovered",
        "evidence": "inventory section 4.4",
    },
)
DUPLICATE_ROWS = (
    {
        "duplicate": "grammars/camxes backup grammar.300 and lojban.bnf",
        "canonical": "cll/src scripts/yacc/lojban_grammar.y and third-baseline bnf.300",
        "relation": "byte-identical",
        "note": "not projected twice",
    },
    {
        "duplicate": "ilmentufa camxes-pamoi.peg",
        "canonical": "grammars/camxes/rcs/lojban.peg at 1.39",
        "relation": "same grammar with one trailing blank line",
        "note": "retained only inside the ilmentufa submodule context",
    },
    {
        "duplicate": "lojban/camxes git snapshot at 1c1d9ec",
        "canonical": "grammars/camxes/rcs/lojban.peg at 1.39",
        "relation": "same grammar minus comments",
        "note": "snapshot repository is cite-only",
    },
    {
        "duplicate": "parser-3.0.00.tar.gz",
        "canonical": "grammars/official/parser/cll-parser gitlink",
        "relation": "same release contents",
        "note": "tarball retained as provenance only",
    },
    {
        "duplicate": "lojban/jbogenturfahi",
        "canonical": "alanpost/jbogenturfahi and alanpost/genturfahi",
        "relation": "squashed mirror",
        "note": "four-commit copy excluded",
    },
)

VENDOR_GROUPS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "official-1989-02-25",
        "1989-02-25",
        (("history-grammar.e25", "grammars/official/1989-02-25/GRAMMAR.E25"),),
    ),
    (
        "official-1989-09-23",
        "1989-09-23",
        (("history-grammar.l23", "grammars/official/1989-09-23/GRAMMAR.L23"),),
    ),
    (
        "official-1990-05-06",
        "1990-05-06",
        (("history-grammar.506", "grammars/official/1990-05-06/GRAMMAR.506"),),
    ),
    (
        "official-1990-07-20",
        "1990-07-20",
        (
            ("history-grammar.b17", "grammars/official/1990-07-20/GRAMMAR.B17"),
            ("history-grammar.new", "grammars/official/1990-07-20/GRAMMAR.NEW"),
            ("history-grammar.28", "grammars/official/1990-07-20/GRAMMAR.28"),
            ("history-bnf.28", "grammars/official/1990-07-20/BNF.28"),
            ("history-techfix.28", "grammars/official/1990-07-20/techfix.28"),
        ),
    ),
    (
        "official-1991-06-23",
        "1991-06-23",
        (("second-bnf-28", "grammars/official/1991-06-23/bnf.28"),),
    ),
    (
        "official-1994-03-29",
        "1994-03-29",
        (
            ("second-bnf-235", "grammars/official/1994-03-29/bnf.235"),
            ("second-techfix-235", "grammars/official/1994-03-29/techfix.235"),
        ),
    ),
    (
        "official-1996-03-20",
        "1996-03-20",
        (("second-bnf-246", "grammars/official/1996-03-20/bnf.246"),),
    ),
    (
        "official-1996-12-20",
        "1996-12-20",
        (("second-bnf-247", "grammars/official/1996-12-20/bnf.247"),),
    ),
    (
        "official-1997-01-10",
        "1997-01-10",
        (
            ("third-bnf.300", "grammars/official/1997-01-10/bnf.300"),
            ("third-techfix.300", "grammars/official/1997-01-10/techfix.300"),
            ("third-xref.300", "grammars/official/1997-01-10/xref.300"),
            ("third-pd", "grammars/official/1997-01-10/PD"),
        ),
    ),
)
CAMXES_SUPPORT_GROUPS: tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "conversion-2004-03-28",
        "2004-03-28",
        "2004-03-28",
        (
            ("./abnf2peg.pl", "conversion/abnf2peg.pl"),
            ("./bnf.vim", "conversion/bnf.vim"),
            ("./bnf_conv.pl", "conversion/bnf_conv.pl"),
            ("./jc_mail.txt", "conversion/jc_mail.txt"),
            ("./lojban.abnf", "conversion/lojban.abnf"),
            ("./lojban2.bnf", "conversion/lojban2.bnf"),
            ("./orig_lojban.peg", "conversion/orig_lojban.peg"),
            ("./old/abnf2bison.pl", "conversion/old/abnf2bison.pl"),
            ("./old/new.abnf.old", "conversion/old/new.abnf.old"),
            ("./old/new_diffs.txt.old", "conversion/old/new_diffs.txt.old"),
            ("./earley/abnf2e2.pl", "conversion/earley/abnf2e2.pl"),
            ("./earley/abnf2earley.pl", "conversion/earley/abnf2earley.pl"),
            ("./earley/earley.pl", "conversion/earley/earley.pl"),
            ("./earley/new.earley", "conversion/earley/new.earley"),
            ("./earley/page.html", "conversion/earley/page.html"),
        ),
    ),
    (
        "tests-2005-01-28",
        "2005-01-28",
        "2005-01-28",
        (("./test_sentences.txt", "test_sentences.txt"),),
    ),
    (
        "morph-tests-2005-02-25",
        "2005-02-25",
        "2005-02-25",
        (("./morph_test_sentences.txt", "morph_test_sentences.txt"),),
    ),
    (
        "rats-support-2005-12",
        "2005-12-16",
        "2005-12-17",
        (
            ("./morph_header.peg", "morph_header.peg"),
            ("./rats/Howto.cook", "rats/Howto.cook"),
            ("./rats/peg2rats.pl", "rats/peg2rats.pl"),
        ),
    ),
    (
        "morphology-2007-05-30",
        "2007-05-30",
        "2007-05-30",
        (("./lojban_morphology_old.peg", "lojban_morphology_old.peg"),),
    ),
)
CAMXES_MEMBER_TIMES = {
    "./abnf2peg.pl": "2004-03-17T20:08:59+00:00",
    "./bnf.vim": "2004-02-10T23:32:20+00:00",
    "./bnf_conv.pl": "2004-02-10T22:27:01+00:00",
    "./jc_mail.txt": "2004-02-10T23:24:06+00:00",
    "./lojban.abnf": "2004-03-28T18:46:28+00:00",
    "./lojban2.bnf": "2004-02-11T00:22:28+00:00",
    "./orig_lojban.peg": "2004-03-17T20:08:46+00:00",
    "./old/abnf2bison.pl": "2004-02-11T22:59:49+00:00",
    "./old/new.abnf.old": "2004-02-11T00:46:39+00:00",
    "./old/new_diffs.txt.old": "2004-02-11T01:04:10+00:00",
    "./earley/abnf2e2.pl": "2004-02-16T09:13:17+00:00",
    "./earley/abnf2earley.pl": "2004-02-12T00:39:49+00:00",
    "./earley/earley.pl": "2004-02-13T18:30:44+00:00",
    "./earley/new.earley": "2004-02-20T20:57:39+00:00",
    "./earley/page.html": "2004-03-16T20:21:03+00:00",
    "./test_sentences.txt": "2005-01-28T19:16:33+00:00",
    "./morph_test_sentences.txt": "2005-02-25T22:00:35+00:00",
    "./morph_header.peg": "2005-12-16T23:35:44+00:00",
    "./rats/Howto.cook": "2005-12-16T23:41:27+00:00",
    "./rats/peg2rats.pl": "2005-12-17T00:00:39+00:00",
    "./lojban_morphology_old.peg": "2007-05-30T07:49:56+00:00",
}


def _manifest_refs(
    archive: Path, source: GitGrammar, manifest: ArchiveManifest
) -> dict[str, str]:
    if (
        manifest.source != f"grammars/{source.key}"
        or manifest.kind != "git-mirror"
        or manifest.origin != source.url
    ):
        raise GrammarProjectError(f"grammar manifest identity mismatch: {source.key}")
    raw_refs = manifest.coverage.get("refs")
    if not isinstance(raw_refs, dict) or source.branch_ref not in raw_refs:
        raise GrammarProjectError(f"grammar manifest lacks branch ref: {source.key}")
    refs = dict(raw_refs)
    obj = object_path(archive, manifest.sha256)
    try:
        payload = obj.read_bytes()
    except OSError as exc:
        raise GrammarProjectError(
            f"grammar ref record is unreadable: {source.key}"
        ) from exc
    if (
        len(payload) != manifest.bytes
        or hashlib.sha256(payload).hexdigest() != manifest.sha256
    ):
        raise GrammarProjectError(f"grammar ref record is corrupt: {source.key}")
    try:
        record = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GrammarProjectError(
            f"grammar ref record is invalid JSON: {source.key}"
        ) from exc
    if record != {"origin": source.url, "refs": refs}:
        raise GrammarProjectError(
            f"grammar ref record disagrees with manifest: {source.key}"
        )
    return refs


def _commit_fields(mirror: Path, object_id: str) -> tuple[Identity, datetime]:
    raw = run_git(
        mirror,
        ["show", "-s", "--format=%an%x00%ae%x00%cI", object_id],
    ).stdout.rstrip("\n")
    try:
        name, email, date_text = raw.split("\0")
        commit_date = datetime.fromisoformat(date_text)
    except ValueError as exc:
        raise GrammarProjectError(
            f"grammar commit metadata is invalid: {object_id}"
        ) from exc
    if commit_date.tzinfo is None or commit_date.microsecond:
        raise GrammarProjectError(f"grammar commit date is invalid: {object_id}")
    try:
        author = Identity.upstream(name, email)
    except ValueError as exc:
        raise GrammarProjectError(
            f"grammar commit author cannot be preserved: {object_id}: {exc}"
        ) from exc
    return author, commit_date


def _commit_date(mirror: Path, object_id: str) -> datetime:
    raw = git_output(mirror, ["show", "-s", "--format=%cI", object_id])
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise GrammarProjectError(
            f"grammar commit date is invalid: {object_id}"
        ) from exc
    if value.tzinfo is None or value.microsecond:
        raise GrammarProjectError(f"grammar commit date is invalid: {object_id}")
    return value


def _pins(archive: Path, source: GitGrammar) -> list[GrammarPin]:
    root = archive / "manifests" / "grammars" / "git" / source.key
    manifests = [ArchiveManifest.load(path) for path in sorted(root.glob("*.toml"))]
    if not manifests:
        raise GrammarProjectError(f"grammar mirror manifest is absent: {source.key}")
    mirror = archive / "git" / "grammars" / f"{source.key}.git"
    if mirror.is_symlink() or not mirror.is_dir():
        raise GrammarProjectError(f"grammar bare mirror is absent: {source.key}")
    if git_output(mirror, ["rev-parse", "--is-bare-repository"]) != "true":
        raise GrammarProjectError(f"grammar mirror is not bare: {source.key}")
    if git_output(mirror, ["remote", "get-url", "origin"]) != source.url:
        raise GrammarProjectError(f"grammar mirror origin mismatch: {source.key}")

    by_commit: dict[str, datetime] = {}
    latest: tuple[ArchiveManifest, dict[str, str]] | None = None
    for manifest in manifests:
        refs = _manifest_refs(archive, source, manifest)
        object_id = refs[source.branch_ref]
        previous = by_commit.get(object_id)
        if previous is None or manifest.fetched_at < previous:
            by_commit[object_id] = manifest.fetched_at
        candidate = (manifest, refs)
        if latest is None or (
            len(refs),
            manifest.fetched_at,
            manifest.sha256,
        ) > (
            len(latest[1]),
            latest[0].fetched_at,
            latest[0].sha256,
        ):
            latest = candidate
    assert latest is not None
    actual_refs = {
        source.branch_ref: git_output(
            mirror, ["rev-parse", "--verify", f"{source.branch_ref}^{{commit}}"]
        )
    }
    for ref in git_output(
        mirror, ["for-each-ref", "--format=%(refname)", "refs/tags"]
    ).splitlines():
        actual_refs[ref] = git_output(
            mirror, ["rev-parse", "--verify", f"{ref}^{{commit}}"]
        )
    if actual_refs != latest[1]:
        raise GrammarProjectError(
            f"grammar mirror refs changed after fetch: {source.key}"
        )

    roots = git_output(
        mirror,
        ["rev-list", "--max-parents=0", "--reverse", latest[1][source.branch_ref]],
    ).splitlines()
    if not roots:
        raise GrammarProjectError(f"grammar mirror has no root commit: {source.key}")
    first_date = min(_commit_date(mirror, object_id) for object_id in roots)
    pins = []
    for object_id, pinned_at in by_commit.items():
        result = run_git(
            mirror, ["cat-file", "-e", f"{object_id}^{{commit}}"], check=False
        )
        if result.returncode != 0:
            raise GrammarProjectError(
                f"grammar pin object is absent: {source.key} {object_id}"
            )
        author, commit_date = _commit_fields(mirror, object_id)
        pins.append(
            GrammarPin(
                source,
                object_id,
                pinned_at,
                commit_date,
                author,
                first_date,
            )
        )
    pins.sort(key=lambda item: (item.commit_date, item.object_id))
    for previous, following in pairwise(pins):
        if (
            run_git(
                mirror,
                [
                    "merge-base",
                    "--is-ancestor",
                    previous.object_id,
                    following.object_id,
                ],
                check=False,
            ).returncode
            != 0
        ):
            raise GrammarProjectError(f"grammar pin history diverges: {source.key}")
    return pins


def _upstream_toml(pin: GrammarPin) -> str:
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    return "\n".join(
        (
            f"url = {quote(pin.source.url)}",
            f"default_branch = {quote(pin.source.default_branch)}",
            f"pinned_commit = {quote(pin.object_id)}",
            f"pinned_at = {quote(pin.pinned_at.isoformat(timespec='seconds'))}",
            f"first_commit_date = {quote(pin.first_commit_date.isoformat(timespec='seconds'))}",
            f"licence = {quote(pin.source.licence)}",
            "",
        )
    )


def _vendor_manifest(archive: Path, key: str) -> tuple[ArchiveManifest, bytes]:
    root = archive / "manifests" / "grammars" / "vendor" / key
    paths = sorted(root.glob("*.toml"))
    if len(paths) != 1:
        raise GrammarProjectError(
            f"expected one grammar vendor manifest for {key}, found {len(paths)}"
        )
    manifest = ArchiveManifest.load(paths[0])
    if manifest.source != f"grammars/{key}" or manifest.kind != "grammar-file":
        raise GrammarProjectError(f"grammar vendor manifest identity mismatch: {key}")
    obj = object_path(archive, manifest.sha256)
    try:
        payload = obj.read_bytes()
    except OSError as exc:
        raise GrammarProjectError(
            f"grammar vendor object is unreadable: {key}"
        ) from exc
    if (
        len(payload) != manifest.bytes
        or hashlib.sha256(payload).hexdigest() != manifest.sha256
    ):
        raise GrammarProjectError(f"grammar vendor object is corrupt: {key}")
    return manifest, payload


def _text(payload: bytes, label: str) -> bytes:
    if payload.startswith(b"\xef\xbb\xbf") or b"\0" in payload:
        raise GrammarProjectError(f"grammar text is not UTF-8/LF-safe: {label}")
    payload = payload.replace(b"\r\n", b"\n")
    if b"\r" in payload:
        raise GrammarProjectError(f"grammar text contains a bare CR: {label}")
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GrammarProjectError(f"grammar text is not UTF-8: {label}") from exc
    return payload


def escape_mixed_bytes(payload: bytes, original: str) -> bytes:
    """Render mixed UTF-8/legacy bytes injectively as UTF-8 text."""

    if "\n" in original or "\r" in original or "\0" in original:
        raise GrammarProjectError("escaped grammar source name must be one line")
    decoded = payload.decode("utf-8", errors="surrogateescape")
    rendered: list[str] = []
    for character in decoded:
        value = ord(character)
        if character == "\\":
            rendered.append("\\\\")
        elif 0xDC80 <= value <= 0xDCFF:
            rendered.append(f"\\x{value - 0xDC00:02X}")
        else:
            rendered.append(character)
    header = (
        "# grammar source bytes escaped by jbomohi grammar-bytes/1 | "
        f"original={original}\n"
    )
    return (header + "".join(rendered)).encode()


def unescape_mixed_bytes(rendered: bytes) -> bytes:
    """Reverse ``escape_mixed_bytes`` for verification and tests."""

    try:
        text = rendered.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GrammarProjectError("escaped grammar source is not UTF-8") from exc
    header, separator, body = text.partition("\n")
    if not separator or not header.startswith(
        "# grammar source bytes escaped by jbomohi grammar-bytes/1 | original="
    ):
        raise GrammarProjectError("escaped grammar source has an invalid header")
    result = bytearray()
    index = 0
    while index < len(body):
        character = body[index]
        if character != "\\":
            result.extend(character.encode())
            index += 1
            continue
        if body.startswith("\\\\", index):
            result.append(ord("\\"))
            index += 2
            continue
        escaped = body[index + 2 : index + 4]
        if (
            not body.startswith("\\x", index)
            or len(escaped) != 2
            or not re.fullmatch(r"[0-9A-F]{2}", escaped)
        ):
            raise GrammarProjectError(
                "escaped grammar source has an invalid byte escape"
            )
        result.append(int(escaped, 16))
        index += 4
    return bytes(result)


def _unshar(payload: bytes) -> dict[str, bytes]:
    try:
        source = gzip.decompress(payload)
    except (OSError, EOFError) as exc:
        raise GrammarProjectError("official parser shar is not valid gzip") from exc
    pattern = re.compile(
        rb"""sed "s/\^X//" >'(?P<path>[^']+)' <<'END_OF_FILE'\n"""
        rb"(?P<body>.*?)\nEND_OF_FILE\n",
        re.DOTALL,
    )
    files: dict[str, bytes] = {}
    for matched in pattern.finditer(source):
        try:
            path = matched["path"].decode("ascii")
        except UnicodeDecodeError as exc:
            raise GrammarProjectError("parser shar contains a non-ASCII path") from exc
        candidate = Path(path)
        if (
            candidate.is_absolute()
            or len(candidate.parts) != 1
            or candidate.name in {"", ".", ".."}
            or path in files
        ):
            raise GrammarProjectError(f"parser shar contains an unsafe path: {path!r}")
        lines = (matched["body"] + b"\n").splitlines(keepends=True)
        if any(not line.startswith(b"X") for line in lines):
            raise GrammarProjectError(f"parser shar body lacks X prefix: {path}")
        files[path] = b"".join(line[1:] for line in lines)
    contents = re.search(rb"# Contents: (?P<value>.*?)\n# Wrapped", source, re.DOTALL)
    if contents is None:
        raise GrammarProjectError("parser shar has no contents list")
    try:
        expected = {
            name.decode("ascii")
            for name in contents["value"].replace(b"#   ", b"").split()
        }
    except UnicodeDecodeError as exc:
        raise GrammarProjectError("parser shar contents list is not ASCII") from exc
    if not files or set(files) != expected:
        raise GrammarProjectError(
            "parser shar contents list disagrees with extracted files"
        )
    return files


def _vendor_events(archive: Path) -> list[Event]:
    payloads = {
        source.key: _vendor_manifest(archive, source.key)[1] for source in VENDOR_FILES
    }
    events: list[Event] = []
    for source_id, date_text, entries in VENDOR_GROUPS:
        changes = {target: _text(payloads[key], key) for key, target in entries}
        source_day = date.fromisoformat(date_text)
        trailers = {"Grammar": "official"}
        if source_id == "official-1990-07-20":
            trailers["Includes-Undated"] = "GRAMMAR.B17, GRAMMAR.NEW"
        events.append(
            Event(
                source="grammars",
                source_id=f"grammars/{source_id}",
                event="import",
                time_confidence="window",
                source_time=datetime.combine(source_day, time.max, UTC).replace(
                    microsecond=0
                ),
                event_window=f"{date_text}..{date_text}",
                summary=source_id.replace("official-", "official "),
                author=Identity.document("lojban.org", "Logical Language Group", "llg"),
                changes=changes,
                trailers=trailers,
            )
        )

    shar = _unshar(payloads["parser-shar"])
    grammar_names = {"grammar.233", "bnf.233", "techfix.233"}
    generation_day = date(1993, 6, 22)
    events.append(
        Event(
            source="grammars",
            source_id="grammars/official-2.33",
            event="import",
            time_confidence="window",
            source_time=datetime.combine(generation_day, time.max, UTC).replace(
                microsecond=0
            ),
            event_window="1993-06-22..1993-06-22",
            summary="official grammar 2.33",
            author=Identity.document("lojban.org", "Logical Language Group", "llg"),
            changes={
                f"grammars/official/1993-06-22/{name}": _text(shar[name], name)
                for name in sorted(grammar_names)
            },
            trailers={"Grammar": "official"},
        )
    )
    parser_day = date(1993, 10, 19)
    events.append(
        Event(
            source="grammars",
            source_id="grammars/official-parser-1993",
            event="import",
            time_confidence="window",
            source_time=datetime.combine(parser_day, time.max, UTC).replace(
                microsecond=0
            ),
            event_window="1993-10-19..1993-10-19",
            summary="official parser source 1993",
            author=Identity.document("lojban.org", "John Cowan", "john-cowan"),
            changes={
                f"grammars/official/parser/2nd-baseline/{name}": _text(payload, name)
                for name, payload in sorted(shar.items())
                if name not in grammar_names
            },
            trailers={"Grammar": "official-parser"},
        )
    )
    analyser_day = date(1993, 8, 7)
    events.append(
        Event(
            source="grammars",
            source_id="grammars/analyser-1993",
            event="import",
            time_confidence="window",
            source_time=datetime.combine(analyser_day, time.max, UTC).replace(
                microsecond=0
            ),
            event_window="1993-08-07..1993-08-07",
            summary="Nick Nicholas analyser 1993",
            author=Identity.document("lojban.org", "Nick Nicholas", "nick-nicholas"),
            changes={
                "grammars/official/analyser/analyser": _text(
                    payloads["analyser"], "analyser"
                ),
                "grammars/official/analyser/lojban_parser_paper": _text(
                    payloads["analyser-parser-paper"], "analyser-parser-paper"
                ),
                "grammars/official/analyser/nsn_semantics_paper": _text(
                    payloads["analyser-semantics-paper"],
                    "analyser-semantics-paper",
                ),
            },
            trailers={"Grammar": "analyser"},
        )
    )
    for event in events:
        event.validate()
    return events


def _camxes_archive_object(archive: Path) -> tuple[ArchiveManifest, Path]:
    root = archive / "manifests" / "grammars" / "vendor" / "camxes"
    paths = sorted(root.glob("*.toml"))
    if len(paths) != 1:
        raise GrammarProjectError(
            f"expected one camxes archive manifest, found {len(paths)}"
        )
    manifest = ArchiveManifest.load(paths[0])
    if manifest.source != "grammars/camxes" or manifest.kind != "rcs-archive":
        raise GrammarProjectError("camxes RCS archive manifest identity mismatch")
    obj = object_path(archive, manifest.sha256)
    try:
        payload = obj.read_bytes()
    except OSError as exc:
        raise GrammarProjectError("camxes archive object is unreadable") from exc
    if (
        len(payload) != manifest.bytes
        or hashlib.sha256(payload).hexdigest() != manifest.sha256
    ):
        raise GrammarProjectError("camxes archive object is corrupt")
    return manifest, obj


def _camxes_rcs(archive: Path) -> list[RcsRevision]:
    _manifest, obj = _camxes_archive_object(archive)
    try:
        with tarfile.open(obj, "r:*") as bundle:
            rcs_member = bundle.getmember("./RCS/lojban.peg,v")
            head_member = bundle.getmember("./lojban.peg")
            if not rcs_member.isfile() or not head_member.isfile():
                raise GrammarProjectError("camxes archive source members are not files")
            rcs_stream = bundle.extractfile(rcs_member)
            head_stream = bundle.extractfile(head_member)
            if rcs_stream is None or head_stream is None:
                raise GrammarProjectError(
                    "camxes archive source members are unreadable"
                )
            revisions = parse_rcs(rcs_stream.read())
            if not revisions or revisions[-1].content != head_stream.read():
                raise GrammarProjectError(
                    "camxes replay head disagrees with lojban.peg"
                )
    except (OSError, KeyError, tarfile.TarError) as exc:
        raise GrammarProjectError(f"cannot read camxes RCS archive: {exc}") from exc
    if len(revisions) != 39:
        raise GrammarProjectError(
            f"camxes RCS replay has {len(revisions)} revisions, expected 39"
        )
    return revisions


def _camxes_members(
    archive: Path, names: Iterable[str]
) -> tuple[ArchiveManifest, dict[str, bytes]]:
    manifest, obj = _camxes_archive_object(archive)
    result: dict[str, bytes] = {}
    try:
        with tarfile.open(obj, "r:*") as bundle:
            for name in names:
                member = bundle.getmember(name)
                if not member.isfile():
                    raise GrammarProjectError(
                        f"camxes support member is not a file: {name}"
                    )
                stream = bundle.extractfile(member)
                if stream is None:
                    raise GrammarProjectError(
                        f"camxes support member is unreadable: {name}"
                    )
                expected_time = CAMXES_MEMBER_TIMES.get(name)
                actual_time = datetime.fromtimestamp(member.mtime, UTC).isoformat()
                if expected_time is not None and actual_time != expected_time:
                    raise GrammarProjectError(
                        f"camxes support member time changed: {name}"
                    )
                result[name] = stream.read()
    except (OSError, KeyError, tarfile.TarError) as exc:
        raise GrammarProjectError(f"cannot read camxes support archive: {exc}") from exc
    return manifest, result


def _camxes_support_events(archive: Path) -> list[Event]:
    names = {
        source
        for _source_id, _start, _end, entries in CAMXES_SUPPORT_GROUPS
        for source, _target in entries
    }
    _manifest, members = _camxes_members(archive, names)
    events = []
    for source_id, _start, _end, entries in CAMXES_SUPPORT_GROUPS:
        source_time = max(
            datetime.fromisoformat(CAMXES_MEMBER_TIMES[source])
            for source, _target in entries
        )
        event = Event(
            source="grammars",
            source_id=f"grammars/camxes-support={source_id}",
            event="import",
            time_confidence="exact",
            source_time=source_time,
            summary=f"camxes support {source_id}",
            author=Identity.namespaced("teddyb.org", "rlpowell"),
            changes={
                f"grammars/camxes/support/{target}": (
                    escape_mixed_bytes(members[source], source)
                    if source in {"./test_sentences.txt", "./morph_test_sentences.txt"}
                    else _text(members[source], source)
                )
                for source, target in entries
            },
            trailers={"Grammar": "camxes"},
        )
        event.validate()
        events.append(event)
    return events


def _zasni_event(archive: Path) -> Event:
    root = archive / "manifests" / "wiki" / "revisions"
    found: list[tuple[dict[str, object], dict[str, object]]] = []
    for path in sorted(root.glob("*.toml")):
        manifest = ArchiveManifest.load(path)
        query = parse_qs(urlsplit(manifest.origin).query)
        if query.get("titles") != ["zasni gerna"]:
            continue
        obj = object_path(archive, manifest.sha256)
        try:
            payload = obj.read_bytes()
        except OSError as exc:
            raise GrammarProjectError("zasni gerna wiki object is unreadable") from exc
        if (
            len(payload) != manifest.bytes
            or hashlib.sha256(payload).hexdigest() != manifest.sha256
        ):
            raise GrammarProjectError("zasni gerna wiki object is corrupt")
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GrammarProjectError(
                "zasni gerna wiki response is invalid JSON"
            ) from exc
        query_value = document.get("query") if isinstance(document, dict) else None
        pages = query_value.get("pages", []) if isinstance(query_value, dict) else []
        if not isinstance(pages, list):
            raise GrammarProjectError("zasni gerna wiki response has no pages")
        for page_value in pages:
            if (
                not isinstance(page_value, dict)
                or page_value.get("title") != "zasni gerna"
            ):
                continue
            revisions = page_value.get("revisions", [])
            if not isinstance(revisions, list):
                raise GrammarProjectError("zasni gerna wiki response has no revisions")
            found.extend(
                (page_value, revision)
                for revision in revisions
                if isinstance(revision, dict) and revision.get("revid") == 111176
            )
    if len(found) != 1:
        raise GrammarProjectError(
            f"expected wiki revid 111176 for zasni gerna, found {len(found)}"
        )
    page, revision = found[0]
    if page.get("pageid") != 2535:
        raise GrammarProjectError("zasni gerna wiki page id changed")
    slots = revision.get("slots")
    main = slots.get("main") if isinstance(slots, dict) else None
    content = main.get("content") if isinstance(main, dict) else None
    if not isinstance(content, str):
        raise GrammarProjectError("zasni gerna revision has no wikitext")
    blocks = re.findall(r"<pre>\s*\n?(.*?)\n?\s*</pre>", content, re.DOTALL)
    if len(blocks) != 1 or not blocks[0].strip():
        raise GrammarProjectError("zasni gerna revision does not contain one PEG block")
    timestamp = revision.get("timestamp")
    user = revision.get("user")
    if not isinstance(timestamp, str) or not isinstance(user, str):
        raise GrammarProjectError("zasni gerna revision lacks timestamp or user")
    try:
        if not timestamp.endswith("Z"):
            raise ValueError
        source_time = datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise GrammarProjectError("zasni gerna revision timestamp is invalid") from exc
    if source_time.tzinfo is None or source_time.microsecond:
        raise GrammarProjectError("zasni gerna revision timestamp is invalid")
    event = Event(
        source="grammars",
        source_id="grammars/zasni-xorxes=revid=111176",
        event="import",
        time_confidence="exact",
        source_time=source_time,
        summary="extract xorxes zasni gerna revid 111176",
        author=Identity.namespaced("mw.lojban.org", user),
        changes={
            "grammars/zasni-gerna/xorxes/zasni-gerna.peg": (
                html.unescape(blocks[0]).rstrip() + "\n"
            )
        },
        trailers={"Grammar": "zasni-gerna", "Wiki-Revision": "111176"},
    )
    event.validate()
    return event


def _provenance(archive: Path) -> dict[str, str]:
    rows: dict[str, list[dict[str, object]]] = {
        "official": [],
        "official-parser": [],
        "analyser": [],
        "camxes": [],
    }
    for source in VENDOR_FILES:
        manifest, _payload = _vendor_manifest(archive, source.key)
        category = (
            "analyser"
            if source.key.startswith("analyser")
            else "official-parser"
            if source.key.startswith("parser")
            else "official"
        )
        capture = re.search(r"/web/([0-9]{8})", manifest.origin)
        capture_date = (
            f"{capture[1][:4]}-{capture[1][4:6]}-{capture[1][6:8]}" if capture else ""
        )
        note = source.note
        if category == "official":
            note += (
                " Commit author: Logical Language Group <llg@lojban.org>."
                " Projected text normalizes CRLF to LF."
            )
        elif category == "analyser":
            note += (
                " Commit author: Nick Nicholas <nick-nicholas@lojban.org>."
                " Projected text normalizes CRLF to LF."
            )
        elif source.key == "parser-shar":
            note += (
                " Commit author: John Cowan <john-cowan@lojban.org>."
                " Projected text normalizes CRLF to LF. The extracted 2.33"
                " grammar headers state that change proposals 1-33 were dated"
                " 22 June 1993."
            )
        rows[category].append(
            {
                "url": manifest.origin,
                "sha256": manifest.sha256,
                "bytes": manifest.bytes,
                "server_date": "",
                "capture_date": capture_date,
                "note": note,
            }
        )
    camxes_root = archive / "manifests/grammars/vendor/camxes"
    camxes_path = next(iter(sorted(camxes_root.glob("*.toml"))), None)
    if camxes_path is None:
        raise GrammarProjectError("camxes archive provenance manifest is absent")
    camxes = ArchiveManifest.load(camxes_path)
    rows["camxes"].append(
        {
            "url": camxes.origin,
            "sha256": camxes.sha256,
            "bytes": camxes.bytes,
            "server_date": "",
            "capture_date": "",
            "note": camxes.notes,
        }
    )
    support_dates = {
        source: CAMXES_MEMBER_TIMES[source]
        for _source_id, _start, _end, entries in CAMXES_SUPPORT_GROUPS
        for source, _target in entries
    }
    jar_name = "./rats/lojban_peg_parser.jar"
    _camxes_manifest, camxes_members = _camxes_members(
        archive, (*support_dates, jar_name)
    )
    for name, source_date in sorted(support_dates.items()):
        payload = camxes_members[name]
        rows["camxes"].append(
            {
                "url": f"{camxes.origin}#{name}",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "server_date": source_date,
                "capture_date": "",
                "note": (
                    "Mixed-encoding bytes rendered reversibly with grammar-bytes/1."
                    if name in {"./test_sentences.txt", "./morph_test_sentences.txt"}
                    else (
                        "Text support member projected in its file-dated event;"
                        " CRLF is normalized to LF."
                    )
                ),
            }
        )
    jar = camxes_members[jar_name]
    rows["camxes"].append(
        {
            "url": f"{camxes.origin}#{jar_name}",
            "sha256": hashlib.sha256(jar).hexdigest(),
            "bytes": len(jar),
            "server_date": "2006-08-21",
            "capture_date": "",
            "note": "Binary Java parser retained in the archive; not projected.",
        }
    )
    result = {}
    columns = ("url", "sha256", "bytes", "server_date", "capture_date", "note")
    for category, values in rows.items():
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(values, key=lambda row: str(row["url"])))
        result[f"_meta/grammars/{category}/provenance.csv"] = stream.getvalue()
    return result


def _index(
    sources: Sequence[GitGrammar],
    *,
    include_camxes: bool,
    include_vendor: bool,
    include_zasni: bool,
) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=INDEX_COLUMNS, lineterminator="\n")
    writer.writeheader()
    rows = [
        {
            "name": source.name,
            "author": source.author,
            "language": source.language,
            "formalism": source.formalism,
            "dialect": source.dialect,
            "years": source.years,
            "mechanism": "submodule",
            "upstream": source.url,
            "licence": source.licence,
        }
        for source in sources
    ]
    if include_vendor:
        rows.extend(VENDOR_INDEX_ROWS)
    if include_camxes:
        rows.append(CAMXES_INDEX_ROW)
    if include_zasni:
        rows.append(ZASNI_INDEX_ROW)
    rows.extend(
        dict(zip(INDEX_COLUMNS, values, strict=True)) for values in CATALOGUE_ROWS
    )
    for row in sorted(rows, key=lambda item: item["name"]):
        writer.writerow(row)
    return stream.getvalue()


def _csv_rows(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def project(
    archive: Path,
    *,
    sources: Sequence[GitGrammar] = GIT_GRAMMARS,
    include_camxes: bool = True,
    include_camxes_support: bool = True,
    include_vendor: bool = True,
    include_zasni: bool = True,
) -> Iterable[Event]:
    """Emit chronological gitlink pin events from archived mirror states."""

    pins = [pin for source in sources for pin in _pins(archive, source)]
    seen: set[str] = set()
    events: list[Event] = []
    for pin in pins:
        created = pin.source.key not in seen
        seen.add(pin.source.key)
        event = Event(
            source="grammars",
            source_id=f"grammars/{pin.source.key}={pin.object_id}",
            event="created" if created else "edited",
            time_confidence="exact",
            source_time=pin.commit_date,
            summary=f"pin {pin.source.key} {pin.object_id[:12]}",
            author=pin.author,
            changes={
                f"_meta/grammars/{pin.source.key}/upstream.toml": _upstream_toml(pin)
            },
            gitlinks={pin.source.path: pin.object_id},
            submodules={pin.source.path: pin.source.url},
            trailers={"Grammar": pin.source.key},
        )
        event.validate()
        events.append(event)
    if include_vendor:
        events.extend(_vendor_events(archive))
    if include_camxes:
        for revision in _camxes_rcs(archive):
            event = Event(
                source="grammars",
                source_id=f"grammars/camxes=lojban.peg@{revision.revision}",
                event="created" if revision.revision == "1.1" else "edited",
                time_confidence="exact",
                source_time=revision.timestamp,
                summary=f"camxes lojban.peg {revision.revision}",
                author=Identity.namespaced("teddyb.org", revision.author),
                changes={"grammars/camxes/rcs/lojban.peg": revision.content},
                body=revision.log,
                trailers={"Grammar": "camxes", "RCS-Revision": revision.revision},
            )
            event.validate()
            events.append(event)
        if include_camxes_support:
            events.extend(_camxes_support_events(archive))
    if include_zasni:
        events.append(_zasni_event(archive))
    events.sort(key=lambda item: (item.source_time, item.source_id))
    if events:
        changes = dict(events[-1].changes)
        changes["_meta/grammars/index.csv"] = _index(
            sources,
            include_camxes=include_camxes,
            include_vendor=include_vendor,
            include_zasni=include_zasni,
        )
        changes["_meta/grammars/gaps.csv"] = _csv_rows(GAP_COLUMNS, GAP_ROWS)
        changes["_meta/grammars/duplicates.csv"] = _csv_rows(
            DUPLICATE_COLUMNS, DUPLICATE_ROWS
        )
        if include_vendor:
            changes.update(_provenance(archive))
        events[-1] = replace(events[-1], changes=changes)
    yield from events
