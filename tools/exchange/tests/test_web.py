"""Tests for the exchange snapshot and read-only web server."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
sys.path.insert(0, str(TOOL_DIR))

import exchange  # noqa: E402
import web as exchange_web  # noqa: E402


REGISTRY = """
protocol = "jbomohi-mail/v1"
spool = ".exchange"
[models.codex]
active = true
display_name = "Codex"
client = "codex"
model = "gpt"
broadcast_recipient = true
[models.fable]
active = true
display_name = "Fable"
client = "claude"
model = "fable"
broadcast_recipient = true
[models.human]
active = true
display_name = "human partner"
client = "none"
model = "human"
sessions = false
broadcast_recipient = false
acknowledges = false
"""

FABLE_SESSION = """---
protocol: jbomohi-mail/v1
session: fable_1
model: fable
client: claude
model_name: fable
index: 1
created_utc: 2026-08-26T12:00:00Z
status: active
---

"""

CODEX_SESSION = """---
protocol: jbomohi-mail/v1
session: codex_1
model: codex
client: codex
model_name: gpt
index: 1
created_utc: 2026-08-26T12:00:01Z
status: active
---

"""

ROOT_ID = "20260826T120100Z-fable_1-reader-proposal"
REPLY_ID = "20260826T120200Z-codex_1-reader-response"

ROOT_MESSAGE = f"""---
protocol: jbomohi-mail/v1
id: {ROOT_ID}
from: fable_1
to: codex_1
audience: direct
created_utc: 2026-08-26T12:01:00Z
kind: proposal
model: fable
client: claude
ack_required: true
in_reply_to: none
supersedes: none
github_issues: #30
---

# Reader proposal

Show the exchange as navigable conversations.
"""

REPLY_MESSAGE = f"""---
protocol: jbomohi-mail/v1
id: {REPLY_ID}
from: codex_1
to: fable_1
audience: direct
created_utc: 2026-08-26T12:02:00Z
kind: response
model: gpt
client: codex
ack_required: false
in_reply_to: {ROOT_ID}
supersedes: {ROOT_ID}
github_issues: #30
---

## Reader response

The first product slice is complete.
"""

ROOT_ACK = f"""---
protocol: jbomohi-mail/v1
acknowledges: {ROOT_ID}
by: codex_1
created_utc: 2026-08-26T12:03:00Z
---

Read and disposition captured in: response above.
"""


class WebReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        control = self.tmp / "tools" / "exchange"
        control.mkdir(parents=True)
        (control / "participants.toml").write_text(REGISTRY)
        spool = self.tmp / ".exchange"
        (spool / "sessions").mkdir(parents=True)
        (spool / "sessions" / "fable_1.md").write_text(FABLE_SESSION)
        (spool / "sessions" / "codex_1.md").write_text(CODEX_SESSION)
        (spool / "messages").mkdir()
        (spool / "messages" / f"{ROOT_ID}.md").write_text(ROOT_MESSAGE)
        (spool / "messages" / f"{REPLY_ID}.md").write_text(REPLY_MESSAGE)
        (spool / "acks" / "codex_1").mkdir(parents=True)
        (spool / "acks" / "codex_1" / f"{ROOT_ID}.ack.md").write_text(ROOT_ACK)

    def snapshot(self):
        return exchange.build_snapshot(exchange.Registry(self.tmp))

    def test_snapshot_groups_replies_and_exposes_disposition_state(self):
        data = self.snapshot()
        self.assertTrue(data["healthy"], data["errors"])
        self.assertEqual(data["protocol"], "jbomohi-mail/v1")
        self.assertNotIn("generation", data)
        self.assertEqual(data["stats"]["threads"], 1)
        self.assertEqual(data["stats"]["messages"], 2)
        thread = data["threads"][0]
        self.assertEqual(thread["id"], ROOT_ID)
        self.assertEqual(thread["title"], "Reader proposal")
        self.assertEqual(thread["message_ids"], [ROOT_ID, REPLY_ID])
        self.assertNotIn("has_legacy", thread)
        by_id = {message["id"]: message for message in data["messages"]}
        self.assertEqual(by_id[REPLY_ID]["root_id"], ROOT_ID)
        self.assertEqual(by_id[REPLY_ID]["depth"], 1)
        self.assertEqual(by_id[ROOT_ID]["superseded_by"], [REPLY_ID])
        self.assertEqual(by_id[ROOT_ID]["pending_for"], [])
        self.assertEqual(by_id[ROOT_ID]["acknowledgements"][0]["disposition"], "response above.")
        self.assertFalse(by_id[REPLY_ID]["ack_required"])
        self.assertNotIn("legacy", by_id[ROOT_ID])

    def test_snapshot_reports_invalid_files_without_including_them(self):
        bad = self.tmp / ".exchange" / "messages" / "bad.md"
        bad.write_text("not front matter")
        data = self.snapshot()
        self.assertFalse(data["healthy"])
        self.assertTrue(any("missing opening" in error for error in data["errors"]))
        self.assertEqual(data["stats"]["messages"], 2)

    def test_cache_keeps_last_snapshot_after_interrupted_read(self):
        cache = exchange_web.SnapshotCache(self.tmp)
        first = cache.read()
        self.assertFalse(first["stale"])
        with mock.patch.object(exchange_web, "build_snapshot", side_effect=OSError("race")):
            second = cache.read()
        self.assertTrue(second["stale"])
        self.assertFalse(second["healthy"])
        self.assertEqual(second["stats"]["messages"], first["stats"]["messages"])
        self.assertIn("interrupted", second["errors"][0])

    def test_server_exposes_snapshot_and_allow_lists_static_paths(self):
        server = exchange_web.make_server(self.tmp, "127.0.0.1", 0, quiet=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(f"{url}/api/snapshot") as response:
                data = json.load(response)
                self.assertEqual(data["stats"]["threads"], 1)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
                self.assertIn("JbomohiExchangeReader/1", response.headers["Server"])
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(f"{url}/../participants.toml")
            self.assertEqual(denied.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
