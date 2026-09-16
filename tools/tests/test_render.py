from __future__ import annotations

import re
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
    assert {"wiki", "mail", "dict", "cll", "irc"} <= set(by_source)
    # Each id is in the grammar the same document defines.
    assert by_source["wiki"].startswith("revid=")
    assert by_source["mail"].startswith("<") and by_source["mail"].endswith(">")
    assert by_source["dict"].startswith("definition=")
    assert by_source["cll"].startswith("cll=")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", by_source["irc"])


def test_the_irc_example_is_marked_as_not_yet_present() -> None:
    """`irc/` is absent from this snapshot, so its example cannot be tried yet."""

    template = (
        Path(__file__).resolve().parents[2] / "tools/templates/main/AGENTS.md"
    ).read_text(encoding="utf-8")
    lines = template.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("irc/lojban/"))
    # The caveat sits in the sentence introducing the example, not far above it.
    preamble = "\n".join(lines[max(index - 4, 0) : index])
    assert "once `irc/` is present" in preamble, preamble
