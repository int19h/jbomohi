from __future__ import annotations

import csv
import io
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.project.cll import (
    CllRenderError,
    Edition,
    RenderedEdition,
    _render_html,
    _render_xml,
    alignment,
    project,
)


def git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+00:00",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+00:00",
    }
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def source_repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "--initial-branch=main")
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(source, "add", ".")
    git(source, "commit", "-m", "source")
    return source, git(source, "rev-parse", "HEAD")


def edition(name: str, object_id: str, *, style: str = "xml") -> Edition:
    return Edition(
        name=name,
        ref="fixture-ref",
        manifest_ref="refs/tags/fixture-ref",
        object_id=object_id,
        commit_date=datetime(2020, 1, 1, tzinfo=UTC),
        source_date=None,
        style=style,
    )


def test_render_legacy_html_drops_markup_and_keeps_example_lines(
    tmp_path: Path,
) -> None:
    source, object_id = source_repo(
        tmp_path,
        {
            "c1/s.html": "<h2>Chapter 1<br>About Lojban</h2>",
            "c1/s1.html": (
                "<h3>1. First section</h3>"
                "<p>A <b>paragraph</b> split\nacross lines .i next.</p>"
                "<pre><a id=e1d1>1.1) mi klama\nI go\nI go.</a></pre>"
                "<pre><a id=e1d2>1.1) do klama .i mi klama</a></pre>"
            ),
        },
    )
    rendered = _render_html(
        edition("1997-online-draft", object_id, style="html-1997"), source
    )
    assert set(rendered.sections) == {"1.1"}
    assert set(rendered.changes) == {"cll/editions/1997-online-draft/01-about.txt"}
    text = next(iter(rendered.changes.values()))
    assert text.startswith(
        "# cll 1997-online-draft chapter 1 About Lojban | "
        "rendered from fixture-ref by jbomohi cll/1\n"
    )
    assert "## 1.1 First section" in text
    assert "A paragraph split across lines .i next." in text
    assert "[Example 1.1]\n\nmi klama\nI go\nI go." in text
    assert text.count("[Example 1.1]") == 2
    assert "do klama .i mi klama" in text
    assert "<b>" not in text


def test_render_docbook_keeps_sections_examples_glosses_and_entities(
    tmp_path: Path,
) -> None:
    source, object_id = source_repo(
        tmp_path,
        {
            "chapters/01.xml": (
                '<chapter xmlns:xlink="urn:xlink" xml:id="chapter-about">'
                '<title><anchor xml:id="c1"/>About</title>'
                '<section><title><anchor xml:id="c1s1"/>First</title>'
                '<para>Before &ndash; <xref linkend="other"/> after .i now.</para>'
                '<example><title><anchor xml:id="c1e1d1"/></title>'
                "<interlinear-gloss><jbo>mi klama .i do klama</jbo><gloss>I go</gloss>"
                "<natlang>I go.</natlang></interlinear-gloss></example>"
                "</section></chapter>"
            )
        },
    )
    rendered = _render_xml(edition("1.1-2016", object_id), source)
    assert set(rendered.sections) == {"1.1"}
    assert set(rendered.changes) == {"cll/editions/1.1-2016/01-about.txt"}
    text = next(iter(rendered.changes.values()))
    assert "## 1.1 First" in text
    assert "Before – [other] after .i now." in text
    assert "[Example 1.1]\n\nmi klama .i do klama\n\nI go\n\nI go." in text


def test_render_legacy_html_rejects_an_example_without_a_printed_label(
    tmp_path: Path,
) -> None:
    source, object_id = source_repo(
        tmp_path,
        {
            "c1/s.html": "<h2>Chapter 1 About</h2>",
            "c1/s1.html": "<h3>1. First</h3><pre><a id=e1d1>mi klama</a></pre>",
        },
    )
    with pytest.raises(CllRenderError, match="has no n.m.*label"):
        _render_html(edition("1997-online-draft", object_id, style="html-1997"), source)


def rendered(name: str, sections: dict[str, str]) -> RenderedEdition:
    return RenderedEdition(edition(name, "a" * 40), {}, sections)


def test_alignment_uses_same_numbers_then_greedy_similarity() -> None:
    left = rendered(
        "left",
        {
            "1.1": "same\n",
            "1.2": "changed old\n",
            "1.3": "a distinctive renumbered section text\n",
            "1.4": "removed\n",
        },
    )
    right = rendered(
        "right",
        {
            "1.1": "same\n",
            "1.2": "changed new\n",
            "1.5": "a distinctive renumbered section text\n",
            "1.6": "added\n",
        },
    )
    rows = alignment(left, right)
    assert [(row["relation"], row["method"]) for row in rows] == [
        ("added", "none"),
        ("identical", "section-number"),
        ("changed", "section-number"),
        ("renumbered", "text-similarity-0.80"),
        ("removed", "none"),
    ]


def test_alignment_similarity_ties_break_by_section_pair() -> None:
    left = rendered("left", {"1.1": "same text", "1.2": "same text"})
    right = rendered("right", {"2.1": "same text", "2.2": "same text"})
    rows = alignment(left, right)
    assert [(row["section_a"], row["section_b"]) for row in rows] == [
        ("1.1", "2.1"),
        ("1.2", "2.2"),
    ]


def test_project_emits_cumulative_metadata_and_exact_gitlinks(
    tmp_path: Path, monkeypatch
) -> None:
    first = Edition(
        "1997-online-draft",
        "old",
        "old",
        "1" * 40,
        datetime(2008, 5, 30, 0, 0, tzinfo=UTC),
        "1997",
        "xml",
    )
    second = Edition(
        "1.0-errata-2014",
        "new",
        "new",
        "2" * 40,
        datetime(2014, 6, 20, 0, 0, tzinfo=UTC),
        None,
        "xml",
    )
    values = {
        first.name: RenderedEdition(first, {"cll/old.txt": "old\n"}, {"1.1": "old\n"}),
        second.name: RenderedEdition(
            second, {"cll/new.txt": "new\n"}, {"1.1": "new\n"}
        ),
    }
    monkeypatch.setattr(
        "jbomohi_tools.project.cll.editions",
        lambda _archive: (tmp_path, [first, second]),
    )
    monkeypatch.setattr(
        "jbomohi_tools.project.cll.render_edition",
        lambda item, _mirror: values[item.name],
    )
    events = list(project(tmp_path))
    assert [event.source_id for event in events] == [
        "cll=1997-online-draft",
        "cll=1.0-errata-2014",
    ]
    assert events[0].source_date == "1997"
    assert events[1].gitlinks == {"cll/src": "2" * 40}
    assert events[1].submodules == {"cll/src": "https://github.com/int19h/cll"}
    edition_rows = list(
        csv.DictReader(io.StringIO(events[1].changes["_meta/cll/editions.csv"]))
    )
    assert [row["edition"] for row in edition_rows] == [first.name, second.name]
    assert [(row["chapters"], row["sections"]) for row in edition_rows] == [
        ("1", "1"),
        ("1", "1"),
    ]
    alignment_rows = list(
        csv.DictReader(io.StringIO(events[1].changes["_meta/cll/alignment.csv"]))
    )
    assert alignment_rows[0]["relation"] == "changed"
