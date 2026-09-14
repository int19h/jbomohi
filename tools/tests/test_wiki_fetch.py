from __future__ import annotations

import json
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path

from jbomohi_tools.archive import verify_manifests
from jbomohi_tools.archive.wiki import ApiResponse, fetch, query_url
from jbomohi_tools.project.wiki import load_archive, project


def revision(revid: int, parentid: int, content: str) -> dict[str, object]:
    return {
        "revid": revid,
        "parentid": parentid,
        "timestamp": f"2014-01-0{revid}T00:00:00Z",
        "user": "Gleki",
        "comment": "",
        "size": len(content),
        "sha1": f"{revid:040x}",
        "slots": {"main": {"content": content}},
    }


class FakeWikiClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def query(self, params):
        params = dict(params)
        self.calls.append(params)
        if params.get("meta") == "siteinfo":
            document = {"query": {"statistics": {"pages": 1}, "namespaces": []}}
        elif params.get("prop") == "revisions|info":
            if "rvcontinue" not in params:
                document = {
                    "continue": {"rvcontinue": "next", "continue": "||info"},
                    "query": {
                        "pages": [
                            {
                                "pageid": 1,
                                "ns": 0,
                                "title": "Page",
                                "revisions": [revision(1, 0, "first\n")],
                            }
                        ]
                    },
                }
            else:
                document = {
                    "query": {
                        "pages": [
                            {
                                "pageid": 1,
                                "ns": 0,
                                "title": "Page",
                                "revisions": [revision(2, 1, "second\n")],
                            }
                        ]
                    }
                }
        elif params.get("list") == "logevents":
            document = {"query": {"logevents": []}}
        elif params.get("list") == "allpages":
            document = {
                "query": {"allpages": [{"pageid": 1, "ns": 0, "title": "Page"}]}
            }
        else:
            raise AssertionError(params)
        return ApiResponse(
            query_url(params),
            json.dumps(document, separators=(",", ":")).encode(),
            Message(),
        )


def test_fetch_archives_paginated_revisions_and_resumes_from_manifests(
    tmp_path: Path,
) -> None:
    client = FakeWikiClient()
    first = fetch(
        tmp_path,
        titles=("Page",),
        client=client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert first.pages == 1
    assert first.revision_batches == 2
    assert first.log_batches == 2
    assert first.reused_responses == 0
    assert len(first.manifests) == 5
    assert len(verify_manifests(tmp_path / "manifests", tmp_path)) == 5
    fragments = load_archive(tmp_path)
    assert len(fragments) == 2
    events = list(project(fragments))
    assert [event.source_id for event in events] == ["revid=1", "revid=2"]

    resumed_client = FakeWikiClient()
    second = fetch(
        tmp_path,
        titles=("Page",),
        client=resumed_client,
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert second.reused_responses == 5
    assert resumed_client.calls == []


def test_fetch_discovers_pages_from_selected_namespaces(tmp_path: Path) -> None:
    client = FakeWikiClient()
    report = fetch(
        tmp_path,
        namespaces=(0,),
        max_pages=1,
        client=client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert report.pages == 1
    assert any(call.get("list") == "allpages" for call in client.calls)
