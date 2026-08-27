# Lojban formal grammars and parsers: inventory

**Purpose.** Decide, for every formal grammar and parser implementation of Lojban, whether it
enters jbomo'i as a git **submodule** (§3.1.6 of `doc/SPEC.md`) or as a **vendored copy with
provenance**, and settle the layout of `grammars/` promised by §3.11.

**Method.** Everything marked *verified* was observed on **2026-08-27 (UTC)** from this machine:
`curl -sI`/`curl -sL` against the live URL, the GitHub REST API via `gh api`, the GitLab v4 API,
the Wayback CDX API, or a local read-only mirror (`~/git/jbofihe`, `~/git/ilmentufa`,
`~/git/grammar-review/upstream/gerna_cipra`, `~/git/cll`, `~/git/jbotci`, `~/git/lojban-ebnf`) or
the vendored wiki snapshot at `~/lojban/wiki`. Sizes and dates are what the server or the API
returned. Items marked *inferred* are conclusions from verified evidence, not direct observations.
Where a local mirror is shallow or stale, the API figure is used and the discrepancy noted.

**Legend.** *mechanism* → `sub` submodule · `vendor` vendored files · `skip` recorded but not
imported. Commit counts are for the default branch.

---

## 1. The official grammar (Logical Language Group)

The official grammar is a document series, not a program. Six generations survive online, all
under the LLG's "permission to copy … for promotion of Lojban" grant (the 3rd baseline adds an
explicit public-domain dedication).

| Generation | Files | Size | Where | Header self-description (verbatim) |
|---|---|---|---|---|
| `grammar.a27` | `GRAMMAR.A27` | — | **404, never published** | referenced as `/*grammar.a27 */` by the two files below |
| undated YACC drafts | `GRAMMAR.B17` (71,187 B), `GRAMMAR.NEW` (69,501 B) | — | `lojban.org/files/history/` | no copyright block; both tagged `/*grammar.a27 */`; `NEW` differs from `B17` in 337 lines (adds `%token tense.974`, comments out `cmene`/`TUhE` productions). Both lack `BEhO` and use `BIhI.506`, so they **predate** `L23` *(inferred; a letter-month code with `A`=Oct 1988 would date `B17` to 1988-11-17 — inferred, not verified)* |
| 1989-02-25 | `GRAMMAR.E25` (61,721 B) | 61 K | `…/history/` | "LOJBAN MACHINE GRAMMAR AS OF 25 FEBRUARY 1989; NON-BASELINE" |
| 1989-09-23 | `GRAMMAR.L23` (67,682 B) | 68 K | `…/history/` | "… AS OF 23 SEPTEMBER 1989; NON-BASELINE"; adds "WE PLAN TO PLACE THE GRAMMAR IN THE PUBLIC DOMAIN UPON BASELINE APPROVAL" |
| 1990-05-06 | `GRAMMAR.506` (67,217 B) | 67 K | `…/history/` | "… AS OF 6 MAY 1990; NON-BASELINE" |
| **1st baseline 1990-07-20** | `GRAMMAR.28` (66,149 B), `BNF.28` (7,493 B), `techfix.28` (17,306 B) | — | `…/history/` | "BASELINED AS OF 20 JULY 1990 / INCORPORATES JC'S TECH FIXES 1-28"; approval "EXPECTED LATE IN 1990" |
| **2nd baseline 1991-06-23** | `bnf.28` (restamped) | — | Wayback `…/files/machine-grammars/bnf.28`, capture 1999-11-04 | "BNF VERSION, BASELINED AS OF 23 June 1991" — the 1990 BNF re-headed, since the 2nd baseline *is* "original + tech fixes 1–28" |
| 2.33 (1993-06-22) | `GRAMMAR.233` (68,280 B), `BNF.233` (8,296 B), `TECHFIX.233` (39,377 B) | — | **only inside** `lojban.org/files/software/parser/parser.zip` / `parser.shar.gz` | "2ND BASELINE AS OF 23 JUNE 1991 / WHICH IS ORIGINAL BASELINE 20 JULY 1990 INCORPORATING JC'S TECH FIXES 1-28 / THIS DRAFT ALSO INCORPORATES CHANGE PROPOSALS 1-33 DATED 22 JUNE 1993" |
| 2.35 (1994-03-29) | `bnf.235`, `techfix.235` | — | Wayback `…/machine-grammars/`, capture 1999-11-04 / 1999-10-09 | "2nd BASELINE AS OF 23 JUNE 1991 … change proposals 1-35 … dated 29 March 1994"; `grammar.235` **404** |
| 2.46 (1996-03-20) | `bnf.246` | — | Wayback, capture 1999-10-09 | "change proposals 1-46 … dated 20 March 1996 by Clark Nelson" |
| 2.47 (1996-12-20) | `bnf.247` | — | Wayback, capture 1999-10-09 | "change proposals 1-47 … revision dated 1996-12-20 by Clark Nelson"; `grammar.247` **404** |
| **3rd baseline 1997-01-10** (current) | `grammar.300` **70,645 B** (sha256 `b863a728…`), `bnf.300` **8,259 B** (`5184c36a…`), `techfix.300` **54,386 B**, `xref.300` **25,769 B**, `PD` **1,023 B**, each duplicated as `.txt` with identical bytes | — | `lojban.org/publications/formal-grammars/`, every file `Last-Modified: Tue, 11 Jan 2005 08:30:22 GMT` | "3RD BASELINE AS OF 10 JANUARY 1997 / WHICH IS ORIGINAL BASELINE 20 JULY 1990 INCORPORATING JC'S TECH FIXES 1-28 / THIS DRAFT ALSO INCORPORATES CHANGE PROPOSALS 1-47 DATED 29 DECEMBER 1996 … EXPLICITLY DEDICATED TO THE PUBLIC DOMAIN BY ITS AUTHOR, THE LOGICAL LANGUAGE GROUP INC." |

**Numbering, now verified rather than guessed.** `.NN` on the 1990 files counts *tech fixes*;
`.2NN` = 2nd baseline plus *change proposals* 1–NN; `.300` = 3rd baseline, revision 00. Only the
**BNF** forms of 2.35/2.46/2.47 were ever served — the YACC text of the 2nd-baseline line survives
solely as `GRAMMAR.233` inside the two parser archives.

**Where the files have lived** (verified): today `https://lojban.org/files/machine-grammars/`
serves the *same* Apache index as `/publications/formal-grammars` — one directory, two paths, so
the wiki's old `files/machine-grammars/*` links still resolve; directory indexing is on across
`/files/`, so the whole tree is enumerable. Historically the paths moved: Wayback shows
`/files/machine-grammars/` carrying the whole 2.x BNF line in 1999, no `history/` directory in the
1999-05-08 roadmap (it first appears 2000-09-02), `/publications/formal-grammars/` first appearing
2006-05-09, and the old path returning 200 through 2005-04-04, 404 from Aug 2005 and 301 from Oct
2007. The 3.00 files have been byte-stable since at least February 2000 (a 2001-12-24 listing shows
the same 1 K / 8 K / 69 K / 53 K / 25 K sizes as today). `techfix.28` was added to `history/` only
in 2005 — it is the one file there not stamped 2002-09-06.

The precedence rule also moved: the 1999-05-08 roadmap says "**the YACC is authoritative**"; by
2000-08-17 the softer "the YACC takes precedence" plus "Chapter 21 … the most authoritative source"
wording is in place — the phrasing the wiki still carries.

`grammar.300` also lives in git: `lojban/cll` carries it as **`scripts/yacc/lojban_grammar.y`**
(1,810 lines, header "grammar.300"), beside `scripts/yacc/lojban_grammar.md`,
`user_friendly_grammar.txt` and `convert.py` (verified in `~/git/cll`, a checkout of the
`int19h/cll` fork). The EBNF is `chapters/21.xml`, "Formal grammars" (113,420 B). Since
`doc/SPEC.md` §3.6 already pins `cll/src` to `int19h/cll`, **the official YACC and EBNF arrive
with the CLL submodule** and must not be vendored a second time under `grammars/`.

The wiki page **`Lojban Formal Grammars`** (pageid 1511, rev 2015-08-07) is the community's own
map of this: it lists exactly `bnf.300`, `grammar.300`, `techfix.300`, points at CLL chapter 21 as
"the baseline grammar document, … the most authoritative source", states "If the BNF and YACC
versions do not agree, the YACC takes precedence", and announces a "Proposed 4th Baseline" in PEG
by `.alyn.post.` and the BPFK. It does **not** mention the 1989/1990/1993 generations above —
those are recoverable only from `/files/history/`, `parser.zip`, and Wayback.

---

## 2. Implementations

### 2.1 The official-grammar era (YACC/BNF, 1989–2003)

| Name | Author | Language | Formalism | Dialect | Years | Where it lives | Kind |
|---|---|---|---|---|---|---|---|
| **Official LLG parser (2nd baseline)** | John Cowan for LLG | K&R C + YACC | YACC (`grammar.233`) + hand-hacked `grammar.c` + C "lexer" pre-pass | 2nd baseline | 1989–1993 | `lojban.org/files/software/parser/parser.shar.gz` (76,350 B), `parser.zip` (75,024 B), `PARSER3.ZIP` (41 K, `parser.exe` 1998-10-09), `parse.lzh` (81 K), `ansi.c.bug` (968 B) — all `Last-Modified: 2002-09-06` | files only |
| **Official LLG parser 3.0.00** | John Cowan | K&R C + YACC | YACC (`grammar.300`, `grammar.y`, `bnf.300`, `gmiddle.y`) + a C "compounder"/lexer pre-pass | 3rd baseline | 2001–2003 | `ccil.org/~cowan/parser-3.0.00.tar.gz` — **dead** (`content-length: 0`); recovered from Wayback `20130116042930`, 123,925 B, sha256 `a86a77d4…`, gzip mtime 2003-11-13, sources 2003-11-13 and grammar files 2001-05-23; **also in git** as `github.com/lojban/cll-parser` ("ye olde baseline parser (version 3.0.00 from the CLL)", 1 commit 2014-07-27, licence file = **AFL 2.0**) | git (1 commit) + Wayback tarball |
| **jbofi'e / jbofihe** | Richard Curnow | C | Bison grammar `rpc2x.y` (2,339 lines) developed "directly from the LLG's bnf.300", made LALR(1) with extra tokens from `categ.c`; morphology by a hand-built DFA generator (`dfasyn/`) | 3rd baseline | 1999–2003 (Curnow), 2016– (LLG) | `github.com/lojban/jbofihe` | **git** |
| **Lojban semantic analyser** | Nick Nicholas | NU-Prolog + lex | consumes the official parser's `-dl` output | 2nd baseline | 1993 | `lojban.org/files/software/analyser` (23,068 B, 2002-09-06); paper `lojban.org/files/papers/lojban_parser_paper` (24,354 B) and `nsn_semantics_paper` (22 K) | files only |
| **valfendi** | Pierre Abbat (phma) | C++ | hand-written lexer, implementing `brkwords.txt` | morphology only | 2014 | `github.com/phma/valfendi`, 2 commits, 2014-09-23, no licence | git (tiny) |

**jbofihe, verified in detail** (local mirror + API): `README.GIT` states "The git repository was
cloned from the original CVS repository on 5th April 2010 using `git cvsimport -k -i …`". Default
branch `master`; **683 commits**, first `df0f5c50` **1999-06-12** ("Initial revision", author
`richard`), last `652c20e6` **2025-11-29**; **47 tags** from `0_2` (1999-06-27) through `V0_38_1`
(2001-11-06), `Vsnap_20030418` (2003-04-18), then LLG-era `v0.40` (2016-09-05) … `v0.44`
(2025-11-29); licence **GPL-2.0** (`COPYING`). Richard Curnow's last commit is 2003-04-27; 631 of
683 commits are his. The author's own site `www.rpcurnow.force9.co.uk/jbofihe/` is **404** and
`rc0.org.uk` now redirects to `about.me/rc0`; Wayback holds `jbofihe-0.38.tar.gz` (325,274 B),
`jbofi038.zip` (664,257 B), `jbofihe-snap_20030418.tar.gz` (438,017 B), two inter-release patches
and `smujmaji.dat.gz` (302,380 B) — all superseded by the git history, which contains the same
releases as tags. Debian shipped 0.38-2 (woody) … 0.38-5.1 (jessie). `lojban/lojban-cvs` (created
2013-10-31, C, no licence) contains a second import of the same `jbofihe` CVS module.
`vlatai`, which the wiki describes as "a program that comes with jbofi'e … determines the class of
the lojban word", is a jbofihe binary (`vlatai.1` is in the repo), not a separate project.

The wiki calls jbofihe "the de facto standard glosser and parser for Lojban" and notes the name is
*Babelfish* → "Lojbanic fish". Its live web front-end is **jboski** (`lojban.org/jboski` →
`jboski.lojban.org`, HTTP 200; source `github.com/lojban/jboski`, MIT, 2021-08-15 → 2025-11-30).

### 2.2 camxes — the original PEG line (2004–2011)

This is the pivot of the whole story and its history **does survive**.

Every wiki page that discusses camxes links to
`www.digitalkingdom.org/~rlpowell/hobbies/lojban/grammar/`. The same directory is **live today** at
**`http://teddyb.org/~rlpowell/hobbies/lojban/grammar/`** (verified, HTTP 200, titled *Issues With
The Lojban Formal Grammar*, banner "HISTORICAL INTEREST ONLY", pointing readers at
`github.com/lojban/ilmentufa` "as of Jan 2025"); `lojban/camxes`'s own README gives the teddyb.org
address as the home of "the historical work". *(That the two are the same directory under a new
hostname is inferred from the identical path and contents, not from a redirect.)* Files, with
`Last-Modified` as returned:

| File | Size | Last-Modified | What it is |
|---|---|---|---|
| `lojban.bnf.txt` | 8,259 B | 2004-02-10 | **byte-identical to `bnf.300`** (verified by diff) — the starting point, unmodified |
| `lojban2.bnf.txt` | 8,777 B | 2004-02-11 | `bnf.300` mechanically cleaned by `bnf_conv.pl` |
| `bnf_conv.pl.txt` | 1,520 B | 2004-02-10 | the converter |
| `lojban.abnf.txt` | 21,359 B | 2004-03-28 | RFC 2234 ABNF form |
| `abnf2peg.pl.txt` | 988 B | 2004-03-17 | ABNF → PEG converter |
| `orig_lojban.peg.txt` | 21,730 B | 2004-03-17 | the **auto-generated** PEG, before hand work |
| `lojban.peg.txt` | 50,652 B | (2025-01-13 refresh) | the hand-modified camxes PEG, head revision |
| `morph_header.peg.txt` | 2,054 B | 2005-12-16 | grammar↔morphology interface |
| `rats/peg2rats.pl` | 8,098 B | 2005-12-17 | PEG → Rats! translator |
| `rats/Howto.cook` | 1,235 B | 2005-12-16 | build instructions |
| `rats/lojban_peg_parser.jar` | 859,090 B | **2006-08-21** | the Java **Rats!/xtc** parser |
| `test_sentences.txt` | 899,399 B | 2005-01-28 | test corpus |
| `jc_mail.txt` | 11,132 B | 2004-02-10 | John Cowan correspondence |
| `lojban_morphology.peg.txt` | — | — | **404** — the page still links it; the file survives in the tarball as `lojban_morphology_old.peg` (22,887 B, 2007-05-30) |
| **`hlg_backup__2011-01-11.tgz`** | 16,021,914 B | (2025-01-13) | **complete backup, 532 entries**, sha256 `ee929be6…` |

The tarball contains **`RCS/lojban.peg,v`** (477,267 B) — **39 revisions, 1.1 (2004-03-18
07:45:35) through 1.39 (2011-01-11 19:19:59), all author `rlpowell`, with log messages** — plus
`RCS/lojban_morphology_old.peg,v` (3 revs from 2004-11-21), `RCS/morph_header.peg,v` (2 revs from
2004-12-20), `RCS/index.html,v`, `RCS/test_sentences.txt,v`, `RCS/morph_test_sentences.txt,v`, an
`earley/` directory of 2004 Perl Earley-parser experiments, `old/abnf2bison.pl`, a copy of
`grammar.300`, and `jbokaj/` (a 2004 E-language IRC bot wrapping an earlier
`lojban_peg_parser.jar` of 392,835 B). **So camxes is a git-recoverable project, not a file-only
one**: `rcs-fast-export` over `RCS/*,v` yields 39+ dated commits.

The public git copy is **`github.com/lojban/camxes`** (created 2011-01-11, default `master`, **3
commits**, no licence, 10★): `first commit, imported` (2011-01-11), `Removing old commented bits`
(2011-01-13, tree = `README` + `lojban.peg` 49,650 B), and `Time has moved on.` (2025-01-13, which
deletes the grammar and leaves only the pointer README). So the grammar is present only at the
middle commit.

Identity checks (verified by hashing/diffing):
* `mw.lojban.org/images/3/38/lojban_peg_parser.zip` (819,413 B, uploaded by Gleki 2013-09-28,
  wiki description "camxes for offline use") contains one `.bat` and `lojban_peg_parser.jar`,
  sha256 `3373a835…` — **byte-identical** to `teddyb.org/…/rats/lojban_peg_parser.jar`. Its
  entries are `xtc/parser/lojban*.class` + `gnu.getopt`: compiled Rats! output, **no source**.
* `ilmentufa/camxes-pamoi.peg` (1,441 lines) is `RCS lojban.peg` **1.39**, differing only by a
  trailing blank line. "pamoi" = "first"; it is Robin's grammar preserved inside ilmentufa.

**Dating the project and the name** (verified). The work is datable from three independent
directions: the file mtimes on the project page (**2004-02-10**, the `bnf_conv.pl` conversion);
the RCS root revision (**2004-03-18**); and the earliest Wayback capture of the project page,
`web.archive.org/web/20040326041857/http://digitalkingdom.org/~rlpowell/hobbies/lojban/grammar/index.html`
(200, 16,747 B), which already reads "I am currently working on a PEG for Lojban. The initial
version… already parses most of Lojban!" — eight days after RCS 1.1.

The *name* is younger than the code. The earliest verified occurrence of "camxes" anywhere
reachable is **2005-04-11**, Adam Lopresto on lojban-beginners
(`mail.lojban.org/lists/lojban-beginners/msg16214.html`), followed by Robin's own first use on
2005-05-03 (`…/lojban-list/msg31690.html`, "The camxes parser and valfendi both have much better
morphology handling") and xorxes on 2005-05-04. All three are bare, unglossed uses, so the name was
already current; **no coining or announcement message survives** in any archive (a scan of ~35,000
messages across lojban-list, lojban-beginners, bpfk, `announce` and eight smaller lists found
none), and the BPFK Yahoo group (2004–2006) and post-April-2003 jboske are not mirrored at all.
2005-04-11 is therefore an **upper bound**, not the coining date; the name reaches Robin's own page
only between 2006-08-06 and 2006-09-11. *Inferred, not stated anywhere:* "camxes" is a portmanteau
of **camgusmis** (Robin) + **xorxes** (Jorge Llambías) — the wiki's "by camgusmis and xorxes"
attribution and the absence of the word from jbovlaste support it, but no source says so.

`camxes.lojban.org` is live (HTTP 200, 1,299 B) and is an ilmentufa front-end, not the Java parser
(inferred from size and from the wiki's own statement that camxes "has been superseded by Masato
Hagiwara's parser, and applied to la ilmentufa, la zantufa etc.").

The wiki page **`camxes`** (pageid 627) credits it to "camgusmis" (Robin Lee Powell) **and
xorxes** (Jorge Llambías) — the morphology half is xorxes', published as
**`BPFK Section: PEG Morphology Algorithm`** (17,456 B on the wiki, whose 2025-01-13 revision now
opens "**NOTE**: As of Jan 2025, the best place for a maintained Lojban PEG grammar is
https://github.com/lojban/ilmentufa").

### 2.3 The camxes.js / ilmentufa line (2013– )

| Name | Author | Lang | Formalism | Dialect | Repo | br | commits | first→last | tags | licence |
|---|---|---|---|---|---|---|---|---|---|---|
| **camxes.js** | Masato Hagiwara | JS | PEG.js port of camxes | camxes standard | `mhagiwara/camxes.js` | master | 11 | 2013-04-29 → 2014-10-06 | 0 | MIT |
| **ilmentufa (original)** | Ilmen (Ntsekees), lagleki | JS/PEG.js | PEG (`.peg` → `.pegjs` → generated `.js`) | standard + experimental | `Ntsekees/ilmentufa` | master | **444** | 2014-03-28 → 2015-12-10 | 0 | MIT |
| **ilmentufa (canonical)** | Ilmen + contributors, LLG org | PEG.js | same | standard / beta / beta-cbm / beta-cbm-ckt / exp / morphology | `lojban/ilmentufa` | master (+`gh-pages`) | **270** | 2016-02-02 → 2026-01-10 | 0 | MIT (`LICENSE`, "© 2014 lagleki, ilmen, and other contributors") |
| **gentufa** | mezohe | JS | fork of the *original* line | standard | `mezohe/gentufa` (branch `fanza`) | fanza | **533** | 2014-03-28 → 2021-01-13 | 0 | MIT |
| **camxes-py** | Riley Martinez-Lynch | Python | `parsimonious` PEG, grammar `parsers/camxes_ilmen.peg` | ilmentufa standard | `teleological/camxes-py` → `lojban/camxes-py` | master | 41 / **56** | 2014-05-19 → 2021-10-18 | 8 / 11 (`v0.1`…`v0.10.0`) | MIT (text in `LICENSE.txt`) |
| **python-camxes** | (LLG org) | Python | JVM bridge to the Java camxes | camxes standard | `lojban/python-camxes` | master | 52 | 2011-03-28 → 2014-10-18 | 2 | BSD-2-Clause |
| **johaus** | Ethan Burns | Go | generated parsers per dialect (`parser/{camxes,ilmentufa,maftufa,zantufa}`) | four dialects | `eaburns/johaus` | master | 6 | 2017-07-05 → 2019-10-27 | 0 | MIT |
| **visual-camxes** | dag | JS | front-end only | — | `dag/visual-camxes` → `lojban/visual-camxes` | master | 19 / 41 | 2011-04-02 → 2021-10-18 | 0 | none / MIT |

**Critical history fact (verified).** `lojban/ilmentufa` is *not* a git fork: `fork: false`, root
commit 2016-02-02. `Ntsekees/ilmentufa` has 444 commits ending 2015-12-10. The two histories are
**disjoint**, so preserving ilmentufa's full record needs **both** repositories. The wiki records
the reason obliquely, in `zantufa/en`: "The source of Ilmentufa was changed … to what cannot be put
under the power of the dictator", with Gleki's counter-explanation, both citing 2015-era mailing
list threads. `guskant/ilmentufa` (2015-06-04, 419 commits) forks the *original*;
`guskant/ilmentufa-1`, `maltesl/ilmentufa`, `int19h/ilmentufa` and a dozen others fork the new one.

Grammars in `lojban/ilmentufa` (verified in the local mirror): `camxes.peg` (1,782 lines, header
"camxes.js.peg / Copyright (c) 2013, 2014 Masato Hagiwara"), `camxes-beta.peg` (1,908),
`camxes-beta-cbm.peg` and `camxes-beta-cbm-ckt.peg` (generated from beta by `std-to-cbm.js` /
`make-ckt.js`), `camxes-exp.peg` (1,910), `camxes-morpho.pegjs` (792, morphology only),
`camxes-mh.js.peg` (Hagiwara's original), `camxes-pamoi.peg` (Robin's 1.39),
`selpatufa.peg` (1,985) and `selpahi-mex.peg` (1,994) — selpa'i's variants —
`camxes-20160209.peg` (a dated flattened snapshot), plus `camxes-std-changelog.txt` and
`camxes-exp-changelog.txt`. The wiki's `la ilmentufa` page: "A javascript parser (grammatical
analyser). Based on the work of Masato Hagiwara and la .uilym.. Developed by la ilmen."

### 2.4 zasni gerna (xorxes) and its implementations

`zasni gerna` ("temporary grammar") is **Jorge Llambías'** own unofficial PEG, published as wiki
text, not as a file: page **`zasni gerna`** (pageid 2535, rev 2015-01-21, 15,767 B) holds the whole
grammar in a `<pre>` block, with xorxes' own caveat "This is a version (not official) of the full
grammar of Lojban. I intend to make many changes to it"; the companion page
**`zasni gerna cenba vreji`** (5,257 B, rev 2014-07-31) is his change log (SA removed, `free*`
generalised, NAI extended, tags simplified, numbers/lerfu separated…). It is a *sibling* of camxes,
not a fork of camxes-beta.

| Implementation | Author | Lang | Formalism | Repo | commits | first→last | tags | licence |
|---|---|---|---|---|---|---|---|---|
| **zasni-gerna** (a.k.a. *iocixes*) | Yoshikuni Jujo (.iocikun.) | Haskell | his own `papillon` PEG generator | `YoshikuniJujo/zasni-gerna` | 76 | 2013-10-21 → 2019-10-27 | 8 (→`0.0.7.1`) | BSD-3-Clause |
| **lojbanParser** | same | Haskell | earlier parser | `YoshikuniJujo/lojban_parser` | 284 | 2012-06-09 → 2014-08-16 | 5 | none in repo; BSD-3 on Hackage |
| **lojysamban** (Prolog in Lojban) | same | Haskell | uses `lojbanParser` | `YoshikuniJujo/lojysamban` | 113 | 2012-09-12 → 2014-10-24 | 8 | BSD-3-Clause |
| **cakyrespa** (LOGO in Lojban) | same | Haskell | uses `lojbanParser` | `YoshikuniJujo/cakyrespa` | — | 2012-09-30 → 2012-10-29 | — | BSD-3-Clause |

The wiki lists the live demo as `skami2.iocikun.jp/lojban/zasniGerna` and already marks it "(dead
link)". Hackage carries `zasni-gerna-0.0.7.1`, `lojbanParser-0.1.9.2`, `cakyrespa-0.0.29`,
`lojysamban` — useful as dated release markers.

### 2.5 zantufa, maftufa, maltufa (guskant)

**There is no `zantufa` repository.** All of guskant's grammars live in one repo (verified):

| | |
|---|---|
| Repo | `github.com/guskant/gerna_cipra` |
| Default branch | `master` (also `gh-pages`, which serves `guskant.github.io/gerna_cipra/…`) |
| Commits | **167**, first 2015-06-04 ("Initial commit"), last **2019-08-20** (`zantufa1.3`) |
| Tags | **0** |
| Licence | **GPL-2.0** (`LICENSE`) |
| Contents | 260 files: **128 `zantufa-*.peg`**, 84 `maltufa-*`, 20 `maftufa-*`, `camxes_lonubrOdababrOde1.js.peg`, prebuilt `js/*.js`, `farvi*.sh` harnesses, `zei-si.txt` |

Versioning is *in the filename*, not in tags: `zantufa-0.1 … 0.18, 0.41, 0.61, 0.9999, 1, 1.1 …
1.17, 1.9999`, each with a `-cekitaujaubu / -cekitaujauzai / -cekitaujeibu / -cekitaujeizai /
-cekitaujoibu / -cekitaujoizai` variant matrix (the *ce ki tau jau* experiment) and both `.peg` and
`.js.peg` forms. `maltufa-*` targets older CgV-era texts; `maftufa-*` targets selpa'i's *lo se
mànci te màkfa pe la .oz.*. The wiki page `zantufa/en` (19,631 B) states the lineage explicitly:
"**Jbofi'e, Camxes and Camxes of Masato Hagiwara are ancestors of Zantufa. Ilmentufa camxes is
mother of Zantufa**", that "Most part of the temporary grammar suggested by Xorxes will be
adopted", that selma'o SA is removed, and that the numbering exists so `jo'au` can name a version.

Derived: `IGJoshua/sotygeha` (39 commits, 2019-08-29 → 2020-06-05, no licence) — a zantufa-derived
grammar with fewer selma'o. `MarkMcCaskey/zantufa` is a 2-commit throwaway.

### 2.6 Semantic parsers

| Name | Author | Lang | Formalism | Dialect | Home | commits | first→last | licence |
|---|---|---|---|---|---|---|---|---|
| **tersmu** | Martin Bays (mbays / zugz); LLG continuation | Haskell (+ a `rust/` port and a WASM build in the LLG repo) | **Pappy** packrat grammars `Lojban.pappy` + `Morphology.pappy` (camxes-derived), then a logic back-end | "CLL + xorlo, where possible" | **`gitlab.com/zugz/tersmu`** = upstream (branches `master`, `alis`, `selbriScope`, no tags); `github.com/lojban/tersmu` = same root commit **plus 49 commits in 2026** | 268 (GitLab) / **317** (GitHub) | **2011-08-17** ("Initial import") → 2023-12-20 / 2026-05-21 | **GPL-3.0** |
| **Nick Nicholas' analyser** | Nick Nicholas | NU-Prolog | see §2.1 | 2nd baseline | `lojban.org/files/software/analyser` | — | 1993-08-07 | LLG grant |
| **OpenCog Lojban parser** | Roman Treutlein | Haskell + C++ | subset grammar → AtomSpace | subset | `opencog/opencog/opencog/nlp/lojban/` (subdir of a monorepo); standalone at `rTreutlein/OpenCogLojbanSyntax` (8 commits, 2016) | — | 2016 | BSD-3-Clause |

GitLab has **no tags** on `zugz/tersmu`; Hackage has `tersmu-0.2`, `0.2.1`, `0.2.2` (last upload
2018-04-29), homepage `mbays.freeshell.org/tersmu` (live, HTTP 200). The wiki's `la tersmu` page:
"a semantic parser for lojban written in Haskell … translates the input to a predicate logic form
… Baseline lojban implemented, CLL+xorlo".

### 2.7 Ports, reimplementations and the modern generation

| Name | Author | Lang | Formalism | Dialect | Repo | commits | first→last | tags | licence |
|---|---|---|---|---|---|---|---|---|---|
| **jbogenturfa'i** | `.alyn.post.` (Alan Post) | Scheme (CHICKEN egg) | PEG on his own packrat engine `genturfahi`; files `gerna.peg`, `rafske.peg`, `rafske_gumgau.peg` | camxes standard | `alanpost/jbogenturfahi` | 154 | 2010-11-01 → 2013-01-04 | 0 | ISC (stated on the egg page) |
| **genturfahi** | same | Scheme | the generic packrat engine | — | `alanpost/genturfahi` | 269 | 2010-10-25 → 2012-10-19 | — | ISC |
| — LLG copy | — | — | — | — | `lojban/jbogenturfahi` | **4 (squashed, history lost)** | 2025-04-25 | 0 | none |
| **jbominji** | John Leuner | ? | PEG "combination of Robin's peg grammar and Xorxes' morphology" | camxes | `subvert-the-dominant-paradigm.net/~jbominji/code/lojban_grammar.peg` — **domain does not resolve** | — | — | — | — |
| **genturfahi (GUI)** | baban | C | front-end to the official parser | 3rd baseline | `baban/genturfahi` | 31 | 2015-11-21 → 2016-01-08 | 0 | none |
| **zirsam** | purpleposeidon | Python | hand-written | camxes-era | `purpleposeidon/zirsam` → `lojban/zirsam` | 145 | **2009-08-12** → 2011-04-14 | 0 | NOASSERTION |
| **sneturfahi** | Matt F. Bacon | Rust | hand-written | standard | `mattfbacon/sneturfahi` | 143 | 2022-08-11 → 2023-01-12 | 0 | AGPL-3.0 |
| **nei** | lynn | TypeScript | "a modern Lojban parser" | standard | `lynn/nei` | 55 | 2025-07-31 → 2025-09-06 | 0 | **none** |
| **jbotci** | Pavel Minaev (int19h) | Rust | hand-written, macro-generated recursive descent (`crates/jbotci-syntax/src/grammar/generated.rs`, 26.5 k lines of syntax crate) + separate morphology crate; dialect **feature flags** (`cbm`, `gadganzu`, `case-insensitive`, `zantufa-*` ×7) | CLL baseline with camxes-exp / zantufa dialects gated | `github.com/int19h/jbotci` (public; mirrors on Codeberg and GitLab) | **2,230** | 2026-05-15 → 2026-08-19 | 2 (`v0.1.0`) | MIT (`LICENSE.md`) |
| **lojban-ebnf** | Pavel Minaev | Rust | the **CLL chapter-21 EBNF** made executable, dynamic Earley parser with packed backpointers, unordered choice (deliberately no PEG first-match) | official CLL EBNF | **local only, no git remote** (`~/git/lojban-ebnf`, 235 commits, 2026-07-14 → 2026-08-03) | 235 | 2026-07-14 → 2026-08-03 | 0 | — |
| **camxes-rs** | — | Rust | **not a Lojban parser** — a generic PEG generator crate named after camxes | — | `lojban/camxes-rs` | 16 | 2024-10-25 → 2026-02-27 | 0 | none |

A long tail exists (verified by API but of marginal historical weight): `advancedresearch/lojban`
(Rust, 21 commits), `shouya/gernytci` (Rust, 57), `himikof/typed-lojban` (Haskell, 25),
`zhuangzi/genrei` (Haskell, 32), `matko/lojban-prolog-things` (Prolog, 4),
`skytomo221/CSharp-Lojban-Project` (128), `Xe/xultybau` (Go, 15), `cigix/la-lojPy`,
`hkmatsumoto/lojban` (OCaml, 2), `Beyley/LojbanParser` (Zig, 1), `clinei/gtf` (D, 4),
`lojban/lllp` (Lua, 2, Unlicense), `xymostech/lojban-parser` (C, 4),
`mlemon0037/lojban-interpreter` (Yacc, 6), `varikvalefor/lojban-fanva` (Agda, 849),
`youxkei/jbogensuhacta` (JS, 5), `La-Lojban/parser` (JS, 67), `skytomo221/genturcta` (a *comparison
viewer* over several parsers), `brismu/brismu` (Python, 312), `jqueiroz/lojban.io` (Haskell, 2,073
commits, 97★ — a study platform that embeds grammar handling), `n0la/lojban-parser` ("the old C
lojban parser with fixes", 9 commits, 2017 → 2026), `timo/lojbantools` (Python bindings to camxes
**and vlatai**, 14 commits, 2010), `timo/lojban-teachparse` (16), `zearen/munje-genturfahi`
(Haskell, 9), `purpleposeidon/cmacam` (7, 2010), `zearen/camxes-bot` (13, 2013),
`MarkMcCaskey/lo-vegadri` (Haskell, 12), `BamBalaam/lojban-toolkit` (55, GPL-3.0),
`alxndr/jbolaltci` (TS, 33, 2026), `DGCK81LNN/koishi-plugin-lojban` (18, MIT),
`La-Lojban/lojban` (TS, 97) and `lagleki/livla` (1,282 commits, 2014 → 2026, a site rather than a
grammar). `mbund/lojban-lsp` and `int19h/lojban-parser` are **empty repos** (0 commits).

Inside the `lojban` org itself the further grammar-adjacent repositories are `lllp` ("Lua LPeg
Lojban Parser", Unlicense, 2014), `mekso` (Perl, 2009, "Parrot-based Lojban math parser" — a MEX
sub-grammar), `lojban-teachparse` (Python, "a partial parser that gives step-by-step explanations
of parsings"), `jbobaf` (Haskell, 2010), `jboread` (C, 2009), `lojbot` (Haskell IRC bot),
`lojban-tools` (Ruby, 2008), plus `zirsam`, `jbogenturfahi`, `camxes`, `camxes-py`,
`python-camxes`, `visual-camxes`, `cll-parser`, `cll`, `cll-old` (an XSLT backup of the
pre-DocBook CLL repo), `lojban-cvs` and `lojban-cvs-attic`. The org holds ~90 repositories and is
the LLG's **only** source-hosting location (§3).

### 2.8 Morphology-only

`camxes-morpho.pegjs` (ilmentufa), `rafske.peg` (jbogenturfa'i), `Morphology.pappy` (tersmu),
`morph_header.peg` + `lojban_morphology_old.peg` (Robin's), `valfendi` (phma, C++, "implementation
of brkwords.txt … predates camxes"), `BRKWORDS.PAS`/`BRKWORDS.EXE`/`BRKWORDS.TXT` on
`lojban.org/files/software/` (52 K Pascal source, 2002-09-06), and jbofihe's `dfasyn` DFA. The
authoritative statement is the wiki's **`BPFK Section: PEG Morphology Algorithm`** (xorxes).
Lujvo/gismu tools (`jvozba`, `gimyzba`, `vlazba`, `latkerlo-jvotci`, `sozysozbot_jvozba`,
`jvoxaskei`, `p-lujvo` on Codeberg) are word-formation, not grammars — out of scope here, though
`jbotci` and `jbofihe` both bundle equivalents.

---

## 3. What the wiki lists that could not be found

* **`jbominji`** (John Leuner) — `subvert-the-dominant-paradigm.net` does not resolve; no Wayback
  capture of `~jbominji/code/lojban_grammar.peg` was located. The CHICKEN egg page also names a
  "jbonminji … Lojban parser for Common Lisp"; no repository found.
* **`iocixes`** demo at `skami2.iocikun.jp` — the wiki itself marks it dead. The code survives as
  `YoshikuniJujo/zasni-gerna`.
* **`lojban.org/tiki/…`** links throughout the older pages — the Tiki wiki is gone; content moved
  to `mw.lojban.org`.
* No repository named **`vlatai`** or **`vlacku`** exists; `vlatai` is a jbofihe binary.
* `home.ccil.org` (the host the wiki gives for Cowan's parser 3.0) does not resolve; `ccil.org`
  serves a zero-length body. Wayback has it.
* The wiki's `Lojban Formal Grammars` page knows nothing of the 1989–1993 grammar generations.
* **There is no `git.lojban.org`.** The name resolves to the lojban.org server, whose certificate
  is issued for `lojban.org` only; over HTTP it 301s to `https://www.lojban.org/mw-redir.html`.
  All LLG source hosting is the `github.com/lojban` organisation. The **GitLab `lojban/` group is
  a dead one-shot mirror**: 63 projects, every one created *and* last active on 2018-06-04/05.

---

## 4. Bringing them into the repository

### 4.1 Mechanism per implementation

| # | Implementation | Mechanism | Upstream / provenance source | Pin or dating strategy |
|---|---|---|---|---|
| 1 | Official YACC `grammar.300` + EBNF ch.21 | **already covered** by `cll/src` | `github.com/int19h/cll` | — (do not duplicate) |
| 2 | Official grammar generations E25/L23/506/28/BNF.28/techfix.28 | `vendor` | `https://lojban.org/files/history/<FILE>` | one commit per generation, date = the date in the file header (1989-02-25, 1989-09-23, 1990-05-06, 1990-07-20); undated `GRAMMAR.B17`/`GRAMMAR.NEW` at the 1990-07-20 boundary, flagged undated |
| 3 | 2nd-baseline `GRAMMAR.233`/`BNF.233`/`TECHFIX.233` | `vendor` | extracted from `https://www.lojban.org/files/software/parser/parser.shar.gz` | one commit, **1993-06-22** (the change-proposal date in the header); zip entry dates 1993-07-21 / 1993-08-26 and the 1993-10-19 shar wrap recorded in `provenance.csv` |
| 3b | 2nd-baseline BNF revisions `bnf.28` (1991 restamp), `bnf.235`, `techfix.235`, `bnf.246`, `bnf.247` | `vendor` (**Wayback**) | `https://web.archive.org/web/1999*/lojban.org/files/machine-grammars/<file>` (captures 1999-10-09 and 1999-11-04) | one commit each, dated **1991-06-23**, **1994-03-29**, **1996-03-20**, **1996-12-20** from the headers. `grammar.235`/`grammar.247` are 404 everywhere — record the gap |
| 4 | 3rd-baseline `bnf.300`/`techfix.300`/`xref.300`/`PD` | `vendor` | `https://lojban.org/publications/formal-grammars/` | one commit, **1997-01-10** (baseline date) |
| 5 | Official LLG parser (2nd baseline) source | `vendor` | `parser.shar.gz` (sha256 `72a4883f…`), `parser.zip` (`39648e2a…`), `PARSER3.ZIP` (`5a662531…`) | one commit **1993-10-19**; `PARSER.EXE`/`parser.exe` are binaries → provenance row only |
| 6 | Official LLG parser **3.0.00** | `sub` + one `vendor` commit | submodule `https://github.com/lojban/cll-parser` (1 commit, the full 3.0.00 tree); plus the release tarball `https://web.archive.org/web/20130116042930if_/http://ccil.org/~cowan/parser-3.0.00.tar.gz` (123,925 B, sha256 `a86a77d4…`) as a provenance row dated **2003-11-13** |
| 7 | **jbofihe** | `sub` | `https://github.com/lojban/jbofihe` | pin `master` @ latest; tags `0_2`…`v0.44` carry the release record |
| 8 | Nick Nicholas' NU-Prolog analyser | `vendor` | `https://lojban.org/files/software/analyser` (+ the two papers) | one commit **1993-08-07** (date in the file's first line) |
| 9 | **camxes** (Robin Lee Powell) | `vendor` **from RCS → replayed** | `hlg_backup__2011-01-11.tgz`, sha256 `ee929be6…` | run `rcs-fast-export` on `RCS/lojban.peg,v` etc. → **39 commits, 2004-03-18 … 2011-01-11**, real log messages; then the 2004 support files as one 2004-03-28 import |
| 10 | camxes git snapshot | `sub` (optional) | `https://github.com/lojban/camxes` | pin the **middle** commit `1c1d9ec` (2011-01-13) — HEAD deletes the grammar |
| 11 | camxes Java jar | **binary → provenance row only** | `teddyb.org/…/rats/lojban_peg_parser.jar`, sha256 `3373a835…` | 2006-08-21; note the wiki zip is the same bytes |
| 12 | **camxes.js** | `sub` | `https://github.com/mhagiwara/camxes.js` | pin `master` @ last commit 2014-10-06 (archived-in-place) |
| 13 | **ilmentufa (original)** | `sub` | `https://github.com/Ntsekees/ilmentufa` | pin `master` @ 2015-12-10 |
| 14 | **ilmentufa (canonical)** | `sub` | `https://github.com/lojban/ilmentufa` | pin `master`, bump on upstream commits |
| 15 | gentufa (longest original-line fork) | `sub` (optional) | `https://github.com/mezohe/gentufa` | pin branch `fanza` @ 2021-01-13 |
| 16 | **gerna_cipra** (zantufa/maftufa/maltufa) | `sub` | `https://github.com/guskant/gerna_cipra` | pin `master` @ 2019-08-20; also `gh-pages` if the rendered pages are wanted |
| 17 | **zasni gerna** (xorxes) | `vendor` | wiki pages `zasni gerna` + `zasni gerna cenba vreji` | already inside the wiki corpus — vendor only a extracted `.peg` under `grammars/`, dated **2015-01-21** (last wiki revision), cross-referenced to the wiki unit |
| 18 | zasni-gerna (Haskell) | `sub` | `https://github.com/YoshikuniJujo/zasni-gerna` | pin `master` @ 2019-10-27; 8 tags |
| 19 | lojbanParser / lojysamban / cakyrespa | `sub` (low priority) | `YoshikuniJujo/lojban_parser`, `…/lojysamban`, `…/cakyrespa` | pin at last commit |
| 20 | **tersmu** | `sub` | `https://gitlab.com/zugz/tersmu` (**upstream**) | pin `master` @ `fcd9038`; add `https://github.com/lojban/tersmu` as a second submodule for the 2026 continuation |
| 21 | **jbogenturfa'i** + `genturfahi` | `sub` | `https://github.com/alanpost/jbogenturfahi`, `…/genturfahi` | pin at 2013-01-04 / 2012-10-19. **Do not use `lojban/jbogenturfahi`** — squashed to 4 commits |
| 22 | **camxes-py** | `sub` | `https://github.com/lojban/camxes-py` (contains teleological's history plus 15 commits) | pin `master` @ 2021-10-18 |
| 23 | python-camxes, visual-camxes | `sub` (optional) | `lojban/python-camxes`, `lojban/visual-camxes` | pin at last commit |
| 24 | **johaus** | `sub` | `https://github.com/eaburns/johaus` | pin `master` @ 2019-10-27 |
| 25 | valfendi | `sub` (tiny) | `https://github.com/phma/valfendi` | pin @ 2014-09-23 |
| 26 | zirsam, sneturfahi, nei, sotygeha, typed-lojban, genrei, … | `sub` (long tail, judgment call) | see §2.7 | pin at last commit |
| 27 | **jbotci** | `sub` | `https://github.com/int19h/jbotci` | pin `main`; tag `v0.1.0` |
| 28 | **lojban-ebnf** | *blocked* | no remote exists | needs to be published before it can be a submodule; until then record it in `index.csv` with `mechanism=pending` |
| 29 | `lojban/camxes-rs` | `skip` | — | not a Lojban parser (generic PEG crate) |

### 4.2 Proposed layout under `grammars/`

```
grammars/
  _meta/
    index.csv                     name,author,language,formalism,dialect,years,mechanism,upstream,licence
    <name>/upstream.toml          submodules: url, default_branch, pinned_commit, pinned_at, first_commit_date, licence
    <name>/provenance.csv         vendored: url, sha256, bytes, server_date, capture_date, note
  official/                       vendored, one commit per generation
    1989-02-25/ 1989-09-23/ 1990-05-06/ 1990-07-20/ 1993-10-19/ 1997-01-10/
    parser/                       LLG parser 2nd baseline (1993) and 3.0.00 (2003)
    analyser/                     Nick Nicholas, 1993
  jbofihe/src                     submodule → lojban/jbofihe
  camxes/
    rcs/                          replayed from RCS: 39 commits 2004-03-18…2011-01-11
    support/                      lojban.bnf, lojban2.bnf, lojban.abnf, converters, earley/, test_sentences.txt
    git/                          submodule → lojban/camxes @ 1c1d9ec
  camxes-js/src                   submodule → mhagiwara/camxes.js
  ilmentufa/
    original/                     submodule → Ntsekees/ilmentufa
    src/                          submodule → lojban/ilmentufa
    gentufa/                      submodule → mezohe/gentufa      (optional)
  zantufa/src                     submodule → guskant/gerna_cipra
  zasni-gerna/
    xorxes/                       vendored wiki text as .peg
    haskell/                      submodule → YoshikuniJujo/zasni-gerna
  tersmu/
    src/                          submodule → gitlab.com/zugz/tersmu
    llg/                          submodule → lojban/tersmu
  jbogenturfahi/{src,engine}      submodules → alanpost/{jbogenturfahi,genturfahi}
  ports/{camxes-py,python-camxes,johaus,valfendi,zirsam,sneturfahi,nei,…}/src
  jbotci/src                      submodule → int19h/jbotci
```

### 4.3 Same code under different names — do not import twice

* `mw.lojban.org/…/lojban_peg_parser.zip` **=** `teddyb.org/…/rats/lojban_peg_parser.jar`
  (sha256 `3373a835…`, identical). One provenance row, no second copy.
* `ilmentufa/camxes-pamoi.peg` **=** Robin's `lojban.peg` rev 1.39. Ships inside the ilmentufa
  submodule; the camxes RCS replay is its history, not a duplicate file.
* `lojban/camxes@1c1d9ec:lojban.peg` **=** rev 1.39 minus commented-out lines.
* `lojban/cll:scripts/yacc/lojban_grammar.y` **=** `grammar.300`. Comes with the CLL submodule.
* Robin's `hlg_backup…/grammar.300` and `hlg_backup…/lojban.bnf` are **byte-identical** to the
  live `grammar.300` and `bnf.300` (verified by diff). Vendor the official files once, from
  `lojban.org`; the camxes copies are context, not separate artefacts.
* `lojban/cll-parser` **=** the contents of Cowan's `parser-3.0.00.tar.gz` (same `README`,
  `grammar.300`, `bnf.300`, `grammar.y`, `COPYING`). Take the repo; keep the tarball as a
  provenance row for the 2003 release date only.
* `lojban/lojban-cvs/jbofihe` and `La-Lojban/jbofihe` **=** the same CVS import as
  `lojban/jbofihe`; `lagleki/jbofihe` is the same plus an emscripten build.
* `teleological/camxes-py` ⊂ `lojban/camxes-py`; `lagleki/camxes-py`, `lagleki/camxes.js`,
  `lagleki/tersmu-0.2`, `La-Lojban/johaus`, `La-Lojban/jvozba` are stale copies.
* The **GitLab `lojban/` group** is a dead 2018-06 mirror of the GitHub org — never a source.
* `lojban/lojban-cvs-attic` is `lojban-cvs` re-run with `--retain-conflicting-attic-files`.

### 4.4 Needs Wayback or archive recovery

| Item | Status | Recovery |
|---|---|---|
| 2nd-baseline BNF revisions `bnf.235`, `bnf.246`, `bnf.247`, `techfix.235`, restamped `bnf.28` | removed from lojban.org | Wayback captures 1999-10-09 / 1999-11-04 of `lojban.org/files/machine-grammars/` |
| `grammar.235`, `grammar.247` (YACC forms of 2.35 / 2.47) | **never published** (404 in 2000-01-20 captures) | none — record the gap; `GRAMMAR.233` is the only 2nd-baseline YACC text |
| Cowan's `parser-3.0.00.tar.gz` | host dead | Wayback `20130116042930`, verified downloadable, sha256 recorded |
| jbofihe release tarballs / author's site | 404 | Wayback `rpcurnow.force9.co.uk/jbofihe/*` (0.38 tarball, zip, 2003 snapshot, patches) — **optional**, the git history supersedes them |
| `digitalkingdom.org/~rlpowell/…/grammar/` | moved | **live at `teddyb.org/~rlpowell/hobbies/lojban/grammar/`** — no Wayback needed today, but mirror it now; it is one person's home directory |
| `jbominji` PEG | domain gone | not recovered; try Wayback for `subvert-the-dominant-paradigm.net` |
| `skami2.iocikun.jp/lojban/zasniGerna` | dead | code survives on GitHub; only the demo is lost |
| `lojban.org/tiki/*` links | site retired | content in the wiki corpus |

### 4.5 Licences, for the README provenance paragraph

**GPL-2.0**: jbofihe, gerna_cipra (zantufa/maftufa/maltufa). **GPL-3.0**: tersmu,
`BamBalaam/lojban-toolkit`, `La-Lojban/vlazba`. **AGPL-3.0**: sneturfahi. **MIT**: ilmentufa (both
repos), camxes.js, camxes-py, johaus, jbotci, jboski, `lojban/visual-camxes`, gentufa.
**BSD-2-Clause**: `lojban/python-camxes`. **BSD-3-Clause**: zasni-gerna, lojysamban, cakyrespa,
OpenCogLojbanSyntax. **ISC**: jbogenturfa'i / genturfahi (stated on the CHICKEN egg page).
**Academic Free License 2.0**: Cowan's parser 3.0.00 (`COPYING` in the tarball).
**LLG permission grant** (verbatim in `parser.shar.gz`'s `license`): "COPYRIGHT 1989,1990,1991,1992,1993
THE LOGICAL LANGUAGE GROUP, INC. … PERMISSION TO COPY GRANTED SUBJECT TO YOUR VERIFICATION THAT
THIS IS THE LATEST VERSION … THAT YOUR DISTRIBUTION BE FOR PROMOTION OF LOJBAN, THAT THERE IS NO
CHARGE FOR THE PRODUCT, AND THAT THIS COPYRIGHT NOTICE IS INCLUDED INTACT". **Public domain**: the
3rd baseline itself ("THIS DOCUMENT IS EXPLICITLY DEDICATED TO THE PUBLIC DOMAIN BY ITS AUTHOR, THE
LOGICAL LANGUAGE GROUP INC."). **No licence at all**: `lojban/camxes`, `lynn/nei`,
`IGJoshua/sotygeha`, `matko/lojban-prolog-things`, `phma/valfendi`, and most of the long tail —
record the fact; do not assume a grant.

### 4.6 Ordering for the vendored (non-git) timeline

*(a27 / B17 / NEW, undated, 1988?)* · 1989-02-25 · 1989-09-23 · 1990-05-06 · **1990-07-20**
(1st baseline) · **1991-06-23** (2nd baseline) · **1993-06-22** (2.33) · 1993-08-07 (Nicholas'
analyser) · 1993-10-19 (LLG parser shar) · **1994-03-29** (2.35) · **1996-03-20** (2.46) ·
**1996-12-20** (2.47) · **1997-01-10** (3rd baseline) ·
1998-10-09 (`PARSER3.ZIP` DOS build) · 1999-06-12 (jbofihe CVS begins — git from here) ·
2004-02-10 → 2004-03-28 (camxes' BNF→ABNF→PEG conversion chain) · **2004-03-18** (camxes RCS 1.1;
project page captured 2004-03-26) · *2005-04-11 (name "camxes" first attested)* ·
2005-12-16/17 (Rats! toolchain) · 2006-08-21 (Java camxes jar) · 2003-11-13 (Cowan's parser 3.0.00,
out of sequence — it is the last of the official-parser line) · 2011-01-11 (camxes RCS 1.39, end of
the line) · then everything else is git-native.

Two dating cautions: the `Last-Modified` on every `lojban.org/files/` object is **2002-09-06** (a
bulk server migration) and on `/publications/formal-grammars/` is **2005-01-11** — neither is a
publication date, so date those commits from the text in the file, never from HTTP. And the
`teddyb.org` files that read **2025-01-13** were merely touched when Robin added the "historical
interest only" banner; their true dates are the RCS revision dates and the sibling files' 2004–2006
mtimes.
