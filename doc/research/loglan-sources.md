# Loglan sources: acquisition and rights inventory

**Purpose.** Decide which *Loglan* materials belong in jbomo'i, where each lives, in what
format, and whether it can be republished. Lojban (1987–) is a fork of Loglan (James Cooke
Brown, 1955–); pre-fork Loglan documents are Lojban's own prehistory, and post-fork TLI
material is the other side of the dispute record and the comparison baseline.

**Method.** Everything marked *verified* was fetched over HTTP on **2026-08-27 (UTC)** with
`curl`/WebFetch from this machine; the observation quoted is what came back (HTTP status,
`Content-Length`, `Last-Modified`, extracted text, `pdfinfo` output, JSON API payload).
Items marked *inferred* are conclusions drawn from verified evidence but not directly
observed. Nothing here is reported from memory. **No WebSearch was used** (session budget
was exhausted); every finding comes from a direct fetch, so absence of a thing below means
"not found by direct probing", not "does not exist".

**Rights legend.** `PD` public domain · `TLI-perm` TLI copyright with a stated permission
that may or may not cover us · `TLI-ARR` TLI copyright, all rights reserved · `LLG-perm`
LLG copyright with the standard "permission to copy for promotion of Lojban" grant ·
`3P` third-party rights (Scientific American, authors) · `?` unstated.

---

## 1. loglan.org — The Loglan Institute

Site root `https://www.loglan.org/` (HTTP 301 from `http://`), `Last-Modified: Mon, 02 Feb
2026 23:31:35 GMT`, 27,418 bytes. Apache with **directory indexing enabled** on most
subdirectories (`/Download/`, `/Articles/`, `/Articles3/`, `/Texts/`, `/Misc/`, `/Lodtua/`,
`/Sanpa/`, `/Loglan3/`, `/Logcue/`, `/Images/`, `/LOD/`, `/Download/Parser/`,
`/Download/Dictionary/`, `/Download/LoglanTeach/`) — so the site is fully enumerable and
mirrorable with `wget -r`. `robots.txt` → **404** (verified). No site-wide licence page.
No mention of Lojban anywhere on the home page.

### 1.1 Books and language descriptions

| Item | URL | Format / size | Date observed | Rights (as stated on the item) |
|---|---|---|---|---|
| **Loglan 1: A Logical Language**, Revised 4th ed. — full text | `https://www.loglan.org/Loglan1/index.html` + `chap1..7.html`, `app-a..h.html`, `preface`, `forward`, `pronunciation`, `bibliography`, `edition_notes`, `copyright` | **HTML, one file per chapter**, ~2.5 MB text total (chap4 320 KB, chap5 356 KB, chap6 221 KB…); index 21,300 B | `Last-Modified: 2009-04-10` | Front matter: *"Downloading the HTML Edition … and making one paper copy … for your personal use, may be done without payment … no such copies, nor portions thereof made on any medium shall be used for any commercial purpose whatever without the express written permission of the copyright owner, The Loglan Institute, Inc."* → **TLI-perm (non-commercial personal copy only; silent on redistribution)** |
| Loglan 1 — HTML zip | `https://www.loglan.org/Download/Loglan1.zip` | ZIP, **816,914 B** | 2008-06-05 | same |
| Loglan 1 — PDF | `https://www.loglan.org/Download/Loglan1.pdf` | PDF, **4,612,776 B** | 2008-11-24 | same |
| Loglan 1 copyright page (reproduced) | `.../Loglan1/copyright.html` | HTML | — | *"Copyright © 1966, 1969, 1975, 1989 by The Loglan Institute, Inc. All Rights Reserved"*; ISBN 1-877665-00-2; LCCN 89-7968; trademark notice for 'Loglan'® |
| Loglan 1 HTML-edition notes (James Jennings, 1999) | `.../Loglan1/edition_notes.html` | HTML, 4,288 B | — | States the HTML edition tracks the 1989 4th ed. "after all known errors have been fixed"; ch. 1, 7, front matter and bibliography were **OCR'd** (so may carry OCR errors); Appendix H is Kirk Sattley's *Loglan 1 Updater* (post-1989 changes) |
| **Notebook 3: The Present State of the Loglan Language** (1987) | `.../Download/NB3-Part-I.pdf` (6,022,854 B, **71 pp**), `NB3-Part-II.pdf` (4,668,209 B), `NB3-Part-III.pdf` (5,285,989 B), plus `NB3-p66.tiff`, `NB3-p70.tiff` | **Image-only PDF scans** (Xerox WorkCentre 5775, created 2013-08-09); `pdftotext` yields **nothing** → no OCR layer | 2013-08-09 | No notice on loglan.org. But the **OCR'd copy on Randall Holmes' site carries an explicit note** — see §5.2 |
| **Loglan 3: Understanding Loglan** (Stephen L. Rice, 1997) | `.../Loglan3Download.html`; files `.../Download/L3.vol1.pdf` (449 K), `L3.vol2.pdf` (457 K), `L3.vol3.pdf` (433 K) | PDF ×3, ~1.3 MB | 2000-02-22 | **Shareware, $5 for the set**, "$3 per set royalties" to the author → **TLI/author, payment expected**. An older partial HTML draft survives at `/Loglan3/Les1..7.html` (2001-09-18) |
| **Loglan 4 & 5** (dictionary, JCB, 2nd ed. 1975 — modern re-edit) | `https://www.loglan.org/LOD/L4and5.zip` | ZIP **1,539,965 B** → `EnglishToLoglan.html` 4,459,783 B + `LoglanToEnglish.html` 3,712,409 B + `ReadingTheDictionary.html` 18,356 B (~8.2 MB uncompressed, searchable HTML with JS index) | 2013-08-25 | `?` — no notice observed in the extracted head |
| Loglan→English (Holmes revision) | `https://www.loglan.org/LOD/LoglanToEnglish-RH.zip` | ZIP 661 K | 2013-08-25 | `?` |
| Loglan Paradigms (A–N tables) | `https://www.loglan.org/Paradigms/` | HTML + PDF + .doc | — | `?` |
| Appendix A little-word lists (Bill Gober) | `/Misc/loglan-lw-by-word.html`, `/Misc/loglan-lw-by-lexeme.html` | HTML, 20 K each | 2012-05-22 | `?` |
| "What is Loglan?" flyer (Alex Leith) | `/what-is-loglan.html` | HTML, 6,507 B | 2007-01-23 | "From a brochure prepared by The Loglan Institute, Inc." — this is the pamphlet TLI mailed to enquirers |
| Price list / catalogue | `/loglan-offerings.html` | HTML, 24,300 B | 2010-02-11 | Marked "out of date, kept for historical and reference purposes". **This is the best single inventory of what TLI ever published**, with ISBNs, page counts and prices |

**Loglan 2** (*Methods of Construction*, 1969 microfilm) is **not online**. Per the Loglan 1
bibliography (verified at `/Loglan1/bibliography.html`) its twelve chapters were reprinted
across *The Loglanist* vols. 1–2, which are also not online. **Notebook 1** (*The Machine
Grammar and Corpus of Loglan*, 1982) and **Notebook 2** (*A Proposed Revision in the
Structure of Loglan Words*, 1982) are not on loglan.org — but scans exist on Holmes' site
(§5.2).

### 1.2 Journals

| Item | URL | Coverage observed | Format | Rights |
|---|---|---|---|---|
| **Lognet** index of contents | `https://www.loglan.org/Lognet/index.html` (33,007 B, 2021-05-12) | **Lognet 89/1 … 00/1** — issue-by-issue tables of contents with page numbers, ~35 issues, plus **La Logli 96/1, 97/1, 97/2, 97/3, 02/1**. Explicitly "a work in progress"; several issues flagged "*missing the original PageMaker files*" (89/1, 90/2, 92/1, 93/1, 97/1) | HTML index; ~90 individual articles re-set as HTML under `/Articles/`, `/Articles2/`, `/Lodtua/`, `/Sanpa/`, `/People/`; 22 Rex May cartoons as PNG under `/Cartoons/` | Per-article footers: *"Copyright 1990 by The Loglan Institute, Inc. All rights reserved."* (verified on `/Articles/faces-of-gu.html`) → **TLI-ARR** |
| **Lognet 99/1** — the only full-issue scan | `https://www.loglan.org/Download/lognet99-1.zip` | 24 pages (cover … back cover) | ZIP **9,789,921 B** of **TIFF page images** (no OCR) | TLI-ARR (inferred) |
| **La Logli** | no separate archive | Only the contents lists inside `/Lognet/index.html`; L3 vols. 1–3 are "nearly identical" to LL 97/1–3 | — | — |
| **The Loglanist (TL), 1976–1984** | **NOT ONLINE ANYWHERE FOUND** | 21 issues, vols. TL1–TL7. `/loglan-offerings.html` (verified): *"Eight of the 21 issues of this 1976-84 journal are still in print … If you wish to use our masters to make copies of out-of-print issues, write for facsimiles of the titlepages"* | Print only | TLI |

*The Loglanist* is the single largest gap. It is the pre-fork technical record (the Great
Morphological Revision, the machine-grammar work, the 1983–84 special issues TL6/1 and
TL7/1 that Notebook 3 was built from). The full per-article citation list survives in the
Loglan 1 bibliography (`/Loglan1/bibliography.html`, verified) — hundreds of TL entries
with volume and page numbers — so a **metadata-only index of TL is buildable today**
without the issues.

### 1.3 Texts, columns, audio, misc

- `/Texts/` — 19 files, Loglan sample texts incl. JCB's Whitman translation, Alex Leith's
  *Nepo Neri Vizgoi La Loglandias*, *La Mioskun* (Alice), 2004–2021.
- `/Tapes/index.html` — *Readings from Loglan 1*, ~2 h 28 m of MP3 (61.1 MB). Explicit
  notice: *"These recordings are Copyright ©1984-2009 by The Loglan Institute. All rights
  reserved. **You may download one copy for yourself for personal use.** If you would like
  to make these files available to other people, please direct them to this web page."* →
  **TLI-ARR, redistribution explicitly refused.**
- `/Logcue/` — Mac text-to-speech experiment, `.talk` files, 2000–2006.
- Scientific American June 1960 article: **not hosted on loglan.org.** `/loglan-offerings.html`
  records that TLI sold *reprints* of it ("The Institute still has a number of reprints of
  the original (June 1960) Scientific American article"). The scan is on the Lojban wiki
  instead (§2.3).
- Mailing list pointer: `http://mailman.ucsd.edu/mailman/listinfo/loglanists` — see §4.
- **No Loglan wiki exists.** `/wiki/` and `/loglan-wiki/` both → **404** (verified). The
  "web dictionary" is the static `L4and5.zip` HTML and Holmes' `E-to-L.html` / `L-to-E.html`.

---

## 2. archive.org, HathiTrust and other scans

### 2.1 Internet Archive

Queried the IA advancedsearch JSON API for `loglan`, `Loglanist`, `Lognet`, `"La Logli"`,
`"Loglan Institute"`, `"James Cooke Brown"`, and `identifier:(*loglan*)`.

| Identifier | Title | What it is | Rights as recorded |
|---|---|---|---|
| `Loglan1` | Loglan 1 | **A third-party re-upload of TLI's own PDF.** Uploader `isenhand@yahoo.co.uk`, `addeddate 2009-09-23`; `Loglan1.pdf` is **4,612,776 B — byte-identical in size to `loglan.org/Download/Loglan1.pdf`**. IA has since derived `Loglan1_djvu.txt` (1,600,689 B full text), EPUB (831,611 B), ABBYY XML, 320 MB JP2 zip | `licenseurl = http://creativecommons.org/licenses/by-nc-nd/3.0/` — **this CC tag was applied by the uploader, not by TLI**, and contradicts the TLI notice inside the file. **Do not rely on it.** |
| `loglan1logicalla0000brow` | Loglan 1: a logical language | **The 1975 3rd edition**, Trent University copy, scanned 2019-05-10. 300 pp. Described as *"A revision and abridgement of the second edition published on microfilm in 1969 (University Microfilms cat. no. S-398) [entitled Loglan 1-5]"*. LCCN 75012985, OL5192215M | `access-restricted-item = true`; collections `inlibrary`, `printdisabled` → **controlled digital lending only**. `_djvu.txt` exists (796,885 B) but is not publicly downloadable |
| `loglan88reporton0000krec` | LOGLAN '88 — report on the programming language | **False positive.** This is the Polish object-oriented programming language LOGLAN'82/'88, unrelated | — |
| `wiki-loglangs.wiki-20230929` | the Logical Languages Wiki | wikiteam3 dump of `loglangs.wiki`, 2023-09-29; `history.xml.zst` 220,545 B | `licenseurl = https://loglangs.wiki/Meta:Copyrights` |

**No IA item exists for *The Loglanist*, *Lognet*, *La Logli*, Notebook 1/2/3, or Loglan 4&5**
(`numFound 0` for `Loglanist` and `"La Logli"`; the two `Lognet` hits are unrelated products).

### 2.2 HathiTrust / Google Books

- HathiTrust Bib API `lccn:75012985` → record `003060688`, *Loglan 1: a logical language*,
  1975, OCLC 2366835. One item: `mdp.39015037447326` (University of Michigan),
  **`rightsCode: "ic"`, `usRightsString: "Limited (search-only)"`** (verified). So:
  full-text search only, no page images, no download.
- `isbn:1877665002` (the 1989 4th ed.) → **no records** in HathiTrust.
- Google Books API `q=loglan` returned `totalItems: None` from this host — **not verified
  either way**; treat Google Books as unchecked.

### 2.3 Scientific American, June 1960

**Already inside the Lojban corpus.** The article is hosted as a wiki file:

- `https://mw.lojban.org/images/9/9a/Scientific_American_Loglan_Article%2C_by_James_Cooke_Brown.pdf`
- **585,581 B, PDF 1.4, 11 pages, `/Title (Loglan)`, Producer "Appligent Document
  Solutions", CreationDate 2008-05-20** — i.e. a Scientific American-produced digital
  reprint, not a home scan. It **has an OCR text layer**: page 1 extracts as
  *"Established 1845 / SCIENTIFIC AMERICAN / June, 1960 / Volume 202 / Number 6 / Loglan …
  by James Cooke Brown"* (verified).
- Two upload versions on the wiki: `2012-11-09T11:43:29Z` (915,199 B) and
  `2024-05-03T12:16:34Z` (585,581 B), both by user `Gleki`.
- Description page: `https://mw.lojban.org/papri/File:Scientific_American_Loglan_Article,_by_James_Cooke_Brown.pdf`;
  the wiki article `Scientific American article` (pageid 43) describes its contents.
- **Rights: Scientific American, Inc., 1960 — a third party, not TLI and not JCB.** No
  licence is asserted on the wiki page.

---

## 3. The fork and the dispute record

| Document | Where it is | Format / size | Rights |
|---|---|---|---|
| **LeChevalier, "Loglan and Lojban — about the dispute"** (1991, rev. 2000) | Two copies, same text: `https://www.lojban.org/old-style/publications/loglan.html` (12,751 B, last modified 2005-06-27) and the wiki page `https://mw.lojban.org/papri/the_Loglan-Lojban_Dispute` (7,661 B wikitext, latest rev. 2014-06-30) | HTML / wikitext | *"Copyright, 1991, 2000 by the Logical Language Group, Inc. … Permission to copy granted subject to your verification that this is the latest version …, that your distribution be for the promotion of Lojban, that there is no charge for the product, and that this copyright notice is included intact."* → **LLG-perm** |
| **Loglan Institute, Inc. v. Logical Language Group, Inc., 962 F.2d 1038 (Fed. Cir. 1992)** — the trademark-cancellation appeal | **`https://static.case.law/f2d/962/cases/1038-01.json`** (Caselaw Access Project static bulk; **HTTP 200, full opinion text, 12,616 characters**) | JSON with structured `casebody` | **PD** — US federal judicial opinion. CAP data carries no additional restriction on the opinion text |
| — its key facts, as verified from that text | Decided **1992-04-28**; docket **No. 91-1254**; Lourie, J.; affirms TTAB **Cancellation No. 18,026, decided 1991-02-04**, which granted LLG summary judgment holding **LOGLAN generic** and ordered the registration cancelled. Opinion records: language invented 1955; *"He first used the term Loglan in a publication in 1956"*; Institute formed **1962**; registration applied for **1987-08-17** for "Dictionaries and Grammars" | — | PD |
| **LeChevalier & Athelstan, long review of Loglan 1 (4th ed.)** | `https://www.lojban.org/files/papers/L1LONGRV.TXT` (HTTP 200) | plain text, ~70 KB | *"Copyright 1989, The Logical Language Group, Inc. … Permission to copy granted for purposes of promotion of Lojban."* → **LLG-perm**. A shorter version was printed in *le lojbo karni* #10 |
| **"How to Use Your Old L1 and L4/5 Books" (excerpt from JL5)** | `https://www.lojban.org/files/papers/useoldL1.txt` (HTTP 200) | plain text, ~15 KB | *"Copyright, 1988, 1991, by the Logical Language Group, Inc. … Permission to copy granted subject to …"* → **LLG-perm** |
| **ju'i lobypli (JL) 1–18 + le lojbo karni LK8–11, LK18** | `https://www.lojban.org/files/jl/` — `JL1.ZIP` … `JL18.ZIP`, `LK8.ZIP`…`LK11.ZIP`, `LK18.ZIP`, plus `jlN.txt.gz` twins | ZIP/gzip plain ASCII, 18–223 KB each | LLG |
| **TLI's side of the dispute** | **Not published by TLI.** The loglan.org home page, `/what-is-loglan.html` and `/loglan-offerings.html` contain **no mention of Lojban at all** (verified by full-text read) | — | — |
| Wiki context pages | `mw.lojban.org/papri/`: `Loglan` (4,460 B), `Loglan 1` (4,072 B — a good edition-by-edition history by user *Mukti*, 2017), `The Loglan Institute` (581 B), `Lojban timeline` (97,999 B, last edited 2026-08-02), `Freudenthal's critique of Loglan`, `borrowing from Loglan`, `Old Loglan gismu` (98,671 B) | wikitext | wiki licence |

**Already inside the Lojban corpus** (needs no separate acquisition): the dispute essay
(both copies), all JL/LK issues, all the wiki pages above, `L1LONGRV.TXT`, `useoldL1.txt`,
and the Scientific American PDF. **Only on loglan.org:** nothing about the dispute at all.
**Neither side hosts:** the TTAB decision of 1991-02-04 (only the Fed. Cir. summary of it),
and the underlying correspondence LeChevalier says he keeps ("Details and documentation are
enormous as I maintain as complete an archive as possible") — that archive has never been
published and is an obvious ask.

---

## 4. TLI mailing lists and Usenet

| List | Status (verified) |
|---|---|
| **`loglanists@ucsd.edu`** (the TLI list) | Host `mailman.ucsd.edu` resolves (132.239.0.184) but **connections time out** — the server is gone. Wayback has captures of the `listinfo` page from **2009-03-03 through 2012-04-26** (mostly 302s, two 200s: 2010-06-13, 2011-07-17). A Wayback CDX prefix query for `mailman.ucsd.edu/pipermail/loglanists/` returns **zero rows** — the Pipermail archive was never captured. **Decisive primary statement**, found in an HTML comment in Randall Holmes' page `https://randall-holmes.github.io/Loglan/cefli.html`: *"The original one, loglanists@ucsd.edu is dead (and alas, **we do not have archives for it**: people who have local archives of this list are encouraged to share them; I have records since about 2008). The new one is loglanists@googlegroups.com."* |
| **`loglanists@googlegroups.com`** | `https://groups.google.com/g/loglanists` → **HTTP 200**. Membership-gated in practice; no export without owner access (same limitation as the Lojban Google Groups documented in `mail-sources-inventory.md`) |
| `alt.language.loglan`, `sci.lang.loglan`, `comp.ai.nat-lang` on Google Groups | Probes returned **HTTP 429** (rate-limited) — **not verified**. No dedicated Loglan newsgroup is attested by any other source I could reach |
| Internet Archive Usenet collections | `usenet-alt.language.loglan`, `usenet-sci.lang.loglan`, `usenet-alt.lang.loglan`, `usenet-comp.ai.nat-lang` → all **HTTP 404**. `usenet-sci.lang` **exists** (71 files, giganews mbox dumps 2014–2015; `sci.lang.20140613.mbox.gz` alone is 546 MB) and `FULL-USENET-BACKUP-2020-Oct-sci.lang.317425.mbox.7z` holds 317,425 sci.lang messages. `utzoo-wiseman-usenet-archive` covers 1981–1991 Usenet. **Inferred:** Loglan discussion of the 1980s–90s exists scattered inside `sci.lang` / `net.nlang`, not as a group of its own; extraction would be a grep over multi-hundred-MB mboxes |
| "loglan" Yahoo group | Wayback CDX for `groups.yahoo.com/group/loglan*` returned **zero rows** in this session (the equivalent query in `mail-sources-inventory.md` §M found only `lojban*` groups). **Inferred:** no TLI Yahoo group of substance |

**Conclusion:** there is no acquirable TLI mailing-list corpus. The 1988–1991 fork
discussions that *are* recoverable live in Lojban List (from 1989-12-07) and in JL — both
already in scope for jbomo'i.

---

## 5. Loglan software and grammar files

### 5.1 On loglan.org

| Item | URL | Format / size | Date | Rights |
|---|---|---|---|---|
| **Machine grammar "Trial 80"** (YACC) | `https://www.loglan.org/Misc/grammar80.y` | YACC source, **33,541 B** | 2000-02-22 | In-file header: *"GRAMMAR 80 — Loglan grammar as of Dec 94 / **Copyright (C) 1982, 1984, 1986-1995 by The Loglan Institute, Inc.** / Created in Jan-Feb 82 from JSP's Aug 81 grammar by SWL & JCB, Modified … by JCB, and in 1987-90 by RAM."* The header is a **trial-by-trial changelog back to Trial 74** — a compact grammar-evolution record |
| **LIP (Loglan Interactive Parser) source** | `https://www.loglan.org/Download/Parser/` — 17 files: `ibmlip.c` 24 K, `maclip.r` 49 K, `parse.c` 18 K, `pback.c` 21 K, `preparse.c` 21 K, `putil.c`, `yyparse.c`, `parse.h`, `maclip.h`, `extval.h`, `lextab` 19 K, `liphelp`, `YC.TAB` 41 K, `YC1.TAB`, **`trial.85` 28 K** (the YACC grammar then in use), `Readme.txt/.html` | C + YACC | 2001-12-13/15 | `/source-code.html`: *"The Loglan Institute is making the source code for its various software products available for download. **Permission is given to use and modify these programmes in any way which will be of benefit to the Loglan community.**"* → **TLI-perm, closest thing to an open licence TLI has granted** |
| LIP binaries / later builds | `/Download/LIP-OSX.dmg` 373 K, `LIPExec6May2012.zip` 53 K, `LIPSource6May2012.zip` 156 K, `lip_cli_2-May-2012.zip` 48 K, `lip_source_2-May-2012.zip` 122 K, `ParserArchive.zip` 98 K, `Parser_XCode.zip` 222 K | binaries + source | 2009–2012 | same |
| **LOD dictionary data + reader** | `https://www.loglan.org/Download/Dictionary/` — `dict.eng` **2.2 MB**, `dict.log` **1.6 MB**, `index.eng` 182 K, `index.log` 117 K, `prim.set` 42 K, `rddict.c`, `rddict.h`, `Readme.txt` | flat data files + C | 2001-12-14 | same |
| **MacTeach 1/2/3 source + data** | `https://www.loglan.org/Download/LoglanTeach/` — 22 files incl. `prims` 55 K, `affs` 37 K, `aff.set` 42 K, `utts` 39 K, `M1-Text` 21 K | C + Mac resource + data | 2001-12 | same |
| LOD binaries | `/Download/LOD*.sit.hqx`, `LODCoreSources.tar` 247 K, `MacLODSources.sit` 272 K, `JavaLOD.app.zip` 1.3 MB, `LODDataFiles.dmg` 1.7 MB | Mac archives | 2000–2009 | same |

The literal string "GPA" does not appear on the site; the machine-grammar artefacts are the
`grammar80.y` / `trial.85` / `YC*.TAB` family above, plus Holmes' PEG (below).

### 5.2 Randall Holmes' site — the richest un-catalogued source

`https://randall-holmes.github.io/` = GitHub repo **`Randall-Holmes/Randall-Holmes.github.io`**
(created 2020-06-05, last push 2026-08-13, **no LICENSE file**). Its `Loglan/` subtree holds
**433 files / 330,020,375 bytes** (verified via the GitHub trees API, `truncated: false`).
Cloning the repo acquires everything in one operation.

| Group | Path | Size | Notes |
|---|---|---|---|
| **Notebook 1 & 2 scans** | `Loglan/NB1 and NB2 scans/` — `NB2-1.pdf` 23.5 MB, `NB2-2.pdf` 14.3 MB, `NB2-3.pdf` 12.8 MB, `NB2-4.pdf` 7.6 MB (30 pp), `macgram-corpus-1.pdf` 13.5 MB, `macgram-corpus-2.pdf` 17.3 MB, `macgram-corpus-3-and-preparser.pdf` 11.7 MB, `macgram-glossary.pdf` 9.8 MB, `trial-19.pdf` 5.1 MB (17 pp) | **115,521,691 B, 9 files** | All *"Microsoft: Print To PDF"*, Author "Randall Holmes", created **2024-05-21**. **Image-only, no OCR layer** (`pdftotext` empty). *Inferred:* `macgram-*` = Notebook 1 *The Machine Grammar and Corpus of Loglan* (1982); `NB2-*` = Notebook 2 *A Proposed Revision in the Structure of Loglan Words* (1982); `trial-19` = an early grammar trial. **These 1982 documents are pre-fork and exist nowhere else online.** |
| **Notebook 3, OCR'd** | `Loglan/Reports/nb3-ocr-original.pdf` 787,107 B (**150 pp, real text layer**) and `.doc` 1,127,936 B | ~1.9 MB | **Carries the only explicit TLI licence statement found anywhere:** *"Copyright© 1987 by The Loglan™ Institute, Inc. … **Note added 7/28/2014: this document remains intellectual property of the Loglan Institute. It is licensed freely for private non-commercial use by people interested in Loglan or Lojban; please contact us about any other use.**"* — note it names **Lojban** explicitly. Its preface also fixes the pre-fork lineage: NB3 is *"a revision and extension of The Institute's two previous notebooks, both published in 1982, and the two special issues of The Loglanist, TL6/1 (1983) and TL7/1 (1984)"* |
| Loglan 1 mirror + revision in progress | `Loglan/Loglan1/` — 46 files, 2,855,691 B, incl. `Loglan-1-4-2025.html`, `Loglan-draft.html`, `Loglan-old.html`, `chap2-revised.html`, `pronunciation.mp3` | 2.9 MB | Holmes' corrected/annotated Loglan 1, tracking the current PEG grammar |
| Reference grammar & PEG | `Loglan/Reports/reference_grammar_proposed.{tex,pdf}` (283 K/552 K), `newgrammar.{tex,pdf}`, `draft-grammar-with-comments-alternative.peg` 117,909 B, `Loglan/Reports/Loglan reference project starting 7-29-2021/` | ~1.5 MB | Revised 2025-10-11 per `cefli.html` |
| Reports | `fall2015loglanreport.pdf` 802 K, `loglanagenda.{tex,pdf}`, `loglanpublicagenda8-11-2013.pdf`, `2019-Loglan-Report.pdf`, `inventory.pdf` | ~1.4 MB | Two are also mirrored on loglan.org `/Articles3/` |
| Dictionaries | `Loglan/Dictionary/` 18 files, 58,545,988 B (`E-to-L*.html` ~5.2 MB each, `LoglanDictionary*.mdb` ~5.3 MB each) | 58.5 MB | The live TLI web dictionary |
| Texts & corpora | `Loglan/Texts/` 270 files, 62.3 MB (incl. `loglandia/loglandia_all.txt` 5.8 MB), `Loglan/Sources/corpus-original.{txt,llg}` | 68 MB | NB3 teaching corpus re-fitted to the modern parser |
| Second Life transcripts | `Loglan/LoglanTranscriptsV2.txt` **14,131,332 B** | 14 MB | Weekly Loglan conversation-group logs from 2008 on, with editorial notes by Holmes and Cyril Slobin. **A genuine post-fork usage corpus** — the nearest TLI equivalent to Lojban IRC logs |
| Loglan Notebook 4 | `Loglan/2023 reference project/LoglanNotebook4.{tex,pdf}` | 290 K PDF | New (2023) |

---

## 6. What is already Lojban-side (do not duplicate `wiki/` or `mail/`)

| Item | Location | Note |
|---|---|---|
| LeChevalier's dispute essay | `mw.lojban.org/papri/the_Loglan-Lojban_Dispute` **and** `lojban.org/old-style/publications/loglan.html` | Two copies of one text; wiki version is the canonical one for `wiki/` |
| `Lojban timeline` | `mw.lojban.org/papri/Lojban_timeline` (97,999 B, edited 2026-08-02) | Dated entries 1955→; supplies the fork chronology |
| `Loglan`, `Loglan 1`, `The Loglan Institute`, `Freudenthal's critique of Loglan`, `borrowing from Loglan`, `Neat features of Loglan that Lojban lacks`, `Near-optimal Loglan syntax`, `Design and Implementation of a Near-optimal Loglan Syntax`, `connotations of using Loglan` | `mw.lojban.org/papri/…` (23 hits for `Loglan` in the wiki search API) | All arrive with the wiki dump |
| **Scientific American 1960 PDF** | `mw.lojban.org/images/9/9a/…pdf` | Arrives with the wiki *images* dump — make sure images are pulled, not just wikitext |
| `Old Loglan gismu` / `oldlog.txt` | wiki page 14477 (98,671 B); original at `https://www.lojban.org/publications/wordlists/oldlog.txt` (GET 200; HEAD returns 521) | *"Correspondence between Lojban gismu and TLI/historical Loglan words — Copyright 1993, The Logical Language Group, Inc."* Its own bibliography names the pre-fork sources it was built from, incl. the **JCB & LeChevalier "Complex-Making Algorithm" (1986)** and the **raw 1974–5 Loglan dictionary computer files** |
| JL1–18, LK8–11, LK18 | `lojban.org/files/jl/` | Already scheduled |
| `L1LONGRV.TXT`, `useoldL1.txt` | `lojban.org/files/papers/` | LLG-perm |
| `eaton.zip` | `lojban.org/files/etymology/eaton.zip` (HTTP 200) | Roadmap: *"old Eaton data from an earlier stage of the **Loglan Project**"* — i.e. **pre-fork JCB-era data now on the Lojban file server** |
| 1988 grammar/gismu lineage | `lojban.org/files/history/` — `GRAMMAR.NEW` (28 Oct 1988), `GRAMMAR.B17`, `GRAMMAR.E25`, `GRAMMAR.L23`, `GRAMMAR.506`, `GRAMMAR.28`, `BNF.28`, `GRSYN.DOC` (Oct-88 synopsis), `CMAV1088.ZIP`, `CMAV0290.ZIP`, `ROGETNEW.TX1`, `bothraf.txt`, `BYLAWS.792.txt`, `ANMTG*.DOC` (1992–98 minutes), `lojban10.html` | 26 files | The Lojban-side fork artefacts; `GRAMMAR.NEW` of **1988-10-28** is the earliest complete Lojban grammar |
| Brochure "Loglan vs Lojban comparison" | Roadmap advertises `brochures/loglan.txt`; the file is **HTTP 404** today | Only recoverable from Wayback |

No `loglan/` subdirectory exists on `lojban.org/files/` (the roadmap lists 21 directories;
none is `loglan`). The Loglan material on the Lojban file server is scattered through
`brochures/`, `papers/`, `etymology/`, `history/` and `publications/wordlists/`.

---

## 7. What belongs in the repository

Relevance codes: **F** pre-fork foundational · **D** dispute record · **C** post-fork
comparative. Disposition codes: **STORE** full content · **CITE** metadata + URL + hash only ·
**ASK** blocked on permission (see 7.1) · **SKIP**.

| # | Item | Rel. | Format / how to acquire | Republication right | Disposition |
|---|---|---|---|---|---|
| 1 | Fed. Cir. opinion, 962 F.2d 1038 (1992-04-28) | D | `curl https://static.case.law/f2d/962/cases/1038-01.json` → 12.6 KB text | **PD** (US judicial opinion) | **STORE** verbatim. Highest-value unencumbered dispute document |
| 2 | LeChevalier, "Loglan and Lojban — about the dispute" (1991/2000) | D | already in wiki dump; second copy `lojban.org/old-style/publications/loglan.html` | LLG-perm | **STORE** (via `wiki/`; keep the `old-style` copy only if bytes differ) |
| 3 | `L1LONGRV.TXT`, `useoldL1.txt` | D/F | HTTP GET, ~85 KB | LLG-perm | **STORE** under the Lojban file-server projection |
| 4 | `oldlog.txt` / `Old Loglan gismu` | F/C | HTTP GET + wiki dump | LLG (1993) | **STORE** |
| 5 | `eaton.zip` (pre-fork Eaton frequency data) | F | `lojban.org/files/etymology/eaton.zip` | LLG file server, `?` | **STORE** |
| 6 | JL1–18 / LK8–11,18 | D | already scheduled | LLG | **STORE** (no Loglan-specific action) |
| 7 | **Scientific American, "Loglan", June 1960, 11 pp** | F | already in the wiki image dump (585,581 B, OCR'd) | **Scientific American, Inc. — third party.** Not TLI's to license | **STORE the metadata + extracted OCR text as a citation record; keep the PDF only inasmuch as it already arrives with the wiki dump.** Do not re-publish it as a standalone repository artefact |
| 8 | TLI bibliography of pre-fork Loglan (all TL volumes, Notebooks, 1956/1960/1966/1969/1975 editions) | F | scrape `loglan.org/Loglan1/bibliography.html` (~17 KB) → structured citation list | Facts/citations — **PD as data** | **STORE** as a generated bibliography file. Cheapest high-value item on this list |
| 9 | TLI catalogue `/loglan-offerings.html` | F/C | HTTP GET, 24,300 B | TLI, `?` | **CITE** + store extracted facts (ISBNs, page counts, TL print status) |
| 10 | **Loglan 1, Revised 4th ed. — full HTML** | F | `Download/Loglan1.zip` 817 KB → 20 HTML files | **TLI-perm, non-commercial personal copy; redistribution not granted** | **ASK** (rank 1). Until then **CITE** + store per-chapter URLs, sizes, and section index |
| 11 | **Notebook 3 (1987) — OCR'd, 150 pp** | F | `randall-holmes.github.io/Loglan/Reports/nb3-ocr-original.pdf` | **TLI-perm: "licensed freely for private non-commercial use by people interested in Loglan or Lojban; please contact us about any other use"** | **ASK** (rank 2) — the note invites exactly this request. Meanwhile **CITE** |
| 12 | Notebook 3 scans (3 PDFs, 16 MB, image-only) | F | `loglan.org/Download/NB3-Part-{I,II,III}.pdf` | as #11 | **ASK**; prefer the OCR'd copy for a text repository |
| 13 | **Notebook 1 & 2 (1982) scans** | F | `git clone Randall-Holmes/Randall-Holmes.github.io` → `Loglan/NB1 and NB2 scans/` 115 MB, 9 PDFs, no OCR | TLI (inferred; no notice on the files, repo has no LICENSE) | **ASK** (rank 3). Would need OCR. **Unique — nowhere else online** |
| 14 | **The Loglanist, TL1–TL7 (21 issues, 1976–84)** | F | **Print only.** 8 of 21 in print as of ~2000; TLI offered facsimile title pages | TLI | **ASK** (rank 4) + **CITE**: build the article-level index from #8 today |
| 15 | Lognet 89/1–00/1: ~90 re-set articles + 22 cartoons | D/C | crawl `loglan.org/{Articles,Articles2,Lodtua,Sanpa,People,Cartoons}/` (~600 KB) | **TLI-ARR** per-article footers | **ASK** (rank 5) + **CITE**: store `/Lognet/index.html` as a contents index now |
| 16 | Lognet 99/1 full-issue TIFF scan | C | `Download/lognet99-1.zip` 9.8 MB | TLI-ARR | **ASK** + CITE |
| 17 | **Machine grammar `grammar80.y` (Trial 80, Dec 94) + `trial.85`** | F/C | HTTP GET, 33 KB + 28 KB | © TLI 1982–1995; covered by the `/source-code.html` grant *"use and modify … in any way which will be of benefit to the Loglan community"* | **STORE** with the grant text quoted alongside. Its header changelog (Trials 74→80) is a primary grammar-evolution record |
| 18 | LIP / LOD / MacTeach sources + data | C | `loglan.org/Download/{Parser,Dictionary,LoglanTeach}/`, ~5 MB | same TLI grant | **STORE** (or CITE if the "benefit to the Loglan community" reading is judged too narrow for a public mirror) |
| 19 | Loglan 4&5 searchable HTML | F/C | `LOD/L4and5.zip` 1.5 MB → 8.2 MB HTML | `?` no notice found | **ASK** + CITE |
| 20 | Loglan 3 (Rice, 1997), 3 PDFs | C | `Download/L3.vol{1,2,3}.pdf` | **Shareware, $5** | **CITE only** |
| 21 | *Readings from Loglan 1* MP3s, 2 h 28 m / 61 MB | C | `loglan.org/Tapes/` | **TLI-ARR, redistribution explicitly refused** | **CITE only** — do not mirror |
| 22 | Holmes: reference grammar, PEG, reports, Loglan 1 revision | C | `git clone` the GitHub Pages repo | No LICENSE; Holmes is TLI/Loglan Center CEO | **ASK** (rank 8) — one email covers the whole repo |
| 23 | `LoglanTranscriptsV2.txt` — Second Life logs, 2008– , 14 MB | C | same repo | participants + Holmes | **ASK** (rank 9); privacy review needed (real names, pseudonyms) |
| 24 | IA `Loglan1` re-upload | — | — | uploader-asserted CC BY-NC-ND that contradicts TLI's notice | **SKIP** as a rights source; **CITE** as an alternate mirror + note the conflict |
| 25 | IA `loglan1logicalla0000brow` (1975 3rd ed.) | F | lending-only scan | controlled digital lending | **CITE only** (identifier, LCCN 75012985, OL5192215M) |
| 26 | HathiTrust `mdp.39015037447326` (1975 3rd ed.) | F | search-only | `ic` / Limited | **CITE only** |
| 27 | `loglanists@ucsd.edu` archive | D/C | **does not exist** — Holmes states TLI has none; Wayback has no Pipermail captures | — | **SKIP**; record the negative finding and the standing request for private copies |
| 28 | Loglan threads inside `sci.lang` Usenet | D | IA `usenet-sci.lang` (546 MB+ mboxes), `utzoo-wiseman-usenet-archive` | Usenet posts, mixed | **SKIP for now**; revisit as a grep-extraction task if the Usenet corpus is ingested for Lojban anyway |
| 29 | `loglangs.wiki` dump (2023-09-29) | C | IA `wiki-loglangs.wiki-20230929`, `history.xml.zst` 220 KB | per `loglangs.wiki/Meta:Copyrights` | **CITE**; small, low priority |
| 30 | Wayback snapshots of loglan.org (earliest **2000-08-15**) | C | CDX API | — | **CITE**; use to recover the dead `brochures/loglan.txt` and any withdrawn pages |

### 7.1 Relicensing candidates (ask TLI)

Ranked by historical value to *Lojban's* history. "Rights holder as stated" is what the
document itself says — several items are **not TLI's to relicense**.

| Rank | Title | Date | Format available | Approx. size | Why it matters | Rights holder **as stated on the document** |
|---|---|---|---|---|---|---|
| 1 | **Loglan 1: A Logical Language**, Revised 4th ed. (electronic ed. of the 1989 print) | 1989 / HTML ed. 1999 | HTML (20 files, per chapter) + ZIP + PDF | 817 KB zip · 2.5 MB HTML · 4.6 MB PDF | The book Lojban forked away from; every Lojban design argument of 1987–91 cites it by chapter and section. Appendix H (Sattley's *Updater*) documents 1989–96 divergence | Copyright page: **"Copyright © 1966, 1969, 1975, 1989 by The Loglan Institute, Inc."** — TLI, cleanly |
| 2 | **Notebook 3: The Present State of the Loglan Language** | 1987 | OCR'd PDF (150 pp, text layer) + `.doc`; also 3 image-only scans | 787 KB OCR PDF · 16 MB scans | **The pre-fork grammar reference.** 1987 is the fork year; this is the language Lojban actually diverged from, and the LLG review (`L1LONGRV.TXT`) argues against it directly | **"Copyright© 1987 by The Loglan™ Institute, Inc."** + 2014 note: *"remains intellectual property of the Loglan Institute … licensed freely for private non-commercial use by people interested in Loglan or Lojban; please contact us about any other use."* — TLI, and it already invites the ask |
| 3 | **Notebook 1: The Machine Grammar and Corpus of Loglan** and **Notebook 2: A Proposed Revision in the Structure of Loglan Words** | both 1982 | Image-only PDF scans (`macgram-*`, `NB2-*`) on Holmes' GitHub Pages | 115 MB total (9 files) | The Great Morphological Revision and the YACC machine-grammar work — the technical crisis of 1978–83 that produced the language Lojban forked. **Available nowhere else**; would need OCR | No notice observed on the scans; TLI as publisher (bibliography: "The Loglan Institute, Gainesville, Florida"). *Inferred* TLI; **confirm** — scans were made by Randall Holmes |
| 4 | **The Loglanist (TL), vols. 1–7, 21 issues** | 1976–1984 | **Print only** — 8 of 21 issues in print c. 2000; TLI held the masters and offered facsimile title pages | ~21 issues × ~100 pp | The complete pre-fork technical debate: JCB's GMR papers, the affix-resolvability work, McIvor's taste tests, the Parks-Clifford editorship — and TL6/1 (1983) and TL7/1 (1984), which NB3 was built from. **Its absence is the single biggest hole in the Loglan record** | TLI (journal of The Loglan Institute; individual articles by named authors — JCB, Parks-Clifford, McIvor, Barton, Carter, May and others, so TLI may not hold every article) |
| 5 | **Lognet 89/1 – 00/1** (esp. 90/2 and 90/3: Rex May's *Critique of Loglan Morphology* + JCB's *Defense* / *Critique of "Rexlan"*; 91/1–91/2 *Shoot the Engineer* exchange) | 1989–2000 | ~90 articles as clean HTML; 1 full issue as TIFF | ~600 KB HTML · 9.8 MB TIFF | Runs exactly across the split and the litigation. JCB's own voice, issue by issue (*Sau La Sacdonsu*), during the years LLG was suing to cancel LOGLAN | Per-article footer: **"Copyright 19xx by The Loglan Institute, Inc. All rights reserved."** — TLI; cartoons by **Rex May ("Baloo")**, likely his own |
| 6 | **Loglan 4 & 5** dictionary (2nd ed. 1975) as searchable HTML | 1975 / HTML c. 2012 | ZIP of two large HTML files | 1.5 MB zip · 8.2 MB HTML | The vocabulary Lojban algorithmically replaced; `oldlog.txt` maps Lojban gismu onto exactly these words | TLI (`loglan-offerings.html`: "collated by JCB, 2nd Edition, 1975", ISBN 1-877665-01-0). No notice inside the HTML — **confirm** |
| 7 | **Loglan 1, 3rd ed. (1975)** and **1st "preprint" ed. (1966)**; **Loglan 1–5, 2nd ed. (1969 microfilm)** | 1966 / 1969 / 1975 | 1975: lending-only IA scan + search-only HathiTrust. 1966 & 1969: **no digital copy found** | 1975 scan ≈ 16 MB | The editions Lojbanists actually owned in the 1980s (`useoldL1.txt` is literally about using them). The 1966 preprint is what Freudenthal and Zwicky reviewed | Same TLI copyright line (1966, 1969, 1975). **TLI could authorise a fresh scan of its own 1966/1969 editions** — that is the ask worth making |
| 8 | Holmes' modern corpus: reference grammar, PEG grammar, parser, Loglan 1 revision, reports 2013–2026 | 2013–2026 | LaTeX + PDF + Python + HTML, in one Git repo | ~10 MB (excl. dictionaries/texts) | The comparative baseline: what TLI Loglan became after the fork, described formally enough to diff against Lojban's CLL and PEG | Randall Holmes personally, as TLI/Loglan Center CEO. Repo has **no LICENSE file** — a one-line grant would clear the whole tree |
| 9 | Second Life Loglan transcripts | 2008– | plain text | 14 MB | The only sustained TLI-Loglan *usage* corpus; the counterpart to Lojban's IRC logs | Holmes + named/pseudonymous participants — **not TLI's alone**; needs participant consideration |
| — | **Scientific American, "Loglan", June 1960** | 1960-06 | PDF, 11 pp, OCR'd, already on the Lojban wiki | 586 KB | The public birth of Loglan; the document everyone in both communities cites | **Scientific American, Inc.** (© 1960). **TLI cannot relicense this** — TLI only ever resold reprints. Any clearance must go to Springer Nature |
| — | *Readings from Loglan 1* audio | 1984–2009 | MP3 | 61 MB | JCB's and Jennifer Brown's own voices reading L1 | TLI, **"All rights reserved… download one copy for yourself for personal use"** — an explicit refusal of redistribution; asking means asking TLI to reverse a stated position |

### 7.2 Earliest date of any candidate document

- **Attested but not acquired:** J. C. Brown, *Loglan: An Experiment in Language
  Construction*, Dept. of Sociology and Anthropology, University of Florida, Gainesville,
  **1956** (mimeographed) — cited in the Loglan 1 bibliography; the Fed. Cir. opinion
  independently confirms *"He first used the term Loglan in a publication in 1956"*. No
  copy located online.
- **Earliest acquirable document: 1960-06** — *Loglan*, Scientific American 202(6), 11 pp,
  already held as a PDF in the Lojban wiki image set. (A second 1960 item, *Some
  Observations on the Loglan Predicate*, International Language Review 6:21, December 1960,
  is cited in the same bibliography and was not located.)

**Recommendation for the root commit:** date it **1960-06-01**, the Scientific American
issue date — the earliest document jbomo'i can actually hold. Record 1955 (invention) and
1956 (first publication) as timeline facts sourced to the Fed. Cir. opinion and the Loglan 1
bibliography, not as commits. If the root commit must correspond to something whose bytes
are unencumbered, use the same date but seed it with the generated bibliography (item #8)
rather than the copyrighted PDF.
