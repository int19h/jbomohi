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

Snapshot `pending`.

## What is where

See `AGENTS.md` for the corpus directory map.

## What this snapshot covers

No source events have been projected yet.

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

Built by tools commit `pending`; rebuilding or updating this snapshot
needs the tools and instructions on the `tools` branch of this repository.
