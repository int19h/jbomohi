from __future__ import annotations

import zipfile
from dataclasses import replace
from datetime import UTC, datetime

from jbomohi_tools.project.mail import (
    MailManifestation,
    RawMessage,
    _Container,
    _link,
    _thread_key,
    _thread_order,
    deduplicate,
    load_mbox,
    load_mh_zip,
    load_numbered_rfc822,
    normalize_message_id,
    normalize_subject,
    parse_mail,
    project,
    reconstruct_mhonarc,
)


def message(
    message_id: str | None,
    *,
    subject: str = "Topic",
    sender: str = "Alice <alice@example.org>",
    date: str = "Sat, 1 Jan 2000 00:00:00 +0000",
    references: str | None = None,
    body: str = "body",
    content_type: str = "text/plain; charset=utf-8",
    extra: tuple[str, ...] = (),
) -> bytes:
    headers = [f"From: {sender}", f"Date: {date}", f"Subject: {subject}"]
    if message_id is not None:
        headers.append(f"Message-ID: <{message_id}>")
    if references is not None:
        headers.extend([f"References: <{references}>", f"In-Reply-To: <{references}>"])
    headers.extend(extra)
    headers.extend([f"Content-Type: {content_type}", "", body])
    return "\r\n".join(headers).encode()


def manifestation(
    payload: bytes,
    *,
    order: int,
    source: str = "lists-plain",
    provenance: str | None = None,
) -> MailManifestation:
    return MailManifestation(
        list_name="lojban-list",
        raw=RawMessage(payload=payload),
        manifestation=source,
        provenance=provenance or f"fixture/{order}",
        archive_order=order,
        archive_time=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_message_id_and_subject_normalization() -> None:
    assert normalize_message_id(" &lt;AbC&#45;1@Example.ORG&gt; ") == (
        "abc-1@example.org"
    )
    assert normalize_subject("[lojban] Re[2]: Fwd:  Topic  name") == "topic name"


def test_dedupe_keeps_more_headers_then_source_rank() -> None:
    sparse = manifestation(
        message("same@example.org", body="sparse"),
        order=0,
        source="lists-plain",
        provenance="maildir/sparse",
    )
    rich = manifestation(
        message(
            "SAME@example.org",
            body="rich",
            extra=("List-Id: <lojban-list.example.org>", "X-Archive: old"),
        ),
        order=1,
        source="files-mbox",
        provenance="mbox/rich",
    )
    richest = manifestation(
        message(
            "same@example.org",
            body="richest",
            extra=(
                "List-Id: <lojban-list.example.org>",
                "X-Archive: final",
                "X-Extra: present",
            ),
        ),
        order=2,
        source="old-lojban-list",
        provenance="numbered/richest",
    )
    winners, duplicates = deduplicate((sparse, rich, richest))
    assert len(winners) == 1
    assert winners[0].manifestation.provenance == "numbered/richest"
    assert len(duplicates) == 2
    assert all(
        item.winner.manifestation.provenance == "numbered/richest"
        for item in duplicates
    )


def test_project_keeps_raw_maildir_and_builds_reference_thread() -> None:
    root_raw = message("root@example.org", body="root body")
    child_raw = message(
        "child@example.org",
        subject="Re: Topic",
        references="root@example.org",
        date="Sat, 1 Jan 2000 00:01:00 +0000",
        body="<p>child<br>body</p>",
        content_type="text/html; charset=utf-8",
    )
    events = list(
        project(
            (
                manifestation(root_raw, order=0),
                manifestation(child_raw, order=1),
            )
        )
    )
    assert [event.source_id for event in events] == [
        "root@example.org",
        "child@example.org",
    ]
    raw_path = next(path for path in events[0].changes if "/cur/" in path)
    assert events[0].changes[raw_path] == root_raw
    assert raw_path.endswith(".jbomohi:2,S")
    thread_path = next(path for path in events[1].changes if "/threads/" in path)
    thread = events[1].changes[thread_path]
    assert isinstance(thread, str)
    assert "root body" in thread
    assert "child\nbody" in thread
    assert "[html]" in thread
    assert events[0].trailers["Thread"] == events[1].trailers["Thread"]
    assert all(len(event.subject) <= 72 for event in events)
    assert "_meta/mail/lojban-list/messages.csv" in events[-1].changes
    assert "_meta/mail/lojban-list/coverage.toml" in events[-1].changes
    coverage = events[-1].changes["_meta/mail/lojban-list/coverage.toml"]
    assert "jbomohi archive fetch old-lojban-list" in coverage
    assert "--list lojban-list-old --start 1" in coverage
    assert "mail/lojban-list/new/.keep" in events[0].changes
    assert "mail/lojban-list/tmp/.keep" in events[0].changes


def test_missing_message_id_gets_raw_hash_identity_and_window_date() -> None:
    raw = b"From: sender@example.org\r\nSubject: no id\r\n\r\nbody"
    events = list(project((manifestation(raw, order=0),)))
    assert events[0].source_id.endswith("@jbomohi.invalid")
    assert events[0].time_confidence == "window"
    assert events[0].event_window == "2026-01-01..2026-01-01"


def test_reconstruct_mhonarc_uses_comments_headers_and_rendered_body() -> None:
    page = b"""<!--X-Subject: Re: Test -->
<!--X-Date: Sat, 17 May 2003 15:37:00 &#45;0700 -->
<!--X-Message-Id: child@example.org -->
<!--X-Reference: root@example.org -->
<li><em>From</em>: Robin &lt;<a href="mailto:r@example.org">r@example.org</a>&gt;</li>
<li><em>To</em>: list@example.org</li>
<li><em>In-reply-to</em>: &lt;root@example.org&gt;</li>
<!--X-Body-of-Message--><pre>one &amp; two
three</pre><!--X-Body-of-Message-End-->
"""
    reconstructed = reconstruct_mhonarc(page)
    assert b"From: Robin <r@example.org>\r\n" in reconstructed
    assert b"Message-ID: <child@example.org>\r\n" in reconstructed
    assert b"References: <root@example.org>\r\n" in reconstructed
    assert b"X-Jbomohi-Manifestation: mhonarc\r\n" in reconstructed
    assert reconstructed.endswith(b"one & two\r\nthree\r\n")


def test_reconstruct_mhonarc_r13_fallback_restores_at_sign() -> None:
    page = b"""<!--X-Subject: Test -->
<!--X-Date: Sat, 17 May 2003 15:37:00 &#45;0700 -->
<!--X-Message-Id: test@example.org -->
<!--X-From-R13: n.ebfgnNylpbf.pb.hx -->
<!--X-Body-of-Message--><pre>body</pre><!--X-Body-of-Message-End-->
"""
    reconstructed = reconstruct_mhonarc(page)
    assert b"From: a.rosta@lycos.co.uk\r\n" in reconstructed


def test_numbered_raw_and_mbox_adapters_remove_transport_envelopes(
    tmp_path,
) -> None:
    numbered = tmp_path / "numbered"
    numbered.mkdir()
    (numbered / "1").write_bytes(
        b"From sender@example.org Sat Jan 1 00:00:00 2000\n"
        + message("one@example.org")
    )
    [raw_message] = list(load_numbered_rfc822(numbered, list_name="lojban-list"))
    assert raw_message.raw.read().startswith(b"From: Alice")

    mbox = tmp_path / "mail.mbox"
    mbox.write_bytes(
        b"orphaned preamble is not a message\n"
        b"From sender@example.org Sat Jan 1 00:00:00 2000\n"
        + message("one@example.org", body=">From escaped\nFrom ordinary body line")
        + b"\nFrom sender@example.org Sat Jan 1 00:01:00 2000\n"
        + message("two@example.org", body="second")
    )
    loaded = list(load_mbox(mbox, list_name="lojban-list"))
    assert len(loaded) == 2
    assert b"\r\nFrom escaped" in loaded[0].raw.read()
    assert b"From ordinary body line" in loaded[0].raw.read()


def test_mh_zip_adapter_loads_only_numeric_message_members(tmp_path) -> None:
    path = tmp_path / "jbosnu_raw.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("jbosnu_raw/.mh_sequences", "unseen: 2")
        archive.writestr("jbosnu_raw/2", message("two@example.org"))
        archive.writestr("jbosnu_raw/1", message("one@example.org"))
    loaded = list(load_mh_zip(path))
    assert [item.archive_order for item in loaded] == [0, 1]
    assert b"<one@example.org>" in loaded[0].raw.read()


def test_subject_fallback_only_joins_recent_orphans() -> None:
    rows = (
        manifestation(
            message(
                "a@example.org",
                subject="Question",
                date="Sat, 1 Jan 2000 00:00:00 +0000",
            ),
            order=0,
        ),
        manifestation(
            message(
                "b@example.org",
                subject="Re: Question",
                date="Sun, 30 Jan 2000 00:00:00 +0000",
            ),
            order=1,
        ),
        manifestation(
            message(
                "d@example.org",
                subject="Question",
                references="phantom@example.org",
                date="Tue, 1 Feb 2000 00:00:00 +0000",
            ),
            order=2,
        ),
        manifestation(
            message(
                "c@example.org",
                subject="Question",
                date="Thu, 1 Jun 2000 00:00:00 +0000",
            ),
            order=3,
        ),
    )
    parsed, _duplicates = deduplicate(rows)
    roots, threads = _thread_order(parsed)
    assert roots["a@example.org"] == roots["b@example.org"]
    assert roots["d@example.org"] == "phantom@example.org"
    assert roots["d@example.org"] != roots["a@example.org"]
    assert roots["c@example.org"] not in {
        roots["a@example.org"],
        roots["d@example.org"],
    }
    assert sorted(map(len, threads.values())) == [1, 1, 2]


def test_spam_headers_require_positive_prefix_not_rule_name() -> None:
    clean = parse_mail(
        manifestation(
            message(
                "clean@example.org",
                extra=("X-Spam-Status: No, hits=1 tests=SPAM_PHRASE_00_01",),
            ),
            order=0,
        )
    )
    spam = parse_mail(
        manifestation(
            message("spam@example.org", extra=("X-Spam-Status: Yes, score=9",)),
            order=1,
        )
    )
    assert not clean.spam_suspect
    assert spam.spam_suspect


def test_raw_8bit_from_and_subject_never_become_replacement_characters() -> None:
    raw = (
        b"From: Jos\xe9 Blanco <jose@example.org>\r\n"
        b"Date: Sat, 1 Jan 2000 00:00:00 +0000\r\n"
        b"Subject: Caf\xe9\r\n"
        b"Message-ID: <eight@example.org>\r\n\r\nbody"
    )
    parsed = parse_mail(manifestation(raw, order=0))
    assert parsed.from_name == "José Blanco"
    assert parsed.subject == "Café"
    assert parsed.raw_8bit_headers == 2
    [event] = list(project((manifestation(raw, order=0),)))
    assert "�" not in event.author.name
    thread = next(value for path, value in event.changes.items() if "/threads/" in path)
    assert "José Blanco" in thread
    coverage = event.changes["_meta/mail/lojban-list/coverage.toml"]
    assert "raw_8bit_headers = 2" in coverage


def test_window_date_uses_nearest_archive_neighbors() -> None:
    before = manifestation(
        message("before@example.org", date="Sat, 1 Jan 2000 00:00:00 +0000"),
        order=0,
        source="files-mbox",
    )
    middle = manifestation(
        b"From: Alice <alice@example.org>\r\nSubject: undated\r\n\r\nbody",
        order=1,
        source="files-mbox",
    )
    after = manifestation(
        message("after@example.org", date="Mon, 3 Jan 2000 00:00:00 +0000"),
        order=2,
        source="files-mbox",
    )
    winners, _duplicates = deduplicate((before, middle, after))
    undated = next(item for item in winners if not item.source_dated)
    assert undated.timestamp == datetime(2000, 1, 1, tzinfo=UTC)
    assert undated.event_window == "2000-01-01..2000-01-03"


def test_undated_no_id_fallback_dedupes_across_archive_fetch_times() -> None:
    raw = b"From: Alice <alice@example.org>\r\nSubject: same\r\n\r\nbody"
    first = manifestation(raw, order=0, source="files-mbox")
    second = replace(
        manifestation(raw, order=0, source="old-lojban-list"),
        archive_time=datetime(2027, 1, 1, tzinfo=UTC),
    )
    winners, duplicates = deduplicate((first, second))
    assert len(winners) == 1
    assert len(duplicates) == 1


def test_reference_cycle_guard_refuses_the_cyclic_link() -> None:
    parent = _Container("parent")
    child = _Container("child")
    assert _link(parent, child)
    assert not _link(child, parent)
    assert parent.parent is None


def test_phantom_reference_is_thread_root_and_key_input() -> None:
    parsed, _duplicates = deduplicate(
        (
            manifestation(
                message(
                    "child@example.org",
                    references="phantom@example.org",
                ),
                order=0,
            ),
        )
    )
    roots, threads = _thread_order(parsed)
    assert roots["child@example.org"] == "phantom@example.org"
    assert list(threads) == ["phantom@example.org"]
    assert _thread_key("phantom@example.org", "topic").startswith("6992fbabfb82-")


def test_a_date_at_or_before_the_epoch_is_not_a_date() -> None:
    """A header no message on these lists could carry is corrupt, not history.

    SPEC.md 2.6 reserves `pre-epoch` for documents that genuinely predate 1970
    and 3.3 says a mail date is never the Unix epoch, so such a header is
    discarded and the next evidence is used, exactly as for one that does not
    parse. Without this the whole build fails closed on one broken header.
    """

    epoch_dated = manifestation(
        message("epoch@example.org", date="Thu, 1 Jan 1970 00:00:00 +0000"),
        order=0,
    )
    parsed = parse_mail(epoch_dated)
    assert parsed.time_confidence == "window"
    assert parsed.source_dated is False
    assert parsed.timestamp == datetime(2026, 1, 1, tzinfo=UTC)

    before = manifestation(
        message("before@example.org", date="Wed, 31 Dec 1969 23:59:59 +0000"),
        order=1,
    )
    assert parse_mail(before).time_confidence == "window"

    # A Received: header is the next evidence, and is refused on the same terms.
    received = manifestation(
        message(
            "received@example.org",
            date="Thu, 1 Jan 1970 00:00:00 +0000",
            extra=("Received: from host by list; Sat, 1 Jan 2000 12:00:00 +0000",),
        ),
        order=2,
    )
    recovered = parse_mail(received)
    assert recovered.time_confidence == "tz-unknown"
    assert recovered.timestamp == datetime(2000, 1, 1, 12, tzinfo=UTC)

    # A real date is still exact, and the first second after the epoch counts.
    just_after = manifestation(
        message("after@example.org", date="Thu, 1 Jan 1970 00:00:01 +0000"),
        order=3,
    )
    assert parse_mail(just_after).time_confidence == "exact"
    assert parse_mail(just_after).timestamp == datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)
