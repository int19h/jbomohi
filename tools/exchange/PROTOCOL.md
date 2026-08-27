# Multi-model message exchange protocol

Protocol version: **`jbomohi-mail/v1`**.

The exchange is a transient peer channel shared through the local filesystem
by every model session working on this repository and by the human partner. It
replaces copy/paste between sessions. The message spool under `.exchange/` is
ignored by Git; this directory holds the tracked control plane: this protocol,
the participant registry ([`participants.toml`](participants.toml)), the helper
([`exchange.py`](exchange.py)), its templates
([message](MESSAGE_TEMPLATE.md), [acknowledgement](ACK_TEMPLATE.md)), the
launch guide ([`LAUNCH.md`](LAUNCH.md)), and its [tests](tests/). File paths in
this document are written relative to the repository root, and all commands are
run from there. Roles in this project: the human partner adjudicates, Fable
directs and reviews, and Codex implements. GitHub issues remain the durable
work queue, and the normative documents plus the human partner's adjudications
remain the authority.

## Models and sessions

[`participants.toml`](participants.toml) is the single **model** allow-list.
Every model has a lowercase slug (`codex`, `fable`), a display name, its
transporting client, its default model selector, an `active` flag, and a
`broadcast_recipient` flag. Model identity is distinct from client and
selector: two models transported by the same client are still separate models.
Adding a model is an edit to the registry, never a code change.

**Actors are sessions.** A session registers itself once, at its first turn,
with `exchange.py join --model <slug>`, and is named `<slug>_<n>`: the first
Fable session is `fable_1`, the next `fable_2`, and the first Codex session
`codex_1`. Ids are assigned by the helper from the spool's session registry
(`.exchange/sessions/<id>.md`), never chosen by hand, so a session needs no
launch prompt to know who it is. A session that has finished its work runs
`exchange.py retire`: it leaves every future `all` audience but stays
addressable, so the human partner can resume it later for a direct question (a
later session asking an earlier one why something is the way it is). Sessions
coexist; nothing retires a session except itself or the human partner.

The human partner is the fixed actor `human` (registry `sessions = false`):
may address any session and be addressed directly (a `decision-query`, say),
adjudicates disagreements, is never a broadcast recipient, and never owes an
acknowledgement — the registry marks it `acknowledges = false`, so messages
addressed to `human` are reported by `status --actor human` as `ADDRESSED`,
never as pending. Each session is one accountable model session; hidden
subagents, teams, or swarms are not used unless the human partner expressly
authorizes them, and any authorized use is disclosed in the message.

## Bootstrapping a session

A new session needs no launch prompt. At its first turn it:

1. reads the charter (`AGENTS.md`), which its client loads;
2. identifies its model slug by self-inspection (a Claude session is `fable`,
   an OpenAI Codex session `codex`);
3. runs `python3 tools/exchange/exchange.py join --model <slug>` and uses the
   printed id as its `--actor` from then on (a tab may also export it as
   `JBOMOHI_EXCHANGE_ACTOR`);
4. runs `status --actor <id>`, reads every message addressed **directly** to
   it (and its reply ancestors) and acts on it; broadcasts are context;
5. otherwise does what its opening prompt asked, or, given none, continues the
   work queued for its model in the tracker and says so.

## Scheduling: no predetermined order

Sessions do not poll. The human partner wakes a session, and that session
processes whatever is pending for its actor. **The protocol imposes no turn
order** — not round-robin, not hub-and-spoke, not "everyone answers before
anyone replies." A message is addressed to the audience the sender actually
needs; the human partner decides who is woken next, and may hand a question
first to whichever actor seems best placed to answer it so that the discussion
starts from the strongest premise. Nothing in the pending sets or
acknowledgements encodes or requires a sequence.

## Layout

Paths relative to the repository root:

```text
tools/exchange/                   tracked control plane
  PROTOCOL.md  participants.toml  exchange.py  web.py  MESSAGE_TEMPLATE.md
  ACK_TEMPLATE.md  LAUNCH.md  WEB.md  web/  tests/

.exchange/                        ignored spool
  sessions/<session-id>.md        the session registry (join/retire)
  messages/                       every published message, stored once
  drafts/<session-id>/            unpublished messages of that session
  acks/<session-id>/              acknowledgements authored by that session
```

Each actor writes only its own draft and acknowledgement directories and
publishes only its own messages. No actor edits or moves another actor's files,
and published files are never edited.

**Actor binding (optional).** A session may export
`JBOMOHI_EXCHANGE_ACTOR=<session-id>` after joining. When it is set,
`new`/`publish`/`ack`/`retire` refuse any other `--actor` (exit 3) and default
to the bound actor when `--actor` is omitted. This is an accidental-safety
boundary for two sessions sharing one client, not security against the shared
account; leaving it unset is the human driver's manual escape.

**Drafts are private.** Only the sender's own `status` reports problems in its
drafts, as `WARNING` lines; other actors' drafts may be half-written at any
moment and never block validation, publication, or acknowledgement.

## Messages

Filename and `id` are identical except for `.md`:
`YYYYMMDDTHHMMSSZ-<session-id>-<short-slug>.md` (UTC; slug lowercase ASCII).
The header is simple `key: value` front matter, not general YAML:

```text
---
protocol: jbomohi-mail/v1
id: 20260826T120000Z-fable_1-example
from: fable_1
to: codex_1,codex_2
audience: all
created_utc: 2026-08-26T12:00:00Z
kind: finding
model: claude-fable-5
client: claude/2.1.0
ack_required: true
in_reply_to: none
supersedes: none
github_issues: #24,#25
---
```

- `to` is a comma-separated list of session ids (or `human`). In a **draft** it
  may be `all`; at publication the helper expands `all` to the **active**
  sessions of every broadcast model other than the sender and records
  `audience: all`. A published message therefore always names its recipients
  explicitly, so a later registry change never alters whom an already published
  message is pending for.
- A sender is never its own recipient. Direct and subset addressing are the
  same mechanism as broadcast; choose the audience the message needs.
- `ack_required: true` makes every recipient pending until its own
  acknowledgement exists; `false` publishes an immutable FYI that is never
  pending.
- `model` and `client` are required provenance on every message; the helper
  fills them from the session registry unless overridden.
- `kind` ∈ `request`, `response`, `finding`, `proposal`, `handoff`,
  `decision-query`. `in_reply_to` and `supersedes` each name one published
  message or `none`; branching discussion is normal and no linear thread is
  imposed. `github_issues` is `none` or a comma-separated list of `#numbers`.
- Body contract: **Context** (live files/sections, commit or dirty-tree
  boundary, issues), **Claims or findings** (separated from settled
  human-partner decisions), **Evidence** (exact lines, terms, countermodels,
  source excerpts, commands), **Questions or objections** (bounded), and
  **Requested disposition** (a gate, not "review this"). Keep quotation
  minimal; cite prior message IDs. Never place secrets in the spool.

## Publication and immutability

Compose with `exchange.py new`, edit the draft, then `exchange.py publish`.
The helper validates the draft and the published spool, materializes the
audience, writes and fsyncs a temporary file, validates that final content
under its final name, and only then links it into `messages/` atomically; a
lost race on the same id fails with a collision code rather than overwriting,
and nothing invalid ever crosses the boundary. A body that is empty or still
the template is refused. `new` reserves the final draft name exclusively with
an empty file (retrying on a same-second collision) and then fills it by
renaming a per-process temporary file over it; the momentarily empty draft is
harmless because drafts are private and never spool errors. Acknowledgements
and published messages are written through per-process temporary files and
linked exclusively, so no final name in `acks/` or `messages/` is ever
observable in a partial state. Appearance in `messages/` is the observable
publication boundary. A correction is a new message with `supersedes`; a reply
is a new message with `in_reply_to`. Files ending in `.tmp` are invisible to
validation.

## Acknowledgements

`exchange.py ack --actor <a> <id> --disposition '…'` writes a temporary file
and links it exclusively as `acks/<a>/<id>.ack.md`. Only a recipient may
acknowledge, once. Acknowledgement means **read and disposition captured** — in
a reply, a GitHub issue or comment, or a short explicit explanation — never
"agreed" and never "queued work completed." A message may be acknowledged with
a concise no-objection disposition. Do not acknowledge a request whose required
response or durable issue update was silently skipped.

## Discussion discipline

- No vote, quorum, majority, silence, or acknowledgement count ever becomes
  consensus. Convergence is recorded by naming reviewers and their exact
  positions; a genuine disagreement is adjudicated by the human partner.
- When a docket goes to several reviewers, name them and name **one** durable
  recorder who promotes the outcome to GitHub; others do not race to edit the
  same issue.
- Read what is pending for you, its reply ancestors, and what you are
  explicitly pointed at — not the whole historical spool.
- The spool is coordination, not authority. Actionable work goes to a GitHub
  issue in the same turn; a proposed normative change stays in review until the
  human partner authorizes it.
- Implementation assignments use separate worktrees/branches; a review names
  the exact commit under review.

## Commands

Run from the repository root:

```sh
python3 tools/exchange/exchange.py join --model <slug> [--note '…']   # once, first turn: prints your id
python3 tools/exchange/exchange.py status --actor <actor>   # start and end of a turn
python3 tools/exchange/exchange.py sessions                 # who exists, active or retired
python3 tools/exchange/exchange.py snapshot                 # validated read model as JSON
python3 tools/exchange/exchange.py retire --actor <actor> [--note '…']   # handoff
python3 tools/exchange/exchange.py new --actor <actor> --to all|a,b --kind <kind> \
    --slug <slug> [--issues '#1,#2'] [--reply-to <id>] [--supersedes <id>] [--no-ack]
python3 tools/exchange/exchange.py publish --actor <actor> <draft-path|draft-id>
python3 tools/exchange/exchange.py ack --actor <actor> <id> --disposition '…'
python3 tools/exchange/exchange.py validate
python3 -m unittest discover -s tools/exchange/tests
JBOMOHI_EXCHANGE_ACTOR=<actor> python3 -m unittest discover -s tools/exchange/tests
python3 tools/exchange/web.py --open                        # local read-only thread client
```

The web client's behavior and safety boundary are documented in
[`WEB.md`](WEB.md).

Run the suite both unbound and bound (the second form, as a launched tab would
run it); both must pass.

Exit codes: 0 ok · 1 usage · 2 validation · 3 ownership/permission ·
4 collision/duplicate · 5 unknown reference.
