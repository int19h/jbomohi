"""Deterministic rendering of the main-branch instruction files."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..git import EPOCH, Event, Identity, commit_event, git_output

TOKEN = re.compile(r"\{\{([a-z_]+)\}\}")
OBJECT_ID = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
DEFAULT_COVERAGE = "No source events have been projected yet."
DEFAULT_LAYOUT = "See `AGENTS.md` for the corpus directory map."
DEFAULT_PROVENANCE = (
    "Each source is republished under its own terms as published by its owner; "
    "this repository claims no licence of its own over the data."
)


# What the root commit shows where a build-specific value would go. SPEC.md
# 3.11/§5: the root must not change when the tools do, so it names neither the
# tools commit nor a snapshot; the tip refresh commit carries both.
PENDING = "pending"


@dataclass(frozen=True, slots=True)
class RenderContext:
    snapshot: str = "root"
    schema: str = "1"
    tools_commit: str = ""
    repo_url: str = "https://github.com/int19h/jbomohi.git"
    coverage_tables: str = DEFAULT_COVERAGE
    layout_summary: str = DEFAULT_LAYOUT
    provenance: str = DEFAULT_PROVENANCE

    @classmethod
    def root(cls) -> RenderContext:
        """The build-invariant form the root commit is rendered with."""

        return cls(snapshot=PENDING, tools_commit=PENDING)

    @property
    def is_root(self) -> bool:
        return self.tools_commit == PENDING

    def values(self) -> dict[str, str]:
        return {
            "snapshot": self.snapshot,
            "schema": self.schema,
            "tools_commit": self.tools_commit,
            "repo_url": self.repo_url,
            "coverage_tables": self.coverage_tables,
            "layout_summary": self.layout_summary,
            "provenance": self.provenance,
        }


def _render(text: str, context: RenderContext, template: Path) -> str:
    values = context.values()

    def replacement(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise ValueError(f"unknown template token {name!r} in {template}")
        return values[name]

    rendered = TOKEN.sub(replacement, text)
    unresolved = TOKEN.search(rendered)
    if unresolved:
        raise ValueError(
            f"unresolved template token in {template}: {unresolved.group(0)}"
        )
    return rendered


def _validate_context(context: RenderContext) -> None:
    if not context.is_root and not OBJECT_ID.fullmatch(context.tools_commit):
        raise ValueError("render context tools_commit must be a git object id")
    if (
        not context.schema.isascii()
        or not context.schema.isdecimal()
        or str(int(context.schema)) != context.schema
    ):
        raise ValueError(
            "render context schema must be a canonical non-negative integer"
        )
    for name, value in context.values().items():
        if (
            not isinstance(value, str)
            or "\0" in value
            or "\r" in value
            or value.startswith("\ufeff")
        ):
            raise ValueError(f"render context {name} is not UTF-8/LF-safe text")


def render_main(
    repo_root: Path, context: RenderContext | None = None
) -> dict[str, bytes]:
    """Render every tracked template plus the projection schema."""

    root = repo_root.resolve()
    actual_context = context or RenderContext(
        tools_commit=git_output(root, ["rev-parse", "HEAD"])
    )
    _validate_context(actual_context)
    templates = root / "tools" / "templates" / "main"
    if not templates.is_dir():
        raise ValueError(f"template directory not found: {templates}")
    rendered: dict[str, bytes] = {}
    for template in sorted(path for path in templates.rglob("*") if path.is_file()):
        if template.is_symlink():
            raise ValueError(f"template must not be a symlink: {template}")
        relative = template.relative_to(templates).as_posix()
        raw = template.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
            raise ValueError(f"template must be UTF-8/LF without BOM: {template}")
        text = raw.decode("utf-8")
        output = _render(text, actual_context, template)
        if "\r" in output or output.startswith("\ufeff"):
            raise ValueError(f"rendered template is not UTF-8/LF-safe: {template}")
        rendered[relative] = output.encode("utf-8")
    # The root carries the schema and the renderer versions only: naming the
    # tools commit there would make every tools commit rewrite all of main.
    tools_line = (
        ""
        if actual_context.is_root
        else f'tools_commit = "{actual_context.tools_commit}"\n'
    )
    schema = (
        f"projection_schema = {int(actual_context.schema)}\n"
        f"{tools_line}"
        "\n[renderers]\n"
        "instructions = 1\n"
    )
    rendered["_meta/schema.toml"] = schema.encode("utf-8")
    return rendered


def commit_root(repo_root: Path, corpus: Path) -> str:
    """Commit the deterministic root, which never names the build that made it."""

    event = Event(
        source="meta",
        source_id="root",
        event="refresh",
        time_confidence="exact",
        source_time=EPOCH,
        summary="initialise corpus root",
        author=Identity.tool(),
        changes=render_main(repo_root, RenderContext.root()),
        trailers={"Renderer": "instructions/1"},
    )
    return commit_event(event, corpus)


def commit_instruction_refresh(
    repo_root: Path,
    corpus: Path,
    *,
    source_time: datetime,
    source_id: str,
    context: RenderContext,
    extra_changes: Mapping[str, str | bytes] | None = None,
) -> str:
    changes = render_main(repo_root, context)
    overlap = changes.keys() & (extra_changes or {}).keys()
    if overlap:
        raise ValueError(
            f"instruction refresh extra changes overlap templates: {', '.join(sorted(overlap))}"
        )
    changes.update(extra_changes or {})
    event = Event(
        source="meta",
        source_id=source_id,
        event="refresh",
        time_confidence="exact",
        source_time=source_time,
        summary="refresh instructions and coverage",
        author=Identity.tool(),
        changes=changes,
        trailers={"Renderer": "instructions/1"},
    )
    return commit_event(event, corpus)
