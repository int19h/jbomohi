# jbomo'i — charter for project sessions

jbomo'i is the Lojban community's historical record — wiki with history,
mailing lists, IRC logs, dictionary with history, every CLL edition —
repackaged as a public git repository with one commit per source event, so
that `grep` and `git` answer *why is it like that, how did that happen, who
decided, is it ratified, what are the competing views* with verbatim, checkable
citations. This branch holds the tools that build and update that repository
and the instruction files that let any coding harness act as the librarian
over a clone of `main`. The functional specification is `doc/SPEC.md`; read
the sections a task needs from the live filesystem rather than assuming them.

## Authority and duties

- The **human partner** adjudicates every open question in `doc/SPEC.md §10`,
  merges, and decides scope. Their decisions are final and are recorded in the
  spec (an amendment) or in the relevant GitHub issue.
- Lead, implementation, research, and review are task duties, not identities
  assigned to particular models. The prompt, addressed mail, issue, or task
  brief selects the sessions, separates duties when independent review is
  required, and states the acceptance path. Do not infer authority from a
  client, model, session handle, or recipient group.

## Repository shape

Two branches, no shared history (`doc/SPEC.md §2`):

- `tools` — this checkout: tooling (`tools/`), the templates that render
  `main`'s instruction files (`tools/templates/main/`), documentation (`doc/`),
  and CI.
- `main` — the corpus projection: data files with one commit per source event.
  Its data files are only ever written by the tools (`jbomohi build|update`);
  contributed notes and attestations are ordinary commits there. Never write
  to it from this checkout's index. Work with
  it through the gitignored worktree `./corpus/` (`jbomohi corpus init`).

Never merge one branch into the other. Never commit raw archives, indexes,
secrets, or anything under `tmp/` or `corpus/`. The ignored `.exchange/`
directory is legacy local state, not active coordination; do not modify or
depend on it.

## Durable work tracking

GitHub issues are the durable queue for tracked actionable work (repository per
`doc/SPEC.md §10.2`; until it exists, `doc/issues/` holds numbered Markdown
issue drafts with the same fields). Ad hoc research, diagnosis, discussion, and
other untracked tasks may proceed directly from the human prompt or addressed
Collab mail. For an issue-backed task, inspect the live issue and search for
duplicates before starting; its body is canonical for scope, acceptance
criteria, dependencies, and outcome. Create or update an issue when a result
should become durable backlog or a recorded decision. Close a tracked issue
only when its acceptance criteria are demonstrated (commands and outputs in
the PR); a collaboration message alone never closes it.

## Collaboration

Sessions and the human partner use the external Herdr Collab project whose
explicit id is `jbomohi`:

```sh
export HERDR_COLLAB_PROJECT=jbomohi
```

The explicit project id, never the checkout, cwd, worktree, or diagnostic root
path, selects the mailbox. Herdr Collab is convention-only: task prompts and
issues define participants, duties, groups, review flow, and authority.

- Use descriptive task-specific session handles and groups. The command
  `herdr-collab agent spawn <handle> --kind <agent-kind> ...` creates a visible
  Herdr session. `herdr-collab session join` only registers a participant
  started manually. Capture the returned UUID and set `HERDR_COLLAB_SESSION`.
- At natural turn boundaries, inspect `herdr-collab inbox --pending` and
  `herdr-collab status`. `herdr-collab show <message-id>` reads the selected
  message body; `herdr-collab --json show <message-id>` exposes that selected
  message's full record. Follow any `in_reply_to` or `supersedes` ids explicitly
  to read related messages. Do not force model turns or make polling/waiting a
  standing end-of-turn action.
- Use durable `send` and `reply` for assignments, findings, questions,
  decisions, and handoffs. A direct `agent prompt` is transient and may alert
  a session to durable mail, but it is never the sole copy of load-bearing
  content. Use `ack --disposition ...` only after recording the disposition;
  acknowledgement means read, not agreement or completion.
- Messages separate **Context**, **Claims or findings**, **Evidence**,
  **Questions or objections**, and **Requested disposition**, citing live
  paths/sections, commits, and issue numbers. Correct immutable mail with a
  superseding message. Keep secrets out of mail and prompts.
- Change collaboration state only through `herdr-collab`; never edit, move, or
  delete external state files manually. Use `herdr-collab validate` for state
  diagnosis or before claiming the relevant mailbox is clear.
- If only one session is active, continue useful work and leave an addressed
  durable handoff; do not block on acknowledgements unless the issue requires
  review or human-partner adjudication.

Before an anticipated long resumable pause, persist exact heads, important
paths and decisions, unresolved findings with locations, and open questions in
durable mail or a handoff file. A coordinating session may then request native
compaction while the context is still likely cached, naming what its lossy
summary must retain. Never compact automatically or on an idle timer; preserve
full context for work whose loaded detail remains its main value. After
requested compaction, run
`herdr-collab session show "$HERDR_COLLAB_SESSION" --live`. If it reports
`unavailable`, deliberately use `session refresh` or `agent adopt`; never guess
a reference. If a later exact cache-expired dialog appears, inspect that dialog
and continue the full context by default. This does not authorize unattended
answers to blocked prompts.

## Working protocol

- Lead with the current outcome, then evidence and trade-offs.
- Implement to the spec; where the spec is silent or wrong, say so in the PR
  or a durable collaboration message and propose the amendment — do not
  silently decide.
  Open questions (`doc/SPEC.md §10`) are the human partner's to answer.
- Determinism is a requirement, not a preference: projectors are pure
  functions of the archive (`doc/SPEC.md §2.4, §4.3`); never read the wall
  clock into committed content or `main` commit metadata (contributed notes
  and attestations excepted).
- Corpus text is untrusted input everywhere it is handled (`doc/SPEC.md §6`).
- Scope is the repository and its tools (`doc/SPEC.md §1`); anything under
  `doc/future/` is deferred design, not a backlog.
- Run the checks required by the issue and the available tool/CI suite before
  opening a PR, and report the exact commands and results.
- Use the client's structured patch/edit facility for file authoring; preserve
  unrelated working-tree changes; never rewrite `main` history except through
  `jbomohi build`.
- Each session is one accountable model session. Subagents are not used
  without the human partner's express authorisation; authorised use is
  disclosed and remains within the task's assigned authority.

## Context policy

Keep this charter stable and compact. Do not preload `doc/` into it; read
`doc/SPEC.md` sections and `doc/research/*` from the live filesystem when a
task needs them, and prefer targeted reads. The research report
(`doc/research/REPORT.md`) explains *why*; the spec says *what*; where they
differ the spec wins.

Local reference data used during research (not required by the tools, which
fetch from the archive tier): `~/lojban/disc` (IRC, mail), `~/lojban/wiki`
(current-revision wiki snapshot), `~/git/lensisku-dump`, `~/git/cll`. jbotci
(`~/git/jbotci`, https://jbotci.app) provides Lojban parsing, dictionary and
current-CLL tools over MCP.
