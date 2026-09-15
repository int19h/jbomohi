"""Prove the export and the API crawl agree, against the real archive.

SPEC.md 3.2 defines the two wiki inputs as equal over their intersection:
every `revid` and `logid` present in both must yield byte-identical events.
That is a property of the actual data, not of a fixture, so these tests run
only where the archive holds both inputs and skip everywhere else, which keeps
CI green while a local run proves the claim the PR body makes.

Run them with the archive in place:

    JBOMOHI_ARCHIVE=~/lojban/archive uv run --python 3.13 pytest \\
        tools/tests/test_wiki_dump_equality.py -q
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest
from jbomohi_tools.project.wiki import (
    load_archive,
    load_log_archive,
    load_media_archive,
    merge_fragments,
    project,
)
from jbomohi_tools.project.wiki_sql import combine_inputs, load_dump_archive

REVISION_FIELDS = (
    "revid",
    "parentid",
    "timestamp",
    "user",
    "comment",
    "size",
    "sha1",
    "content",
    "text_hidden",
    "text_missing",
    "user_hidden",
    "comment_hidden",
)
LOG_FIELDS = (
    "log_type",
    "pageid",
    "namespace",
    "title",
    "timestamp",
    "user",
    "comment",
    "target_namespace",
    "target_title",
    "suppress_redirect",
    "move_redir",
)
EVENT_FIELDS = (
    "source",
    "source_id",
    "event",
    "time_confidence",
    "source_time",
    "summary",
    "author",
    "changes",
    "deletions",
    "trailers",
)


def archive_root() -> Path:
    configured = os.environ.get("JBOMOHI_ARCHIVE")
    return (
        Path(configured).expanduser()
        if configured
        else Path.home() / "lojban" / "archive"
    )


@pytest.fixture(scope="module")
def inputs() -> tuple[object, list, list, list]:
    root = archive_root()
    if not (root / "manifests" / "wiki" / "db-export").is_dir():
        pytest.skip(f"no ingested wiki SQL export under {root}")
    if not (root / "manifests" / "wiki" / "revisions").is_dir():
        pytest.skip(f"no archived wiki API responses under {root}")
    dump = load_dump_archive(root)
    if dump is None:
        pytest.skip("the wiki export manifest names no object")
    return dump, load_archive(root), load_log_archive(root), load_media_archive(root)


def test_shared_pages_and_revisions_are_identical(inputs) -> None:
    dump, api_fragments, _logs, _media = inputs
    api = {page.pageid: page for page in merge_fragments(api_fragments)}
    export = {page.pageid: page for page in merge_fragments(list(dump.fragments))}

    shared = sorted(set(api) & set(export))
    assert shared, "the two inputs share no page"
    for pageid in shared:
        left, right = api[pageid], export[pageid]
        assert (left.namespace, left.title, left.is_redirect) == (
            right.namespace,
            right.title,
            right.is_redirect,
        ), f"page {pageid} identity differs"

    api_revisions = {r.revid: r for p in api.values() for r in p.revisions}
    export_revisions = {r.revid: r for p in export.values() for r in p.revisions}
    both = sorted(set(api_revisions) & set(export_revisions))
    assert both, "the two inputs share no revision"
    differing = [
        (revid, field)
        for revid in both
        for field in REVISION_FIELDS
        if getattr(api_revisions[revid], field)
        != getattr(export_revisions[revid], field)
    ]
    assert differing == []


def test_shared_log_events_are_identical(inputs) -> None:
    dump, _fragments, api_logs, _media = inputs
    api = {event.logid: event for event in api_logs}
    export = {event.logid: event for event in dump.logs}
    both = sorted(set(api) & set(export))
    assert both, "the two inputs share no log event"
    differing = [
        (logid, field)
        for logid in both
        for field in LOG_FIELDS
        if getattr(api[logid], field) != getattr(export[logid], field)
    ]
    assert differing == []


def test_both_paths_project_the_same_events_over_the_same_range(inputs) -> None:
    dump, api_fragments, api_logs, media = inputs
    export_revisions = {r.revid for f in dump.fragments for r in f.revisions}
    export_logids = {event.logid for event in dump.logs}
    api_revisions = {r.revid for f in api_fragments for r in f.revisions}
    api_logids = {event.logid for event in api_logs}

    # Restrict both sides to what both inputs hold, so a difference can only be
    # a decoding difference and never a coverage one.
    shared_revisions = api_revisions & export_revisions
    shared_logids = api_logids & export_logids

    def restrict(fragments):
        return [
            replace(
                fragment,
                revisions=tuple(
                    r for r in fragment.revisions if r.revid in shared_revisions
                ),
            )
            for fragment in fragments
        ]

    left = list(
        project(
            restrict(api_fragments),
            [event for event in api_logs if event.logid in shared_logids],
            media,
        )
    )
    right = list(
        project(
            restrict(list(dump.fragments)),
            [event for event in dump.logs if event.logid in shared_logids],
            media,
        )
    )
    assert len(left) == len(right)
    assert [event.source_id for event in left] == [event.source_id for event in right]

    differing: list[tuple[str, str]] = []
    for one, other in zip(left, right, strict=True):
        for field in EVENT_FIELDS:
            if getattr(one, field) == getattr(other, field):
                continue
            if field == "changes":
                # Each input can only explain the text it itself could not
                # resolve, so the cause recorded in gaps.csv is allowed to
                # differ; nothing else may.
                keys = set(one.changes) | set(other.changes)
                assert set(one.changes) == set(other.changes)
                for key in sorted(keys):
                    if one.changes[key] == other.changes[key]:
                        continue
                    if key != "_meta/wiki/gaps.csv":
                        differing.append((one.source_id, key))
                        continue
                    mine = one.changes[key].splitlines()
                    theirs = other.changes[key].splitlines()
                    assert len(mine) == len(theirs)
                    for a, b in zip(mine, theirs, strict=True):
                        if a != b:
                            assert (
                                a.split(",text unresolvable:")[0]
                                == b.split(",text unresolvable:")[0]
                            ), "only the unresolvable-text cause may differ"
                continue
            differing.append((one.source_id, field))
    assert differing == []


def test_the_union_projects_and_records_every_additive_class(inputs) -> None:
    dump, api_fragments, api_logs, media = inputs
    combined = combine_inputs(dump, api_fragments, api_logs)
    events = list(
        project(
            combined.fragments,
            combined.logs,
            media,
            combined.extra_gaps,
            combined.ended_at,
            combined.unaccounted,
            combined.additive,
        )
    )
    assert events
    coverage = events[-1].changes["_meta/wiki/coverage.toml"]
    for name, count, _cause in combined.additive:
        assert f"[additive.{name}]" in coverage
        assert f"count = {count}" in coverage

    # The export adds events, and anything it stops projecting is written down
    # rather than dropped: adding the export's own move logs and deleted
    # lineages can change which page holds a path when a log entry fires, and
    # such an entry must then appear in gaps.csv.
    api_only = list(project(api_fragments, api_logs, media))
    assert len(events) > len(api_only)
    gaps = events[-1].changes["_meta/wiki/gaps.csv"]
    dropped = {e.source_id for e in api_only} - {e.source_id for e in events}
    for source_id in sorted(dropped):
        kind, _, value = source_id.partition("=")
        column = 1 if kind == "logid" else 0
        assert any(row.split(",")[column] == value for row in gaps.splitlines()[1:]), (
            f"{source_id} is neither projected nor recorded as a gap"
        )


def test_the_union_is_deterministic(inputs) -> None:
    _dump, api_fragments, api_logs, media = inputs
    root = archive_root()

    def once() -> list[tuple[object, ...]]:
        dump = load_dump_archive(root)
        combined = combine_inputs(dump, api_fragments, api_logs)
        return [
            (
                event.source_id,
                event.event,
                event.source_time,
                event.summary,
                event.author,
                sorted(event.changes.items()),
                event.deletions,
                sorted(event.trailers.items()),
            )
            for event in project(
                combined.fragments,
                combined.logs,
                media,
                combined.extra_gaps,
                combined.ended_at,
                combined.unaccounted,
                combined.additive,
            )
        ]

    assert once() == once()
