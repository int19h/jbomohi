# jbomo'i — architecture research report

*2026-08-26. Scope: what the standard arrangement for an LLM "librarian" over a private historical corpus looks like in mid-2026, and how jbomo'i should differ from a generic "throw docs at it" system given the specific shape of the Lojban record. Detailed evidence lives in `doc/research/` (four literature/data reports) and the prototype (`tmp/fable/proto/`, session scratch — see `doc/research/proto-notes.md`); this document is the synthesis.*

---

## 1. TL;DR

1. **The 2026 standard is an agent that searches iteratively, not a pipeline that retrieves once.** "Embed everything → top-k → stuff → answer" is now the baseline people benchmark *against*. The working shape is: a capable model, a small set of high-resolution retrieval tools (exact/lexical search with filters, "read this span + neighbours", optional semantic search), a tool budget, and a verification pass on citations.
2. **Lexical search is the primary primitive; embeddings are the second tool.** This is doubly true for Lojban: cmavo, gismu, nicknames and proposal names are exact tokens, and BM25 already gets 88% R@10 on term-keyed queries. Embeddings earn their keep only on vague natural-language questions (where BM25 collapses to 24% and the best embedder reaches 66%). The prototype librarian answered every hard question correctly with **BM25 only**, because the agent compensates by iterating.
3. **The design win is in the units and metadata, not the vector store.** Each source type has a natural retrieval unit (wiki section @ revision, mail message in thread, IRC episode, CLL section @ edition, definition @ version) and a natural citation id. Generic products cannot model *time, version, thread, author identity, or ratification status* — and those are exactly what "why is it like that / who ratified it" questions need. That is where a corpus-shaped design beats generic RAG on both quality and token cost.
4. **Cost is dominated by the agent loop, not by indexing.** Indexing the whole ~57M-token cleaned corpus with a top cloud embedder is a one-off ~$7 (free tier on Voyage direct). A deep answer costs **$0.5 (Opus 5, cached) / $0.17 (Sonnet 5, cached)** and ~80 s with 15–25 tool calls; without prompt caching it is 2–3× more. Caching the conversation prefix is the single biggest cost lever, ahead of any retrieval trick.
5. **"History" is mostly acquirable.** The local snapshots are current-state only (wiki, dictionary), but mw.lojban.org allows full-history export, the old Tiki wiki is still live with page histories, Lensisku has a per-definition version/diff API and a public changes feed, and lojban/cll git has line-level history since 2008 (though CLL 1.0 exists only as a diff ancestor, not as text). 22 public list archives are on mail.lojban.org (MHonArc); locally we only have the main list.
6. **Do not build a knowledge graph.** GraphRAG-style indexing is expensive (~$5–10/MB), noisy on entities, and judged superseded for this class of question by cheaper "multi-representation" indexes (raw chunks + thread/episode summaries + change notes) with time metadata everywhere. A *curated* timeline + entity/alias registry + ratification-status table is the graph-shaped part worth having, and it is small enough to be human-maintained with LLM-proposed candidates.
7. **Quote/citation verification must be mechanical.** The literature reports 39–77% citation accuracy for deep-research agents; our prototype did better (0 bad ids out of ~90 citations, 27 of 28 quotes verbatim) but the one miss was a gloss dressed as a quote. A `quote` tool that returns exact spans, plus a fuzzy verbatim check before sending, closes this.
8. **Harness: Rust-first hand-rolled Messages loop + serenity/poise Discord bot + SQLite/LanceDB + `rmcp` to jbotci on a small VPS** is the sane default for you; the Python Claude Agent SDK is worth a weekend as a quality yardstick because its grep/read/subagent loop *is* a librarian. Cloudflare only fits a slash-command-only bot (gateway connection + multi-minute jobs don't fit Workers).

---

## 2. What "standard" means in mid-2026 (and what's dead)

**Consensus** (sources and dates in `research/retrieval-sota.md`):

- *Agentic retrieval.* Anthropic's "just-in-time context" guidance (Sep 2025), A-RAG (Feb 2026), Direct Corpus Interaction (May 2026): give the model exact search + read tools and let it iterate. Amazon (AAAI 2026) got >90% of RAG quality with keyword tools and no vector store; DCI beat embedding retrieval by 11–30 points on agentic benchmarks. But Cursor (Nov 2025) and LlamaIndex (Jan 2026) both measured real gains from *adding* semantic search on top of grep as corpora grow. Net: **hybrid, lexical-first**.
- *Deployed retrieval stack.* BM25 + dense fused by RRF, then a cross-encoder reranker; contextual chunk headers (title/section/thread/date prepended before embedding and indexing) are cheap and reliably help (we measured +4 points R@10 for BM25 from the header alone).
- *Indexing units.* Paragraph/section-sized chunks with metadata; per-thread / per-episode / per-history summaries as *additional* documents ("multi-representation indexing"); VersionRAG-style change notes for versioned documents (90% on "what changed" questions vs 64% for GraphRAG, at 3% of the indexing tokens).
- *Long context as retrieval substitute.* With 1M-token models and 0.1× cache reads, stable references up to ~200k tokens are cheaper to keep in a cached prefix than to chunk; beyond that, retrieve. Long-context degradation ("context rot", NoLiMa) is real, so this is for *reference material the model consults*, not for dumping the corpus.
- *Deep-research loops.* Plan → search → read → verify → cite, with a token/tool budget, subagents on cheaper models for reading-heavy sub-tasks, and a separate citation-verification pass. Two 2026 papers show multi-agent gains largely vanish at equal token budgets — one good loop with cheap read-subagents beats an orchestra.
- *Evaluation.* Corpus-generated synthetic query sets for retrieval recall; hand-written realistic questions with pairwise/LLM judging for answers; citation precision measured mechanically.

**Superseded (2023–24 ideas to ignore):** proposition/atomic-fact indexing (loses to plain paragraphs), chunk overlap, embedding-based "semantic chunking", full Microsoft GraphRAG, "long context kills RAG", Likert LLM-judges, parallel multi-writer agent swarms, and single-shot retrieve-then-answer pipelines.

**Generic products** (Claude Projects/Files knowledge, OpenAI vector stores, Vertex RAG Engine, Cloudflare AI Search, LlamaCloud, Ragie) all do: fixed chunker → embeddings (some hybrid) → top-k → answer. None model versions, threads, time windows, author identity, or "as-of" queries, and none let the agent iterate with filters. They are fine for a FAQ; they cannot answer "what did the BPFK gadri page say before the 2005 checkpoint, and who objected".

---

## 3. What the data actually is

Token counts are cl100k after cleaning (`proto/data/token_counts.json`); full inventory in `research/data-survey.md`.

| Source | Local state | Clean tokens | History? | Natural unit / citation id |
|---|---|---|---|---|
| Wiki (mw.lojban.org) | 14,118 pages, current rev only (2026-06-08); 411 Talk pages; 393 BPFK titles; 66 fetch failures incl. `Talk:BPFK Section: gadri` | 11.7M (main+talk; BPFK ≈2.5M of it, 2.1M is BPFK *talk*) | **Not local**; full-history export allowed via API; pre-2013 Tiki history still live at tiki.lojban.org | section @ revision → `mw oldid=N §heading` |
| IRC #lojban (+#jbosnu prefix) | 1.15M lines 2000–2026, four line formats, 2000-11→2002-05 gap, bridged Discord/Telegram nicks | 23.6M (67.7k episode chunks) | n/a (append-only) | time-gap episode → `#chan date HH:MM nick` (line no.) |
| lojban-list mail | 107k files → **74k unique** messages 1989–2025; 66% contain quoted text | 21M after quote/sig stripping (110M raw) | n/a | message in thread → Message-ID |
| Other lists | none local; 22 public lists on mail.lojban.org (MHonArc), incl. bpfk, jboske, wikidiscuss, lojban-beginners; llg-members/board need auth | — | — | Message-ID |
| Dictionary (Lensisku dump) | 57,687 current definitions / 30,650 words, with votes, examples, rafsi | ~14M as ndjson; ~4M as compact text | **Not local**; Lensisku has `/api/versions/{def}/history` + diffs and a public changes feed | definition @ version → `lensisku def N v M` |
| CLL | DocBook git fork, 1,899 commits since 2008; 1.1 official builds; 1.2.x (geklojban); 1.3.2 (yours); **no 1.0 text**, only as git ancestor | 364k plain text (922k as XML) per edition | git history = line-level 1.1 errata history | section @ edition → `CLL 1.1 §9.3 (tag)` |
| Discord | nothing exported; bridged traffic appears in IRC under relay nicks | — | — | — |

Total cleaned corpus today ≈ **57M tokens**; with the other lists and wiki history, plausibly 100–150M. This is small: it fits on one disk, in one Tantivy/LanceDB index, and is ~$7 to embed end-to-end once.

**The big gaps are the "history" halves of two sources (wiki revisions, dictionary versions), the other mailing lists, and identity resolution** (the same person is `xorxes`, "Jorge Llambías", a Google-Groups address, a wiki user, a Discord relay nick). None require research — just acquisition scripts.

---

## 4. Why a corpus-shaped design wins here (evidence)

Three prototype experiments (`tmp/fable/proto/`, session scratch — see `doc/research/proto-notes.md`), all reproducible:

**(a) Retrieval benchmark.** 20k wiki chunks (~350 tokens, with `Title > Section` header), 366 synthetic queries generated by Claude from 122 random chunks in three styles — *vague* (Discord-style, no distinctive wording), *keyed* (hinges on specific Lojban words/names), *paraphrase* (keyword search string). Recall@10 of the source chunk:

| system | all | vague | keyed | paraphrase |
|---|---|---|---|---|
| BM25 (text only) | 0.62 | 0.22 | 0.84 | 0.79 |
| BM25 (+context header) | 0.66 | 0.24 | 0.88 | 0.86 |
| best dense (voyage-4-large) | 0.82 | 0.66 | 0.95 | 0.84 |
| naive RRF hybrid | 0.82 | 0.59 | 0.95 | 0.93 |
| other dense models (Gemini-2, Qwen3-8B, OpenAI-3-large, bge-m3) | 0.60–0.69 | 0.30–0.60 | 0.69–0.79 | 0.58–0.77 |

Three architectural lessons, independent of which embedder wins: (1) the *query style* decides the tool — exact-term questions are a lexical problem, vague ones a semantic one — so the agent should have both as separate tools with the prompt telling it when to use which, rather than one fused "search"; (2) embedding models differ by 2× on Lojban-keyed queries (the ones that tokenize Lojban badly fail), so this must be tested per model rather than picked from MTEB, but that is a separate decision; (3) naive equal-weight fusion *hurts* the vague case because BM25 contributes noise — fusion weights or a reranker are needed if you fuse at all. The mixed wiki+IRC+mail run (36k chunks, 771 queries, `proto/data/bench_mixed.json`) confirms the pattern and sharpens it: on chat/mail text BM25 *beats* the best dense model on keyed queries (0.91 vs 0.88 R@10) while dense still triples it on vague ones (0.53 vs 0.19); hybrid is best overall (0.76) but again drags the vague bucket down (0.46). Conversational text is where "lexical-first, semantic as a separate tool for vague questions" matters most.

**(b) The librarian loop works on lexical search alone.** A ~60-line Claude tool loop (`proto/agent.py`) with two tools — `search(query, source?, date_from?, date_to?)` over a Tantivy BM25 index of all 210k chunks (with an apostrophe-safe Lojban field so `ce'u` is one token) and `read(id, before, after)` — answered the hard realistic questions (`proto/data/questions_realistic.jsonl`) correctly: xorlo's rationale, the 11–0 BPFK vote of 2004-12-25, the 2007 LLG "zasni gafyfantymanri" compromise; the four competing `ce'u` positions (Cowan/Rosta n-adic, nitcion's single-ce'u default, xorxes' monadic, pc's "always explicit") and the fact that Abstractors was never checkpointed; the BPFK checkpoint list; and the deliberately vague "big fight over lo in the mid-2000s". Each answer cited 14–20 chunk ids, **0 invalid ids**, and 27/28 verbatim quotes checked out. Answers are in `proto/data/agent_runs*.jsonl`.

What the loop did is instructive: 15–23 calls, mostly *search with a specific Lojban term or proposal name → read the hit with neighbours → search for the phrase it just learned* ("zasni gafyfantymanri", "checkpoint", a person's name). That is exactly the grep-and-follow behaviour the 2026 literature describes, and it is why lexical-first works: the agent's second query is always keyed, even when the user's first one was vague.

**(c) Cost.** Per question, Opus 5 at medium effort:

| configuration | tool calls | time | input tokens (uncached / cache-read) | cost |
|---|---|---|---|---|
| Opus 5, system prompt cached only | 16–22 | 81–97 s | 155–276k / 12–16k | **$0.90–1.52** |
| Opus 5, conversation prefix cached each turn | 23 | 83 s | ~0 / 270k | **$0.54** |
| Sonnet 5 (effort high), cached | 14 | 74 s | ~0 / 124k | **$0.17** |

Indexing side: the whole cleaned corpus is ~57M tokens; at $0.12/M that is ~$7 once (or free under Voyage's 200M-token tier); contextual headers cost nothing extra when they are metadata rather than LLM-written. LLM-written summaries (thread/episode/change notes) are the only expensive indexing step: ~57M input tokens through Sonnet 5 via Batch ≈ $60–100 one-off, and they are optional per source.

So the economics are: **retrieval infrastructure ≈ free; each deep answer ≈ 20–50¢; the loop's context growth is the cost driver**, which argues for (i) prompt caching, (ii) compact tool results (snippets first, full text on `read`), (iii) cheap read-subagents for long threads, (iv) a budget per question, (v) caching final verified answers for reuse.

---

## 5. Proposed architecture

```
 acquisition ─▶ canonical store ─▶ indexes ─▶ librarian agent ─▶ interfaces
 (scrapers,      (versioned units,   (lexical,    (tool loop,       (Discord bot,
  git mirrors,    stable ids,         dense,       verifier,         web app,
  API pulls)      bitemporal meta)    derived docs) notes/KB)        MCP for others)
```

### 5.1 Canonical store: units with time and identity

One SQLite/Postgres schema (or LanceDB tables) of **units**, each with: `source_type, source_id, unit_id (stable citation id), valid_from, valid_to (for versioned things), observed_at, author_canonical, parent (thread/page/edition), text, ctx_header`. Per source:

- **Wiki**: section @ revision. Ingest full revision history (API `prop=revisions`), store into a git-like content-addressed table so unchanged sections across revisions share one row. Talk pages and BPFK Section pages are *discussion* units with an extracted thread structure (signatures/dates) — they are the single richest source for "who argued what" and are currently 2.1M tokens of BPFK talk alone.
- **Mail**: message, deduped by Message-ID, quotes stripped, threaded (JWZ on References/In-Reply-To; the survey found 56% have In-Reply-To, enough with subject fallback). Ingest the other 21 public lists from MHonArc.
- **IRC**: time-gap episodes (45-min gap or ~350 tokens) with participant list; split #jbosnu out of the prefix block; normalise the four formats and reconstruct 2015 irssi dates. Bridged-nick unwrapping (`<xxxx> <la kanba>: …`) matters for identity.
- **CLL**: section @ edition, aligned across editions by section id; **change notes** per (section, edition A→B) generated once from git diffs. 1.0 must be reconstructed from the earliest DocBook commit + the 1997 HTML (lojban.github.io/cll states it matches the printed first edition).
- **Dictionary**: definition @ version from Lensisku's version API, plus votes/comments; link definitions to discussions by word-name search at index time.
- **Entity registry** (small, curated, LLM-seeded): person → {IRC nicks, e-mail addresses, wiki users, Discord handles}, role/tenure (BPFK jatna, LLG board). Applied at ingest (author_canonical) and at query time (search by person).
- **Timeline + status register** (curated): dated events from the wiki `Lojban timeline`, LLG minutes (38 pages), BPFK checkpoints, CLL tags, Lensisku changes; and a table of normative claims with `status ∈ {baseline-1997, baseline-2002, BPFK-checkpointed, voted-not-checkpointed, LFK, unofficial-1.2, proposal}` + ratifying document id. This is what lets the agent say "ratified by X on D [cite]" instead of "it seems accepted".

### 5.2 Indexes (multi-representation)

- **Lexical (Tantivy/LanceDB FTS)** over `ctx_header + text` with two analyzers: English-stemmed and Lojban-exact (apostrophe-preserving; `'`→`h` normalisation works and is what the prototype does). Fielded and filterable by source, date range, author, thread/page, edition.
- **Dense** over the same units with the header prepended; int8 storage; model id stored per vector so re-embedding is a migration, not a rebuild. Which model is a separate decision — but the benchmark says the choice matters 2× on Lojban-keyed text, so gate it with the `proto/bench.py` harness rather than MTEB.
- **Derived documents**, each indexed like any unit and citing its sources: thread summaries (mail, BPFK talk), IRC episode summaries for long/high-signal episodes, page-history summaries, CLL change notes, definition-history notes. These are what make *vague* questions land without a semantic index doing all the work, and they are cheap to regenerate incrementally.
- **Corpus map** (~2–5k tokens, in the cached system prompt): what the sources are, their coverage/gaps, the citation id grammar, the entity registry's top names, the status vocabulary. The prototype's much smaller map already steered the agent well.
- **Whole-reference prefixes** where the reference is small and stable: CLL plain text is 364k tokens — it can live in a 1-hour-cached prefix for a "CLL specialist" tool/subagent that answers "what does chapter 9 say / what changed in 1.1", at 0.1× read price, instead of being chunk-retrieved. BPFK sections (2.5M) and the dictionary (4–14M) cannot; those stay retrieved.

### 5.3 The librarian agent

- **Tools** (typed, in-process): `search_lexical`, `search_semantic`, `read` (unit + neighbours), `thread` (whole thread/episode/page-history in order, truncated with `read` for more), `diff` (CLL/wiki/definition between versions), `who` (entity registry), `timeline` (events in a window), `status` (ratification register), `quote` (return exact span from a unit — the only way a quote may enter the answer), `jbotci.*` via MCP (parse/gloss — e.g. to expand a question's Lojban into search terms), `note` (write a verified finding to the notes KB).
- **Loop**: one orchestrator model with a tool/token budget (Anthropic task budgets or a counter), adaptive thinking, prompt caching on every turn, results as snippets-first. Read-heavy sub-tasks (summarise a 40-message thread) go to a cheap subagent so the orchestrator's context stays small. Effort/model tier chosen by question class: lookup (Sonnet, low) vs history/dispute (Opus or Sonnet-high).
- **Answer contract**: claims with `[unit-id]` citations; quotes only via `quote`; disputes rendered as *Positions / Ratified / Open* with attribution and dates; explicit "corpus does not settle this". A mechanical verifier rejects unknown ids and non-verbatim quotes before the message is sent (fuzzy on whitespace/quote-prefixes/ellipses, as `proto/verify.py` learned the hard way).
- **Notes KB**: verified answers and intermediate findings ("the gadri checkpoint page revision that was officialised is X") are stored as units with provenance and searched first next time — this is the "librarian remembers" layer, and it compounds.

### 5.4 Interfaces and harness

Discord first: mention/DM-triggered, one thread per question, ack in <3 s, progress edits ≤1 Hz, 2,000-char chunks with masked-link citations resolving to a web viewer that shows the cited unit in context (the web app's first job). Web app hosts the viewer, the notes KB, and later a chat UI; the same agent is exposed as an MCP server so other agents (and jbotci users) can call the librarian. Harness choice and Rust crate state are in `research/agent-harness.md`; the short version: hand-rolled Messages loop in Rust + serenity/poise + `rmcp`, one small VPS, SQLite + Tantivy/LanceDB — or the Python Claude Agent SDK if you want grep/read/subagents/compaction for free at the cost of a second runtime.

---

## 6. Where the effort should go (in order)

1. **Acquisition + canonical store** with stable ids: wiki full history (+ re-fetch the 66 failed pages, esp. `Talk:BPFK Section: gadri`), other lists, Lensisku versions, CLL editions incl. a reconstructed 1.0, IRC normalisation. This is the only part with no shortcut and it unblocks everything else.
2. **Lexical index + the two-tool agent + verifier + Discord bot.** The prototype shows this alone is already useful; ship it early and let real questions drive the rest.
3. **Entity registry, timeline, status register** (curated, LLM-seeded). Highest quality-per-token of anything here.
4. **Derived documents** (thread/episode/change summaries) and **dense index** — measure with the query harness which of the two moves the *vague* bucket more before paying for both.
5. Notes KB, web viewer, MCP exposure, evaluation set growth.

## 7. Open questions for you

- Do you want CLL 1.0 reconstructed as a first-class edition (needs the 1997 HTML + earliest DocBook commit alignment), or is git history of 1.1 errata enough?
- Should identity resolution be public-facing (the bot naming people across nicks/e-mails) or internal only? It affects both the registry design and Discord etiquette.
- Is the notes KB allowed to be *cited* as a source, or must every answer bottom out in primary units?
- Acquisition of llg-members/llg-board archives needs a member's credentials or mbox — is that available?

---

## 8. Notes after comparing with the Codex report (`tmp/jbomohi-mid-2026-architecture-research.md`)

**Agreement on the system shape** (independently reached): immutable native sources → source-aware identity → structured + lexical + dense indexes; lexical/exact search first-class; hybrid + RRF + bounded reranker; hit → neighbourhood expansion (thread / revision / section); typed read-only tools; evidence ledger and a separate citation/coverage check; Discord as an adapter over a durable web report; evaluation before model selection; no GraphRAG up front; acquire wiki/dictionary history first.

**Where Codex is stronger and I under-weighted:** (1) the identity model — `Resource/Version/SourceEvent → Manifestation → Span`, with span ids independent of chunk ids so re-chunking never breaks citations; (2) "time is not one column" (source-asserted vs current-range vs effective vs system time); (3) mirror/quote de-amplification ("present in two backups ≠ two sources agree"); (4) coverage-aware negatives ("no decision found in the indexed sources through date X" rather than "never ratified"); (5) corpus text as untrusted input (prompt injection) and sandboxed ingestion; (6) rights/privacy as a launch gate (mail addresses, Discord data policy); (7) its evaluation strata and hard-negative list are directly reusable.

**Where I'd push back:** it is un-empirical (no prototype, no measurements), and from that it over-engineers the front end — four fixed effort "modes" with hard budgets and "not an agent loop for everything". The prototype shows a plain two-tool loop already answers the hard classes at $0.2–0.5; routing is a later cost optimisation and the "lookup" route is mostly jbotci. It also leans Postgres-everything (append-only PROV-style tables, pgvector) — the *schema ideas* are right, the ops weight is not needed for a solo project (SQLite/LanceDB + Tantivy carries the same schema). Its dictionary figures come from jbotci's copy (17.5k records) rather than the Lensisku dump (57.7k definitions), and it did not find Lensisku's version/diff API.

**Corrections to my own §3–5 after this comparison and the user's questions:**
- *IRC "episodes" are not a stored boundary.* Measured on 1.07M #lojban messages: median gap between messages 0.5 min, p90 10 min, p95 32 min, p99 3.7 h. A 45-min gap rule yields 42.7k episodes with sizes p50 = 5, p90 = 60, p99 = 291, max = 2,760 messages, and 60% of adjacent episodes share a participant — i.e. gap rules both fragment and merge conversations. So: index fixed-size windows (gap *or* ~350-token cap, as the prototype does), cite at line level (`#chan date HH:MM nick`), and make "episode" a *query-time expansion* (`read(before, after)` / time window). LLM-written episode summaries as derived documents are an optional, fully mechanical second pass (~23M tokens through a cheap batch model, ~$10–25), to be added only if the vague-IRC bucket needs it.
- *"Generic products cannot model time"* was overstated: date fields and range filters are universal. The real gap is **validity intervals** (what a page/definition said between versions; as-of queries) and version diffs — a small `valid_from/valid_to` per unit plus a `diff` tool, not a special database.
- *Thread and author are plain columns.* The system needs `parent`, `thread/page`, `author`, `date` and a neighbour/thread tool; the *semantics* live in the agent's prompt. The only non-generic piece is cross-source identity (nick ↔ e-mail ↔ wiki user), which is a small alias table — seedable by an LLM pass, and usable as a plain "who's who" document.
- *CLL 1.0 cannot be reconstructed from lojban/cll.* The repo starts 2008-05-30 as 342 HTML section files of the **online draft** ("pre-final version, has some typos" per the wiki), gets 265 community typo/errata commits, and is converted to DocBook on 2010-12-05 (`html2docbook.xslt`). `gh-pages` (2014-06) *claims* correspondence to the printed first edition with errata; `CLL-1_0-errata` is actually the 1.1 line (VERSION=1.1, "Red Book + errata only"). Label the states honestly — `1997-online-draft`, `1.0+errata-2014`, `1.1` (2016/18/19), `1.2.x`, `1.3.2` — and treat the printed 1.0 as an optional scan/OCR acquisition; align editions by chapter/section and example numbers across the HTML→DocBook shape change.
- *Ratification status is an output of research, not an input table.* Drop the curated status register; keep the status *vocabulary* (baseline-2002, BPFK checkpoint, ZG, LFK…) in the corpus map so the agent knows what acts to look for, apply Codex's rule ("say ratified only after finding a qualifying act; otherwise state coverage"), and memoise conclusions in the notes KB with provenance. Same for the timeline: the wiki already has one; notes accumulate the rest.

- *How notes get found later.* (a) Indexed like any unit (`source=notes`), so keyed searches hit them; (b) indexed by stored *question paraphrases* + key terms (question↔question matching is the easy direction for embeddings), with `search` returning a "related notes" strip mechanically on every call; (c) most importantly, **reverse linkage from evidence**: `read(unit)` reports "cited by note N: <conclusion>", so any research path that reaches the same evidence reaches the prior conclusion regardless of question wording. Notes are shortcuts to evidence, never evidence: answers still cite units, so reuse saves the 15–20 `search` calls, not the reads. Notes carry coverage (sources/date ranges/snapshot searched) so staleness is a coverage gap, not an age; they are append-only with supersession pointers. The agent writes one automatically after every research-class answer.

Net: the store is simpler than §5.1 said (units + parent/author/date/validity + neighbour and diff tools); the intelligence stays in the loop and in memoised, cited notes.

## 9. Prior art for "versioned documents + metadata + retrieval agent", and the corpus-as-repository option

Two product classes already combine all four ingredients: (1) **coding agents over git** (Claude Code, Cursor, Sourcegraph agentic search, Copilot) — versioned store, metadata, `log/blame/diff/show rev:path`, exact search, iterative agent; the "why is this line like this → blame → commit → PR discussion" loop is the same shape as our "why is it like that" questions; (2) **legal research platforms** with point-in-time law (legislation.gov.uk "Timeline of Changes" — verified; Westlaw/Lexis/vLex versions + citator metadata + agentic assistants with linked citations). Enterprise agentic search (Glean, Elastic, Azure, Onyx) has documents + metadata + permissions + agent but treats history as a re-indexing concern. No generic product covers a bring-your-own heterogeneous versioned archive because history semantics are source-specific. (Search budget was exhausted this session; Sourcegraph pages returned 403 — those characterisations are from prior knowledge.)

**Design consequence — materialise the corpus as a git repository and use a coding-agent harness as the librarian.** Wiki pages as files with revisions replayed as commits (author/time/comment preserved; Tiki history likewise); CLL brought in as a `git subtree` (its history is already native git, 2008→); dictionary words as files with Lensisku definition versions as commits; mail as one file per thread, IRC as one file per channel-day (append-only, no history needed); the notes KB as a directory of front-mattered markdown committed by the agent (cited-by = grep for the unit id). Free: `rg` (apostrophe-safe), neighbourhoods (the file), page/thread context, history/diff/as-of/authorship (`git`), stable citations (`path@rev:line`), and a harness (Claude Code / Agent SDK: Grep/Glob/Read/Bash, caching, compaction, subagents) tuned for exactly this shape. Dense search + jbotci remain MCP tools beside it. Costs: a one-off revision-replay job; Discord/web/permissions still to build; derived docs are just more files. Scale is fine (≈125k wiki revisions + dictionary versions ≪ kernel-scale git). Granularity rules: **one commit per event** (mail message, IRC day, wiki revision, dictionary definition version, dictionary comment), author/date taken from the source, applied in chronological order so `git log --since/--until/--author` is a cross-source timeline and `git rev-list -1 --before=<date>` gives as-of. Mail is stored as a real, deterministic-named, read-only Maildir (human-readable) plus a generated decoded per-thread text projection in the same commit (agent-readable); votes go to a per-word `votes.csv` (header row) rather than commits; Lensisku/jbovlaste definition comments are first-class (one commit each into `dict/<word>/comments.md`; jbovlaste's old comments may need scraping since the XML export omits them). The repo is a deterministic, rebuildable projection of the raw archives (which remain the system of record), so late-arriving sources are added by rebuild rather than by breaking chronology; dictionary history carries an explicit coverage boundary (versions exist only from when Lensisku/jbovlaste recorded them). Maintenance model (agreed with user): an orphan `tools` branch holds all acquisition/replay scripts and operates on a `git worktree` of `main`, committing events with committer date = author date = source time, tagging `snapshot/<ts>`; a scheduled GitHub Action runs increments (initial rebuild local; raw dumps outside git/LFS). Back-fill is allowed: `--since/--until/--author` work on source time regardless of insertion order; as-of is per-file (`git log -1 --before=<d> -- path`, then `git show`), whole-tree as-of only at snapshot tags; citations use stable source ids in commit trailers (Message-ID, revid, definition version id), never SHAs. Initial dictionary replay from full jbovlaste/Lensisku DB dumps (history, comments, votes tables); periodic full-dump diffs produce events, with in-place changes dated as an `Event-Window` between dumps. Maildir files pre-created in `cur/` with `:2,S`, mode 0444. File metadata in TOML (state), flat ledgers as CSV with header rows (JSONL only if nesting is needed); commit metadata (event) is deliberately separate: commits say who/when/what changed, files say what is. This is now the default to beat; the bespoke SQLite/Tantivy/LanceDB store from §5 is the fallback if git's query surface proves too coarse (e.g. dictionary as-of at scale).

## Appendix: artifacts

- `research/data-survey.md` — full local inventory, formats, quirks, gaps.
- `research/retrieval-sota.md` — dated sources for §2; superseded-ideas list.
- `research/domain-data-handling.md` — techniques per data shape; **verified online availability of every Lojban source** (Lensisku API, wiki export, Tiki, MHonArc lists, IRC, Google Groups limits); design implications.
- `research/embeddings-landscape.md`, `research/agent-harness.md` — the two "separate questions" (model/store choice; harness/Discord/hosting), for when you get there.
- `tmp/fable/proto/` (session scratch; see `doc/research/proto-notes.md`) — `chunk_{wiki,irc,mail}.py` (unit extraction), `index_lex.py` + `corpus.py` (Tantivy index, 210k chunks, ms latency), `bench.py`/`bench_post.py` (retrieval benchmark, synthetic queries via `gen_queries.py`), `agent.py` (librarian loop), `verify.py` (quote/citation check), `data/questions_realistic.jsonl` (28 hand-written questions by category), `data/agent_runs*.jsonl` (full answers + traces + usage). `uv run` in `proto/`; keys are read from `~/git/jguvi-api-keys.md` (OpenRouter for embeddings/rerank, Anthropic for the agent).
