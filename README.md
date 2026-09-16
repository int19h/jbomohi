# jbomo'i

The Lojban community's historical record — wiki with history, mailing lists,
IRC logs, dictionary with history, every CLL edition — repackaged as a public
git repository with one commit per source event, plus the tools that build it
and the instructions that let a coding harness act as a research librarian
over a clone.

This is the `tools` branch — the maintainers' checkout. It holds the tooling
that builds and maintains the corpus, the templates for the instruction files
that make a clone of `main` usable by a coding harness, the documentation, and
CI. End users clone `main`. The corpus itself is the `main` branch (no shared
history), materialised at `JBOMOHI_CORPUS` (default `~/lojban/corpus`) as a git
worktree.

- Start here: `AGENTS.md` (charter and working protocol), then `doc/SPEC.md`.
- Multi-session coordination: external Herdr Collab project `jbomohi`; see
  `AGENTS.md`.
- Research and evidence: `doc/research/`.
