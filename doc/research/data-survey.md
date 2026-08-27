# jbomo'i data survey — what already exists on this machine

Surveyed 2026-08-26. All paths absolute. Token estimates are bytes/4 unless stated.
Nothing outside `~/git/jbomohi/tmp/fable/` was modified.

Three byte-identical copies of the IRC+mail bundle exist (`~/lojban/disc`, `~/git/lojban-disc`,
`~/build/prov/{irc,mail}`), and two of the wiki snapshot (`~/lojban/wiki`, `~/git/lojban-wiki`).
`~/lojban/*` is the canonical fast copy (the `~/git` ones are on a slow virtiofs share — see §3).

---

## 1. IRC logs — `/home/int19h.linux/lojban/disc/irc/`

| file | size | notes |
|---|---|---|
| `all_logs.txt` | 73,173,505 B (70 MiB), **1,151,468 lines** | single concatenated file, mtime 2026-08-16 |
| `irclogs.zip` | 18 MiB | contains exactly one member: `all_logs.txt` (same 73,173,505 B) |
| `raw/` | 86 MiB, 287 dirs, 7,853 files | one dir per month `YYYY_MM` (2003-01 … 2026-08) plus `2000_all`, `2002_middle`, `2002_12`; one file per day |

**Token estimate:** ~18.3 M tokens for `all_logs.txt`. Message lines (containing `<nick> `): 1,033,923;
`/me` actions: ~8,200; server/system lines (`***`, join/quit): ~3,000 (raw has ~3,255 → mostly already stripped).
Distinct `<nick>` strings: ~7,449 (upper bound, includes bridge-mangled nicks). 90 NUL bytes in the file (use `grep -a`).

**Channels:** essentially one channel, `#lojban` on freenode (later Libera; topic lines: `sterling.freenode.net has changed the topic to "Lojban - http://www.lojban.org/ …"`). Mentions of `#ckule`, `#jbosnu`, `#jbopre` appear only in-text. **However** the first 51,004 lines of `all_logs.txt` are a *separate, undated-header block* that is not in `raw/`: it runs 2010-11-24 → 2026-08 (starts `2010-11-24 10:07:46 EST/-0500 <Twey> coi jbosnu`), contains bridge relays like `<||> <11uakci>: …` and `<xxxx> <la kanba>: …`, and is almost certainly the **#jbosnu** log (~46.5k dated lines). Verify before ingesting; it must be split out or the timeline will be non-monotonic (the #lojban part starts at line 51,005).

**Date range:** 2000-05-26 → 2026-08-16. Gap: 2000-10-28 → 2002-05-12 (nothing). Coverage thins after 2017.
Lines per year (dated lines only): 2003 13.7k · 2005 26.7k · 2008 75k · 2010 89k · **2012 137k (peak)** · 2014 100k · 2015 108k · 2016 68k · 2017 18k · 2019 11k · 2020 17.6k · 2022 11k · 2024 2.1k · 2025 1.7k · 2026 (to Aug) 0.96k.

**Four line formats over time** (counts from `all_logs.txt`):

| era | format | example | lines |
|---|---|---|---|
| 2000-05 → 2000-10 | `[HH:MM] <nick> msg` (no date in line; date from filename) | `[00:38] <rlpowell> coi uacort.` | 16,659 |
| 2002-05 → 2010-10-01 | `DD Mon YYYY HH:MM:SS <nick> msg` (TZ unknown/implicit) | `31 Dec 2002 14:28:57 <rlpowell> coi xod.` | 348,750 |
| 2010-10-02 → present | `YYYY-MM-DD HH:MM:SS PDT/-0700 <nick> msg` (explicit TZ) | `2014-03-01 04:07:13 PST/-0800 <gleki> ma prali tu'a lo BNF genturfa'i` | 693,044 |
| 2015-05 → 2015-07 only | irssi: `HH:MM < nick> msg`, with `--- Log opened …` / `--- Day changed Tue Jun 02 2015` markers | `11:51 < gleki> exp: lo ka mo e lo ka mo` | 87,499 |

The irssi block is `raw/2015_0{5,6,7}/lojban-special.2015.0N.log` (21,774 + 39,157 + 26,645 lines) and fills a gap when the
main logger was down (only 2,740 ISO-format lines exist for May–Jul 2015; `raw/2015_06/` has only 2 daily files). Its per-line
dates must be reconstructed from the `Day changed` markers (29 in June).

Other quirks: actions are `* nick does x`; bridged users (Telegram/Discord relay) appear as `<xxxx_> <la cenzis>: …` /
`<kahai> <05syski'os>: …` (mIRC colour codes `\x0305` inside nicks); bot `mensi` posts parse trees.
`raw/*` concatenated = 1,100,469 lines vs 1,151,468 in `all_logs.txt` (difference ≈ the 51k #jbosnu prefix).

Sample 10 lines (2003, 2011, 2026):
```
31 Dec 2002 05:25:35 *** sterling.freenode.net has changed the topic to "Lojban - http://www.lojban.org/ - …"
31 Dec 2002 14:28:57 <rlpowell> coi xod.
31 Dec 2002 14:29:01 <xod> coi coi
2011-10-31 15:25:30 PDT/-0700 <mouk> vlabacru zo ai ma
2012-08-09 13:22:02 PDT/-0700 <selpa`i> .i je'u gy sampu mutce
2019-06-12 07:01:34 PDT/-0700 <xxxx_> <la cenzis>: .i fu ma fi lo jbobau fa rodo cilre
2026-08-14 14:39:33 PDT/-0700 <Adam> u'e
2026-08-15 13:11:16 PDT/-0700 <korvo> zo'o da'i zo {xlane} morna pagbu
2026-08-16 10:33:32 PDT/-0700 <Ntsékees> coi fi'i @tim640527
2026-08-16 10:59:33 PDT/-0700 <korvo> coi .i zabna
```

---

## 2. Mailing lists — `/home/int19h.linux/lojban/disc/mail/`

| item | size | content |
|---|---|---|
| `maildir/{cur,new,tmp}` | 814–820 MiB, **107,672 files** (cur 92,674 + new 14,995) | extracted `lojban-list.maildir.zip`; RFC822, one message per file, Maildir filenames `1721701740.3712622_N.lebna:2,` |
| `lojban-list.maildir.zip` | 329,942,488 B | 107,673 entries, 636,295,559 B uncompressed; newest member 2025-06-26 |
| `b2024/maildir/` | 825–831 MiB, **109,619 files** | extracted `backup-2024-10-09.zip` ("backup-before-changes"); superset: 107,648 common, **1,971 only in b2024**, 21 only in `maildir/` |
| `backup-2024-10-09.zip` | 332,008,264 B | 109,623 entries |
| `tail/` | 12 MiB, **708 files** `msg78400.html` … `msg79107.html` | MHonArc v2.6.24 HTML from `lojban.org/lists-plain/lojban-list/`, 2017-10-12 → 2025-08-26; each has `<!--X-Message-Id:` / `<!--X-Reference:` comments and `<li><em>In-reply-to</em>` |
| `plainlist.html` | 680 B | index of `https://…/lists-plain/lojban-list/`: also lists `lojban-list-backup-2024-07-22.zip` and `lojban-list-up-to-2018-08-12.zip` (**not downloaded**) |

**Which lists:** effectively **only the main `lojban` list** (`lojban-list@lojban.org` → after 2011-09 `lojban@googlegroups.com`).
`X-BeenThere` histogram over `maildir/`: `lojban@googlegroups.com` 22,884 · `lojban-beginners@googlegroups.com` **6** ·
`news@lists.conlang.org` 2 · stray `sfbay-poly` 1. Subject tags (1/7 sample): `[lojban]` 62%, none 37% (pre-Google-Groups era),
`[lojban-beginners]` 16, `[jboske]` 2. No jboske, llg-members, lojban-beginners, wikidiscuss, or bpfk-list archives exist locally.

**Date range:** 1989-12-07 → 2025-06-26 (latest real traffic ~2024; 2025 items are spam). Files per 5-year bucket (1/3 sample ×3, incl. duplicates):
1989–94 ≈ 10.3k · 1995–99 ≈ 24.6k · 2000–04 ≈ **32.7k** · 2005–09 ≈ 15.6k · 2010–14 ≈ 21k · 2015–19 ≈ 3k · 2020–24 ≈ 290.

**Threading headers:** `Message-ID` in 107,583/107,672 files; `In-Reply-To` in 59,835; `References` in 43,938.
**Duplicates:** only **77,527 unique Message-IDs** — 25,737 IDs occur ≥2× (Google-Groups relay copies + list copies), so ~30k files are dupes; dedupe by Message-ID first. (MHonArc numbering `msg79107` ≈ consistent with ~79k unique.)
**Quoting:** ~66% of messages contain `> ` quote lines; bodies are mostly plain text, some `multipart/alternative` HTML (Google Groups era).
Top sender domains: gmail.com 21k, lojban.org 10k, digitalkingdom.org 5k, access.digex.net 4.3k, phyast.pitt.edu 4.2k.

**Size/tokens:** avg file 6,134 B, avg body (after first blank line) 4,099 B → ~441 MB of bodies ≈ **110 M tokens raw**; after Message-ID dedupe ≈ 80 M; after stripping quoted text and signatures probably 40–50 M.

Sample header block (`maildir/cur/1721701740.3712622_1.lebna:2,`, Received/DKIM lines elided):
```
X-BeenThere: lojban@googlegroups.com
Date: Tue, 20 Sep 2011 11:14:00 -0600
From: ".alyn.post." <alyn.post@lodockikumazvati.org>
To: lojban-list@lojban.org
Subject: Re: [lojban] lojban.org email also moved.
Message-ID: <20110920171424.GQ15253@sunflowerriver.org>
Mail-Followup-To: lojban-list@lojban.org
References: <20110921072132.GI14754@digitalkingdom.org>
MIME-Version: 1.0
In-Reply-To: <20110921072132.GI14754@digitalkingdom.org>
```

---

## 3. `/home/int19h.linux/git/lojban-disc/` vs `~/lojban/disc`

`~/git/lojban-disc` is **not a git repo** (no `.git`), 2.4 GiB, `irc/` + `mail/`. `find -type f | sort` lists are **identical** to `~/lojban/disc`; files have the same sizes and mtimes (2024-10-14 / 2026-08-22) but different inodes → a full byte copy, not a symlink. `~/lojban/disc` was created 2026-08-26 00:08 as a copy. smusni's charter (`~/git/smusni/AGENTS.md`, commit `bef01d1`) says `~/git/lojban-disc` and `~/git/lojban-wiki` live on a virtiofs share whose per-file overhead stalls `rg`, hence the `~/lojban/` copies — use `~/lojban/`. A third identical copy sits in `~/build/prov/{irc,mail}` (2.5 GiB, ephemeral partition).

---

## 4. MediaWiki snapshot — `~/lojban/wiki/` and `~/git/lojban-wiki/`

Both are the **same snapshot**: `snapshot.json` and `DIGESTS.sha256` are byte-identical (`fetchedAt: 2026-06-08T14:27:44Z`, started 06:23:30Z, MediaWiki 1.38.7, source `https://mw.lojban.org`, full-reconcile fetch of 14,184 pages). Generated by `cargo xtask vendor-wiki` (jbotci). 350 MiB (`pages/` 337 MiB, `media/` 9.4 MiB manifest only). `~/git/lojban-wiki` is not a git repo either.

Layout: `pages/index.json` (14,118 entries: `pageid, ns, title, redirect, revid, timestamp, model, bytes, source_sha256, …`), `pages/errors.json` (66), `pages/by-id/NNNNNNNN/{meta.json, source.wiki, parsoid.html}`, `media/manifest.json` (4,808 uploads, 1.83 GiB, **binaries not vendored**), `siteinfo.json`, `namespaces.json` (24 namespaces incl. custom `UserWiki` 200/201, `User profile` 202/203).

**Current revision only.** `meta.json` carries exactly one `revision` object (`revid, parentid, timestamp, user, comment, size, sha1`); `parentid` proves history exists upstream but no prior revisions are stored. Max `revid` seen = 125,431 → the wiki has ~125k revisions in total to fetch if history is wanted. Sample `meta.json` (page 5):
```json
{"pageid":5,"ns":8,"title":"MediaWiki:Mainpage","touched":"2015-04-06T06:59:09Z","lastrevid":112777,"length":6,
 "revision":{"revid":112777,"parentid":84125,"timestamp":"2015-04-06T06:59:09Z","user":"Gleki","userid":1,"comment":"","size":6,
 "sha1":"8ffcbc7f…","contentmodel":"wikitext","contentformat":"text/x-wiki"}, "sourcePath":"pages/by-id/00000005/source.wiki", …}
```

**Pages per namespace:** ns0 (Main) **5,790** · Talk(1) **372** · User(2) 277 · User talk(3) 31 · Lojban/Project(4) 9 · File(6) 4,878 · MediaWiki(8) 1,364 · MediaWiki talk(9) 2 · Template(10) 1,039 · Template talk(11) 5 · Help(12) 3 · Category(14) 183 · UserWiki(200) 51 · UserWiki talk(201) 1 · Module(828) 113.
**Discussion pages total: 411** (11.06 MB of wikitext — talk pages are large: `Talk:BPFK Section: PEG Morphology Algorithm` 1.99 MB, `Talk:BPFK gismu Section: Parenthetical Remarks…` 648 KB, `Talk:BPFK Section: Subordinators` 622 KB, `…Irrealis Attitudinals` 565 KB, `…Epistemology sumtcita` 509 KB). 2,656 redirects. ns0 `/Forum` subpages: 160 (tiki-forum imports); `/jbo`,`/en`,`/fr`… language subpages.
**BPFK material:** 393 titles containing "BPFK" (9.47 MB) — `BPFK Section: *`, `BPFK Checkpoint: *`, `BPFK Decisions`, `BPFK 2003 Report`, member pages. Also `LLG 2018 Annual Meeting Transcript` (534 KB), `L17-03`, `me lu ju'i lobypli li'u NN moi` (JL issues).
Last-revision years: 2013 3,617 · 2014 6,388 (tiki→MW migration) · 2015 1,634 · 2016 1,160 · 2020 304 · 2023 146 · 2024 165 · 2025 33 · 2026 4.

**66 failed pages** (HTTP 500 from Parsoid `with_html`, "Call to a member function getContent() on null"): 44 are `File:` pages, 9 `User talk:`, 4 main (`cipra/jbo`, `cipra55/jbo`, `me la mambl moi voksa nu casnu/jbo`, `ralju ckupau/nds`), 2 Talk — notably **`Talk:BPFK Section: gadri`** and `Talk:Flow QA` — plus `User:Ciste/Talk:BPFK Section: gadri`. These could be re-fetched via `action=query&prop=revisions&rvprop=content` (raw wikitext path) instead of Parsoid.

**Size/tokens:** all `source.wiki` = **48,324,346 B ≈ 12 M tokens** (ns0 34.0 MB ≈ 8.5 M; talk 11.1 MB ≈ 2.8 M); `parsoid.html` = 112.8 MB. Sample `source.wiki` head (`BPFK Section: gadri`, `pages/by-id/00000527/`):
```
{{BPFK Section from tiki|BPFK Section: gadri|95}}
==Proposed definitions ==
{{BPFK Section box open}}
=== cmavo: lo (LE) ===
==== Proposed Definition ====
Generic article. It converts a selbri, selecting its first argument, into a sumti. …
```

---

## 5. Dictionary — `/home/int19h.linux/git/lensisku-dump/` (+ other jbovlaste data)

Not a git repo. `README.md` (4.8 KB), `scripts/dump_lensisku.py` (59 KB, stdlib only), `upstream/lensisku/` (Lensisku Rust source checkout used to audit the API), `data/`. Purpose: a **complete, auditable snapshot of every *current* Lensisku definition**, because Lensisku's export endpoints only emit the single best-scoring definition per word/language (`valsibestguesses`). It combines three API read paths, cross-checks their definition-ID sets, and refuses to publish on disagreement.

**Snapshot date:** raw scrape 2026-07-26 (~8.5 h at 1 req/s), materialized **2026-08-02T14:43:57Z**. `api_base_url = https://lensisku.lojban.org/api`.

**Counts (`data/manifest.json`):** words **30,650** · definitions **57,687** · languages 70 · contributors 282 · examples 819 · gloss keywords 56,321 · place keywords 13,236 · images 0. Definitions by language: en 32,235 · jbo 4,502 · ru 2,950 · fr-facile 2,895 · es 2,620 · ja 2,589 · de 2,202 · zh 1,681 · eo 1,571 · en-simple 1,417 · hu 1,353 · sv 955 … By score sign: positive 42,903 · zero 13,947 · negative 837.

**Files:** `definitions.ndjson` 42.6 MB (≈10.6 M tokens; one normalized current definition per line: `definitionid, definitionnum, valsiid, langid, language_tag, definition, notes, etymology, selmaho, jargon, username, time, created_at, score, gloss_keywords[], place_keywords[], examples[], rafsi, type_name, sound_url…`), `definitions.json.gz` 4.9 MB, `words.ndjson` 6.0 MB (word → all definition IDs), `lensisku.sqlite3` 75.9 MB (tables `languages, words, definitions, keywords(69,557), examples, images, contributors`), `languages.json`, `contributors.json`, `capture-drift.json` (5 vote-score changes during capture), `data/raw/` (cached API pages + per-word responses).

**Contains:** definitions, notes, etymology, selma'o, jargon, aggregate score, author username, keywords (gloss + place), examples, rafsi, word type. **Excludes** per-user votes, comments, and — explicitly — **any edit history**: "The snapshot represents current records, not edit history."

**Other jbovlaste data on disk:**
- `~/git/cll/build/jbovlaste.xml` (12,314,420 B, 2026-08-17, **22,609 `<valsi>`**) and `~/git/cll.v0/xml/jbovlaste.xml` (11,764,371 B, 2026-03-10): the legacy **jbovlaste XML export** (`<dictionary><direction from="lojban" to="English"><valsi word=…><definition>…`) fetched by `~/git/cll/scripts/update_jbovlaste_xml.sh` from `http://jbovlaste.lojban.org/export/xml-export.html?lang=en&bot_key=…` — best-definition-only, English only, used by the CLL build for glosses. Two dated copies ⇒ a coarse diff is possible.
- `~/git/jbotci/crates/jbotci-dictionary-data/data/dictionary-en.json` (9,910,792 B, **17,536 entries**, Lensisku cached export `…/api/export/cached/en/json`, created 2026-07-27) — what `vlacku` ships; plus `extracted-rafsi-en.json` (55 gismu/60 rafsi recovered by LLM from prose).
- No jbovlaste SQL dumps, no per-definition version history anywhere on disk.

---

## 6. CLL sources — `~/git/cll`, `~/git/cll.v0`, `~/git/cll-review`; what `cukta` uses

**`~/git/cll`** (1.1 GiB, **1,899 commits**, first commit 2008-05-30 "first commit", HEAD 2026-08-17 on `text/89-chrestomathy-restore`). Fork of `github.com/lojban/cll` (`upstream`) at `github.com/int19h/cll` (`origin`). DocBook 5 XML with custom tags (`README-tags`), XSLT + Prince build. `chapters/`: **25 files, 3,290,186 B (≈0.8 M tokens)** — `01.xml`–`21.xml` (21 = EBNF), fork additions `22.xml` (dialects/experimental), `a01.xml` (Chrestomathy), `a02.xml` (PEG morphology), `a03.xml` ("Changes from the first edition").
Editions available:
- **CLL 1.0** (1997 Red Book): only as the ancestor of the DocBook text; no separate 1.0 source tree.
- **CLL 1.1** (official LLG): `official/` has 8 dated builds (2016-04-13 … 2019-11-14) as PDF/EPUB/MOBI + 3 XHTML variants; tags `v1.1-{2016-08-26,2018-05-21,2019-11-14}-{epub,html,mobi,pdf,print}`; branch `docbook-prince` = upstream default. `official/CHANGELOG`: 1.1 = Red Book + errata only.
- **1.2.x** (gleki's "UnCLL"/geklojban): tags `geklojban-1.2.12/13/15`, branch `baseline/uncll-1.2.16`, `official/cll_v1.2.12_xhtml-no-chunks`, `…1.2.15…`.
- **1.3.x** (this fork, "colojban"): branches `edition/1.3.0/1/2`, tag `v1.3.2`.
- Version lineage write-up: `~/git/cll/research/audits/cll-versions.md`. `research/` (31 MB, git-excluded) holds `CHANGES.md` (authority catalog), `sources/` (wiki exports), ~90 chapter-review files and codex logs.
- Git history back to 2008 gives **line-level history of every CLL 1.1 errata edit**; 1.0→1.1 diffs are therefore recoverable from git, 1.0 itself is not on disk as text.

**`~/git/cll.v0`** (656 MiB, 1,378 commits): abandoned earlier clone of the same fork (remote is a dangling macOS path), branch `work`, HEAD 2026-03-10, `VERSION = 1.1-lagleki-unofficial-candidate`, 21 chapters (3,107,963 B), plus an experimental Python/Lark grammar dir. `cll/CLAUDE.md`: "reuse build/DocBook fixes only, NEVER its wording".

**`~/git/cll-review`** (688 MiB): a **git worktree** of `cll` (detached at `8145b12`, 2026-07-28 `main`), used for per-chapter/per-PR cross-model editorial review; 91 `*review*.md` files under `research/`. Reviews cite chapter diffs vs `origin/geklojban-development`, `research/CHANGES.md`, pinned wiki history snapshots and `~/git/lojban-wiki`.

**What `cukta` uses:** git submodule `~/git/jbotci/vendor/cll` → `https://github.com/int19h/cll` branch `main`, pinned in `vendor/cll.VENDORED_FROM` to **`v1.3.2`, commit `2272321b`, 2026-07-17**. `crates/jbotci-cll/build.rs` bzip2-embeds the 25 DocBook chapters (3,304,746 B) into the binary; `import.rs` parses with `roxmltree` at load. Indexed: 25 chapters, **339 sections, 1,857 examples**, 4,763 `xml:id`s (asserted in `crates/jbotci-cll/src/lib.rs:1505`). Sidecars: `vendor/cll-import-metadata.toml`, `vendor/cll-chrestomathy.toml`. **Only one edition is served** (1.3.2); no 1.0/1.1 text in jbotci — the 1.1→1.3 delta is only narrated in `a03.xml`. Addressing: DocBook `xml:id`s (`section-what-is-lojban`) or numeric `9.6`; legacy `cNsM`/`#eN` anchors preserved and never renumbered (`README-urls`).

---

## 7. `/home/int19h.linux/git/jbotci/`

Rust Cargo workspace (39 members; 28 crates in `crates/`, apps `apps/jbotci` CLI+LSP, `apps/jbotci-server` axum+Dioxus, `apps/jbotci-app` Dioxus web/desktop/mobile, `bindings/python` PyO3), MIT, 2,135 commits, 7.3 GiB source tree (24 GiB with `target`). Remotes GitHub (`int19h/jbotci`), GitLab, Codeberg. `CLAUDE.md` = `@AGENTS.md`; `AGENTS.md` (38 KB) = code doctrine + agent-ops coordination protocol.

**Tools** (`apps/jbotci-server/src/mcp.rs:224-300`): `cukta` CLL read/search (semantic by default) · `vlacku` dictionary cards · `gentufa` parse tree · `vlasei` morphology/word classes · `tersmu` logical meaning (SFN-XML / smusni / json) · `jvozba` lujvo construction · `gimfihi` gismu proposals.
**Deployment:** Render (`render.yaml` → `deploy/render/Dockerfile`, health `/api/health`, domain **jbotci.app**); routes `/api/{health,gentufa,gimfihi,tersmu}`, `/mcp` (stateless Streamable-HTTP JSON-RPC, protocol 2025-06-18, no SSE), `/discord` (interactions endpoint). Static embedding packs/models on Cloudflare R2 (`assets.jbotci.app`) via `cargo xtask publish-*-r2`. Workflows: `test.yml`, `render-image.yml`, `python-wheels.yml`, `prepare-cli-release.yml`, `claude.yml`.

**Existing search/index code — dense-only, no lexical index:**
- `crates/jbotci-search` (3,002 lines): `Embedding{model,dimensions,values:Vec<f32>}`, `trait VectorSearchIndex<T>` with one `search()` method; `vlacku.rs` does exact/rafsi/lujvo index lookups, regex patterns, ALINE phonetic similarity; `Meaning` mode delegates to embeddings.
- `crates/jbotci-embeddings` (4,988 lines): normalized f32 vectors, `dot_product`, **exhaustive linear `top_vector_hits`** (no ANN); sharded "vector pack" files + JSON manifests (8 MiB shards, brotli siblings for web); corpora `vlacku` and `cukta` (chunks = CLL sections/paragraphs/examples from `jbotci-cll/src/search.rs`); models **F2LLM-v2** (CodeFuse, Qwen3-shaped) 80M/320d, 160M/640d, **330M/896d default**, 0.6B/1024d, GGUF Q4_K_M via llama.cpp (`native.rs`, feature `native-llama`); precomputed packs downloadable from `assets.jbotci.app/embeddings/gguf/v1`.
- `crates/jbotci-embedding-inputs` (857 lines): canonical retrieval-document/query text builders + SHA-256 corpus fingerprints.
- `crates/jbotci-f2llm-runtime` (5,372 lines): hand-written WebGPU (wgpu/WGSL) inference for F2LLM in the browser, replacing ONNX Runtime/Transformers.js.
- `grep` for `tantivy|bm25|fts5|rusqlite|sqlite` in `crates/ apps/` → **zero hits**. `cukta` "Word" mode is tagged-word set intersection, not full text. No hybrid/BM25 fusion anywhere.
- `.jbotci-build/web-embedding-corpus.json` records an earlier **EmbeddingGemma-300m-q4-768** corpus (superseded by F2LLM; inactive catalog entries preserved).

**`~/git/jbotci-f2llm-webgpu-prototype`** (757 MB, not a repo): offline exporters (`export-f2llm-webgpu-from-onnx-q4.py` repacks Transformers.js q4 `MatMulNBits` weights into WebGPU shards), goldens, and a browser harness comparing the custom runtime against ORT-Web. Artifact sizes: 160M ≈110 MB, 330M ≈231 MB, 0.6B ≈416 MB. It succeeded and became `crates/jbotci-f2llm-runtime` + `tools/embedding-pack/f2llm/`.
**`~/git/f2llm-*.json`** (8 files, 1.07 MB, 2026-06-05/06): harness run logs `{summary, events[]}` — correctness vs ONNX goldens (cosine ≥0.999, deterministic sha256 across runs on 0.6B) and a "packed-512" experiment (batch-packing dictionary entries into 512-token sequences: order-isolation passed, but speedup only 1.0069×). No vectors inside.

---

## 8. `~/git/smusni` and the ad-hoc research repos

**smusni** (83 commits, 22 MB): a prescriptive typed semantic core for Lojban ("semantic assembly language") — `spec.md` 285 KB normative, `rationale.md`, `catalog.md`, `cmavo.md`, `samples.md`, `primer.md`, `brief.md` charter. Research process: (a) markdown dockets in `review/` (30 files: `ADJUDICATIONS.md`, `CONSENSUS.md`, `COUNTEREXAMPLES.md`, `SOURCE_AUDIT.md` claim-by-claim vs pinned commits, `DISCORD_POLLS.md` speaker-intuition polls); (b) a multi-model review exchange with real tooling (`tools/review-exchange/{exchange,bundle,web}.py`, `review/exchange/messages/*.md`, `review/bundle/full-pass-{1,2}.md`); (c) executable Racket/Redex models (`tools/smusni-redex/`) and a Lean probe; (d) small checkers (`tools/check-docs.py`, `review/checks.py`) and one-offs (`attest_and_review.py`). **Corpus lookups were manual `rg` over `~/lojban/wiki` and `~/lojban/disc`** per `AGENTS.md:272-286`, with results pasted as prose citations: e.g. `spec.md:4835-4880` cites `irc/all_logs.txt` **line numbers** 408817–408825, 477248, 1005240 and mailing-list Message-IDs (`<9106201157.aa26475@COR4.PICA.ARMY.MIL>`, `<51BDBA1D.80602@gmx.de>`). This is exactly the fragile pattern jbomo'i should replace: line-number citations into a mutable concatenated file, no stable IDs, no thread/date context, no dedupe. Siblings `smusni-mechanization`, `smusni-group-sync`, `smusni-gemini_2_fix` are worktrees; `smusni-review` is a standalone review dump.

**kuna-research** (52 KB, not a repo): six 2026-07-07 notes comparing Toaq's Kuna parser/semantics with jbotci's, plus Predilex lexicon; sources = other repos only, no Lojban archives, no corpus data.
**tersmu-dsl-research** (806 MB, 238 commits): LLM-panel experiments (OpenRouter A/B batteries, debates) toward a lossless tersmu DSL; data = jbotci's own renderings; large `raw-calls-*.jsonl` logs (20–38 MB each); reusable: a ~50-sentence battery with parallel SFN-XML/smusni renders (`experiments/phase-a/battery-*`, <1 MB). Only wiki hit `mw.lojban.org/papri/lo_valslinku`.
**grammar-review** (251 MB, 18 commits): source-only comparison of jbotci's grammar vs CLL EBNF, camxes-std/exp, Zantufa, by external models; reusable: `upstream/gerna_cipra` mirror of camxes/maftufa/maltufa/zantufa PEG+JS grammars; wiki hit `mw.lojban.org/papri/zasni_gerna_cenba_vreji`. No text corpora.
**jbotci-pm-archive** (2 MB, not a repo): project-management archive for jbotci epic #554 (handover, briefs, prompts, gate logs). No Lojban data.

---

## 9. Other Lojban corpora on disk

| path | size | what |
|---|---|---|
| `~/lojban/wiki/` BPFK pages (393 titles) + `Talk:BPFK Section:*` | 9.5 MB + most of the 11 MB of talk | the only BPFK material; **no bpfk-list mailing list archive** locally |
| `~/git/cll/chapters/a01.xml` (Chrestomathy: Alice ch.1, North Wind, Terry the Tiger, Soft Rains, Xanadu…) | 46–62 KB | canonical texts in the fork |
| `~/git/alis.txt`, `~/git/alis-recovered/{alis.txt,alis-visible*.txt,alis.html,REPORT.md}`, `~/git/jonlehu/alis.{txt,html,bak}`, `~/git/jbotci.v0/doc/alis-plus.md` | 164 KB / 680 KB / (17 MB dir is mostly font `.ttf` builds) | xorxes' *Alice* translation in several recovered versions |
| `~/build/prov/` (2.9 GiB; ephemeral `/build`-era dir) | `alis-hist.json` (MediaWiki `prop=revisions` metadata for the Alice page), `alis-2012/2013/2015/2016` snapshots, `pw-*.html/.tsv` (Alice, North Wind, Soft Rains, Terry from a Next.js "pwrepo" texts site, 277 MB), `tiki.html`, wayback `w-2012…html`, `ws-alice1.*`, `texts/` (11 files), `site-132.pdf`, `recheck/` (140 MB), `irc/`+`mail/` = third copy of §1–2 | chrestomathy provenance research (`~/git/chrestomathy-provenance`, 56 KB, holds the report) |
| `~/git/lojban-ebnf/corpus/` | 44 KB, 3 files (`boundary-judgments.toml`, `cll-selmaho.tsv`, `historical-lookahead.toml`) | grammar judgments, not text |
| `~/git/grammar-review/upstream/gerna_cipra/` | tens of MB | camxes/zantufa/maftufa grammar versions |
| `~/git/ilmentufa` (23 MB), `~/git/jbofihe` (3.5 MB), `~/git/lojban-parser` (empty), `~/git/lojban-ebnf` (192 MB) | parsers/grammars | |
| `~/git/jbotci/vendor/cll-chrestomathy.toml`, `scripts/register-discord-command.mjs`, `~/git/discord.env`, `~/git/discord-bot-token` | — | Discord *bot* integration only; **no Discord chat export** |
| `~/git/smusni/review/DISCORD_POLLS.md` | 5 KB | poll designs, no responses captured |

**Not found anywhere:** Google Groups exports, `jboske`/`llg-members`/`lojban-beginners`/`wikidiscuss`/`bpfk-list` archives, wikispaces/tiki dumps (only the MW `{{BPFK Section from tiki|…}}` migration templates and `/Forum` subpages), Tatoeba, Discord/Telegram exports, `lojban-list-up-to-2018-08-12.zip`, `lojban-list-backup-2024-07-22.zip`.

---

## 10. Toolchains and embedding tooling

- `uv` 0.9.17 (`~/.local/bin/uv`; `uv tool list` → only `datamodel-code-generator`), `python3` 3.13.7 (`/usr/bin`), `node` v24.19.0 + npm, `cargo`/`rustc` 1.96.1 (`~/.cargo/bin`). `jq` present; `rg` only via `~/.kimi-code/bin/rg`; **no** `sqlite3` CLI, `duckdb`, `ollama`, `llama-server` on PATH (Python's stdlib `sqlite3` module works).
- `pip list | grep sentence|faiss|lance|qdrant|chroma|voyage|openai|anthropic|tantivy|torch|transformers|onnx` → **nothing** system-wide. Per-project venvs exist (`~/git/jbotci-f2llm-webgpu-prototype`, `~/git/jbotci/.jbotci-build/f2llm-python`, `tersmu-dsl-research`) but nothing global.
- `~/.cache/huggingface/hub/models--codefuse-ai--F2LLM-v2-80M` is the only cached model; `~/.config/openrouter`, `~/.config/kimi` exist (API-key configs). `~/.cache/lojban`/vector DBs: none.
- Hardware: 15 CPUs, 62 GiB RAM, **no NVIDIA GPU** (`nvidia-smi` absent). llama.cpp CPU embedding via jbotci's `native-llama` feature is the only local embedding path already built.

---

## Gaps — what jbomo'i would still need to acquire or build

1. **Wiki revision history** — snapshot is current-revision only (~125k revisions upstream, 14,118 pages). Need `action=query&prop=revisions&rvlimit=max` per page (or `Special:Export` with history) to answer "when/why did page X change"; also re-fetch the 66 Parsoid-failed pages (incl. `Talk:BPFK Section: gadri`) via raw wikitext.
2. **Wiki media** — 1.83 GiB of uploads (audio, images, some PDFs like JL issues) are manifest-only.
3. **Dictionary change history** — Lensisku dump and both jbovlaste XML exports are current-state only; no per-definition versions, no vote timelines, no comments. Sources to pursue: jbovlaste's old `history`/comment tables (SQL dump from the LLG server), or diffing periodic snapshots going forward (two XML snapshots 2026-03 vs 2026-08 exist as a start).
4. **Mailing lists** — only the main `lojban` list. Missing: `lojban-beginners`, `jboske`, `llg-members`, `bpfk-list`, `wikidiscuss`, `lojban-announcements`, `lojban-list-up-to-2018-08-12.zip` (may contain messages not in maildir). Google Groups web archives would need scraping; `lojban.org/lists-plain/` MHonArc (`tail/`) shows that route works.
5. **IRC** — no 2000-11 → 2002-05 coverage; #jbosnu prefix must be separated and verified; #ckule/#jbopre logs absent; irssi 2015 block needs date reconstruction; 2002-2010 lines lack TZ.
6. **Discord / Telegram** — no chat exports at all despite bridged traffic appearing in IRC since ~2016 (relay nicks `<xxxx> <la kanba>:`). Bot tokens exist in `~/git/discord*`, so an export is feasible.
7. **CLL 1.0 text and tiki-era pages** — 1.0 is not on disk as text (only 1.1+ DocBook and its git history since 2008); the original tiki wiki (pre-2014) history is absent, only the MW import remains.
8. **BPFK process artifacts** — no bpfk-list archive, no vote records beyond what is on wiki pages.
9. **Infrastructure** — no lexical/BM25 index or vector DB anywhere; jbotci only has exhaustive dense F2LLM search over dictionary+CLL (~18k entries, ~1.9k examples). For ~150 M raw tokens (IRC 18 M + mail 110 M + wiki 12 M + dict 11 M) a hybrid BM25 + dense index with stable citation IDs (message-id, IRC channel+timestamp, wiki pageid+revid, definition id, CLL xml:id) is needed; dedupe of ~30k duplicate mail files and quote-stripping first.
