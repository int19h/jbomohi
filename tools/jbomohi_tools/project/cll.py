"""Pure rendering of archived Complete Lojban Language git editions."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

from ..archive.cll import CLL_URL, DYNAMIC_TAGS, FROZEN_REFS
from ..archive.manifest import ArchiveManifest, object_path
from ..git import Event, Identity, git_output, run_git

RENDERER = "cll/1"
GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")
HTML_1997_PATH = re.compile(r"^c(?P<chapter>[0-9]+)/s(?P<section>[0-9]+)\.html$")
HTML_2014_PATH = re.compile(r"^(?P<chapter>[0-9]+)/(?P<section>[0-9]+)/index\.html$")
XML_CHAPTER_PATH = re.compile(r"^chapters/(?P<chapter>a?[0-9]+)\.xml$")
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
CHAPTER_SLUGS = {
    "1": "about",
    "2": "tour",
    "3": "phonology",
    "4": "morphology",
    "5": "selbri",
    "6": "sumti",
    "7": "anaphoric-cmavo",
    "8": "relative-clauses",
    "9": "sumti-tcita",
    "10": "tenses",
    "11": "abstractions",
    "12": "lujvo",
    "13": "attitudinals",
    "14": "connectives",
    "15": "negation",
    "16": "quantifiers",
    "17": "letterals",
    "18": "mekso",
    "19": "structure",
    "20": "catalogue",
    "21": "grammars",
    "22": "dialects",
    "A1": "chrestomathy",
    "A2": "peg-morphology",
    "A3": "changes",
}
EDITION_COLUMNS = (
    "edition",
    "ref",
    "peeled_commit",
    "commit_date",
    "source_date",
    "chapters",
    "sections",
)
ALIGNMENT_COLUMNS = (
    "edition_a",
    "section_a",
    "edition_b",
    "section_b",
    "relation",
    "method",
)


class CllRenderError(ValueError):
    """The archived CLL mirror cannot produce a faithful deterministic rendering."""


@dataclass(frozen=True, slots=True)
class Edition:
    name: str
    ref: str
    manifest_ref: str
    object_id: str
    commit_date: datetime
    source_date: str | None
    style: str


@dataclass(frozen=True, slots=True)
class RenderedEdition:
    edition: Edition
    changes: Mapping[str, str]
    sections: Mapping[str, str]


def _manifest(archive: Path) -> ArchiveManifest:
    root = archive / "manifests" / "cll" / "git-mirror"
    manifests = [ArchiveManifest.load(path) for path in sorted(root.glob("*.toml"))]
    valid = [
        item
        for item in manifests
        if item.source == "cll" and item.kind == "git-mirror" and item.origin == CLL_URL
    ]
    if not valid:
        raise CllRenderError("CLL git-mirror manifest is absent")
    return max(
        valid,
        key=lambda item: (
            len(item.coverage.get("refs", {})),
            item.fetched_at,
            item.sha256,
        ),
    )


def _mirror_refs(archive: Path) -> tuple[Path, dict[str, str]]:
    manifest = _manifest(archive)
    raw_refs = manifest.coverage.get("refs")
    if not isinstance(raw_refs, dict) or not raw_refs:
        raise CllRenderError("CLL git-mirror manifest has no scoped refs")
    refs = dict(raw_refs)
    obj = object_path(archive, manifest.sha256)
    try:
        payload = obj.read_bytes()
    except OSError as exc:
        raise CllRenderError(f"CLL scoped-ref object is unreadable: {obj}") from exc
    if (
        len(payload) != manifest.bytes
        or hashlib.sha256(payload).hexdigest() != manifest.sha256
    ):
        raise CllRenderError("CLL scoped-ref object does not match its manifest")
    try:
        recorded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CllRenderError("CLL scoped-ref object is invalid JSON") from exc
    if recorded != {"origin": CLL_URL, "refs": refs}:
        raise CllRenderError("CLL scoped-ref object disagrees with its manifest")

    mirror = archive / "git" / "cll.git"
    if mirror.is_symlink() or not mirror.is_dir():
        raise CllRenderError(f"CLL bare mirror is absent or unsafe: {mirror}")
    if git_output(mirror, ["rev-parse", "--is-bare-repository"]) != "true":
        raise CllRenderError(f"CLL mirror is not a bare repository: {mirror}")
    tags = set(
        git_output(mirror, ["for-each-ref", "--format=%(refname)", "refs/tags"])
        .strip()
        .splitlines()
    )
    dynamic = {
        ref for ref in tags if any(pattern.fullmatch(ref) for pattern in DYNAMIC_TAGS)
    }
    expected_refs = {*FROZEN_REFS, *dynamic}
    if set(refs) != expected_refs:
        raise CllRenderError("CLL mirror and manifest disagree on scoped refs")
    for ref, expected in FROZEN_REFS.items():
        if refs.get(ref) != expected:
            raise CllRenderError(f"frozen CLL ref changed in manifest: {ref}")
    for ref, expected in sorted(refs.items()):
        actual = run_git(
            mirror,
            ["rev-parse", "--verify", f"{ref}^{{commit}}"],
            check=False,
        ).stdout.strip()
        if actual != expected:
            raise CllRenderError(
                f"CLL ref {ref!r} peels to {actual or 'missing'}, expected {expected}"
            )
    return mirror, refs


def _commit_date(mirror: Path, object_id: str) -> datetime:
    value = git_output(mirror, ["show", "-s", "--format=%cI", object_id])
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CllRenderError(f"invalid CLL commit date for {object_id}") from exc
    if parsed.tzinfo is None or parsed.microsecond:
        raise CllRenderError(f"invalid CLL commit date for {object_id}")
    return parsed


def editions(archive: Path) -> tuple[Path, list[Edition]]:
    """Load the scoped edition table and verify every mirrored ref."""

    mirror, refs = _mirror_refs(archive)
    values = [
        Edition(
            "1997-online-draft",
            "8048799d",
            next(ref for ref in refs if ref.startswith("8048799d")),
            FROZEN_REFS[next(ref for ref in refs if ref.startswith("8048799d"))],
            _commit_date(
                mirror,
                FROZEN_REFS[next(ref for ref in refs if ref.startswith("8048799d"))],
            ),
            "1997",
            "html-1997",
        ),
        Edition(
            "1.0-errata-2014",
            "dabe6154",
            next(ref for ref in refs if ref.startswith("dabe6154")),
            FROZEN_REFS[next(ref for ref in refs if ref.startswith("dabe6154"))],
            _commit_date(
                mirror,
                FROZEN_REFS[next(ref for ref in refs if ref.startswith("dabe6154"))],
            ),
            None,
            "html-2014",
        ),
    ]
    for manifest_ref, object_id in sorted(refs.items()):
        ref = manifest_ref.removeprefix("refs/tags/")
        if match := re.fullmatch(
            r"v1\.1-(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})-html", ref
        ):
            values.append(
                Edition(
                    f"1.1-{match['date'][:4]}",
                    ref,
                    manifest_ref,
                    object_id,
                    _commit_date(mirror, object_id),
                    match["date"],
                    "xml",
                )
            )
        elif re.fullmatch(r"geklojban-1\.2\.[0-9]+", ref):
            values.append(
                Edition(
                    ref.removeprefix("geklojban-"),
                    ref,
                    manifest_ref,
                    object_id,
                    _commit_date(mirror, object_id),
                    None,
                    "xml",
                )
            )
        elif re.fullmatch(r"v1\.3\.[0-9]+", ref):
            values.append(
                Edition(
                    ref.removeprefix("v"),
                    ref,
                    manifest_ref,
                    object_id,
                    _commit_date(mirror, object_id),
                    None,
                    "xml",
                )
            )
    values.sort(key=lambda item: (item.commit_date, item.name))
    names = [item.name for item in values]
    if len(names) != len(set(names)):
        raise CllRenderError("CLL edition names are not unique")
    return mirror, values


def _show(mirror: Path, object_id: str, path: str) -> str:
    result = run_git(mirror, ["show", f"{object_id}:{path}"], check=False)
    if result.returncode != 0:
        raise CllRenderError(f"CLL {object_id} lacks source path {path}")
    return result.stdout


def _paths(mirror: Path, object_id: str) -> list[str]:
    return git_output(mirror, ["ls-tree", "-r", "--name-only", object_id]).splitlines()


def _plain(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _tag_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]*>", " ", value, flags=re.DOTALL)
    return _plain(html.unescape(without_tags))


def _html_heading(document: str, tag: str, chapter: int) -> str:
    matched = re.search(
        rf"<{tag}\b[^>]*>(?P<value>.*?)</{tag}>",
        document,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if matched is None:
        raise CllRenderError(f"CLL HTML chapter {chapter} lacks {tag}")
    value = _tag_text(matched["value"])
    value = re.sub(rf"^Chapter\s+{chapter}\s*", "", value, flags=re.IGNORECASE)
    if not value:
        raise CllRenderError(f"CLL HTML chapter {chapter} has an empty {tag}")
    return value


class _HtmlBody(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.in_head = False
        self.nav_depth = 0
        self.heading: str | None = None
        self.suppress_anchor = False
        self.pre_depth = 0

    def _break(self) -> None:
        self.parts.append("\n\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        if tag == "head":
            self.in_head = True
            return
        if tag == "div" and self.nav_depth:
            self.nav_depth += 1
            return
        if tag == "div" and "nav" in (attributes.get("class") or "").split():
            self.nav_depth = 1
            return
        if self.in_head or self.nav_depth:
            return
        if tag in {"h1", "h2", "h3"}:
            self.heading = tag
            return
        anchor = attributes.get("id") or attributes.get("name")
        if tag == "a" and anchor and re.fullmatch(r"e[0-9]+(?:d[0-9]+)?", anchor):
            self.suppress_anchor = True
            return
        if tag in {"p", "pre", "blockquote", "li", "tr"}:
            self._break()
            if tag == "pre":
                self.pre_depth += 1
            if tag == "li":
                self.parts.append("- ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag in {"td", "th"} and self.parts and not self.parts[-1].endswith("\n\n"):
            self.parts.append(" | ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "head":
            self.in_head = False
            return
        if tag == "div" and self.nav_depth:
            self.nav_depth -= 1
            return
        if self.in_head or self.nav_depth:
            return
        if self.heading == tag:
            self.heading = None
            return
        if tag == "a" and self.suppress_anchor:
            raise CllRenderError("CLL HTML example anchor has no n.m) label")
        if tag in {"p", "pre", "blockquote", "li", "tr"}:
            if tag == "pre" and self.pre_depth:
                self.pre_depth -= 1
            self._break()

    def handle_data(self, data: str) -> None:
        if self.in_head or self.nav_depth or self.heading is not None:
            return
        if self.suppress_anchor:
            matched = re.match(r"^\s*(?P<label>[0-9]+\.[0-9]+)\)\s*", data)
            if matched is None:
                raise CllRenderError("CLL HTML example anchor has no n.m) label")
            self._break()
            self.parts.append(f"[Example {matched['label']}]")
            self._break()
            data = data[matched.end() :]
            self.suppress_anchor = False
        self.parts.append(data if self.pre_depth else re.sub(r"\s+", " ", data))

    def text(self) -> str:
        lines: list[str] = []
        blank = True
        for raw in "".join(self.parts).splitlines():
            line = _plain(raw)
            if line:
                lines.append(line)
                blank = False
            elif not blank:
                lines.append("")
                blank = True
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)


def _chapter_sort(value: str) -> tuple[int, int]:
    return (1, int(value[1:])) if value.startswith("a") else (0, int(value))


def _render_html(edition: Edition, mirror: Path) -> RenderedEdition:
    pattern = HTML_1997_PATH if edition.style == "html-1997" else HTML_2014_PATH
    grouped: dict[int, list[tuple[int, str]]] = {}
    tree_paths = _paths(mirror, edition.object_id)
    for path in tree_paths:
        matched = pattern.fullmatch(path)
        if matched:
            grouped.setdefault(int(matched["chapter"]), []).append(
                (int(matched["section"]), path)
            )
    landing = re.compile(
        r"^c(?P<chapter>[0-9]+)/s\.html$"
        if edition.style == "html-1997"
        else r"^(?P<chapter>[0-9]+)/index\.html$"
    )
    landing_paths = {
        int(matched["chapter"]): path
        for path in tree_paths
        if (matched := landing.fullmatch(path))
    }
    for chapter, path in landing_paths.items():
        if chapter not in grouped:
            grouped[chapter] = [(1, path)]
    if not grouped:
        raise CllRenderError(f"CLL edition {edition.name} has no HTML sections")
    changes: dict[str, str] = {}
    sections: dict[str, str] = {}
    for chapter, source_paths in sorted(grouped.items()):
        source_paths.sort()
        title_path = (
            f"c{chapter}/s.html" if edition.style == "html-1997" else source_paths[0][1]
        )
        title_document = _show(mirror, edition.object_id, title_path)
        try:
            chapter_title = _html_heading(title_document, "h2", chapter)
        except CllRenderError:
            chapter_title = _html_heading(title_document, "h3", chapter)
        chapter_label = str(chapter)
        rendered_sections: list[str] = []
        for section, path in source_paths:
            document = _show(mirror, edition.object_id, path)
            try:
                section_title = _html_heading(document, "h3", chapter)
            except CllRenderError:
                if path != landing_paths.get(chapter):
                    raise
                section_title = chapter_title
            section_title = re.sub(rf"^{section}\.\s*", "", section_title)
            parser = _HtmlBody()
            parser.feed(document)
            parser.close()
            section_id = f"{chapter_label}.{section}"
            rendered = f"## {section_id} {section_title}\n\n{parser.text()}".rstrip()
            rendered_sections.append(rendered)
            sections[section_id] = rendered + "\n"
        header = (
            f"# cll {edition.name} chapter {chapter_label} {chapter_title} | "
            f"rendered from {edition.ref} by jbomohi {RENDERER}\n"
        )
        chapter_slug = CHAPTER_SLUGS.get(chapter_label)
        if chapter_slug is None:
            raise CllRenderError(f"CLL HTML chapter has no stable slug: {chapter}")
        target = f"cll/editions/{edition.name}/{chapter:02d}-{chapter_slug}.txt"
        changes[target] = header + "\n".join(
            f"\n{section}\n" for section in rendered_sections
        )
    return RenderedEdition(edition, changes, sections)


def _local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _inline(element: ET.Element) -> str:
    parts: list[str] = [element.text or ""]
    for child in element:
        tag = _local(child)
        if tag in {"indexterm", "anchor", "mediaobject"}:
            pass
        elif tag == "xref":
            target = child.attrib.get("linkend", "reference")
            parts.append(f"[{target}]")
        elif tag == "quote":
            parts.append(f'"{_inline(child)}"')
        else:
            parts.append(_inline(child))
        parts.append(child.tail or "")
    return _plain("".join(parts))


def _literal(element: ET.Element) -> str:
    lines = [_plain(line) for line in "".join(element.itertext()).splitlines()]
    return "\n".join(line for line in lines if line)


def _blocks(element: ET.Element, chapter: str, examples: list[int]) -> list[str]:
    tag = _local(element)
    if tag in {"title", "indexterm", "mediaobject", "anchor"}:
        return []
    if tag in {"para", "simpara"}:
        text = _inline(element)
        return [text] if text else []
    if tag in {"programlisting", "literallayout", "screen", "grammar-template", "math"}:
        text = _literal(element)
        return [text] if text else []
    if tag in {"itemizedlist", "orderedlist"}:
        result: list[str] = []
        number = 0
        for child in element:
            if _local(child) != "listitem":
                continue
            number += 1
            value = _inline(child)
            marker = f"{number}." if tag == "orderedlist" else "-"
            if value:
                result.append(f"{marker} {value}")
        return result
    if tag == "example":
        examples[0] += 1
        result = [f"[Example {chapter}.{examples[0]}]"]
        for child in element:
            if _local(child) == "title":
                continue
            result.extend(_blocks(child, chapter, examples))
        return result
    if tag == "interlinear-gloss":
        return [value for child in element if (value := _inline(child))]
    if tag in {"table", "informaltable"}:
        rows: list[str] = []
        for row in element.iter():
            if _local(row) not in {"tr", "row"}:
                continue
            cells = [
                _inline(cell) for cell in row if _local(cell) in {"td", "th", "entry"}
            ]
            if cells:
                rows.append(" | ".join(cells))
        return rows
    if tag in {"cmavo-list", "cmavo-list-head"}:
        rows = []
        for entry in element:
            value = " | ".join(text for child in entry if (text := _inline(child)))
            if value:
                rows.append(value)
        return rows
    result: list[str] = []
    for child in element:
        result.extend(_blocks(child, chapter, examples))
    if not result and not list(element):
        text = _inline(element)
        if text:
            result.append(text)
    return result


def _xml_root(document: str, path: str) -> ET.Element:
    document = document.replace("&InvisibleTimes;", "&#8290;")
    document = document.replace("&hellip;", "&#8230;").replace("&ndash;", "&#8211;")
    document = re.sub(
        r"<(chapter|appendix)\b",
        r'<\1 xmlns:mml="urn:jbomohi:mathml"',
        document,
        count=1,
    )
    try:
        return ET.fromstring(document)
    except ET.ParseError as exc:
        raise CllRenderError(f"CLL XML is invalid at {path}: {exc}") from exc


def _render_xml(edition: Edition, mirror: Path) -> RenderedEdition:
    paths = []
    for path in _paths(mirror, edition.object_id):
        matched = XML_CHAPTER_PATH.fullmatch(path)
        if matched:
            paths.append((matched["chapter"], path))
    paths.sort(key=lambda item: _chapter_sort(item[0]))
    if not paths:
        raise CllRenderError(f"CLL edition {edition.name} has no XML chapters")
    changes: dict[str, str] = {}
    sections: dict[str, str] = {}
    for raw_chapter, path in paths:
        root = _xml_root(_show(mirror, edition.object_id, path), path)
        title_element = next(
            (child for child in root if _local(child) == "title"), None
        )
        if title_element is None or not (chapter_title := _inline(title_element)):
            raise CllRenderError(f"CLL XML chapter has no title: {path}")
        chapter = (
            f"A{int(raw_chapter[1:])}"
            if raw_chapter.startswith("a")
            else str(int(raw_chapter))
        )
        examples = [0]
        rendered_sections: list[str] = []
        ordinal = 0
        for section in (item for item in root.iter() if _local(item) == "section"):
            ordinal += 1
            section_title_element = next(
                (child for child in section if _local(child) == "title"), None
            )
            if section_title_element is None or not (
                section_title := _inline(section_title_element)
            ):
                raise CllRenderError(f"CLL XML section has no title: {path}")
            anchor = next(
                (
                    child.attrib.get(XML_ID, "")
                    for child in section_title_element.iter()
                    if _local(child) == "anchor" and child.attrib.get(XML_ID)
                ),
                "",
            )
            matched = re.fullmatch(rf"c{re.escape(chapter)}s([0-9]+)", anchor)
            section_number = int(matched.group(1)) if matched else ordinal
            section_id = f"{chapter}.{section_number}"
            values: list[str] = []
            for child in section:
                if _local(child) in {"title", "section"}:
                    continue
                values.extend(_blocks(child, chapter, examples))
            rendered = (
                f"## {section_id} {section_title}\n\n" + "\n\n".join(values)
            ).rstrip()
            if section_id in sections:
                raise CllRenderError(
                    f"CLL edition {edition.name} repeats section {section_id}"
                )
            rendered_sections.append(rendered)
            sections[section_id] = rendered + "\n"
        header = (
            f"# cll {edition.name} chapter {chapter} {chapter_title} | "
            f"rendered from {edition.ref} by jbomohi {RENDERER}\n"
        )
        prefix = (
            f"A{int(raw_chapter[1:])}"
            if raw_chapter.startswith("a")
            else f"{int(raw_chapter):02d}"
        )
        chapter_slug = CHAPTER_SLUGS.get(chapter)
        if chapter_slug is None:
            raise CllRenderError(f"CLL XML chapter has no stable slug: {chapter}")
        target = f"cll/editions/{edition.name}/{prefix}-{chapter_slug}.txt"
        changes[target] = header + "\n".join(
            f"\n{section}\n" for section in rendered_sections
        )
    return RenderedEdition(edition, changes, sections)


def render_edition(edition: Edition, mirror: Path) -> RenderedEdition:
    if edition.style in {"html-1997", "html-2014"}:
        return _render_html(edition, mirror)
    if edition.style == "xml":
        return _render_xml(edition, mirror)
    raise CllRenderError(f"unknown CLL source style: {edition.style}")


def _csv(columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def alignment(left: RenderedEdition, right: RenderedEdition) -> list[dict[str, str]]:
    """Align one adjacent edition pair under the deterministic §3.6 policy."""

    rows: list[dict[str, str]] = []
    left_ids = set(left.sections)
    right_ids = set(right.sections)
    common = left_ids & right_ids
    for section in sorted(common):
        rows.append(
            {
                "edition_a": left.edition.name,
                "section_a": section,
                "edition_b": right.edition.name,
                "section_b": section,
                "relation": (
                    "identical"
                    if left.sections[section].encode()
                    == right.sections[section].encode()
                    else "changed"
                ),
                "method": "section-number",
            }
        )
    unmatched_left = left_ids - common
    unmatched_right = right_ids - common
    candidates = sorted(
        (
            (
                SequenceMatcher(
                    None,
                    left.sections[section_a],
                    right.sections[section_b],
                    autojunk=False,
                ).ratio(),
                section_a,
                section_b,
            )
            for section_a in unmatched_left
            for section_b in unmatched_right
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    claimed_left: set[str] = set()
    claimed_right: set[str] = set()
    for ratio, section_a, section_b in candidates:
        if ratio < 0.80 or section_a in claimed_left or section_b in claimed_right:
            continue
        claimed_left.add(section_a)
        claimed_right.add(section_b)
        rows.append(
            {
                "edition_a": left.edition.name,
                "section_a": section_a,
                "edition_b": right.edition.name,
                "section_b": section_b,
                "relation": "renumbered",
                "method": "text-similarity-0.80",
            }
        )
    for section in sorted(unmatched_left - claimed_left):
        rows.append(
            {
                "edition_a": left.edition.name,
                "section_a": section,
                "edition_b": right.edition.name,
                "section_b": "",
                "relation": "removed",
                "method": "none",
            }
        )
    for section in sorted(unmatched_right - claimed_right):
        rows.append(
            {
                "edition_a": left.edition.name,
                "section_a": "",
                "edition_b": right.edition.name,
                "section_b": section,
                "relation": "added",
                "method": "none",
            }
        )
    rows.sort(key=lambda row: (row["section_a"], row["section_b"]))
    return rows


def project(archive: Path) -> Iterable[Event]:
    """Render every scoped CLL edition into chronological gitlink events."""

    mirror, source_editions = editions(archive)
    rendered = [render_edition(item, mirror) for item in source_editions]
    all_alignment: list[dict[str, str]] = []
    events: list[Event] = []
    for index, item in enumerate(rendered):
        if index:
            all_alignment.extend(alignment(rendered[index - 1], item))
        edition_rows = [
            {
                "edition": value.edition.name,
                "ref": value.edition.ref,
                "peeled_commit": value.edition.object_id,
                "commit_date": value.edition.commit_date.isoformat(timespec="seconds"),
                "source_date": value.edition.source_date or "",
                "chapters": len(value.changes),
                "sections": len(value.sections),
            }
            for value in rendered[: index + 1]
        ]
        changes = {
            **item.changes,
            "_meta/cll/editions.csv": _csv(EDITION_COLUMNS, edition_rows),
            "_meta/cll/alignment.csv": _csv(ALIGNMENT_COLUMNS, all_alignment),
        }
        event = Event(
            source="cll",
            source_id=f"cll={item.edition.name}",
            event="render",
            time_confidence="exact",
            source_time=item.edition.commit_date,
            source_date=item.edition.source_date,
            summary=f"render {item.edition.name}",
            author=Identity.tool(),
            changes=changes,
            gitlinks={"cll/src": item.edition.object_id},
            submodules={"cll/src": CLL_URL},
            trailers={"Edition": item.edition.name, "Renderer": RENDERER},
        )
        event.validate()
        events.append(event)
    yield from events
