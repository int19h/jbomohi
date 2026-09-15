from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from jbomohi_tools.git import Identity
from jbomohi_tools.project.wiki import (
    WikiLogEvent,
    WikiMedia,
    WikiPageFragment,
    WikiParseError,
    WikiRevision,
    merge_fragments,
    parse_log_response,
    parse_media_response,
    parse_revision_response,
    project,
    slug,
    verify_slug_injectivity,
    wiki_path,
)


def response(*pages: object) -> bytes:
    return json.dumps({"query": {"pages": pages}}, ensure_ascii=False).encode()


def revision(
    revid: int,
    *,
    parentid: int = 0,
    timestamp: str = "2014-01-01T00:00:00Z",
    user: str = "Gleki",
    comment: str = "",
    content: str = "text\n",
) -> dict[str, object]:
    return {
        "revid": revid,
        "parentid": parentid,
        "timestamp": timestamp,
        "user": user,
        "comment": comment,
        "size": len(content.encode()),
        "sha1": hashlib.sha1(content.encode()).hexdigest(),
        "slots": {"main": {"content": content}},
    }


def test_slug_applies_unicode_percent_and_length_rules() -> None:
    assert slug("BPFK Section: gadri") == "BPFK_Section%3A_gadri"
    assert slug("a_b") == slug("a b") == "a_b"
    assert slug("café/.") == "caf%C3%A9%2F%2E"
    assert slug("-leading") == "%2Dleading"
    assert slug("e\u0301") == slug("é") == "%C3%A9"
    long_title = "é" * 100
    expected_suffix = "-" + hashlib.sha1(long_title.encode()).hexdigest()[:8]
    encoded = slug(long_title)
    assert len(encoded.encode()) <= 200
    assert encoded.endswith(expected_suffix)


def test_slug_collision_check_fails_closed_per_namespace() -> None:
    first = "A" * 220 + "58248"
    second = "A" * 220 + "95216"
    assert slug(first) == slug(second)
    with pytest.raises(WikiParseError, match="slug collision"):
        verify_slug_injectivity([(0, first), (0, second)])
    verify_slug_injectivity([(0, "a b"), (0, "a b")])
    verify_slug_injectivity([(0, "same"), (1, "Talk:same")])


def test_wiki_paths_use_the_supported_namespace_directories() -> None:
    assert wiki_path(0, "BPFK Section: gadri") == (
        "wiki/main/BPFK_Section%3A_gadri.wiki"
    )
    assert wiki_path(1, "Talk:BPFK Section: gadri") == (
        "wiki/talk/BPFK_Section%3A_gadri.wiki"
    )
    with pytest.raises(WikiParseError, match="unsupported wiki namespace"):
        wiki_path(999, "Unknown:title")


def test_parse_revision_response_keeps_content_and_suppression_flags() -> None:
    visible = revision(
        10,
        user="2001:db8::1",
        comment="create",
        content="coi rodo\n",
    )
    hidden = {
        "revid": 11,
        "parentid": 10,
        "timestamp": "2014-01-02T00:00:00Z",
        "userhidden": True,
        "commenthidden": True,
        "texthidden": True,
    }
    [fragment] = parse_revision_response(
        response(
            {
                "pageid": 527,
                "ns": 0,
                "title": "BPFK Section: gadri",
                "revisions": [visible, hidden],
            }
        )
    )
    assert fragment.pageid == 527
    assert fragment.revisions[0].content == "coi rodo\n"
    assert fragment.revisions[1].content is None
    assert fragment.revisions[1].user_hidden
    assert fragment.revisions[1].comment_hidden
    assert fragment.revisions[1].text_hidden


def test_parse_and_project_revision_with_textmissing_records_gap() -> None:
    missing = revision(12, parentid=11, timestamp="2014-01-03T00:00:00Z")
    missing["slots"] = {"main": {"textmissing": True}}
    [fragment] = parse_revision_response(
        response(
            {
                "pageid": 527,
                "ns": 0,
                "title": "BPFK Section: gadri",
                "revisions": [missing],
            }
        )
    )
    parsed = fragment.revisions[0]
    assert parsed.content is None
    assert parsed.text_missing
    [event] = list(project([fragment]))
    assert "wiki/main/BPFK_Section%3A_gadri.wiki" not in event.changes
    gaps = event.changes["_meta/wiki/gaps.csv"]
    assert isinstance(gaps, str)
    assert "12,,527,BPFK Section: gadri,2014-01-03T00:00:00Z,text missing" in gaps


def test_parse_revision_rejects_invalid_textmissing_shapes() -> None:
    invalid = revision(12)
    invalid["slots"] = {"main": {"textmissing": False}}
    with pytest.raises(WikiParseError, match="invalid textmissing marker"):
        parse_revision_response(
            response({"pageid": 527, "ns": 0, "title": "Page", "revisions": [invalid]})
        )
    conflicting = revision(13)
    assert isinstance(conflicting["slots"], dict)
    conflicting["slots"]["main"]["textmissing"] = True
    with pytest.raises(WikiParseError, match="conflicts with content"):
        parse_revision_response(
            response(
                {"pageid": 527, "ns": 0, "title": "Page", "revisions": [conflicting]}
            )
        )


def test_merge_fragments_is_order_independent_and_rejects_disagreement() -> None:
    first = WikiPageFragment(
        1,
        0,
        "Page",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "",
                1,
                "a" * 40,
                "a",
            ),
        ),
    )
    second = WikiPageFragment(
        1,
        0,
        "Page",
        False,
        (
            WikiRevision(
                2,
                1,
                datetime(2014, 1, 2, tzinfo=UTC),
                "Gleki",
                "",
                1,
                "b" * 40,
                "b",
            ),
        ),
    )
    assert merge_fragments([first, second]) == merge_fragments([second, first])
    conflicting = WikiPageFragment(1, 0, "Other", False, ())
    with pytest.raises(WikiParseError, match="inconsistent response fragments"):
        merge_fragments([first, conflicting])


def test_project_keeps_published_ip_user_and_anonymizes_suppression() -> None:
    [fragment] = parse_revision_response(
        response(
            {
                "pageid": 527,
                "ns": 0,
                "title": "BPFK Section: gadri",
                "redirect": False,
                "revisions": [
                    revision(
                        10,
                        user="192.0.2.1",
                        comment="initial",
                        content="first\n",
                    ),
                    {
                        "revid": 11,
                        "parentid": 10,
                        "timestamp": "2014-01-02T00:00:00Z",
                        "userhidden": True,
                        "commenthidden": True,
                        "texthidden": True,
                    },
                ],
            }
        )
    )
    events = list(project([fragment]))
    assert len(events) == 2
    assert events[0].event == "created"
    assert events[0].source_id == "revid=10"
    assert events[0].author == Identity.namespaced("mw.lojban.org", "192.0.2.1")
    assert events[0].changes == {"wiki/main/BPFK_Section%3A_gadri.wiki": b"first\n"}
    assert events[1].event == "edited"
    assert events[1].author == Identity.anonymous("mw.lojban.org")
    assert "wiki/main/BPFK_Section%3A_gadri.wiki" not in events[1].changes
    revisions = events[1].changes["_meta/wiki/revisions.csv"]
    assert isinstance(revisions, str)
    assert "192.0.2.1" in revisions
    assert revisions.count(",anonymous,") == 1
    gaps = events[1].changes["_meta/wiki/gaps.csv"]
    assert isinstance(gaps, str)
    assert "11,,527,BPFK Section: gadri,2014-01-02T00:00:00Z," in gaps
    assert "text suppressed; user suppressed; comment suppressed" in gaps
    assert all(len(event.subject) <= 72 for event in events)


def test_api_error_and_malformed_revision_fail_closed() -> None:
    with pytest.raises(WikiParseError, match="API error"):
        parse_revision_response(json.dumps({"error": {"code": "maxlag"}}).encode())
    bad = revision(1)
    bad["timestamp"] = "not-a-date"
    with pytest.raises(WikiParseError, match="timestamp"):
        parse_revision_response(
            response({"pageid": 1, "ns": 0, "title": "Page", "revisions": [bad]})
        )


def test_move_precedes_same_timestamp_redirect_revision() -> None:
    page = WikiPageFragment(
        1,
        0,
        "New",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "",
                4,
                "a" * 40,
                "body",
            ),
        ),
    )
    redirect = WikiPageFragment(
        2,
        0,
        "Old",
        True,
        (
            WikiRevision(
                2,
                0,
                datetime(2014, 1, 2, tzinfo=UTC),
                "Gleki",
                "redirect",
                17,
                "b" * 40,
                "#REDIRECT [[New]]",
            ),
        ),
    )
    move = WikiLogEvent(
        5,
        "move",
        1,
        0,
        "Old",
        datetime(2014, 1, 2, tzinfo=UTC),
        "Gleki",
        "rename",
        0,
        "New",
        False,
    )
    events = list(project([page, redirect], [move]))
    assert [event.source_id for event in events] == [
        "revid=1",
        "logid=5",
        "revid=2",
    ]
    assert events[1].event == "moved"
    assert events[1].deletions == ("wiki/main/Old.wiki",)
    assert events[1].changes == {"wiki/main/New.wiki": b"body"}
    assert events[1].trailers["Moved-From"] == "wiki/main/Old.wiki"
    assert events[2].changes["wiki/main/Old.wiki"] == b"#REDIRECT [[New]]"


def test_unassigned_move_does_not_move_its_left_behind_redirect() -> None:
    destination = WikiPageFragment(
        1,
        0,
        "New",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 3, tzinfo=UTC),
                "Gleki",
                "",
                4,
                "a" * 40,
                "body",
            ),
        ),
    )
    redirect = WikiPageFragment(
        2,
        0,
        "Old",
        True,
        (
            WikiRevision(
                2,
                0,
                datetime(2014, 1, 2, tzinfo=UTC),
                "Gleki",
                "move marker",
                17,
                "b" * 40,
                "#REDIRECT [[New]]",
            ),
        ),
    )
    move = WikiLogEvent(
        5,
        "move",
        2,
        0,
        "Old",
        datetime(2014, 1, 2, 0, 0, 1, tzinfo=UTC),
        "Gleki",
        "rename",
        0,
        "New",
        False,
    )
    events = list(project([destination, redirect], [move]))
    assert all(event.event != "moved" for event in events)
    assert events[0].changes == {"wiki/main/Old.wiki": b"#REDIRECT [[New]]"}
    assert events[1].changes["wiki/main/New.wiki"] == b"body"
    gaps = events[1].changes["_meta/wiki/gaps.csv"]
    assert isinstance(gaps, str)
    assert "move; history not API-accessible" in gaps


def test_move_history_uses_each_hops_namespace() -> None:
    page = WikiPageFragment(
        1,
        0,
        "BPFK Section: Draft",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "",
                4,
                "a" * 40,
                "body",
            ),
        ),
    )
    move = WikiLogEvent(
        5,
        "move",
        1,
        2,
        "User:Draft",
        datetime(2014, 1, 2, tzinfo=UTC),
        "Gleki",
        "publish",
        0,
        "BPFK Section: Draft",
        False,
    )
    events = list(project([page], [move]))
    assert events[0].changes == {"wiki/user/Draft.wiki": b"body"}
    assert events[1].deletions == ("wiki/user/Draft.wiki",)
    assert events[1].changes["wiki/main/BPFK_Section%3A_Draft.wiki"] == b"body"


def test_unrelated_log_pageid_move_is_recovered_from_target_title() -> None:
    page = WikiPageFragment(
        1,
        0,
        "New",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "",
                4,
                "a" * 40,
                "body",
            ),
        ),
    )
    move = WikiLogEvent(
        5,
        "move",
        999,
        0,
        "Old",
        datetime(2014, 1, 2, tzinfo=UTC),
        "Gleki",
        "rename",
        0,
        "New",
        False,
        True,
    )
    events = list(project([page], [move]))
    assert [event.source_id for event in events] == ["revid=1", "logid=5"]
    assert events[0].changes == {"wiki/main/Old.wiki": b"body"}
    assert events[1].event == "moved"
    assert events[1].trailers["Log-Type"] == "move_redir"
    assert events[1].deletions == ("wiki/main/Old.wiki",)
    assert events[1].changes["wiki/main/New.wiki"] == b"body"


def test_recreated_title_stops_move_chain_at_current_lineage_root() -> None:
    first = WikiPageFragment(
        1,
        0,
        "Final A",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "",
                4,
                "a" * 40,
                "body",
            ),
        ),
    )
    second = WikiPageFragment(
        2,
        0,
        "Final B",
        False,
        (
            WikiRevision(
                2,
                0,
                datetime(2014, 1, 4, tzinfo=UTC),
                "Gleki",
                "recreated",
                5,
                "b" * 40,
                "other",
            ),
        ),
    )
    moves = [
        WikiLogEvent(
            10,
            "move",
            999,
            0,
            "Old",
            datetime(2014, 1, 2, tzinfo=UTC),
            "Gleki",
            "",
            0,
            "Shared",
            True,
        ),
        WikiLogEvent(
            11,
            "move",
            999,
            0,
            "Shared",
            datetime(2014, 1, 3, tzinfo=UTC),
            "Gleki",
            "",
            0,
            "Final A",
            True,
        ),
        WikiLogEvent(
            12,
            "move",
            999,
            0,
            "Shared",
            datetime(2014, 1, 5, tzinfo=UTC),
            "Gleki",
            "",
            0,
            "Final B",
            True,
        ),
    ]
    events = list(project([first, second], moves))
    assert [event.source_id for event in events] == [
        "revid=1",
        "logid=10",
        "logid=11",
        "revid=2",
        "logid=12",
    ]
    assert events[0].changes == {"wiki/main/Old.wiki": b"body"}
    assert events[3].changes == {"wiki/main/Shared.wiki": b"other"}


def test_merged_lineage_is_labelled_and_placed_at_earliest_safe_path() -> None:
    page = WikiPageFragment(
        1,
        0,
        "New",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "old lineage",
                3,
                "a" * 40,
                "old",
            ),
            WikiRevision(
                2,
                0,
                datetime(2014, 1, 2, tzinfo=UTC),
                "Gleki",
                "current lineage",
                7,
                "b" * 40,
                "current",
            ),
        ),
    )
    move = WikiLogEvent(
        5,
        "move",
        999,
        0,
        "Old",
        datetime(2014, 1, 3, tzinfo=UTC),
        "Gleki",
        "rename",
        0,
        "New",
        True,
    )
    events = list(project([page], [move]))
    assert events[0].changes == {"wiki/main/Old.wiki": b"old"}
    assert events[0].trailers["Lineage"] == "merged"
    assert events[1].changes == {"wiki/main/Old.wiki": b"current"}
    gaps = events[-1].changes["_meta/wiki/gaps.csv"]
    assert isinstance(gaps, str)
    assert "pre-merge title unknown; placed at wiki/main/Old.wiki" in gaps


def test_branched_revision_parent_uses_newest_spine_as_current() -> None:
    page = WikiPageFragment(
        1,
        0,
        "Page",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "",
                3,
                "a" * 40,
                "one",
            ),
            WikiRevision(
                2,
                1,
                datetime(2014, 1, 2, tzinfo=UTC),
                "Gleki",
                "older branch",
                3,
                "b" * 40,
                "two",
            ),
            WikiRevision(
                3,
                1,
                datetime(2014, 1, 3, tzinfo=UTC),
                "Gleki",
                "current branch",
                5,
                "c" * 40,
                "three",
            ),
        ),
    )
    events = list(project([page]))
    by_id = {event.source_id: event for event in events}
    assert "Lineage" not in by_id["revid=1"].trailers
    assert by_id["revid=2"].trailers["Lineage"] == "merged"
    assert "Lineage" not in by_id["revid=3"].trailers


def test_migration_skew_forces_move_before_marker_revision() -> None:
    page = WikiPageFragment(
        1,
        0,
        "New",
        False,
        (
            WikiRevision(
                1,
                0,
                datetime(2014, 1, 1, tzinfo=UTC),
                "Gleki",
                "",
                3,
                "a" * 40,
                "old",
            ),
            WikiRevision(
                2,
                1,
                datetime(2014, 1, 2, tzinfo=UTC),
                "Gleki",
                "moved page [[Old]] to [[New]]",
                3,
                "a" * 40,
                "old",
            ),
        ),
    )
    move = WikiLogEvent(
        5,
        "move",
        999,
        0,
        "Old",
        datetime(2014, 1, 2, 0, 0, 1, tzinfo=UTC),
        "Gleki",
        "rename",
        0,
        "New",
        True,
    )
    events = list(project([page], [move]))
    assert [event.source_id for event in events] == [
        "revid=1",
        "logid=5",
        "revid=2",
    ]
    assert events[1].trailers["Ordering"] == "forced-before"
    assert events[2].changes["wiki/main/New.wiki"] == b"old"


def test_same_time_move_candidates_are_gapped_as_ambiguous() -> None:
    [page] = parse_revision_response(
        response(
            {
                "pageid": 1,
                "ns": 0,
                "title": "New",
                "revisions": [revision(1, timestamp="2014-01-01T00:00:00Z")],
            }
        )
    )
    moves = [
        WikiLogEvent(
            logid,
            "move",
            0,
            0,
            old,
            datetime(2014, 1, 2, tzinfo=UTC),
            "Gleki",
            "",
            0,
            "New",
            True,
        )
        for logid, old in ((5, "Old A"), (6, "Old B"))
    ]
    [event] = list(project([page], moves))
    assert event.changes["wiki/main/New.wiki"] == b"text\n"
    gaps = event.changes["_meta/wiki/gaps.csv"]
    assert isinstance(gaps, str)
    assert "move ambiguous: logid=5,logid=6" in gaps


def test_preacquisition_delete_is_a_gap_not_an_event() -> None:
    [page] = parse_revision_response(
        response(
            {
                "pageid": 1,
                "ns": 0,
                "title": "Held",
                "revisions": [revision(1, content="held")],
            }
        )
    )
    deletion = WikiLogEvent(
        9,
        "delete",
        0,
        0,
        "Gone",
        datetime(2013, 1, 1, tzinfo=UTC),
        "Gleki",
        "delete inaccessible page",
    )
    events = list(project([page], [deletion]))
    assert [event.source_id for event in events] == ["revid=1"]
    gaps = events[-1].changes["_meta/wiki/gaps.csv"]
    assert isinstance(gaps, str)
    assert "9,0,Gone,2013-01-01T00:00:00Z,deleted; history not API-accessible" in gaps


def test_historical_removed_namespace_log_is_an_explicit_gap() -> None:
    [page] = parse_revision_response(
        response(
            {
                "pageid": 1,
                "ns": 0,
                "title": "Held",
                "revisions": [revision(1, content="held")],
            }
        )
    )
    deletion = WikiLogEvent(
        9,
        "delete",
        0,
        1198,
        "Special:Badtitle/NS1198:Held",
        datetime(2013, 1, 1, tzinfo=UTC),
        "Gleki",
        "removed Translate namespace",
    )
    [event] = list(project([page], [deletion]))
    gaps = event.changes["_meta/wiki/gaps.csv"]
    assert isinstance(gaps, str)
    assert "delete; unsupported historical namespace 1198" in gaps


def test_page_without_public_revisions_is_listed_in_errors_index() -> None:
    [held, broken] = parse_revision_response(
        response(
            {
                "pageid": 1,
                "ns": 0,
                "title": "Held",
                "revisions": [revision(1, content="held")],
            },
            {"pageid": 2, "ns": 0, "title": "Broken", "revisions": []},
        )
    )
    [event] = list(project([held, broken]))
    errors = event.changes["_meta/wiki/errors.csv"]
    assert isinstance(errors, str)
    assert "2,0,Broken,no public revisions returned" in errors


def test_parse_log_response_keeps_stable_move_and_delete_ids() -> None:
    payload = json.dumps(
        {
            "query": {
                "logevents": [
                    {
                        "logid": 5,
                        "ns": 0,
                        "title": "Old",
                        "pageid": 1,
                        "params": {
                            "target_ns": 0,
                            "target_title": "New",
                            "suppressredirect": False,
                        },
                        "type": "move",
                        "action": "move",
                        "user": "Gleki",
                        "timestamp": "2014-01-02T00:00:00Z",
                        "comment": "rename",
                    },
                    {
                        "logid": 6,
                        "ns": 0,
                        "title": "New",
                        "pageid": 0,
                        "params": {
                            "target_ns": 0,
                            "target_title": "Newest",
                            "suppressredirect": True,
                        },
                        "type": "move",
                        "action": "move_redir",
                        "user": "Gleki",
                        "timestamp": "2014-01-03T00:00:00Z",
                        "comment": "move over redirect",
                    },
                    {
                        "logid": 9,
                        "ns": 0,
                        "title": "Gone",
                        "pageid": 0,
                        "params": {},
                        "type": "delete",
                        "action": "delete",
                        "user": "Gleki",
                        "timestamp": "2013-01-01T00:00:00Z",
                        "comment": "",
                    },
                ]
            }
        }
    ).encode()
    events = parse_log_response(payload)
    assert [event.logid for event in events] == [5, 6, 9]
    assert events[0].target_title == "New"
    assert events[1].target_title == "Newest"
    assert events[1].suppress_redirect
    assert events[1].move_redir
    assert events[2].log_type == "delete"


def test_media_metadata_is_manifest_only_and_keeps_published_ip_uploader() -> None:
    payload = json.dumps(
        {
            "query": {
                "allimages": [
                    {
                        "name": "Example.png",
                        "timestamp": "2014-01-01T00:00:00Z",
                        "user": "192.0.2.1",
                        "size": 123,
                        "url": "https://mw.lojban.org/images/a/ab/Example.png",
                        "descriptionshorturl": "https://mw.lojban.org/index.php?curid=7",
                        "sha1": "a" * 40,
                        "mime": "image/png",
                        "ns": 6,
                        "title": "File:Example.png",
                    }
                ]
            }
        }
    ).encode()
    [item] = parse_media_response(payload)
    assert item == WikiMedia(
        7,
        "File:Example.png",
        "https://mw.lojban.org/images/a/ab/Example.png",
        "a" * 40,
        123,
        "image/png",
        datetime(2014, 1, 1, tzinfo=UTC),
        "192.0.2.1",
    )
    [page] = parse_revision_response(
        response(
            {
                "pageid": 1,
                "ns": 0,
                "title": "Page",
                "revisions": [revision(1)],
            }
        )
    )
    [event] = list(project([page], media=[item]))
    index = event.changes["_meta/wiki/media.csv"]
    assert isinstance(index, str)
    assert "File:Example.png" in index
    assert "192.0.2.1" in index
    assert index.endswith(",192.0.2.1\n")
