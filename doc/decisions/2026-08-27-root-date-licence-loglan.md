# 2026-08-27 — jbovlaste-admin, dump hand-off, provenance terms, root-commit date, Loglan

**Decisions (human partner, 2026-08-27).**

1. `jbovlaste-admin` (automated notifications) is excluded from `mail/`.
2. The operator-side export commands are handed to the server operator (Robin Lee Powell) — `doc/ops/dump-request.md`.
3. Provenance: each source is republished under its own terms, stated per directory in `main:README.md`; the repository claims no licence of its own.
4. The root commit is distinct from the earliest event and backdated to a round date earlier than anything that can appear. **Constraint found:** git (2.51) rejects any timestamp before 1970-01-01, including the raw `@-seconds` form, so the root commit is dated exactly `1970-01-01T00:00:00Z`; events with a true date before 1970 (pre-fork Loglan papers, 1955–69) are committed right after it in true-date order with the date clamped to the epoch, `Time-Confidence: pre-epoch`, and the true date in `Source-Date:`.
5. Loglan is part of the pile: pre-fork Loglan papers are Lojban history; an inventory with republication terms is in progress (`doc/research/loglan-sources.md`) and `doc/SPEC.md §3.9` is reserved for it (text where permitted, cite-only catalogue otherwise).
