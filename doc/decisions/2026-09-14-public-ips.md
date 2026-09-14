# 2026-09-14 — IP addresses: published vs hidden

**Question.** Issue #3 found IP-shaped page titles (`User talk:173.13.139.235`), IPs in delete-log comments, and IP attributions for logged-out edits; spec §2.5/§6 said contributor IPs never enter the repository, which would force excluding public pages or rewriting archival content.

**Decision (spec-lead, applying the human partner's 2026-08-27 principle "public data, no redaction").** The prohibition covers only IPs the sites keep *hidden* (MediaWiki `rc_ip`, `ip_changes`, `cu_*`; Tiki `ip`/`user_ip` columns; request logs) — those columns are never exported or projected. IPs the sites *publish* — a logged-out editor's attribution in page histories, `User talk:<IP>` titles, log comments, wikitext — are public data and are kept exactly as published: files, indexes, subjects, and git author `<ip>@mw.lojban.org`. `anonymous@<host>` is reserved for revision-deleted (suppressed) usernames. Flagged to the human partner for veto.

**Consequences.** §2.5 identity table, §3.2 masking sentence, and §6 provenance statement amended; no page is excluded for being IP-titled; no content is rewritten.
