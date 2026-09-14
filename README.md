# jbomo'i — the Lojban historical record as a git repository

<!-- Generated file; edit the template on the tools branch. -->

This repository republishes the Lojban community's public historical record as
plain text under git: the wiki with its full revision history, the earlier Tiki
wiki it replaced, the mailing lists, the IRC logs, the dictionary with its
definition history, every edition of *The Complete Lojban Language*, and the
formal grammars.

**Every commit is one source event** — a wiki revision, a mail message, a day
of IRC, a definition version — authored by the person who made it and dated to
when they made it. That is the whole idea. It means standard tools answer
questions about the language's history: `rg` finds the words, and `git log`,
`git blame` and `git show` find the when, the who, and what changed.

Snapshot `snapshot/20260914T131605Z`.

## What is where

- **`wiki/`** — MediaWiki pages as raw wikitext, UTF-8, one file per page, full revision history in git. `wiki/talk/` holds the Talk namespace.
- **`tiki/`** — The pre-2013 Tiki wiki in Tiki markup, UTF-8, with history. `tiki/forums/` holds WikiDiscuss threads and `tiki/talk/` page comments. Some text is stored mojibake and is published unrepaired.
- **`mail/`** — One Maildir per list under `<list>/cur/`, byte-exact RFC 822 as the archives hold it, so transfer encodings and original charsets are intact. `<list>/threads/<YYYY>/` holds decoded thread renderings, UTF-8, which are derived views and name their originals.
- **`irc/`** — One UTF-8 file per channel-day, `<channel>/<YYYY>/<date>.txt`, with a header line giving the timezone and line format.
- **`dict/`** — One directory per word: `word.toml` for the word and its etymology, `<lang>-<id>.md` per definition with its examples, `comments.md`. UTF-8, front matter in TOML.
- **`cll/`** — *The Complete Lojban Language* as plain UTF-8 text, one file per chapter per edition, under `cll/editions/<edition>/`, which need no submodule. `cll/src` is the DocBook source as a submodule; if it is empty, run `git submodule update --init`.
- **`grammars/`** — Formal grammars and parsers: the official YACC/BNF baselines, camxes and its lineage, ilmentufa, zantufa, zasni gerna and others. The vendored ones are ordinary files; the rest are submodules, so run `git submodule update --init` if a `src` directory is empty. `_meta/grammars/index.csv` says which is which and under what terms.
- **`who/`** — `attestations.csv`: dated, cited claims relating nicks, addresses and wiki users. Claims, never resolved identities. *Not yet in this snapshot.*
- **`notes/`** — Contributed research notes under `<YYYY>/`, UTF-8 Markdown with TOML front matter. Maps to evidence, never evidence. *Not yet in this snapshot.*
- **`loglan/`** — Loglan-era documents, where republication is permitted. *Not yet in this snapshot.*
- **`llg/`** — The Logical Language Group's own publications. *Not yet in this snapshot.*
- **`_meta/`** — Coverage files, archive manifests and CSV indexes. TOML and CSV with header rows, UTF-8.

## What this snapshot covers

| source | events | period | notes |
|---|---:|---|---|
| `cll/` | 11 | 2008–2026 | none recorded |
| `dict/` | 100,189 | 2003–2026 | none recorded |
| `grammars/` | 72 | 1989–2026 | 4 gaps recorded in `grammars/gaps.csv`, mostly "YACC form never published; BNF form survives" (2) and "referenced by surviving drafts but never published" (1) |
| `irc/` | 10,536 | 2000–2026 | 10 files the upstream listed but this archive does not hold |
| `mail/` | 112,300 | 1989–2025 | archives known incomplete: lojban-beginners, lojban-list; 9 unusable date headers |
| `tiki/` | 21,047 | 2001–2015 | 180 gaps recorded in `tiki/gaps.csv`, mostly "no current row; rename/deletion undocumented" (171) and "forum parent 4475 absent from export" (4) |
| `wiki/` | 59,474 | 2005–2026 | 21,224 gaps recorded in `wiki/gaps.csv`, mostly "move; history not API-accessible" (6,204) and "deleted; history not API-accessible" (3,410) |

Total: **303,629** source events.

This matters for reading answers as much as for finding them. "Nobody ever
proposed that" is only ever shorthand for "not in what this snapshot covers",
and the gaps files under `_meta/` record what was deliberately left out and
why.

## Start here

```sh
git clone --recurse-submodules https://github.com/int19h/jbomohi.git jbomohi
cd jbomohi

# what does the record say about a word?
rg -n "xorlo" wiki/ mail/ | head

# what happened across every source in one fortnight?
git log --since=2004-12-20 --until=2005-01-05 --format='%ad %an %s' --date=short

# how did one page get to be the way it is?
git log --follow -p -- "wiki/main/BPFK_Section%3A_gadri.wiki" | less

# what did this page say in 2015?
git show "$(git log -1 --format=%H --before=2015-06-01 -- wiki/main/xorlo.wiki)":wiki/main/xorlo.wiki
```

If `cll/src` or the `src` directories under `grammars/` are empty, you cloned
without `--recurse-submodules`; run `git submodule update --init --recursive`
inside the clone. The plain-text editions under `cll/editions/` and the
vendored grammars need no submodule, so most questions never require this — but
an empty directory reads like a missing source, which is why it is worth
checking first.

## Citing what you find

```
<path>@<Source-Id>:L<start>[-<end>]
```

The `Source-Id` names the version rather than a commit hash, so citations
survive a rebuild: `revid=<n>` for a wiki revision, the `Message-ID` for mail,
the date for an IRC day, `definition=<id> version=<n>` for a dictionary entry,
`cll=<edition>` for the book. The same ids appear in the commit trailers,
alongside `Source:`, `Event:`, `Time-Confidence:` and, where they apply,
`Event-Window:` and `Source-Date:` — so `git log --grep='Source-Id: revid=108932'`
goes from a citation back to the commit. `AGENTS.md` has the full grammar,
worked examples, and how to read each trailer.

Mail thread views and CLL edition text are renderings rather than originals;
line 1 of each names what it was rendered from. The originals are the Maildir
files and the `cll/src` submodule.

## Contributing

Research notes belong under `notes/<YYYY>/<date>-<slug>.md` and attestations
about identities in `who/attestations.csv`, as ordinary commits. Every claim in
them must cite primary units, because notes are maps to the evidence rather
than evidence themselves. `AGENTS.md` gives the citation grammar they must use.

Data files are never edited by hand: this snapshot is generated.

## Provenance and terms

Each source is republished under its own terms as published by its owner; this repository claims no licence of its own over the data.

Grammar and parser submodules keep their upstream licence files, and the
per-source terms are indexed in `_meta/grammars/index.csv`.

Names and email addresses appear as the public archives hold them. The
synthetic addresses used as git author placeholders — `…@mw.lojban.org`,
`…@jbovlaste.lojban.org`, `irclogs@irc.lojban.org` — are not deliverable.
Identities are recorded as dated, cited claims, never as resolved facts.

## Reading this with an assistant

Open the clone in a coding assistant and ask your question. `AGENTS.md` tells
it how the repository is arranged, how to search each kind of file, and how to
cite what it finds. Some harnesses read `AGENTS.md` on their own; others need
to be pointed at it.

Built by tools commit `2891f82ce593f0fa624167fc060ba05e4db9b777`; rebuilding or updating this snapshot
needs the tools and instructions on the `tools` branch of this repository.
