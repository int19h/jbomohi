# 2026-08-27 — mail acquisition plan

**Source.** `doc/research/mail-sources-inventory.md` (every archive fetched and verified 2026-08-27).

**Findings adopted into `doc/SPEC.md` v0.5 §3.3.**

1. `mail.lojban.org/lists-plain/` serves raw RFC 822 Maildirs with per-list `.maildir.zip` bulk downloads for `lojban-list` and eleven other lists — the primary source; no scraping for those.
2. `lists/old_lojban-list/` (19,674 raw files) is the complete onelist/eGroups/Yahoo-era export; `lists/jbosnu_raw.zip` and `www.lojban.org/files/lojban-list/*.gz` (1989–1998 mbox) complete Tier 1.
3. Eight small lists exist only as MHonArc pages and are crawled by message number until 404 (indexes are incomplete); `lojban-beginners` needs the union of its Maildir and its MHonArc pages.
4. Google Groups (`lojban`, `lojban-beginners`, `bpfk-list`, `lojban-announcements`) is upstream of the 2011-09+ traffic and adds nothing; Lensisku's mail archive is an index over the same Maildir; Yahoo rescue material is redundant; `lojban-list-old` is a stale generation. None are scraped.
5. The Maildir contains up to five copies of the same message in the early years; dedupe on normalised Message-ID, keep the copy with the most headers, record the others' provenance.
6. `llg-board`, `llg-members`, `special*` are 401 → excluded; `jbovlaste-admin` (≈80k automated notifications) excluded by default.
7. Estimated unique human-authored messages across all public lists ≈ 118k.
