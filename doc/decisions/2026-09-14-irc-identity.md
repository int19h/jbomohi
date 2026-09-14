# 2026-09-14 — IRC commit identity

## Question

The initial specification was internally inconsistent: §2.5 and issue #5 used `irclogs <irclogs@irc.lojban.org>`, while §3.4 and the rendered instruction templates used `irc-logger <irclogs@lojban.org>`.

## Decision

Spec-lead decided on 2026-09-14 that IRC day-file commits use `irclogs <irclogs@irc.lojban.org>`; §3.4 and the instruction templates are corrected to match §2.5 and issue #5.

## Rationale

Section 2.5 is the normative identity table, and its source-namespace rule assigns IRC its own `irc.lojban.org` namespace just as wiki identities use `mw.lojban.org`; the distinct synthetic domain also avoids looking like a real mailbox at `lojban.org`.

## Consequences

`Identity.irc()` remains unchanged, IRC projectors use the canonical identity, and every rendered synthetic-address notice names `irclogs@irc.lojban.org`; the placeholder is not deliverable and does not identify a real person.
