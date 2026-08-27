# jbomo'i — functional specification

Status: **draft v0.2, 2026-08-27**. Authors: Fable (spec), the human partner (adjudication). Implementer: Codex. Changes from v0.1 are recorded in `doc/decisions/2026-08-27-scope-and-policies.md`; the deferred v0.1 material (indexes, a librarian service, Discord/web/MCP interfaces) is preserved in `doc/future/librarian-service.md` and is **out of scope**.

Conventions: MUST / SHOULD / MAY as in RFC 2119. "Corpus" means the Lojban historical record as materialised on the `main` branch. Paths are relative to the `tools` checkout unless prefixed `main:`.

---

## 1. What is being built

### 1.1 Deliverable

A **public git repository** whose `main` branch is the Lojban community's historical record — the wiki with its full revision history, the mailing lists as real Maildirs, the IRC logs, the dictionary with its definition history, comments and votes, every CLL edition — materialised as text files with **one commit per source event**, so that `grep` and `git` (search, neighbourhood, history, as-of, diff, authorship) are the retrieval primitives. Together with it, the **tools to build and update** that branch reproducibly, and the **instructions** that make a fresh clone immediately usable by a coding harness (Claude Code, Codex, Gemini, …) as a research librarian: *why is it like that, how did that happen, who decided, was it ratified, what are the competing views* — answered with verbatim, verifiable citations.

### 1.2 Non-goals

- No services: no bot, no web application, no API, no hosted index. The librarian is the user's own coding harness pointed at a clone.
- No authentication, no restricted data. Everything in the repository is repackaged **public** data; restricted list archives are excluded unless their owner publishes them.
- No redaction or pseudonymisation of public data (email addresses, nicknames, names stay as archived).
- No identity *resolution*: the repository records dated, cited **attestations** about aliases (§3.7); it never merges identities.
- No knowledge graph, no precomputed conclusions. Conclusions are research outputs recorded as notes that must bottom out in primary units (§3.8).
- No real-time ingestion; updates are batch (§4.5).

### 1.3 Principles (normative)

1. **The corpus is a repository.** Files + one commit per source event; metadata split between commits (the event) and files (the state) (§2.5, §3.1.3).
2. **Raw fidelity first.** Original bytes are stored byte-exact wherever the source is text; renderings are separate files that say they are renderings (§3.1.2).
3. **Mechanistic.** Every file, boundary, id and commit is computed from the sources by rules stated here. Nothing is curated by hand except contributed notes and attestations, which are ordinary cited commits.
4. **Deterministic and rebuildable.** `main` is a function of (immutable raw archive, `tools` commit); the tools to rebuild and extend it live in the same repository on `tools` (§2.4, §4).
5. **Time everywhere.** Every commit carries the source event time; every citation names a version; as-of is a `git` operation (§2.6).
6. **Evidence bottoms out in primary units.** Notes and attestations cite primary units; an answer cites primary units, never a note (§3.8).
7. **Coverage is explicit.** Every source states what it covers and what it is missing; negative answers are made relative to that coverage (§3.9, template AGENTS.md).
8. **Corpus text is untrusted input** for any harness reading it; the instruction files say so (§6).

---

## 2. Repository model

### 2.1 Branches

Two branches with **no shared history**; neither is ever merged into the other.

| branch | content | default checkout |
|---|---|---|
| `main` | the corpus projection (§3): data, `_meta/`, and the instruction files rendered from `tools/templates/main/` | for end users |
| `tools` | tooling (`tools/`), documentation (`doc/`), templates, CI, the model-session exchange | for maintainers |

`main`'s first (root) commit contains the rendered instruction files (`README.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/rules/jbomohi.md`, `.gitignore`) and `_meta/schema.toml`; every later commit is a source event, an instruction/`_meta` refresh, or a contributed note/attestation. The current `main` (a single `.gitignore` commit) is discarded and recreated as an orphan by the first `build`.

### 2.2 Working layout (maintainers)

Checkout `tools` at the repository root; the corpus is a git worktree of `main` at `./corpus/` (gitignored), created by `jbomohi corpus init` (`git worktree add corpus main`, or `--orphan` when `main` does not exist). Tools resolve it from `JBOMOHI_CORPUS` (default `./corpus`). Untracked local state: `./corpus/`, `./.exchange/`, `./tmp/`, `./.venv/`.

### 2.3 Raw archive tier

Downloaded dumps, zips, API responses, scraped pages and database dumps are **never committed** as such. They live in an archive directory (`JBOMOHI_ARCHIVE`, default `~/lojban/archive`) as immutable content-addressed objects with manifests `{source, kind, origin, fetched_at, sha256, bytes, coverage {from, to, counts}, notes}`. Manifests are tracked on `main:_meta/archive/` so the projection is reproducible by anyone with the same objects. Public objects MAY be mirrored as assets of a GitHub Release tagged with the snapshot (§10.3); private database dumps are never mirrored — their manifests suffice to prove what was used.

The raw **mail** is the exception to "never committed": the Maildirs on `main` *are* the raw objects (§3.3), because the repository's purpose is to publish them.

### 2.4 Rebuild contract

`main` is a deterministic function of (archive contents, `tools` commit, contributed content harvested from the previous `main` — §3.8). Two `build`s on the same inputs MUST produce identical commit hashes: author/committer identities and dates come from the sources, never from the wall clock (the sole exception is §2.5's `Event: contributed`, whose date is the contribution's own commit date, also not the wall clock). `update` appends events without rewriting history. A full `build` (re-linearisation) is allowed at any time; nothing cites commit hashes (§3.1.4).

### 2.5 Commit conventions on `main`

One commit per **source event**: a wiki revision; a Tiki page version; a mail message; an IRC day file (import or amendment); a dictionary definition version; a dictionary comment; one day of dictionary votes; a CLL edition rendering; a `_meta`/instruction refresh; a contributed note or attestation. Batching several events into one commit is forbidden except for the daily vote batch.

- **Author** = the source author: `GIT_AUTHOR_NAME`/`EMAIL` from the source verbatim (mail `From:`); where the source has a username but no email, a synthetic `<username>@<source-host>` (`Gleki@mw.lojban.org`, `xod@irc.lojban.org` is *not* used — IRC day files are authored by the logger, see §3.4). Synthetic addresses are documented in `main:README.md`.
- **Committer** = `jbomohi <jbomohi@lojban.org>` (placeholder, Open Question §10.2).
- `GIT_AUTHOR_DATE` = `GIT_COMMITTER_DATE` = the source event time. UTC when the source is unambiguous; otherwise the source's own local time, with `Time-Confidence` set.
- **Subject**: `<source>: <summary ≤ 72 chars>` — `wiki: BPFK Section: gadri (rev 108932) fix typo`, `mail/lojban: Re: [lojban] xorlo podcast`, `irc/lojban: 2015-06-20 (412 lines)`, `dict: kau en#12345 v3`, `cll: render 1.1-2019`, `meta: refresh README and coverage`, `notes: xorlo adoption (2004–2007)`.
- **Trailers** (`Key: value`, one per line, at the end of the body):
  - `Source: wiki | tiki | mail/<list> | irc/<channel> | dict | cll | meta | notes | who`
  - `Source-Id: <stable id>` — the citation anchor (§3.1.4)
  - `Event: created | edited | deleted | moved | comment | vote-batch | import | render | refresh | contributed`
  - `Time-Confidence: exact | tz-unknown | window`
  - `Event-Window: <iso-date>..<iso-date>` when only bounded
  - source-specific: `Page-Id`, `Parent-Rev`, `Message-Id`, `In-Reply-To`, `Thread`, `Definition-Id`, `Version`, `Word`, `Edition`, `Renderer`.

### 2.6 Ordering, back-fill, as-of

- `build` emits events in strict chronological order across sources (merge by event time; ties by source name, then id).
- `update` appends; a newly added source or late batch may therefore sit at the tip with old dates. `git log --since/--until/--author` still work (they use committer date = source time). **Per-file as-of** is always correct: `git log -1 --before=<date> -- <path>` then `git show <commit>:<path>`, because each event commit writes that file's state at that event.
- **Whole-tree as-of** is guaranteed only at snapshot tags: `snapshot/<UTC ts>`, annotated, created after every `build`/`update`, message = the coverage summary.
- `build` re-linearises; because citations use `Source-Id`s, nothing breaks.

### 2.7 Size, hosting, pushing

Hosting: GitHub. Text only (no media, PDFs, HTML renderings). Budget: stay under GitHub's 5 GB recommendation and 100 MB per file; expected packed size ≈ 0.6–1.2 GB (mail dominates; git delta-compresses RFC 822 text well — measure at M1 and record in `doc/decisions/`). Pushes are limited to 2 GB each: the initial push is done in commit ranges (`git push origin <sha>:refs/heads/main` stepwise). If mail alone would exceed the budget, the mail raw tier moves to a companion repository (`jbomohi-mail`) and `main` keeps the thread views — decided at M1 with numbers, not before.

---

## 3. Corpus projection (`main`)

### 3.1 Cross-cutting rules

#### 3.1.1 Layout

```
README.md AGENTS.md CLAUDE.md GEMINI.md .agents/rules/jbomohi.md .gitignore   rendered from tools/templates/main/
_meta/          schema, archive manifests, coverage, CSV indexes (§3.9)
wiki/<ns>/      MediaWiki pages, raw wikitext, full history (§3.2)
tiki/           pre-2013 Tiki wiki pages with history (§3.2.5)
mail/<list>/    real Maildir + generated thread views (§3.3)
irc/<channel>/  one file per channel-day (§3.4)
dict/<word>/    definitions, comments, votes (§3.5)
cll/            CLL source submodule + per-edition text renderings (§3.6)
who/            alias attestations (§3.7)
notes/          contributed research notes (§3.8)
```

#### 3.1.2 Encoding and fidelity

UTF-8, LF, no BOM for generated files. Raw-fidelity files (wikitext, RFC 822 messages, IRC lines, Tiki markup) are byte-exact as archived except for the normalisations listed per source. Renderings (thread views, CLL edition text) start with a `#` header line naming the source and renderer so they are never mistaken for originals.

#### 3.1.3 Metadata split

Commit metadata describes the **event** (who, when, what, source id). File metadata describes the **state**: TOML front matter between `+++` lines for Markdown/TOML-bearing files; a single `#` header line for plain-text renderings; none for raw-fidelity files (their metadata is in `_meta/` CSVs and in commits). Ledgers are CSV with a header row (RFC 4180). JSONL only where records nest.

#### 3.1.4 Citations

```
<path>@<Source-Id>:L<start>[-<end>]
```

`<path>` on `main`; `<Source-Id>` the stable id of the cited **version** (wiki `revid=…`, mail `<Message-ID>`, IRC `YYYY-MM-DD`, dict `definition=<id> version=<n>`, CLL `cll=<edition>`, note id, tiki `tiki=<page>@<version>`); `L…` 1-based lines in that version. Resolution: the commit whose `Source-Id` trailer matches for that path (for append-only files — IRC days, thread views — the commit at or after that id); read the lines from that blob. Commit hashes are never part of a citation. Short forms (`wiki:<pageid>@<revid>:L…`, `mail:<Message-ID>:L…`, `irc:<channel>/<date>:L…`, `dict:<word>/<id>@<v>:L…`, `cll:<edition>/<chapter>:L…`, `note:<id>`) are defined in `main:AGENTS.md` for harness use.

#### 3.1.5 Filename slugs

`slug()`: NFC; keep `[A-Za-z0-9'_,-]`; space → `_`; percent-encode everything else (including `/`, `:`, `.`); percent-encode a leading `.`/`-`; cap at 200 bytes (excess → `-` + 8 hex of SHA-1 of the full title). Injective on MediaWiki titles and dictionary words; `_meta/<source>/*.csv` maps title/word ↔ path so nothing depends on inverting it.

### 3.2 Wiki (`wiki/`)

**Source.** `https://mw.lojban.org/api.php` — `prop=revisions` with `rvprop=ids|timestamp|user|comment|size|sha1|content`, `rvlimit=max`, `rvdir=newer`, all namespaces except `File` binaries, full history; ≤ 1 request/s, `maxlag=5`. The local snapshot (`~/git/lojban-wiki`) is a page-count cross-check only. The 66 pages it could not fetch are retried by title each update and listed in `_meta/wiki/errors.csv` while they fail.

**Layout.** `wiki/<ns>/<slug(title)>.wiki`, `<ns>` ∈ `main, talk, user, user_talk, lojban, lojban_talk, userwiki, userwiki_talk, file, file_talk, template, template_talk, category, category_talk, module, module_talk, mediawiki, mediawiki_talk, help, help_talk`. `File:` pages keep the description wikitext; media are manifest-only in `_meta/wiki/media.csv` (`pageid,title,url,sha1,size,mime,uploaded,uploader`). Redirects are stored as their wikitext.

**Content.** The revision's raw wikitext, byte-exact. No front matter.

**Events.** One commit per revision, page-internal order by `revid`, global order chronological. Author `<user>` / `<user>@mw.lojban.org`; date = revision timestamp (UTC, `exact`). Subject `wiki: <title> (rev <revid>) <comment ≤ 40>`. Trailers `Source: wiki`, `Source-Id: revid=<revid>`, `Page-Id`, `Parent-Rev`, `Event: created|edited|moved|deleted` (`Moved-From:` on moves; deletions only where the API exposes them). Suppressed revisions go to `_meta/wiki/gaps.csv`, never reconstructed.

**Indexes.** `_meta/wiki/pages.csv` (`pageid,ns,title,path,is_redirect,first_rev,last_rev,revisions`), `revisions.csv` (`revid,pageid,parentid,timestamp,user,size,sha1,comment`).

**Quirks.** The 2014 bulk "Text replace" revisions are kept; `main:AGENTS.md` warns that they are noise when reading history. Talk pages are wikitext; no thread reconstruction at projection time.

#### 3.2.5 Tiki (`tiki/`)

`https://tiki.lojban.org` (`tiki-index.php?page=`, `tiki-pagehistory.php?page=`), HTML scrape ≤ 1 request/s; coverage ≈ 2001–2015; best effort (M2). `tiki/<slug(page)>.tiki` (Tiki markup, HTML-unescaped, otherwise byte-exact), one commit per version (`Source: tiki`, `Source-Id: tiki=<page>@<version>`, author from the history table, `exact`). `_meta/tiki/pages.csv`, `versions.csv`, with a `migrated_to` column naming the MediaWiki page where an import template (`{{BPFK Section from tiki|…}}`) or identical title establishes the correspondence.

### 3.3 Mail (`mail/<list>/`)

**Sources.** (a) the local `lojban-list` Maildirs (`~/lojban/disc/mail/maildir` **and** `b2024/maildir`; both ingested, dedupe handles the overlap); (b) `https://mail.lojban.org/lists/<list>/` MHonArc archives for every other **public** list (`announce, bpfk, bpfk-announce, dracyselkei, jbofongri, jboske, jbosnu, jbovlaste, lbck, lojban-beginners, lojban-de, lojban-es, lojban-fr, lojban-list-old, old_lojban-list, lojban_story, pod, wikichanges, wikidiscuss, wikineurotic`), ≤ 1 request/s, each `msgNNNNN.html` reconstructed into an RFC 822 message (headers from the `<!--X-…-->` comments and the rendered header block, body from the rendered text) carrying `X-Jbomohi-Manifestation: mhonarc`; (c) `old_lojban-list/` raw RFC 822 files (1998–2003). Lists that return 401 (`llg-members`, `llg-board`) are excluded.

**Layout.**

```
mail/<list>/cur/<unixtime>.<sha1(message-id)[:16]>.jbomohi:2,S   raw RFC 822, byte-exact, mode 0444
mail/<list>/new/  mail/<list>/tmp/                                 present, empty (.keep)
mail/<list>/threads/<YYYY>/<thread-key>.txt                        rendered thread view
```

A real Maildir readable by mutt/notmuch/mu; files are born in `cur/` with the Seen flag so readers do not rename them. `<thread-key>` = 12 hex of SHA-1(root Message-ID) + `-` + `slug(normalised subject)` ≤ 60 chars.

**Thread view.** Line 1: `# mail/<list> thread <thread-key> | root <Message-ID> | <n> messages | rendered by jbomohi <renderer>`; then per message `=== <n> | <ISO date> | <From> | <Message-ID> | <maildir file>` followed by the decoded `text/plain` body verbatim (HTML-only messages converted deterministically and marked `[html]` in the entry line); messages in JWZ order (References/In-Reply-To; subject fallback for orphans). Quotes and signatures are kept.

**Events.** One commit per unique message (Message-ID normalised: trim, strip `<>`, lower-case the domain; missing → `sha1(raw)@jbomohi.invalid`). Author = `From:` verbatim; date = `Date:` → UTC (`exact`), else first `Received:` (`tz-unknown`), else archive order (`window`). Subject `mail/<list>: <Subject ≤ 60>`; trailers `Source: mail/<list>`, `Source-Id: <Message-ID>`, `Message-Id`, `In-Reply-To`, `Thread: <key>`, `Event: created`. The same commit appends the message to its thread view.

**Indexes.** `_meta/mail/<list>/messages.csv` (`message_id,date,from,subject,thread_key,file,manifestation,duplicate_of`), `threads.csv`, `duplicates.csv`.

### 3.4 IRC (`irc/<channel>/`)

**Sources.** `https://lojban.org/irclogs/<channel>/<YYYY_MM>/<YYYY_MM_DD>.txt` for `lojban`, `jbosnu`, `ckule` (plus `2000_all`, `2002_middle`, `2002_12`); the local `all_logs.txt` only as a cross-check (its first 51,004 lines are `#jbosnu`, not `#lojban`).

**Layout.** `irc/<channel>/<YYYY>/<YYYY-MM-DD>.txt`; line 1 `# irc #<channel> <date> tz=<±HHMM|unknown> source=<archive path> format=<iso|legacy|bracket|irssi>`; then lines in exactly one of the forms `HH:MM:SS <nick> message`, `HH:MM:SS * nick action`, `HH:MM:SS -- system/topic text`. Timestamps stay in the log's own timezone (in the header), seconds `00` where absent; text byte-exact except mIRC control codes and NULs removed. Bridged relays (`<xxxx_> <la cenzis>: …`) are kept verbatim (`who/relays.toml` documents the patterns). Irssi-block dates come from `--- Day changed` markers; the 2000 bracket format takes its date from the file name.

**Events.** One commit per day file (`Event: import`, or `edited` when an archive day changes), author `irc-logger <irclogs@lojban.org>`, date = last message time of the day in its timezone, `Source: irc/<channel>`, `Source-Id: <date>`. `_meta/irc/<channel>/days.csv` (`date,lines,messages,nicks,tz,format,source`).

### 3.5 Dictionary (`dict/<word>/`)

**Sources.** Initial replay from full jbovlaste and Lensisku database dumps (schemas per §10.5; the loader is written against the dumps). Ongoing: Lensisku's public changes feed / version API where available, else periodic dumps diffed by primary key. jbovlaste's read-only site is scraped only for comment/etymology pages absent from the dumps.

**Layout.** `dict/<slug(word)>/word.toml` (`word, type, rafsi, selmaho, created, creator, source_ids`); `dict/<slug(word)>/<lang>-<definition-id>.md` with `+++` front matter (`id, word, lang, author, created, updated, version, score, status, source, keywords = [{word, sense, place}], examples`) and body = definition text verbatim, then `## Notes` verbatim; `comments.md` (append-only, `## <ISO date> — <author> (comment <id>, on definition <id>)` + text; replies noted `(in reply to <id>)`); `votes.csv` (`definition_id,voter,date,value`; voter as published by the source, §10.5).

**Events.** One commit per definition version (`created|edited|deleted`; author `<user>@jbovlaste.lojban.org`; date = version time, or the later dump's date with `Event-Window`/`window`); one per comment (`comment`); one per day of votes (`vote-batch`, author `jbomohi`, also updating `score`). Trailers `Source: dict`, `Source-Id: definition=<id> version=<n>` | `comment=<id>` | `votes=<date>`, `Definition-Id`, `Version`, `Word`. `_meta/dict/coverage.toml` states from when history is event-accurate, where it is dump-window-accurate, and which definitions have only a creation date.

### 3.6 CLL (`cll/`)

**Source.** A git **submodule** at `cll/src` (upstream `lojban/cll` or the fork `int19h/cll`, §10.4) so upstream commits, tags and history are preserved verbatim. Plus tracked per-edition plain-text renderings `cll/editions/<edition>/<ch>-<slug>.txt`:

| edition | source ref | note |
|---|---|---|
| `1997-online-draft` | first import `8048799d` (342 HTML sections) | the pre-final online draft, not the printed book |
| `1.0-errata-2014` | `gh-pages` @ `dabe6154` | maintainers' reconstruction of printed 1.0 + errata (a claim, not diff-verified) |
| `1.1-2016`, `1.1-2018`, `1.1-2019` | `v1.1-<date>-html` tags | official LLG 1.1 |
| `1.2.<n>` | `geklojban-1.2.*` | unofficial |
| `1.3.2` | `v1.3.2` | fork |

The printed 1.0 is not recoverable from the repository; a future scan/OCR would be edition `1.0-print`.

**Rendering.** Line 1 `# cll <edition> chapter <n> <title> | rendered from <ref> by jbomohi <renderer version>`; sections as `## <n>.<m> <title>` (numbers are stable across editions), examples as `[Example <n>.<m>]`, markup dropped deterministically, Lojban/gloss lines preserved one per line. One commit per edition rendering (`Event: render`, author `jbomohi`, date = the edition's publication/tag date, `Source-Id: cll=<edition>`, `Renderer:`). `_meta/cll/alignment.csv` (`edition_a,section_a,edition_b,section_b,relation,method`) from section-number matching plus text similarity.

### 3.7 Alias attestations (`who/`)

Identities are **not resolved**. `who/attestations.csv` (header: `id,date,kind_a,value_a,kind_b,value_b,relation,method,source,note`) records dated, cited claims that two handles are related: `relation ∈ same-person | signature | self-statement | profile | relay | retired-nick | contradicts`; `kind ∈ irc | email | wiki | jbovlaste | discord | telegram | name`; `method ∈ signature-line | self-statement | profile-page | relay-pattern | maintainer | inference`; `source` is a citation (§3.1.4). `who/relays.toml` documents bridge patterns. Learning later that A = B is a **new attestation** dated when it was learned, citing the evidence; nothing earlier is rewritten, and a reader must combine attestations per question. Tools MAY propose attestations (`jbomohi who propose`, heuristics over signatures, "X (nick)" mentions, user pages) into `who/proposed.csv` for a human to promote; every promoted row is an ordinary commit (`Source: who`, `Event: contributed`).

### 3.8 Notes (`notes/`)

Research conclusions contributed by humans or by harness sessions. `notes/<YYYY>/<YYYYMMDD>-<slug>.md`, front matter (`+++`): `id, created, author, status ∈ draft|verified|superseded, supersedes, questions = [...], terms = [...], sources = [citations], coverage = {sources, from, to, snapshot}, confidence`; body `## Conclusion`, `## Positions` (attributed and dated), `## Ratified` (acts found with citations, or "none found within coverage"), `## Open`, `## Trace`. **Every claim in a note cites primary units; a note is never itself cited as evidence** — it is a map to evidence. `jbomohi notes lint` validates front matter and resolves every citation.

Notes and attestations are **contributed content**: they are committed to `main` directly (or via pull request), one commit each, `Event: contributed`, author = contributor, date = contribution time (the only commits not carrying a source time). A `build` harvests them from the previous `main` history (or a `git bundle` of it) before rebuilding and replays them in date order, so re-linearisation never loses contributions.

### 3.9 `_meta/` and coverage

`_meta/schema.toml` (`projection_schema`, renderer versions, tools commit), `_meta/archive/*.toml` (§2.3), per-source `coverage.toml` (`from, to, counts, gaps = [...], updated`), and the CSV indexes above. `build`/`update` re-render `README.md` (coverage tables) and the instruction files from `tools/templates/main/` as an `Event: refresh` commit at the tip, dated at the last event's time.

---

## 4. Tools (`tools` branch)

### 4.1 Language and layout

Python ≥ 3.13 with `uv`; package `jbomohi_tools`, CLI `jbomohi` (`uv run jbomohi …`). Third-party dependencies only with a reason recorded in `pyproject.toml`. Layout: `tools/exchange/` (the exchange, §9), `tools/jbomohi_tools/` (`archive/`, `project/<source>.py`, `render/`, `who/`, `notes/`, `git.py`), `tools/templates/main/` (instruction files for `main`), `tools/tests/`, `doc/`, `.github/workflows/`.

### 4.2 CLI

```
jbomohi corpus init|status                  create / inspect ./corpus (worktree of main)
jbomohi archive fetch <source> [--since …]  fetch into the archive tier; write manifests
jbomohi archive verify                      sha256-check every manifest
jbomohi build [--sources …] [--until DATE]  full deterministic rebuild of main (orphan root)
jbomohi update [<source> …]                 append new events; refresh; tag snapshot/<ts>
jbomohi verify                              invariants (§4.4)
jbomohi cll render <edition>                per-edition rendering (§3.6)
jbomohi who propose|promote                 attestation helpers (§3.7)
jbomohi notes lint                          front matter + citation resolution (§3.8)
jbomohi cite resolve <citation>             print the cited lines (the reference resolver)
```

Idempotent and resumable; network commands rate-limited per source (default ≤ 1 request/s) with backoff; writes only to the archive, the corpus worktree, and `tmp/`.

### 4.3 Fetch/project split

Each source module exposes `fetch(archive, since) -> manifests` (network; writes only the archive) and `project(archive, state) -> events` (pure: no network, no clock). A single `commit_event(event)` helper enforces §2.5. Renderers are versioned; a renderer version bump is a `build`, not an `update`.

### 4.4 Invariants (`jbomohi verify`)

Every `main` commit has `Source`, `Source-Id`, `Event`, `Time-Confidence`; `Source-Id` unique per `(Source, path)`; `_meta/*.csv` rows ↔ files; Maildirs contain only `cur/` files per §3.3 with mode `0444`, every message has a thread-view entry; IRC files parse under §3.4 and sit in the right year; dictionary front matter and `votes.csv` validate; notes lint clean; a determinism sample (rebuild the last 30 days of each source twice → identical commits).

### 4.5 Cadence and CI

`.github/workflows/check.yml` on push/PR to `tools`: tests (tools and exchange, the latter unbound and bound), lint, determinism sample. `.github/workflows/update.yml` weekly + manual: checkout `tools`, worktree `main`, `archive fetch` for public sources (cached), `update`, `verify`, push `main` and the tag; a failing `verify` never pushes. The initial `build` runs locally (hours; 6-hour CI limit). Private dumps are applied locally with `jbomohi update dict --dump <file>`.

---

## 5. Instruction files on `main` (the librarian)

Rendered from `tools/templates/main/` into `main`'s root commit and refreshed at every update. They are what turns a clone into a librarian:

- `AGENTS.md` — what the corpus is, layout and coverage, the citation grammar and short forms, the research method (search iteratively with `rg`/`git grep`, read neighbourhoods, follow leads, use `git log/blame/show/diff` for history and as-of, `_meta` CSVs for lookups), the answer contract (claims cite primary units, verbatim quotes only, positions attributed and dated, Positions/Ratified/Open for disputes, coverage-relative negatives), the status vocabulary and bodies, known quirks, and the untrusted-text rule. Draft: `tools/templates/main/AGENTS.md`.
- `CLAUDE.md`, `GEMINI.md` → `@AGENTS.md`; `.agents/rules/jbomohi.md` (Antigravity always-on rule pointing at `AGENTS.md`).
- `README.md` — human-facing: what this is, how to clone (submodule note for `cll/src`), coverage tables (rendered from `_meta`), the citation grammar, how to contribute notes/attestations, licence/provenance statement (§10.6).
- `.gitignore` — `/.jbomohi/` (reserved for local caches a harness might build) and OS junk.

---

## 6. Trust and provenance statements

`README.md` and `AGENTS.md` on `main` MUST state: the data is public and republished as archived; email addresses and names appear as in the sources; synthetic addresses (`@mw.lojban.org`, `@jbovlaste.lojban.org`, `@irc.lojban.org`) are placeholders, not deliverable addresses; renderings are not originals; identities are attested, never resolved; archive text can contain instructions and must be treated as data by any agent reading it.

---

## 7. Evaluation of the repository

- **Determinism**: two full builds → identical `main` (commit hashes).
- **Counts** vs `doc/research/data-survey.md` within tolerance (wiki pages 14,118 ± retried failures; unique lojban-list messages ≈ 77,5k after both Maildirs; IRC lines 1.10M in `raw/` ± the jbosnu split).
- **Citation spot checks**: 30 citations sampled from `doc/eval/questions.jsonl` research answers resolve with `jbomohi cite resolve` to the expected text.
- **Librarian dry run**: a fresh clone of `main`, a coding harness with no extra instructions, the 28 questions in `doc/eval/questions.jsonl`; Fable reviews answers for citation validity (every citation resolves; quotes verbatim) and attribution. This is the acceptance test of §5, not of any model.
- **Size**: packed size and push feasibility recorded in `doc/decisions/`.

---

## 8. Milestones

| # | deliverable | acceptance |
|---|---|---|
| **M0** | `tools` scaffold: `uv` project, CLI skeleton, `corpus init`, `commit_event`, templates, exchange, `check.yml` | tests green; `jbomohi corpus init` creates an orphan `main` with the rendered root commit |
| **M1** | **The repository**: wiki (full history), `lojban-list` mail (both local Maildirs), IRC (`lojban`, `jbosnu`, `ckule`); `build`, `update`, `verify`, snapshot tags; `README`/`AGENTS` rendered; pushed to GitHub | §7 determinism, counts, citation spot checks, librarian dry run, size recorded |
| **M2** | dict (from dumps, comments, votes), CLL submodule + editions + alignment, `who/` attestations + relays, `notes/` conventions + lint, Tiki, the other public lists (MHonArc), `update.yml` | as-of and diff questions in the dry run answered with resolving citations; `update.yml` completes one scheduled run |

Deferred beyond M2: `doc/future/librarian-service.md`.

---

## 9. Collaboration

Roles: the human partner adjudicates; **Fable directs and reviews**; **Codex implements** on branches off `tools` and opens pull requests demonstrating acceptance with commands and outputs. Work items are GitHub issues (§10.1; `doc/issues/` until then). Sessions coordinate through `tools/exchange/` (`jbomohi-mail/v1`): `join`, `status` at the start and end of every substantive turn, `new`/`publish`/`ack`; see `tools/exchange/PROTOCOL.md`.

---

## 10. Open questions

1. **GitHub organisation/repository name** and whether `main` and `tools` live in the same repository (default: yes, `int19h/jbomohi`); issue tracker there.
2. **Committer identity** for `main` commits (name/email) and for CI pushes.
3. **Raw archive mirroring**: whether public raw objects (irclogs zip, MHonArc scrapes, wiki API dumps) are attached to snapshot Releases for reproducibility (recommendation: yes, per snapshot).
4. **CLL submodule source**: `lojban/cll` (upstream, no 1.3.x) vs `int19h/cll` (fork, all editions). Recommendation: the fork, with the upstream tags mirrored.
5. **Dictionary dumps**: schema (on receipt); whether vote rows name voters in the public data (if not, `votes.csv` carries counts per day only); whether jbovlaste comments migrated to Lensisku.
6. **Licence/provenance statement** for the repository: the sources' terms (wiki policy, LLG copyright on CLL, list archives) need one paragraph each in `README.md`; recommendation: republish under the sources' own terms, stated per directory, no new licence claimed.
7. **Root-commit date**: dated at the earliest source event (recommendation) vs a fixed date.
8. **Tiki scraping**: acceptable to the site owner? (ask before M2).
9. **Mail size**: whether both Maildirs' raw messages fit GitHub's budget (measured at M1); companion repository only if not.

---

## Appendix A — Glossary

event · unit (a file or line range) · citation (`<path>@<Source-Id>:L<a>-<b>`) · snapshot (`snapshot/<ts>` tag) · note · attestation · coverage — as defined above.

## Appendix B — Source documents

`doc/research/REPORT.md` (architecture research, prototype results, Codex comparison), `data-survey.md` (local data inventory, parsing quirks), `domain-data-handling.md` (verified online sources), `retrieval-sota.md`, `embeddings-landscape.md`, `agent-harness.md`, `codex-architecture-research.md`, `proto-notes.md`; `doc/future/librarian-service.md` (deferred design); `doc/decisions/` (adjudications).
