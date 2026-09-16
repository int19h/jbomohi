from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jbomohi_tools.render import (
    RenderContext,
    SourceTally,
    coverage_table,
    layout_summary,
    render_main,
)

OBJECT_ID = "a" * 40


def template_repo(tmp_path: Path, content: bytes) -> Path:
    root = tmp_path / "tools-checkout"
    templates = root / "tools/templates/main"
    templates.mkdir(parents=True)
    (templates / "README.md").write_bytes(content)
    return root


def test_render_rejects_an_unknown_template_token(tmp_path: Path) -> None:
    root = template_repo(tmp_path, b"{{unknown}}\n")
    with pytest.raises(ValueError, match="unknown template token"):
        render_main(root, RenderContext(tools_commit=OBJECT_ID))


def test_render_rejects_a_token_introduced_by_context(tmp_path: Path) -> None:
    root = template_repo(tmp_path, b"{{coverage_tables}}\n")
    context = RenderContext(tools_commit=OBJECT_ID, coverage_tables="{{snapshot}}")
    with pytest.raises(ValueError, match="unresolved template token"):
        render_main(root, context)


def test_render_rejects_a_non_object_id_tools_commit(tmp_path: Path) -> None:
    root = template_repo(tmp_path, b"plain text\n")
    with pytest.raises(ValueError, match="must be a git object id"):
        render_main(root, RenderContext(tools_commit="not-an-object-id"))


def test_render_preserves_literal_double_braces_outside_token_grammar(
    tmp_path: Path,
) -> None:
    literal = b"Use {{Like this}} and {{BPFK Section from tiki|example}}.\n"
    root = template_repo(tmp_path, literal)
    rendered = render_main(root, RenderContext(tools_commit=OBJECT_ID))
    assert rendered["README.md"] == literal


@pytest.mark.parametrize("content", [b"\xef\xbb\xbftext\n", b"text\r\n"])
def test_render_rejects_bom_and_crlf_templates(tmp_path: Path, content: bytes) -> None:
    root = template_repo(tmp_path, content)
    with pytest.raises(ValueError, match="UTF-8/LF without BOM"):
        render_main(root, RenderContext(tools_commit=OBJECT_ID))


def test_every_projector_falls_back_to_the_untitled_placeholder() -> None:
    """SPEC.md 3.1: a subject is one non-empty line, never an invented one.

    No source on today's archive produces an empty title, so this is insurance
    for the next input rather than a fix for present data; that is exactly why
    it is worth pinning.
    """

    from jbomohi_tools.git import UNTITLED
    from jbomohi_tools.project.dictionary import _summary as dict_summary
    from jbomohi_tools.project.mail import _summary as mail_summary
    from jbomohi_tools.project.tiki import _summary as tiki_summary
    from jbomohi_tools.project.wiki import _log_summary
    from jbomohi_tools.project.wiki import _summary as wiki_summary

    assert wiki_summary("", 1, "") == f"{UNTITLED} (rev 1)"
    assert wiki_summary("   ", 1, "note") == f"{UNTITLED} (rev 1) note"
    assert _log_summary("", 5, "") == f"{UNTITLED} (log 5)"
    assert tiki_summary("", "@3") == f"{UNTITLED} @3"
    assert dict_summary("", "en#1 v1") == f"{UNTITLED} en#1 v1"
    # Mail keeps its own placeholder, which its indexes and thread views use.
    assert mail_summary("", "lojban-list") == "[no subject]"

    for summary in (
        wiki_summary("", 1, ""),
        _log_summary("", 5, ""),
        tiki_summary("", "@3"),
        dict_summary("", "en#1 v1"),
        mail_summary("", "lojban-list"),
    ):
        assert summary and summary == summary.strip()


def _corpus_with(tmp_path: Path, *present: str) -> Path:
    corpus = tmp_path / "corpus"
    (corpus / "_meta").mkdir(parents=True)
    for name in present:
        (corpus / name).mkdir(parents=True, exist_ok=True)
    return corpus


def test_layout_says_which_directories_this_snapshot_actually_has(
    tmp_path: Path,
) -> None:
    """The map used to be a fixed list, so it promised directories that were absent.

    The 2026-09-16 corpus had no `irc/`, `who/`, `notes/`, `loglan/` or `llg/`,
    and the layout described all five as present — while `AGENTS.md` used an
    IRC citation as its worked example.
    """

    corpus = _corpus_with(tmp_path, "wiki", "mail")
    summary = layout_summary(corpus)

    for line in summary.splitlines():
        absent = "Not yet in this snapshot" in line
        if line.startswith(("- **`wiki/`**", "- **`mail/`**")):
            assert not absent, line
        elif line.startswith(("- **`irc/`**", "- **`who/`**", "- **`notes/`**")):
            assert absent, line
    # The map still describes what a directory holds, present or not, because a
    # reader asking "where would IRC be" deserves an answer.
    assert "channel-day" in summary
    assert "wikitext" in summary


def test_coverage_counts_a_source_even_when_its_coverage_file_has_no_counters(
    tmp_path: Path,
) -> None:
    """The wiki's coverage.toml holds only [additive.*] tables and no integers.

    The old renderer printed every top-level integer of every coverage file, so
    the wiki — the largest single source after the dictionary — rendered as an
    empty entry, and the reader was told nothing at all about it.
    """

    corpus = _corpus_with(tmp_path, "wiki")
    (corpus / "_meta" / "wiki").mkdir()
    (corpus / "_meta" / "wiki" / "coverage.toml").write_text(
        '[additive.export_revisions_without_actor_row]\ncount = 2608\ncause = "x"\n',
        encoding="utf-8",
    )
    tally = SourceTally()
    tally.record(datetime(2005, 3, 1, tzinfo=UTC))
    tally.record(datetime(2026, 1, 9, tzinfo=UTC))

    table = coverage_table(corpus, {"wiki": tally})

    assert "| `wiki/` | 2 | 2005–2026 |" in table
    assert "Total: **2** source events." in table


def test_coverage_reports_the_gaps_a_source_recorded_about_itself(
    tmp_path: Path,
) -> None:
    corpus = _corpus_with(tmp_path, "mail")
    root = corpus / "_meta" / "mail" / "lojban-list"
    root.mkdir(parents=True)
    (root / "coverage.toml").write_text(
        'unusable_date_headers = 9\n\n[archive_gaps]\n"old" = "not populated"\n',
        encoding="utf-8",
    )
    (corpus / "_meta" / "mail" / "gaps.csv").write_text(
        "source_id,reason\na,b\nc,d\n", encoding="utf-8"
    )
    tally = SourceTally()
    tally.record(datetime(1989, 6, 1, tzinfo=UTC))

    table = coverage_table(corpus, {"mail/lojban-list": tally})

    assert "2 gaps recorded in `mail/gaps.csv`" in table
    assert "archives known incomplete: lojban-list" in table
    assert "9 unusable date headers" in table
    # Lists are one source to a reader, so they are one row.
    assert table.count("| `mail/`") == 1


CITATION = re.compile(r"^(?P<path>[^@\s]+)@(?P<id>.+?):L\d+(?:-\d+)?$")


def test_every_citation_example_is_shaped_like_a_citation() -> None:
    """The examples are the first thing a reader copies, so they must resolve.

    An earlier draft used invented paths and an invented Message-ID. Nobody
    notices until someone tries one, and then the document has taught them the
    repository is broken. These are checked against the built corpus by hand
    and pinned here by shape and by the index files that resolve them.
    """

    template = (
        Path(__file__).resolve().parents[2] / "tools/templates/main/AGENTS.md"
    ).read_text(encoding="utf-8")
    examples = [
        line.strip() for line in template.splitlines() if CITATION.match(line.strip())
    ]
    assert len(examples) >= 5, examples

    by_source: dict[str, str] = {}
    for example in examples:
        match = CITATION.match(example)
        assert match is not None, example
        path = match.group("path")
        by_source[path.split("/", 1)[0]] = match.group("id")

    # One worked example per source a reader is likely to start from.
    assert {"wiki", "mail", "dict", "cll", "irc", "tiki"} <= set(by_source)
    # Each id is in the grammar the same document defines.
    assert by_source["wiki"].startswith("revid=")
    assert by_source["mail"].startswith("<") and by_source["mail"].endswith(">")
    assert by_source["dict"].startswith("definition=")
    assert by_source["cll"].startswith("cll=")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", by_source["irc"])
    # A Source-Id may itself contain "@"; the path ends at the first one.
    assert by_source["tiki"].startswith("tiki=") and "@" in by_source["tiki"]


def test_a_short_fetch_and_a_short_record_read_differently(tmp_path: Path) -> None:
    corpus = _corpus_with(tmp_path, "irc")
    root = corpus / "_meta" / "irc" / "lojban"
    root.mkdir(parents=True)
    (root / "coverage.toml").write_text(
        "days = 6892\n\n[archive]\nfiles_listed_but_not_archived = 951\n",
        encoding="utf-8",
    )
    tally = SourceTally()
    tally.record(datetime(2000, 5, 26, tzinfo=UTC))
    tally.record(datetime(2022, 7, 31, tzinfo=UTC))

    table = coverage_table(corpus, {"irc/lojban": tally})

    assert "951 files the upstream listed but this archive does not hold" in table
    # And a complete fetch says nothing, rather than saying zero.
    (root / "coverage.toml").write_text(
        "days = 10\n\n[archive]\nfiles_listed_but_not_archived = 0\n", encoding="utf-8"
    )
    assert "does not hold" not in coverage_table(corpus, {"irc/lojban": tally})


def _templates() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2] / "tools/templates/main"
    return {
        "AGENTS.md": (root / "AGENTS.md").read_text(encoding="utf-8"),
        "README.md": (root / "README.md").read_text(encoding="utf-8"),
        "rules": (root / ".agents/rules/jbomohi.md").read_text(encoding="utf-8"),
    }


def test_the_three_files_do_not_repeat_each_other() -> None:
    """Each fact belongs in one file; the others point at it.

    The citation grammar was in two files and had already drifted into two
    spellings, and the rules file carried a compressed copy of a contract it
    could not keep in step with.
    """

    files = _templates()
    # The grammar itself lives only in AGENTS.md.
    grammar = "<path>@<Source-Id>:L<start>"
    assert grammar in files["AGENTS.md"]
    assert grammar not in files["rules"]
    # The rules file points rather than restates.
    assert "AGENTS.md" in files["rules"]
    assert len(files["rules"].splitlines()) < 25, "the rules file is a pointer"
    # The synthetic-address list is worded once, not twice differently.
    assert files["README.md"].count("irclogs@irc.lojban.org") == 1


def test_the_tools_branch_pointer_is_one_sentence_at_the_end() -> None:
    """The human partner's rule: a brief mention, not a section, and not early."""

    for name, text in (("AGENTS.md", None), ("README.md", None)):
        body = _templates()[name]
        assert body.count("tools` branch") == 1, name
        where = body.index("tools` branch") / len(body)
        assert where > 0.9, f"{name}: pointer at {where:.0%} of the file"


def test_no_development_or_coordination_content_reaches_main() -> None:
    """These files ship to readers of the corpus, not to its maintainers."""

    banned = ("herdr", "collab", "pull request", "worktree", "pytest", "uv run")
    for name, text in _templates().items():
        lowered = text.lower()
        for word in banned:
            assert word not in lowered, f"{name} mentions {word!r}"


def test_every_citation_example_resolves_in_the_corpus() -> None:
    """Shape is not resolution, and checking shape is how a broken one got in.

    A Tiki example was added with an invented version number and a sibling test
    that checked the grammar it was written in. It parsed perfectly and pointed
    at nothing. This resolves each example against a real corpus when one is
    configured, which is the only check that would have caught it.
    """

    corpus = os.environ.get("JBOMOHI_CORPUS")
    if not corpus:
        pytest.skip("set JBOMOHI_CORPUS to resolve the citation examples")
    root = Path(corpus)
    if not (root / ".git").is_dir():
        pytest.skip(f"no corpus repository at {root}")

    template = (
        Path(__file__).resolve().parents[2] / "tools/templates/main/AGENTS.md"
    ).read_text(encoding="utf-8")
    unresolved: list[str] = []
    for line in template.splitlines():
        match = CITATION.match(line.strip())
        if match is None:
            continue
        path, span = match.group("path"), match.group(0).rsplit(":L", 1)[1]
        first = int(span.split("-", 1)[0])
        target = root / path
        if not (root / path.split("/", 1)[0]).is_dir():
            # A source this snapshot does not carry yet, such as irc/ before
            # its first fetch. Skipping the whole directory is honest; skipping
            # a missing file inside a present one would hide the bug this test
            # exists for.
            continue
        if not target.is_file():
            unresolved.append(f"{path}: no such file in the corpus")
            continue
        lines = target.read_text(encoding="utf-8", errors="replace").count("\n")
        if first > lines:
            unresolved.append(f"{path}: cites L{span} but has {lines} lines")
    assert not unresolved, "; ".join(unresolved)


def test_every_cited_source_id_exists_in_the_history() -> None:
    """The version an example names must be one the history actually recorded."""

    corpus = os.environ.get("JBOMOHI_CORPUS")
    if not corpus:
        pytest.skip("set JBOMOHI_CORPUS to resolve the citation examples")
    root = Path(corpus)
    if not (root / ".git").is_dir():
        pytest.skip(f"no corpus repository at {root}")

    template = (
        Path(__file__).resolve().parents[2] / "tools/templates/main/AGENTS.md"
    ).read_text(encoding="utf-8")
    missing: list[str] = []
    for line in template.splitlines():
        match = CITATION.match(line.strip())
        if match is None:
            continue
        source_id = match.group("id")
        if not (root / match.group("path").split("/", 1)[0]).is_dir():
            continue
        # A citation writes a mail Message-ID inside the angle brackets that
        # are part of its syntax; the trailer stores it bare (SPEC.md 3.1.4).
        source_id = source_id.strip("<>")
        found = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "-1",
                "--format=%H",
                f"--grep=Source-Id: {re.escape(source_id)}$",
                "--extended-regexp",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if not found.stdout.strip():
            missing.append(f"{source_id}: no commit carries this Source-Id")
    assert not missing, "; ".join(missing)
