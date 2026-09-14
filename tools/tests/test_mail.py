from __future__ import annotations

from datetime import UTC, datetime

from jbomohi_tools.project.mail import (
    MailManifestation,
    RawMessage,
    deduplicate,
    normalize_message_id,
    normalize_subject,
    project,
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
    winners, duplicates = deduplicate((sparse, rich))
    assert len(winners) == 1
    assert winners[0].manifestation.provenance == "mbox/rich"
    assert duplicates[0].loser.manifestation.provenance == "maildir/sparse"


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
    assert "mail/lojban-list/new/.keep" in events[0].changes
    assert "mail/lojban-list/tmp/.keep" in events[0].changes


def test_missing_message_id_gets_raw_hash_identity_and_window_date() -> None:
    raw = b"From: sender@example.org\r\nSubject: no id\r\n\r\nbody"
    events = list(project((manifestation(raw, order=0),)))
    assert events[0].source_id.endswith("@jbomohi.invalid")
    assert events[0].time_confidence == "window"
    assert events[0].event_window == "2026-01-01..2026-01-01"
