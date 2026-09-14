# Database export request — for the lojban.org server operator

Purpose: jbomo'i (`https://github.com/int19h/jbomohi`) republishes the Lojban community's **public** record as a git repository with one commit per source event (wiki revision, definition edit, comment, …). Everything that is publicly visible on the sites goes in; everything that is not (passwords, e-mails, tokens, sessions, private messages, payments, IP addresses, unpublished/queued content, per-user notes, per-voter vote rows) must never leave your machine. The commands below produce exactly that split. Details and the reasoning behind every table are in `doc/research/dump-schemas.md` in the repository (verified against the jbovlaste, Lensisku, MediaWiki 1.38 and Tiki sources).

Three databases are wanted; one dump each, gzip'd, with a `sha256sum` line for each file (a `SHA256SUMS` file next to the dumps is ideal). Rough sizes: Lensisku/jbovlaste tens of MB, MediaWiki a few hundred MB (the `text` table), Tiki tens of MB. Any transfer method is fine (a URL behind HTTP auth, scp, …); the files are consumed locally and are never checked into git or uploaded to CI.

---

## 1. Lensisku (this is also the jbovlaste data)

Lensisku's PostgreSQL database (`lojban_lens`) *is* the jbovlaste database migrated in place (same `users`, `valsi`, `definitions`, `comments`, `definitionvotes` tables and ids), so one dump covers both. If a separate, frozen jbovlaste database still exists as well (a `jbovlaste` database distinct from `lojban_lens`), please dump it the same way (§1b) — it is the only place a pre-migration state could differ; if `lojban_lens` is the only one, §1b does not apply.

```sh
DB=lojban_lens   # the Lensisku database (contains the migrated jbovlaste tables)

# a) everything except the tables that hold private data
pg_dump -Fp --no-owner --no-privileges --exclude-table-data='*' --schema-only "$DB" > lensisku-schema.sql
pg_dump -Fp --no-owner --no-privileges --data-only \
  -T users -T users_view -T definitionvotes -T natlangwordvotes \
  -T user_sessions -T user_session_events -T password_reset_requests -T password_change_verifications \
  -T oauth_accounts -T private_messages -T message_threads -T thread_participants -T user_message_blocks \
  -T message_encryption_keys -T message_notifications -T webrtc_signaling \
  -T payments -T balance_transactions -T paypal_subscriptions -T payment_audit_log -T user_balances \
  -T user_search_history -T assistant_chats -T user_notifications -T user_settings -T user_profile_images \
  -T valsi_subscriptions -T follows -T comment_bookmarks -T comment_opinion_votes -T comment_reactions \
  -T flashcards -T flashcard_levels -T flashcard_level_items -T flashcard_quiz_options -T flashcard_review_history \
  -T user_flashcard_progress -T user_level_progress -T user_quiz_answer_history -T level_prerequisites \
  -T collections -T collection_items -T collection_images -T collection_item_images -T collection_item_sounds \
  -T cached_dictionary_exports -T wiki_articles -T wiki_sync_state \
  "$DB" > lensisku-public-data.sql

# b) the public columns of users, as data only (no password, no email, no tokens, no votesize)
psql "$DB" -c "\copy (SELECT userid, username, realname, url, personal, created_at, role, disabled FROM users) TO 'lensisku-users-public.csv' CSV HEADER"

# c) vote totals only — voter identity is not public in either application
psql "$DB" -c "\copy (SELECT definitionid, valsiid, langid, SUM(value) AS score, COUNT(*) AS votes, MAX(time) AS last_vote_time FROM definitionvotes GROUP BY definitionid, valsiid, langid) TO 'lensisku-definition-scores.csv' CSV HEADER"

gzip lensisku-schema.sql lensisku-public-data.sql
sha256sum lensisku-*.gz lensisku-*.csv
```

The exclusion list is the union of what the source schema and the 2026-09-13 export showed: everything per-user (chats with the site's AI assistant, notifications, settings, avatars, balances, subscriptions, follows, bookmarks, reactions, flashcard/quiz progress, collections — including private ones — and `users_view`, which exposes the private `votesize`), plus caches and the MediaWiki mirror we take from the source. If any table name above does not exist in your version, just drop that `-T` (a missing exclusion is harmless only if the table is absent; please do not remove an exclusion for a table that exists). If there are other tables you consider private, exclude them too and tell us their names.

### 1b. A separate jbovlaste database, if one still exists

```sh
DB=jbovlaste
pg_dump -Fp --no-owner --no-privileges -T users -T definitionvotes -T natlangwordvotes "$DB" | gzip > jbovlaste-public.sql.gz
psql "$DB" -c "\copy (SELECT userid, username, realname, url, personal FROM users) TO 'jbovlaste-users-public.csv' CSV HEADER"
psql "$DB" -c "\copy (SELECT definitionid, valsiid, langid, SUM(value) AS score, COUNT(*) AS votes, MAX(time) AS last_vote_time FROM definitionvotes GROUP BY definitionid, valsiid, langid) TO 'jbovlaste-definition-scores.csv' CSV HEADER"
```

---

## 2. MediaWiki (mw.lojban.org, 1.38.7 / MariaDB)

`mysqldump` cannot filter columns, so the `user` table is exported separately with only its public columns.

```sh
DB=my_wiki   # adjust
MYSQLDUMP="mysqldump --single-transaction --quick --no-tablespaces \
  --default-character-set=binary --hex-blob --skip-extended-insert"

# a) everything needed to reconstruct every revision of every page
$MYSQLDUMP $DB \
  page revision revision_actor_temp revision_comment_temp \
  slots slot_roles content content_models text comment actor \
  archive logging log_search page_props redirect page_restrictions \
  image oldimage change_tag change_tag_def category categorylinks \
  interwiki site_stats | gzip > wiki-content.sql.gz

# b) the user table, public columns only
mysql --batch --raw $DB -e \
  "SELECT user_id, user_name, user_real_name, user_registration, user_editcount FROM user" \
  | gzip > wiki-users.tsv.gz

# c) only if $wgDefaultExternalStore is set in LocalSettings.php: the external-store cluster(s)
# $MYSQLDUMP <cluster_db> blobs | gzip > wiki-es-cluster1.sql.gz

sha256sum wiki-*.gz
```

`--hex-blob` and `--default-character-set=binary` are essential: `text.old_text` holds compressed binary and must not be transcoded. Tables deliberately **not** requested: `user_properties`, `user_former_groups`, `bot_passwords`, `ipblocks*`, `watchlist*`, `user_newtalk`, `recentchanges`, `ip_changes`, `filearchive`, `uploadstash`, `objectcache`, `cu_*`, and any `user` column other than the five above. Two notes: `archive` (deleted revisions) is requested because deleted-then-restored history matters, but drop it if you prefer; revisions with `rev_deleted` bits are masked by our importer, not by the dump, so the dump does contain them in the clear — treat the file accordingly.

---

## 3. Tiki (tiki.lojban.org, the pre-2013 wiki)

The Tiki tables are `latin1`-declared but hold UTF-8 bytes, and `tiki_history.data` is a blob while `tiki_pages.data` is text, so the character-set flags below are required or the current version and its own history will disagree byte-for-byte.

```sh
DB=tiki   # adjust
MYSQLDUMP="mysqldump --single-transaction --quick --no-tablespaces \
  --default-character-set=latin1 --skip-set-charset --hex-blob --skip-extended-insert"

# a) pages, history, forums/comments, action log, categories, links
$MYSQLDUMP $DB \
  tiki_pages tiki_history tiki_comments tiki_actionlog \
  tiki_categories tiki_category_objects tiki_links tiki_wiki_attachments \
  tiki_pages_translation_bits tiki_translated_objects \
  | gzip > tiki-content.sql.gz
# (drop any table that does not exist in your Tiki version)

# NOT tiki_forums: it holds forum_password and a PLAINTEXT inbound_pop_password.
# Export only its public columns instead:
mysql --batch --raw $DB -e \
  "SELECT forumId, name, description, created, lastPost, comments, threads, moderator, section FROM tiki_forums" \
  | gzip > tiki-forums.tsv.gz

# b) users: login only, plus the public preference rows (real name, "information public/private")
mysql --batch --raw $DB -e "SELECT userId, login FROM users_users" | gzip > tiki-users.tsv.gz
mysql --batch --raw $DB -e \
  "SELECT user, prefName, value FROM tiki_user_preferences WHERE prefName IN ('realName','user_information','email is public')" \
  | gzip > tiki-user-preferences.tsv.gz

sha256sum tiki-*.gz
```

Deliberately **not** requested: every other `users_users` column (`password`, `provpass`, `hash`, `challenge`, `valid`, `email`, login timestamps, avatars), the whole `tiki_forums` table (see above — its password columns cannot be filtered by `mysqldump`), `tiki_page_footnotes` (private per-user notes), `tiki_comments_queue` / `tiki_forums_queue` (never-published posts), `tiki_semaphores`, session/login tables, galleries and file blobs. The requested tables contain IP columns (`tiki_pages.ip`, `tiki_history.ip`, `tiki_comments.user_ip`, `tiki_actionlog.ip`); if you can null them before dumping (`UPDATE … SET ip=''` on a copy) please do — otherwise our importer discards them and they never enter the repository.

---

## 4. Nothing else is needed from the server

Mailing lists come from the public `mail.lojban.org/lists-plain/*.maildir.zip` files and the MHonArc pages; IRC logs from `lojban.org/irclogs/`; ongoing wiki updates from the API and dictionary updates from Lensisku's public `/api/jbovlaste/changes` feed. If the `lists-plain` zips are regenerated on a schedule, knowing the cadence would help; if `llg-members`/`llg-board` are ever meant to be public, their `lists-plain` directories would be picked up automatically.
