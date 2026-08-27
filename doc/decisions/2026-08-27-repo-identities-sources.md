# 2026-08-27 — repository, commit identities, raw objects, CLL source, dumps

**Decisions (human partner, 2026-08-27).**

1. **Repository**: `https://github.com/int19h/jbomohi` (created blank). Both branches live there; `tools` is the default branch; `main` is the corpus.
2. **Commit identities on `main`**: author and committer are a dummy identity corresponding to the person who made the original edit or message, in **separate namespaces per source** — `mw.lojban.org:guskant` is not assumed to be `#lojban:guskant` or `jbovlaste.lojban.org:guskant`. Spec §2.5 gives the rendering table; relating identities is exclusively the job of `who/attestations.csv`.
3. **Public raw objects** (irclogs zip, MHonArc scrapes, API dumps) are published as GitHub Release assets per snapshot for reproducibility — never checked into the repository.
4. **CLL**: the submodule points at the fork `int19h/cll`.
5. **Dictionary dumps**: jbovlaste and Lensisku are open source; their schemas are determined from the code (`doc/research/dump-schemas.md`), so the loaders can be written before the dumps arrive.
6. **Wiki and Tiki**: SQL dumps are likely obtainable for the initial import (all hosted in one place). The Tiki is read-only, so it is a one-time import; the MediaWiki keeps changing, so its ongoing updates come from the API.
7. **Mail sources**: more lists are archived than exist locally, and Google Groups (e.g. BPFK) may be different views of the same emails — an inventory is required before §3.3's acquisition plan is final (`doc/research/mail-sources-inventory.md`).

**Consequences.** Spec bumped to v0.3: §2.3, §2.5, §3.2, §3.2.5, §3.5, §3.6, §10 amended; tool commits use `jbomohi <tools@jbomohi.invalid>`; the projector must produce identical wiki events from a SQL dump and from the API for the same range (determinism test at M1).
