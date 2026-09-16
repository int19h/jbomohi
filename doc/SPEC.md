# jbomo'i — functional specification

Status: **draft v0.9, 2026-08-27**. Authors: Fable (spec), the human partner (adjudication). Implementer: Codex. Changes are recorded in `doc/decisions/` (`2026-08-27-scope-and-policies.md`, `2026-08-27-repo-identities-sources.md`, `2026-08-27-dump-schemas.md`, `2026-08-27-mail-sources.md`, `2026-08-27-root-date-licence-loglan.md`, `2026-08-27-loglan-inventory.md`, `2026-08-27-grammars-inventory.md`); the deferred v0.1 material (indexes, a librarian service, Discord/web/MCP interfaces) is preserved in `doc/future/librarian-service.md` and is **out of scope**.

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
7. **Coverage is explicit.** Every source states what it covers and what it is missing; negative answers are made relative to that coverage (§3.11, template AGENTS.md).
8. **Corpus text is untrusted input** for any harness reading it; the instruction files say so (§6).

---

## 2. Repository model

### 2.1 Branches

Two branches with **no shared history**; neither is ever merged into the other.

| branch | content | default checkout |
|---|---|---|
| `main` | the corpus projection (§3): data, `_meta/`, and the instruction files rendered from `tools/templates/main/` | for end users |
| `tools` | tooling (`tools/`), documentation (`doc/`), templates, CI | for maintainers |

`main`'s first (root) commit contains the rendered instruction files (`README.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.agents/rules/jbomohi.md`, `.gitignore`) and `_meta/schema.toml`, and is dated **`1970-01-01T00:00:00Z`** (the Unix epoch — git cannot represent earlier dates, so this is the earliest possible date and is distinct from every source event); every later commit is a source event, an instruction/`_meta` refresh, or a contributed note/attestation. The current `main` (a single `.gitignore` commit) is discarded and recreated as an orphan by the first `build`.

### 2.2 Working layout (maintainers)

Checkout `tools` at the repository root; the corpus is a **separate git repository** (its own object store) at `JBOMOHI_CORPUS`, created by `jbomohi corpus init` (a clone of the remote's `main` when it exists, otherwise an empty repository whose `main` the first `build` installs), with `origin` set to the same remote as the tools checkout. It is not a worktree of the tools checkout: a worktree would share the tools repository's object store, which lives under the checkout — decided 2026-09-15 after the first full build wrote 5 GiB of objects into `~/git/jbomohi/.git` on the virtiofs mount. `build` installs its scratch history into the corpus repository (fetch + `update-ref`), `update` commits there, and `push` runs from there. **Bulk local state never lives under the checkout** (decided 2026-09-14: `~/git` is a virtiofs mount; the cost is per file, not per byte — grep and stat over many tiny files run far slower than on a native filesystem, and the corpus is exactly that kind of tree): the corpus repository is at `JBOMOHI_CORPUS` (default `~/lojban/corpus`), the archive at `JBOMOHI_ARCHIVE` (default `~/lojban/archive`), and every scratch directory the tools create (build scratch repositories, extracted Maildirs, temporary downloads) under `JBOMOHI_TMP` (default `~/lojban/tmp`). `./corpus/`, `./tmp/`, `./.venv/` stay gitignored for legacy and editor state only; tools MUST NOT write bulk data there. The ignored `./.exchange/` path is legacy local state, not active coordination, and tools MUST NOT depend on it.

### 2.3 Raw archive tier

Downloaded dumps, zips, API responses, scraped pages and database dumps are **never committed** as such. They live in an archive directory (`JBOMOHI_ARCHIVE`, default `~/lojban/archive`) as immutable content-addressed objects with manifests `{source, kind, origin, fetched_at, sha256, bytes, coverage {from, to, counts}, notes}`. Manifests are tracked on `main:_meta/archive/` so the projection is reproducible by anyone with the same objects; kinds that produce one manifest per fetched page or message (`mhonarc-page`, `numbered-rfc822`) are tracked there as one consolidated TOML per list and kind (`_meta/archive/mail/<list>/<kind>.toml`, an array of tables with the same fields, ordered by origin) rather than tens of thousands of files, while the archive directory keeps the per-object manifests (decided 2026-09-14). Public objects are mirrored as assets of the GitHub Release for each snapshot tag (never checked into the repository); private database dumps are never mirrored — their manifests suffice to prove what was used. The `sha256` in manifests is the tool's own content address, computed at ingest; no externally supplied checksum is required, transported, or verified (decided 2026-09-14). Operator exports are archived like any other object, with `origin` naming the export (`operator export <date>`), never a temporary hosting URL.

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
  | unrecorded author (the source keeps no author at all, e.g. a MediaWiki transwiki import with no actor row — not suppression) | `unrecorded` | `unrecorded@<host>` (decided 2026-09-15) |
  | `jbovlaste.lojban.org:<user>` (jbovlaste and Lensisku are one database and one user namespace — verified in `doc/research/dump-schemas.md` §2.1) | `<user>` | `<user>@jbovlaste.lojban.org` |
  | IP-only (logged-out) edits on the wiki or Tiki | the IP literal, exactly as the site itself publishes it in page histories and `User talk:<IP>` titles | `<ip>@<host>` — the site's own public attribution; **hidden** IP columns (`rc_ip`, `ip_changes`, `cu_*`, Tiki `*.ip`/`user_ip`) are never exported or projected (§6) |
  | suppressed / revision-deleted usernames (`rev_deleted` user bit) | `anonymous` | `anonymous@<host>` |
  | IRC day files (many speakers) | `irclogs` | `irclogs@irc.lojban.org` |
  | tool-generated commits (renderings, vote batches, refreshes) | `jbomohi` | `tools@jbomohi.invalid` |
  | contributed notes/attestations | the contributor's own git identity | as configured by the contributor |

  Usernames are used verbatim (case preserved) in projected file metadata and indexes. Git identity names cannot preserve `<`, `>`, or leading/trailing dots, so those characters are percent-encoded there; `%` is encoded first to keep the mapping injective. Characters not allowed in an email local part, including leading/trailing dots, are likewise percent-encoded. This encoding affects only git metadata, never the canonical source spelling in files. The `.invalid` and `*.lojban.org` placeholders are not deliverable addresses and `main:README.md` says so.
- `GIT_AUTHOR_DATE` = `GIT_COMMITTER_DATE` = the source event time. UTC when the source is unambiguous; otherwise the source's own local time, with `Time-Confidence` set.
- **Subject**: `<source>: <summary ≤ 72 chars>` — `wiki: BPFK Section: gadri (rev 108932) fix typo`, `mail/lojban: Re: [lojban] xorlo podcast`, `irc/lojban: 2015-06-20 (412 lines)`, `dict: kau en#12345 v3`, `cll: render 1.1-2019`, `meta: refresh README and coverage`, `notes: xorlo adoption (2004–2007)`.
- **Trailers** (`Key: value`, one per line, at the end of the body):
  - `Source: wiki | tiki | mail/<list> | irc/<channel> | dict | cll | loglan | llg | grammars | meta | notes | who` (the complete set; a new source directory adds its slug here first)
  - `Source-Id: <stable id>` — the citation anchor (§3.1.4)
  - `Event: created | edited | deleted | moved | comment | vote-batch | import | render | refresh | contributed`
  - `Time-Confidence: exact | tz-unknown | window | pre-epoch`
  - `Source-Date: <YYYY-MM-DD | YYYY-MM | YYYY>` — the source's own, independently evidenced publication date when it differs from the commit date: mandatory for `pre-epoch` (the true date that git cannot carry, full `YYYY-MM-DD`), optional with `exact` manifestation commits whose source states a publication date at a coarser or different resolution (CLL editions, §3.6; amended 2026-09-14). Never a guess: absent when the source gives none.
  - `Event-Window: <iso-date>..<iso-date>` when only bounded
  - source-specific: `Page-Id`, `Parent-Rev`, `Message-Id`, `In-Reply-To`, `Thread`, `Definition-Id`, `Version`, `Word`, `Edition`, `Renderer`.

### 2.6 Ordering, back-fill, as-of

- `build` emits events in strict chronological order across sources (merge by event time; ties by source name, then id). Events whose true date is **before 1970** (pre-fork Loglan documents, §3.9) cannot carry their date in git: they are committed immediately after the root commit, in true-date order, with the date clamped to `1970-01-01T00:00:00Z`, `Time-Confidence: pre-epoch`, and the true date in a `Source-Date:` trailer and in `_meta/`.
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
loglan/ llg/    Loglan documents and LLG publications (§3.9)
grammars/       formal grammars and parsers: submodules, vendored and replayed histories (§3.10)
```

#### 3.1.2 Encoding and fidelity

UTF-8, LF, no BOM for generated files. Raw-fidelity files (wikitext, RFC 822 messages, IRC lines, Tiki markup) are byte-exact as archived except for the normalisations listed per source. **Commit subjects are never empty** (decided 2026-09-15): every projector's summary is one non-empty line; when the source offers no title, subject or comment to build it from, the placeholder `[untitled]` stands in the title position (mail keeps its existing `[no subject]`), never an invented description, so the shapes fixed per source (§3.2 `wiki: <title> (rev <revid>) …`, etc.) still hold with the placeholder as `<title>`. Renderings (thread views, CLL edition text) start with a `#` header line naming the source and renderer so they are never mistaken for originals. **Mixed-encoding originals (decided 2026-09-14):** a raw-fidelity file whose bytes are neither valid UTF-8 nor attributable to one known legacy encoding (e.g. the camxes test corpora, which mix Latin-1 bytes with valid UTF-8 sequences) is stored with an injective, reversible byte escape rather than replaced or guessed: valid UTF-8 sequences are kept, every literal backslash becomes `\\`, every other invalid byte becomes `\xHH`, and line 1 is `# <source> source bytes escaped by jbomohi <escaper>/<version> | original=<archive member>`. The archive object keeps the original bytes; the provenance row records the escaper. This is the only permitted deviation from byte-exactness and it never applies where one encoding is known (Tiki, §3.2.5(c)).

#### 3.1.3 Metadata split

Commit metadata describes the **event** (who, when, what, source id). File metadata describes the **state**: TOML front matter between `+++` lines for Markdown/TOML-bearing files; a single `#` header line for plain-text renderings; none for raw-fidelity files (their metadata is in `_meta/` CSVs and in commits). Ledgers are CSV with a header row (RFC 4180). JSONL only where records nest.

#### 3.1.4 Citations

```
<path>@<Source-Id>:L<start>[-<end>]
```

`<path>` on `main`; `<Source-Id>` the stable id of the cited **version** (wiki `revid=…`, or `logid=…` for a wiki move or deletion recorded only in the log, mail `<Message-ID>`, IRC `YYYY-MM-DD`, dict `definition=<id> version=<n>`, CLL `cll=<edition>`, note id, tiki `tiki=<slug(page)>@<version>`); `L…` 1-based lines in that version. **Event citation (amended 2026-09-16):** a claim about the event itself rather than about its text — its actor, date, edit summary or trailers — cites the bare `<Source-Id>` with no path and no lines (`revid=119555`, `logid=61219`); it resolves to the commit whose `Source-Id` trailer matches, and the cited facts are that commit's metadata. Resolution: the commit whose `Source-Id` trailer matches for that path (for append-only files — IRC days, thread views — the commit at or after that id); read the lines from that blob. Where a file has been re-imported from a later archive manifestation (§3.4), the bare id (`2015-06-20`) names the initial import, the digest-qualified id (`2015-06-20@a1b2c3d4e5f6`) names that amendment, and a path with no `@…` names the current version. Commit hashes are never part of a citation. Short forms (`wiki:<pageid>@<revid>:L…`, `mail:<Message-ID>:L…`, `irc:<channel>/<date>:L…`, `dict:<word>/<id>@<v>:L…`, `cll:<edition>/<chapter>:L…`, `note:<id>`) are defined in `main:AGENTS.md` for harness use.

#### 3.1.5 Filename slugs

`slug()`: NFC; keep `[A-Za-z0-9'_,-]`; space → `_`; percent-encode everything else (including `/`, `:`, `.`); percent-encode a leading `.`/`-`; cap at 200 bytes (excess → `-` + 8 hex of SHA-1 of the full title). Space → `_` is injective on the actual domains: MediaWiki titles never distinguish a space from an underscore (the database stores spaces as underscores and normalises `a_b` to the page `a b`), and dictionary words contain neither. The projector nevertheless MUST verify injectivity rather than assume it — within one namespace (and within `dict/`) it computes every slug first and fails the build if two distinct source titles map to one path (including via the truncation suffix); it never disambiguates by suffix, because that would silently change citations and `git log --follow`. `_meta/<source>/*.csv` always maps original title/word ↔ path so nothing depends on inverting `slug()`. Case: most namespaces here are case-sensitive; `User`, `MediaWiki`, `Template`, `Module` and their talk namespaces are first-letter-capitalised, so titles differing only in first-letter case are one page there and two pages in the main namespace — the check is per namespace with the namespace's own case rule.

#### 3.1.6 Third-party repositories: submodule, vendored copy, replayed history

(Restored 2026-09-14 after an accidental deletion at 859c7a8, and reconciled with the archive-mirror/gitlink rules adopted for CLL in §3.6.) Sources that are themselves version-controlled elsewhere (the CLL DocBook, grammars and parsers, §3.6, §3.10) are brought in by exactly one of three mechanisms per source:

- **Submodule** when the source lives in a git repository. The tools never hold a checkout of it under the `tools` branch: `jbomohi archive fetch <source>` keeps a bare mirror at `<archive>/git/<name>.git` with a `git-mirror` manifest whose coverage lists the scoped refs and their peeled commits (§3.6(a)); projection is a pure function of that mirror. On `main` the source is a gitlink at `<dir>/src` (or a named subdirectory when a project has several histories) written as an `Event` gitlink change (mode `160000`, §3.6(b)), with the upstream URL declared on the event (`Event.submodules = {path: url}`, paired with the gitlink) and recorded in `_meta/<source>/upstream.toml` (`url, default_branch, pinned_commit, pinned_at, first_commit_date, licence`). The upstream history is *theirs* and is not replayed into `main`. A pin bump is one event commit: `Source: <source>`, `Event: edited` (`created` for the first pin), `Source-Id: <source>=<upstream commit>`, commit date = the upstream commit's committer date (`exact`), author = the upstream commit's author name and address verbatim (public git metadata, the same policy as a mail `From:`). A clone needs `--recurse-submodules`; `main:README.md` says so and lists every submodule with its pinned commit.
- **Vendored copy** when the source exists only as files (a zip, tarball, web page, Wayback capture): stored as text under the source directory, one commit per known release or capture, `Event: import`, date = the release/capture date as evidenced by the file's own text (`window` with `Event-Window` when only bounds are known; `Source-Date` when the file states a date at coarser resolution), `Source-Id: <source>=<version-or-capture-date>`, provenance (URL, archive object sha256, capture date) in `_meta/<source>/provenance.csv`. Binary-only material (jars, compiled parsers) is not stored; its provenance row is, and the object stays in the archive.
- **Replayed history** when a source survives in a non-git version-control store (RCS/CVS files inside a backup): the revisions are converted from the archived object (`rcs-fast-export`-equivalent logic inside the projector, no external tool at build time) and replayed into `main` as ordinary events — one commit per revision with its original author (in the source's namespace, e.g. `<login>@teddyb.org` for the camxes RCS), date and log message, `Event: created|edited`, `Source-Id: <source>=<file>@<revision>` — because the history *is* the artefact and no upstream repository exists to point at.

Where a file-only artefact later turns out to have a surviving repository, the vendored history is left in place (it is a record of what was published when) and the submodule is added alongside. `_meta/grammars/index.csv` (§3.10) names the mechanism per source.

### 3.2 Wiki (`wiki/`)

**Sources.** Initial import from a **full SQL dump** of the MediaWiki database supplied by the site operator (tables and private columns per `doc/research/dump-schemas.md`; passwords/emails/tokens are excluded before the dump leaves the server). Ongoing updates from `https://mw.lojban.org/api.php` — `prop=revisions` with `rvprop=ids|timestamp|user|comment|size|sha1|content`, `rvlimit=max`, `rvdir=newer`, `rvstart` = last imported timestamp, all namespaces except `File` binaries; ≤ 1 request/s, `maxlag=5`. The projector accepts either input for any range and MUST produce identical events from both (a determinism test at M1). The local snapshot (`~/git/lojban-wiki`) is a page-count cross-check only. The 66 pages it could not fetch are retried by title each update and listed in `_meta/wiki/errors.csv` while they fail.

**Layout.** `wiki/<ns>/<slug(title)>.wiki`, `<ns>` ∈ `main, talk, user, user_talk, lojban, lojban_talk, userwiki, userwiki_talk, user_profile, user_profile_talk, file, file_talk, template, template_talk, category, category_talk, module, module_talk, mediawiki, mediawiki_talk, help, help_talk` (ids 0–15, 200–203, 828–829 as reported by `siprop=namespaces`). `File:` pages keep the description wikitext; media are manifest-only in `_meta/wiki/media.csv` (`pageid,title,url,sha1,size,mime,uploaded,uploader`). Redirects are stored as their wikitext.

**Content.** The revision's raw wikitext, byte-exact. No front matter.

**Events.** One commit per revision, page-internal order by `revid`, global order chronological. Author `<user>` / `<user>@mw.lojban.org`; date = revision timestamp (UTC, `exact`). Subject `wiki: <title> (rev <revid>) <comment ≤ 40>`. Trailers `Source: wiki`, `Source-Id: revid=<revid>`, `Page-Id`, `Parent-Rev`, `Event: created|edited|moved|deleted` — moves and deletions come from the log, not from revisions (MediaWiki need not create a revision for either), so their events carry `Source-Id: logid=<logid>` (the API's stable log-event id) with `Page-Id` and `Log-Type: move|delete`; a **move** is a rename only (`git mv`, content unchanged, `Moved-From: <old path>`) and the redirect MediaWiki leaves at the old title is an ordinary revision with its own `revid`, projected independently at the old path, with `logid=` events sorting before `revid=` events at equal timestamps so the rename precedes its redirect; a **deletion** is projected (removing the file) only for a page whose history the projection already holds, while a page deleted before acquisition, whose revisions the public API refuses, is listed in `_meta/wiki/gaps.csv` by `logid`, title and timestamp with reason `deleted; history not API-accessible` and may be back-filled from the SQL dump's `archive` table (#14). Revision-deletion bits (`rev_deleted`) are honoured by the projector, not the dump: suppressed text is never written, suppressed usernames become `anonymous` (a logged-out editor's IP is not suppressed — MediaWiki publishes it and so does the projection), and such revisions are listed in `_meta/wiki/gaps.csv`. The dump-specific joins (`revision_actor_temp`, `revision_comment_temp`, MCR `slots → content → text`, `old_flags` decoding, external-store clusters) are specified in `doc/research/dump-schemas.md` §3; the loader MUST produce the same events from the dump and from the API for any overlapping range — **defined (2026-09-15, from the reconciliation of the 2026-09-15 export against the 2026-09-14 API crawl) as:** for every `revid` and `logid` present in *both* inputs the two paths emit byte-identical events; ids present in only one input are additive, and `_meta/wiki/coverage.toml` enumerates each additive class with its count and cause — dump-only revisions with no `revision_actor_temp` row (`rev_actor = 0`, the foreign halves of transwiki imports, invisible to `api.php` under `SCHEMA_COMPAT_READ_TEMP`), dump-only move logs whose `log_actor` is absent from `actor` (the 2013–2014 "Move page script" run), rows in namespaces the projection does not cover (`274 Widget`, `275 Widget talk`, `1198 Translations` — Translate-extension and widget machinery, listed with page counts, never projected), `rev_page` rows naming no `page` row, and API-only revisions newer than the export snapshot. A revision whose author the source does not record at all (no actor row, no suppression) is attributed to `unrecorded@mw.lojban.org` (display name `unrecorded`; §2.5 — distinct from `anonymous@`, which means *suppressed*), with a `gaps.csv` row `imported revision; author not recorded in the export`. A revision whose content cannot be resolved (the dump's `text` row is missing, or either path returns content whose length or SHA-1 disagrees with the source's declared `size`/`sha1`) is `text missing` on **both** paths: no file is written and `gaps.csv` says `text unresolvable: <cause>` — so the API's empty string for a revision with a non-zero declared size is a missing blob, not empty content.

**Lineage placement (decided 2026-09-14, from the full API crawl).** MediaWiki binds every revision to a page id (`rev_page`) for life; a move keeps the id and changes the title, and the redirect left behind is a *new* page id. The move log's `pageid` is therefore **not** the moved lineage: MediaWiki records the source title's page id *after* the move, i.e. the left-behind redirect (or `0` when none was left, as with `move_redir`). Placement rules, all mechanistic and fail-closed: (1) A page's path at time *t* is derived from its **current title by replaying move logs backward by title**: the latest move whose *new* title equals the page's title in the chain and whose timestamp is ≤ the chain's current bound gives the previous title, and so on; the chain stops at the timestamp of the oldest revision of the page's **current lineage** (rule 3), not of the page id as a whole — the earlier bound let one log be claimed by several reused-title histories; the current-lineage bound gives unique ownership (verified on the 2026-09-14 crawl: 4,851 moves, all unique). A move is attributed to a page by this title chain, never by the log's `pageid`. When two move logs into the same title could both fit (title reuse with no discriminating bound), neither is applied: the affected revisions stay at the latest safely derived title and `gaps.csv` records `move ambiguous: logid=<a>,<b>`. (2) `move_redir` is a move whose target was a redirect that MediaWiki deleted first. It is **one** event, `Event: moved`, `Source-Id: logid=<n>`, `Log-Type: move_redir`: the rename removes the old path and writes the target path, overwriting the redirect's file, and the trailer `Overwritten-Page-Id: <page id of the deleted redirect>` (plus `Overwritten-Last-Rev: <its last revid>` when the projection holds it) records that the redirect lineage ended in this commit. No second event and no synthetic `Source-Id` suffix: one source log is one commit, so citations resolve uniquely. (3) A page id whose revisions form **more than one parent chain** (`parentid=0` more than once: history merges and undeletes) has one *current lineage* — the chain containing the newest revision — placed by rule 1; every older chain is placed at the path the title chain gives for its own time range when the chain reaches it, otherwise at the current lineage's earliest derived path, with trailer `Lineage: merged` on each such revision and a `gaps.csv` row `pre-merge title unknown; placed at <path>`. A merged revision is written only when that path is free or held by the same page id at that moment; if another page holds it, the revision's commit carries no file change and the gap row reads `pre-merge title unknown; path <path> held by page <id>; not projected` — a placeholder never overwrites another page's state. The same rule governs lineages backfilled from the dump's `archive` table (#14): a deleted lineage is ended by the one log entry that accounts for it (`logging.log_page`, then a `move_redir` that overwrote its title, then title-and-time assignment with each entry used once); a lineage no entry accounts for is still projected, but when the next page claims its path it yields without a file change and `gaps.csv` says `deleted lineage unaccounted; path <path> released to page <id>` — never refused, never overwritten (decided 2026-09-15). (4) Migration skew: a redirect page's first revision at the source title may be stamped up to 60 s *before* the move log that vacated the title. Within a 60 s window the rename is ordered first (`Ordering: forced-before` on the move event; commit dates keep source times, non-monotonic as in §3.2.5(b)); a collision outside the window is a projector error, not a gap. (4b) A move whose normalised target is its own source (a case-only rename in a first-letter namespace, e.g. `Module:documentation/doc` → `Module:Documentation/doc`; three in the 2026-09-15 export) is still one `moved` commit with `Source-Id: logid=<n>`, carrying no file change (`Moved-From` equals the path): the log entry is a source event and must resolve as a citation, and a tree equal to its parent's is already a legitimate commit shape (§3.2.5(b)); decided 2026-09-15. (5) The archived `siteinfo` statistics are the comparison authority for acceptance counts (the live site keeps moving); the PR body explains any difference between statistics pages/edits and selected pages/revisions (namespace selection, deleted revisions counted in `edits`, pages created after discovery). The SQL dump (#14) supplies what the API cannot: `archive` rows (deleted lineages, rebuilt as real `deleted` events by the mechanisms in rule 3). It does **not** supply pre-move titles for merged lineages — verified 2026-09-15 on the operator export: no `merge` log entries exist (the multi-parent chains come from transwiki imports), all `import`/`upload` log rows have empty `log_params`, `log_search` carries no title association, and `revision_actor_temp.revactor_page` equals `rev_page` throughout — so rule 3's placements stand as the permanent record and `doc/research/dump-schemas.md` §3 records those four checks. A deleted lineage whose page id has since been reused by a live page is not rebuilt (gap `deleted lineage; page id reused by <id>`). Any future change to placement is a rebuild, never a patch.

**Indexes.** `_meta/wiki/pages.csv` (`pageid,ns,title,path,state,is_redirect,first_rev,last_rev,revisions`; `state` ∈ `current | deleted | not-projected`, `path` empty unless `current` — the historical path stays recoverable from the page's `moved`/`deleted` commits and `Moved-From` trailers), `revisions.csv` (`revid,pageid,parentid,timestamp,user,size,sha1,comment`).

**Quirks.** The 2014 bulk "Text replace" revisions are kept; `main:AGENTS.md` warns that they are noise when reading history. Talk pages are wikitext; no thread reconstruction at projection time.

#### 3.2.5 Tiki (`tiki/`)

Initial and only import from a **SQL dump** of the Tiki database (`doc/research/dump-schemas.md` §4; the dump must be taken with `--default-character-set=latin1 --skip-set-charset --hex-blob` because `tiki_history.data` is a blob while `tiki_pages.data` is text); the Tiki is read-only, so there is no ongoing update path, and HTML scraping of `tiki-pagehistory.php` is only the fallback if no dump is obtainable. Coverage ≈ 2001–2015 (M2).

Page versions: `tiki_history` holds versions 1..N−1 and `tiki_pages` holds the current version N; `version` numbers are neither dense nor monotonic, so events are ordered by `lastModif` (unix UTC, `exact`) and the `Source-Id` keeps the source's own version number. Forums: `tiki_comments` with `objectType='forum'` are projected as `tiki/forums/<forum-slug>/<topic-threadId>.txt` (rendering; one commit per post in `commentDate` order; nesting from `in_reply_to`; `Source-Id: tiki=forum/<threadId>`). The **WikiDiscuss** forum (id 1, ≈5.6k posts) is projected; the **mailing-list mirror** forum (id 5) is a duplicate view of `mail/` and is skipped, recorded in `_meta/tiki/coverage.toml`. Per-page comments (`objectType='wiki page'`) go to `tiki/talk/<slug(page)>.txt`, one commit per comment (`Source-Id: tiki=comment/<threadId>`). Display names come from `tiki_user_preferences.realName`; the literal login `Anonymous` maps to `anonymous@tiki.lojban.org` (IP-only rows keep the IP per §2.5).

**Facts of the 2026-09-13 export (decided 2026-09-14).** (a) `tiki_actionlog` holds no page rename/delete rows (only `db error`, `Viewed`, `system`, `login`), so **no rename or deletion events are projected**: the 171 titles that exist only in `tiki_history` are projected from their history alone, left at their last known state, and listed in `_meta/tiki/gaps.csv` with reason `no current row; rename/deletion undocumented`; coverage records `rename_delete_log = "unavailable"`. (b) Every current page also has a `tiki_history` row with the same `(pageName, version)`, and 784 of those pairs differ in content: both are evidence. History rows keep `Source-Id: tiki=<page>@<version>`; the current `tiki_pages` row is a separate final event `Source-Id: tiki=<page>@current`, dated by its own `lastModif` but always ordered last for its title (the 16 current rows whose timestamp is not the latest carry `Ordering: forced-final`). (c) Decoding never repairs or replaces characters: character columns of the latin1-client export decode as cp1252 with a per-field ISO-8859-1 fallback (preserving bytes 81/8D/8F/90/9D as C1 code points); `tiki_history.data` blobs decode strict UTF-8, then cp1252, then ISO-8859-1; the branch taken is counted per table in `coverage.toml` alongside the `?`/high-byte fidelity counts, under `tiki_text_fidelity`. A corrected `utf8mb4` export, if received, replaces the object and is re-imported by `build`. (d) A page version whose decoded content contains a NUL byte is not text and is not projected as a `.tiki` file (the corpus is UTF-8 text; the librarian surface is `grep`): both the history and current rows are listed in `_meta/tiki/gaps.csv` with reason `non-text page content (NUL bytes); preserved in archive object`, and coverage records `binary_page_versions_skipped` — a generic rule, never keyed on a title (one title, `av.gif.php`, in the 2026-09-13 export). (e) Tiki `Source-Id`s use the **slugged** page name — `tiki=<slug(pageName)>@<version>` and `tiki=<slug(pageName)>@current` — so the id is always a single line and equals the file's basename; `versions.csv` maps every id to the original title. This is required because two history titles contain CR/LF bytes; the title itself is never rewritten. `tiki/<slug(page)>.tiki` (Tiki markup, HTML-unescaped, otherwise byte-exact), one commit per version (`Source: tiki`, `Source-Id: tiki=<page>@<version>`, author from the history table, `exact`). `_meta/tiki/pages.csv`, `versions.csv`, with a `migrated_to` column naming the MediaWiki page where an import template (`{{BPFK Section from tiki|…}}`) or identical title establishes the correspondence.

### 3.3 Mail (`mail/<list>/`)

**Sources** (inventory and verification in `doc/research/mail-sources-inventory.md`; the whole corpus reduces to four physical archives, everything else — Google Groups, Lensisku's archive, Wayback/Archive-Team Yahoo captures, `lojban-list-old` — is a derived view of them and is never scraped):

- **Tier 1, bulk download** (no scraping): `https://mail.lojban.org/lists-plain/<list>/<list>.maildir.zip` — raw RFC 822 Maildirs, regenerated by the server — for `lojban-list` (107,669 files, 1989-12 → 2025-08) and `lojban-beginners, bpfk, jbovlaste, lojban-de, lojban-es, lojban-fr, lbck, lojban-announcements, wikichanges, wikidiscuss, wikineurotic`; `lists/old_lojban-list/1…19674` (the complete onelist/eGroups/Yahoo-era raw export, 1998-11 → 2003-05); `lists/jbosnu_raw.zip`; `www.lojban.org/files/lojban-list/lojban-*.gz` (native mbox, 1989-12 → 1998-04). The local Maildirs under `~/lojban/disc/mail` are earlier copies of the first zip and are superseded by it.
- **Tier 2, MHonArc crawl** only for the lists with no `lists-plain` counterpart: `announce, bpfk-announce, dracyselkei, jbofongri, jboske, jbosnu, lojban_story, pod` (≈5.7k pages). Crawl `msgNNNNN.html` **by number from 0 until 404** (indexes are incomplete), ≤ 2 requests/s; each page is reconstructed into an RFC 822 message (headers from the `<!--X-Message-Id/X-Reference-->` comments and the rendered header block, body from the rendered text) and carries `X-Jbomohi-Manifestation: mhonarc`.
- **Tier 3, gap-fill**: `lists/lojban-beginners/msg*.html` (20,910 pages; its Maildir has only 16,623 files and neither is a superset — take the union); `lists/lojban-list-old/` only for Message-IDs absent from Tier 1; `files/lojban-list/*.ZIP` (headerless eGroups text, 1998-10 → 2000-01) only for months missing from `old_lojban-list`.
- **Excluded**: `llg-board`, `llg-members`, `special*` (HTTP 401 — restricted); `jbovlaste-admin` (≈80k automated dictionary-change notifications; excluded — decided 2026-08-27 — and listed in coverage as available).

**Deduplication** (the Tier 1 Maildir is ≈45% duplicate copies in the pre-1995 era, up to five copies per message): primary key = normalised Message-ID (strip `<>`, trim, HTML-unescape, NFC, case-fold); among copies keep the one with the most headers, ranked `lists-plain Maildir > old_lojban-list / jbosnu_raw > files mbox > MHonArc page > files ZIP text`, and record the losers in `_meta/mail/<list>/duplicates.csv` with their provenance; fallback key when no Message-ID exists = hash of (normalised subject, from local-part, date to the minute when the message carries a `Date:` or `Received:` date, else the empty string, first 200 body characters); never dedupe on subject alone (amended 2026-09-14: archive-order dates differ per manifestation and must not enter the key). Threading uses `References` (all, in order) with `In-Reply-To` as fallback. Spam that reached a list is kept and flagged (`_meta/mail/<list>/messages.csv` column `spam_suspect`), never dropped.

**Layout.**

```
mail/<list>/cur/<unixtime>.<sha1(message-id)[:16]>.jbomohi:2,S   raw RFC 822, byte-exact, mode 0444
mail/<list>/new/  mail/<list>/tmp/                                 present, empty (.keep)
mail/<list>/threads/<YYYY>/<thread-key>.txt                        rendered thread view
```

A real Maildir readable by mutt/notmuch/mu; files are born in `cur/` with the Seen flag so readers do not rename them. `<thread-key>` = 12 hex of SHA-1(root Message-ID) + `-` + `slug(normalised subject)` ≤ 60 chars.

**Thread view.** Line 1: `# mail/<list> thread <thread-key> | root <Message-ID> | <n> messages | rendered by jbomohi <renderer>`; then per message `=== <n> | <ISO date> | <From> | <Message-ID> | <maildir file>` followed by the decoded `text/plain` body verbatim (HTML-only messages converted deterministically and marked `[html]` in the entry line); messages in JWZ order (References/In-Reply-To; subject fallback for orphans). **Subject fallback (decided 2026-09-14)** applies only to an *orphan* — a message with neither `References` nor `In-Reply-To` — and only joins it to the most recent same-subject thread (normalised subject) in the same list whose latest message is dated within 90 days before the orphan; otherwise the orphan starts its own thread. Roots that carry references are never merged by subject, so distinct threads that reuse a subject years apart stay distinct. Quotes and signatures are kept.

**Events.** One commit per unique message (Message-ID normalised as above; missing → `sha1(raw)@jbomohi.invalid`). Author = `From:` verbatim; date = `Date:` → UTC (`exact`), else first `Received:` (`tz-unknown`), else archive order (`window`: the date of the nearest preceding dated message in the same manifestation's archive order, with `Event-Window` from that date to the nearest following dated message's date; the manifest's fetch date when no neighbour is dated — never the Unix epoch). A `Date:` or `Received:` value that resolves at or before the Unix epoch is a corrupt header, not a date (no list existed before 1970; `pre-epoch` is reserved for documents that genuinely predate 1970, §2.6/§3.9): it is discarded and the next evidence is used, exactly as for a value that does not parse; `messages.csv` gains a `date_source` column (`header | received | archive-order`), `gaps.csv` records each discarded value verbatim (`date header unusable: <literal>`), and `coverage.toml` counts `unusable_date_headers` (decided 2026-09-15). Raw 8-bit header bytes in `From:`/`Subject:` that are not valid MIME-encoded words decode byte-preservingly (UTF-8, then cp1252, then ISO-8859-1) for the commit author, subject and thread view; U+FFFD replacement is never introduced, and the count of such headers is recorded in `coverage.toml` (decided 2026-09-14). `spam_suspect` is set only by `X-Spam-Flag: YES`, an `X-Spam-Status` beginning `Yes`, an `X-Bogosity` beginning `Spam`, or a `*****SPAM*****` subject marker — never by substring matches on rule names. Subject `mail/<list>: <Subject ≤ 60>`; trailers `Source: mail/<list>`, `Source-Id: <Message-ID>`, `Message-Id`, `In-Reply-To`, `Thread: <key>`, `Event: created`. The same commit appends the message to its thread view.

**Indexes.** `_meta/mail/<list>/messages.csv` (`message_id,date,from,subject,thread_key,file,manifestation,duplicate_of`), `threads.csv`, `duplicates.csv`.

### 3.4 IRC (`irc/<channel>/`)

**Sources.** `https://lojban.org/irclogs/<channel>/<YYYY_MM>/<YYYY_MM_DD>.txt` for `lojban`, `jbosnu`, `ckule` (plus `2000_all`, `2002_middle`, `2002_12`); the local `all_logs.txt` only as a cross-check (its first 51,004 lines are `#jbosnu`, not `#lojban`).

**Layout.** `irc/<channel>/<YYYY>/<YYYY-MM-DD>.txt`; line 1 `# irc #<channel> <date> tz=<±HHMM|unknown> source=<archive path> format=<iso|legacy|bracket|irssi|undated, or several joined by `+` when one day mixes shapes, e.g. legacy+iso, iso+irssi, legacy+undated>`; then lines in exactly one of the forms `HH:MM:SS <nick> message`, `HH:MM:SS * nick action`, `HH:MM:SS -- system/topic text`. Timestamps stay in the log's own timezone (in the header), seconds `00` where absent; a day whose ISO lines carry more than one explicit offset (a DST transition) keeps every offset known: header `tz=<first>/<second>` in order of first appearance, `Time-Confidence: exact`, and the commit date uses the last line's own offset; text byte-exact except mIRC control codes and NULs removed. Bridged relays (`<xxxx_> <la cenzis>: …`) are kept verbatim (`who/relays.toml` documents the patterns). Irssi-block dates come from `--- Day changed` markers.

**Undated and bounded sources.** A bracket-format file without day markers (`2000_05_26--2000_10_28.txt`, `2002_05_12--2002_11_28.txt`, `2002_11_29--2002_12_26.txt`) is projected as one bounded unit `irc/<channel>/<YYYY>/<from>--<to>.txt` with header `# irc #<channel> <from>..<to> tz=unknown … format=bracket days=unknown`, a `-- day boundary <n>` line at each observed clock rollover (an ordinal, never a date), one `Event: import` commit with `Source-Id: <from>..<to>`, `Time-Confidence: window`, `Event-Window: <from>..<to>`, git date `<to>T23:59:59+00:00`; `days.csv` records `days_observed` and `days_in_range`. No per-day files are fabricated. A source line with no timestamp is kept and rendered with the explicit placeholder `--:--:--` in place of `HH:MM:SS`; a wholly undated file becomes the day its file name names (`format=undated`), a dated file with an undated tail renders the tail after its last dated line (`format=legacy+undated`); `days.csv` records `undated_lines`. `_meta/irc/<channel>/gaps.csv` lists source days that are absent, never lines the repository holds.

**Overlapping fragments.** When several archive files contribute to one day: same-format fragments are unioned by clock with exact-line multiset-max deduplication; ISO and irssi fragments are matched on minute plus body, matched lines take the ISO seconds, unmatched lines from both are kept, all sorted by clock, and the header is `format=iso+irssi tz=<the ISO zone>` (a minute-plus-body match shows the irssi clock is in the ISO zone; only an irssi day with no ISO match stays `tz=unknown`); irssi-only lines carry `:00` seconds. The header's `source=` lists every contributing file and `days.csv` records `fragments`.

Legacy transition files may contain ISO lines: a day whose lines are all ISO is `format=iso` with its explicit offset; a day mixing legacy and ISO lines is `format=legacy+iso`, and the legacy clocks use the same-day ISO offset (without a same-day ISO line the legacy zone remains `unknown`). The same rule applies when legacy and ISO fragments come from separate files.

**Events.** One commit per day file (`Event: import`, or `edited` when an archive day changes), author `irclogs <irclogs@irc.lojban.org>`, date = last message time of the day in its timezone, `Source: irc/<channel>`, `Source-Id: <date>` for the initial import. When a later archive manifestation of the same day differs, the amendment commit's `Source-Id` is `<date>@<sha256 of the archive object, first 12 hex>` (unique per §4.4; the full digest is in the object's manifest), its git date is the day's last message time as before, and the trailer `Supersedes-Manifestation: <previous 12-hex digest or none>` records the chain. Each bounded unit is one `Event: import` with git date `<to>T23:59:59+00:00`, `Source-Id: <from>..<to>`, `Time-Confidence: window`, and the matching `Event-Window`. `_meta/irc/<channel>/days.csv` (`date,lines,messages,nicks,tz,format,source,days_observed,days_in_range,undated_lines,fragments`; the range-only fields are empty for ordinary day files).

### 3.5 Dictionary (`dict/<word>/`)

**Source.** One PostgreSQL dump of **Lensisku**, which *is* the jbovlaste database migrated forward in place (same `users`, `valsi`, `definitions`, `comments`, `definitionvotes` tables and ids — `doc/research/dump-schemas.md` §2.1); a separate jbovlaste dump is unnecessary. If a separate jbovlaste database export is nevertheless received, it is **not** a second projection input: Lensisku is the sole source of dictionary events, and the jbovlaste export is loaded only to produce `_meta/dict/jbovlaste-diff.csv` — rows present only in the jbovlaste export, and rows whose text or timestamps differ between the two (by shared id) — so that any pre-migration divergence is visible and can be adjudicated later rather than merged silently. Event-Windows are computed from Lensisku alone. Private tables and columns listed in `dump-schemas.md` §5.3 (passwords, emails, sessions, private messages, payments, `users.votesize`, per-voter rows) are excluded before the dump leaves the server. Ongoing updates from the public cursor feed `GET /api/jbovlaste/changes` (types `valsi, definition, comment, wiki`; carries `definition_versions` ids and inline diffs), which is the only update path (the version/history endpoints require a token). **Caveat (2026-09-14):** the live feed does not serialize `version_id` (Lensisku's `RecentChange` model drops it), so feed items cannot yield `Source-Id: definition=<id> version=<n>`. Until Lensisku exposes `version_id` (and ideally `prev_version_id`) on feed items — an upstream change to `lojban/lensisku` requested via the human partner — ongoing dictionary updates come from **periodic full exports diffed by primary key** (which carry version ids); the feed is archived raw as evidence but not projected. No cursor-derived or synthetic version ids are ever used.

**What history exists.** jbovlaste edited definitions **in place**: `definitions.time` is the last-modified time and the creation time is not recorded. Lensisku's `definition_versions` records every edit **since ~2024** and was not back-filled. Lensisku keeps the pre-version state as a frozen timestamp `definitions.created_at` and, for definitions edited under Lensisku, as a baseline snapshot row in `definition_versions` at exactly that timestamp; `definitions.time` is the *latest* edit time and must not date the initial state. Therefore each definition has one initial state whose date is only bounded (`Event-Window: <valsi.time>..<definitions.created_at>`, `Time-Confidence: window`) followed by exact edit events (the direct version rows after the baseline); the loader fails closed if a baseline row is not the earliest direct row or disagrees on the definition id or the word (`valsiid`); the **language** may differ — a baseline or intermediate version carries its own historical `langid`, and an edit that changes the language deletes `<old-lang>-<id>.md` and writes `<new-lang>-<id>.md` in the same `Event: edited` commit with a `Moved-From: <old path>` trailer, the index recording the current language's path (14 such moves in the 2026-09-13 export), and cross-checks the current `definitions` row against the latest direct version on **state** (text, notes, keywords, language, selma'o, jargon) but not on time — `definitions.time` is not reliably advanced by every Lensisku write path (2,573 rows differ from the latest version, by −4,181 s to +7 s, in the 2026-09-13 export), so version `created_at` is the authoritative exact time and `definitions.time` is kept only as input evidence; coverage records `latest_legacy_time_mismatches` with the minimum and maximum delta; comments, examples, etymology and word creation are dated exactly. `_meta/dict/coverage.toml` states this and `main:AGENTS.md` repeats it.

**Layout.**

```
dict/<slug(word)>/word.toml               word-level state: word, type, rafsi, selmaho, created, creator, etymology (with author/date), source ids
dict/<slug(word)>/<lang>-<definition-id>.md  one file per definition: front matter + definition text + ## Notes + ## Examples
dict/<slug(word)>/comments.md             append-only, one section per comment (threaded via "in reply to")
dict/<slug(word)>/examples.md             append-only, word-level examples (source `definitionid = 0`), one section per example
dict/_pages/<lang>/<pagename>.txt         jbovlaste's own wiki pages, every version (decompressed where compressed)
```

Definition front matter (`+++`): `id, word, lang, author, updated, version, score, status ∈ current|deleted|superseded, jargon, selmaho, keywords = [{word, sense, place}]` (place 0 = gloss word). `score` is the **aggregate** vote sum — per-voter data is not public in either application and is not projected; `votes.csv` from v0.2 is dropped.

**Events → commits.**

| event | source | author | date | `Source-Id` |
|---|---|---|---|---|
| word `created` | `valsi` | submitter | `valsi.time` (exact) | `valsi=<valsiId>` |
| definition initial state (`created`) | the **baseline snapshot**: the earliest direct (non-`mw_revid`) `definition_versions` row whose `created_at` equals `definitions.created_at`, or the `definitions` row itself when no version rows exist; plus `keywordmapping` and the aggregate score | `definitions.userId` | `definitions.created_at` (the frozen pre-version timestamp; **not** `definitions.time`, which moves with every edit) with `Event-Window: <valsi.time>..<definitions.created_at>` | `definition=<id> version=0` |
| definition `edited` | every direct `definition_versions` row **after** the baseline snapshot (skipping rows with `mw_revid`, which are re-imported wiki revisions already in `wiki/`; the baseline row itself is not emitted again) | version author | `created_at` (exact); subject = the version's edit message | `definition=<id> version=<version_id>` |
| `comment` | `comments` ⋈ `threads` (post-V81 JSONB: subject + text blocks, `header` block dropped) | comment author | `time` (exact) | `comment=<commentId>` |
| example added | `example` | author | `time` (exact); appended to the target definition's `## Examples`, or to `examples.md` when `definitionid = 0` (word-level) | `example=<exampleId>` |
| etymology added/edited | `etymology` | author | `time` (exact; edits in place → `window`) | `etymology=<etymologyId>` |
| score change | dump-to-dump or feed-to-feed difference in the vote sum | `jbomohi` | later dump/feed date with `Event-Window` | `score=<definitionId>@<date>` |
| jbovlaste wiki page version | `pages` | page author | `pages.time` (exact) | `jvspage=<pagename>@<version>` |

Deleted definitions (present in an earlier dump, absent later, or `status` in the feed) become `Event: deleted` with `status = "deleted"` kept in the file's last state. Rows authored by `officialdata` are ordinary events (the feed hides them; the dump does not).


**Timestamps.** Lensisku's `definition_versions.created_at` carries microseconds: events are ordered by the full source timestamp and the full value is kept in `_meta/dict/definitions.csv` and file front matter, while the git date is floored to the whole second (git's resolution); same-second events keep the §2.6 tie-break.


**MediaWiki mirror records are not dictionary data.** Lensisku mirrors wiki articles into the dictionary as type-16 (`wiki`) words whose `definition_versions` rows carry `mw_revid`. For any definition with at least one `mw_revid` version row, the whole record — its current `definitions` baseline, its `valsi` row and every version — is excluded from `dict/` (the canonical text and history are in `wiki/`); a type-16 word left with no ordinary definition is excluded too. `_meta/dict/coverage.toml` records `mirror_definitions_excluded` and `mirror_versions_excluded`. A type-16 definition with no `mw_revid` rows is ordinary dictionary data. The public feed's `change_type = wiki` entries are archived but never projected into `dict/`; wiki updates come only from the MediaWiki source.
**Clock skew between a word and its first definition.** Lensisku stamps `definitions.created_at` from the transaction start (`CURRENT_TIMESTAMP`) but `valsi.time` from application wall time, so a definition's baseline can precede its own word by a few seconds (1,353 rows, ≤ 7 s, in the 2026-09-13 export). The v0 event's window end and git date are the **effective** time `max(floor(definitions.created_at), valsi.time)`, so the word-created event always precedes its definition and the window never runs backwards; the full `created_at` stays in file metadata and indexes; `_meta/dict/coverage.toml` records `baseline_time_clamps = <n>`; an inversion larger than **10 seconds** fails the build as probable corruption rather than skew.

**Exact children that predate the baseline.** Examples (and any other exactly dated child event) can precede a definition's baseline time, because jbovlaste edited definition text in place while examples kept their original dates (342 definition-scoped examples, up to ~15 years earlier, in the 2026-09-13 export). An exact child proves the *definition* existed by that time, not that the baseline *text* did. So: the v0 commit is placed at the earlier of the effective baseline time and the earliest exact child targeting the definition (files must exist before their dependents), the `Event-Window` stays `<valsi.time>..<definitions.created_at>` (the bound on when the recorded text was set), and the v0 commit carries `State-As-Of: <definitions.created_at>` so a reader knows the text is the state as of that later time; coverage records `baseline_dependency_clamps = <n>`.
**Indexes.** `_meta/dict/words.csv`, `definitions.csv` (`definition_id,word,lang,author,updated,versions,score,status,path`), `coverage.toml`.

### 3.6 CLL (`cll/`)

**Source.** A git **submodule** at `cll/src` pointing at the fork `https://github.com/int19h/cll` (decided; it carries every edition including 1.2.x and 1.3.x, with the upstream `lojban/cll` tags mirrored) so commits, tags and history are preserved verbatim. Plus tracked per-edition plain-text renderings `cll/editions/<edition>/<ch>-<slug>.txt`:

| edition | source ref | note |
|---|---|---|
| `1997-online-draft` | first import `8048799d` (340 HTML files: 319 numbered `cN/sM.html` sections plus 20 chapter landings, chapter 20 holding its single section in `c20/s.html` → rendered as `20.1`; 320 sections in all — corrected 2026-09-14) | the pre-final online draft, not the printed book |
| `1.0-errata-2014` | `gh-pages` @ `dabe6154` | maintainers' reconstruction of printed 1.0 + errata (a claim, not diff-verified) |
| `1.1-2016`, `1.1-2018`, `1.1-2019` | `v1.1-<date>-html` tags | official LLG 1.1 |
| `1.2.<n>` | `geklojban-1.2.*` | unofficial |
| `1.3.<n>` | `v1.3.*` tags | fork; every `v1.3.<n>` tag is an edition, new tags become new editions on `update` |

The printed 1.0 is not recoverable from the repository; a future scan/OCR would be edition `1.0-print`.

**Source checkout, gitlink and dates (decided 2026-09-14).** (a) The tools never hold a CLL checkout inside the `tools` branch: `jbomohi archive fetch cll` keeps a bare mirror of the fork under the archive (`<archive>/git/cll.git`, manifest kind `git-mirror` whose coverage lists every scoped ref with its peeled commit); the renderer is a pure function of that mirror (§4.3) and fails closed if a ref in the frozen edition table peels to a different commit than the manifest recorded. (b) `Event` gains gitlink changes (git mode `160000`, written with `update-index --cacheinfo`) paired with `Event.submodules = {path: url}`; `main:.gitmodules` is **shared state owned by `commit_event`, never by a projector** (amended 2026-09-14 — CLL and grammar pin events interleave chronologically): `commit_event` reads the `.gitmodules` committed at the parent, validates it, replaces or adds only the entries the event declares, renders the whole file in sorted path order and stages it in that same commit, so every historical snapshot carries a usable `.gitmodules` for every gitlink it contains. Each CLL edition event declares `cll/src` → `https://github.com/int19h/cll` and points the gitlink at that edition's peeled commit, so a historical snapshot carries the exact source and the final tree points at the newest edition. (c) Commit date of an edition event = the committer date of the peeled commit (`exact`; it is the manifestation, exactly as an IRC re-import is dated by its manifestation). Where the edition has a publication date of its own it goes in `Source-Date`: the date embedded in a `v1.1-<date>-html` tag name; `1997` for `1997-online-draft` (the book's year — the draft's posting day is unknown, and the `8048799d` import of 2008-05-30 is the only evidence in the repository); nothing for `1.0-errata-2014`, `1.2.<n>` and `1.3.<n>`. The edition table with refs, peeled commits, commit dates and `Source-Date`s is `_meta/cll/editions.csv`.

**Rendering.** Line 1 `# cll <edition> chapter <n> <title> | rendered from <ref> by jbomohi <renderer version>`; sections as `## <n>.<m> <title>` (numbers are stable across editions; appendix chapters keep the source labels `A1`, `A2`, `A3` as `<n>`; a chapter whose only content is an unnumbered landing page is section `<n>.1`, as later DocBook editions number it — decided 2026-09-14), examples as `[Example <n>.<m>]`, markup dropped deterministically, Lojban/gloss lines preserved one per line. One commit per edition rendering (`Event: render`, author `jbomohi`, commit date = the committer date of the edition's peeled source commit with `Source-Date` per the paragraph above, `Source-Id: cll=<edition>`, `Renderer:`). `_meta/cll/alignment.csv` (`edition_a,section_a,edition_b,section_b,relation,method`) computed for each **adjacent pair** of editions in the table's chronological order (not every pair; the chain composes): sections with the same number are `identical` (byte-equal rendered text) or `changed` (`method=section-number`); sections left unmatched on either side are paired one-to-one, greedily by descending `difflib.SequenceMatcher` ratio over rendered text, and accepted at ratio ≥ 0.80 as `renumbered` (`method=text-similarity-0.80`); what remains is `added` or `removed` (`method=none`). Deterministic ties break on `(section_a, section_b)` order (decided 2026-09-14).

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

### 3.10 Grammars and parsers (`grammars/`)

Every formal grammar and parser implementation of Lojban is part of the record. Inventory, provenance, licences and duplicates: `doc/research/grammars-inventory.md` (§4 is the authoritative table; this section fixes the rules). Layout `grammars/<name>/…` with `_meta/grammars/index.csv` (`name, author, language, formalism, dialect, years, mechanism, upstream, licence`), per-source `upstream.toml` (submodules) or `provenance.csv` (vendored/replayed), and a paragraph in `main:AGENTS.md` mapping grammars to dialects (official 1990/1991/1997 baselines; camxes "standard"; ilmentufa beta/experimental; zantufa; zasni gerna).

- **Official grammar lineage — vendored, one commit per generation**, dated from the text in each file (never from HTTP `Last-Modified`, which reflects server migrations): the 1988–90 generations from `lojban.org/files/history/` (1989-02-25, 1989-09-23, 1990-05-06, **1st baseline 1990-07-20**; the undated `GRAMMAR.B17`/`GRAMMAR.NEW` at the 1990-07-20 boundary, flagged), the **2nd baseline 1991-06-23** and its 2.33/2.35/2.46/2.47 revisions (`GRAMMAR.233` from `parser.shar.gz`; `bnf.235`, `bnf.246`, `bnf.247`, `techfix.235`, restamped `bnf.28` recovered from Wayback 1999 captures; `grammar.235`/`grammar.247` were never published — recorded as gaps), the **3rd baseline 1997-01-10** (`bnf.300`, `techfix.300`, `xref.300`, `PD` — public domain by LLG's own dedication; `grammar.300` itself already arrives with `cll/src`), the LLG parser sources (1993-10-19 shar; binaries → provenance rows only), Nick Nicholas' NU-Prolog analyser (1993-08-07), and Cowan's parser 3.0.00 as the submodule `lojban/cll-parser` plus a provenance row for the 2003-11-13 tarball.
- **camxes (Robin Lee Powell) — replayed history.** `hlg_backup__2011-01-11.tgz` from `teddyb.org/~rlpowell/hobbies/lojban/grammar/` (mirror it into the archive tier now; it is one person's home directory) contains `RCS/lojban.peg,v` with 39 dated revisions, 2004-03-18 → 2011-01-11, and log messages: replayed per §3.1.6 into `grammars/camxes/` — only `RCS/lojban.peg,v` is replayed; the other RCS files contribute their selected head versions as support files, not histories. Support files are imported as **file-dated vendored events** that the global merge places wherever their dates fall (amended 2026-09-14; "preceded" was conceptual, not commit order): one 2004-03-28 conversion import holding the non-duplicate files dated on or before that day (`bnf_conv.pl`, `lojban2.bnf`, `abnf2peg.pl`, `lojban.abnf`, `orig_lojban.peg`, `jc_mail.txt`, `bnf.vim`, the `old/` conversion files, the `earley/` experiments — it lands between RCS 1.7 and 1.8), then separate events for the later heads on their own dates (`test_sentences` 2005-01-28, `morph_test_sentences` 2005-02-25, `morph_header` and the Rats translator/build notes 2005-12-16/17, `lojban_morphology_old.peg` 2007-05-30); the Java jar (2006-08-21) is binary → provenance row (the wiki's `lojban_peg_parser.zip` is the same bytes). `lojban/camxes` on GitHub is a snapshot whose HEAD deletes the grammar: optional submodule pinned at `1c1d9ec` (2011-01-13).
- **Submodules** (pinned per `upstream.toml`, bumped as events per §3.1.6): `lojban/jbofihe` (tags `0_2`…`v0.44` are the release record); `mhagiwara/camxes.js`; **both** ilmentufa histories — `Ntsekees/ilmentufa` (original, ends 2015-12-10) and `lojban/ilmentufa` (fresh root 2016-02-02, canonical) — plus optionally `mezohe/gentufa`; `guskant/gerna_cipra` (zantufa, maftufa, maltufa); `YoshikuniJujo/zasni-gerna` (Haskell) and, low priority, his `lojban_parser`/`lojysamban`/`cakyrespa`; `gitlab.com/zugz/tersmu` (upstream) and `lojban/tersmu` (2026 continuation); `alanpost/jbogenturfahi` + `alanpost/genturfahi` (not the squashed `lojban/` copy); `lojban/camxes-py`; `eaburns/johaus`; `phma/valfendi`; `int19h/jbotci`; the long tail in inventory §2.7 (`zirsam`, `sneturfahi`, `nei`, `sotygeha`, `typed-lojban`, `genrei`, …) is included when the maintainer decides — default: include anything that parses Lojban and has a licence, list the rest in `index.csv` with `mechanism = cite`.
- **zasni gerna (xorxes)**: the grammar is wiki text already in `wiki/`; vendored as an extracted `.peg` under `grammars/zasni-gerna/xorxes/`, dated 2015-01-21 (its last wiki revision), cross-referenced to the wiki unit.
- **Duplicates are imported once** (inventory §4.3): `camxes-pamoi.peg` in ilmentufa is `lojban.peg` rev 1.39; `lojban/cll:scripts/yacc/lojban_grammar.y` is `grammar.300`; `lojban/cll-parser` is Cowan's tarball; the GitLab `lojban/` group and the `lojban-cvs*`/`La-Lojban/`/`lagleki/` copies are mirrors, never sources; `lojban/camxes-rs` is not a Lojban parser.
- **Licences** are recorded per row in `index.csv` (GPL-2/3, AGPL-3, MIT, BSD-2/3, ISC, AFL-2.0, LLG's 1993 permission grant, public domain, and *none* for `lojban/camxes` and much of the long tail — recorded as "no licence", never assumed) and summarised in `main:README.md`'s provenance paragraph.

### 3.11 `_meta/` and coverage

`_meta/schema.toml` (`projection_schema`, renderer versions; **the tools commit and snapshot name only in the tip refresh commit, never in the root** — decided 2026-09-15: the root commit's rendered files are a pure function of the templates and the projection schema version, so a tools change that leaves every projected byte unchanged leaves every event commit hash unchanged, and one that changes output changes hashes only from the first affected event; the README's "built by tools commit" line and the snapshot name are therefore rendered as `pending` in the root and filled in by the refresh commit), `_meta/archive/*.toml` (§2.3), per-source `coverage.toml` (`from, to, counts, gaps = [...], updated`), and the CSV indexes above. `build`/`update` re-render `README.md` (coverage tables) and the instruction files from `tools/templates/main/` as an `Event: refresh` commit at the tip, dated at the last event's time. Per-source `_meta/<source>/**` index files ride each projector's final event; `update` folds those files into the refresh commit whenever the source yielded at least one new event, even when that final event's own `Source-Id` was already present (decided 2026-09-14).

---

## 4. Tools (`tools` branch)

### 4.1 Language and layout

Python ≥ 3.13 with `uv`; package `jbomohi_tools`, CLI `jbomohi` (`uv run jbomohi …`). Third-party dependencies only with a reason recorded in `pyproject.toml`. Layout: `tools/jbomohi_tools/` (`archive/`, `project/<source>.py`, `render/`, `who/`, `notes/`, `git.py`), `tools/templates/main/` (instruction files for `main`), `tools/tests/`, `doc/`, `.github/workflows/`.

### 4.2 CLI

```
jbomohi corpus init|status                  create / inspect the corpus repository holding main (JBOMOHI_CORPUS)
jbomohi archive fetch <source> [--since …]  fetch into the archive tier; write manifests
jbomohi archive verify                      sha256-check every manifest
jbomohi build [--sources …] [--until DATE]  full deterministic rebuild of main (orphan root; --until is refused until every selected projector accepts the cut-off itself, since a merge-time filter would drop the _meta files that ride each stream's final event — decided 2026-09-14)
jbomohi update [<source> …]                 append new events; refresh; tag snapshot/<ts> (never moves an existing tag; build, which replaces main by definition, retires and re-creates a snapshot tag that names a commit outside the new history, and the push of a rebuilt main updates such tags with --force only under the same human authorisation as the branch — decided 2026-09-15)
jbomohi verify                              invariants (§4.4)
jbomohi cll render <edition>                per-edition rendering (§3.6)
jbomohi who propose|promote                 attestation helpers (§3.7)
jbomohi notes lint                          front matter + citation resolution (§3.8)
jbomohi cite resolve <citation>             print the cited lines (the reference resolver)
```

Idempotent and resumable; network commands rate-limited per source (default ≤ 1 request/s) with backoff; writes only to the archive, the corpus repository, and `JBOMOHI_TMP`.

### 4.3 Fetch/project split

Each source module exposes `fetch(archive, since) -> manifests` (network; writes only the archive) and `project(archive, state) -> events` (pure: no network, no clock). A single `commit_event(event)` helper enforces §2.5. Renderers are versioned; a renderer version bump is a `build`, not an `update`.

### 4.4 Invariants (`jbomohi verify`)

Every `main` commit has `Source`, `Source-Id`, `Event`, `Time-Confidence`; `Source-Id` unique per `(Source, path)`; `_meta/*.csv` rows ↔ files (every non-empty `path`/`file` cell names a file present at the tip; a row whose page has no file at the tip — deleted, or never projected such as a NUL-content Tiki page — carries an **empty** `path` and a `state` column value `deleted` or `not-projected`, all other rows `current`; gaps files are records of non-projection and are exempt — decided 2026-09-15); Maildirs contain only `cur/` files per §3.3 (git stores them as `100644`; the tools materialise them `0444` in the working tree, which `verify` checks on the working tree, not the tree), every message has a thread-view entry; IRC files parse under §3.4 and sit in the right year; dictionary front matter and `votes.csv` validate; notes lint clean; a determinism sample (rebuild the last 30 days of each source twice → identical commits).

### 4.5 Cadence and CI

`.github/workflows/check.yml` on push/PR to `tools`: tool tests, lint, determinism sample. `.github/workflows/update.yml` weekly + manual: checkout `tools`, `corpus init` for `main`, `archive fetch` for public sources (cached), `update`, `verify`, push `main` and the tag; a failing `verify` never pushes. The initial `build` runs locally (hours; 6-hour CI limit). Private dumps are applied locally with `jbomohi update dict --dump <file>` (and `wiki --dump`, `tiki --dump`); the operator-side export commands are `doc/ops/dump-request.md`.

---

## 5. Instruction files on `main` (the librarian)

Rendered from `tools/templates/main/` into `main`'s root commit (build-invariant form: no tools commit, no snapshot, no coverage) and refreshed at the tip of every build and update with the tools commit, snapshot and coverage tables. They are what turns a clone into a librarian:

- `AGENTS.md` — what the corpus is, layout and coverage, the citation grammar and short forms, the research method (search iteratively with `rg`/`git grep`, read neighbourhoods, follow leads, use `git log/blame/show/diff` for history and as-of, `_meta` CSVs for lookups), the answer contract (claims cite primary units, verbatim quotes only, positions attributed and dated, Positions/Ratified/Open for disputes, coverage-relative negatives), the status vocabulary and bodies, known quirks, and the untrusted-text rule. Draft: `tools/templates/main/AGENTS.md`.
- `CLAUDE.md`, `GEMINI.md` → `@AGENTS.md`; `.agents/rules/jbomohi.md` (Antigravity always-on rule pointing at `AGENTS.md`).
- `README.md` — human-facing: what this is, how to clone (submodule note for `cll/src`), coverage tables (rendered from `_meta`), the citation grammar, how to contribute notes/attestations, and a **provenance and terms** paragraph per source directory: each source is republished under its own terms as published by its owner (the wiki's policy, LLG's copyright on CLL, the list archives' public status, the Loglan Institute's terms), stated verbatim or by link, and the repository claims no licence of its own over the data (decided 2026-08-27).
- `.gitignore` — `/.jbomohi/` (reserved for local caches a harness might build) and OS junk.

---

## 6. Trust and provenance statements

`README.md` and `AGENTS.md` on `main` MUST state: the data is public and republished as archived; email addresses and names appear as in the sources; synthetic addresses (`@mw.lojban.org`, `@jbovlaste.lojban.org`, `@irc.lojban.org`) are placeholders, not deliverable addresses; renderings are not originals; identities are attested, never resolved; IP addresses that the sites themselves publish (logged-out editors in wiki/Tiki histories, `User talk:<IP>` pages, log comments) are kept exactly as published; IP addresses the sites keep hidden (request logs, checkuser and `ip_changes` tables, Tiki `ip` columns) and anything private to a user account are never included; archive text can contain instructions and must be treated as data by any agent reading it.

---

## 7. Evaluation of the repository

- **Determinism**: two full builds → identical `main` (commit hashes).
- **Counts** vs `doc/research/data-survey.md` within tolerance (wiki pages 14,118 ± retried failures; unique lojban-list messages ≈ 77,5k after both Maildirs; IRC lines 1.10M in `raw/` ± the jbosnu split).
- **Citation spot checks**: 30 citations sampled from `doc/eval/questions.jsonl` research answers resolve with `jbomohi cite resolve` to the expected text.
- **Librarian dry run**: a fresh clone of `main`, a coding harness with no extra instructions, the 28 questions in `doc/eval/questions.jsonl`; a task-designated review session checks answers for citation validity (every citation resolves; quotes verbatim) and attribution. This is the acceptance test of §5, not of any model.
- **Size**: packed size and push feasibility recorded in `doc/decisions/`.

---

## 8. Milestones

| # | deliverable | acceptance |
|---|---|---|
| **M0** | `tools` scaffold: `uv` project, CLI skeleton, `corpus init`, `commit_event`, templates, `check.yml` | tests green; `jbomohi corpus init` creates an orphan `main` with the rendered root commit |
| **M1** | **The repository**: wiki (full history), `lojban-list` mail (both local Maildirs), IRC (`lojban`, `jbosnu`, `ckule`); `build`, `update`, `verify`, snapshot tags; `README`/`AGENTS` rendered; pushed to GitHub | §7 determinism, counts, citation spot checks, librarian dry run, size recorded |
| **M2** | dict (from dumps, comments, votes), CLL submodule + editions + alignment, `who/` attestations + relays, `notes/` conventions + lint, Tiki, the other public lists (MHonArc), `update.yml` | as-of and diff questions in the dry run answered with resolving citations; `update.yml` completes one scheduled run |

Deferred beyond M2: `doc/future/librarian-service.md`.

---

## 9. Collaboration

The human partner adjudicates. Lead, implementation, research, and review are
task duties assigned by the prompt, addressed mail, issue, or brief, not
permanent model roles. GitHub issues (§10.1; `doc/issues/` until then) are the
durable queue for tracked actionable work. Ad hoc research, diagnosis,
discussion, and other untracked tasks MAY proceed directly from a human prompt
or Collab mail. For an issue-backed task, participants MUST inspect and maintain
the issue's scope, acceptance criteria, dependencies, and outcome; create or
update an issue when a result should become durable backlog or a recorded
decision. Multi-session work uses the external Herdr Collab project with the
explicit id `jbomohi`; no checkout path or cwd selects it. Sessions and
recipient groups are tailored to the task. Durable `send`, `reply`, `show`, and
`ack` preserve assignments, findings, decisions, and disposition; direct Herdr
prompts are transient wakeups and never the only record. Herdr Collab does not
impose the workflow, review sequence, issue policy, or authority, and its
external state is changed only through `herdr-collab`, never by editing files
manually. Projects MAY use cache-aware resumable-pause and compaction
conventions, but MUST NOT schedule forced model turns, polling, automatic
compaction, or unattended dialog input.

---

## 10. Open questions

1. **Grammars long tail** — which of the small/unlicensed parsers in `doc/research/grammars-inventory.md` §2.7 to include as submodules (default above: include what parses Lojban and carries a licence). `lojban-ebnf` is a private project and is out of scope (decided 2026-09-02).
2. **Loglan relicensing** — the ranked ask list in `doc/research/loglan-sources.md` §7.1 is with the human partner's TLI contact; each grant flips a catalogue row to `permitted` and adds the text (§3.9). Also to confirm: whether the TLI source-code grant is read as permitting a public mirror of the LIP/LOD sources (default: yes, with the grant quoted).
3. **Mail size** vs GitHub's budget, measured at M1; companion repository only if needed.
4. **Dump delivery** — `doc/ops/dump-request.md` has been handed to the server operator; the loaders are written against the schemas meanwhile and adjusted if the delivered tables differ.

Decided 2026-08-27 (see `doc/decisions/`): repository and default branch; namespaced commit identities; raw objects as Release assets; CLL fork; SQL-dump import for wiki/Tiki with API updates for the wiki; dictionary from one Lensisku dump with aggregate votes; the mail acquisition plan; `jbovlaste-admin` excluded; provenance per source under the sources' own terms; root commit at the Unix epoch with the `pre-epoch` rule for earlier documents; the grammars/parsers plan (§3.10).

---

## Appendix A — Glossary

event · unit (a file or line range) · citation (`<path>@<Source-Id>:L<a>-<b>`) · snapshot (`snapshot/<ts>` tag) · note · attestation · coverage — as defined above.

## Appendix B — Source documents

`doc/research/REPORT.md` (architecture research, prototype results, Codex comparison), `data-survey.md` (local data inventory, parsing quirks), `domain-data-handling.md` (verified online sources), `retrieval-sota.md`, `embeddings-landscape.md`, `agent-harness.md`, `codex-architecture-research.md`, `proto-notes.md`; `doc/future/librarian-service.md` (deferred design); `doc/decisions/` (adjudications).
