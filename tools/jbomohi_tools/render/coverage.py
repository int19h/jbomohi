"""What the snapshot covers, and where things are, rendered from the corpus.

The README used to paste every integer in every `coverage.toml` as one
comma-separated line per file. That is twenty lines of counters a reader
cannot use, and it silently said nothing at all about the wiki, whose coverage
file holds only `[additive.*]` tables and no top-level integers. The layout in
`AGENTS.md` had the opposite problem: it was a fixed list, so it described
`irc/`, `who/`, `notes/`, `loglan/` and `llg/` as present in a snapshot that
has none of them.

Both are now read from the corpus that is being built.
"""

from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# What each top-level directory holds, in the terms a reader needs before
# opening one: the format on disk and the encoding. Presence is never asserted
# here; it is read from the corpus.
LAYOUT: tuple[tuple[str, str], ...] = (
    (
        "wiki/",
        (
            "MediaWiki pages as raw wikitext, UTF-8, one file per page, full "
            "revision history in git. `wiki/talk/` holds the Talk namespace."
        ),
    ),
    (
        "tiki/",
        (
            "The pre-2013 Tiki wiki in Tiki markup, UTF-8, with history. "
            "`tiki/forums/` holds WikiDiscuss threads and `tiki/talk/` page "
            "comments. Some text is stored mojibake and is published "
            "unrepaired."
        ),
    ),
    (
        "mail/",
        (
            "One Maildir per list under `<list>/cur/`, byte-exact RFC 822 as "
            "the archives hold it, so transfer encodings and original charsets "
            "are intact. `<list>/threads/<YYYY>/` holds decoded thread "
            "renderings, UTF-8, which are derived views and name their "
            "originals."
        ),
    ),
    (
        "irc/",
        (
            "One UTF-8 file per channel-day, `<channel>/<YYYY>/<date>.txt`, "
            "with a header line giving the timezone and line format."
        ),
    ),
    (
        "dict/",
        (
            "One directory per word: `word.toml` for the word and its "
            "etymology, `<lang>-<id>.md` per definition with its examples, "
            "`comments.md`. UTF-8, front matter in TOML."
        ),
    ),
    (
        "cll/",
        (
            "*The Complete Lojban Language* as plain UTF-8 text, one file per "
            "chapter per edition, under `cll/editions/<edition>/`. `cll/src` is "
            "the DocBook source as a submodule."
        ),
    ),
    (
        "grammars/",
        (
            "Formal grammars and parsers: the official YACC/BNF baselines, "
            "camxes and its lineage, ilmentufa, zantufa, zasni gerna and "
            "others, as submodules or vendored text. `_meta/grammars/index.csv` "
            "says which is which and under what terms."
        ),
    ),
    (
        "who/",
        (
            "`attestations.csv`: dated, cited claims relating nicks, addresses "
            "and wiki users. Claims, never resolved identities."
        ),
    ),
    (
        "notes/",
        (
            "Contributed research notes under `<YYYY>/`, UTF-8 Markdown with "
            "TOML front matter. Maps to evidence, never evidence."
        ),
    ),
    (
        "loglan/",
        "Loglan-era documents, where republication is permitted.",
    ),
    (
        "llg/",
        "The Logical Language Group's own publications.",
    ),
    (
        "_meta/",
        (
            "Coverage files, archive manifests and CSV indexes. TOML and CSV "
            "with header rows, UTF-8."
        ),
    ),
)


@dataclass(slots=True)
class SourceTally:
    """What one source contributed, counted as the build emitted it."""

    events: int = 0
    first: datetime | None = None
    last: datetime | None = None

    def record(self, moment: datetime) -> None:
        self.events += 1
        if self.first is None or moment < self.first:
            self.first = moment
        if self.last is None or moment > self.last:
            self.last = moment


@dataclass(slots=True)
class _SourceCoverage:
    events: int
    period: str
    notes: list[str] = field(default_factory=list)


def _period(tally: SourceTally) -> str:
    if tally.first is None or tally.last is None:
        return "—"
    first, last = tally.first.date(), tally.last.date()
    return str(first.year) if first.year == last.year else f"{first.year}–{last.year}"


def _rows(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


def _load(path: Path) -> dict[str, object]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return {}


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count:,} {singular if count == 1 else (plural or singular + 's')}"


def _notes_for(corpus: Path, source: str) -> list[str]:
    """The honest gaps for one source, from what it recorded about itself."""

    notes: list[str] = []
    root = corpus / "_meta" / source
    gaps = root / "gaps.csv"
    if gaps.is_file():
        count = _rows(gaps)
        if count:
            notes.append(f"{_plural(count, 'gap')} recorded in `{source}/gaps.csv`")
    incomplete: list[str] = []
    unusable = 0
    for coverage in sorted(root.rglob("coverage.toml")):
        data = _load(coverage)
        archive_gaps = data.get("archive_gaps")
        if isinstance(archive_gaps, dict) and archive_gaps:
            incomplete.append(coverage.parent.name)
        value = data.get("unusable_date_headers")
        if isinstance(value, int):
            unusable += value
    if incomplete:
        notes.append("archives known incomplete: " + ", ".join(sorted(incomplete)))
    if unusable:
        notes.append(f"{_plural(unusable, 'unusable date header')}")
    return notes


def coverage_table(corpus: Path, tallies: dict[str, SourceTally]) -> str:
    """One row per source: what it contributed, over what period, and the gaps."""

    if not tallies:
        return "No source events have been projected yet."
    grouped: dict[str, SourceTally] = {}
    for name, tally in tallies.items():
        top = name.split("/", 1)[0]
        merged = grouped.setdefault(top, SourceTally())
        merged.events += tally.events
        for moment in (tally.first, tally.last):
            if moment is not None:
                merged.record(moment)
                merged.events -= 1
    lines = [
        "| source | events | period | notes |",
        "|---|---:|---|---|",
    ]
    for source in sorted(grouped):
        tally = grouped[source]
        notes = _notes_for(corpus, source)
        lines.append(
            f"| `{source}/` | {tally.events:,} | {_period(tally)} | "
            f"{'; '.join(notes) if notes else 'none recorded'} |"
        )
    total = sum(tally.events for tally in grouped.values())
    lines.append(f"\nTotal: **{total:,}** source events.")
    return "\n".join(lines)


def layout_summary(corpus: Path) -> str:
    """The directory map, saying which parts this snapshot actually has."""

    lines = []
    for name, description in LAYOUT:
        present = (corpus / name.rstrip("/")).is_dir()
        marker = "" if present else " *Not yet in this snapshot.*"
        lines.append(f"- **`{name}`** — {description}{marker}")
    return "\n".join(lines)
