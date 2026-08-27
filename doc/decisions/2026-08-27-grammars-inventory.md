# 2026-08-27 — grammars and parsers

**Source.** `doc/research/grammars-inventory.md` (every repository and file re-queried 2026-08-27).

**Adopted into `doc/SPEC.md` v0.9 §3.10 and §3.1.6.**

1. A third import mechanism, **replayed history**, for sources that survive only in RCS/CVS files: camxes's `RCS/lojban.peg,v` (39 revisions, 2004-03-18 → 2011-01-11, with log messages) in Robin Lee Powell's `hlg_backup__2011-01-11.tgz` is replayed as real commits rather than vendored as a snapshot.
2. The official grammar lineage is vendored one commit per generation, dated from file headers (1st baseline 1990-07-20, 2nd 1991-06-23 with 2.33/2.35/2.46/2.47, 3rd 1997-01-10 — public domain); Wayback 1999 captures recover the removed 2nd-baseline BNF revisions; `grammar.235`/`.247` are recorded as never published.
3. Both ilmentufa histories (`Ntsekees/` and `lojban/`, disjoint) are submodules; `lojban/cll-parser`, `lojban/jbofihe`, `mhagiwara/camxes.js`, `guskant/gerna_cipra`, `YoshikuniJujo/zasni-gerna`, `zugz/tersmu` + `lojban/tersmu`, `alanpost/jbogenturfahi` + `genturfahi`, `lojban/camxes-py`, `eaburns/johaus`, `int19h/jbotci` are submodules; squashed or mirror copies are never sources.
4. Duplicates are imported once (`camxes-pamoi.peg` = `lojban.peg` 1.39; `lojban_grammar.y` = `grammar.300`; the jar = the wiki zip).
5. Licences recorded per implementation; "no licence" is recorded as such, never assumed.
6. Open: the long tail of small/unlicensed parsers; `lojban-ebnf` needs a remote before it can be pinned.
