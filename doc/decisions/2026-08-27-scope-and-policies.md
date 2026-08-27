# 2026-08-27 — scope of the first milestones and data policies

**Question.** `doc/SPEC.md` v0.1 §10 listed twelve open questions (service language, remote, privacy, hosting, CLL source, restricted lists, dictionary dumps, notes as evidence, Discord, hosting, embeddings, initial build).

**Decision (human partner, 2026-08-27).**

1. The first milestone is **the git repository by itself** plus the tools to create and update it plus the instructions to use it. No services, no bot, no web application, no authenticated surfaces — none in scope. Server-side hosting, Discord, indexes and embeddings are out of the picture for now.
2. `main` gets a root commit with the rendered `README.md` (from the `tools` branch template) and instruction files (`AGENTS.md`, `CLAUDE.md`, Gemini rules) so that an end user can clone and point a coding harness at it and start asking questions immediately; a `.gitignore` may be included.
3. **Public data, public repository.** Everything is public data repackaged as a public git repository on GitHub (if within its limits). No restricted lists unless the LLG publishes them. No email-address stripping or pseudonymisation.
4. **All raw emails go in the repository** (the Maildirs are the raw tier for mail).
5. **Notes must bottom out** in primary units; a note is never evidence.
6. **Identity resolution is out.** Alias information derived from public data is itself public and part of the repository, but identities are not *resolved*: resolution is unreliable and retroactive (A did X, B did Y, much later we learn A = B). The repository records dated, cited attestations instead.

**Consequences.**

- `doc/SPEC.md` rewritten as v0.2: §1 scope, §2.3 mail as raw tier, §2.7 GitHub sizing/pushing, §3.7 attestations replace the identity registry, §3.8 contributed content harvested across rebuilds, §5 instruction files as the librarian, §7 repository evaluation, §8 milestones M0–M2, §10 reduced to nine questions.
- v0.1 §5–§8 (indexes, service, interfaces, evaluation of a service) moved verbatim to `doc/future/librarian-service.md`.
- Templates for `main`'s instruction files added under `tools/templates/main/`.
- Closed without further action: v0.1 §10.1 (service language), §10.3 (privacy/access), §10.6 (restricted lists), §10.8 (notes as evidence), §10.9–10.11 (Discord, hosting, embeddings).
