from __future__ import annotations

import gzip
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.archive.mail import (
    MailFetchError,
    extract_maildir_zip,
    fetch_jbosnu_raw,
    fetch_mail_mboxes,
    fetch_maildir_zip,
    fetch_mhonarc,
    fetch_old_lojban_list,
    inspect_maildir_zip,
    load_jbosnu_manifestations,
    load_mbox_manifestations,
    load_mhonarc_manifestations,
    load_old_lojban_manifestations,
)
from jbomohi_tools.archive.manifest import ArchiveManifest, object_path


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return stream.getvalue()


def test_maildir_zip_inventory_and_safe_extraction(tmp_path: Path) -> None:
    archive = tmp_path / "maildir.zip"
    archive.write_bytes(
        zip_bytes(
            {
                "maildir/cur/1.example:2,S": b"From: a@example.org\r\n\r\nbody",
                "maildir/new/2.example": b"From: b@example.org\r\n\r\nbody",
                "maildir/tmp/.keep": b"",
            }
        )
    )
    inventory = inspect_maildir_zip(archive)
    assert (inventory.cur, inventory.new, inventory.messages) == (1, 1, 2)
    destination = tmp_path / "out"
    assert extract_maildir_zip(archive, destination) == inventory
    assert (destination / "maildir/cur/1.example:2,S").is_file()


def test_maildir_zip_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    archive.write_bytes(zip_bytes({"../escape": b"bad"}))
    with pytest.raises(MailFetchError, match="unsafe maildir zip member"):
        inspect_maildir_zip(archive)


def test_fetch_maildir_zip_writes_verified_manifest(tmp_path: Path) -> None:
    payload = zip_bytes(
        {"maildir/cur/1.example:2,S": b"From: a@example.org\r\n\r\nbody"}
    )

    class Client:
        def download(self, url: str, destination) -> None:
            assert url.endswith("/lojban-list.maildir.zip")
            destination.write(payload)

    report = fetch_maildir_zip(
        tmp_path,
        "lojban-list",
        client=Client(),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    manifest = ArchiveManifest.load(report.manifest)
    assert manifest.kind == "maildir-zip"
    assert manifest.coverage["counts"]["messages"] == 1
    assert object_path(tmp_path, manifest.sha256).is_file()


def test_fetch_mhonarc_stops_at_404_and_resumes_existing_pages(tmp_path: Path) -> None:
    page = b"""<!--X-Subject: Test -->
<!--X-Date: Sat, 17 May 2003 15:37:00 &#45;0700 -->
<!--X-Message-Id: test@example.org -->
<li><em>From</em>: Test &lt;test@example.org&gt;</li>
<!--X-Body-of-Message--><pre>body</pre><!--X-Body-of-Message-End-->
"""

    class Client:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get(self, url: str) -> bytes | None:
            self.urls.append(url)
            return page if url.endswith("msg00000.html") else None

    first_client = Client()
    first = fetch_mhonarc(
        tmp_path,
        "announce",
        client=first_client,
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert (first.downloaded, first.reused, first.next_missing) == (1, 0, 1)
    assert ArchiveManifest.load(first.manifests[0]).kind == "mhonarc-page"

    second_client = Client()
    second = fetch_mhonarc(
        tmp_path,
        "announce",
        client=second_client,
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert (second.downloaded, second.reused, second.next_missing) == (0, 1, 1)
    assert second_client.urls == [
        "https://mail.lojban.org/lists/announce/msg00001.html"
    ]
    [manifestation] = list(load_mhonarc_manifestations(tmp_path, "announce"))
    assert manifestation.manifestation == "mhonarc"
    assert b"Message-ID: <test@example.org>" in manifestation.raw.read()


def test_fetch_jbosnu_raw_validates_mh_members_and_writes_manifest(
    tmp_path: Path,
) -> None:
    payload = zip_bytes(
        {
            "jbosnu_raw/.mh_sequences": b"",
            "jbosnu_raw/1": b"From: a@example.org\r\n\r\nbody",
        }
    )

    class Client:
        def download(self, url: str, destination) -> None:
            assert url.endswith("/lists/jbosnu_raw.zip")
            destination.write(payload)

    report = fetch_jbosnu_raw(
        tmp_path,
        client=Client(),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert report.messages == 1
    manifest = ArchiveManifest.load(report.manifest)
    assert manifest.kind == "mh-folder-zip"
    assert object_path(tmp_path, manifest.sha256).is_file()
    [loaded] = list(load_jbosnu_manifestations(tmp_path))
    assert b"From: a@example.org" in loaded.raw.read()


def test_fetch_old_lojban_list_stops_and_loads_numbered_raw(tmp_path: Path) -> None:
    raw = (
        b"From sender@example.org Sat Jan 1 00:00:00 2000\n"
        b"From: Sender <sender@example.org>\n"
        b"Date: Sat, 1 Jan 2000 00:00:00 +0000\n"
        b"Message-ID: <one@example.org>\n\nbody\n"
    )

    class Client:
        def get(self, url: str) -> bytes | None:
            return raw if url.endswith("/1") else None

    report = fetch_old_lojban_list(
        tmp_path,
        client=Client(),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert (report.downloaded, report.reused, report.next_missing) == (1, 0, 2)
    [loaded] = list(load_old_lojban_manifestations(tmp_path))
    assert loaded.raw.read().startswith(b"From: Sender")
    resumed = fetch_old_lojban_list(
        tmp_path,
        client=Client(),
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert (resumed.downloaded, resumed.reused, resumed.next_missing) == (0, 1, 2)


def test_fetch_old_lojban_list_records_empty_200_as_gap_and_continues(
    tmp_path: Path,
) -> None:
    raw = (
        b"From sender@example.org Sat Jan 1 00:00:00 2000\n"
        b"From: Sender <sender@example.org>\n"
        b"Date: Sat, 1 Jan 2000 00:00:00 +0000\n"
        b"Message-ID: <two@example.org>\n\nbody\n"
    )

    class Client:
        def get(self, url: str) -> bytes | None:
            if url.endswith("/1"):
                return b""
            if url.endswith("/2"):
                return raw
            return None

    report = fetch_old_lojban_list(
        tmp_path,
        client=Client(),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert (report.downloaded, report.next_missing) == (2, 3)
    manifests = [ArchiveManifest.load(path) for path in report.manifests]
    assert [item.coverage["counts"]["messages"] for item in manifests] == [0, 1]
    loaded = list(load_old_lojban_manifestations(tmp_path))
    assert len(loaded) == 1
    assert b"<two@example.org>" in loaded[0].raw.read()


def test_fetch_mail_mboxes_discovers_validates_and_loads_gzip(tmp_path: Path) -> None:
    raw = (
        b"From sender@example.org Sat Jan 1 00:00:00 2000\n"
        b"From: Sender <sender@example.org>\n"
        b"Date: Sat, 1 Jan 2000 00:00:00 +0000\n"
        b"Message-ID: <one@example.org>\n\nbody\n"
    )

    class Client:
        def get(self, url: str) -> bytes | None:
            if url.endswith("/lojban-list/"):
                return b'<a href="lojban-0001.gz">one</a>'
            return gzip.compress(raw)

    report = fetch_mail_mboxes(
        tmp_path,
        client=Client(),
        now=lambda: datetime(2026, 9, 14, tzinfo=UTC),
    )
    assert (report.downloaded, report.reused, report.messages) == (1, 0, 1)
    [loaded] = list(load_mbox_manifestations(tmp_path))
    assert b"Message-ID: <one@example.org>" in loaded.raw.read()
    resumed = fetch_mail_mboxes(
        tmp_path,
        client=Client(),
        now=lambda: datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert (resumed.downloaded, resumed.reused, resumed.messages) == (0, 1, 1)

    manifest_path = report.manifests[0]
    text = manifest_path.read_text()
    manifest_path.write_text(text.replace('"messages" = 1', '"messages" = 2'))
    with pytest.raises(MailFetchError, match="message count disagrees"):
        fetch_mail_mboxes(
            tmp_path,
            client=Client(),
            now=lambda: datetime(2026, 9, 16, tzinfo=UTC),
        )
