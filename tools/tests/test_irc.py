from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from jbomohi_tools.git import Identity, commit_event
from jbomohi_tools.project.irc import (
    IrcAmendment,
    IrcParseError,
    SourceObject,
    parse_source,
    project,
    validate_rendered,
)


def source(path: str, text: str, channel: str = "lojban") -> SourceObject:
    return SourceObject(channel=channel, path=path, payload=text.encode())


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def test_iso_lines_preserve_zone_and_normalize_kinds_and_controls() -> None:
    item = SourceObject(
        channel="lojban",
        path="lojban/2014_03/2014_03_01.txt",
        payload=(
            b"2014-03-01 04:07:13 PST/-0800 <gleki> ma \x0305prali\x00\n"
            b"2014-03-01 05:25:18 PST/-0800 * Twey cortu le kerfa\n"
            b"2014-03-01 06:00:00 PST/-0800 *** server changed the topic\n"
        ),
    )
    [unit] = parse_source(item)
    assert unit.date_key == "2014-03-01"
    assert unit.tz == "-0800"
    assert unit.format == "iso"
    assert unit.body == (
        "04:07:13 <gleki> ma prali",
        "05:25:18 * Twey cortu le kerfa",
        "06:00:00 -- server changed the topic",
    )
    assert unit.messages == 2
    assert unit.nicks == 2
    assert unit.source_time.isoformat() == "2014-03-01T06:00:00-08:00"
    validate_rendered(unit)


def test_legacy_combined_source_splits_exact_days_with_unknown_zone() -> None:
    units = parse_source(
        source(
            "lojban/2002_middle/2002_05_12--2002_11_28.txt",
            "12 May 2002 23:59:00 <a> first\n13 May 2002 00:01:02 <b> second\n",
        )
    )
    assert [unit.date_key for unit in units] == ["2002-05-12", "2002-05-13"]
    assert all(unit.time_confidence == "tz-unknown" for unit in units)
    assert units[1].source_time.isoformat() == "2002-05-13T00:01:02+00:00"


def test_pre_utf8_and_transitional_dated_sources_normalize_deterministically() -> None:
    item = SourceObject(
        "lojban",
        "lojban/2010_10/2010_10_02.txt",
        (
            b"02 Oct 2010 20:49:12 <Zarutian> caf\xe9\x1c lojban\n"
            b"2010-10-02 21:58:00 EDT/-0400 <latros> coi rodo\n"
            b"2010-10-02 22:00:00 EDT/-0400 <Nts\xc3\xa9kees> valid UTF-8\n"
        ),
    )
    [unit] = parse_source(item)
    assert unit.format == "legacy"
    assert unit.tz == "unknown"
    assert unit.body == (
        "20:49:12 <Zarutian> café lojban",
        "21:58:00 <latros> coi rodo",
        "22:00:00 <Ntsékees> valid UTF-8",
    )


def test_legacy_secondless_full_dates_get_zero_seconds() -> None:
    [unit] = parse_source(
        source(
            "lojban/2010_09/2010_09_19.txt",
            "19 Sep 2010 00:35 < remod> coi rodo\n",
        )
    )
    assert unit.body == ("00:35:00 <remod> coi rodo",)


def test_empty_source_file_has_no_event() -> None:
    assert parse_source(SourceObject("lojban", "lojban/empty.txt", b"")) == []


def test_wholly_undated_file_uses_explicit_clock_placeholder() -> None:
    [unit] = parse_source(
        source(
            "lojban/2002_12/2002_12_27.txt",
            "<Ellmist> ki'e\n*** lalo changes nickname\n",
        )
    )
    assert unit.date_key == "2002-12-27"
    assert unit.format == "undated"
    assert unit.undated_lines == 2
    assert unit.time_confidence == "window"
    assert unit.event_window == "2002-12-27..2002-12-27"
    assert unit.body == (
        "--:--:-- <Ellmist> ki'e",
        "--:--:-- -- lalo changes nickname",
    )
    validate_rendered(unit)


def test_dated_file_keeps_undated_tail_in_source_order() -> None:
    [unit] = parse_source(
        source(
            "lojban/2003_08/2003_08_19-02_21.txt",
            "18 Aug 2003 15:09:37 <Mhoram> dated\n<rlpowell> timestamp absent\n",
        )
    )
    assert unit.format == "legacy+undated"
    assert unit.body == (
        "15:09:37 <Mhoram> dated",
        "--:--:-- <rlpowell> timestamp absent",
    )
    assert unit.undated_lines == 1


def test_iso_dst_transition_day_is_marked_timezone_unknown() -> None:
    [unit] = parse_source(
        source(
            "lojban/2010_11/2010_11_07.txt",
            "2010-11-07 01:30:00 EDT/-0400 <a> before\n"
            "2010-11-07 01:15:00 EST/-0500 <b> after\n",
        )
    )
    assert unit.tz == "unknown"
    assert unit.time_confidence == "tz-unknown"


def test_irssi_day_markers_reconstruct_june_2015_dates() -> None:
    units = parse_source(
        source(
            "lojban/2015_06/lojban-special.2015.06.log",
            "--- Log opened Mon Jun 01 00:00:19 2015\n"
            "00:02 < noncomcinse> cy. mo\n"
            "04:00  * nuzba posts news\n"
            "--- Day changed Tue Jun 02 2015\n"
            "02:06 -!- Irssi: #lojban: Total of 141 nicks\n"
            "11:51 <@gleki> exp: lo ka mo\n"
            "--- Log closed Wed Jun 03 00:00:20 2015\n",
        )
    )
    assert [unit.date_key for unit in units] == ["2015-06-01", "2015-06-02"]
    assert units[0].body == (
        "00:02:00 <noncomcinse> cy. mo",
        "04:00:00 * nuzba posts news",
    )
    assert units[1].body == (
        "02:06:00 -- Irssi: #lojban: Total of 141 nicks",
        "11:51:00 <gleki> exp: lo ka mo",
    )
    assert units[1].output_path == "irc/lojban/2015/2015-06-02.txt"


def test_bracket_range_is_one_window_unit_with_ordinal_boundaries() -> None:
    [unit] = parse_source(
        source(
            "lojban/2000_all/2000_05_26--2000_10_28.txt",
            "[23:59] <a> first\n"
            "[00:01] <b> second active day\n"
            "[12:00] *** topic changed\n"
            "[00:00] * c third active day\n",
        )
    )
    assert unit.output_path == "irc/lojban/2000/2000-05-26--2000-10-28.txt"
    assert unit.date_key == "2000-05-26..2000-10-28"
    assert unit.body == (
        "23:59:00 <a> first",
        "-- day boundary 1",
        "00:01:00 <b> second active day",
        "12:00:00 -- topic changed",
        "-- day boundary 2",
        "00:00:00 * c third active day",
    )
    assert unit.header.endswith("format=bracket days=unknown")
    assert unit.days_observed == 3
    assert unit.days_in_range == 156
    assert unit.time_confidence == "window"
    assert unit.event_window == "2000-05-26..2000-10-28"
    assert unit.source_time.isoformat() == "2000-10-28T23:59:59+00:00"
    validate_rendered(unit)


def test_project_emits_day_file_and_cumulative_rfc4180_index() -> None:
    sources = [
        source(
            "lojban/2014_03/2014_03_01.txt",
            "2014-03-01 04:07:13 PST/-0800 <gleki> first\n",
        ),
        source(
            "lojban/2014_03/2014_03_02.txt",
            "2014-03-02 05:00:00 PST/-0800 <ilmen> second\n",
        ),
    ]
    events = list(project(sources))
    assert len(events) == 2
    assert events[0].source == "irc/lojban"
    assert events[0].source_id == "2014-03-01"
    assert events[0].author == Identity.irc()
    assert events[0].event == "import"
    assert set(events[0].changes) == {"irc/lojban/2014/2014-03-01.txt"}
    index = events[1].changes["_meta/irc/lojban/days.csv"]
    assert isinstance(index, str)
    assert index.splitlines() == [
        "date,lines,messages,nicks,tz,format,source,days_observed,days_in_range,undated_lines,fragments",
        "2014-03-01,1,1,1,-0800,iso,lojban/2014_03/2014_03_01.txt,,,,1",
        "2014-03-02,1,1,1,-0800,iso,lojban/2014_03/2014_03_02.txt,,,,1",
    ]


def test_project_records_absent_source_days_as_gaps() -> None:
    first = source(
        "lojban/2014_03/2014_03_01.txt",
        "2014-03-01 04:07:13 PST/-0800 <gleki> first\n",
    )
    third = source(
        "lojban/2014_03/2014_03_03.txt",
        "2014-03-03 04:07:13 PST/-0800 <gleki> third\n",
    )
    events = list(project([first, third]))
    assert "_meta/irc/lojban/gaps.csv" not in events[0].changes
    assert events[1].changes["_meta/irc/lojban/gaps.csv"] == (
        "date,reason\n2014-03-02,no source file\n"
    )


def test_projected_days_commit_as_one_source_event_each(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    git(corpus, "init", "--initial-branch=main")
    sources = [
        source(
            "lojban/2014_03/2014_03_01.txt",
            "2014-03-01 04:07:13 PST/-0800 <gleki> first\n",
        ),
        source(
            "lojban/2014_03/2014_03_02.txt",
            "2014-03-02 05:00:00 PST/-0800 <ilmen> second\n",
        ),
    ]
    for event in project(sources):
        commit_event(event, corpus)
    assert git(corpus, "rev-list", "--count", "HEAD") == "2"
    assert set(git(corpus, "ls-tree", "-r", "--name-only", "HEAD").splitlines()) == {
        "_meta/irc/lojban/days.csv",
        "irc/lojban/2014/2014-03-01.txt",
        "irc/lojban/2014/2014-03-02.txt",
    }
    log = git(
        corpus,
        "log",
        "--reverse",
        "--format=%an <%ae>|%aI|%(trailers:key=Source-Id,valueonly)",
    )
    assert [line for line in log.splitlines() if line] == [
        "irclogs <irclogs@irc.lojban.org>|2014-03-01T04:07:13-08:00|2014-03-01",
        "irclogs <irclogs@irc.lojban.org>|2014-03-02T05:00:00-08:00|2014-03-02",
    ]


def test_update_amendment_uses_unique_digest_id_and_supersession_trailer() -> None:
    item = source(
        "lojban/2014_03/2014_03_01.txt",
        "2014-03-01 04:07:13 PST/-0800 <gleki> corrected\n",
    )
    output_path = "irc/lojban/2014/2014-03-01.txt"
    [event] = list(
        project(
            [item],
            amendments={
                output_path: IrcAmendment("a" * 64, "b" * 64),
            },
        )
    )
    assert event.event == "edited"
    assert event.source_id == "2014-03-01@aaaaaaaaaaaa"
    assert event.trailers == {"Supersedes-Manifestation": "bbbbbbbbbbbb"}


def test_update_amendment_rejects_noncanonical_digests() -> None:
    item = source(
        "lojban/2014_03/2014_03_01.txt",
        "2014-03-01 04:07:13 PST/-0800 <gleki> corrected\n",
    )
    with pytest.raises(IrcParseError, match="64 lowercase hex"):
        list(
            project(
                [item],
                amendments={
                    "irc/lojban/2014/2014-03-01.txt": IrcAmendment("short", None)
                },
            )
        )
    with pytest.raises(IrcParseError, match="unprojected paths"):
        list(
            project(
                [item],
                amendments={
                    "irc/lojban/2014/missing.txt": IrcAmendment("a" * 64, None)
                },
            )
        )


def test_project_merges_overlapping_source_fragments() -> None:
    first = source(
        "lojban/a.txt",
        "2014-03-01 04:07:13 PST/-0800 <gleki> first\n",
    )
    second = replace(
        first,
        path="lojban/b.txt",
        payload=b"2014-03-01 05:00:00 PST/-0800 <ilmen> second\n",
    )
    [event] = list(project([second, first]))
    output = event.changes["irc/lojban/2014/2014-03-01.txt"]
    assert isinstance(output, str)
    assert output.splitlines()[1:] == [
        "04:07:13 <gleki> first",
        "05:00:00 <ilmen> second",
    ]
    assert list(project([first, second])) == list(project([second, first]))


def test_project_merges_dated_and_undated_fragments_for_one_day() -> None:
    dated = source(
        "lojban/2002_12/dated.txt",
        "31 Dec 2002 12:00:00 <a> dated\n",
    )
    undated = source(
        "lojban/2002_12/2002_12_31-02_21.txt",
        "<b> timestamp absent\n",
    )
    [event] = list(project([undated, dated]))
    output = event.changes["irc/lojban/2002/2002-12-31.txt"]
    assert isinstance(output, str)
    assert output.splitlines()[0].endswith("format=legacy+undated")
    assert output.splitlines()[1:] == [
        "12:00:00 <a> dated",
        "--:--:-- <b> timestamp absent",
    ]
    assert event.time_confidence == "window"
    assert event.event_window == "2002-12-31..2002-12-31"


def test_iso_irssi_merge_prefers_exact_seconds_and_keeps_unique_lines() -> None:
    iso = source(
        "lojban/2015_06/2015_06_02.txt",
        "2015-06-02 11:51:37 PDT/-0700 <gleki> shared\n"
        "2015-06-02 12:00:02 PDT/-0700 <ilmen> iso only\n",
    )
    irssi = source(
        "lojban/2015_06/lojban-special.2015.06.log",
        "--- Log opened Tue Jun 02 00:00:19 2015\n"
        "11:51 < gleki> shared\n"
        "13:00 < selpahi> irssi only\n",
    )
    [event] = list(project([irssi, iso]))
    output = event.changes["irc/lojban/2015/2015-06-02.txt"]
    assert isinstance(output, str)
    assert output.splitlines()[1:] == [
        "11:51:37 <gleki> shared",
        "12:00:02 <ilmen> iso only",
        "13:00:00 <selpahi> irssi only",
    ]
    assert output.splitlines()[0].endswith("format=iso+irssi")
    assert "tz=-0700" in output.splitlines()[0]
    assert (
        "source=lojban/2015_06/2015_06_02.txt,lojban/2015_06/lojban-special.2015.06.log"
    ) in output.splitlines()[0]
    index = event.changes["_meta/irc/lojban/days.csv"]
    assert isinstance(index, str)
    assert index.splitlines()[1].endswith(",,,2")


def test_disjoint_iso_irssi_fragments_do_not_infer_a_timezone() -> None:
    iso = source(
        "lojban/2015_07/2015_07_27.txt",
        "2015-07-27 12:00:02 PDT/-0700 <a> iso only\n",
    )
    irssi = source(
        "lojban/2015_07/lojban-special.2015.07.log",
        "--- Log opened Mon Jul 27 00:00:19 2015\n13:00 < b> irssi only\n",
    )
    [event] = list(project([irssi, iso]))
    output = event.changes["irc/lojban/2015/2015-07-27.txt"]
    assert isinstance(output, str)
    assert "tz=unknown" in output.splitlines()[0]
    assert output.splitlines()[0].endswith("format=irssi")


@pytest.mark.parametrize(
    "item",
    [
        source("lojban/bad.txt", "not a log line\n"),
        source("lojban/bad.txt", "2014-03-01 25:00:00 PST/-0800 <a> bad\n"),
        SourceObject("Bad Channel", "x.txt", b"[00:00] <a> bad\n"),
    ],
)
def test_invalid_source_shapes_fail_closed(item: SourceObject) -> None:
    with pytest.raises(IrcParseError):
        parse_source(item)


def test_units_sort_by_actual_instant_across_offsets() -> None:
    early = source(
        "lojban/early.txt",
        "2014-03-01 04:00:00 PST/-0800 <a> noon UTC\n",
    )
    later = source(
        "ckule/later.txt",
        "2014-03-01 13:00:00 UTC/+0000 <b> later\n",
        channel="ckule",
    )
    events = list(project([later, early]))
    assert [event.source for event in events] == ["irc/lojban", "irc/ckule"]
    assert events[1].source_time - events[0].source_time == timedelta(hours=1)
