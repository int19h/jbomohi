# jbomo'i — functional specification

Status: **draft v0.7, 2026-08-27**. Authors: Fable (spec), the human partner (adjudication). Implementer: Codex. Changes are recorded in `doc/decisions/` (`2026-08-27-scope-and-policies.md`, `2026-08-27-repo-identities-sources.md`, `2026-08-27-dump-schemas.md`, `2026-08-27-mail-sources.md`, `2026-08-27-root-date-licence-loglan.md`, `2026-08-27-loglan-inventory.md`); the deferred v0.1 material (indexes, a librarian service, Discord/web/MCP interfaces) is preserved in `doc/future/librarian-service.md` and is **out of scope**.

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

`main`'s first (root) commit contains the rendered instruction files (`README.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/rules/jbomohi.md`, `.gitignore`) and `_meta/schema.toml`, and is dated **`1970-01-01T00:00:00Z`** (the Unix epoch — git cannot represent earlier dates, so this is the earliest possible date and is distinct from every source event); every later commit is a source event, an instruction/`_meta` refresh, or a contributed note/attestation. The current `main` (a single `.gitignore` commit) is discarded and recreated as an orphan by the first `build`.

### 2.2 Working layout (maintainers)

Checkout `tools` at the repository root; the corpus is a git worktree of `main` at `./corpus/` (gitignored), created by `jbomohi corpus init` (`git worktree add corpus main`, or `--orphan` when `main` does not exist). Tools resolve it from `JBOMOHI_CORPUS` (default `./corpus`). Untracked local state: `./corpus/`, `./.exchange/`, `./tmp/`, `./.venv/`.

### 2.3 Raw archive tier

Downloaded dumps, zips, API responses, scraped pages and database dumps are **never committed** as such. They live in an archive directory (`JBOMOHI_ARCHIVE`, default `~/lojban/archive`) as immutable content-addressed objects with manifests `{source, kind, origin, fetched_at, sha256, bytes, coverage {from, to, counts}, notes}`. Manifests are tracked on `main:_meta/archive/` so the projection is reproducible by anyone with the same objects. Public objects are mirrored as assets of the GitHub Release for each snapshot tag (never checked into the repository); private database dumps are never mirrored — their manifests suffice to prove what was used.

The raw **mail** is the exception to "never committed": the Maildirs on `main` *are* the raw objects (§3.3), because the repository's purpose is to publish them.

### 2.4 Rebuild contract

`main` is a deterministic function of (archive contents, `tools` commit, contributed content harvested from the previous `main` — §3.8). Two `build`s on the same inputs MUST produce identical commit hashes: author/committer identities and dates come from the sources, never from the wall clock (the sole exception is §2.5's `Event: contributed`, whose date is the contribution's own commit date, also not the wall clock). `update` appends events without rewriting history. A full `build` (re-linearisation) is allowed at any time; nothing cites commit hashes (§3.1.4).

### 2.5 Commit conventions on `main`

One commit per **source event**: a wiki revision; a Tiki page version; a mail message; an IRC day file (import or amendment); a dictionary definition version; a dictionary comment; one day of dictionary votes; a CLL edition rendering; a `_meta`/instruction refresh; a contributed note or attestation. Batching several events into one commit is forbidden except for the daily vote batch.

- **Author and committer** are both the **namespaced identity of the person who made the original edit or message**. Each source is its own namespace, so the same username in two sources is two identities (`mw.lojban.org:guskant` ≠ `tiki.lojban.org:guskant` ≠ `jbovlaste.lojban.org:guskant`); relating them is the job of `who/attestations.csv` (§3.7), never of the projection. Git identities are rendered as:

  | namespace | git name | git email |
  |---|---|---|
  | mail (`From:` header) | the display name as written (or the local part if none) | the address as written — the archive's own identifier |
  | `mw.lojban.org:<user>` | `<user>` | `<user>@mw.lojban.org` |
  | `tiki.lojban.org:<user>` | `<user>` | `<user>@tiki.lojban.org` |
  | `jbovlaste.lojban.org:<user>` (jbovlaste and Lensisku are one database and one user namespace — verified in `doc/research/dump-schemas.md` §2.1) | `<user>` | `<user>@jbovlaste.lojban.org` |
  | anonymous / IP-only edits (wiki, Tiki) | `anonymous` | `anonymous@<host>` — contributor IP addresses never enter the repository, in commits or in `_meta/` |
  | IRC day files (many speakers) | `irclogs` | `irclogs@irc.lojban.org` |
  | tool-generated commits (renderings, vote batches, refreshes) | `jbomohi` | `tools@jbomohi.invalid` |
  | contributed notes/attestations | the contributor's own git identity | as configured by the contributor |

  Usernames are used verbatim (case preserved); characters not allowed in an email local part are percent-encoded. The `.invalid` and `*.lojban.org` placeholders are not deliverable addresses and `main:README.md` says so.
- `GIT_AUTHOR_DATE` = `GIT_COMMITTER_DATE` = the source event time. UTC when the source is unambiguous; otherwise the source's own local time, with `Time-Confidence` set.
- **Subject**: `<source>: <summary ≤ 72 chars>` — `wiki: BPFK Section: gadri (rev 108932) fix typo`, `mail/lojban: Re: [lojban] xorlo podcast`, `irc/lojban: 2015-06-20 (412 lines)`, `dict: kau en#12345 v3`, `cll: render 1.1-2019`, `meta: refresh README and coverage`, `notes: xorlo adoption (2004–2007)`.
- **Trailers** (`Key: value`, one per line, at the end of the body):
  - `Source: wiki | tiki | mail/<list> | irc/<channel> | dict | cll | meta | notes | who`
  - `Source-Id: <stable id>` — the citation anchor (§3.1.4)
  - `Event: created | edited | deleted | moved | comment | vote-batch | import | render | refresh | contributed`
  - `Time-Confidence: exact | tz-unknown | window | pre-epoch`
  - `Source-Date: <iso-date>` when the true date could not be represented (`pre-epoch`)
  - `Event-Window: <iso-date>..<iso-date>` when only bounded
  - source-specific: `Page-Id`, `Parent-Rev`, `Message-Id`, `In-Reply-To`, `Thread`, `Definition-Id`, `Version`, `Word`, `Edition`, `Renderer`.

### 2.6 Ordering, back-fill, as-of

- `build` emits events in strict chronological order across sources (merge by event time; ties by source name, then id). Events whose true date is **before 1970** (pre-fork Loglan documents, §3.11) cannot carry their date in git: they are committed immediately after the root commit, in true-date order, with the date clamped to `1970-01-01T00:00:00Z`, `Time-Confidence: pre-epoch`, and the true date in a `Source-Date:` trailer and in `_meta/`.
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

`slug()`: NFC; keep `[A-Za-z0-9'_,-]`; space → `_`; percent-encode everything else (including `/`, `:`, `.`); percent-encode a leading `.`/`-`; cap at 200 bytes (excess → `-` + 8 hex of SHA-1 of the full title). Injective per namespace on MediaWiki titles (most namespaces here are case-sensitive; `User`, `MediaWiki`, `Template`, `Module` and their talk namespaces are first-letter-capitalised, so titles differing only in first-letter case are one page there and two pages in the main namespace) and on dictionary words; `_meta/<source>/*.csv` maps title/word ↔ path so nothing depends on inverting it.

### 3.2 Wiki (`wiki/`)

**Sources.** Initial import from a **full SQL dump** of the MediaWiki database supplied by the site operator (tables and private columns per `doc/research/dump-schemas.md`; passwords/emails/tokens are excluded before the dump leaves the server). Ongoing updates from `https://mw.lojban.org/api.php` — `prop=revisions` with `rvprop=ids|timestamp|user|comment|size|sha1|content`, `rvlimit=max`, `rvdir=newer`, `rvstart` = last imported timestamp, all namespaces except `File` binaries; ≤ 1 request/s, `maxlag=5`. The projector accepts either input for any range and MUST produce identical events from both (a determinism test at M1). The local snapshot (`~/git/lojban-wiki`) is a page-count cross-check only. The 66 pages it could not fetch are retried by title each update and listed in `_meta/wiki/errors.csv` while they fail.

**Layout.** `wiki/<ns>/<slug(title)>.wiki`, `<ns>` ∈ `main, talk, user, user_talk, lojban, lojban_talk, userwiki, userwiki_talk, user_profile, user_profile_talk, file, file_talk, template, template_talk, category, category_talk, module, module_talk, mediawiki, mediawiki_talk, help, help_talk` (ids 0–15, 200–203, 828–829 as reported by `siprop=namespaces`). `File:` pages keep the description wikitext; media are manifest-only in `_meta/wiki/media.csv` (`pageid,title,url,sha1,size,mime,uploaded,uploader`). Redirects are stored as their wikitext.

**Content.** The revision's raw wikitext, byte-exact. No front matter.

**Events.** One commit per revision, page-internal order by `revid`, global order chronological. Author `<user>` / `<user>@mw.lojban.org`; date = revision timestamp (UTC, `exact`). Subject `wiki: <title> (rev <revid>) <comment ≤ 40>`. Trailers `Source: wiki`, `Source-Id: revid=<revid>`, `Page-Id`, `Parent-Rev`, `Event: created|edited|moved|deleted` (`Moved-From:` on moves; deletions only where the API exposes them). Revision-deletion bits (`rev_deleted`) are honoured by the projector, not the dump: suppressed text is never written, suppressed usernames become `anonymous`, and such revisions are listed in `_meta/wiki/gaps.csv`. The dump-specific joins (`revision_actor_temp`, `revision_comment_temp`, MCR `slots → content → text`, `old_flags` decoding, external-store clusters) are specified in `doc/research/dump-schemas.md` §3; the loader MUST produce the same events from the dump and from the API for any overlapping range.

**Indexes.** `_meta/wiki/pages.csv` (`pageid,ns,title,path,is_redirect,first_rev,last_rev,revisions`), `revisions.csv` (`revid,pageid,parentid,timestamp,user,size,sha1,comment`).

**Quirks.** The 2014 bulk "Text replace" revisions are kept; `main:AGENTS.md` warns that they are noise when reading history. Talk pages are wikitext; no thread reconstruction at projection time.

#### 3.2.5 Tiki (`tiki/`)

Initial and only import from a **SQL dump** of the Tiki database (`doc/research/dump-schemas.md` §4; the dump must be taken with `--default-character-set=latin1 --skip-set-charset --hex-blob` because `tiki_history.data` is a blob while `tiki_pages.data` is text); the Tiki is read-only, so there is no ongoing update path, and HTML scraping of `tiki-pagehistory.php` is only the fallback if no dump is obtainable. Coverage ≈ 2001–2015 (M2).

Page versions: `tiki_history` holds versions 1..N−1 and `tiki_pages` holds the current version N; `version` numbers are neither dense nor monotonic, so events are ordered by `lastModif` (unix UTC, `exact`) and the `Source-Id` keeps the source's own version number. Forums: `tiki_comments` with `objectType='forum'` are projected as `tiki/forums/<forum-slug>/<topic-threadId>.txt` (rendering; one commit per post in `commentDate` order; nesting from `in_reply_to`; `Source-Id: tiki=forum/<threadId>`). The **WikiDiscuss** forum (id 1, ≈5.6k posts) is projected; the **mailing-list mirror** forum (id 5) is a duplicate view of `mail/` and is skipped, recorded in `_meta/tiki/coverage.toml`. Per-page comments (`objectType='wiki page'`) go to `tiki/talk/<slug(page)>.txt`, one commit per comment (`Source-Id: tiki=comment/<threadId>`). `tiki_actionlog` supplies rename/delete events. Display names come from `tiki_user_preferences.realName`; the literal login `Anonymous` and IP-only rows map to `anonymous@tiki.lojban.org`. `tiki/<slug(page)>.tiki` (Tiki markup, HTML-unescaped, otherwise byte-exact), one commit per version (`Source: tiki`, `Source-Id: tiki=<page>@<version>`, author from the history table, `exact`). `_meta/tiki/pages.csv`, `versions.csv`, with a `migrated_to` column naming the MediaWiki page where an import template (`{{BPFK Section from tiki|…}}`) or identical title establishes the correspondence.

### 3.3 Mail (`mail/<list>/`)

**Sources** (inventory and verification in `doc/research/mail-sources-inventory.md`; the whole corpus reduces to four physical archives, everything else — Google Groups, Lensisku's archive, Wayback/Archive-Team Yahoo captures, `lojban-list-old` — is a derived view of them and is never scraped):

- **Tier 1, bulk download** (no scraping): `https://mail.lojban.org/lists-plain/<list>/<list>.maildir.zip` — raw RFC 822 Maildirs, regenerated by the server — for `lojban-list` (107,669 files, 1989-12 → 2025-08) and `lojban-beginners, bpfk, jbovlaste, lojban-de, lojban-es, lojban-fr, lbck, lojban-announcements, wikichanges, wikidiscuss, wikineurotic`; `lists/old_lojban-list/1…19674` (the complete onelist/eGroups/Yahoo-era raw export, 1998-11 → 2003-05); `lists/jbosnu_raw.zip`; `www.lojban.org/files/lojban-list/lojban-*.gz` (native mbox, 1989-12 → 1998-04). The local Maildirs under `~/lojban/disc/mail` are earlier copies of the first zip and are superseded by it.
- **Tier 2, MHonArc crawl** only for the lists with no `lists-plain` counterpart: `announce, bpfk-announce, dracyselkei, jbofongri, jboske, jbosnu, lojban_story, pod` (≈5.7k pages). Crawl `msgNNNNN.html` **by number from 0 until 404** (indexes are incomplete), ≤ 2 requests/s; each page is reconstructed into an RFC 822 message (headers from the `<!--X-Message-Id/X-Reference-->` comments and the rendered header block, body from the rendered text) and carries `X-Jbomohi-Manifestation: mhonarc`.
- **Tier 3, gap-fill**: `lists/lojban-beginners/msg*.html` (20,910 pages; its Maildir has only 16,623 files and neither is a superset — take the union); `lists/lojban-list-old/` only for Message-IDs absent from Tier 1; `files/lojban-list/*.ZIP` (headerless eGroups text, 1998-10 → 2000-01) only for months missing from `old_lojban-list`.
- **Excluded**: `llg-board`, `llg-members`, `special*` (HTTP 401 — restricted); `jbovlaste-admin` (≈80k automated dictionary-change notifications; excluded — decided 2026-08-27 — and listed in coverage as available).

**Deduplication** (the Tier 1 Maildir is ≈45% duplicate copies in the pre-1995 era, up to five copies per message): primary key = normalised Message-ID (strip `<>`, trim, HTML-unescape, NFC, case-fold); among copies keep the one with the most headers, ranked `lists-plain Maildir > old_lojban-list / jbosnu_raw > files mbox > MHonArc page > files ZIP text`, and record the losers in `_meta/mail/<list>/duplicates.csv` with their provenance; fallback key when no Message-ID exists = hash of (normalised subject, from local-part, date to the minute, first 200 body characters); never dedupe on subject alone. Threading uses `References` (all, in order) with `In-Reply-To` as fallback. Spam that reached a list is kept and flagged (`_meta/mail/<list>/messages.csv` column `spam_suspect`), never dropped.

**Layout.**

```
mail/<list>/cur/<unixtime>.<sha1(message-id)[:16]>.jbomohi:2,S   raw RFC 822, byte-exact, mode 0444
mail/<list>/new/  mail/<list>/tmp/                                 present, empty (.keep)
mail/<list>/threads/<YYYY>/<thread-key>.txt                        rendered thread view
```

A real Maildir readable by mutt/notmuch/mu; files are born in `cur/` with the Seen flag so readers do not rename them. `<thread-key>` = 12 hex of SHA-1(root Message-ID) + `-` + `slug(normalised subject)` ≤ 60 chars.

**Thread view.** Line 1: `# mail/<list> thread <thread-key> | root <Message-ID> | <n> messages | rendered by jbomohi <renderer>`; then per message `=== <n> | <ISO date> | <From> | <Message-ID> | <maildir file>` followed by the decoded `text/plain` body verbatim (HTML-only messages converted deterministically and marked `[html]` in the entry line); messages in JWZ order (References/In-Reply-To; subject fallback for orphans). Quotes and signatures are kept.

**Events.** One commit per unique message (Message-ID normalised as above; missing → `sha1(raw)@jbomohi.invalid`). Author = `From:` verbatim; date = `Date:` → UTC (`exact`), else first `Received:` (`tz-unknown`), else archive order (`window`). Subject `mail/<list>: <Subject ≤ 60>`; trailers `Source: mail/<list>`, `Source-Id: <Message-ID>`, `Message-Id`, `In-Reply-To`, `Thread: <key>`, `Event: created`. The same commit appends the message to its thread view.

**Indexes.** `_meta/mail/<list>/messages.csv` (`message_id,date,from,subject,thread_key,file,manifestation,duplicate_of`), `threads.csv`, `duplicates.csv`.

### 3.4 IRC (`irc/<channel>/`)

**Sources.** `https://lojban.org/irclogs/<channel>/<YYYY_MM>/<YYYY_MM_DD>.txt` for `lojban`, `jbosnu`, `ckule` (plus `2000_all`, `2002_middle`, `2002_12`); the local `all_logs.txt` only as a cross-check (its first 51,004 lines are `#jbosnu`, not `#lojban`).

**Layout.** `irc/<channel>/<YYYY>/<YYYY-MM-DD>.txt`; line 1 `# irc #<channel> <date> tz=<±HHMM|unknown> source=<archive path> format=<iso|legacy|bracket|irssi>`; then lines in exactly one of the forms `HH:MM:SS <nick> message`, `HH:MM:SS * nick action`, `HH:MM:SS -- system/topic text`. Timestamps stay in the log's own timezone (in the header), seconds `00` where absent; text byte-exact except mIRC control codes and NULs removed. Bridged relays (`<xxxx_> <la cenzis>: …`) are kept verbatim (`who/relays.toml` documents the patterns). Irssi-block dates come from `--- Day changed` markers; the 2000 bracket format takes its date from the file name.

**Events.** One commit per day file (`Event: import`, or `edited` when an archive day changes), author `irc-logger <irclogs@lojban.org>`, date = last message time of the day in its timezone, `Source: irc/<channel>`, `Source-Id: <date>`. `_meta/irc/<channel>/days.csv` (`date,lines,messages,nicks,tz,format,source`).

### 3.5 Dictionary (`dict/<word>/`)

**Source.** One PostgreSQL dump of **Lensisku**, which *is* the jbovlaste database migrated forward in place (same `users`, `valsi`, `definitions`, `comments`, `definitionvotes` tables and ids — `doc/research/dump-schemas.md` §2.1); a separate jbovlaste dump is unnecessary. Private tables and columns listed in `dump-schemas.md` §5.3 (passwords, emails, sessions, private messages, payments, `users.votesize`, per-voter rows) are excluded before the dump leaves the server. Ongoing updates from the public cursor feed `GET /api/jbovlaste/changes` (types `valsi, definition, comment, wiki`; carries `definition_versions` ids and inline diffs), which is the only update path (the version/history endpoints require a token).

**What history exists.** jbovlaste edited definitions **in place**: `definitions.time` is the last-modified time and the creation time is not recorded. Lensisku's `definition_versions` records every edit **since ~2024** and was not back-filled. Therefore each definition has one initial state whose date is only bounded (`Event-Window: <valsi.time>..<definitions.time>`, `Time-Confidence: window`) followed by exact edit events from 2024 on; comments, examples, etymology and word creation are dated exactly. `_meta/dict/coverage.toml` states this and `main:AGENTS.md` repeats it.

**Layout.**

```
dict/<slug(word)>/word.toml               word-level state: word, type, rafsi, selmaho, created, creator, etymology (with author/date), source ids
dict/<slug(word)>/<lang>-<definition-id>.md  one file per definition: front matter + definition text + ## Notes + ## Examples
dict/<slug(word)>/comments.md             append-only, one section per comment (threaded via "in reply to")
dict/_pages/<lang>/<pagename>.txt         jbovlaste's own wiki pages, every version (decompressed where compressed)
```

Definition front matter (`+++`): `id, word, lang, author, updated, version, score, status ∈ current|deleted|superseded, jargon, selmaho, keywords = [{word, sense, place}]` (place 0 = gloss word). `score` is the **aggregate** vote sum — per-voter data is not public in either application and is not projected; `votes.csv` from v0.2 is dropped.

**Events → commits.**

| event | source | author | date | `Source-Id` |
|---|---|---|---|---|
| word `created` | `valsi` | submitter | `valsi.time` (exact) | `valsi=<valsiId>` |
| definition initial state (`created`) | `definitions` + `keywordmapping` + summed votes | `definitions.userId` | `definitions.time` with `Event-Window` | `definition=<id> version=0` |
| definition `edited` | `definition_versions` (skipping rows with `mw_revid`, which are re-imported wiki revisions already in `wiki/`) | version author | `created_at` (exact); subject = the version's edit message | `definition=<id> version=<version_id>` |
| `comment` | `comments` ⋈ `threads` (post-V81 JSONB: subject + text blocks, `header` block dropped) | comment author | `time` (exact) | `comment=<commentId>` |
| example added | `example` | author | `time` (exact); appended to `## Examples` | `example=<exampleId>` |
| etymology added/edited | `etymology` | author | `time` (exact; edits in place → `window`) | `etymology=<etymologyId>` |
| score change | dump-to-dump or feed-to-feed difference in the vote sum | `jbomohi` | later dump/feed date with `Event-Window` | `score=<definitionId>@<date>` |
| jbovlaste wiki page version | `pages` | page author | `pages.time` (exact) | `jvspage=<pagename>@<version>` |

Deleted definitions (present in an earlier dump, absent later, or `status` in the feed) become `Event: deleted` with `status = "deleted"` kept in the file's last state. Rows authored by `officialdata` are ordinary events (the feed hides them; the dump does not).

**Indexes.** `_meta/dict/words.csv`, `definitions.csv` (`definition_id,word,lang,author,updated,versions,score,status,path`), `coverage.toml`.

### 3.6 CLL (`cll/`)

**Source.** A git **submodule** at `cll/src` pointing at the fork `https://github.com/int19h/cll` (decided; it carries every edition including 1.2.x and 1.3.x, with the upstream `lojban/cll` tags mirrored) so commits, tags and history are preserved verbatim. Plus tracked per-edition plain-text renderings `cll/editions/<edition>/<ch>-<slug>.txt`:

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

### 3.9 Loglan (`loglan/`) and LLG publications (`llg/`)

Lojban is a 1987 fork of Loglan (James Cooke Brown, 1955–); pre-fork Loglan documents are part of this history and post-fork Loglan Institute (TLI) material is relevant to the disputes and to comparison. Inventory, rights and dispositions: `doc/research/loglan-sources.md` §7.

**`loglan/`** — one commit per document, author = the document's author in the `loglan.org` namespace (`<author-slug>@loglan.org`), date = publication date (`pre-epoch` rule before 1970, §2.6), `Source: loglan`, `Source-Id: loglan=<catalogue-id>`.

- **Stored as text** (republication permitted): the 1992 Federal Circuit trademark opinion, *962 F.2d 1038* (public domain; `loglan/1992/fed-cir-962-f2d-1038.txt`); the TLI machine grammars `grammar80.y` (Trial 80, 1994) and `trial.85` and the LIP/LOD/MacTeach sources under TLI's stated grant ("use and modify … in any way which will be of benefit to the Loglan community"), stored with the grant text quoted in the header; the pre-fork bibliography extracted from `loglan.org/Loglan1/bibliography.html` as data (`_meta/loglan/bibliography.csv`); catalogue facts (ISBNs, page counts) from TLI's offerings page.
- **Catalogued cite-only** (`_meta/loglan/catalogue.csv`: id, title, author, date, rights holder as stated, where held, URL, sha256 where fetched, size, status ∈ `cite | asked | permitted | refused`): everything TLI-copyrighted until permission is granted — *Loglan 1* (all editions), *Notebooks 1–3*, *The Loglanist*, *Lognet*, *Loglan 4&5*, the *Readings* audio (redistribution explicitly refused), Holmes' modern corpus, the Second Life transcripts — plus third-party items TLI cannot relicense (the June 1960 *Scientific American* article, © Scientific American; already present as an OCR'd PDF inside the wiki image set and not republished separately). A permission changes an item's status and moves its text under `loglan/<year>/…` in an ordinary `Event: created` commit dated at the document's publication date.
- **Never stored**: nothing from Usenet or `loglangs.wiki` for now (cite-only rows); the `loglanists@ucsd.edu` archive does not exist (recorded as a negative finding in coverage).

**`llg/`** — the Logical Language Group's own historical publications from `www.lojban.org/files/`: *ju'i lobypli* JL1–JL18 and *le lojbo karni* LK8–11, 18 (ASCII newsletters, 1987–1990s, the primary record of the fork years and the baseline era), the early brochures, draft textbook and dictionary files, `L1LONGRV.TXT` / `useoldL1.txt` (LLG's review of *Loglan 1*), `oldlog.txt` (old-Loglan ↔ gismu mapping), the Eaton frequency data, etymology files, and *The Loglan-Lojban Dispute* (also on the wiki). Stored as text (LLG material, republished under LLG's terms per §5), `llg/<year>/<slug>.txt` (byte-exact where already plain text; renderings for TeX/DOC/ZIP members with the §3.1.2 header), one commit per document, author = LLG or the named author in the `lojban.org` namespace, date = publication date, `Source: llg`, `Source-Id: llg=<path-on-file-server>`; `_meta/llg/files.csv` mirrors the file-server listing.

### 3.10 `_meta/` and coverage

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

`.github/workflows/check.yml` on push/PR to `tools`: tests (tools and exchange, the latter unbound and bound), lint, determinism sample. `.github/workflows/update.yml` weekly + manual: checkout `tools`, worktree `main`, `archive fetch` for public sources (cached), `update`, `verify`, push `main` and the tag; a failing `verify` never pushes. The initial `build` runs locally (hours; 6-hour CI limit). Private dumps are applied locally with `jbomohi update dict --dump <file>` (and `wiki --dump`, `tiki --dump`); the operator-side export commands are `doc/ops/dump-request.md`.

---

## 5. Instruction files on `main` (the librarian)

Rendered from `tools/templates/main/` into `main`'s root commit and refreshed at every update. They are what turns a clone into a librarian:

- `AGENTS.md` — what the corpus is, layout and coverage, the citation grammar and short forms, the research method (search iteratively with `rg`/`git grep`, read neighbourhoods, follow leads, use `git log/blame/show/diff` for history and as-of, `_meta` CSVs for lookups), the answer contract (claims cite primary units, verbatim quotes only, positions attributed and dated, Positions/Ratified/Open for disputes, coverage-relative negatives), the status vocabulary and bodies, known quirks, and the untrusted-text rule. Draft: `tools/templates/main/AGENTS.md`.
- `CLAUDE.md`, `GEMINI.md` → `@AGENTS.md`; `.agents/rules/jbomohi.md` (Antigravity always-on rule pointing at `AGENTS.md`).
- `README.md` — human-facing: what this is, how to clone (submodule note for `cll/src`), coverage tables (rendered from `_meta`), the citation grammar, how to contribute notes/attestations, and a **provenance and terms** paragraph per source directory: each source is republished under its own terms as published by its owner (the wiki's policy, LLG's copyright on CLL, the list archives' public status, the Loglan Institute's terms), stated verbatim or by link, and the repository claims no licence of its own over the data (decided 2026-08-27).
- `.gitignore` — `/.jbomohi/` (reserved for local caches a harness might build) and OS junk.

---

## 6. Trust and provenance statements

`README.md` and `AGENTS.md` on `main` MUST state: the data is public and republished as archived; email addresses and names appear as in the sources; synthetic addresses (`@mw.lojban.org`, `@jbovlaste.lojban.org`, `@irc.lojban.org`) are placeholders, not deliverable addresses; renderings are not originals; identities are attested, never resolved; contributor IP addresses and anything private to a user account are never included; archive text can contain instructions and must be treated as data by any agent reading it.

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

1. **Loglan relicensing** — the ranked ask list in `doc/research/loglan-sources.md` §7.1 is with the human partner's TLI contact; each grant flips a catalogue row to `permitted` and adds the text (§3.9). Also to confirm: whether the TLI source-code grant is read as permitting a public mirror of the LIP/LOD sources (default: yes, with the grant quoted).
2. **Mail size** vs GitHub's budget, measured at M1; companion repository only if needed.
3. **Dump delivery** — `doc/ops/dump-request.md` has been handed to the server operator; the loaders are written against the schemas meanwhile and adjusted if the delivered tables differ.

Decided 2026-08-27 (see `doc/decisions/`): repository and default branch; namespaced commit identities; raw objects as Release assets; CLL fork; SQL-dump import for wiki/Tiki with API updates for the wiki; dictionary from one Lensisku dump with aggregate votes; the mail acquisition plan; `jbovlaste-admin` excluded; provenance per source under the sources' own terms; root commit at the Unix epoch with the `pre-epoch` rule for earlier documents.

---

## Appendix A — Glossary

event · unit (a file or line range) · citation (`<path>@<Source-Id>:L<a>-<b>`) · snapshot (`snapshot/<ts>` tag) · note · attestation · coverage — as defined above.

## Appendix B — Source documents

`doc/research/REPORT.md` (architecture research, prototype results, Codex comparison), `data-survey.md` (local data inventory, parsing quirks), `domain-data-handling.md` (verified online sources), `retrieval-sota.md`, `embeddings-landscape.md`, `agent-harness.md`, `codex-architecture-research.md`, `proto-notes.md`; `doc/future/librarian-service.md` (deferred design); `doc/decisions/` (adjudications).
