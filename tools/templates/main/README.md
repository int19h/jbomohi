# jbomo'i — the Lojban historical record as a git repository

This repository republishes the Lojban community's public historical record as
plain text under git: the wiki with its full revision history, the mailing
lists, the IRC logs, the dictionary with its definition history, and every
edition of *The Complete Lojban Language*.

**Every commit is one source event** — a wiki revision, a mail message, a day
of IRC, a definition version — authored by the person who made it and dated
when they made it. That is the whole idea. It means the tools you already have
answer questions about the language's history: `grep` finds the words, and
`git log`, `git blame` and `git show` find the when, the who and the what
changed.

Snapshot `{{snapshot}}` · schema `{{schema}}`.
Built by tools commit `{{tools_commit}}`.

## Start here

```sh
git clone --recurse-submodules {{repo_url}} jbomohi
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

If `cll/src` or the `grammars/*/src` directories are empty, you cloned without
`--recurse-submodules`; run `git submodule update --init`. The rendered
editions under `cll/editions/` and the vendored grammars need no submodule, so
most questions never require this — but an empty directory reads like a missing
source, which is why it is worth checking first.

If you use a coding assistant, open the clone in it and ask your question:
`AGENTS.md` tells it how this repository is arranged and how to cite what it
finds.

## What is covered

{{coverage_tables}}

This matters for reading answers as much as for finding them. "Nobody ever
proposed that" is only ever shorthand for "not in what this snapshot covers",
and the gaps files under `_meta/` record what was deliberately not included and
why.

## What is where

{{layout_summary}}

## Citing what you find

```
<path>@<Source-Id>:L<start>[-<end>]
```

The `Source-Id` names the version rather than a commit hash, so citations
survive a rebuild: `revid=<n>` for a wiki revision, the `Message-ID` for mail,
the date for an IRC day, `definition=<id> version=<n>` for a dictionary entry,
`cll=<edition>` for the book. The same ids are in the commit trailers, so
`git log --grep='Source-Id: revid=108932'` goes from a citation back to the
commit. `AGENTS.md` has the full grammar and examples.

## Contributing

Research notes belong under `notes/<YYYY>/` and attestations about identities
in `who/attestations.csv`, as ordinary commits or pull requests. Every claim in
them must cite primary units, because notes are maps to the evidence rather
than evidence themselves.

The data files are not edited by hand. This repository is generated, and
rebuilding or updating it requires the tools and instructions on the `tools`
branch of this same repository; see `doc/SPEC.md` there.

## Provenance and terms

{{provenance}}

Grammar and parser submodules keep their upstream licence files, and the
per-source terms are indexed in `_meta/grammars/index.csv`. A missing licence
is recorded as missing and never treated as a grant. Vendored official
generations retain the LLG permission notice in their text, and the third
baseline carries its own public domain dedication.

Names and email addresses appear as the public archives hold them. The
synthetic addresses used as git author placeholders — `…@mw.lojban.org`,
`…@jbovlaste.lojban.org`, `irclogs@irc.lojban.org` — are not deliverable.
Rendered files, meaning the mail thread views and the CLL edition text, are
derived from the originals they name in their first line; the originals are the
Maildir files and the `cll/src` submodule. Identities are recorded as dated,
cited attestations, never as resolved facts.
