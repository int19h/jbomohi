# Lojban mailing-list email: archive inventory

**Purpose.** Decide what a projection/ingest tool should scrape, in what order, and how to
deduplicate across archives that are different views of the same messages.

**Method.** Everything below marked *verified* was fetched over HTTP on **2026-08-27** (UTC)
with `curl` / WebFetch and the observation is quoted. Items marked *inferred* are conclusions
drawn from verified evidence but not directly observed. No item is reported from memory.

---

## 0. Executive shape of the corpus

There are effectively **four physical corpora** and several derived views:

1. **`mail.lojban.org` Maildir store** (`/lists-plain/`) — raw RFC 822, live, bulk-downloadable.
   *This is the primary source.*
2. **`mail.lojban.org` MHonArc HTML render** (`/lists/`) — a de-duplicated HTML view of (1)
   plus ten lists that have **no** `/lists-plain/` equivalent.
3. **`www.lojban.org/files/lojban-list/`** — the 1989–2000 monthly archives (mbox `.gz`, plus
   degraded `.ZIP` text for 1998-10…2000-01). Ancestor of (1)/(2) for the early era.
4. **`mail.lojban.org/lists/old_lojban-list/`** — 19,674 raw eGroups/Yahoo-Groups files,
   1998-11-04 → 2003-05-07. Ancestor of (1)/(2) for the Yahoo era.

Derived views that add **no new messages**: `lensisku.lojban.org` (a Postgres index over the
`lojban-list` Maildir), Google Groups (upstream of the 2011-09→ traffic, which is relayed into
(1) and (2) with headers intact), and the Wayback Machine's thin Yahoo Groups captures.

---

## 1. Master table

| # | Archive | URL | Lists covered | Date range (verified) | Message count | Format | Message-ID / In-Reply-To / References recoverable? | Bulk download? | Duplicates which archive? |
|---|---|---|---|---|---|---|---|---|---|
| A | mail.lojban.org MHonArc | `https://mail.lojban.org/lists/<list>/` | 21 public lists + 2 × 401 (see §2) | 1989-12-07 → 2025-08-26 (`lojban-list`) | ~187k msg pages across all lists (per-list in §2) | MHonArc 2.5.13–2.6.24 HTML, `index.html`/`mailN.html`/`threads.html`/`msgNNNNN.html` | **Yes.** `<!--X-Message-Id: …-->`, one `<!--X-Reference: …-->` per References entry, and `<li><em>In-reply-to</em>: &lt;…&gt;</li>` in the head-of-message list. 20/20 sampled `lojban-list` pages had X-Message-Id. | No archive-level tarball; must crawl `msgNNNNN.html` (numbering is dense — see §2.3) | De-dup'd render of B (for the 13 lists that exist in both) |
| B | mail.lojban.org Maildir ("lists-plain") | `https://mail.lojban.org/lists-plain/<list>/maildir/{cur,new}/` | 14 public + 8 × 401 (see §3) | `lojban-list` 1989-12-07 → 2025-08-26 | `lojban-list` 107,669 files (92,674 `cur` + 14,995 `new`); others in §3 | **Raw RFC 822**, one file per message, Apache directory listing enabled | **Yes, everything** — full original headers incl. all `Received:`, `List-Id:`, `DKIM-Signature:` | **Yes** — per-list `<list>.maildir.zip` (see §3 for sizes) **and** per-file HTTP | Superset of A; contains **~45 % duplicate copies in the pre-1995 era** (§8) |
| C | lojban.org 1990s file server | `https://www.lojban.org/files/lojban-list/` | `lojban-list` only | 1989-12 → 2000-01 (87 monthly files) | 87 archives; ~25 messages in the smallest (`lojban-8912`) | 74 × `.gz` = **Unix mbox** with full headers; 14 × `.ZIP` + 1 × `.zip.gz` = **eGroups web-scrape text**, no headers | `.gz`: **yes** (real `Message-Id:`). `.ZIP`: **no** — entries look like `#260 / 5:05 PM Thu 1 Oct 98 / Subject: … / From: paul.stadle-` (truncated address, no Message-ID) | Yes, 87 small files, ~9 MB total | Ancestor of A/B for 1989-12…1998-04; the `.ZIP` era overlaps D and is strictly worse |
| D | `old_lojban-list` raw eGroups export | `https://mail.lojban.org/lists/old_lojban-list/<N>` (N = 1…19674) | `lojban-list` @ onelist→eGroups→Yahoo | **1998-11-04 → 2003-05-07** (file `1` and file `19674` inspected) | **19,674** files (directory listing has 19,675 `<li>` incl. Parent Directory) | **Raw RFC 822** with mbox `From ` line; eGroups artefacts (`X-Digest-Num`, `X-eGroups-From`, `X-Apparently-To: lojban@yahoogroups.com`), sender addresses munged to `xxxxx.xxxx.xxxx` in the `From ` line only | **Yes** — `Message-ID`, `References`, `In-Reply-To` all present in file 19674 | No zip; 19,674 individual GETs | Ancestor of A/B for 1998-11…2003-05; supersedes C's `.ZIP` files |
| E | `lojban-list-old` MHonArc | `https://mail.lojban.org/lists/lojban-list-old/` | `lojban-list` | 1989-12-08 → ≥2021-03-07 (tail entries carry unparseable `Thu, 1 Jan 70` dates) | index: **80,203**; `msgNNNNN.html` exists up to **80226** → 80,227 files | MHonArc (mixed 2.5.13 / 2.6.24 — rebuilt incrementally) | Yes, same comment structure as A | Crawl only | **Near-duplicate of A.** Both `index.html` files were last modified 2024-10-05; A has 79,108 pages, E has 80,227. *Inferred:* E is the pre-rebuild generation kept alongside the rebuilt A. |
| F | `jbosnu_raw.zip` | `https://mail.lojban.org/lists/jbosnu_raw.zip` | `jbosnu` | ≤2004-06-22 (zip mtime) | 449,913 bytes | **MH folder** (contains `jbosnu_raw/.mh_sequences`), raw RFC 822 per file | Yes (raw) | **Yes**, one 440 KB zip | Raw form of the `jbosnu` MHonArc archive (A) |
| G | lensisku mail index | `https://lensisku.lojban.org/api/…` | `lojban-list` only | **1989-12-07 → 2025-08-26** (API `sort_by=date`) | **107,674** rows (`/api/waves/search?search=&source=mail&per_page=1` → `"total":107674`) | JSON API; `Message` object = `{id, message_id, date, subject, cleaned_subject, from_address, to_address, parts_json, file_path, spam_vote_count}` | **Message-ID yes** (`"message_id":"<…@…>"`). **In-Reply-To / References: NO** — not in the schema; threading is by *normalised subject* (`/api/mail/thread?subject=…`) | **No** — pagination is broken: `page=2` returns `items: []` (verified). Max 100 rows per query. | **Pure view of B.** `/api/mail/message/1` returns `"file_path":"cur/1721701740.3712622_25.lebna:2,"` — literally a `lists-plain/lojban-list/maildir` filename. |
| H | Google Groups `lojban` | `https://groups.google.com/g/lojban` | main list, 2011-09 → present | oldest visible topic in first page 2021-09; newest 2025-04 | **14,225 conversations** (rendered page: "1–30 of 14225") | JS web UI; no RSS (`/forum/feed/lojban/msgs/rss.xml` → **HTTP 404**) | **No.** UI shows author display-names and dates only; Message-ID is not exposed. Export is **owner-only** (Google Takeout for group owners). | No | **Upstream of A/B from 2011-09.** Verified: `lojban-list/msg65942.html` carries `List-Id: <lojban.googlegroups.com>`, `X-BeenThere`, `List-archive: http://groups.google.com/group/lojban`; and the thread "nice sound for lojban 'r'" (1/3/12) is visible in both g/lojban and `lojban-list` msg65904…65942. |
| I | Google Groups `lojban-beginners` | `https://groups.google.com/g/lojban-beginners` | beginners list | topics visible 2017-10 → 2024-10 | **2,267 conversations** | as H | as H | No | Upstream of A/B `lojban-beginners`; verified via `List-id: <lojban-beginners.googlegroups.com>` on `lojban-beginners/msg20909.html` (2024-10-21) |
| J | Google Groups `bpfk-list` | `https://groups.google.com/g/bpfk-list` | BPFK | 2016-03 → 2021-04 visible | **538** items ("1–30 of 538") | as H | as H | No | Upstream of A/B `bpfk`; verified via `List-id: <bpfk-list.googlegroups.com>` on `bpfk/msg02360.html` (2021-04-18) |
| K | Google Groups `lojban-announcements` | `https://groups.google.com/g/lojban-announcements` | LLG announcements | **2010-04 → 2025-12** | **34** conversations | as H | as H | No | Upstream of B's `lojban-announcements` maildir (44 files) |
| L | Google Groups `jboske` | `https://groups.google.com/g/jboske` | — | — | — | — | — | — | **Not publicly readable**: renders "Content unavailable". Use A's `jboske` instead. |
| M | Wayback Machine, Yahoo Groups | `http://web.archive.org/web/*/groups.yahoo.com/group/lojban*` | lojban, lojban1, jbosnu, jboske, lojban-java, lojban-beginners, lojban-announce | 2001-05-11 (first HTTP 200) → 2021-02 (redirect stubs) | **562** distinct URLs under `groups.yahoo.com/group/lojban*`, of which only **111 are HTTP 200** and only a handful are `/message/N` pages (e.g. `20010626215441 …/lojban/message/1643 200`). `jboske` 47 URLs, `jbosnu` 74, `lojban-java` 80, `lojban-beginners` 2, `lojban-announce` 1, `bpfk` **0**. | Wayback HTML captures of the Yahoo web UI | Poor — Yahoo's UI never showed Message-ID | via Wayback API only | **Redundant.** Everything in this window is in D at far higher fidelity. |
| N | Archive Team "Yahoo Groups" rescue | `https://archive.org/details/yahoo-groups-2015-12-18T23-49-46Z-h0tp9q` and 3 sibling items (`…2016-10-09T09-02-28Z-2138ac`, `…2017-03-24T19-40-09Z-3f5f7f`, `…2017-06-30T19-39-39Z-c0fed7`), collection `archiveteam_yahoogroups` | unknown / mixed | — | 4 items matched `lojban AND (yahoogroups OR egroups)` in the IA full-text index | WARC packs | *Inferred:* not per-group; extraction would require WARC scanning | Yes but enormous | *Inferred:* redundant with D |
| O | onelist.com archive | `http://www.onelist.com/archive/lojban` | lojban-list | pointer dated "since 5 November 1998" in `lojban.org/files/roadmap.html` | — | — | — | **Dead** — all Wayback captures are HTTP 302/999, no content | Superseded by D (whose file `1` is dated **1998-11-04**, matching the pointer) |

---

## 2. `mail.lojban.org/lists/` — MHonArc, per list

### 2.1 Directory listing (verified, HTTP 200, 2026-08-27)

`https://mail.lojban.org/lists/` lists **23 directories + 1 zip**:
`announce, bpfk-announce, bpfk, dracyselkei, jbofongri, jboske, jbosnu, jbosnu_raw.zip,
jbovlaste, lbck, llg-board, llg-members, lojban-beginners, lojban-de, lojban-es, lojban-fr,
lojban-list-old, lojban-list, lojban_story, old_lojban-list, pod, wikichanges, wikidiscuss,
wikineurotic`.

`llg-board/` and `llg-members/` return **HTTP 401**, `WWW-Authenticate: Basic realm="LLG
Members -- Ask the board for access"`. Everything else is 200.

### 2.2 Per-list figures

"Index count" = `(last_page − 1) × 100 + entries_on_last_page`, read off `index.html`'s
`[Last Page]` link. "Max msg" = highest `msgNNNNN.html` that returns 200 (binary search).
Dates are the `<!--X-Date: …-->` of the first entry of `index.html` and the last entry of the
last page.

| List | Index count | Max msg → files | First message | Last message | Notes |
|---|---|---|---|---|---|
| `announce` | 81 | — | 2003-05-17 | 2009-11-30 | Mixed: early `To: announce@lojban.org`, later `To: lojban-lbck@googlegroups.com`; msg00001 is CJK spam |
| `bpfk` | 2,361 | 2360 → 2,361 | 2003-03-28 | 2021-04-18 | = Google Group `bpfk-list` from ~2016 |
| `bpfk-announce` | 428 | — | 2003-03-28 | 2008-11-21 | |
| `dracyselkei` | 22 | — | 2007-09-14 | 2007-10-01 | Role-playing-game list, 3 weeks of life |
| `jbofongri` | 168 | — | 2004-04-14 | 2011-06-02 | Mostly spam by subject |
| `jboske` | 2,479 | 2478 → 2,479 | 2001-08-27 | 2003-04-30 | Only public copy (Google Group L is unavailable) |
| `jbosnu` | 489 | — | 2000-01-24 | 2003-10-17 | `To: jbosnu@yahoogroups.com` — a Yahoo Group. Raw form = F |
| `jbovlaste` | 1,501 | 1500 → 1,501 | 2004-11-18 | 2021-08-01 | Latest msgs carry `List-id: <mailman.thrivology.org>` — list moved to a Mailman at `thrivology.org`, which now **401s** (redirects to `greendesigncenter.org`) |
| `lbck` | 147 | — | 2009-12-01 | 2016-08-05 | Lojban Beginner/Certification (`lojban-lbck@googlegroups.com`) |
| `lojban-beginners` | **15,496** | **20909 → 20,910** | 2002-09-16 | 2024-10-21 | ⚠ **5,414 message files are not in the date index.** Crawl by number, not by index. |
| `lojban-de` | 142 | — | 2010-03-24 | 2024-11-20 | Tail is spam |
| `lojban-es` | 384 | — | 2003-05-20 | 2023-03-01 | |
| `lojban-fr` | 453 | — | 2003-05-16 | 2023-03-01 | |
| `lojban-list` | 79,091 | **79107 → 79,108** | **1989-12-07** (`msg00434`) | **2025-08-26** (`msg79107`) | Numbering is **dense** (44 random probes, 0 missing). `msg00000` = 2011-09-21 → archive was seeded at the Google-Groups cutover and history back-imported later |
| `lojban-list-old` | 80,203 | **80226 → 80,227** | 1989-12-08 (`msg49433`; `msg00000` **404s**) | ≥2021-03-07 | Near-duplicate of `lojban-list` |
| `lojban_story` | 195 | — | 2001-08-23 | 2006-07-31 | |
| `pod` | 1,847 | 1846 → 1,847 | 2002-08-21 | 2004-09-17 | `pod@lojban.org` — CLL print-on-demand logistics |
| `wikichanges` | 2,892 | 2891 → 2,892 | 2011-09-26 | 2015-12-01 | Automated wiki-diff mail |
| `wikidiscuss` | 50 | — | 2011-11-01 | 2015-12-01 | Mostly Mailman reminders |
| `wikineurotic` | 2,889 | — | 2011-09-26 | 2015-12-01 | Automated wiki-diff mail |
| `llg-board` | — | — | — | — | **401** |
| `llg-members` | — | — | — | — | **401** |

### 2.3 Page structure (verified on `lojban-list/msg00434.html`, `msg65942.html`)

```
<!-- MHonArc v2.6.24 -->
<!--X-Subject: Re: [lojban] nice sound for lojban "r" -->
<!--X-From-R13: … -->                       ← ROT-13'd From, decodable
<!--X-Date: Mon, 09 Jan 2012 03:18:15 -0800 -->
<!--X-Message-Id: CAMKwHj2iLRq…@mail.gmail.com -->
<!--X-Content-Type: multipart/alternative -->
<!--X-Reference: 3add2d11-…@u6g2000vbc.googlegroups.com -->   ← one per References entry
…
<!--X-Head-End-->
… <li><em>In-reply-to</em>: &lt;CAKv2tT4…@mail.gmail.com&gt;</li> …
<!--X-Body-of-Message--> <pre>…</pre> <!--X-Body-of-Message-End-->
```

Notes for a scraper:
* `X-Message-Id` and `X-Reference` values are **unbracketed** and HTML-entity-escaped
  (`&#45;` for `-`, `&#60;` for `<`). Normalise before use.
* Only `index.html` + `mailN.html` (N ≥ 2) exist; `maillist.html`, `author.html`,
  `subject.html`, `mail1.html` all **404**. `threads.html` exists (200).
* Index pages hold exactly 100 entries. Index order is by date, **message numbers are not
  chronological** (history was back-imported in batches).
* Pages are served as ISO-8859-1 but bodies contain raw legacy bytes (GB2312/Big5 spam, etc.).
  Treat as bytes, not UTF-8.

---

## 3. `mail.lojban.org/lists-plain/` — the Maildir store

`https://www.lojban.org/lists-plain/lojban-list/` **301-redirects** to
`http://mail.lojban.org/lists` (verified) — the useful path is on the `mail.` host:
`https://mail.lojban.org/lists-plain/`.

Index (verified) contains 23 entries: `backup-2024-07-22/, bpfk/, jbovlaste-admin/, jbovlaste/,
lbck/, llg-board/, llg-members/, lojban-announcements/, lojban-beginners/, lojban-de/,
lojban-es/, lojban-fr/, lojban-list/, special-fulfillment/, special-lojban/, special-president/,
special-secretary/, special-treasurer/, special-vp/, special/, wikichanges/, wikidiscuss/,
wikineurotic/`.

**401:** `llg-board`, `llg-members`, `special`, `special-lojban`, `special-president`,
`special-secretary`, `special-treasurer`, `special-vp`.

Each open list is `<list>/maildir/{cur,new,tmp}/` (Apache listing enabled, so every filename is
enumerable) **plus** `<list>/<list>.maildir.zip`.

| List | `cur` | `new` | Total files | zip | zip size | zip last-modified | MHonArc counterpart (§2.2) |
|---|---|---|---|---|---|---|---|
| `lojban-list` | 92,674 | 14,995 | **107,669** | `lojban-list.maildir.zip` | 329,942,488 B | **2026-08-26** | 79,108 (A) / 80,227 (E) |
| `lojban-beginners` | 12,750 | 3,873 | 16,623 | ✓ | 67,234,601 B | 2026-08-26 | 20,910 files / 15,496 indexed |
| `jbovlaste-admin` | 10,118 | 70,397 | **80,515** | ✓ | 106,059,930 B | 2026-08-26 | **none** — automated jbovlaste notifications |
| `wikichanges` | 0 | 2,892 | 2,892 | ✓ | 31,857,940 B | 2024-07-23 | 2,892 ✓ |
| `wikineurotic` | 0 | 2,889 | 2,889 | ✓ | 31,757,333 B | 2024-07-23 | 2,889 ✓ |
| `bpfk` | 1,033 | 1,370 | 2,403 | ✓ | 16,039,837 B | 2024-07-23 | 2,361 |
| `jbovlaste` | 331 | 1,175 | 1,506 | ✓ | 3,388,955 B | 2026-08-26 | 1,501 |
| `lojban-fr` | 223 | 229 | 452 | ✓ | 995,489 B | 2026-08-26 | 453 |
| `lojban-es` | 242 | 141 | 383 | ✓ | 585,098 B | 2026-08-26 | 384 |
| `lbck` | 111 | 35 | 146 | ✓ | 402,208 B | 2024-07-23 | 147 |
| `lojban-de` | 1 | 140 | 141 | ✓ | 893,676 B | 2026-08-26 | 142 |
| `wikidiscuss` | 0 | 51 | 51 | ✓ | 59,152 B | 2024-07-23 | 50 |
| `lojban-announcements` | 27 | 17 | **44** | ✓ | 141,819 B | 2024-07-23 | **none** (≠ `/lists/announce`) |
| `special-fulfillment` | 0 | 0 | 0 | ✓ | 166 B (empty) | 2024-07-23 | none |

The near-equality of the last ten rows with §2.2 is the evidence that **A is a render of B**.
`lojban-list` and `lojban-beginners` are the exceptions (B is much larger; see §8).

### `lists-plain/lojban-list/` also holds three snapshot zips

| File | Size | Last-modified | Contents (first entries read via HTTP Range) |
|---|---|---|---|
| `lojban-list.maildir.zip` | 329,942,488 B | 2026-08-26 | `maildir/`, `maildir/cur/1721701740.3712622_25.lebna:2,` … — the live Maildir |
| `lojban-list-backup-2024-07-22.zip` | 332,004,898 B | 2024-07-23 | contains a nested `lojban-list.maildir.zip` **and** `maildir/new/…` |
| `lojban-list-backup-before-changes-2024-10-09.zip` | 332,008,264 B | 2024-11-03 | same shape; snapshot taken just before the 2024-10-05 MHonArc rebuild |
| `lojban-list-up-to-2018-08-12.zip` | 369,913,294 B | 2018-08-12 | **month-partitioned Maildirs**: `2011-09/`, `2011-09/cur/1316738767.5812_1.stodi.digitalkingdom.org:2,` … — i.e. **starts at 2011-09**, the Google-Groups cutover |

So the 2018 zip is *not* a superset of the 2024 one for pre-2011 mail; it only covers
2011-09 → 2018-08 but keeps the original per-month layout and the original Maildir filenames
(`…@stodi.digitalkingdom.org`), which the 2024 rebuild destroyed (all files were re-stamped
`1721701740.*.lebna`). It is therefore worth keeping for provenance, not for coverage.

---

## 4. `www.lojban.org/files/` — the 1990s file server

`https://www.lojban.org/files/roadmap.html` (verified) says, under `lojban-list:`

> "Files are named by year and month… Because of apparent inconsistencies in the automated
> archives due to missing and damaged messages, starting in November 1998 the archives contain
> two separate versions of each month's archive. onelist.com has a searchable archive covering
> the period since 5 November 1998 at http://www.onelist.com/archive/lojban"

`https://www.lojban.org/files/lojban-list/` (verified) contains **89 entries**: 87 monthly
archives + `dates.gz` + `subjects.gz`.

* **74 × `lojban-YYMM.gz`**, `8912` … `9804` (plus oddities `9507b`, `9508x`, `9509x` — the
  "two separate versions" mentioned above). `gunzip -c lojban-8912.gz` yields a **real Unix
  mbox**: `From KFL@ai.ai.mit.edu Thu Dec  7 12:19:41 1989` + full `Received:`/`Message-Id:`
  headers; 25 `^From ` lines in that month.
* **14 × `lojban-YYMM.ZIP`** (`9810` … `9911`) + `lojban-9912.zip.gz` + `lojban-0001.ZIP`.
  These contain files like `LOJL1098.TXT` whose records are **eGroups web-scrape text**:
  `#260` / `5:05 PM Thu 1 Oct 98` / ` Subject: Web Presence` / ` From: paul.stadle-`.
  **No Message-ID, truncated senders, minute-resolution timestamps.** Do not ingest these when
  `old_lojban-list` covers the same month.
* `dates.gz` is a human-written index ("Note - these are just rough guesses because some of the
  archives are not entirely in date order  -Erik") giving first/last `Date:` per file — a cheap
  way to plan the mbox era. `subjects.gz` (22 K) is a subject listing.
* Also on the file server but **not mailing-list mail**: `/files/jl/` (ju'i lobypli JL1–JL18,
  le lojbo karni LK8–LK11 + LK18, ASCII, `.ZIP` and `.txt.gz`), `/files/texts/archives/`
  (26 per-author `.ZIP` text collections: `COWAN.ZIP`, `NICK.ZIP`, `XORXES.ZIP`, …),
  `/files/history/`, `/files/papers/` (incl. `4thtense`, described as "A lengthy discussion
  from Lojban List"). These are edited compilations, not archived email; treat as a separate
  corpus.

**Overlap check (verified):** `lojban-8912.gz`'s first message is
`Message-Id: <676765.891207.KFL@AI.AI.MIT.EDU>`, `Date: Thu, 7 Dec 89 00:33:01 EST` — the same
message as `lojban-list/msg00434.html` (`<!--X-Message-Id: 676765.891207.KFL@AI.AI.MIT.EDU-->`)
and the oldest row in lensisku. So C's mboxes are the source of A/B's pre-1998 content, and
`lojban.org/files` adds no unique messages there — but it is the only place where the early
material exists in **native mbox** form.

---

## 5. Yahoo Groups / eGroups / onelist era (≈1998–2011)

**Yes, the main list was there.** Verified from `old_lojban-list/1`:

```
From cowan@xxxxx.xxxx.xxxx Wed Nov 4 11:48:27 1998
X-Digest-Num: 0
Message-ID: <44114.0.1.959273823@eGroups.com>
Date: Wed, 04 Nov 1998 14:48:27 -0500
Subject: Preliminary test message
```

and `old_lojban-list/19674`:

```
X-Apparently-To: lojban@yahoogroups.com
Received: (EGP: mail-8_2_6_6); 8 May 2003 01:18:06 -0000
Message-ID: <20030508011759.GA20466@ccil.org>
References: <20030507224737.GE7295@digitalkingdom.org>
In-Reply-To: <20030507224737.GE7295@digitalkingdom.org>
```

So `lojban@onelist.com` → `lojban@egroups.com` → `lojban@yahoogroups.com`, **1998-11-04 →
2003-05-07**, and the LLG kept a **complete raw export** of it as `old_lojban-list` (19,674
files). This is why the roadmap's dead onelist pointer says "since 5 November 1998".

`jbosnu` was also a Yahoo Group (`To: jbosnu@yahoogroups.com`, 2000-01 → 2003-10), preserved
both as MHonArc (`/lists/jbosnu/`, 489 msgs) and raw (`/lists/jbosnu_raw.zip`, MH folder).

**BPFK was never on Yahoo** — `bpfk` starts 2003-03-28 on lojban.org and moves to Google Groups
`bpfk-list`; Wayback has **0** URLs under `groups.yahoo.com/group/bpfk*`.

**archive.org holdings:** nothing per-group. The only IA items matching
`lojban AND (yahoogroups OR "yahoo groups" OR egroups)` are four Archive Team WARC packs
(`yahoo-groups-2015-12-18T23-49-46Z-h0tp9q`, `yahoo-groups-2016-10-09T09-02-28Z-2138ac`,
`yahoo-groups-2017-03-24T19-40-09Z-3f5f7f`, `yahoo-groups-2017-06-30T19-39-39Z-c0fed7`,
collection `archiveteam_yahoogroups`). *Inferred:* these are opportunistic UI crawls, and
anything in them is already in `old_lojban-list`. **No Mark-Fletcher-era export exists as a
distinct public item.** The Wayback Machine's own coverage is thin (§1 row M).

---

## 6. Google Groups

`lojban@googlegroups.com` became the transport in **September 2011** and is relayed into
`mail.lojban.org` with headers intact. Verified end-to-end:

* `mail.lojban.org/lists/lojban-list/msg00000.html` — the archive's message #0 — is dated
  **2011-09-21**, and lensisku's `/api/mail/message/1` is
  `<1f80cb56-…@l4g2000vbz.googlegroups.com>`, 2011-09-21, subject "Should we have another
  mailing list for abstruse discussions?".
* `msg65942.html` (2012-01-09) carries `To: lojban@googlegroups.com`, `Sender:`,
  `Mailing-list: list lojban@googlegroups.com`, `List-id: <lojban.googlegroups.com>`,
  `List-archive: <http://groups.google.com/group/lojban?hl=en_US>`, plus its own
  `In-reply-to:` and an 11-entry `References:`.
* The same thread — **"nice sound for lojban 'r'", 1/3/12** — is visible on
  `groups.google.com/g/lojban` via search. Same subject, same start date, same participants
  (`buro…@yahoo.co.uk`, Pierre Abbat). **Confirmed duplicate.**

| Group | Conversations | Range seen | Public? | Export |
|---|---|---|---|---|
| `lojban` | 14,225 | first page 2021-09 → 2025-04; about page: "The main Lojban discussion list", anyone on the web can view/post/join | Yes | owner-only |
| `lojban-beginners` | 2,267 | 2017-10 → 2024-10 visible | Yes | owner-only |
| `bpfk-list` | 538 | 2016-03 → 2021-04 | Yes | owner-only |
| `lojban-announcements` | 34 | 2010-04 → 2025-12 | Yes | owner-only |
| `jboske` | — | — | "Content unavailable" | — |

Google Groups has **no RSS/Atom** any more (`/forum/feed/…/rss.xml` → 404) and no Message-ID in
the UI. **Recommendation: do not scrape Google Groups.** Every message it holds is already in B
with better metadata; the only thing it would add is post-2025-08 traffic, and even that arrives
in `lists-plain/lojban-list/maildir/new/` (the newest `new/` file sampled was 2025-06-26 and the
maildir zip is regenerated — mtime 2026-08-26).

---

## 7. lensisku

* Spec: `https://lensisku.lojban.org/api-docs/openapi.json` (267 KB, OpenAPI 3.1, 176 paths).
  **API base is `/api/`**, not the documented bare path — `/waves/search` serves the SPA shell,
  `/api/waves/search` serves JSON.
* Mail endpoints: `GET /api/waves/search?search=&source={all|jbotcan|comments|mail}&page&per_page&sort_by&sort_order`,
  `GET /api/mail/message/{id}`, `GET /api/mail/thread?subject=…&include_content=`,
  `POST /api/mail/messages/{id}/spam-vote`.
* Coverage: `source=mail` total **107,674**; oldest `1989-12-07T05:33:01Z`
  (`<676765.891207.KFL@AI.AI.MIT.EDU>`), newest `2025-08-26T07:51:43Z` (a phishing mail —
  the tail of the corpus is spam). **`"dot side"` → `total: 2515`**, matching the figure
  observed earlier.
* Stores `message_id` verbatim (angle brackets included) and `file_path` relative to the
  Maildir. Does **not** store `In-Reply-To`/`References`; `/api/mail/thread` groups by
  normalised subject only.
* **Not usable for bulk export:** `page=2` returns zero items (verified for both `asc` and
  `desc`), so at most 100 rows are reachable per distinct query. Use it for *search* and for
  cheap Message-ID spot checks, not for acquisition.
* It indexes **only `lojban-list`** — no `bpfk`, `jboske`, `lojban-beginners` rows were
  observed and there is no list/source selector beyond `jbotcan|comments|mail`.

---

## 8. Duplication inside the primary corpus (important)

The `lojban-list` Maildir is a **merge of at least three source archives** and was never
de-duplicated:

* Sampling the 100 oldest rows via lensisku (`sort_by=date&sort_order=asc`):
  **55 distinct Message-IDs among 100 rows — 45 % are extra copies**, with up to **5 copies**
  of a single message (`<9005151721.AA29466@julia.math.ucla.edu>`, `<9005181343.AA06252@cs.NYU.EDU>`).
* Sampling the 100 newest rows: **99 distinct of 100** — the modern era is clean.
* A 2003 example with two copies differing only in `Subject` prefix:
  `<LPBBJKMNINKHACNDIIGMKEKIHGAA.a.rosta@lycos.co.uk>` appears as both
  `RE: [lojban] Re: valfendi algorithm` and `[lojban] Re: valfendi algorithm` — i.e. one copy
  from the local mbox feed and one from the Yahoo/eGroups feed, which rewrote subjects.
* By contrast the **MHonArc render is de-duplicated**: 83 consecutive `lojban-list`
  message pages (`msg00434`…`msg00519`) yielded **83 distinct Message-IDs, 0 duplicates**.

Hence: `107,669` Maildir files → `79,108` MHonArc pages. The ~28.5 k difference is duplicates
plus messages MHonArc dropped (empty/undecodable). **Estimated unique lojban-list messages:
≈ 79 k**, of which a non-trivial tail (post-2016) is spam.

---

## 9. What to scrape, in what order, and how to dedupe

### 9.1 Acquisition plan

**Tier 1 — bulk download, no scraping (do this first).**

| Order | What | How | Yield |
|---|---|---|---|
| 1 | `lists-plain/lojban-list/lojban-list.maildir.zip` | one GET, 330 MB | 107,669 raw messages, 1989-12→2025-08, the whole main list |
| 2 | `lists-plain/{lojban-beginners,bpfk,jbovlaste,lojban-de,lojban-es,lojban-fr,lbck,lojban-announcements,wikichanges,wikidiscuss,wikineurotic}/<list>.maildir.zip` | 11 GETs, ~150 MB | 27,527 raw messages |
| 3 | `lists/old_lojban-list/1…19674` | 19,674 GETs (small, no zip) | Yahoo-era raw, 1998-11→2003-05 |
| 4 | `lists/jbosnu_raw.zip` | one GET, 440 KB | jbosnu raw |
| 5 | `www.lojban.org/files/lojban-list/lojban-*.gz` (74 files) + `dates.gz` | 75 GETs, ~9 MB | native mbox 1989-12→1998-04 |
| — | *skip* `jbovlaste-admin` (80,515 automated notifications) unless wanted | | |

**Tier 2 — MHonArc crawl, only for lists with no `lists-plain` counterpart.**
`announce` (81), `bpfk-announce` (428), `dracyselkei` (22), `jbofongri` (168), `jboske`
(2,479), `jbosnu` (489 — or use the raw zip), `lojban_story` (195), `pod` (1,847).
**≈ 5,709 pages total.** Crawl `msgNNNNN.html` **by number from 0 upward until 404**, not via
the index — `lojban-beginners` proves the index can be short by 26 % (15,496 indexed vs 20,910
files). Honour `www.lojban.org`'s `Crawl-Delay: 5` in spirit (`mail.lojban.org/robots.txt`
returns 403, i.e. no policy); a 200–500 ms delay is polite for a single-host crawl.

**Tier 3 — gap-fill only.**
* `lists/lojban-list-old/` (80,227 pages) — crawl **only** to find Message-IDs absent from
  Tier 1; it is a stale generation of the same archive.
* `lists/lojban-beginners/msg*.html` — worth a full crawl anyway (20,910 pages) because the
  Maildir holds only 16,623 files; the two differ and neither is a superset.
* `www.lojban.org/files/lojban-list/*.ZIP` (1998-10…2000-01) — **only** if a month turns out
  to be missing from `old_lojban-list`; the records have no Message-ID and must be matched
  heuristically.

**Never scrape:** Google Groups (H–K), Wayback Yahoo captures (M), Archive Team WARCs (N),
onelist (O), lensisku bulk (G — pagination broken). `llg-board`, `llg-members`, `special*`,
and `thrivology.org`'s jbovlaste Mailman are behind HTTP 401 and need a credential from the
LLG board.

**Not email, out of scope (noted for completeness):** ju'i lobypli / le lojbo karni newsletters
(`/files/jl/`), `/files/texts/archives/` per-author compilations, the Wikispaces-era wiki (only
its *notification* mail survives, as `wikichanges`/`wikineurotic`/`wikidiscuss`), the `conlang`
list's Lojban threads (a separate corpus, hosted elsewhere), Discord and Telegram.

### 9.2 Dedupe keys

1. **Primary key: normalised Message-ID.**
   `strip <>` → `trim` → `unescape HTML entities` (MHonArc emits `&#45;`, `&#60;`, `&#62;`)
   → `NFC` → **case-fold the domain part only** (the local part is case-sensitive per RFC 5322,
   but observed data mixes case: `676765.891207.KFL@AI.AI.MIT.EDU` in the mbox vs the same id
   in MHonArc). In practice folding the whole id is safer and has not been observed to collide.
2. **Prefer the copy with the most headers.** Rank sources:
   `lists-plain Maildir` > `old_lojban-list` / `jbosnu_raw` > `files/*.gz` mbox >
   `MHonArc msg page` > `files/*.ZIP` text. Keep the winner's raw bytes; keep the losers'
   provenance record only.
3. **Fallback when Message-ID is absent** (only the `files/*.ZIP` eGroups text, and a handful of
   malformed 1970-dated messages in `lojban-list-old`): hash
   `(normalised_subject, from_localpart, date_truncated_to_minute, first_200_chars_of_body_after_whitespace_collapse)`.
   Normalised subject = strip leading `Re:`/`RE:`/`Fwd:` runs and `[lojban]`, `[jbosnu]`,
   `[POD]`, `[lojban-story]` style tags — the same normalisation lensisku exposes as
   `cleaned_subject`, which can be used as a cross-check.
4. **Do not** dedupe on subject alone. The Yahoo relay rewrote subject prefixes
   (`RE: [lojban] Re: X` vs `[lojban] Re: X` for one Message-ID), and `[no subject]` is common
   in the 1989–1992 material.
5. **Threading:** build from `References` (all `X-Reference` comments, in order) with
   `In-Reply-To` as fallback; MHonArc preserves both. Do **not** use lensisku's subject-threading
   — it merges unrelated threads that share a cleaned subject.
6. **Flag, don't drop, spam.** `announce/msg00001`, the `lojban-de`/`jbofongri` tails and the
   post-2016 `lojban-list` tail are bulk spam that reached the list; the archive's own tail
   (2025-08-26) is a phishing mail. Keep with a `spam_suspect` flag; lensisku's
   `spam_vote_count` is a usable prior.

### 9.3 Estimated unique message counts

| List | Best source | Raw items | **Estimated unique** | Confidence |
|---|---|---|---|---|
| `lojban-list` (1989-12→2025-08) | Maildir zip | 107,669 | **≈ 79,000** | high — MHonArc's de-dup'd render is 79,108 and sampled MHonArc blocks are duplicate-free |
| `lojban-beginners` | Maildir ∪ MHonArc | 16,623 ∪ 20,910 | **≈ 21,000** | medium — the two disagree; union needed |
| `jbovlaste-admin` | Maildir zip | 80,515 | ≈ 80,000 | high (machine-generated, unlikely duplicated) — *exclude by default* |
| `jboske` | MHonArc crawl | 2,479 | 2,479 | high |
| `bpfk` | Maildir zip | 2,403 | ≈ 2,361 | high |
| `wikichanges` | Maildir zip | 2,892 | 2,892 | high |
| `wikineurotic` | Maildir zip | 2,889 | 2,889 | high |
| `pod` | MHonArc crawl | 1,847 | 1,847 | high |
| `jbovlaste` | Maildir zip | 1,506 | ≈ 1,501 | high |
| `lojban-fr` / `lojban-es` / `bpfk-announce` | Maildir / MHonArc | 452 / 383 / 428 | 453 / 384 / 428 | high |
| `jbosnu` | raw zip | 489 | 489 | high |
| `lojban_story` / `lbck` / `lojban-de` / `announce` / `jbofongri` / `wikidiscuss` / `lojban-announcements` / `dracyselkei` | as tabled | 195 / 147 / 142 / 81 / 168 / 51 / 44 / 22 | same | high |
| `llg-board`, `llg-members`, `special*` | — | — | **unknown (401)** | — |

**Total, excluding `jbovlaste-admin`: ≈ 118,000 unique messages**; including it, ≈ 198,000.
Human-authored discussion (excluding `jbovlaste-admin`, `wikichanges`, `wikineurotic`,
`wikidiscuss`) is **≈ 112,000**.
