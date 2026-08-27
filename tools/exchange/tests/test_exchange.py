"""Tests for the exchange helper. Run: python3 -m unittest discover -s tools/exchange/tests"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "exchange.py"

REGISTRY = """
protocol = "jbomohi-mail/v1"
spool = ".exchange"
[models.codex]
active = true
display_name = "Codex"
client = "codex"
model = "m1"
broadcast_recipient = true
[models.fable]
active = true
display_name = "Fable"
client = "claude"
model = "m2"
broadcast_recipient = true
[models.inactive]
active = false
display_name = "Inactive"
client = "x"
model = "m3"
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


class ExchangeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "tools" / "exchange").mkdir(parents=True)
        (self.tmp / "tools" / "exchange" / "participants.toml").write_text(REGISTRY)
        for name in ("MESSAGE_TEMPLATE.md", "ACK_TEMPLATE.md"):
            (self.tmp / "tools" / "exchange" / name).write_text((HERE.parent / name).read_text())
        (self.tmp / "tools" / "exchange" / "exchange.py").write_text(TOOL.read_text())
        self.spool = self.tmp / ".exchange"
        self.spool.mkdir(parents=True)

    def run_tool(self, *args, env=None, expect=0):
        e = dict(os.environ)
        e.pop("JBOMOHI_EXCHANGE_ACTOR", None)
        if env:
            e.update(env)
        r = subprocess.run([sys.executable, str(self.tmp / "tools" / "exchange" / "exchange.py"), *args],
                           capture_output=True, text=True, env=e)
        if expect is not None:
            self.assertEqual(r.returncode, expect, f"{args}\nstdout: {r.stdout}\nstderr: {r.stderr}")
        return r

    def join(self, model, **kw):
        return self.run_tool("join", "--model", model).stdout.strip()

    def fill(self, draft: str, body: str = "\n# Title\n\nReal content.\n"):
        p = Path(draft)
        text = p.read_text()
        head, _, _ = text.partition("\n---\n")
        p.write_text(head + "\n---\n" + body)

    def new(self, actor, to, slug="note", **kw):
        args = ["new", "--actor", actor, "--to", to, "--kind", "handoff", "--slug", slug]
        for k, v in kw.items():
            args += [f"--{k.replace('_', '-')}", v]
        return self.run_tool(*args).stdout.strip()

    # ---- sessions

    def test_join_assigns_sequential_ids_per_model(self):
        self.assertEqual(self.join("fable"), "fable_1")
        self.assertEqual(self.join("fable"), "fable_2")
        self.assertEqual(self.join("fable"), "fable_3")
        self.assertEqual(self.join("codex"), "codex_1")
        out = self.run_tool("sessions").stdout
        self.assertIn("fable_3 model=fable", out)
        self.assertIn("codex_1 model=codex", out)

    def test_join_for_fable_yields_fable_1_then_fable_2(self):
        self.assertEqual(self.join("fable"), "fable_1")
        self.assertEqual(self.join("fable"), "fable_2")

    def test_join_refuses_fixed_inactive_and_unknown_models(self):
        self.run_tool("join", "--model", "human", expect=1)
        self.run_tool("join", "--model", "inactive", expect=3)
        self.run_tool("join", "--model", "nobody", expect=1)

    def test_bare_model_slug_is_not_an_actor(self):
        r = self.run_tool("status", "--actor", "fable", expect=3)
        self.assertIn("join --model fable", r.stderr)

    def test_retire_leaves_broadcast_but_stays_addressable(self):
        f1, c1, c2 = self.join("fable"), self.join("codex"), self.join("codex")
        self.run_tool("retire", "--actor", c2, "--note", "handed off")
        self.run_tool("retire", "--actor", c2, expect=4)  # twice is a collision
        d = self.new(f1, "all")
        self.fill(d)
        pub = self.run_tool("publish", "--actor", f1, d).stdout.strip()
        text = Path(pub).read_text()
        self.assertIn("to: codex_1\n", text)
        self.assertNotIn("codex_2", text.split("\n---\n")[0])
        d2 = self.new(f1, c2, slug="direct")
        self.fill(d2)
        self.run_tool("publish", "--actor", f1, d2)
        self.assertIn("pending_for_codex_2=1", self.run_tool("status", "--actor", c2).stdout)

    # ---- messages

    def test_direct_round_trip_carries_provenance(self):
        f1, c1 = self.join("fable"), self.join("codex")
        d = self.new(f1, c1)
        head = Path(d).read_text().split("\n---\n")[0]
        self.assertIn("protocol: jbomohi-mail/v1\n", head)
        self.assertIn("model: m2\n", head)
        self.assertIn("client: claude\n", head)
        self.assertNotIn("generation", head)
        self.fill(d)
        pub = self.run_tool("publish", "--actor", f1, d).stdout.strip()
        self.assertTrue(Path(pub).exists() and not Path(d).exists())
        self.assertIn("pending_for_codex_1=1", self.run_tool("status", "--actor", c1).stdout)
        mid = Path(pub).stem
        self.run_tool("ack", "--actor", c1, mid, "--disposition", "done")
        self.assertIn("pending_for_codex_1=0", self.run_tool("status", "--actor", c1).stdout)
        self.run_tool("ack", "--actor", c1, mid, "--disposition", "again", expect=4)
        self.run_tool("ack", "--actor", f1, mid, "--disposition", "not mine", expect=3)

    def test_broadcast_excludes_sender_inactive_model_and_unjoined(self):
        f1, c1 = self.join("fable"), self.join("codex")
        d = self.new(f1, "all")
        self.fill(d)
        pub = self.run_tool("publish", "--actor", f1, d).stdout.strip()
        head = Path(pub).read_text().split("\n---\n")[0]
        self.assertIn("to: codex_1\n", head)
        self.assertIn("audience: all", head)
        self.assertNotIn("fable_1", head.split("to:")[1].split("\n")[0])

    def test_broadcast_with_no_active_sessions_is_refused(self):
        f1 = self.join("fable")
        d = self.new(f1, "all")
        self.fill(d)
        self.run_tool("publish", "--actor", f1, d, expect=1)

    def test_human_is_addressed_but_never_pending(self):
        f1 = self.join("fable")
        d = self.new(f1, "human", slug="ask")
        self.fill(d)
        self.run_tool("publish", "--actor", f1, d)
        out = self.run_tool("status", "--actor", "human").stdout
        self.assertIn("pending_for_human=0", out)
        self.assertIn("ADDRESSED", out)

    def test_fyi_is_not_pending(self):
        f1, c1 = self.join("fable"), self.join("codex")
        d = self.run_tool("new", "--actor", f1, "--to", c1, "--kind", "handoff",
                          "--slug", "fyi", "--no-ack").stdout.strip()
        self.fill(d)
        self.run_tool("publish", "--actor", f1, d)
        self.assertIn("pending_for_codex_1=0", self.run_tool("status", "--actor", c1).stdout)

    def test_foreign_draft_unknown_target_and_bare_id_publish(self):
        f1, c1 = self.join("fable"), self.join("codex")
        d = self.new(f1, c1)
        self.fill(d)
        self.run_tool("publish", "--actor", c1, d, expect=3)
        d2 = self.new(f1, c1, slug="reply", reply_to="20260101T000000Z-fable_1-nothing")
        self.fill(d2)
        self.run_tool("publish", "--actor", f1, d2, expect=5)
        self.run_tool("publish", "--actor", f1, Path(d).stem)  # bare id works

    def test_actor_binding(self):
        f1, c1 = self.join("fable"), self.join("codex")
        env = {"JBOMOHI_EXCHANGE_ACTOR": f1}
        self.run_tool("new", "--actor", c1, "--to", f1, "--kind", "handoff", "--slug", "x", env=env, expect=3)
        d = self.run_tool("new", "--to", c1, "--kind", "handoff", "--slug", "y", env=env).stdout.strip()
        self.assertIn(f"/drafts/{f1}/", d)
        self.run_tool("new", "--to", c1, "--kind", "handoff", "--slug", "z",
                      env={"JBOMOHI_EXCHANGE_ACTOR": "fable"}, expect=3)

    def test_tmp_files_are_invisible_and_ids_never_collide(self):
        f1, c1 = self.join("fable"), self.join("codex")
        (self.spool / "messages").mkdir(exist_ok=True)
        (self.spool / "messages" / "garbage.md.123.tmp").write_text("junk")
        self.run_tool("validate")
        a = self.new(f1, c1, slug="same")
        b = self.new(f1, c1, slug="same")
        self.assertNotEqual(a, b)

    def test_message_cannot_name_bare_model(self):
        f1 = self.join("fable")
        self.run_tool("new", "--actor", f1, "--to", "codex", "--kind", "handoff", "--slug", "x", expect=3)

    def test_markdown_links_resolve_relative_to_their_file(self):
        link = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
        for md in [HERE.parent / "PROTOCOL.md", HERE.parent / "LAUNCH.md", HERE.parent / "WEB.md"]:
            for target in link.findall(md.read_text()):
                t = target.split("#", 1)[0]
                if not t or "://" in t:
                    continue
                self.assertTrue((md.parent / t).resolve().exists(), f"{md.name}: {target}")


if __name__ == "__main__":
    unittest.main()
