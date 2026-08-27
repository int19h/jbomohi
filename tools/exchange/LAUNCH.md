# Launching a session

Sessions bootstrap themselves from the charter; there is no launch prompt to
paste. Start the client in the repository root and give the session whatever
task you have — or nothing. See [`PROTOCOL.md`](PROTOCOL.md) for the session
model (`<slug>_<n>`) and the message contract.

## What a fresh session does on its own

1. Reads the charter (`AGENTS.md`); the client loads it.
2. Identifies its model slug — a Claude session is `fable`, an OpenAI Codex
   session `codex` — and runs
   `python3 tools/exchange/exchange.py join --model <slug>`; the printed id
   (`fable_1`, `codex_1`, …) is its actor from then on.
3. Runs `status --actor <id>`, reads what is addressed directly to it, and acts
   on that; otherwise acts on your opening prompt; otherwise continues the
   work queued for its model in the tracker.

## Per client

- **Terminal tabs (Claude Code, Codex):** one tab per session; after joining,
  a tab may `export JBOMOHI_EXCHANGE_ACTOR=<id>` so the helper refuses any
  other actor. Resume a tab with the client's own resume/continue command.
- **Clients that do not keep an exported variable between commands:** spell the
  actor on every helper call:
  `JBOMOHI_EXCHANGE_ACTOR=<id> python3 tools/exchange/exchange.py … --actor <id>`.

## Several sessions of one model

`join` hands out `fable_1`, then `fable_2`, `fable_3`, … Use extra sessions for
work that benefits from a clean context; they are peers, not subagents, and
each is accountable for its own messages.

## Handing off and retiring

A session that is done runs `exchange.py retire --actor <id> --note '…'`
after leaving an addressed handoff. Retired sessions drop out of `all` but
stay addressable: resume the client session and it can answer a direct
message from a later session.
