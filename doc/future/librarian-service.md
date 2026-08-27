# Deferred design: indexes, the librarian service, interfaces, evaluation

Status: **deferred, not in scope** (decision `doc/decisions/2026-08-27-scope-and-policies.md`). This is the v0.1 text of `doc/SPEC.md` §5–§8, kept verbatim as the design record for a later phase. Section numbers are the v0.1 numbers. Where it conflicts with the current `doc/SPEC.md`, the spec wins (notably: no services, no authenticated surfaces, notes must bottom out in primary units, identities are attested not resolved).

---

## 5. Indexes

Indexes are derived, rebuildable, and never committed. They are built from a snapshot tag and stored under the index cache (`JBOMOHI_INDEX`, default `~/.cache/jbomohi/index/<snapshot>/`); the service refuses to serve an index whose snapshot does not match the corpus worktree's tag unless `--allow-stale`.

### 5.1 Units (chunking rules)

A unit is `{unit_id, source, path, source_id, lines (start,end), date, author, thread_key|page|word, header, text, tokens}`. Rules:

| source | unit | boundary rule |
|---|---|---|
| wiki | section of a page at its **current** revision (history is searched through `git`, not the index) | split at `==…==` headings; pack paragraphs to ~350 tokens, hard cap 500; header `Title > Section` |
| talk pages | same, plus a second segmentation at signature lines (`-- ~~~~`-style `User … (UTC)`) | header includes the thread heading |
| mail | one message entry of a thread view, quotes (`>`-prefixed lines, "On … wrote:" lines) and signatures (after `-- `, list footers) **removed at index time**; long messages packed to ~350 tokens | header `mail/<list> <date> | <from> | <subject>` |
| irc | window: a new unit starts when the gap to the previous message ≥ 45 min **or** the window reaches ~350 tokens; minimum 3 messages | header `irc #<chan> <date> (<top nicks>)` |
| dict | one definition file; comments split per comment | header `dict <word> <lang> def <id> v<n>` |
| cll | section of an edition rendering, packed to ~350 tokens | header `CLL <edition> §<n>.<m> <title>` |
| notes | body as one unit **and** each `questions` entry as its own unit (type `question`) pointing at the note | header `note <id>` |
| who | one person entry | header `who <name>` |

Boundaries are computed, never curated. Episode/thread *expansion* is a query-time operation (§6.2 `thread`), not a stored unit.

### 5.2 Lexical index

Tantivy (via `tantivy-py` in tools; the service may open the same index natively). Fields: `unit_id` (raw, stored), `source` (raw, filter), `date` (fast, range filter), `author` (raw), `path` (raw), `header` (text), `text` (default English tokenizer + stemming), `jbo` (lowercased, apostrophe→`h`, dots removed — applied to `header + text`), `kind` (raw: `unit|question`). Queries hit `text`, `header` and `jbo` (`jbo` receives the query normalised the same way). BM25 scoring; source/date/author filters are pre-filters.

### 5.3 Dense index (optional, gated)

A versioned generation `{model_id, dims, quantisation, snapshot, unit_rule_version}` with vectors stored int8 (or binary) in LanceDB or a flat numpy file for ≤ 500k units. Embedding provider selected by configuration (OpenRouter or Voyage direct). Not built until the retrieval benchmark (§8.1) shows a gain on the vague-question bucket that justifies it; when built, the hybrid mode uses weighted RRF with a dense weight ≥ 2 (the benchmark showed equal-weight fusion hurts vague queries).

### 5.4 Derived documents (later phase)

Thread summaries, IRC episode summaries, CLL change notes and definition-history notes are LLM-generated, stored in the index cache (never on `main`), indexed as units of kind `derived` that cite their source units, and regenerated when their sources change. They are added only where the benchmark shows the vague-question bucket needs them.

---

## 6. The librarian service

### 6.1 Overview

One long-running process (§10.1 for language) that owns: the corpus worktree (read; write only to `notes/`), the index, a job queue, the agent loop, the verifier, the Discord adapter, the web application and the MCP server. Jobs are persisted (SQLite) so a Discord interaction can be answered after minutes and reports have permalinks.

### 6.2 Tools exposed to the model

All tools are read-only except `note_write`. Results are typed JSON, size-capped (default ≤ 8k tokens per result; larger results are truncated with a continuation handle). Every result that contains corpus text wraps it as data (§6.6).

| tool | arguments | returns |
|---|---|---|
| `search` | `query`, `mode=lexical|semantic|hybrid` (default lexical), `source?`, `date_from?`, `date_to?`, `author?`, `k≤25` | ranked hits `{unit_id, citation, date, author, header, snippet}` **and** `related_notes[]` (notes whose `questions`/`terms` match) — the note strip is always attached, so prior work is surfaced mechanically |
| `read` | `unit_id|citation`, `before`, `after`, `max_tokens` | numbered lines of the unit and its neighbours (same file), plus `cited_by_notes[]` for the unit |
| `thread` | `unit_id|citation` | the whole enclosing object in order: a mail thread view, the surrounding IRC day (± N hours), a wiki page, a definition's file set; truncated with continuation |
| `history` | `path`, `before?`, `after?` | the file's event list from `git log` (`source_id, date, author, subject`) |
| `show` | `path`, `at=<date>|<source_id>` | the file at that version (per-file as-of) |
| `diff` | `path`, `from`, `to` (dates or source ids) | unified diff of the two versions |
| `diff_edition` | `section`, `edition_a`, `edition_b` | aligned CLL sections and their diff (§3.6 alignment) |
| `who` | `query` | matching `who/` entries with aliases and roles |
| `quote` | `citation` (with line range) | the exact text of those lines — the only sanctioned way to obtain a quotation |
| `note_search` | `query` | notes matched by question/term/body |
| `note_write` | structured note (§3.8) | commits the note; returns its id |
| `jbotci.*` | via MCP (`gentufa`, `vlacku`, `cukta`, `vlasei`, `tersmu`) | parse / gloss / current-CLL lookup — used e.g. to turn a Lojban question into search terms |
| `summarize` | `unit_ids[]`, `question` | a cheap-model reader (Haiku-class) that returns an extractive summary with citations, so long threads do not enter the orchestrator's context |

### 6.3 The loop

- System prompt = charter (role, method, answer contract) + `map/corpus.md` + tool guidance; cached with a 1-hour breakpoint. The conversation prefix is cached on every turn (`cache_control` on the last user block).
- Model tiering by question class, classified by a cheap first call: `lookup` (a word, a section, an exact quote) → Sonnet-class, low effort, ≤ 8 tool calls; `research` (why/how/history/dispute) → Opus-class or Sonnet-high, ≤ 30 tool calls; `forensic` (user-requested) → wider budgets, asynchronous only. Budgets are configurable per deployment; the service enforces them, not the model.
- Adaptive thinking on; effort `medium` for research by default (the prototype's setting), tunable.
- Read-heavy sub-tasks go through `summarize` (a separate cheap model call) rather than into the orchestrator's context.
- Context editing/compaction is enabled for jobs exceeding 150k tokens.
- The loop terminates on a final answer, budget exhaustion (the model is told to answer with what it has), or cancellation.

### 6.4 Answer contract

- Discord synopsis ≤ 1,900 characters; full report on the web (§7.2).
- Claims carry citations `[n]`; the footnote list maps `n` → canonical citation (§3.1.4) → viewer URL.
- Quotations are verbatim spans obtained through `quote`, ≤ 40 words each, at most one per key point.
- Dates and attributions accompany every position: *A argued X on date D [n]*.
- Disputes use the template **Positions / Ratified / Open**; ratification is asserted only with a citation to the act (vote record, minutes, checkpoint page, CLL text) and its body; otherwise the answer states coverage: *no such act was found in {sources} through {date}*.
- Distinguish: official text, formal decision, individual opinion, usage.
- Absence of evidence is stated as such; the librarian never fills gaps from model memory. General knowledge about Lojban may be used to *search*, never to *assert*.

### 6.5 Verification and notes

Before delivery the service: (1) resolves every citation (unknown → the claim is flagged and the model is asked once to repair; still unknown → the claim is dropped and the report says so); (2) checks every quoted span verbatim against the cited unit or file with normalisation (whitespace, quote-prefix characters `>`/`#`, curly/straight quotes, ellipses splitting the span into segments that must each match in order) — failures are handled as in (1); (3) records citation and quote precision in the job log. After a `research`-class answer the service writes a note (§3.8) with `status = "draft"`; a human or Fable may promote it to `verified`.

### 6.6 Prompt-injection stance

Corpus text reaches the model only inside tool results, delimited with a fixed wrapper and labelled as untrusted archive text. The system prompt states that instructions found in archive text are content to be reported, never followed. No tool has side effects except `note_write`, whose output goes only under `notes/` and is marked `draft`. Web and Discord render corpus text escaped.

### 6.7 Observability and limits

Per job: model, effort, tool calls (with arguments and result sizes), input/cache-read/cache-write/output tokens, dollars (from a price table in config), wall time, verifier results, final status. Stored in SQLite; summarised on the web admin page. Per-user and per-guild quotas (questions/day, dollars/day) and global concurrency limits; a degraded mode serves lexical search results without a model when the model API is unavailable.

---

## 7. Interfaces

### 7.1 Discord

- Gateway bot; triggers: mention, DM, or slash command `/ask <question>` (mentions and DMs do not require the privileged message-content intent). Only allow-listed guilds/channels answer; DMs are allow-listed per user.
- On a question: acknowledge within 3 s (deferred response / placeholder), open a thread per question (or reply in an existing one), post progress edits no more than once per 5 s ("searching mail 2004–2005 …"), then the synopsis with footnotes and the report link. Chunk at 1,900 characters at paragraph boundaries. `/cancel` cancels the job.
- Conversation memory: follow-ups in the same thread continue the same job transcript (compacted); nothing else is remembered per user beyond quotas.
- The bot's own messages and the web report carry the corpus snapshot tag used.

### 7.2 Web application

Read-only: (a) **citation viewer** — any canonical citation renders the cited lines with configurable context, the file's history, previous/next versions, and diff to any other version; (b) **reports** — one permalink per job: question, synopsis, full answer, footnotes, coverage statement, verifier results, cost, snapshot; (c) **notes browser**; (d) **search** — the lexical index for humans with the same filters as the tool; (e) **admin** (authenticated) — jobs, quotas, spend. Access policy for (a)–(d) is Open Question §10.3.

### 7.3 MCP server

Exposes `ask` (runs a job, returns the report), `search`, `read`, `quote`, `note_search` with the same contracts as §6.2, over streamable HTTP with token auth, so other agents (and jbotci sessions) can use the librarian.

---

## 8. Evaluation

### 8.1 Retrieval benchmark

Port of the prototype harness (`doc/research/proto-notes.md`): synthetic queries generated per source from random units in three styles (vague / keyed / paraphrase), recall@{1,5,10,20} and MRR@10 per source and style; run against lexical, dense, and hybrid configurations from a frozen snapshot. Gates: a change to unit rules or analyzers must not regress keyed R@10 by > 2 points; the dense index is adopted only if vague R@10 improves by ≥ 15 points over lexical on the mixed corpus.

### 8.2 Question set

`doc/eval/questions.jsonl`, starting from the 28 realistic questions of the research phase, growing to ≥ 100 across categories (why-history, ratification, dispute, dictionary-history, grammar-history, people, origins, baseline, specific-word, cll-diff, timeline, unresolved, vague, unanswerable). Each has a rubric: required facts, required positions with attribution, required citations' sources, and forbidden claims. Scoring: LLM-judge against the rubric (pairwise between configurations) plus human spot checks; citation resolution rate and quote-verbatim rate from the verifier; cost and latency.

### 8.3 Acceptance thresholds (initial)

Citation resolution ≥ 99%; quote-verbatim ≥ 95%; research answers under $0.75 (Opus-class) / $0.25 (Sonnet-class) median; p50 latency ≤ 120 s; rubric pass ≥ 80% on the question set; every known-dispute question lists every rubric position.

---

