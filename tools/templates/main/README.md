# jbomo'i — the Lojban historical record as a git repository

<!-- Rendered by `jbomohi build|update` from tools/templates/main/README.md and _meta/. Do not edit on main; edit the template on the tools branch. -->

This repository republishes the Lojban community's public historical record —
the wiki with its full revision history, the mailing lists, the IRC logs, the
dictionary with its definition history, and every edition of *The Complete
Lojban Language* — as plain text under git, with **one commit per source
event** authored by the original author at the original time. It exists so
that anyone can research the language's history with `grep` and `git`, and so
that a coding agent pointed at a clone can act as a librarian: see
`AGENTS.md`.

Snapshot: `{{snapshot}}` · schema `{{schema}}` · built by tools commit `{{tools_commit}}`.

## Getting started

```sh
git clone --recurse-submodules {{repo_url}} jbomohi
cd jbomohi
rg -n "xorlo" wiki/main | head          # exact search
git log --since=2004-12-20 --until=2005-01-05 --format='%ad %an %s' --date=short   # what happened that fortnight
git log --follow -p -- "wiki/main/BPFK_Section%3A_gadri.wiki" | less              # a page's history
```

Open the clone in Claude Code, Codex, Gemini, Antigravity or another harness
that reads `AGENTS.md` and ask your question.

## Coverage

{{coverage_tables}}

Known gaps and quirks per source are listed under each table and in
`AGENTS.md`. Negative claims ("nobody ever proposed X") are only meaningful
relative to this coverage.

## Layout and citations

{{layout_summary}}

Citation grammar: `<path>@<Source-Id>:L<start>[-<end>]` — see `AGENTS.md`.
Commit trailers carry the same ids (`Source:`, `Source-Id:`, `Event:`,
`Time-Confidence:`), so `git log --grep='Source-Id: revid=108932'` finds the
commit for a specific wiki revision.

## Contributing

Research notes go under `notes/<YYYY>/`, alias attestations into
`who/attestations.csv`; both must cite primary units (front-matter and CSV
formats are documented in the `tools` branch, `doc/SPEC.md §3.7–3.8`). Data
files are never edited by hand: they are rebuilt from the sources by the tools
on the `tools` branch, which also holds the specification and the update
workflow.

## Provenance and terms

{{provenance}}

Email addresses and names appear as they do in the public archives.
Synthetic addresses used as git author placeholders (`…@mw.lojban.org`,
`…@jbovlaste.lojban.org`, `irclogs@lojban.org`) are not deliverable.
Rendered files (thread views, CLL edition text) are derived from the originals
they name in their first line; the originals are the Maildir files and the
`cll/src` submodule. Identities are recorded as dated, cited attestations, not
resolved.
