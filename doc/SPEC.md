# jbomo'i — functional specification

Status: **draft v0.1, 2026-08-26**. Authors: Fable (spec), the human partner (adjudication). Implementer: Codex. This document supersedes `doc/research/REPORT.md` wherever the two differ; the research report remains the evidence base and the record of why.

Conventions: MUST / SHOULD / MAY as in RFC 2119. "Corpus" means the Lojban historical record as materialised on the `main` branch. "Service" means the long-running librarian process. Paths are relative to the `tools` checkout unless prefixed `main:`.

---

## 1. Purpose, scope, principles

### 1.1 Purpose

jbomo'i is a research librarian for the Lojban community's historical record. Given a possibly vague question — *why is it like that? how did that happen? who decided, and was it ever ratified? what are the competing views?* — it searches the record iteratively, reads the evidence, and answers with verbatim, verifiable citations, presenting all documented positions where a question is unsettled. Discord is the first interface; a web application shows full reports and cited sources; the same capability is exposed over MCP to other agents.

### 1.2 Non-goals (v1)

- Being an authority on Lojban. The librarian reports what the record says and who said it; it does not rule.
- Ambient reading of Discord channels or any live chat; the bot answers when addressed.
- Automated knowledge-graph extraction over the corpus.
- Real-time ingestion. The corpus is updated in batches (§4.5).
- Hosting the corpus for the general public as a product. Public access is a policy decision (§10).

### 1.3 Principles (normative)

1. **Evidence first.** Every factual claim in an answer cites a unit of the corpus by stable id; every quotation is verbatim and mechanically verified before delivery.
2. **The corpus is a repository.** The record is materialised as files under git with one commit per source event, so exact search, neighbourhood reading, history, as-of, diff and authorship are all provided by `grep` and `git` (§2, §3).
3. **Lexical first, semantic second.** Exact/lexical search is the primary retrieval tool; semantic search is a separate, optional tool for vague questions (§5).
4. **Mechanistic units.** Retrieval units and boundaries are computed by rules from the source (§5.1). Nothing about the corpus requires human curation except the small alias registry (§3.7), and even that is seeded automatically.
5. **Time everywhere.** Every unit carries source time; versioned sources carry validity; answers distinguish what was said, when, and what was in force when (§3.1, §6.4).
6. **Conclusions are outputs.** Ratification status, timelines and "what changed" conclusions are the results of research, memoised as notes with provenance and coverage (§3.8), never precomputed tables.
7. **Coverage-aware negatives.** "No decision was found in *these* sources through *this* date" is a valid answer; "this was never ratified" is not, unless a source says so.
8. **Corpus text is untrusted input.** Everything read from the corpus is data, delimited as such; no instruction in it is followed (§6.6).
9. **Cost is visible.** Every job records tokens, cache hits, tool calls, latency and dollars (§6.7).
10. **Rebuildable, extensible.** Everything derived — the corpus projection, indexes, derived documents — is a deterministic function of immutable raw archives plus a `tools` commit, and the tools to rebuild it live in this repository (§2.3, §4).

---

## 2. Repository model

### 2.1 Branches

The repository has two branches with **no shared history**:

| branch | content | default checkout |
|---|---|---|
| `main` | the corpus projection: data files and their event history (§3) | no |
| `tools` | tooling, service code, documentation, the exchange, CI | **yes** |

No file exists on both branches. `tools` MUST never be merged into `main` or vice versa.

### 2.2 Working layout

A developer or CI checkout is the `tools` branch at the repository root. The corpus is a **git worktree** of `main` at `./corpus/` (gitignored), created on demand by `jbomohi corpus init` (`git worktree add corpus main`, or `--orphan main` if `main` does not yet exist locally). All tools resolve the corpus path from configuration (`JBOMOHI_CORPUS`, default `./corpus`). Nothing on `tools` assumes `main` is checked out anywhere else.

Local, untracked state: `./corpus/` (worktree), `./.exchange/` (message spool, §9), `./tmp/` (scratch), `./.venv/`, and the index cache (§5.4).

### 2.3 Raw archive tier

Raw source material — downloaded dumps, zips, API responses, scraped pages, database dumps — is **never committed to git**. It lives in an *archive* directory (`JBOMOHI_ARCHIVE`, default `~/lojban/archive`) as immutable, content-addressed objects. For every object the tools write a manifest: `{source, kind, url_or_origin, fetched_at, sha256, bytes, coverage: {from, to, counts}, notes}`. Manifests (small JSON/TOML) ARE tracked, under `main:_meta/archive/`, so that anyone with access to the same raw objects can reproduce `main`. Whether raw objects are mirrored somewhere shared (a GitHub Release, an object-store bucket) is Open Question §10.4; private database dumps are never mirrored.

### 2.4 Rebuild contract

`main` is a deterministic function of (archive contents, `tools` commit). Two invocations of `jbomohi build` on the same inputs MUST produce identical tree hashes at every commit (commit hashes will also match if author/committer identities and dates are derived from the sources, which they are; the build MUST NOT read the wall clock into any committed content or commit metadata). `jbomohi update` appends new events without rewriting history. A full `build` (re-linearisation) is permitted at any time because nothing cites commit hashes (§3.1.4).

### 2.5 Commit conventions on `main`

One commit per **source event**. Events are: a wiki revision; a Tiki page version; a mail message; an IRC day file (import or amendment); a dictionary definition version (create/edit/delete); a dictionary comment; a daily vote batch; a CLL edition rendering; a note; a `who` registry change; a manifest/coverage update. Batching two events into one commit is forbidden except for the vote batch.

- `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL`: the source author (§3 per source). Where the source has no email, a synthetic one of the form `<user>@<source-host>` is used (e.g. `Gleki@mw.lojban.org`).
- `GIT_AUTHOR_DATE` = `GIT_COMMITTER_DATE` = the source event time, in UTC where the source is unambiguous; otherwise the source's local time with the trailer `Time-Confidence:` set (`exact`, `tz-unknown`, `window`).
- `GIT_COMMITTER_NAME/EMAIL`: `jbomohi <jbomohi@lojban.org>` (placeholder; §10.2).
- Subject line: `<source>: <summary ≤ 72 chars>` (e.g. `wiki: BPFK Section: gadri (rev 108932) fix typo`, `mail/lojban: Re: [lojban] xorlo podcast`, `dict: kau en#12345 v3`).
- Trailers (all `Key: value`, one per line, at the end of the body):
  - `Source: <source name>` (`wiki`, `tiki`, `mail/<list>`, `irc/<channel>`, `dict`, `cll`, `notes`, `who`, `meta`)
  - `Source-Id: <stable id>` — the citation anchor for this event (§3.1.4)
  - `Event: created|edited|deleted|moved|comment|vote-batch|import|render|note|registry|manifest`
  - `Event-Window: <iso-date>..<iso-date>` when the event time is only bounded (e.g. between two database dumps)
  - `Time-Confidence: exact|tz-unknown|window`
  - source-specific trailers (`Page-Id`, `Parent-Rev`, `Message-Id`, `In-Reply-To`, `Thread`, `Definition-Id`, `Version`, `Edition`, …) as listed per source in §3.

### 2.6 Ordering, back-fill, as-of

- A full `build` emits events in strict chronological order across all sources (merge by event time; ties broken by source name then id).
- `update` appends. A newly added source or a late-arriving batch may therefore appear at the tip with old dates. This is acceptable: `git log --since/--until/--author` filter on committer date, which equals source time; **per-file as-of** (`git log -1 --before=<date> -- <path>` then `git show <commit>:<path>`) is always correct because each event commit writes the file's state at that event.
- **Whole-tree as-of** is only guaranteed at snapshot tags. `snapshot/<UTC timestamp>` is an annotated tag created after every `build`/`update`; its message carries the coverage summary (§3.9).
- Citations never use commit hashes (§3.1.4), so a re-linearising `build` never invalidates a citation.

### 2.7 Size budget

`main` holds text only: no media, no PDFs, no rendered HTML. Expected initial size ≈ 1 GB of history (≈ 640 MB of raw mail, plus wiki history, IRC, dictionary). The Maildir is stored uncompressed because git deltas RFC 822 text well; if the repository exceeds 2 GB the mail raw tier moves to a separate repository (Open Question §10.4).

---

## 3. Corpus projection (`main`)

### 3.1 Cross-cutting rules

#### 3.1.1 Top-level layout

```
_meta/          manifests, coverage, csv indexes, schema version (§3.9)
wiki/           MediaWiki pages, one file per page, raw wikitext (§3.2)
tiki/           pre-2013 Tiki wiki pages (§3.2.5)
mail/<list>/    Maildir + generated thread views per list (§3.3)
irc/<channel>/  one file per channel-day (§3.4)
dict/<word>/    dictionary: definitions, comments, votes (§3.5)
cll/            CLL source (submodule) and per-edition text renderings (§3.6)
who/            alias / identity registry (§3.7)
notes/          research notes written by the librarian or humans (§3.8)
map/            the corpus map read by the librarian (§3.10)
README.md       generated: layout, coverage, citation grammar
```

#### 3.1.2 Text encoding and fidelity

All generated text files are UTF-8, LF line endings, no BOM. Raw-fidelity files (wikitext, RFC 822 messages, IRC lines) are stored **byte-exact** as archived except for the documented normalisations per source; a file that is a *rendering* (thread views, CLL edition text) is marked as such in its header line so it is never mistaken for the original.

#### 3.1.3 Metadata split

- **Commit metadata describes the event** (who, when, what changed, source id).
- **File metadata describes the state**, in TOML front matter delimited by `+++` lines for Markdown/TOML-bearing files, and in a single `#`-prefixed header line for plain-text renderings. Raw-fidelity files carry no in-file metadata; their metadata lives in `_meta/` CSV indexes and in commits.
- Flat ledgers are CSV with a header row (RFC 4180 quoting). JSONL is used only where records nest.

#### 3.1.4 Citation ids

The canonical citation is

```
<path>@<Source-Id>:L<start>[-<end>]
```

where `<path>` is the file path on `main`, `<Source-Id>` is the stable source identifier of the *version* of that file being cited (a wiki `revid`, a `Message-ID`, an IRC file date, a dictionary `definition=<id> version=<n>`, a CLL edition tag, a note id), and `L<start>-<end>` are 1-based line numbers in that version. Resolution rule: find the commit whose `Source-Id` trailer matches for that path (or, for append-only files such as IRC days and thread views, the commit at or after that id), and read the lines from that blob. Commit hashes are never part of a citation. The web viewer (§7.2) renders any citation with context, history and diff.

Short forms accepted from the model and expanded by the service: `wiki:<pageid>@<revid>:L…`, `mail:<Message-ID>:L…` (lines within the thread view entry of that message), `irc:<channel>/<date>:L…`, `dict:<word>/<definition-id>@<version>:L…`, `cll:<edition>/<chapter>:L…`, `note:<id>`.

#### 3.1.5 Filename slugs

Titles and words are mapped to filenames by `slug()`: NFC-normalise; keep letters, digits, `'`, `-`, `_`, `,`; replace space with `_`; percent-encode everything else (including `/`, `:`, `.`); a leading `.` or `-` is percent-encoded; the result is limited to 200 bytes (excess is replaced by `-` + 8 hex chars of the SHA-1 of the full title). `slug()` is injective on the set of MediaWiki titles and dictionary words and is documented in `main:README.md`. `_meta/<source>/*.csv` always maps original title/word ↔ path so nothing depends on inverting `slug()`.

### 3.2 Wiki (`wiki/`)

**Source.** `https://mw.lojban.org` via `api.php` (`prop=revisions`, `rvprop=ids|timestamp|user|comment|size|sha1|content`, `rvlimit=max`, `rvdir=newer`), all namespaces except `File` binaries; full revision history. The local current-revision snapshot (`~/git/lojban-wiki`) is used only as a cross-check of page counts. The 66 pages the snapshot could not fetch MUST be retried by title through the API each update and listed in `_meta/wiki/errors.csv` while they fail.

**Layout.** `wiki/<ns>/<slug(title)>.wiki` with `<ns>` ∈ `main, talk, user, user_talk, lojban, lojban_talk, userwiki, userwiki_talk, file, file_talk, template, template_talk, category, category_talk, module, module_talk, mediawiki, mediawiki_talk, help, help_talk`. `File:` pages store the description wikitext only; the media manifest is `_meta/wiki/media.csv` (`pageid,title,url,sha1,size,mime,uploaded,uploader`). Redirect pages are stored as their wikitext (`#REDIRECT [[…]]`).

**File content.** The raw wikitext of the revision, byte-exact. No front matter.

**Events → commits.** One commit per revision, in `revid` order within a page and chronological across pages. Author `<user>` / `<user>@mw.lojban.org`; date = revision timestamp (UTC, `Time-Confidence: exact`). Subject `wiki: <title> (rev <revid>) <comment ≤ 40 chars>`. Trailers `Source: wiki`, `Source-Id: revid=<revid>`, `Page-Id: <pageid>`, `Parent-Rev: <parentid>`, `Event: created|edited`. A page move is a commit with `git mv` and `Event: moved` (`Moved-From:` trailer); a deletion visible through the API is `Event: deleted` removing the file. Suppressed/oversighted revisions are recorded in `_meta/wiki/gaps.csv`, never reconstructed.

**Indexes.** `_meta/wiki/pages.csv` (`pageid,ns,title,path,is_redirect,first_rev,last_rev,revisions`), `_meta/wiki/revisions.csv` (`revid,pageid,parentid,timestamp,user,size,sha1,comment`).

**Quirks to handle.** The 2014 bulk "Text replace" edits are legitimate revisions and are kept, but `map/corpus.md` warns the librarian that they are noise when reading history. Talk-page threads are not reconstructed at projection time (they are wikitext); the index (§5.1) segments them by signature/date lines.

#### 3.2.5 Tiki (`tiki/`)

**Source.** `https://tiki.lojban.org` — `tiki-index.php?page=…` and `tiki-pagehistory.php?page=…` (HTML scrape; rate-limited ≤ 1 request/s). Coverage 2001–~2015; best-effort; phase 5 (§9). Layout `tiki/<slug(page)>.tiki` (Tiki markup, byte-exact after HTML-unescaping the `<textarea>`/history payload), one commit per version with `Source: tiki`, `Source-Id: tiki=<page>@<version>`, author from the history table, `Time-Confidence: exact`. `_meta/tiki/pages.csv`, `versions.csv`, and a `migrated_to` column linking to the MediaWiki page where the import template (`{{BPFK Section from tiki|…}}`) or an identical title establishes the correspondence.

### 3.3 Mail (`mail/<list>/`)

**Sources.** (a) The local `lojban-list` Maildir (`~/lojban/disc/mail/maildir` and the `b2024` superset — both are ingested; dedupe handles the overlap). (b) `https://mail.lojban.org/lists/<list>/` MHonArc archives for the other public lists (`announce, bpfk, bpfk-announce, dracyselkei, jbofongri, jboske, jbosnu, jbovlaste, lbck, lojban-beginners, lojban-de, lojban-es, lojban-fr, lojban-list-old, old_lojban-list, lojban_story, pod, wikichanges, wikidiscuss, wikineurotic`), scraped at ≤ 1 request/s, reconstructing RFC 822 messages from each `msgNNNNN.html` (headers from the `<!--X-…-->` comments and the rendered header block; body from the rendered text; such messages carry `X-Jbomohi-Manifestation: mhonarc` so they are never mistaken for originals). (c) `old_lojban-list/` raw RFC 822 files (1998–2003) where present. `llg-members` and `llg-board` require credentials (Open Question §10.6).

**Layout.**

```
mail/<list>/cur/<unixtime>.<sha1(message-id)[:16]>.jbomohi:2,S   raw RFC 822, byte-exact
mail/<list>/new/  mail/<list>/tmp/                                 present, always empty
mail/<list>/threads/<YYYY>/<thread-key>.txt                        generated thread view
```

The Maildir is a real Maildir readable by mutt/notmuch/mu. Files are created directly in `cur/` with the Seen flag and mode `0444`; readers must be pointed at a copy or a separate worktree if they need to write flags. `<thread-key>` = first 12 hex of SHA-1 of the root Message-ID + `-` + `slug(normalised subject)` (≤ 60 chars).

**Thread view format** (rendering; line 1 is a header):

```
# mail/<list> thread <thread-key> | root <Message-ID> | <n> messages | rendered by jbomohi
=== 1 | 2004-12-25T15:02:11Z | Robin Lee Powell <rlpowell@digitalkingdom.org> | <20041225150211.GA1234@chain.digitalkingdom.org> | mail/lojban/cur/1104... 
<decoded plain-text body, verbatim, quoted lines kept with their '>' prefixes>
=== 2 | ...
```

Messages appear in JWZ thread order (References/In-Reply-To; subject fallback for orphans). Bodies are the `text/plain` part decoded to UTF-8 (HTML-only messages are converted with a deterministic HTML→text rule and marked `[html]` in the entry header). Quotes and signatures are **kept** in the view (fidelity); they are stripped at **index** time (§5.1).

**Events → commits.** One commit per unique message (Message-ID normalised: trim, lowercase the domain part, strip surrounding `<>`; messages lacking a Message-ID get `sha1(raw)@jbomohi.invalid`). Author = `From:` (display name and address as written — see §10.3 on pseudonymisation); date = `Date:` header parsed to UTC (`Time-Confidence: exact`); if unparsable, the first `Received:` date (`tz-unknown`), else the archive position (`window`). Subject `mail/<list>: <Subject ≤ 60 chars>`; trailers `Source: mail/<list>`, `Source-Id: <Message-ID>`, `Message-Id:` (same), `In-Reply-To:`, `Thread: <thread-key>`, `Event: created`. The same commit appends the message to its thread view (creating it for a root) — so the thread view's history is the thread's timeline.

**Indexes.** `_meta/mail/<list>/messages.csv` (`message_id,date,from,subject,thread_key,file,manifestation,duplicates`), `threads.csv` (`thread_key,root_message_id,subject,first,last,count`), `duplicates.csv`.

### 3.4 IRC (`irc/<channel>/`)

**Sources.** `https://lojban.org/irclogs/<channel>/<YYYY_MM>/<YYYY_MM_DD>.txt` for `lojban`, `jbosnu`, `ckule` (plus the `2000_all`, `2002_middle`, `2002_12` directories), and the local `all_logs.txt` for cross-checking. The first 51,004 lines of the local `all_logs.txt` are `#jbosnu`, not `#lojban`, and MUST be assigned accordingly.

**Layout.** `irc/<channel>/<YYYY>/<YYYY-MM-DD>.txt`, one file per channel-day. Line 1 is a header: `# irc #<channel> <date> tz=<±HHMM|unknown> source=<archive path> format=<iso|legacy|bracket|irssi>`. Following lines are normalised to exactly one of:

```
HH:MM:SS <nick> message
HH:MM:SS * nick action
HH:MM:SS -- system/topic/join text
```

Timestamps are kept in the log's own timezone (recorded in the header), never converted; seconds are `00` where the source has none. Message text is byte-exact except that mIRC colour/format control codes are removed and NUL bytes dropped. Bridged relays (`<xxxx_> <la cenzis>: …`) are kept verbatim; the `who/` registry (§3.7) documents the relay patterns. The 2015 irssi block has its dates reconstructed from `--- Day changed` markers; the 2000 bracket format takes its date from the file name.

**Events → commits.** One commit per day file, `Event: import` (or `edited` when an archive day file changes), author `irc-logger <irclogs@lojban.org>`, date = last message time of that day in the log's timezone (`Time-Confidence: exact` when tz known, else `tz-unknown`). Subject `irc/<channel>: <date> (<n> lines)`. Trailers `Source: irc/<channel>`, `Source-Id: <date>`.

**Indexes.** `_meta/irc/<channel>/days.csv` (`date,lines,messages,nicks,tz,format,source`).

### 3.5 Dictionary (`dict/<word>/`)

**Sources.** Initial replay from full database dumps of jbovlaste and Lensisku (schemas unknown until received — Open Question §10.7; the loader is written against the dump, not the API). Ongoing: Lensisku's public changes feed and definition version API where available, else periodic full dumps diffed by primary key. jbovlaste (read-only) is scraped only for comment/etymology pages that did not migrate.

**Layout.**

```
dict/<slug(word)>/word.toml            word-level state
dict/<slug(word)>/<lang>-<definition-id>.md   one file per definition (front matter + text)
dict/<slug(word)>/comments.md          append-only, one section per comment
dict/<slug(word)>/votes.csv            header: definition_id,voter,date,value
```

`word.toml`: `word, type (gismu|cmavo|lujvo|fu'ivla|cmevla|experimental-…), rafsi = [...], selmaho, created, creator, source_ids = {jbovlaste = …, lensisku = …}`.
Definition file front matter (`+++`): `id, word, lang, author, created, updated, version, score, status (current|deleted|superseded), source, keywords = [{word, sense, place}], examples = [...]`; body: the definition text as written, then `## Notes` with the definition notes verbatim.
`comments.md` sections: `## <ISO date> — <author> (comment <id>, on definition <id>)` followed by the comment text verbatim; replies are indented with `>`-free nesting recorded in a trailing `(in reply to <id>)`.

**Events → commits.** One commit per definition version (`Event: created|edited|deleted`; author = the definition's user, `<user>@jbovlaste.lojban.org`; date = the version timestamp or, when the dump only shows a state change between two dumps, the later dump's date with `Event-Window` and `Time-Confidence: window`); one commit per comment (`Event: comment`); one commit per day of votes (`Event: vote-batch`, author `jbomohi`), which also updates `score` in the affected definition files. Trailers `Source: dict`, `Source-Id: definition=<id> version=<n>` (or `comment=<id>`, `votes=<date>`), `Definition-Id`, `Version`, `Word`.

**Coverage boundary.** `_meta/dict/coverage.toml` records from which date version history is event-accurate, which range is dump-window-accurate, and which definitions have only a creation date. `map/corpus.md` states this so the librarian never implies completeness.

**Indexes.** `_meta/dict/words.csv`, `definitions.csv` (`definition_id,word,lang,author,created,updated,versions,score,status,path`).

### 3.6 CLL (`cll/`)

**Sources.** `https://github.com/lojban/cll` (upstream) and/or `int19h/cll` (fork, includes 1.3.x) — Open Question §10.5 — as a **git submodule** at `cll/src` so that upstream commit ids, tags and full history are preserved verbatim (a subtree would rewrite them and lose tags). Plus per-edition **plain-text renderings** tracked on `main` under `cll/editions/<edition>/`:

| edition id | source | notes |
|---|---|---|
| `1997-online-draft` | first import commit `8048799d` (342 HTML sections) | the pre-final online draft, not the printed book |
| `1.0-errata-2014` | `gh-pages` @ `dabe6154` | maintainers' reconstruction of printed 1.0 + errata; a claim, not diff-verified |
| `1.1-2016`, `1.1-2018`, `1.1-2019` | tags `v1.1-<date>-html` | official LLG 1.1 |
| `1.2.<n>` | `geklojban-1.2.*` tags/branches | unofficial |
| `1.3.2` | tag `v1.3.2` | this fork; what jbotci `cukta` serves |

The printed 1.0 is not reconstructible from the repository; if a scan/OCR is ever acquired it becomes edition `1.0-print`.

**Rendering.** `cll/editions/<edition>/<ch>-<slug>.txt`, one file per chapter, line 1 header `# cll <edition> chapter <n> <title> | rendered from <source ref> by jbomohi <renderer version>`; section headings rendered as `## <n>.<m> <title>` (numbers stable across editions), examples as `[Example <n>.<m>]` lines, DocBook/HTML markup dropped deterministically (Lojban text and glosses preserved line-per-line). One commit per (edition) rendering, `Event: render`, author `jbomohi`, date = the edition's publication/tag date, `Source-Id: cll=<edition>`. The renderer version is part of the header so re-rendering is a visible event.

**Alignment.** `_meta/cll/alignment.csv` (`edition_a,section_a,edition_b,section_b,relation (exact|edited|moved|split|merged|added|deleted),method`) generated by chapter/section-number matching plus text similarity; used by the `diff_edition` tool (§6.2).

### 3.7 Identity registry (`who/`)

`who/people.toml` — `[[person]]` entries: `id` (slug), `name`, `aliases = [{kind = "irc"|"email"|"wiki"|"discord"|"telegram"|"jbovlaste"|"other", value, from?, to?, evidence?}]`, `roles = [{body = "LLG"|"BPFK"|"LFK"|…, title, from, to, evidence}]`, `notes`. `who/relays.toml` documents bridge-nick patterns (`<xxxx_> <name>: …` → speaker `name` via relay `xxxx_`).

Seeded by `jbomohi who propose` (LLM pass over signatures, "X (nick)" mentions, wiki user pages, mail From lines) into `who/proposed/*.toml`; promotion to `people.toml` is a human or Fable decision recorded as an ordinary commit (`Source: who`, `Event: registry`). The librarian reads `who/` as a document and via the `who` tool; it is never used to rewrite source text.

### 3.8 Notes (`notes/`)

`notes/<YYYY>/<YYYYMMDD>-<slug>.md`, front matter:

```toml
+++
id = "note:20260826-xorlo-adoption"
created = 2026-08-26T18:40:00Z
author = "jbomohi/claude-opus-5"        # or a person
status = "draft" | "verified" | "superseded"
supersedes = ""                         # note id
questions = ["Why was xorlo adopted?", "What changed about lo/le/la in xorlo?", "…"]
terms = ["xorlo", "gadri", "zasni gafyfantymanri", "BPFK"]
sources = ["wiki/main/BPFK_Section%3A_gadri.wiki@revid=…:L12-30", "mail/lojban/threads/2004/…:L1-40", …]
coverage = { sources = ["wiki", "mail/lojban", "irc/lojban"], from = "1989-12-07", to = "2026-06-08", snapshot = "snapshot/20260826T170000Z" }
confidence = "high" | "medium" | "low"
+++
```

Body: `## Conclusion` (≤ 300 words), `## Positions` (attributed, dated), `## Ratified` (acts found, with citations, or "none found within coverage"), `## Open`, `## Trace` (the searches that mattered). The service writes a note after every research-class answer (§6.5) as one commit (`Source: notes`, `Event: note`, author `jbomohi <…>`, date = creation time — the only commits whose time is not a source time). Humans edit notes by ordinary commits; corrections are new notes with `supersedes`. Notes are indexed like any other unit and additionally by their `questions` and `terms` fields (§5.1); the `read` tool reports `cited_by_notes` for any unit a note cites (§6.2).

### 3.9 `_meta/` and coverage

`_meta/schema.toml` (`projection_schema = 1`, renderer versions), `_meta/archive/*.toml` manifests (§2.3), per-source `coverage.toml` (`from, to, counts, gaps = [...]`, last update), and the CSV indexes listed per source. `jbomohi build`/`update` regenerate `main:README.md` from these. The snapshot tag message is the concatenation of the per-source coverage summaries.

### 3.10 Corpus map (`map/`)

`map/corpus.md` (≤ 5,000 tokens): what each source is, its coverage and known gaps, the citation grammar, the file layouts a searcher needs, the status vocabulary the librarian should recognise (`baseline 1997 (CLL 1.0)`, `Official Baseline Statement 2002/2003`, `BPFK checkpoint`, `BPFK vote not checkpointed`, `zasni gafyfantymanri (2007)`, `LFK`, `CLL 1.1 errata`, `unofficial 1.2.x`, `proposal`, `experimental cmavo`), the major bodies and roles, and the top entries of `who/`. Generated skeleton + hand-maintained prose; loaded verbatim into the service's cached system prompt.

---

## 4. Tools (`tools` branch)

### 4.1 Language and layout

Python ≥ 3.13 managed with `uv`; one package `jbomohi_tools` exposing the CLI `jbomohi` (`uv run jbomohi …`). No third-party dependency without a reason recorded in `pyproject.toml` comments. Directory layout:

```
tools/exchange/        the model-to-model message exchange (§9)
tools/jbomohi_tools/   the CLI package: archive/, project/, index/, bench/, who/, notes/
tools/tests/           unit + determinism tests
service/               the librarian service (§6) — language per §10.1
doc/                   this spec, research, decisions
.github/workflows/     CI (§4.6)
```

### 4.2 CLI

```
jbomohi corpus init|status                      create/inspect the ./corpus worktree
jbomohi archive fetch <source> [--since …]      download into the archive tier, write manifests
jbomohi archive verify                          check sha256 of every manifest
jbomohi build [--sources …] [--until DATE]      full deterministic rebuild of main from the archive
jbomohi update [<source> …]                     append new events; tag snapshot/<ts>
jbomohi verify                                  invariants on main (§4.4)
jbomohi index build|update [--snapshot TAG]     build the lexical (and optional dense) index (§5)
jbomohi bench retrieval|questions               evaluation harness (§8)
jbomohi who propose|promote                     identity registry (§3.7)
jbomohi notes lint                              front-matter and citation validity of notes/
jbomohi cll render <edition>                    per-edition text rendering (§3.6)
```

Every command is idempotent and resumable; network commands are rate-limited per source (default ≤ 1 request/s, configurable) and retry with backoff; nothing writes outside the archive, the corpus worktree, and the index cache.

### 4.3 Per-source fetchers

Each source has a module with `fetch(archive, since) -> manifests` and `project(archive, corpus, state) -> events`. Fetchers write only to the archive; projectors write only to the corpus worktree and commit through a single `commit_event(event)` helper that enforces §2.5. Projectors are pure functions of archive objects: they MUST NOT call the network.

### 4.4 Invariants (`jbomohi verify`)

- every commit on `main` has `Source`, `Source-Id`, `Event` trailers and a `Time-Confidence`;
- `Source-Id` is unique per `(Source, path)`; `_meta/*.csv` rows match files on disk;
- Maildirs contain only `cur/` files named per §3.3 with mode `0444`; every `messages.csv` row has a file and a thread-view entry;
- IRC files parse line-by-line under the §3.4 grammar; day files are in the right year directory;
- dictionary front matter validates; `votes.csv` headers present;
- notes front matter validates and every `sources` citation resolves (§3.1.4);
- rebuild determinism (in CI on a sample): building the last N days twice yields identical trees.

### 4.5 Update cadence

Weekly scheduled `update` for public sources (wiki, IRC, MHonArc lists, Lensisku feed); manual `update dict --dump <file>` when a database dump arrives; `build` when a new source is added or a projector's rendering rule changes (renderer version bump). Every run ends with `verify` and a snapshot tag; a failed `verify` MUST NOT push.

### 4.6 CI (`.github/workflows/`)

- `check.yml` (push/PR on `tools`): unit tests, exchange tests (unbound and bound), lint, determinism sample test.
- `update.yml` (schedule + `workflow_dispatch`): checks out `tools`, adds the `main` worktree, runs `archive fetch` for public sources into a job-local archive (or a cached one), `update`, `verify`, pushes `main` and the tag. Secrets: Lensisku token if needed. The 6-hour job limit means the initial `build` is run locally; CI does increments only. Private dumps never enter CI.

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

## 9. Collaboration: exchange, roles, work tracking

- Roles: the human partner adjudicates; **Fable directs and reviews**; **Codex implements**. Codex works on branches off `tools` and opens pull requests; Fable reviews against this spec; the human merges (or delegates merge to Fable per PR).
- Work items are GitHub issues on the project repository (§10.2); an issue is the durable record of scope, acceptance criteria and outcome. The exchange is coordination, never the sole record.
- The message exchange (`tools/exchange/`, protocol `jbomohi-mail/v1`) is the channel between model sessions and the human: sessions self-register (`join`), messages are addressed and acknowledged, and `status` is run at the start and end of every substantive turn. See `tools/exchange/PROTOCOL.md`.

---

## 10. Open questions (require adjudication; the spec will be amended)

1. **Service language.** Recommendation: build the v1 service in **Python** (reuses the prototype, the Anthropic SDK, `discord.py`, `tantivy-py`; Codex reaches a working Discord bot fastest) behind the tool contracts of §6.2, and revisit Rust (serenity/poise, `rmcp`, native Tantivy) once the contracts are stable. Alternative: Rust from the start, accepting a slower first slice. *Decision needed before M2.*
2. **GitHub repository and CI.** Which remote (`int19h/jbomohi`?), whether `main` (the data) is pushed to GitHub at all (size, licensing), issue tracker location, CI secrets, the committer identity/email used on `main`.
3. **Privacy and access.** (a) Email addresses in Maildir files and commit metadata: keep verbatim (they are already in public archives) or pseudonymise in commit metadata only; (b) whether the citation viewer and search are public or authenticated; (c) a take-down/suppression process for people who ask; (d) whether identity resolution (`who/`) is public-facing in answers.
4. **Archive hosting.** Where raw objects live for reproducibility (local only, a GitHub Release per snapshot, an object-store bucket); whether the mail raw tier stays in `main` or moves to its own repository if size demands.
5. **CLL source.** `lojban/cll` vs `int19h/cll` as the submodule; whether 1.2.x and 1.3.x renderings are included as editions (recommendation: yes, labelled unofficial / fork).
6. **Restricted lists.** Whether `llg-members`/`llg-board` archives can be obtained (credentials or a member's mbox) and whether they may be indexed.
7. **Dictionary dumps.** Schema of the jbovlaste and Lensisku database dumps (unknown until received); whether jbovlaste comment threads migrated to Lensisku (else scrape); whether vote events carry timestamps.
8. **Notes as evidence.** Whether a `verified` note may be cited in an answer as a source in its own right, or answers must always bottom out in primary units (recommendation: notes may be *used* and linked, but claims cite primary units).
9. **Discord deployment.** Target guild(s)/channels, bot identity, DM policy, quotas.
10. **Hosting.** VPS provider/domain for the service and web app; where the corpus worktree and index live in production.
11. **Embedding provider** — deferred by design until the benchmark gate (§5.3); `doc/research/embeddings-landscape.md` is the shortlist.
12. **Update cadence and the initial build** — who runs the multi-hour initial `build` and from which machine; whether Tiki scraping is acceptable to the site owner.

---

## 11. Milestones and acceptance

| # | deliverable | acceptance |
|---|---|---|
| **M0** | `tools` scaffold: `uv` project, CLI skeleton, `corpus init`, exchange ported, CI `check.yml` green, `doc/` in place | tests pass unbound and bound; `jbomohi corpus init` creates the worktree |
| **M1** | Projection for wiki (with history), `lojban-list` mail (local Maildirs), IRC; `build` deterministic; `verify`; snapshot tag; generated `main:README.md` | two builds → identical trees; counts match `doc/research/data-survey.md` within stated tolerances; 20 hand-checked citations resolve to the right text; §4.4 passes |
| **M2** | Lexical index; CLI librarian `jbomohi ask "…"` with the §6.2 tools (minus dict/CLL/notes), verifier, job log | the 28-question set reviewed by Fable and the human; citation resolution ≥ 99%; cost logged |
| **M3** | dict (from dumps), CLL submodule + edition renderings + alignment, `who/`, `notes/`, `map/corpus.md`, `history/show/diff/diff_edition/who/note_*` tools | as-of and diff questions in the question set pass; notes round-trip (written, indexed, surfaced via `search.related_notes` and `read.cited_by_notes`) |
| **M4** | Discord bot, web viewer/reports, job queue, quotas, deployment on the chosen host | end-to-end from a Discord mention to a report permalink within budgets; degraded mode works |
| **M5** | Other lists (MHonArc), Tiki history, `update.yml`, retrieval benchmark, dense index decision, derived documents if gated in, MCP server | benchmark reports per source; the gate decisions recorded in `doc/decisions/` |

Each milestone is an issue with sub-issues; a milestone closes when its acceptance row is demonstrated in a PR description with commands and outputs.

---

## Appendix A — Glossary

- **event**: one source-level change (a revision, a message, a day of IRC, a definition version…); one commit on `main`.
- **unit**: one retrieval item in the index (§5.1).
- **citation**: `<path>@<Source-Id>:L<a>-<b>` (§3.1.4).
- **snapshot**: an annotated tag `snapshot/<ts>` on `main` naming a whole-tree state.
- **note**: a memoised research conclusion with provenance and coverage (§3.8).
- **coverage**: the sources, date ranges and known gaps searched or projected, stated wherever a negative claim is made.

## Appendix B — Source documents

- `doc/research/REPORT.md` — architecture research, prototype results, comparison with the Codex research report.
- `doc/research/data-survey.md` — inventory of local data and formats (authoritative for parsing quirks).
- `doc/research/domain-data-handling.md` — verified availability and formats of every online source.
- `doc/research/retrieval-sota.md`, `embeddings-landscape.md`, `agent-harness.md` — literature and product landscape.
- `doc/research/codex-architecture-research.md` — Codex's independent architecture research (evidence model, evaluation strata, hard negatives).
