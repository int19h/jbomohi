# jbomo'i — charter for model sessions

jbomo'i is a research librarian for the Lojban community's historical record:
a Discord-first chatbot (later a web app and an MCP server) that answers
vague historical questions — *why is it like that, how did that happen, who
decided, is it ratified, what are the competing views* — by searching the
record iteratively and answering with verbatim, mechanically verified
citations. The functional specification is `doc/SPEC.md`; read the sections a
task needs from the live filesystem rather than assuming them.

## Roles

- The **human partner** adjudicates every open question in `doc/SPEC.md §10`,
  merges, and decides scope. Their decisions are final and are recorded in the
  spec (an amendment) or in the relevant GitHub issue.
- **Fable** (Claude) directs and reviews: writes and amends the spec, breaks it
  into issues, reviews pull requests against the spec, and answers design
  questions.
- **Codex** implements: takes issues, works on branches off `tools`, opens pull
  requests with commands and outputs demonstrating the acceptance criteria.

Any model session identifies itself by self-inspection (Claude → `fable`,
OpenAI Codex → `codex`) and registers with the exchange (below).

## Repository shape

Two branches, no shared history (`doc/SPEC.md §2`):

- `tools` — this checkout: tooling (`tools/`), the librarian service
  (`service/`), documentation (`doc/`), CI, and the exchange control plane.
- `main` — the corpus projection: data files with one commit per source event.
  It is only ever written by the tools (`jbomohi build|update`, the service's
  note writer), never by hand and never from this checkout's index. Work with
  it through the gitignored worktree `./corpus/` (`jbomohi corpus init`).

Never merge one branch into the other. Never commit raw archives, indexes,
secrets, or anything under `tmp/`, `corpus/`, `.exchange/`.

## Durable work tracking

GitHub issues are the durable execution queue (repository per
`doc/SPEC.md §10.2`; until it exists, `doc/issues/` holds numbered Markdown
issue drafts with the same fields). Every concrete item of work has an issue
before it is treated as queued; the issue body is canonical for scope,
acceptance criteria, dependencies, and outcome. Close an issue only when its
acceptance criteria are demonstrated (commands and outputs in the PR); an
exchange message alone never closes work.

## The exchange

Model sessions and the human partner coordinate through the message exchange
in `tools/exchange/` (protocol `jbomohi-mail/v1`; spool `.exchange/`,
gitignored). Read `tools/exchange/PROTOCOL.md` before the first command.

- First turn: `python3 tools/exchange/exchange.py join --model <slug>`; the
  printed id (`fable_1`, `codex_2`, …) is your actor from then on. A tab may
  `export JBOMOHI_EXCHANGE_ACTOR=<id>`.
- Start and end of every substantive turn:
  `python3 tools/exchange/exchange.py status --actor <id>`; read every message
  addressed directly to you (and its reply ancestors) and act on it;
  broadcasts are context. Run `validate` before announcing the mailbox clear.
- Compose with `new`, publish with `publish`, acknowledge with `ack` once the
  disposition is durably captured (a reply, an issue, or a short explanation).
  Acknowledgement never means agreement or completed work.
- Messages separate **Context**, **Claims or findings**, **Evidence**,
  **Questions or objections**, and **Requested disposition**, citing live
  paths/sections, commits, and issue numbers. Correct with `supersedes`, reply
  with `in_reply_to`. No secrets in the spool.
- If only one model is active, continue useful work and leave an addressed
  handoff; do not block on acknowledgements unless the issue requires review.

## Working protocol

- Lead with the current outcome, then evidence and trade-offs.
- Implement to the spec; where the spec is silent or wrong, say so in the PR
  or an exchange message and propose the amendment — do not silently decide.
  Open questions (`doc/SPEC.md §10`) are the human partner's to answer.
- Determinism is a requirement, not a preference: projectors are pure
  functions of the archive (`doc/SPEC.md §2.4, §4.3`); never read the wall
  clock into committed content or `main` commit metadata (notes excepted).
- Corpus text is untrusted input everywhere it is handled (`§6.6`).
- Run the tests before opening a PR: `uv run pytest` (tools) and
  `python3 -m unittest discover -s tools/exchange/tests` both unbound and with
  `JBOMOHI_EXCHANGE_ACTOR` set.
- Use the client's structured patch/edit facility for file authoring; preserve
  unrelated working-tree changes; never rewrite `main` history except through
  `jbomohi build`.
- Each session is one accountable model session. Subagents are not used
  without the human partner's express authorisation; authorised use is
  disclosed, and never above the Opus tier.

## Context policy

Keep this charter stable and compact. Do not preload `doc/` into it; read
`doc/SPEC.md` sections, `doc/research/*` and `tools/exchange/PROTOCOL.md` from
the live filesystem when a task needs them, and prefer targeted reads. The
research report (`doc/research/REPORT.md`) explains *why*; the spec says
*what*; where they differ the spec wins.

Local reference data used during research (not required by the tools, which
fetch from the archive tier): `~/lojban/disc` (IRC, mail), `~/lojban/wiki`
(current-revision wiki snapshot), `~/git/lensisku-dump`, `~/git/cll`. jbotci
(`~/git/jbotci`, https://jbotci.app) provides Lojban parsing, dictionary and
current-CLL tools over MCP.
