# Dump schemas and event extraction for the four database sources

*Research note, 2026-08-27. Scope: the database schemas and dump-handling needed to project
jbovlaste, Lensisku, mw.lojban.org (MediaWiki 1.38) and tiki.lojban.org (old Tiki) into `main`
as one commit per source event, per `doc/SPEC.md` §3.2, §3.2.5, §3.5. Companion to
`doc/research/data-survey.md` (what exists) — this note is about **how the rows are shaped**.*

**Verification key.** ✅ = read in the source repository or observed on the live API;
⚠️ = inferred from adjacent code/docs, needs confirmation against the real dump.

---

## 0. Summary of what each source can actually give us

| Source | Per-event history in the DB? | Ongoing update path | Blocking unknown |
|---|---|---|---|
| jbovlaste | **No** for definitions — edits are in place (§1.2). Yes for its own wiki `pages`; comments/votes/examples/etymology are append-rows carrying `time` | Site is read-only (§1.4); `recent.rss` is a time-window feed | Nothing structural — **Lensisku's database *is* jbovlaste's** (§2.1), so one Lensisku dump covers both |
| Lensisku | **Yes** — `definition_versions`, but only from ~2024 on; the jbovlaste import was **not** back-filled into it (§2.2) | Public `/api/jbovlaste/changes` cursor feed ✅ | Obtaining a pg dump; the version API needs a bearer token ✅ |
| MediaWiki 1.38 | **Yes** — full `revision`/`slots`/`content`/`text` chain | `api.php?action=query&prop=revisions` ✅ (already proven against this wiki, §2.8) | Operator willingness to strip private `user` columns (§3.9) |
| Tiki | **Yes** in principle — every version, but split `tiki_history` (1..N-1) + `tiki_pages` (N) (§4.2) | None — read-only, no API | Whether `maxVersions` pruning was ever enabled (§4.3); dump charset handling (§4.9) |

---

## 1. jbovlaste (Perl/Mason + PostgreSQL)

Source: `https://github.com/lojban/jbovlaste`, branch `master`. The **entire** schema is one file,
`design/jbovlaste.sql` (413 lines) ✅, plus `design/languages.sql` (seed data),
`design/users.sql` (4 seed users) and 8 files in `design/migrations/`.
There is no ORM and no migration framework; the Mason components issue raw DBI SQL.

### 1.1 Tables

| Table | Columns (type — meaning) | Source ref |
|---|---|---|
| `users` | `userId serial PK`, `username varchar(64) UNIQUE`, `password char(32)` **PRIVATE** (MD5), `email text NOT NULL` **PRIVATE**, `realname text`, `url text`, `personal text` (wiki-marked self-description), `votesize real DEFAULT 0.0` ("the secret size of their vote") | `design/jbovlaste.sql:23-33` ✅ |
| `languages` | `langId serial PK`, `tag varchar(128)` (IANA), `englishname`, `lojbanname`, `realname` (in-language), `forlojban`, `url` | `:41-49` ✅ |
| `pages` | jbovlaste's **own** wiki. `pagename text`, `version int4`, `time int4` (unix), `userId int4`, `langId int4`, `content text`, `compressed boolean`, `latest boolean`; PK `(pagename, version, langId)` | `:56-70` ✅ |
| `valsitypes` | `typeId int2 PK`, `descriptor varchar(128)` — 16 rows seeded: `nalvla, gismu, cmavo, cmevla, lujvo, fu'ivla, cmavo-compound, experimental gismu, experimental cmavo, bu-letteral, zei-lujvo, obsolete cmevla, obsolete fu'ivla, obsolete zei-lujvo, obsolete cmavo, phrase` | `:96-115` ✅ |
| `valsi` | `valsiId serial PK`, `word text UNIQUE`, `typeId int2 → valsitypes`, `userId int4` (submitter), `rafsi text` (**space-separated list**, not a table), `time int4` (unix, submission) | `:119-126` ✅ |
| `natlangwords` | `wordId serial PK`, `langId`, `word text`, `meaning text` (sense disambiguator), `meaningNum int4`, `userId`, `time int4`, `notes text`; UNIQUE `(langId, word, meaning)` | `:140-156` ✅ |
| `definitions` | `langId`, `valsiId`, `definitionNum int4` (per lang+word), `definitionId serial PK`, `definition text NOT NULL` (the place structure), `notes text`, `jargon text`, `userId int4`, `time int4`, `selmaho text`; UNIQUE `(langId, valsiId, definitionNum)` | `:169-186` ✅ |
| `keywordmapping` | `natlangwordId → natlangwords`, `definitionId → definitions`, `place int2` (**0 = gloss word**, 1..n = place keywords); PK all three | `:205-210` ✅ |
| `definitionvotes` | `valsiId`, `langId`, `definitionId`, `value real`, `userId int4`, `time int4`; **PK `(valsiId, langId, userId)`** — one vote per user per (word, language), so re-voting *moves* the vote and history is overwritten | `:226-232` ✅ |
| `natlangwordvotes` | `natlangwordId`, `definitionid`, `place int4`, `userId`, `value real`, `time int4`; PK `(natlangwordId, userId)` — reverse-direction votes | `:246-254` ✅ |
| `threads` | `threadId serial PK`, `valsiId int4`, `natlangwordId int4`, `definitionId int4` (**0 = about the word as a whole**) | `:266-272` ✅ |
| `comments` | `commentId serial PK`, `threadId int4`, `parentId int4` (**0 = top level**, else parent `commentId`), `userId int4`, `commentNum int4`, `time int4`, `subject text`, `content text` (wiki-marked) | `:286-295` ✅ |
| `etymology` | `etymologyId serial UNIQUE`, `valsiId`, `langId`, `content text` (wiki-marked), `time int4`, `userId` | `:329-337` ✅ |
| `example` | `exampleId serial UNIQUE`, `valsiId`, `definitionId` (0 = word-level), `exampleNum int4`, `content text`, `time int4`, `userId` | `:348-356` ✅ |
| `xrefs` | `srctype int2, srcId int4, desttype int2, destId int4` — generic cross-refs, "as yet undecided set of values"; effectively unused ⚠️ | `:313-320` ✅ |
| `valsibestdefinitions`, `natlangwordbestplaces` | materialised "best guess" tables used by the exporter and lookup, rebuilt by `bin/updatevbg` / `bin/updatenlbg` | `design/migrations/140330_03_guesses_material_views.sql:19,159` ✅ |

Convenience views (`convenientcomments`, `convenientdefinitions`, `convenientvalsi`,
`convenientexamples`, `convenientetymology`, `convenientthreads`) join the above with `users`
and `languages`; a dump taken with `pg_dump` will carry them but they add nothing we cannot
join ourselves (`design/jbovlaste.sql:367-411` ✅).

### 1.2 Is there definition history? **No.**

`dict/editdef.html:154-157` ✅ does:

```perl
$dbh->do("UPDATE definitions SET definition=?, notes=?,
    jargon=?, time=?, selmaho=?
    WHERE definitionid=?", undef,
    $definitiontxt, $notes, $jargon, time(), $selmaho, $definition);
```

Consequences, all load-bearing for the projection:

* There is **no `version`, no `oldid`, no history table** for definitions. `definitions.time` is
  the **last-modified** time; the creation time is destroyed by the first edit, surviving only as
  `valsi.time` for the word as a whole.
* The edit also does `DELETE FROM keywordmapping WHERE definitionid=?` and re-inserts
  (`editdef.html:159-193` ✅) — keyword history is likewise gone.
* An edit **auto-votes**: it deletes the editor's existing vote for `(valsiid, langid)` and inserts
  a fresh one with `value = users.votesize` (`editdef.html:196-206` ✅). So `definitionvotes.time`
  for the definition's author is usually just the last-edit time, not a deliberate vote.
* `pages` (the jbovlaste wiki) *does* keep every version — a trigger `pages_sanity_check()`
  enforces monotonic `version` and flips `latest` (`design/jbovlaste.sql:74-93` ✅). Old versions
  may be `compressed`: `maintenance/compress.pl` ✅ stores
  `base64(Compress::Zlib::compress(content))` and sets `compressed='true'`. Decode accordingly.
* `comments`, `example`, `etymology`, `valsi` are append-only rows carrying `time` — these give
  genuine events. `etymology` has an `etymologyId` "needed to be able to go back and edit a
  specific bit", i.e. etymology is also editable in place ⚠️.

### 1.3 What the XML export omits

`export/xml-export.html` ✅ (467 lines) is the whole exporter. Per `valsi` it emits
`word`, `type` (+ `unofficial="true"` for experimental/obsolete), `<rafsi>`, `<selmaho>`,
`<user><username><realname>`, `<definition>`/`<text>`, `<definitionid>`, `<score>`, `<notes>`,
`<glossword>` and `<keyword place= sense=>`; plus a reverse `<direction>` of `<nlword>` elements.

Omitted, confirmed by reading the generator: **all timestamps**, `valsiid`, `langid`,
`definitionNum`, **examples**, **etymology**, **comments**, and **individual votes** — only the
*sum* is emitted as `<score>` (`xml-export.html:161-172` ✅). `positive_scores_only=1` (default)
drops every definition scoring < 1; `all_defs=1` switches from `valsibestdefinitions` to
`definitions`. Captcha-gated for anonymous users, with a hardcoded `bot_key=z2BsnKYJhAB0VNsl`
bypass (`xml-export.html:21,56` ✅).

**So: the XML export is not a substitute for a dump.** Everything the SPEC wants for `dict/`
except the definition text itself — dates, comments, votes, examples, etymology — is absent.

### 1.4 What a dump must contain, and what must never leave the server

Wanted: `users` (`userid, username, realname, url, personal, votesize`), `languages`, `valsi`,
`valsitypes`, `definitions`, `keywordmapping`, `natlangwords`, `definitionvotes`,
`natlangwordvotes`, `threads`, `comments`, `etymology`, `example`, `pages`.

**Never leave the database owner's machine:** `users.password` (MD5 of rot13'd password —
still *live* credentials, see §2.5) and `users.email`. `users.votesize` is documented in the
schema as "the secret size of their vote" and should be treated as private too — it is an
administrative trust weight, not a public fact. Suggested producer-side command:

```sh
pg_dump -Fp --no-owner --no-privileges \
  -T users -T '*_seq_backup' jbovlaste > jbovlaste-public.sql
psql -c "\copy (SELECT userid, username, realname, url, personal FROM users)
         TO 'users-public.csv' CSV HEADER" jbovlaste
```

(`-T users` excludes the table wholesale; the public columns come back via the `\copy`.)

---

## 2. Lensisku (Rust/actix-web + PostgreSQL)

Source: **`https://github.com/lojban/lensisku`** ✅ (Rust, ~661 tracked files, 144 migrations in
`migrations/V*.sql`, flyway-style naming). Related repos: `lojban/lensisku-containers` (deploy),
`lojban/lensisku-go`, `lojban/lensisku-net` (partial re-implementations, ignorable).

### 2.1 How it relates to jbovlaste: same database, extended in place

This is the single most important structural fact. `migrations/V2__lensisku.sql` ✅ creates only
`messages`, `muplis`, `muplis_update`, `dictionary` — the mail/example/legacy-dictionary tables.
Every jbovlaste table (`users`, `valsi`, `definitions`, `definitionvotes`, `comments`, `threads`,
`keywordmapping`, `natlangwords`, `etymology`, `languages`) appears **only in `ALTER TABLE`
statements**, never in a `CREATE TABLE` ✅. Lensisku was bootstrapped by restoring a jbovlaste
`pg_dump` and migrating forward from there.

Therefore **ids, usernames and timestamps are preserved**:

* `users.userid` 3 is still `rlpowell` on the live API ✅, matching `design/users.sql:3` ✅.
* `definitions.definitionid`, `valsi.valsiid`, `comments.commentid`/`threadid`/`commentnum`/
  `parentid` all survive — visible in `GET /api/comments/list` ✅.
* `definitions.time` (int4 unix) is kept, and `V25__definitions_created_at.sql:1-6` ✅ added
  `created_at TIMESTAMPTZ` initialised as `to_timestamp(COALESCE(time, now()))` — i.e.
  **`created_at` inherits jbovlaste's last-modified semantics, it is not a real creation date.**
* `users.created_at` was added with `DEFAULT '1970-01-01 00:00:00'`
  (`V12__user_created_at.sql:3-5` ✅), so every imported jbovlaste user reports a 1970 join date —
  observed live for `rlpowell` ✅. **Do not project it.**

**Lensisku shares jbovlaste's user namespace.** Same `users` table, same `userid`s, same
usernames. One identity namespace (`<user>@jbovlaste.lojban.org`) covers both, with the caveat
that accounts created after ~2024 exist only on the Lensisku side.

### 2.2 `definition_versions` — the real per-edit history

`migrations/V22__owner_editable_definitions.sql:2-25` ✅:

| Column | Type | Notes |
|---|---|---|
| `version_id` | `SERIAL PK` | the `<n>` for `Source-Id: definition=<id> version=<n>` |
| `definition_id` | `INTEGER → definitions(definitionid)` | jbovlaste id preserved |
| `langid`, `valsiid` | `INTEGER` FKs | target language / word at that version |
| `definition` | `TEXT NOT NULL` | the definition body |
| `notes`, `selmaho`, `jargon` | `TEXT` | |
| `gloss_keywords`, `place_keywords` | `JSONB DEFAULT '[]'` | snapshot of the keyword mapping |
| `user_id` | `INTEGER → users(userid)` | **the author of the version** |
| `created_at` | `TIMESTAMP NOT NULL` → later `TIMESTAMPTZ` (`V96__timestamps.sql:10-13` ✅) | |
| `message` | `TEXT NOT NULL` | free-text **commit message** ("Updated version" is the default seen live ✅) |
| `owner_only` | `BOOLEAN` (added same file, `:49`) | |
| `etymology` | `TEXT` (`V24__etymology_in_versions.sql:2` ✅) | |
| `rafsi` | `TEXT` (`V153…:9` ✅) | |
| `mw_revid` | `BIGINT` + partial UNIQUE index (`V158__wiki_revision_history.sql:3-7` ✅) | set when the row was imported from a mw.lojban.org revision |

**Critical gap: there is no back-fill.** No migration inserts a baseline row per pre-existing
definition (`grep -i insert … definition_versions migrations/` returns nothing ✅), and
`src/users/service.rs:310-317` ✅ has an explicit `NOT EXISTS (SELECT 1 FROM definition_versions …)`
branch to synthesise a contribution card for definitions that have no versions at all. So:

* Definitions untouched since the import have **zero** version rows → their only event is a
  synthetic "as of the dump" state, which is exactly the SPEC's `Event-Window` / `window`
  time-confidence case (`doc/SPEC.md:195`).
* Definitions edited since the import have version rows **only from the first Lensisku-era edit
  onwards**; the jbovlaste-era text is not recoverable from this table.

`src/versions/service.rs:194` ✅ is the only non-import writer; `src/jbovlaste/service.rs` writes
at 6 more call sites (create/edit/bulk-import/revert paths) ✅.

### 2.3 Other tables of interest

| Table | Purpose | Ref |
|---|---|---|
| `wiki_articles` | mirror of mw.lojban.org: `page_id UNIQUE`, `namespace`, `title`, `revision_id`, `wikitext`, `markdown`, `plain_text`, `is_redirect`, `last_edited`, `fetched_at`, `history_imported_until` | `V146__create_wiki_articles.sql:5-19` ✅, `V158:9-10` ✅ |
| `wiki_sync_state` | singleton row, `last_full_sync`, `last_incremental_sync` | `V146:26-31` ✅ |
| `messages` | **mailing-list archive**: `id`, `message_id UNIQUE`, `date TEXT`, `sent_at timestamptz`, `subject`, `cleaned_subject`, `from_address`, `to_address`, `content`, `plain`/`parts_json JSONB`, `file_path UNIQUE` | `V2:2-11` ✅ + `V58`, `V59`, `V80` ✅ |
| `message_spam_votes`, `message_threads`, `thread_participants`, `private_messages` | spam voting and the *private* DM system — **not** list mail | `V102`, `V147` ✅ |
| `etymology_backup` | `CREATE TABLE etymology_backup AS SELECT * FROM etymology` — the jbovlaste `etymology` table was folded into `definitions.etymology` by `V23__move_etymology.sql` ✅, keeping a copy | `V23:76` ✅ |
| `definition_links`, `definition_images`, `valsi_sounds`, `collections`, `flashcards*`, `comment_reactions/bookmarks/opinions`, `user_sessions`, `payments`, `oauth_accounts` | Lensisku-native features; not source events for us | various ✅ |

**Mail note (a separate task covers mail):** the list archive lives in `messages`, keyed by
`file_path` to a maildir; `fetch_mail.sh` and `src/mailarchive/` drive it. Public read endpoints
are `GET /api/mail/thread` and `GET /api/mail/message/{id}` ✅.

### 2.4 Comments: converted in place, and lossy about `subject`

`V81__add_rich_text_comments.sql:5` ✅ changed `comments.content` from `TEXT` to `JSONB`:

```sql
ALTER TABLE comments ALTER COLUMN content TYPE jsonb
  USING jsonb_build_array(jsonb_build_object('type', 'text', 'data', content));
```

Then `V87__migrate_comment_subjects.sql:6-17` ✅ **prepended the `subject` into the content array**
as `{"type":"header","data":<subject>}` — while leaving `comments.subject` in place. So in a
current Lensisku dump every migrated jbovlaste comment reads
`[{"type":"header","data":"<subject>"},{"type":"text","data":"<original body>"}]`, and the live
`/api/comments/list` shows exactly that ✅. `V82` ✅ added `plain_content TEXT` maintained by an
`extract_plain_content()` trigger that concatenates only the `text` blocks.

**For the projection:** reconstruct the jbovlaste comment body from the `text` blocks (or
`plain_content`) and take the subject from `comments.subject`, *not* from the `header` block, to
avoid duplicating it. `comment_media` (`V81`) holds attachments ⚠️.

### 2.5 Users: private columns

`users` now carries, beyond jbovlaste's columns: `created_at`, `role user_role`
(`admin|moderator|editor|user|unconfirmed`), `email_confirmed`, `email_confirmation_token`,
`email_confirmation_sent_at` (`V36__roles.sql:20-24` ✅), `disabled` (`V61`), and a widened
`password text` (`V14` ✅).

**`users.password` still contains live jbovlaste credentials.** `src/auth/service.rs:63-72` ✅:

```rust
/// Verify a password against a stored hash, supporting both MD5 and bcrypt
… if stored is 32 hex chars {
    let digest = format!("{:x}", md5::compute(rot13(password).as_bytes()));
```

i.e. unmigrated accounts authenticate against `md5(rot13(password))` — trivially crackable and
still accepted. **Must never leave the owner's machine.** Same for `email`,
`email_confirmation_token`, and every row of `user_sessions`, `password_reset_requests`,
`password_change_verifications`, `oauth_accounts`, `private_messages`, `message_threads`,
`thread_participants`, `payments`, `balance_transactions`, `paypal_subscriptions`,
`user_search_history`, `user_session_events`.

Public per the API: `username`, `realname`, `url`, `personal`, `user_id`, `role`, contribution
counts (`src/users/dto.rs` `PublicUserProfile` ✅). The admin `GET /api/users` list returns
*obfuscated* emails (`src/users/service.rs:89-101` ✅) — never the raw address.

### 2.6 Votes: aggregate is public, voter identity is not

`definitionvotes` is unchanged from jbovlaste (`valsiid, langid, definitionid, value real,
userid, time`), still with PK `(valsiid, langid, userid)` ✅. Every public read path selects
`COALESCE(SUM(value),0)::bigint AS score` (e.g. `src/jbovlaste/service.rs:4031,4222` ✅); the only
per-voter query is `GET /api/users/votes`, which is bearer-authenticated and filtered
`WHERE dv.userid = $1` — **your own votes only** (`src/users/service.rs:216-229` ✅). No public
endpoint exposes who voted for what.

**So voter identity is available only from a dump.** `doc/SPEC.md:195` writes `votes.csv` with
"voter as published by the source" — from the API that means no voter column at all; from a dump
it means a decision to make, and the conservative default is to record the voter only if the
operator agrees, else write `voter=` empty with the score.

### 2.7 Public changes feed ✅ (verified live, unauthenticated)

`GET https://lensisku.lojban.org/api/jbovlaste/changes` — the OpenAPI marks it
`bearer_auth`, but it answers **HTTP 200 without a token** ✅ (unlike
`/api/versions/{id}/history`, which returns **401** ✅).

* Params ✅: `limit` (default 20, clamped 1–100, `src/jbovlaste/service.rs:4761`), `types` (CSV of
  `comment,definition,valsi,message,wiki`), `after` (opaque cursor), `home` (excludes `valsi`).
* **Cursor pagination, no time window** — the cursor is `(time, type_sort_order, cursor_id)`
  compared as a tuple, so it is stable for back-fill: `(c.time, -2, c.commentid)`,
  `(EXTRACT(EPOCH FROM dv.created_at), -0, dv.version_id)`, `(v.time, -1, v.valsiid)`
  (`service.rs:4778-4880` ✅).
* Response fields (observed ✅): `change_type` (`valsi|definition|comment|message|wiki`), `word`,
  `content`, `valsi_id`, `lang_id`, `natlang_word_id`, `comment_id`, `thread_id`,
  `definition_id`, `username`, `time` (**unix int**), `language_name`,
  `language_english_name`, `language_lojban_name`, `comment_num`, `parent_id`, `valsi_word`, and
  for definitions a full inline **`diff`** with `old_content`/`new_content`
  (`definition, notes, selmaho, jargon, rafsi, gloss_keywords, place_keywords, has_image,
  langid, language_*`) and a `changes[]` array.
* Rows authored by `officialdata` are excluded (`WHERE u.username != 'officialdata'` ✅), and the
  definition branch is restricted to `v.source_langid = 1` (Lojban headwords) ✅. Results are
  Redis-cached for 300 s ✅.

**This feed is the ongoing update path for `dict/`** and it carries version ids, so
`Source-Id: definition=<id> version=<n>` is directly derivable. What it does *not* give is the
pre-2024 history — that needs the dump.

Export endpoint: `GET /api/export/dictionary/{lang}?format=pdf|latex|xml|json&positive_scores_only=false&all…`
✅ — same shape as jbovlaste's XML export, with `positive_scores_only=false` lifting the score
filter (and `V157__export_all_definitions_when_scores_unfiltered.sql` ✅ making that emit *every*
definition). Still no timestamps or comments; treat it as a convenience, not a history source.

### 2.8 Lensisku already imports MediaWiki history — useful precedent

`src/wiki/importer.rs` ✅ pulls `https://mw.lojban.org/api.php` with
`action=query&prop=revisions&rvslots=main&rvprop=ids|timestamp|user|comment|content&rvlimit=50`
(`:441,1052-1054` ✅), paginating on `rvcontinue`, and writes each revision into
`definition_versions` with `mw_revid` and `ON CONFLICT (mw_revid) … DO NOTHING` (`:1015-1032` ✅).
That is an existence proof that the API path in `doc/SPEC.md:143` works against this wiki, and
`wiki_articles.history_imported_until` is the same watermark pattern we need.


---

## 3. MediaWiki 1.38.7 (mw.lojban.org)

**Live facts ✅** (`api.php?action=query&meta=siteinfo`): `generator` = **MediaWiki 1.38.7**,
`phpversion` 8.0.29, `dbtype` mysql / `dbversion` **10.4.34-MariaDB**, `timezone` UTC,
`articlepath` `/papri/$1`, `maxarticlesize` 10 240 000. Statistics: **14 338 pages, 2 251
articles, 62 478 edits, 4 808 images, 418 users, 23 admins** ✅.

Schema line numbers below are from git tag **`1.38.7`** ✅ (`includes/Defines.php:36` →
`MW_VERSION = '1.38.7'`). Note `maintenance/tables.sql:1-2` is a stub — the real MySQL/MariaDB DDL
is **`maintenance/tables-generated.sql`**, generated from `maintenance/tables.json` (which carries
the per-column doc comments).

### 3.1 Two 1.38-specific traps that break a naive reader

| Trap | Evidence |
|---|---|
| **`revision.rev_actor` is normally 0.** `$wgActorTableSchemaMigrationStage = SCHEMA_COMPAT_TEMP` is the 1.38 default (`includes/DefaultSettings.php:2444`); `ActorMigration.php:27-36` maps `rev_user` to the temp table **`revision_actor_temp`** (`revactor_rev`, `revactor_actor`); `ActorMigrationBase.php:388` writes `rev_actor` only under `WRITE_NEW`. | `ActorMigrationBase.php:259-278` ✅ |
| **`revision.rev_comment_id` is normally 0.** `CommentStore::TEMP_TABLES['rev_comment']['stage'] = MIGRATION_OLD` (`CommentStore.php:67-73`) — "OLD" means *use the temp table* **`revision_comment_temp`**; `CommentStore.php:507-525` sets `rev_comment_id` only on the temp-NEW branch. | `CommentStore.php:192-206` ✅ |

> **Rule:** resolve `rev_id → revision_actor_temp → actor` and
> `rev_id → revision_comment_temp → comment`, falling back to `rev_actor` / `rev_comment_id` when
> the temp row is missing (a wiki that has run `migrateActors.php`/`migrateComments.php`).
> **Which applies to mw.lojban.org can only be settled by looking at the actual dump** ⚠️ — write
> the loader to handle both. `archive`, `logging`, `image`, `oldimage`, `filearchive` and
> `recentchanges` use their own `*_actor` / `*_comment_id` columns directly, no temp tables
> (`RevisionStore.php:2597-2625` ✅).

### 3.2 Tables needed for full revision reconstruction

| Table | Key columns |
|---|---|
| `page` (`tables-generated.sql:822-845`) | `page_id` PK, `page_namespace`, `page_title` VARBINARY(255) (**DB key**: spaces→underscores, no ns prefix), `page_is_redirect`, `page_latest` → `rev_id`, `page_len`, `page_content_model`, `page_lang`; UNIQUE `(page_namespace, page_title)` |
| `revision` (`:872-891`) | `rev_id` PK, `rev_page`, `rev_comment_id`, `rev_actor`, `rev_timestamp` BINARY(14), `rev_minor_edit`, `rev_deleted` bitfield, `rev_len`, `rev_parent_id`, `rev_sha1` |
| `revision_actor_temp`, `revision_comment_temp` | see §3.1 |
| `slots` (`:60-71`) | PK `(slot_revision_id, slot_role_id)`; `slot_revision_id` = `rev_id` **or `ar_rev_id`**; `slot_content_id`; **`slot_origin`** = the rev that *originated* this slot — `slot_origin == slot_revision_id` ⇒ this revision changed the slot, else inherited |
| `slot_roles` (`:488-495`) | `role_id` AI, `role_name` UNIQUE. **IDs are assigned on demand — read the table, never hardcode `1='main'`** |
| `content` (`:119-128`) | `content_id` PK, `content_size`, `content_sha1` (base-36), `content_model` → `content_models.model_id`, `content_address` |
| `content_models` (`:496-503`) | `model_id` AI, `model_name` UNIQUE (`wikitext`, `javascript`, `css`, `text`, `json`) — also on-demand ids |
| `text` (`:626-633`) | `old_id` PK, `old_text` MEDIUMBLOB, `old_flags` TINYBLOB |
| `comment` (`:50-59`) | `comment_id`, `comment_hash`, `comment_text` BLOB (≤500 UTF-8 chars), `comment_data` BLOB (**JSON**, localisation of auto-summaries) |
| `actor` (`:22-31`) | `actor_id`, `actor_user` **NULL for anonymous**, `actor_name` = username **or IP literal** |
| `user` (`:847-870`) | see §3.6 |
| `archive` (`:799-820`) | `ar_id`, `ar_namespace`, `ar_title`, `ar_comment_id`, `ar_actor`, `ar_timestamp`, `ar_rev_id` UNIQUE, `ar_deleted`, `ar_len`, `ar_page_id`, `ar_parent_id`, `ar_sha1`. **No `ar_text_id`, no `ar_flags`** ✅ |
| `logging` (`:523-551`) | `log_id`, `log_type`, `log_action`, `log_timestamp`, `log_actor`, `log_namespace`, `log_title`, `log_page`, `log_comment_id`, `log_params` BLOB, `log_deleted` |
| `log_search` (`:93-101`) | `(ls_field, ls_value, ls_log_id)` — carries `associated_rev_id` (`ManualLogEntry.php:298-303`), maps log entries to revisions |
| `image`/`oldimage` (`:719-754`, `:634-671`) | media manifest, §3.5 |
| `page_props` (`:451-461`), `redirect` (`:145-155`) | current-state only, not versioned; marginal |

`ipblocks` is **not** wanted, per the brief — correct: it is block data about named people.

### 3.3 The MCR resolution chain (1.35+)

```
revision.rev_id  (or archive.ar_rev_id)
  → slots WHERE slot_revision_id = rev_id            -- one row per role
      slot_role_id    → slot_roles.role_name         -- 'main', …
      slot_content_id → content.content_id
          content_model → content_models.model_name
          content_sha1  -- base-36
          content_address → 'tt:<old_id>'
              → text WHERE old_id = <old_id>
                  old_text + old_flags → decode
```

**`content_address` formats in 1.38 are only `tt:<decimal old_id>`** (`SqlBlobStore.php:699-700`)
**and `bad:<urlencoded>`** (written by `maintenance/findBadBlobs.php:497`) ✅.
`SqlBlobStore.php:363-376` rejects anything else, and `:352` carries an explicit
`// TODO: MCR: also support 'ex' schema`. **So `es:`/`ES:` content addresses do NOT exist in
1.38** — external storage is signalled by `old_flags`, not by the address. (ES URLs move into
`content_address` only from 1.43.) The address grammar allows a `?k=v` query part
(`SqlBlobStore.php:713-722`).

**`old_flags`** is comma-separated (`SqlBlobStore.php:490-492`); decode order matters:

| Flag | Meaning | Action |
|---|---|---|
| `external` | `old_text` is a **URL**, not data (`:233`) | fetch first, then apply remaining flags to the fetched bytes (`:496-524`) |
| `gzip` | `gzdeflate()` | `gzinflate()` (`:588-596`) — **raw DEFLATE, not a zlib/gzip container** |
| `object` | PHP-serialized HistoryBlob | `unserialize()` then `->getText()` (`:600-608`) |
| `utf-8` (sometimes mis-written `utf8`, T18841) | content is UTF-8 | **absence** + `$wgLegacyEncoding` ⇒ iconv from the legacy charset (`:611-624`) |
| `error` | poisoned row | return false (`:583-586`) |

**External store** (`ExternalStoreDB.php:59-60,130,435-442` ✅): addresses are
`DB://<cluster>/<blob_id>[/<itemID>]`, resolved against a **separate cluster database**, table
`blobs (blob_id INT UNSIGNED AI PK, blob_text LONGBLOB)` (`maintenance/storage/blobs.sql:4-7`);
with an `itemID`, `blob_text` is unserialized and `->getItem($itemID)` called. `tables.json` notes
the `object` flag is *not* set for these, because the ES layer decompresses them itself.
⇒ **a full logical dump must include the ES cluster DBs, or those revisions are unrecoverable.**
Whether mw.lojban.org uses ES is unknown ⚠️ — ask, and check for `old_flags LIKE '%external%'`.

**HistoryBlob classes** (`includes/historyblob/` ✅): `ConcatenatedGzipHistoryBlob`
(`gzdeflate(serialize(hash→text))`, index by MD5 key); `HistoryBlobStub` (pointer
`{mOldId, mHash, mRef}` — re-read that `text` row, which may itself be `external`/`gzip`/`object`;
double-unserialize workaround at `:129-132`); `DiffHistoryBlob` (xdiff chains, needs
`xdiff_string_bpatch`); `HistoryBlobCurStub` (pre-1.5, unrecoverable). Pre-1.5 blobs may serialize
**lowercase class names**.

### 3.4 Revision metadata

* **Timestamp** `rev_timestamp` is TS_MW `YYYYMMDDHHMMSS`, **always UTC**
  (`rdbms/database/Database.php:4635-4639` ✅). Git author dates need `+0000`.
* **Actor**: anonymous ⇒ `actor_user IS NULL`, `actor_name` = the IP literal.
* **Comment**: when `comment_data` is non-NULL JSON, `comment_text` is the *already-localised*
  rendering — safe to use as-is.
* **`rev_deleted` bitfield** (`includes/Revision/RevisionRecord.php:53-58` ✅):
  `DELETED_TEXT=1`, `DELETED_COMMENT=2`, `DELETED_USER=4`, `DELETED_RESTRICTED=8`
  (`SUPPRESSED_USER=12`, `SUPPRESSED_ALL=15`). Publishing rule: bit 1 ⇒ do not publish content;
  bit 2 ⇒ blank the commit message; bit 4 ⇒ replace the author; **bit 8 (oversight) ⇒ omit the
  revision entirely** and record it in `_meta/wiki/gaps.csv` per `doc/SPEC.md:151`. `log_deleted`
  uses the same bits except bit 1 = `DELETED_ACTION` (`logging/LogPage.php:39-42`).
* **`rev_parent_id`** is the git parent edge and is *not* always the previous row by timestamp
  (imports, undeletes).
* **`rev_sha1`** = left fold of slot base-36 sha1s in role-name sort order, `base36(prev . next)`
  (`RevisionSlots.php:153-157,195-208,249-256` ✅); base-36 =
  `base_convert(sha1($blob), 16, 36, 31)`, 31 chars zero-padded (`SlotRecord.php:630-631`).
  **Use it as the integrity check after decoding a blob** — this is how we prove the dump path and
  the API path agree, satisfying the SPEC's determinism requirement (`doc/SPEC.md:143`).

### 3.5 `archive` and media

Deleted revisions are **moved** into `archive` keeping `ar_rev_id = rev_id`, and their
`slots`/`content`/`text` rows are **left in place keyed by `ar_rev_id`**
(`RevisionStore.php:1683` → `newRevisionSlots($row->ar_rev_id, …)`, `:1416-1440` ✅) — the identical
MCR chain, no `ar_text_id` path. A fully deleted page has archive rows and no `page` row, so the
title comes from `ar_namespace`/`ar_title`.

**Recommendation:** exclude `archive` by default (deleted revisions were withdrawn from public
view deliberately) but record their existence in `_meta/wiki/gaps.csv` so gaps are explainable.
Never project `ar_deleted & 8`.

**`logging`** matters for page identity: `move`/`move|move_redir` (params `4::target` = new
prefixed title, `5::noredir`; `log_page` is the moved page — `MovePage.php:899-910` ✅);
`delete`/`delete|restore|revision|event`; `merge`/`merge` (revisions re-parented retroactively);
`import`; `upload`. `log_params` is `serialize((array)$params)` (`logging/LogEntryBase.php:58-60`)
— **try `unserialize()`, and on failure treat it as a legacy `\n`-separated positional list**
(`DatabaseLogEntry.php:182-194` ✅). Modern keys are `N::name`.

**Media manifest.** `image` = current version only, PK `img_name` (the DB key); `oldimage` =
superseded versions keyed `oi_name` + `oi_archive_name` (`<TS_MW>!<basename>`), plus `oi_deleted`;
`filearchive` = deleted files (**treat as private**). Columns of interest: `img_size`,
`img_width/height/bits`, `img_media_type`, `img_major_mime`+`img_minor_mime`, `img_metadata`
(MEDIUMBLOB, JSON or serialized PHP, **may itself hold a `text`/ES address**),
`img_description_id`→`comment`, `img_actor`→`actor`, `img_timestamp`, `img_sha1` (base-36) ✅.
On-disk path (`FileRepo.php:769-781,223`; `File.php:1694-1696,1706-1715` ✅):
`$hash = md5($img_name)`, current = `<upload>/<h0>/<h0h1>/<img_name>`, old =
`<upload>/archive/<h0>/<h0h1>/<oi_archive_name>`, deleted =
`<deleted>/<k0>/<k1>/<k2>/<fa_storage_key>` at `deletedHashLevels = 3`.
**A SQL dump contains no file bytes** — the `images/` tree ships separately, or the manifest is
built from `imageinfo` URLs (4 808 images ✅ makes the manifest-only approach in
`doc/SPEC.md:143` clearly right).

### 3.6 `user`: public vs private

| Safe to publish | **Must be stripped** |
|---|---|
| `user_id`, `user_name`, `user_real_name`¹, `user_registration`, `user_editcount`, `user_touched`² | `user_password`, `user_newpassword`, `user_newpass_time`, `user_email`, `user_token`, `user_email_authenticated`, `user_email_token`, `user_email_token_expires`, `user_password_expires` |

¹ opt-in display name, still PII-adjacent. ² harmless but useless.
Note that `user_id`, `user_name`, `user_editcount` and `user_registration` are **already public**
via `api.php?action=query&list=allusers&auprop=editcount|registration` ✅ — so the only thing the
dump adds about users is the private half.

Other private tables that must never be in a dump handed to us: `user_properties`,
`user_former_groups`, `bot_passwords` (`bp_password`, `bp_token`), `ipblocks`,
`ipblocks_restrictions`, `watchlist`, `watchlist_expiry`, `user_newtalk`, `recentchanges`
(holds **`rc_ip`**), `ip_changes` (hex IPs), `filearchive`, `uploadstash`, and any CheckUser
extension tables (`cu_changes`, `cu_log`, `cu_private_event`).

### 3.7 Dump vs `Special:Export` vs API

| | `mysqldump` | `dumpBackup.php` / `Special:Export` | `api.php prop=revisions` |
|---|---|---|---|
| Full history | ✅ | ✅ (`WikiExporter::FULL`) | ✅, paginated |
| Deleted revisions | ✅ | ❌ | only `prop=deletedrevisions` + right |
| Suppressed content | ✅ **raw — dangerous** | masked `deleted="deleted"` (`XmlDumpWriter.php:356-376`) | masked |
| `rev_sha1` | ✅ | ✅ (`:402-410`) | with `rvprop=sha1` |
| Non-`main` slots | ✅ | schema **0.11** only (`:443-462`); default `$wgXmlDumpSchemaVersion = XML_DUMP_SCHEMA_VERSION_11` | needs `rvslots=*` |
| `slot_origin` | ✅ | ✅ (0.11 only) | ✗ |
| Log entries | ✅ | `dumpBackup.php --logs` only; `Special:Export` never | `list=logevents` |
| `page_props`, `redirect`, `page_restrictions` | ✅ | ❌ | partly via `prop=pageprops`/`info` |
| File binaries | ❌ | `--include-files` only | separate `imageinfo` fetch |
| Private `user` columns | ✅ (**the problem**) | ❌ | ❌ |

Caps ✅: `$wgExportMaxHistory = 0` (unlimited, but sites lower it), `$wgExportPagelistLimit = 5000`,
`$wgExportAllowAll = false`. API `rvlimit` max **500** (`LIMIT_BIG1`) / 5000 with `apihighlimits`
(`ApiBase.php:220-226`), dropping to **50/500 when content is requested**
(`ApiQueryRevisionsBase.php:220-247`); `rvlimit`/`rvstart`/`rvend` are **single-page-only**
(`ApiQueryRevisions.php:96,120-126`); payload capped by `$wgAPIMaxResultSize = 8388608`.

**Why the split in `doc/SPEC.md:143` is right:** the dump alone gives `slot_origin`, raw blob
flags, `archive`, `log_search` and byte-exact `old_text` — a faithful one-time backfill — but needs
DB access, is a privacy hazard and cannot be re-taken cheaply. The API is incremental,
permission-filtered (suppressed content never leaks) and rate-limited. **Use `rev_sha1` to verify
continuity at the seam.** Lensisku already runs this API path against this wiki (§2.8) ✅.

### 3.8 Namespaces

Canonical names are `NamespaceInfo::CANONICAL_NAMES` (`includes/title/NamespaceInfo.php:64-83`);
full title = `canonical + ':' + page_title` (empty prefix for NS 0). Odd namespaces are the talk
counterpart of the even one below. **`Talk:` pages are ordinary pages with their own `page_id` and
independent revision history** — not attached to the subject page in the DB, which is exactly why
`doc/SPEC.md:143` stores them as plain wikitext with no thread reconstruction.

**Live namespace map ✅** (`siprop=namespaces`) — note two entries the SPEC's list omits:

| id | name | case | id | name | case |
|---|---|---|---|---|---|
| 0 | *(main)* | **case-sensitive** | 12/13 | Help / Help talk | case-sensitive |
| 1 | Talk | case-sensitive | 14/15 | Category / Category talk | case-sensitive |
| 2/3 | User / User talk | first-letter | 200/201 | UserWiki / UserWiki talk | case-sensitive |
| 4/5 | **Lojban / Lojban talk** (`$wgSitename` project ns) | case-sensitive | **202/203** | **User profile / User profile talk** | case-sensitive |
| 6/7 | File / File talk | case-sensitive | 828/829 | Module / Module talk | first-letter |
| 8/9 | MediaWiki / MediaWiki talk | first-letter | | | |
| 10/11 | Template / Template talk | first-letter | | | |

⚠️ **Two corrections for `doc/SPEC.md:143`:** (a) namespaces **202/203 `User profile` /
`User profile talk`** are missing from the SPEC's namespace list; (b) **most namespaces on this
wiki are `case-sensitive`**, while 2/3, 8/9, 10/11, 828/829 are `first-letter`. The slug function
(`doc/SPEC.md:139`) must therefore be injective *per namespace* — two titles differing only in the
first letter's case are distinct pages in NS 0 but the same page in NS 2.

Capture `api.php?action=query&meta=siteinfo&siprop=namespaces` alongside any dump: a dump alone
does not carry the display names of custom namespaces ≥ 100.

### 3.9 Producing a safe dump

`mysqldump` cannot filter columns, only rows and tables — so `user` must be exported separately:

```bash
DB=my_wiki
MYSQLDUMP="mysqldump --single-transaction --quick --no-tablespaces \
  --default-character-set=binary --hex-blob --skip-extended-insert"

# 1) Everything needed for history, minus every table with private data.
$MYSQLDUMP $DB \
  page revision revision_actor_temp revision_comment_temp \
  slots slot_roles content content_models text comment actor \
  archive logging log_search page_props redirect page_restrictions \
  image oldimage change_tag change_tag_def category categorylinks \
  interwiki site_stats | gzip > wiki-content.sql.gz

# 2) The user table, column-filtered, as data only.
mysql --batch --raw $DB -e \
 "SELECT user_id, user_name, user_real_name, user_registration, user_editcount \
  FROM user" | gzip > wiki-users.tsv.gz

# 3) External-store clusters, only if $wgDefaultExternalStore is set.
$MYSQLDUMP <cluster_db> blobs | gzip > wiki-es-cluster1.sql.gz
```

`--hex-blob` is essential: `old_text` is a MEDIUMBLOB routinely holding raw DEFLATE bytes, which
will not survive a text-mode dump. `--default-character-set=binary` stops MySQL transcoding
VARBINARY columns.

If deleted history is out of scope, drop `archive` too and pre-filter `logging` with
`--where="log_deleted = 0"`. **Tell the operator explicitly** that `comment_text` and `log_params`
can contain text users typed about other people, and that `text` rows for `rev_deleted & 1`
revisions sit in the dump *in the clear* — masking is enforced by our projector, not by the dump.

---

## 4. Tiki Wiki (tiki.lojban.org)

Schema read from three vintages of the installer SQL: **1.9.11** (SourceForge tarball),
**2.4** and **3.9** (`github.com/tikiorg/tiki` branches `2.0`/`3.0` — note the canonical repo moved
to GitLab; `github.com/tikiwiki/tiki` is 404) ✅. **Caveat:** `tiki.lojban.org` today serves a
*modern* Tiki (`<meta name="generator" content="Tiki Wiki CMS Groupware - https://tiki.org">` ✅),
and `www.lojban.org/tiki/…` 301s to it. Which schema applies depends on the **vintage of the dump
we are handed**, not on the live site. The columns below are stable across 1.9→3.x; differences
are called out.

### 4.1 `tiki_pages` — the CURRENT version only

`db/tiki.sql:2431` (1.9) / `:2493` (2.x) / `:1750` (3.x) ✅.

| Column | Type | Meaning |
|---|---|---|
| `page_id` | `int(14)` AI PK | surrogate id |
| `pageName` | `varchar(160)` UNIQUE | the title — **the real join key**; `tiki_history` joins on this, not `page_id` |
| `data` | `text` (64 KB!) in 1.9 → `mediumtext` in 2.x/3.x | **current wiki markup** |
| `description` | `varchar(200)` | subtitle |
| `lastModif` | `int(14)` | unix epoch of the current version |
| `comment` | `varchar(200)` | edit summary **of the current version** |
| `version` | `int(8)` | current version number |
| `user` | `varchar(40)` → `varchar(200)` | login of last editor; NULL/'' = anonymous |
| `ip` | `varchar(15)` | editor IP — **strip** |
| `flag` | `char(1)` | `'L'` = locked |
| `creator` | `varchar(200)` | original creator's login |
| `created` | `int(14)` | page creation epoch |
| `is_html` | `tinyint(1)` | 1 = `data` is raw HTML, 0 = wiki markup — **carry into git**, it changes how the body must be read |
| `lang` | `varchar(16)` | language code |
| `page_size`, `hits`, `points`, `votes`, `pageRank`, `lockedby` | | metadata |
| `cache`, `wiki_cache`, `cache_timestamp` | `longtext`/int | rendered-HTML cache — **discard** |
| `wysiwyg`, `wiki_authors_style` | 2.x+ | |

`voteswanted` and `keywords` **do not exist** in any of 1.9/2.x/3.x ✅ (zero grep hits).

### 4.2 `tiki_history` — PRIOR versions only

`db/tiki.sql:1597` (1.9) / `:1640` (2.x) / `:1153` (3.x) ✅.

| Column | Type | Meaning |
|---|---|---|
| `historyId` | `int(12)` AI, **2.x+ only** (`db/tiki_1.9to2.0.sql:239` ✅) | |
| `pageName` | `varchar(160)` | PK part 1 |
| `version` | `int(8)` | PK part 2 |
| `version_minor` | `int(8)` | **vestigial**, always 0 ✅ |
| `lastModif` | `int(14)` | epoch that version was saved |
| `description` | `varchar(200)` | |
| `user` | `varchar(40)` → `varchar(200)` | author of that version |
| `ip` | `varchar(15)` | **strip** |
| `comment` | `varchar(200)` | edit summary of that version |
| `data` | **`longblob`** | markup — **binary type, no charset conversion** (see §4.6) |
| `type` | `varchar(50)`, 2.x+ | |
| `is_html` | `tinyint(1)`, **3.x only** (`installer/schema/20081027_wysiwyg_history_tiki.sql` ✅) | |

**The current version is NOT duplicated into `tiki_history`.** Verified in
`lib/tikilib.php:5913-6035` (`update_page`) and `:3933` (`create_page`) ✅: `create_page()` writes
`tiki_pages` at `version=1` with no history row; `update_page()` computes
`$old_version = MAX(tiki_history.version)+1`, writes the **new** content to `tiki_pages` at
`$old_version+1`, and inserts the **old** content into `tiki_history` at `$old_version`.

> **Reconstruction rule:** `SELECT … FROM tiki_history WHERE pageName=? ORDER BY version`, then
> append the `tiki_pages` row as the final version.

**Traps that will bite the projection** (all ✅):

1. **`version` is not dense or monotonic.** A history row is written only when
   `feature_wiki_history_full=='y' || data/description/comment changed`
   (`tikilib.php:5999`), but `tiki_pages.version` is incremented *unconditionally*. A no-op save
   bumps `version` with no history row; the next real save recomputes from
   `MAX(history.version)+1` and can produce a duplicate or lower number.
   **Sort by `lastModif`, use `version` only as a tiebreak.**
2. **Rollback rewrites metadata.** `lib/wiki/histlib.php:30` `use_version()` copies the old
   version's `data`, `lastModif`, `user`, `comment`, `ip` into `tiki_pages` and does
   `version = version+1`. After a rollback `tiki_pages.lastModif` is the *original* version's
   timestamp — so `lastModif` is not monotonic either.
3. **`pageName` is mutable** and is the join key; identity across a rename is recoverable only
   from `tiki_actionlog`. `SandBox` is excluded from history and the action log.
4. **1.9's `tiki_pages.data` is `text` = 65 535 bytes.** A page whose UTF-8 body exceeded 64 KB was
   silently truncated on save while its `longblob` history rows were not — look for a current
   version shorter than its predecessor.
6. Upstream's own comment (`tikilib.php:7651`, 3.x): *"tiki_history is also bugged as not all
   changes get stored in the history"* ✅.

### 4.3 Retention: unlimited by default, but check for gaps

| Preference | Default | Effect |
|---|---|---|
| `maxVersions` | **`0`** (`db/tiki.sql:4542` ✅) | `0` = unlimited. If > 0, each update deletes the oldest `count - maxVersions` rows **that also satisfy** `lastModif <= now - keep_versions*86400` |
| `keep_versions` | **`1`** day (`db/tiki.sql:4531` ✅) | floor: never delete versions younger than N days |
| `feature_wiki_history_full` | **`'n'`** (`tiki-setup.php:387` ✅) | `'y'` forces a history row on *every* save |

Pruning runs **inline in `update_page()` only** — there is no cron job ✅. Manual deletion via
`histlib::remove_version()` from `tiki-pagehistory.php`. **Stock settings retain everything**, and
gaps in the `version` sequence are the fingerprint of a site that changed `maxVersions`.

**Live spot-check ✅:** `tiki-pagehistory.php?page=How+to+use+xorlo` lists versions **26 down to 1
contiguously**, back to 2004-12-25, with date (GMT), user, IP and comment per row — no pruning on
that page. The page also exposes `…&clear_versions=1&show_all` (the admin prune action) and
`…&preview=<version>` to read one version.

### 4.4 `tiki_comments` — forum posts AND per-object comments

`db/tiki.sql:943` (1.9) / `:975` (2.x) / `:680` (3.x) ✅.

| Column | Type | Meaning |
|---|---|---|
| `threadId` | `int(14)` AI PK | post id — **every** post, topic or reply |
| `object` | `varchar(255)` | the `forumId` **as a string**, or the wiki `pageName`, or article/blog id |
| `objectType` | `varchar(32)` | `forum`, `wiki page`, `article`, `post`, `blog`, `faq`, `poll`, `image gallery`, `file gallery` ✅ |
| `parentId` | `int(14)` | `0` = top-level topic; else **the topic's `threadId`** (flat, not the immediate parent) |
| `userName` | `varchar(40)` → `varchar(200)` | author login; literal `'Anonymous'` when not logged in |
| `commentDate` | `int(14)` | unix epoch of posting — **never updated on edit** |
| `title` | `varchar(100)` → `varchar(255)` | subject line |
| `data` | `text` (64 KB) | body |
| `hash` | `varchar(32)` | `md5($title . $data)` **at post time**; a global duplicate guard. Not refreshed by `update_comment()`, so `hash != md5(title.data)` ⇒ **the post was edited** ✅ |
| `message_id` | `varchar(250)` → `varchar(128)` | RFC-822-ish; auto-built `"{userName}-{parentId}-{hash[0:10]}@{SERVER_NAME}"` if absent |
| `in_reply_to` | `varchar(250)` → `varchar(128)` | parent post's `message_id` — **this, not `parentId`, carries the reply tree** ✅ |
| `type` | `char(1)` | `'s'` = sticky, else `'n'` |
| `user_ip` | `varchar(15)` | **strip** |
| `summary`, `smiley`, `hits`, `points`, `votes`, `average`, `comment_rating` | | metadata |
| `archived` (2.x+), `approved` (3.x, default `'y'`), `locked` (3.x) | `char(1)` | moderation |

**Thread shape.** Topic: `objectType='forum'`, `object='<forumId>'`, `parentId=0`
(`commentslib.php:645-672` ✅). Reply: same `object`, `parentId = <threadId of the TOPIC>` —
`comments.php:190-196` explicitly substitutes the grandparent for forums ✅. Real nesting comes
from `in_reply_to → message_id`, self-joined within the same `parentId`
(`commentslib.php:1543-1556` ✅).

> **Rebuild rule:** group by `parentId`, link children via `in_reply_to → message_id`, fall back
> to flat chronological order (`commentDate`, tiebreak `threadId`) when `in_reply_to` is empty.

**The URL in the brief decodes as** ✅: `forumId=1` → `tiki_forums.forumId=1` →
`tiki_comments.object='1' AND objectType='forum'`; `comments_parentId=3348` → the **topic's
`threadId`** (`threadId=3348`, `parentId=0`). The page renders that row plus
`WHERE objectType='forum' AND object='1' AND parentId=3348`. The pretty form is
`forumthread<threadId>-<slug>` ✅.

**No comment revision history exists.** `update_comment()` (`commentslib.php:1744` ✅) overwrites
`title`/`data` in place, leaving `commentDate` and `hash` untouched. One commit per row is all
that is recoverable.

### 4.5 `tiki_forums` and the live forum inventory

`db/tiki.sql:1390` (1.9), 54 columns ✅. Relevant: `forumId` AI PK, `name`, `description text`,
`created`/`lastPost` `int(14)`, **`threads`** (topic count — *not* `numTopics`), **`comments`**
(post count — *not* `numComments`), `section`, `moderator`, `usePruneUnreplied`+`pruneUnrepliedAge`,
`usePruneOld`+`pruneMaxAge`, `approval_type`, attachment settings, and mail-gateway columns.

⚠️ **`usePruneOld='y'` + `pruneMaxAge` means old posts may already be gone** from `tiki_comments`.

**Private in this table:** `forum_password` (md5) and `inbound_pop_password` (**plaintext**) ✅.
Related: `tiki_forums_queue` (unapproved posts — content never published), `tiki_forum_reads`,
`tiki_user_postings`.

**Live inventory ✅** (`tiki-forums.php`): only three forums —

| forumId | Name | Posts | Note |
|---|---|---|---|
| 5 | Lojban In General | 2 892 | "A mirror of the main Lojban mailing list; post here go to the list, and vice versa" — **overlaps the mail source**; dedupe by `message_id` |
| 4 | Test | 29 | discard |
| 1 | **WikiDiscuss** | 5 578 | "Used for discussions attached to Wiki pages" — the one MediaWiki Talk pages point at |

Thread ids observed up to ~9 566 ✅. WikiDiscuss topics are auto-created with a stub first post
("Use this thread to discuss the page:: <pageName>") ✅, so the topic title is effectively the
wiki page name — a free `tiki_comments.title → tiki_pages.pageName` correspondence for
`_meta/tiki/`.

⚠️ **Attribution caveat:** a post in thread 9561 attributed to `userName='30Seconds'` is signed
`-- xorxes` in the body ✅ — gatewayed/relayed posts can carry the wrong `userName`. Do not treat
`userName` as authoritative for the mailing-list-mirror forum (id 5).

**MediaWiki → Tiki link count is small.** `list=exturlusage&euquery=lojban.org/tiki` returns only
**7** pages ✅ (e.g. `Talk:proga:LMW - Lojbanic MediaWiki` → `http://lojban.org/tiki/forum1`,
`Talk:BPFK Section: lerfu Forming cmavo` → `/tiki/BPFK+Procedures`). `insource:` is unavailable
(no CirrusSearch) ✅, so this is a floor, not a total — but the "Talk pages link to the forum"
premise is real yet **narrow**. The forum is worth projecting on its own merits (8 499 posts),
not because of the cross-links.

### 4.6 Users and privacy

`db/tiki.sql:4220` (1.9) / `:4443` (2.x) / `:3142` (3.x) ✅.

| Column | Share? |
|---|---|
| `userId`, `login` | ✅ — `login` is the join key to `tiki_pages.user`, `tiki_history.user`, `tiki_comments.userName` |
| `score` | ✅ |
| **`email`** | ❌ PII |
| **`password`** (`varchar(30)`, md5 or **plaintext** if `feature_clear_passwords`), **`provpass`**, **`hash`**, **`challenge`**, **`valid`** | ❌ credentials/tokens |
| `pass_due`/`pass_confirm`, `email_due`/`email_confirm` | ❌ |
| `lastLogin`, `currentLogin`, `registrationDate`, `created` | ⚠️ behavioural |
| `avatarData` (`longblob`) + `avatar*` | ⚠️ |
| `unsuccessful_logins`, `openid_url`, `waiting` (2.x+) | ❌/⚠️ |

> **Minimum safe projection of `users_users`: `userId` and `login` only.**

**`realName` is NOT a `users_users` column** ✅ — it lives in `tiki_user_preferences`
(`db/tiki.sql:3647`) as `(user, prefName, value)` where `user` is the **login**. The installer
seeds `('admin','realName','System Administrator')`. Two consent flags live there too:
`user_information` (`'public'`/`'private'`, default `'public'`) and `email is public`
(`'y'`/`'n'`, default `'n'`, honoured at `commentslib.php:1233`) ✅ — **honour both** when
deciding what to attribute publicly. Also `users_groups`, `users_usergroups`.

Strip IPs everywhere: `tiki_pages.ip`, `tiki_history.ip`, `tiki_comments.user_ip`,
`tiki_actionlog.ip`.

### 4.7 Other tables

| Table | Holds |
|---|---|
| `tiki_actionlog` (1.9 `:316`; redesigned 3.x `:192` with `actionId` PK + `object`/`objectType` + `tiki_actionlog_params`) | `action` (`Created`/`Updated`/`Removed version N`/`Changed actual version to N`), `lastModif`, `pageName`, `user`, `ip`, `comment`. **Best source for renames and deletions.** No PK in 1.9. |
| `tiki_wiki_attachments` (`:3885`) | `attId`, `page`, `filename`, `filetype`, `filesize`, `user`, `data longblob` (in-DB) or `path`, `created`, `comment`. Not versioned. |
| `tiki_page_footnotes` (`:2414`) | `(user, pageName, data)` — **per-user private notes**. Do not project. |
| `tiki_links` (`:1775`) | derived `(fromPage, toPage)` link graph — disposable |
| `tiki_semaphores` (`:2912`) | transient edit locks — disposable |
| `tiki_galleries`/`tiki_images`/`tiki_files` | media, blob or `path` |
| `tiki_comments_queue`, `tiki_forums_queue` | unapproved posts — **content never published**; exclude |
| `tiki_pages_translation_bits`, `tiki_pages_changes`, `tiki_translated_objects` | 3.x only, multilingual segments |

### 4.8 Timestamps: unix epoch seconds, true UTC

Every temporal column is `int(14)` — a MySQL *display width* on a 4-byte `INT`, not a length limit
(some importers mangle this) ✅. Writers use `date("U")` / `mktime()`
(`tikilib.php:5934`, `:3963`; `commentslib.php:1852`; `histlib.php:24,71` ✅), which return the
epoch and are therefore **timezone-independent**; only display was localised. Feed straight to
`git commit --date=@<value>`.

### 4.9 Encoding: latin1-declared columns holding UTF-8 bytes

Verified across all three vintages ✅: **no `CHARSET`/`COLLATE` clause anywhere** in `db/tiki.sql`
(grep count 0 in 1.9, 2.4, 3.9), so tables inherit the *server* default — `latin1` in the
2005–2010 era; **no `SET NAMES` on the connection** (`db/tiki-db.php`, `tiki-setup.php`), so bytes
pass through unconverted; but **the HTTP layer is hard-wired UTF-8** (`tiki-setup.php:23`,
`templates/header.tpl:11`). ⇒ latin1 columns holding raw UTF-8 bytes: benign in situ, broken on
dump/restore. **Observed live**: the WikiDiscuss topic list renders `Â¿QuÃ© es Lojban?` ✅ — real
double-encoding is already in the data, not merely a dump risk.

Detection in a dump: `SHOW CREATE TABLE` says `DEFAULT CHARSET=latin1`; `LENGTH(data)` equals
`CHAR_LENGTH(data)` even for non-ASCII text; `HEX(pageName) REGEXP 'C[23]'` matches accented titles.

**The asymmetry that will bite:** `tiki_pages.data` is `text` (a character type) but
`tiki_history.data` is `longblob` (binary). `mysqldump --default-character-set=utf8` **transcodes
the `text` column and passes the `longblob` through untouched**, so the current version and its own
history disagree byte-for-byte and every accented page gets a spurious final diff.

> **Required dump recipe:**
> `mysqldump --default-character-set=latin1 --skip-set-charset --hex-blob …`
> Then treat every recovered string as **raw bytes**; decode UTF-8 last, falling back to cp1252
> only on failure. Distinguish true double-encoding (bytes decode as UTF-8 *and* the result,
> re-encoded latin1 then decoded UTF-8 again, also succeeds with fewer `Ã`-class characters).

---

## 5. Event extraction, identity, and privacy

### 5.1 Event mapping per source

Column names below are the source's; `→` gives the git commit field per `doc/SPEC.md` §2.5/§3.

**jbovlaste** (`Source: dict`, layout `dict/<slug(word)>/`)

| Event | Source rows | Author | Date | Content | `Source-Id` |
|---|---|---|---|---|---|
| `created` (word) | `valsi` | `users.username` of `valsi.userid` | `valsi.time` (unix, **exact**) | `word.toml` (`word, type` from `valsitypes.descriptor`, `rafsi` split on space) | `valsi=<valsiid>` ⚠️ *new — SPEC has no valsi event; fold into the first definition commit or add one* |
| `created`/`edited` (definition) | `definitions` **+ its `keywordmapping` rows** | `users.username` of `definitions.userid` | `definitions.time` — **last-modified, not creation** | `<lang>-<definitionid>.md`: front matter from `definitions` + `languages.tag` + summed `definitionvotes.value`; body = `definition`, then `## Notes` = `notes` | `definition=<definitionid> version=0` (a synthetic v0 for the pre-Lensisku state) |
| `comment` | `comments` ⋈ `threads` | `users.username` of `comments.userid` | `comments.time` (**exact**) | append to `comments.md`: `## <ISO> — <author> (comment <commentid>, on definition <threads.definitionid>)`, `parentid != 0` ⇒ `(in reply to <parentid>)`; subject then `content` | `comment=<commentid>` |
| `vote-batch` | `definitionvotes` grouped by `date(time)` | `jbomohi` | the day | rewrite `votes.csv`, update `score` in front matter | `votes=<date>` |
| *(example)* | `example` | `users.username` of `userid` | `example.time` | ⚠️ **not in the SPEC layout** — propose `examples` in definition front matter or a per-definition `examples.md` | `example=<exampleid>` |
| *(etymology)* | `etymology` | ditto | `etymology.time` | ⚠️ likewise unplaced; `etymology` is per-`valsiid`, so `word.toml` is the natural home | `etymology=<etymologyid>` |
| *(jbovlaste wiki)* | `pages` (all versions) | `users.username` of `pages.userid` | `pages.time` | decompress if `compressed` (`base64` → `zlib`) | ⚠️ out of scope of `dict/`; a fourth wiki, currently unprojected |

**Time confidence.** Word creation and comments/examples/etymology/votes are `exact`. Definition
`created`/`edited` is **`window`** wherever the row has been edited (indistinguishable from a
creation), which is most of them — record this in `_meta/dict/coverage.toml` per `doc/SPEC.md:195`.

**Lensisku** (same `Source: dict`, continuing the same files)

| Event | Source rows | Author | Date | Content | `Source-Id` |
|---|---|---|---|---|---|
| `edited` (definition) | `definition_versions` | `users.username` of `user_id` | `created_at` (timestamptz, **exact**) | rewrite `<lang>-<definition_id>.md` from `definition, notes, selmaho, jargon, rafsi, etymology, gloss_keywords, place_keywords` | `definition=<definition_id> version=<version_id>` |
| `edited` (wiki-sourced) | `definition_versions` **WHERE `mw_revid IS NOT NULL`** | ditto | ditto | ⚠️ **skip** — these are mw.lojban.org revisions re-imported by `src/wiki/importer.rs`; projecting them would duplicate the `wiki/` source | — |
| `comment` | `comments` (post-V81 JSONB) | as jbovlaste | `time` | subject from `comments.subject`; body from the `text` blocks of `content` (**drop the `header` block**, §2.4) | `comment=<commentid>` |
| `vote-batch` | `definitionvotes` | `jbomohi` | day | as jbovlaste | `votes=<date>` |

Commit subject: use `definition_versions.message` (the user-supplied edit summary) — this is the
one source of the four that has a real commit message.

**MediaWiki** (`Source: wiki`) — per `doc/SPEC.md:151`, one commit per `revision` row:

`page` ⋈ `revision` ⋈ (`revision_actor_temp`→`actor` | `rev_actor`→`actor`) ⋈
(`revision_comment_temp`→`comment` | `rev_comment_id`→`comment`) ⋈ `slots` ⋈ `content` ⋈ `text`.
Author `actor_name` (or the IP literal); date `rev_timestamp` (TS_MW, UTC, `exact`); content the
decoded `main`-slot blob; `Source-Id: revid=<rev_id>`, plus `Page-Id: <page_id>`,
`Parent-Rev: <rev_parent_id>`. `Event:` from `logging` (`move` ⇒ `moved` + `Moved-From:`,
`delete` ⇒ `deleted`), else `created` when `rev_parent_id = 0`, else `edited`.
`rev_deleted` drives masking (§3.4); bit 8 ⇒ the revision goes to `_meta/wiki/gaps.csv` only.

**Tiki** (`Source: tiki`)

| Event | Source rows | Author | Date | Content | `Source-Id` |
|---|---|---|---|---|---|
| page version 1..N-1 | `tiki_history` ORDER BY `lastModif`, `version` | `tiki_history.user` (login) | `lastModif` (unix, **exact**) | `tiki/<slug(pageName)>.tiki` = `data` (longblob → bytes) | `tiki=<pageName>@<version>` |
| page version N (current) | `tiki_pages` | `tiki_pages.user` | `tiki_pages.lastModif` | `tiki_pages.data` | `tiki=<pageName>@<version>` |
| forum post | `tiki_comments` WHERE `objectType='forum'` | `userName` (⚠️ unreliable for forum 5, §4.5) | `commentDate` (unix, **exact**) | append to `tiki/forums/<forum>/<threadId-of-topic>.txt`; `title` + `data` | `tiki=forum/<threadId>` |
| page comment | `tiki_comments` WHERE `objectType='wiki page'` | `userName` | `commentDate` | ⚠️ **not in the SPEC layout** — propose `tiki/talk/<slug(object)>.txt` | `tiki=comment/<threadId>` |

Commit subject uses `tiki_pages.comment` / `tiki_history.comment` (the edit summary) for pages and
`tiki_comments.title` for posts. Rename/delete events come from `tiki_actionlog` only.

### 5.2 Identity namespaces

| Source | Placeholder | Notes |
|---|---|---|
| MediaWiki | `<user_name>@mw.lojban.org` | anonymous edits: `actor_user IS NULL` ⇒ `actor_name` is an IP. **Do not put a contributor IP in a git author field**; use `anonymous@mw.lojban.org` and keep the IP out of the repo entirely |
| Tiki | `<login>@tiki.lojban.org` | display name from `tiki_user_preferences (user=<login>, prefName='realName')`, **not** `users_users`. `'Anonymous'` is a literal login value ⇒ `anonymous@tiki.lojban.org`. Honour `user_information='private'` |
| jbovlaste | `<username>@jbovlaste.lojban.org` | display name from `users.realname` |
| **Lensisku** | **`<username>@jbovlaste.lojban.org` — the same namespace** ✅ | Lensisku *is* the jbovlaste database migrated forward (§2.1): same `users` table, same `userid`s, same usernames. Do **not** mint a `@lensisku.lojban.org` namespace; it would split one person's history across two identities at the 2024 seam. |

Three namespaces for four sources, deliberately *not* unified: `who/` (`doc/SPEC.md:213`) is where
a person's aliases across MediaWiki, Tiki, jbovlaste and mail get attested. Resolving them at
projection time would be an unrecorded editorial judgement.

### 5.3 Private columns — the "never leaves the owner's machine" list

| Source | Never export |
|---|---|
| **jbovlaste** | `users.password` (MD5 of rot13'd password), `users.email`; treat `users.votesize` as private (the schema calls it "the secret size of their vote") |
| **Lensisku** | `users.password` (**still accepts the jbovlaste MD5 hashes**, `src/auth/service.rs:63-72` ✅), `users.email`, `users.email_confirmation_token`; and the whole of `user_sessions`, `user_session_events`, `password_reset_requests`, `password_change_verifications`, `oauth_accounts`, `private_messages`, `message_threads`, `thread_participants`, `user_message_blocks`, `payments`, `balance_transactions`, `paypal_subscriptions`, `payment_audit_log`, `user_search_history` |
| **MediaWiki** | `user_password`, `user_newpassword`, `user_newpass_time`, `user_email`, `user_token`, `user_email_authenticated`, `user_email_token`, `user_email_token_expires`, `user_password_expires`; tables `user_properties`, `user_former_groups`, `bot_passwords`, `ipblocks`, `ipblocks_restrictions`, `watchlist`, `watchlist_expiry`, `user_newtalk`, `recentchanges` (`rc_ip`), `ip_changes`, `filearchive`, `uploadstash`, `cu_*` |
| **Tiki** | `users_users.password` (**may be plaintext** if `feature_clear_passwords`), `.provpass`, `.hash`, `.challenge`, `.valid`, `.email`, `pass_confirm`/`email_confirm`; `tiki_forums.forum_password` and **`inbound_pop_password` (plaintext)**; `tiki_page_footnotes` (private per-user notes); `tiki_comments_queue`/`tiki_forums_queue` (never-published content). Minimum safe `users_users` projection: `userId`, `login` |
| **All four** | **Contributor IP addresses**: `tiki_pages.ip`, `tiki_history.ip`, `tiki_comments.user_ip`, `tiki_actionlog.ip`, MediaWiki `rc_ip` / `ip_changes` / anonymous `actor_name`. None of these belong in a public git repository, in commits or in `_meta/`. |

Two further cautions that are about *data we do want*, not columns to drop: MediaWiki
`comment_text`/`log_params` and Tiki `comment`/`data` fields contain free text users typed about
each other, and `text` rows for `rev_deleted & 1` revisions arrive in the dump **in the clear** —
masking is enforced by our projector, not by the dump.

### 5.4 Open items for `doc/SPEC.md`

1. **§3.2 namespace list** omits MediaWiki namespaces **202/203 (`User profile`,
   `User profile talk`)** ✅, and the slug function needs to be injective *per namespace* because
   most namespaces on this wiki are `case-sensitive` while 2/3, 8/9, 10/11, 828/829 are
   `first-letter` ✅.
2. **§3.5 has no home for jbovlaste `example` or `etymology` rows**, both of which are dated,
   attributed events the XML export drops — they are among the few things a dump uniquely buys.
3. **jbovlaste's own `pages` wiki** (versioned, with a compression scheme) is a fourth wiki that
   no section currently covers.
4. **§3.2.5 assumes `tiki_history` is the whole story**; it is versions 1..N-1 only, and `version`
   is neither dense nor monotonic (§4.2).
5. The dictionary **`Event-Window`** case is the common case, not the exception: every jbovlaste
   definition never edited under Lensisku has no version row at all (§2.2).
6. **Votes**: `doc/SPEC.md:195` says "voter as published by the source". No Lensisku endpoint
   publishes voter identity (§2.6) — so from the API the column is always empty, and from a dump
   it is a deliberate disclosure decision, not a default.
