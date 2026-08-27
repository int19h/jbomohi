# 2026-08-27 — consequences of the dump-schema research

**Source.** `doc/research/dump-schemas.md` (verified against the jbovlaste, Lensisku, MediaWiki 1.38 and Tiki sources and live APIs).

**Findings adopted into `doc/SPEC.md` v0.4.**

1. Lensisku's database *is* jbovlaste's, migrated in place: one dump, one user namespace (`@jbovlaste.lojban.org`), ids preserved. No `@lensisku.lojban.org` namespace.
2. jbovlaste kept **no definition history** (edits in place; `time` = last modified). Lensisku's `definition_versions` starts ~2024 and was not back-filled. The projection therefore emits one bounded-date initial state per definition and exact edits from 2024 on; coverage says so.
3. **Voter identity is not public** in either application; per-voter rows are treated as private and not exported. Scores are projected as aggregates; `votes.csv` is dropped.
4. Ongoing dictionary updates come from the public `/api/jbovlaste/changes` cursor feed; the version/history endpoints are token-gated.
5. jbovlaste's `example`, `etymology`, `comments` and its own versioned `pages` wiki are exact, attributed events and are projected (`## Examples`, `word.toml.etymology`, `comments.md`, `dict/_pages/`).
6. MediaWiki namespaces 202/203 (`User profile`) added; slugs are injective per namespace (mixed case-sensitivity); `rev_deleted` masking is enforced by the projector; contributor IP addresses never enter the repository (`anonymous@<host>`).
7. Tiki: `tiki_history` holds versions 1..N−1 and `tiki_pages` the current one; order by `lastModif`; the WikiDiscuss forum (≈5.6k posts) and per-page comments are projected; the mailing-list mirror forum is skipped as a duplicate of `mail/`; the dump needs latin1/hex-blob flags.
8. Private columns and tables per source are the list in `dump-schemas.md` §5.3; they are stripped by the operator before hand-over.
