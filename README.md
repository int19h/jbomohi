# jbomo'i

A research librarian for the Lojban community's historical record: it searches
the record iteratively and answers vague historical questions with verbatim,
verified citations. Discord first; web app and MCP server to follow.

This is the `tools` branch — the default checkout. It holds the tooling that
builds and maintains the corpus, the librarian service, the documentation, and
the model-session exchange. The corpus itself is the `main` branch (no shared
history), materialised as a git worktree at `./corpus/`.

- Start here: `AGENTS.md` (charter and working protocol), then `doc/SPEC.md`.
- Exchange between model sessions and the human partner: `tools/exchange/`.
- Research and evidence: `doc/research/`.
