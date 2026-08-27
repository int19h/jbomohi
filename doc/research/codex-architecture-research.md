# jbomohi: architecture research and recommended first design

**Research cutoff:** 2026-06-30

**Local corpus inspection:** 2026-08-26

**Report written:** 2026-08-26

## Executive conclusion

By mid-2026, the common production primitives had moved beyond “split files into chunks, put the chunks in a vector database, and send the nearest few to an LLM.” Hybrid lexical+dense retrieval, deterministic filters, bounded reranking, source metadata, and inspectable traces recur across current systems. The fuller arrangement below combines that observed baseline with jbomohi-specific recommendations for historical research, disagreement coverage, and citation checking:

```text
immutable native sources and revisions
  -> source-specific normalization, identity, and provenance
  -> structured + lexical + dense indexes

question
  -> deterministic scope/date/authority filters
  -> fast lookup OR bounded research plan
  -> parallel source-specific retrieval
  -> fusion and direct reranking
  -> thread/revision/document-neighborhood expansion
  -> compact evidence ledger
  -> grounded synthesis with claim-local citations
  -> citation, contradiction, and coverage checks
  -> Discord synopsis + durable web report
```

Azure's [agentic retrieval overview, updated 12 June 2026](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview), is the clearest vendor description of the architectural direction: decompose difficult questions, execute lexical/vector/hybrid subqueries in parallel, rerank, merge, preserve references, and expose an activity log. At the cutoff, however, Azure's stable `2026-04-01` surface was the minimal/extractive subset; richer reasoning, multi-turn planning, synthesis, and retry behavior remained preview without an SLA ([migration boundary](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-migrate)). OpenAI File Search, Google Vertex ranking/grounding, Anthropic citation blocks, and current search platforms provide other subsets. None supplies the historical and normative model that jbomohi needs.

| Common mid-2026 production primitives | jbomohi-specific additions proposed here |
|---|---|
| Hybrid lexical+dense recall, metadata filters, reranking, source references, asynchronous jobs, tracing/evaluation | Native revision/thread/edition model, temporal and authority facets, exact stable spans, parser tools, view/era diversification, contradiction/supersession search, coverage-aware negative answers |

The recommended position is therefore:

> **Own the evidence model and corpus-specific retrieval; place embedding, reranking, and generation models behind versioned adapters and rebuildable indexes.**

jbomohi should begin as a modular monolith plus durable workers, with:

- immutable raw source objects;
- an append-only relational canonical store for resources, versions, spans, threads, alignments, provenance, assertions, roles, and decisions; PostgreSQL 18 is the leading reversible first hypothesis;
- exact/structured lookup plus fielded full-text search and character n-grams;
- a replaceable vector index; pgvector is the simplest initial experiment, while the evaluation decides whether a dedicated search engine is necessary;
- hybrid fusion, a direct reranker, and source-neighborhood expansion;
- a bounded librarian whose tools return typed evidence objects rather than shell output;
- a claim/evidence ledger and an independent citation/coverage pass;
- a Discord interaction adapter for short answers and a web application for the durable report, source viewer, revision comparison, and audit trail.

This design is more work than uploading documents to a hosted RAG product. Its central hypothesis is that it will be more efficient and reliable for the important query classes in this corpus: exact and structural queries can avoid embeddings and often avoid generation; historical questions can expand only the relevant thread or revision neighborhood; identical mirrors and unchanged revisions need be processed once; and the final model sees a small evidence pack rather than arbitrary chunks. The proposed evaluation must confirm those gains rather than presuming them.

The two most important things to do before choosing infrastructure are:

1. acquire and identify the missing historical sources, especially full wiki and dictionary history; and
2. construct a real, stratified Lojban retrieval-and-citation evaluation set.

An embedding bakeoff without that evaluation would mostly measure vendor reputation. No checked provider explicitly documents Lojban support.

## Scope and evidence policy

I treated “as of mid-2026” as a 30 June 2026 architecture cutoff. Product documentation is living documentation and was checked on 26 August 2026; dated release notes establish whether a feature existed by the cutoff. A small amount of July 2026 evaluation work is mentioned only as cutoff-adjacent confirmation, not as the basis for a June architecture claim.

The local inspection was read-only. Nothing was added to `/home/int19h.linux/git/jbomohi`. The checkout was effectively empty at inspection time, so there is no existing implementation to preserve or assess.

Several older sources remain relevant because they define stable primitives or because newer systems still depend on them: BM25, reciprocal-rank fusion, W3C PROV, Web Annotation selectors, and RFC mail threading are not obsolete merely because their specifications are older. By contrast, model rankings, managed product features, prices, and “best RAG stack” posts age quickly; this report relies on current official documentation and recent primary research for those claims.

## What is standard by mid-2026

There is no one standard product stack. There is a fairly stable **system shape**.

### 1. Source-aware ingestion and immutable evidence

A production research system keeps the native object and its identity before making retrieval chunks. It records where a passage came from, which version it belongs to, how it was decoded or rendered, and which pipeline produced every derived representation. A vector chunk is an index artifact, not a citation target.

This is a natural application of [W3C PROV-O](https://www.w3.org/TR/prov-o/)—entities, activities, agents, revisions, quotations, primary sources, and derivations—and the [W3C Web Annotation model](https://www.w3.org/TR/annotation-model/)—versioned targets, text positions, and exact quotes with prefix/suffix anchors. The standards are old, but their identity model is still a better foundation than model-generated URLs or mutable line numbers.

### 2. Hybrid candidate generation

Lexical and dense retrieval are complementary. Current Azure search runs BM25 and vector queries in parallel and combines them using reciprocal-rank fusion before semantic reranking ([hybrid scoring documentation, updated 8 June 2026](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)). Elastic likewise recommends hybrid retrieval and RRF as its default combination ([Elastic hybrid search](https://www.elastic.co/docs/solutions/search/hybrid-search)).

The research evidence is consistent but more cautious. [BEIR](https://openreview.net/pdf?id=wCu6T5xFjeJ) found BM25 a robust zero-shot baseline and found no universal dense winner out of domain. [BRIGHT](https://openreview.net/pdf?id=ykuc5q381b) showed that systems strong on ordinary retrieval can collapse on reasoning-intensive searches. RRF is a good label-free starting point, not a theorem: a [fusion analysis](https://arxiv.org/abs/2210.11934) found that calibrated score fusion can beat it with a small amount of target-domain data.

For Lojban, retaining lexical retrieval is especially important. Apostrophes, rafsi, cmavo sequences, quoted examples, grammar productions, personal names, dates, issue numbers, and exact historical wording frequently carry the answer. A dense model can bridge an English paraphrase to semantically related material; it must not erase literal evidence.

### 3. Broad recall, then bounded reranking

The common ranking pattern is inexpensive candidate generation followed by a more expensive direct relevance model on tens or perhaps a low hundreds of candidates. The reranker cannot recover evidence that the first stage missed. Azure's semantic ranker, for example, reranks the top 50 candidates ([semantic ranker overview](https://learn.microsoft.com/en-us/AZURE/search/semantic-search-overview)); Google's [Vertex Ranking API](https://cloud.google.com/blog/products/ai-machine-learning/launching-our-new-state-of-the-art-vertex-ai-ranking-api) is similarly positioned as a precision stage after retrieval.

Current research also gives a useful negative result: [Rethinking Reasoning in Document Ranking, ICLR 2026](https://arxiv.org/abs/2510.08985), found chain-of-thought rerankers less accurate and more expensive than direct rerankers on its BEIR and BRIGHT experiments. Let the librarian reason about *which searches to run*; use a calibrated specialist to score *whether a passage answers a query*.

### 4. Conditional query planning, not an agent loop for everything

A production design needs at least three routes:

- **lookup:** exact dictionary, section, quote, parse, date, or ID query;
- **ordinary:** one hybrid retrieval, rerank, context expansion, and synthesis pass;
- **research:** bounded decomposition, parallel searches, coverage assessment, and at most one or two follow-up rounds.

Azure's preview retrieval reasoning-effort design illustrates essentially these distinctions: a minimal path without LLM planning, a planned fan-out path, and a path with an additional sufficiency check ([reasoning-effort documentation](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort)). Beyond `minimal`, this was preview at the cutoff and is evidence of design direction, not a generally available production primitive.

Every research job should have ceilings for search calls, iterations, wall time, retrieved tokens, output tokens, and money. A coverage rule—not the model merely saying “I think I am done”—should determine whether another search round is justified.

### 5. Parent/child and neighborhood retrieval

The first useful hit often identifies the **object to read**, not the final quote. After finding one message, expand its mail thread; after finding one IRC line, inspect an episode around it; after finding a paragraph, inspect its section and corresponding edition; after finding a wiki claim, inspect the relevant revisions and talk page.

Vespa's current [chunk and layered-ranking design](https://docs.vespa.ai/en/rag/working-with-chunks.html) preserves parent documents and ranks their elements rather than treating every chunk as an unrelated document. That maps much better to jbomohi than generic fixed-size chunking.

Long context belongs here: as a reader over one bounded coherent unit. [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/), [RULER](https://openreview.net/pdf?id=kIoBbc76Sy), and [LaRA](https://proceedings.mlr.press/v267/li25dv.html) all argue against equating a nominally large context window with reliable whole-corpus reasoning. Retrieve the thread or chapter first; then read as much of that coherent object as is useful.

### 6. Evidence-aware generation and independent checks

Modern APIs can return structured citations, but citation formatting is not citation correctness. Anthropic's [citation API](https://platform.claude.com/docs/en/build-with-claude/citations) returns cited spans or caller-defined blocks; OpenAI's current [retrieval API](https://developers.openai.com/api/docs/guides/retrieval) exposes rewritten queries, filters, ranking settings, result chunks, and scores; Google's [Check Grounding API](https://docs.cloud.google.com/generative-ai-app-builder/docs/check-grounding) returns claim-level support and cited evidence.

jbomohi should nevertheless own the evidence ledger and renderer. The model chooses existing evidence IDs; application code turns those IDs into URLs and locators. After drafting, a separate pass should check:

- whether every externally checkable claim has evidence;
- whether each cited span actually supports, qualifies, or contradicts that claim;
- whether the version, date, and claimed authority are correct;
- whether later superseding evidence exists;
- whether a request for “known views” omitted a documented dissent.

[ALCE](https://aclanthology.org/2023.emnlp-main.398/) established that citation correctness and completeness are separate metrics. [OpenScholar, published in Nature in February 2026](https://www.nature.com/articles/s41586-025-10072-4/), is a useful contemporary design analogue: bi-encoder retrieval, cross-encoder reranking, citation-aware generation, and iterative verification. Its scholarly-paper corpus differs materially from Lojban history, so whether the pipeline transfers is a hypothesis to test.

### 7. Durable asynchronous delivery

Deep research is a job, not a request/response transaction. Discord requires an initial interaction response within three seconds and interaction tokens remain valid for fifteen minutes ([Discord interactions](https://docs.discord.com/developers/interactions/receiving-and-responding)). Discord messages are limited to 2,000 characters, with 6,000 aggregate characters across embeds ([message resource](https://docs.discord.com/developers/resources/message)).

The bot should defer immediately, enqueue an idempotent job, and later post a concise answer with a durable web link. The web application should own the complete report, evidence excerpts, revision comparison, source browsing, progress state, export, and correction history.

Prefer slash commands, mentions, or context-menu interactions at first. Broad ambient message reading needs Discord's privileged `MESSAGE_CONTENT` intent. The documented content exceptions are the app's own messages, DMs with the app, messages mentioning the app, and the target message of a message context-menu command; slash-command input arrives as interaction data rather than granting arbitrary message access ([message resource](https://docs.discord.com/developers/resources/message), [Gateway and intents](https://docs.discord.com/developers/events/gateway)). Honor dynamic rate-limit headers rather than hardcoding limits ([rate limits](https://docs.discord.com/developers/topics/rate-limits)).

## What the local corpus actually contains

The present local trees are valuable inputs, but they are not yet a canonical historical corpus. Counts below are point-in-time observations, not guarantees about upstream completeness.

| Source family | Local observation | What is useful now | Important gap or trap |
|---|---|---|---|
| Lojban wiki | `/home/int19h.linux/git/lojban-wiki`; 14,118 stored pages and 48,324,346 bytes of source text in the vendoring report | Stable current page/revision IDs, raw wikitext, Parsoid output, metadata | It is a **current-revision snapshot**, not wiki history. The report records 66 failures; its media manifest has 4,808 records but the binaries are absent. Historical answers require a separate full-history acquisition. |
| Mirrored wiki | `/home/int19h.linux/lojban/wiki` | Appears to be another available copy | A sampled tree digest matched the git checkout. Do not index it as independent evidence. |
| IRC | `raw/`: 7,853 files, 1,100,469 lines, 69,077,092 bytes; `all_logs.txt`: 1,151,468 lines, 73,173,505 bytes; plus a ZIP | Convenient exhaustive text scan and native file layout, with paths spanning 2000, partial 2002, and 2003–2026-08-16 | Raw and aggregate overlap heavily but are not exact concatenations. This local layout has no 2001 path; that is not evidence that no 2001 conversation occurred. Formats/timestamps vary, and historical messages usually lack native global IDs or explicit reply edges. |
| Mailing lists | `maildir`: 107,669 files and 77,116 unique normalized Message-IDs; `b2024/maildir`: 109,619 files and 77,943 IDs; plus 708 MHonArc pages and ZIPs | Raw RFC messages, Message-ID, References/In-Reply-To, complete headers; observed dates begin 1989-12-07 | The two maildirs overlap on 77,095 IDs and each has unique material; neither is a safe superset. Their observed maxima differ (2025-06-26 and 2024-07-23), and 86/1,172 files respectively lack Message-ID. The data includes addresses, transit headers, signatures, and quotations. |
| CLL | `/home/int19h.linux/git/jbotci/vendor/cll`, a 1,873-commit submodule at `v1.3.2`, with 25 current XML chapters, 4,763 unique `xml:id`s, rendered artifacts, git history, and release tags | Strong structural source for chapters, sections, examples, commits, and editions | `jbotci cukta` indexes only the checked-out XML. Git has a `geklojban-1.2.13` tag without a same-named local `official/` rendering, while `v1.3.2` is source/tag state rather than a demonstrated official manifestation. |
| Dictionary snapshot | `/home/int19h.linux/git/jbotci/crates/jbotci-dictionary-data/data`, about 9.5 MB; current JSON has 17,536 records, with `definition_id` and `word` each unique in this snapshot | Rich current entries with IDs, author/user fields, scores, glosses, and definitions | The Lensisku export was captured 2026-07-27. Git exposes only two substantive snapshots (May 17,415; July 17,536), a coarse diff rather than definition/vote history; long-term ID stability is not established. |
| jbotci derived tools | Parser, dictionary, embedding-input, embedding, search, and CLL tooling are present in the jbotci checkout | Reusable parsing and enrichment, plus useful comparative baselines | A parse is a versioned derived artifact, not evidence of meaning, usage, or ratification. Pin commit, feature flags, input span, and diagnostics. |

One current generated jbotci embedding manifest illustrates the stale-artifact problem: `.jbotci-build/web-embedding-corpus.current.json` dates from June and contains 17,415 dictionary inputs and 3,925 CLL chunks, predating the current dictionary and CLL checkout. Its model/input/corpus hash discipline is worth reusing; its sequential row IDs are not durable evidence identities, and the artifact must not be mistaken for current corpus coverage. `extracted-rafsi-en.json` is another useful but distinct artifact: an audited model-derived augmentation covering 55 gismu and 60 rafsi. Its provenance must not be merged invisibly into the Lensisku source.

The local wiki README says the snapshot was generated from `mw.lojban.org` by `cargo xtask vendor-wiki`, beginning 8 June 2026, and stores `source.wiki`, Parsoid HTML, and metadata under page-ID directories. That is excellent provenance for the captured present. It does not answer “what did this page say in 2005?” One captured failure is a talk page relevant to BPFK/gadri history, a reminder that an ingestion report must be treated as a coverage artifact rather than merely a build log.

The wiki copies under `/home/int19h.linux/git/lojban-wiki` and `/home/int19h.linux/lojban/wiki` had identical path-and-size manifests even though they are separate files, and sampled discussion files matched across the corresponding `lojban-disc` trees. Inside the IRC archive, the ZIP contains a byte-identical copy of `all_logs.txt`. Canonical ingestion should therefore identify native objects and content hashes before counting or embedding anything. “Present in two backups” is not “two sources agree.”

Mail deserves a separate public-surface policy. Search indexing may need decoded body text, addresses, and message topology internally, but a public web result should not casually expose every raw header or email address. Licensing, archive expectations, robots/access rules, deletion/correction requests, and the intended public/private boundary should be reviewed before launch. This report does not make a legal conclusion.

The 708 MHonArc tail pages are mostly a presentation mirror: 703 normalized IDs overlap the main Maildir. Five tail-only pages appear to be 2025 spam, but they still need classification rather than silent deletion. Older mail commonly lacks `List-ID`, so list membership cannot be inferred from that header alone.

## Sources still to acquire or classify

The requested historical product cannot be built solely from the present snapshots. The first corpus project should produce a source registry, acquisition method, license/access decision, native identity scheme, and coverage statement for at least:

- **Dictionary history:** the canonical jbovlaste/Lensisku data source, all available revision events, sense/definition identity, authorship, scores/status, and deletion/revert semantics. The official [jbovlaste help](https://jbovlaste.lojban.org/help/definitions.html) and [jbovlaste source repository](https://github.com/lojban/jbovlaste) are starting points, not proof that an export is historically complete.
- **Every CLL edition and manifestation:** DocBook sources, published HTML/PDF/e-book manifestations, errata, release tags, and a curated authority record. The Lojban wiki's [CLL page](https://mw.lojban.org/papri/CLL) identifies the 2016 v1.1 release and its editions; local newer branches/tags must be classified rather than silently promoted.
- **Authorized/public MediaWiki history:** all obtainable public page revisions, move history, talk pages, and enough rendering dependency information to avoid rendering an old page with present-day templates. Record deleted or oversight-suppressed gaps as coverage boundaries; do not attempt to reconstruct suppressed material. MediaWiki exposes revision IDs, parents, timestamps, actors, and hashes in its [revision schema](https://www.mediawiki.org/wiki/Manual%3ARevision_table/en) and [Revisions API](https://www.mediawiki.org/wiki/API%3ARevisions).
- **Mailing-list archive coverage:** list names, start/end dates, known outages, mirror overlaps, Message-ID collisions, duplicate MIME objects, and threading quality.
- **IRC coverage:** networks/channels, date ranges, log source, gaps, timestamp/timezone conventions, edits/redactions if any, and nickname/account identity confidence.
- **Formal and institutional record:** LLG bylaws and meeting minutes; BPFK decision/proposal records; official release notes and errata; historical grammar files; explicitly adopted policies. The official [Lojban file archive](https://www.lojban.org/static/files/index.html) and [formal grammar index](https://mw.lojban.org/papri/Lojban_Formal_Grammars) enumerate useful historical material.
- **Development record:** relevant git commits, issues, pull requests, design notes, and release artifacts for maintained tooling, with project status kept distinct from language authority.
- **Community sources:** forum and Discord material going forward only under an explicit consent, retention, and citation policy. A live chat should not quietly become a permanent public corpus.

Each acquisition needs a machine-readable coverage record: source, snapshot/retrieval time, known date range, expected and retrieved item counts, failures, exclusions, checksums, license/access status, and pipeline version. Negative answers must cite this coverage: “I found no explicit decision in the indexed BPFK and meeting records through date X” is defensible; “this was never ratified” usually is not.

## The canonical evidence model

The system needs richer identity than a generic document store, but it should not begin by extracting a universal knowledge graph from every sentence. A small source-first core can grow without forcing early ontological decisions.

### Minimum viable entities

| Entity | Purpose | Required identity/provenance |
|---|---|---|
| `Resource` | Enduring logical object or collection: wiki page, dictionary lexeme, CLL work/edition/section, mail thread, list, channel | Internal stable ID, source family, native ID where available |
| `Version` | One immutable state of a versionable resource: wiki revision, dictionary revision/snapshot state, CLL source revision/release | Native revision/commit ID, parent(s), source-asserted times, acquisition time |
| `SourceEvent` | Intrinsically event-like source item: mail message, IRC record, meeting act | Native or synthesized event ID, collection/thread membership, raw asserted timestamp and provenance |
| `Manifestation` | Bytes/text representing a `Version` or `SourceEvent`: DocBook, PDF, rendered HTML, wikitext, raw MIME, decoded body, mirror copy | Parent record, media type, object hash, acquisition record, transform provenance |
| `StructuralNode` | Chapter, section, paragraph, example, dictionary sense, heading, or message body block | Parent manifestation/resource, ordered position, structural path |
| `Span` | Exact citeable target in one immutable manifestation | Manifestation ID + selector; canonical-text offsets; exact quote and prefix/suffix; raw-byte mapping when possible |
| `Relation` | Native or deterministic topology: revision parent, reply, quote, wiki link, section alignment, adjacency | Relation kind, endpoints, source/derivation, confidence if inferred |
| `PipelineRun` | Reproducibility for decoding, parsing, chunking, embedding, alignment, extraction, generation, verification | Tool/model/version/config, input/output hashes, time, status |
| `CorpusSnapshot` | Frozen set of source/version manifests used for an index or answer | Manifest hash, coverage report, exclusions/failures, creation time |

`Span` and its immutable `Manifestation`, not `chunk`, form the citation contract. One possible identifier rule is:

```text
record_id        = version_id OR source_event_id
manifestation_id = hash(record_id, media_type, raw_sha256, transform_id?)
span_id          = hash(manifestation_id, selector)
chunk_id         = hash(index_profile, manifestation_id, retrieval_bounds)
```

Changing an embedding model or chunker then changes `chunk_id` without breaking old citations.

For text, a robust selector stores Unicode code-point offsets in a declared canonical representation, the exact selected string, a prefix and suffix, and—where possible—raw byte offsets plus a decoder/normalizer offset map. PDF manifestations can add page and bounding-box coordinates. A citation page can verify the hash and show the surrounding source even if the public upstream URL later changes.

Deduplication must not erase provenance. Two byte-identical mirrors can share one content object and one embedding, while retaining distinct acquisition and native-identity records. A quoted email can link to the original and be collapsed for ranking without deleting the fact that the quotation occurred. Generated CLL formats can be alternate manifestations without being counted as independent corroboration.

Here “immutable” means that retained source bytes and answer provenance are never silently rewritten. It is subordinate to rights and privacy policy. An authorized deletion or suppression can tombstone the identity and purge or cryptographically erase content, vectors, caches, traces, and affected answer excerpts; backups must honor the policy through expiry or key destruction. Old public citation/report URLs then render an authorized tombstone, not the deleted quote.

### Time is not one column

At least four time dimensions matter:

- `source_asserted_time`: the timestamp asserted by the source, stored with raw value, timestamp kind, issuer, timezone, normalization/derivation, interval, and confidence;
- `source_current_range`: an evidenced or derived interval during which a source version was current, with derivation/confidence;
- `effective_range`: when a decision, rule, role, or status applied in the modeled world;
- `system_range`, observation, and acquisition time: when jbomohi observed, knew, or stored it.

A message carrying a 2004 `Date` can announce a policy effective in 2005 and be ingested in 2026. Mail `Date`, IRC log time, MediaWiki time, git author/committer time, and publication time have different issuers and confidence. “What did the wiki display?”, “what did people say?”, “what was officially effective?”, and “what had the system indexed?” are different questions.

PostgreSQL 18 added `WITHOUT OVERLAPS` temporal keys and `PERIOD` foreign keys ([release](https://www.postgresql.org/about/news/postgresql-18-released-3142/), [CREATE TABLE documentation](https://www.postgresql.org/docs/18/sql-createtable.html)). Append-only PostgreSQL tables are a reasonable first implementation; they do not automatically supply bitemporal truth. [XTDB's time model](https://docs.xtdb.com/about/time-in-xtdb.html) is a useful conceptual reference and a possible later database choice if whole-database “as we knew it then” queries become central.

### Assertions, decisions, roles, and authority

Do not maintain one mutable “truth” or one scalar `authority_score` per topic. Official publication, formal ratification, proposal status, a dictionary vote, parser acceptance, actual usage, recency, and speaker expertise are orthogonal and can be disputed.

Add curated or conservatively extracted objects where they earn their cost:

- `Claim`: a proposition, not an accepted fact;
- `Assertion`: who expressed it, when, in which role, with which stance, at which exact span;
- `DecisionEvent`: proposed/adopted/rejected/withdrawn/superseded, deciding body, procedure, scope, effective period, and primary evidence;
- `RoleAssignment`: a person's evidenced role during a time range;
- `EvidenceLink`: supports, disputes, qualifies, mentions, or reports.

These need not cover every sentence in the MVP. Start with high-value governance questions and source-native events. LLM-extracted assertions should be versioned hypotheses that help retrieval, never a new source of ratification.

The answer policy should only say “ratified” after finding a qualifying act under an evidenced process. Frequency, repetition on the wiki, dictionary score, parser acceptance, or a prominent participant's opinion are not automatically qualifying acts. In some scopes an official publication can itself be the promulgation/adoption act; that must be established from the applicable source and procedure rather than inferred merely from inclusion. If no qualifying act is found, report the indexed sources and time coverage searched.

### Source-specific representations

#### Dictionary

Keep lexeme/form, sense, definition, example, and revision event distinct. Preserve author, vote/score, editorial status, timestamps, deletion/revert events, and relations such as rename, split, merge, and supersession where the source supports them. Identical definition text can share a content object; two revision events remain two events. A timestamp is not automatically an official effective date.

#### CLL

Model:

```text
Work -> Edition -> Manifestation -> StructuralNode -> Span
```

Corresponding sections across editions need many-to-many alignment edges: exact, edited, moved, split, merged, added, or deleted, with method and confidence. Do not overwrite several editions into one canonical paragraph. PDF extraction is derived; the citation should retain edition and page alongside extracted text and transform provenance.

#### Wiki

Keep articles, talk pages, policy/decision pages, redirects, and templates as distinct source kinds. Preserve raw wikitext. An old revision rendered using today's template or module is historically misleading; preserve the original rendering dependency set where feasible, otherwise label the result as reconstructed.

#### Mailing lists

Use `Message-ID` for native identity and `In-Reply-To`/`References` for topology as specified by [RFC 5322](https://www.rfc-editor.org/rfc/rfc5322.html). Preserve raw MIME separately from decoded/searchable text and record the decoder. Identify quoted blocks and signatures for ranking, but keep them in the citeable raw representation. A quoted copy is not independent evidence.

#### IRC

Modern IRCv3 has network-scoped [message IDs](https://ircv3.net/specs/extensions/message-ids) and [server timestamps](https://ircv3.net/specs/extensions/server-time); the historical logs often do not. Derive stable IDs from the archive object hash plus byte range or record ordinal. Nickname-to-person resolution, reply edges, and conversation episodes are probabilistic annotations, not source facts. Retrieve a hit, then expand a bounded time/message neighborhood; do not make arbitrary 512-token windows the sole structure.

#### jbotci

Record an analysis as:

```text
(source span, jbotci commit, parser mode, feature/dialect flags,
 result or failure, diagnostics, pipeline run)
```

Never use current parser acceptance to filter historical utterances out of retrieval. Dialects and parser behavior changed, and a parse result is not evidence of community interpretation or authority.

## Retrieval designed for the shape of the corpus

The recommended default pipeline is:

```text
structured/exact lookup
   + fielded BM25
   + character n-gram recall
   + dense retrieval
        -> rank fusion
        -> direct reranker
        -> source-neighborhood expansion
        -> evidence selection/diversification
```

### Indexed fields

Do not feed one normalized text field to every retriever. Preserve and search separate fields for:

- untouched raw/canonical text and exact phrase matching;
- normalized Lojban orthography, with normalization rules versioned;
- whole Lojban forms and lower-weight character 3–5 grams for variants and typos;
- parser-derived lemmas, rafsi/components, selma'o, and construction features where reliable;
- English prose, definitions, glosses, headings, and subjects with ordinary English analysis;
- author/speaker, native ID, date, source family, edition/revision, channel/list/thread, status, and authority facets;
- deterministic retrieval context: page title, section path, headword, thread subject, reply target, edition, and date.

Elasticsearch's current [multi-field model](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/multi-fields) is a clear example of indexing the same value in several analyzed forms. That capability matters more here than a fashionable vector-store brand.

For English questions seeking Lojban-only evidence, retain the original query and fuse additional branches rather than replacing it:

- dictionary/gloss expansion;
- jbotci-derived forms;
- a conservative English paraphrase;
- proposed Lojban lexical forms.

Query rewriting can improve conversational ellipsis and synonyms, but it can also discard the rare spelling or name that makes a historical result findable.

### Query routing

| Question shape | Primary route | Expansion/check |
|---|---|---|
| “What does *x* mean?” | Dictionary structured lookup + current/historical status | Definition history, corpus examples only if asked |
| Exact quote, rafsi, cmavo sequence, person, date, issue | Exact/fielded lexical search | Character n-grams and alias expansion; verify original source |
| “Where does CLL say…?” | Edition-constrained structural + lexical search | Section neighborhood and aligned editions |
| “What changed between these versions?” | Version alignment and deterministic diff | Retrieve commentary/decision evidence explaining the change |
| Vague recollection | Hybrid lexical+dense search | Rerank and read parent thread/page |
| “Why/how did this happen?” | Time/source decomposition + hybrid search | Traverse revision/thread/decision edges, then countersearch |
| “What views exist?” | Proposition/terms + source/time/participant diversification | Explicit dissent and supersession search; do not infer consensus from rank |
| Parse/construction examples | jbotci tool + parser-feature index | Pin parser versions; retain failures; cite the language sources/examples |
| Exhaustive count | Bounded deterministic scan over a frozen canonical representation | State exclusions, normalization, date, and dedup rules; no sampling claim |
| Whole-corpus themes | Optional hierarchical summaries or GraphRAG | Reopen original spans for every factual claim |

Hard filters—requested edition, date boundary, source access class, or a precise formal body—must be application-enforced before ranking where missing a match is costly. A semantic reranker should not be trusted to obey them implicitly. Azure's [vector filtering guidance](https://learn.microsoft.com/en-us/azure/search/vector-search-filters) calls prefiltering the recall-first mode and warns that postfiltering can introduce false negatives.

### Chunking and contextualization

Keep two strings:

- `evidence_text`: exact original citeable text;
- `search_text`: evidence plus deterministic retrieval-only context.

Use source-native evidence units first:

- one dictionary sense/revision or coherent field group;
- CLL paragraph/example with its section path;
- wiki section within one immutable revision;
- one mail message paragraph/block, with thread and subject metadata;
- one IRC message or short native block, later expanded to an episode;
- one formal decision item and its exact evidence.

Generated chunk context can be tested, but it is not evidence. Anthropic's 2024 [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) prepended short document-specific context before both embedding and BM25 and reported substantial vendor-run improvements. A 2025 study, however, found that “semantic chunking” did not yield consistent gains over simple approaches ([Qu et al.](https://aclanthology.org/2025.findings-naacl.114/)). The appropriate conclusion is to ablate contextualization on this corpus, not to install it everywhere.

Contextual embeddings are particularly plausible for immutable CLL editions. They are less obviously economical for high-churn wiki history: if each chunk vector depends on the rest of a page, a small edit can invalidate vectors for unchanged text. Dictionary records already have cheap deterministic context; mail and IRC are better handled with stable bounded windows plus post-hit neighborhood expansion.

### Graphs: useful topology, optional GraphRAG

“Use a graph” hides three different systems:

1. **Canonical topology:** revision parents, mail replies, CLL structure/alignment, dictionary history, wiki links, IRC adjacency. This is deterministic or explicitly confidence-scored and should be built.
2. **Claim/evidence graph:** assertions, stances, roles, decisions, support, contradiction, and supersession. Build selectively around high-value questions, with exact provenance.
3. **Statistical GraphRAG:** model-extracted entities/relations, community clustering, and generated summaries. Treat this as a disposable retrieval index.

Microsoft's original [GraphRAG paper](https://arxiv.org/abs/2404.16130) targets global questions over large corpora. Microsoft's [current repository](https://github.com/microsoft/graphrag) still labels the system a research project and warns that indexing is expensive. One [2025 comparative preprint](https://arxiv.org/abs/2502.11371), on its particular stack and corpus, found ordinary RAG stronger for specific/detail questions and graph methods helpful for multi-hop/global questions. That result makes query-class routing a worthwhile experiment; it does not establish a field-wide graph architecture.

PostgreSQL can represent the first two graphs as typed edge tables. A graph database and corpus-wide model extraction should be deferred until evaluation shows that relational traversal plus hybrid retrieval cannot answer a valuable query class.

## The librarian should be a constrained research program

The librarian is valuable because it can decide *which evidence operation is needed next*. It should not be a shell-enabled autonomous agent.

Candidate typed tools are:

```text
resolve_terms(names, aliases, dialect?, time?)
lookup_dictionary(form, as_of?, status?, include_history?)
compare_dictionary(form, from_version, to_version)
lookup_cll(query, editions?, section?, exact?)
compare_cll(anchor, editions)
search_passages(query, sources?, dates?, fields?, mode?)
search_conversations(query, lists_or_channels?, dates?, participants?)
expand_context(evidence_ids, before?, after?, thread?, revisions?)
parse_lojban(span_or_text, parser_version, feature_flags)
trace_decision(topic, body?, date_range?)
find_counterevidence(claim, scope)
scan_corpus(literal_or_safe_pattern, representation, snapshot, dedup_policy)
get_source(evidence_id, context_size)
```

Every result should be a typed, bounded object containing evidence IDs, exact excerpts, source/version/time, structural position, scores by retrieval channel, and coverage/failure notes. Tools enforce access classes, date bounds, result limits, and timeouts. Corpus scans default to literals; any regex mode uses a linear-time engine or tightly validated syntax plus CPU, input, match, and result ceilings. The planner never receives raw SQL, arbitrary filesystem paths, arbitrary URLs, shell access, ingestion privileges, or write tools.

Corpus text—including mail, wiki pages, source code, and quoted prompts—is untrusted data. It can contain accidental or deliberate instructions. NIST's March 2026 [agent security red-team summary](https://www.nist.gov/blogs/caisi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition) specifically covers hijacking through email, web, and code inputs; OpenAI's March 2026 [prompt-injection guidance](https://openai.com/index/designing-agents-to-resist-prompt-injection/) argues that impact must remain constrained even when classification fails. Source text must be delimited and labeled as evidence, never concatenated into privileged instructions.

Parsing and ingestion are a separate trust domain. MIME decoders, archive readers, wiki rendering, regex scans, and document converters need sandboxing and limits for decompression bombs, pathological regexes, malformed encodings, HTML/script content, filesystem traversal, and network fetches. The public viewer must escape source HTML.

### Bounded research behavior

A research plan should be explicit and inspectable, for example:

```text
question class: historical_status
required coverage: definition history, CLL editions, formal decisions,
                   discussion before/after decision
hard filters: through 2016-08-26
queries: [original, exact terms, aliases, English gloss]
budgets: <= 12 searches, <= 2 follow-up rounds, <= 90 s,
         <= N retrieved tokens, <= $X
stop: required source classes covered OR report precise gaps
```

The activity record should distinguish the model's plan from what actually ran. A failure to search one archive is part of the answer's coverage, not an invisible implementation detail.

## Embeddings are an architectural interface, not a decision here

Dense retrieval should be one replaceable channel behind a stable retrieval interface. It should never be the canonical evidence store or the only way to find material. No provider evidence checked for this report explicitly establishes Lojban retrieval quality, so choosing a model is a separate, corpus-specific evaluation task.

The architecture only needs to commit now to three invariants:

- every vector belongs to a versioned index generation recording its source snapshot, source-native chunk/context profile, provider/model, and creation pipeline;
- lexical/structured retrieval continues to work independently, including during provider outages or reindexing;
- index generations are independently versioned and can coexist when shadow evaluation, rollback, or zero-downtime migration requires it.

Reranking is likewise a replaceable precision stage after broad hybrid recall. Date, edition, authority scope, and access class remain application-enforced constraints rather than model judgments. Provider, dimension, fusion, reranker, and ANN details should be selected later from a frozen Lojban evaluation and the project's privacy/retention requirements.

## Recommended implementation boundary

The following is the cheapest reversible starting hypothesis, not a final infrastructure selection.

```text
                                      +----------------------+
Discord interactions ---------------->| API/session adapter  |<---- Web application
                                      +----------+-----------+
                                                 |
                                      defer / enqueue / stream
                                                 |
                                      +----------v-----------+
                                      | durable research jobs |
                                      +----------+-----------+
                                                 |
                       +-------------------------+--------------------------+
                       |                         |                          |
             +---------v---------+     +---------v---------+      +---------v---------+
             | planner/tool loop |     | evidence verifier |      | report renderer   |
             +---------+---------+     +---------+---------+      +-------------------+
                       |                         ^
              typed read-only tools             |
                       |                         |
       +---------------+-------------------------+----------------+
       |               |                |                         |
  structured/FTS   dense index      topology/versions       exact source spans
       +---------------+----------------+-------------------------+
                               |
                 append-only canonical evidence store
                               |
                   immutable raw object snapshots
```

### Initial components

- **Object storage:** content-addressed, write-once-while-authorized raw MIME, wikitext, XML, PDFs, rendered artifacts, manifests, and quarantined failures, with policy-compliant tombstone/erasure paths. Local development can use a filesystem; production can use an S3-compatible service.
- **Canonical database:** PostgreSQL append-only tables for source identity, versions, manifestations, events, spans, structural relations, acquisition runs, coverage, access class, and initially curated decisions/assertions. PostgreSQL is the evidence store, not automatically the complete retrieval engine.
- **Workers:** a durable queue for ingestion and research jobs, with idempotency keys, cancellation, leases, retries, quarantine, and bounded concurrency.
- **Retrieval layer:** typed application queries over structured lookup, FTS/n-grams, vector search, fusion, reranking, and neighborhood expansion. Keep its interface independent of the underlying engine.
- **Research service:** framework-light orchestration with explicit state and budgets. A fast-moving “agent framework” may help implementation, but its abstractions should not become the corpus schema or citation contract.
- **Report store:** append-only answer-revision metadata tied to corpus snapshot, pipeline versions, evidence ledger, plan/activity log, user-visible coverage, and correction/supersession state; stored query/content/excerpts remain subject to ACL, retention, redaction, and erasure.
- **Adapters:** Discord and web consume the same research API. Discord is a summary/notification surface, not the system of record.

[pgvector](https://github.com/pgvector/pgvector) supports exact search, HNSW/IVFFlat, and iterative scans for filtered ANN. PostgreSQL is appealing because the relational source model is central and it can host a simple vertical slice. Its built-in FTS ranks with `ts_rank`/`ts_rank_cd`, not BM25 ([PostgreSQL text-search controls](https://www.postgresql.org/docs/18/textsearch-controls.html)); `pg_trgm` ignores non-alphanumeric characters, which is unsafe as the sole Lojban n-gram channel because apostrophes matter ([pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)). The baseline therefore needs an application-controlled apostrophe-preserving tokenizer/n-gram index, a suitable extension, or a separate lexical engine. The benchmark should determine whether the unified Postgres experiment is sufficient or whether a source-aware platform such as Elastic or Vespa earns its operational cost. Vespa's layered parent/element ranking is conceptually attractive; Elastic's analyzers, multi-fields, filters, and inspectable hybrid pipelines are operationally mature.

OpenAI File Search is useful as a rapid generic control condition: its current hosted path combines semantic and keyword search with metadata filters and ranking configuration ([File Search](https://developers.openai.com/api/docs/guides/tools-file-search), [retrieval](https://developers.openai.com/api/docs/guides/retrieval)). It can participate in coarse attribute filtering, but it does not replace jbomohi's canonical version/span/topology/authorization model; returned file/chunk identity is insufficient as the sole durable citation contract.

### Ingestion and index operations

An ingestion source needs:

- resumable cursors and idempotent native IDs;
- immutable acquisition manifests and expected/retrieved/failure counts;
- authenticated acquisition-channel provenance, upstream native-ID/revision verification, and anomaly/rewrite detection;
- retry, quarantine, and manual inspection paths;
- explicit transform lineage and deterministic rebuilds;
- reconciliation against upstream rather than “last job was green”;
- freshness dashboards and visible stale/partial states;
- shadow index builds, validation, atomic promotion, and rollback;
- backups plus exercised restore tests;
- deletion/suppression propagation through raw/public tiers, indexes, embeddings, caches, logs, and backups according to policy.

Cache keys must include corpus snapshot, access/privacy tier, query and filters, retrieval/index version, parser version/flags, model and prompt version, and generation policy. Never share an answer or evidence-pack cache across access classes. Apply ACL, retention, redaction, and erasure to queries, plans, reports, job metadata, metrics labels, and correction history as well as source content; hashes and stable IDs can themselves be identifying.

## Rights, privacy, and provider handling are launch gates

“Publicly reachable archive” does not automatically settle permission to rehost, transform, publish enriched search results, or transmit the data to a model provider. Source-level review is required before cloud embedding or a public citation interface.

The registry for every source/version should record:

- copyright/license or other asserted terms and provenance of that determination;
- allowed internal processing, cloud processing, excerpt display, bulk export, and redistribution;
- privacy/access tier and redaction state;
- retention and suppression/deletion requirements;
- source-specific contact and correction process;
- provider/region restrictions.

The Lojban wiki's own [WikiPolicy](https://mw.lojban.org/papri/WikiPolicy) contains content and privacy qualifications, and older LLG material has document-specific terms such as the [LLG Web Copyright License](https://mw.lojban.org/papri/LLG_Web_Copyright_License). These need source-by-source interpretation; this report does not make a legal conclusion.

Use at least two representations:

- a restricted raw preservation tier, access logged and tightly scoped;
- a sanitized/searchable/public tier with address/header handling, suppressions, and safe excerpts.

Mail and chat deserve particular care because quotation can expose people who did not write to the indexed venue, and enriched search changes practical discoverability even where the source was technically public. Establish a correction, suppression, and deletion workflow before launch. Discord's developer terms and policy need to be reflected in an accurate privacy policy, retention limits, secure storage, and a user data deletion mechanism ([Discord Developer Terms](https://support-dev.discord.com/hc/articles/8562894815383-Discord-Developer-Terms-of-Service)).

For a cloud model, a request flag is not the whole retention story. Provider behavior can depend on account/project configuration, abuse-monitoring exceptions, region, and feature-specific conditions. Procurement should verify the actual configured service, contract/DPA, logging, training use, data location, deletion, and incident behavior—not rely on a product-family slogan.

## Citation and answer contract

The evidence ledger should exist before prose generation. A compact record could contain:

```json
{
  "evidence_id": "span:...",
  "resource": "mail-thread:...",
  "source_event": "message-id:...",
  "manifestation": "decoded-body-sha256:...",
  "source_kind": "mailing-list-message",
  "author_or_speaker": "...",
  "source_asserted_time": {"raw": "...", "normalized": "...", "confidence": "..."},
  "structural_path": "thread/message/paragraph",
  "quote": "exact source text",
  "relation_to_claim": "supports|contradicts|qualifies|mentions",
  "authority_facets": {"mode": "personal-analysis", "role_at_time": "..."},
  "retrieval": {"channels": ["bm25", "dense"], "scores": {}},
  "coverage_snapshot": "corpus-snapshot:..."
}
```

The writer receives these IDs and authorized excerpts. It may cite only supplied IDs. The renderer produces a stable jbomohi URL and, subject to the requesting principal's current ACL and any suppression/redaction, can show:

- exact quote and surrounding context;
- source kind, author/speaker, and source-asserted/normalized date with uncertainty where relevant;
- immutable event/version, native permalink, and hash;
- previous/next revision, adjacent messages, or full thread where separately authorized;
- the authorized public/sanitized manifestation, and raw or reconstructed manifestations only to entitled principals;
- extraction/rendering/parser provenance;
- whether the span supports, contradicts, qualifies, or merely provides background.

After drafting:

1. split externally checkable prose into reasonably atomic claims;
2. verify every selector resolves and quote matches the version hash;
3. classify the claim/evidence relation;
4. use an independent entailment/stance classifier as a fallible diagnostic;
5. search for contradiction and later supersession;
6. rewrite or remove unsupported claims;
7. check citation completeness after the final edit.

Citation integrity is not truth verification. A matching quote proves location; an entailment score is not adjudication. Keep link resolution, support/entailment, completeness, authority, temporal correctness, and counterevidence as separate statuses, and expose uncertainty.

For an unresolved issue, the answer shape should be explicit:

```text
A argued X at time T [source].
B disputed X on grounds Y [source].
C later qualified the scope [source].
The only explicit formal decision found in sources S through date D was Z [source].
No decision was found for the remaining question within that stated coverage.
```

Do not silently average these into “the community believes…”.

## Where source-shaped design can improve quality and token cost

These are the mechanisms to test, not guaranteed gains:

1. **Deterministic questions avoid model work.** A dictionary ID, exact CLL anchor, version diff, parser probe, message ID, or exhaustive count is answered by a typed operation and a small rendering pass.
2. **Metadata narrows before semantics.** Edition, date, source, list/channel, decision body, and access class filters reduce false candidates and embedding/reranker work.
3. **One canonical object avoids mirror amplification.** ZIPs, extracted Maildirs, Parsoid HTML, aggregate logs, quoted replies, and rendered CLL formats need not be embedded independently.
4. **Content hashes make history incremental.** Unchanged text can reuse lexical analysis and ordinary embeddings even when a revision event is new. The event remains distinct for provenance. A hash proves post-acquisition integrity, not upstream authenticity or authority; acquisition provenance and controlled promotion remain necessary.
5. **Native structure makes smaller chunks useful.** A paragraph with its section path or a message with its thread subject needs less generated context than an anonymous 800-token slice.
6. **Retrieve a hit, expand its neighborhood.** Embed individual messages or blocks; only place the relevant thread or conversation window into the reader context.
7. **Query modes allocate effort.** Lookup and ordinary questions do not pay for a deep-research planner; difficult history questions do.
8. **Fusion precedes expensive ranking.** Cheap exact/BM25/dense recall feeds a bounded reranker, and only a small evidence set reaches generation.
9. **Stable prompt prefixes can be cached.** Librarian policy, tool schemas, and source descriptions precede the dynamic question and evidence. Both Anthropic's [prompt-caching guidance](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) and OpenAI's [prompt-caching launch explanation](https://openai.com/index/api-prompt-caching/) depend on stable matching prefixes.
10. **Coverage and evidence are cached against snapshots.** Repeated research can reuse verified source neighborhoods without presenting a stale answer as current.

A useful product-level effort policy is:

| Mode | Typical behavior | Intended use |
|---|---|---|
| `lookup` | Structured/exact search, optional one lexical fallback, templated cited answer | Definitions, locations, parses, exact quotes, counts |
| `answer` | Hybrid search, one fusion/rerank pass, one neighborhood expansion, synthesis/check | Most ordinary questions |
| `research` | Query decomposition, parallel source routes, up to two coverage-guided rounds, countersearch | “Why?”, history, comparison, unresolved issues |
| `forensic` | User-selected wider budgets, exhaustive scan or larger historical scope, detailed audit | Rare high-value investigations; asynchronous only |

The UI should show the selected mode, corpus snapshot, important filters, and whether any required source failed. Users can then request a deeper pass instead of every query silently spending the maximum.

Do not assume the cheapest model should plan and the most expensive should write. That is a plausible configuration, not a law. Evaluate plan fidelity, retrieval recall, supported-answer quality, latency, and total spend for each role. A bad cheap rewrite can cost more downstream than it saves.

## Evaluation is the provider and complexity gate

Build the evaluation before selecting the embedding provider, dedicated search engine, GraphRAG system, or contextualization policy. Start with several hundred real questions, then grow it from usage. It must be stratified so easy dictionary lookup cannot hide failures on historical research.

### Query strata

1. exact word, rafsi, cmavo sequence, quote, name, and identifier lookup;
2. English paraphrase to English evidence;
3. English question to Lojban-only evidence;
4. Lojban question to English explanation/evidence;
5. parser construction and example search;
6. dictionary or wiki revision comparison;
7. CLL edition comparison and stable-anchor lookup;
8. mail thread reconstruction;
9. IRC episode reconstruction;
10. multi-hop “why/how did this happen?”;
11. unresolved issues requiring competing views;
12. ratification, authority, role-at-time, and status/date constraints;
13. typo, punctuation, and historical orthography variants;
14. genuinely unanswerable, underspecified, ambiguous, or non-standalone follow-ups;
15. exhaustive/counting questions with a known frozen-snapshot answer.

Seed the set with prior jbotci/smusni research because it represents genuine difficult work, but do not stop there: that is selection-biased. Add ordinary user questions, stratified random archive questions, rare-language phenomena, and adversarial counterexamples. Record annotator disagreement rather than forcing every historical controversy into one gold answer.

Hard negatives should include:

- correct words from the wrong CLL edition;
- an obsolete definition or proposal presented as current;
- a quoted reply instead of the original message;
- nearby but unrelated IRC chatter;
- the correct headword in the wrong historical interval;
- a parser result under the wrong dialect/version;
- a popular view that omits a documented dissent;
- a wiki summary that conflicts with the primary decision record;
- duplicate mirrors that look like independent agreement;
- a source passage containing prompt-injection-like instructions;
- a private/restricted span that relevance ranking would otherwise surface.

Pool candidates from every system and judge them blind to provider. Compare, in order:

1. structured lookup + exact search + fielded BM25/character n-grams;
2. each dense model alone;
3. lexical+dense RRF;
4. deterministic source context;
5. generated contextual embedding or late chunking where appropriate;
6. learned sparse retrieval;
7. late interaction;
8. direct reranking at several depths;
9. source-aware routing, neighborhood expansion, and diversification;
10. optional deterministic graph expansion and, separately, statistical GraphRAG.

Include a generic hosted-file RAG baseline and the simplest deterministic librarian. The custom system has not demonstrated value until it beats them on the query classes that matter.

### Metrics

Measure components separately:

| Layer | Metrics |
|---|---|
| Candidate retrieval | Recall@20/50/100, nDCG@10/20, MRR for single-hit tasks, relevant thread/version coverage |
| ANN | Recall relative to every evaluation query searched exactly against the full frozen corpus at equal filters; index build/update time and storage |
| Reranking | nDCG/recall after rerank, direct cost and p50/p95 latency, calibration by query class |
| Evidence selection | Minimal-evidence-set recall, duplicate amplification, source/version/time correctness, viewpoint/era diversity |
| Answer | Domain-reviewed correctness, answerability/abstention, temporal and authority accuracy, disagreement coverage |
| Citation | Locator resolution, quote match, entailment/precision, completeness/recall, granularity, supersession detection |
| Safety/privacy | Access-control escape rate, PII leakage, prompt-injection impact, unsafe renderer/parser cases |
| Operations | End-to-end p50/p95, search/model calls, retrieved/final tokens, dollars/job, cache hit rate, provider failure recovery |

Freeze corpus snapshots, qrels, prompts, model versions, and index configurations. Report per stratum and source family, not only a global average. Use inter-annotator agreement and adjudication notes for disputed relevance or authority.

[T2-RAGBench, EACL 2026](https://aclanthology.org/2026.eacl-long.8/), supports the need to measure retrieval and generation separately in a current complex-domain system. A cutoff-adjacent July 2026 multi-turn benchmark, [MTRAGEval](https://aclanthology.org/2026.semeval-1.447/), further emphasizes unanswerable, underspecified, non-standalone, and unclear turns and reports that retrieval errors compound downstream. These are external datasets, not substitutes for Lojban judgments.

## Observability without creating another sensitive archive

Trace enough to reproduce and diagnose a job:

- corpus snapshot and access tier;
- selected route and plan revision;
- subqueries, hard filters, and tool results by evidence ID;
- lexical/vector/fusion/rerank scores;
- context-expansion and evidence-selection decisions;
- generation and verification model/version;
- citations, coverage warnings, latency, tokens, cost, cache outcomes, and failures.

Default logs should contain IDs, counts, timing, token totals, and hashes—not entire prompts, mail excerpts, email addresses, or Discord identifiers. OpenTelemetry's GenAI work marks retrieval query text and related content as potentially sensitive ([GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)); those registry fields are developmental and some retrieval attributes have been deprecated or moved. Use OpenTelemetry transport and trace shape while retaining a stable jbomohi audit schema rather than copying unstable attribute names into the product contract. Make content capture opt-in, redacted, access-controlled, and separately retained.

## Discord and web product behavior

A Discord interaction should look approximately like this:

1. when using Discord's outgoing HTTP interactions endpoint, verify its Ed25519 signature (Gateway receipt is a separate, mutually exclusive mode);
2. create an idempotent job keyed by interaction ID and immediately defer;
3. acknowledge the chosen mode, scope, and any ambiguity that does not block useful work;
4. allow cancellation and suppress duplicate jobs;
5. post at most coarse progress events;
6. persist the answer independently of the fifteen-minute interaction token;
7. edit/respond with a short cited synopsis while the interaction channel remains usable; if it expires, require an explicitly configured, visibility-preserving notification path or let the user retrieve the job from the web app—never fall back from a private invocation to a public channel;
8. authorize the durable report from the intersection of invocation visibility, requesting principal, query sensitivity, and every evidence ACL; an unguessable URL is not authorization.

The web report is not merely a way around Discord's character limit. It is where a reader can inspect context, compare versions, switch among manifestations, see what sources were searched, report a bad citation, and distinguish a later corrected answer from its original revision.

Use per-user and per-guild quotas, bounded concurrency, cost attribution, expiration policies, provider timeouts/circuit breakers, and a degraded mode that can still perform deterministic/lexical search during model outages. Avoid `MESSAGE_CONTENT` unless a demonstrated feature requires it; commands, mentions, and explicit context actions are a clearer consent boundary. Discord announced stronger and annual review requirements for server/member/message-content access on 10 June 2026 ([Discord announcement](https://discord.com/blog/updated-requirements-to-how-apps-access-data-in-servers)); this should be treated as a product constraint, not a launch-time paperwork detail.

## Phased implementation plan

### Phase 0 — corpus, rights, and benchmark foundations

Deliver:

- source/acquisition/rights/privacy registry;
- canonical mirror and representation identity rules;
- immutable manifests and coverage reports for every current local collection;
- full-history acquisition plans for wiki and dictionary, plus at least one representative authorized/public revision-heavy slice acquired and measured before retrieval infrastructure is selected;
- verified CLL release/manifestation catalog and authority metadata;
- first 150–300 adjudicated queries across all major source/query classes;
- a public/restricted representation policy and suppression/deletion design.

Gate: no raw corpus goes to a cloud embedding/generation service and no public citation browser launches until its source class has passed the rights/privacy/provider review.

### Phase 1 — deterministic vertical slice

Choose a bounded slice containing at least:

- current dictionary plus its May/July coarse diff;
- two explicitly classified CLL versions;
- a wiki subset with talk pages and representative public revision chains;
- several complete mail threads and IRC periods from real prior research.

Implement `Resource` plus `Version`/`SourceEvent` -> `Manifestation` -> `Span`, manifests, structural/thread relations, exact lookup, fielded lexical search with apostrophe-preserving n-grams, source viewer, coverage reporting, and jbotci annotations pinned to version/flags. Build answers by templating or manually controlled evidence packs before adding a planner.

Gate: exact locators resolve reproducibly; mirror/quote/rendering duplicates do not inflate evidence; deterministic baseline metrics are published per stratum.

### Phase 2 — retrieval-channel evaluation

Add a small number of dense and reranking configurations behind the versioned retrieval interface and compare them with the deterministic/lexical baseline on the same frozen source-native units. Model selection is a separate work item; this phase only proves whether and where semantic retrieval and reranking add value.

Gate: adopt a hybrid configuration only from Lojban-specific quality, latency, cost, and privacy results. Treat choices as provisional until a representative amount of revision-heavy history is present; preserve parallel index generations when rollback or zero-downtime migration requires them.

### Phase 3 — evidence-first librarian

Add typed tools, three bounded effort routes, an evidence ledger, source-neighborhood expansion, claim-local citation rendering, contradiction/supersession search, and independent citation/coverage checks. Test with deliberately conflicting and unanswerable questions.

Gate: citation integrity, support, completeness, temporal correctness, authority handling, and viewpoint coverage meet explicit thresholds; no side-effectful tool is reachable from the answer loop.

### Phase 4 — Discord and web application

Ship the job API, queue, Discord interaction adapter, durable web report, progress/cancel flow, authentication/access classes, quotas, audit/correction UI, privacy controls, and operational dashboards. Begin with commands/mentions rather than ambient reading.

Gate: signature verification, idempotency, rate-limit behavior, deletion/suppression propagation, restore testing, model outage degradation, and prompt-injection/access-control tests all pass.

### Phase 5 — historical depth and optional graph methods

Complete wiki/dictionary history; add cross-edition alignments, curated decision/role/claim records for high-value topics, stance/time/source diversification, and historical query UI. Evaluate hierarchical summaries or GraphRAG only for whole-corpus or multi-hop strata where the simpler pipeline demonstrably fails.

Gate: every derived graph edge/summary remains traceable and disposable, and factual output still cites original immutable spans.

## Decisions to make now and decisions to defer

| Decide now | Defer until measured or governed |
|---|---|
| Native source/version/span identity precedes chunks | Embedding provider and dimension |
| Write-once-while-authorized raw evidence is separate from derived/public text | PostgreSQL/pgvector versus Elastic/Vespa/other production search engine |
| Exact/structured and lexical search are first-class | Fusion weights, ANN index, reranker and depth |
| Corpus text is untrusted; librarian tools are typed and read-only | Generated contextual embeddings and learned sparse retrieval |
| Claims cite immutable spans; coverage is visible | Corpus-wide claim extraction or GraphRAG |
| Authority is multidimensional and evidence-backed | Automatic stance/authority classifiers |
| Discord is an adapter; web reports are durable | Ambient Discord message access |
| Source-level rights/privacy/provider review is a launch gate | Which source classes may be publicly excerpted or cloud-processed |
| Evaluation is stratified and snapshot-pinned | Final model allocation among planning, ranking, writing, and checking |

## Principal risks and mitigations

| Risk | Consequence | Primary mitigation |
|---|---|---|
| Missing history masquerades as no history | False answers about development or ratification | Coverage manifests in every negative claim; acquire full wiki/dictionary history |
| Dense retrieval misses rare Lojban forms | Semantically plausible but historically wrong evidence | Mandatory exact/BM25/n-gram routes and local bakeoff |
| Mirrors/quotes amplify one claim | False consensus | Content/native identity graph, quote linkage, rank collapse |
| Present parser judges historical language | Archive evidence disappears or is mislabeled | Parser is optional, version/dialect pinned, failures retained |
| Model infers authority | Proposal or opinion becomes “official” | Curated decision events, role-at-time, primary-act citation, multidimensional facets |
| Citation resolves but does not support | Polished unsupported answer | Separate integrity, entailment, completeness, temporal, authority, and countersearch checks |
| Prompt injection in archives | Tool misuse or instruction corruption | Read-only allowlisted tools, data/instruction separation, budgets, sandboxed ingestion |
| Public search exposes personal data | Harm and policy/legal failure | Raw/public tiers, redaction/suppression workflow, source review, restricted logs/caches |
| Provider/model/index drift | Irreproducible answers and forced reindex | Versioned namespaces, immutable snapshots, shadow builds, parallel migration |
| Agent loop consumes unbounded time/tokens | Poor reliability and high cost | Explicit effort modes, ceilings, sufficiency/coverage stop rules, cancellation |
| Overengineered graph/schema delays useful search | Long project with little demonstrated value | MVP identities/topology first; add claims/graphs only against query-class gains |

## Recommended first commitment

Do **not** start by selecting a vector database or building the Discord bot. Start with one vertical evidence slice and a benchmark.

The first durable artifact should be a corpus/source registry plus the `Resource` / `Version` / `SourceEvent` -> `Manifestation` -> `Span` store, with policy-compliant tombstones. The first working interface should be a local research harness that can answer and cite a deliberately mixed set of dictionary, CLL-version, wiki/talk, mail-thread, and IRC-window questions using exact/lexical retrieval. Then add semantic retrieval, fusion, reranking, and planning as measured ablations.

If the hybrid system wins on vague and historical questions without regressing exact/version/authority questions, deploy that same typed research API behind Discord and the web app. This sequence tests the central hypothesis—that the data's shape can buy both quality and efficiency—before committing to the expensive parts.

## Selected references

### Current system and product architecture

- [Azure agentic retrieval overview, updated 2026-06-12](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview)
- [Azure hybrid RRF scoring, updated 2026-06-08](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)
- [Azure index design, updated 2026-06-05](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-index)
- [OpenAI File Search](https://developers.openai.com/api/docs/guides/tools-file-search) and [Retrieval](https://developers.openai.com/api/docs/guides/retrieval)
- [Anthropic citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Google Vertex Ranking API](https://cloud.google.com/blog/products/ai-machine-learning/launching-our-new-state-of-the-art-vertex-ai-ranking-api) and [Check Grounding](https://docs.cloud.google.com/generative-ai-app-builder/docs/check-grounding)
- [Vespa layered ranking](https://blog.vespa.ai/introducing-layered-ranking-for-rag-applications/) and [working with chunks](https://docs.vespa.ai/en/rag/working-with-chunks.html)
- [Elastic hybrid search](https://www.elastic.co/docs/solutions/search/hybrid-search)

### Retrieval, reasoning, and grounding research

- [BEIR, NeurIPS 2021](https://openreview.net/pdf?id=wCu6T5xFjeJ)
- [BRIGHT, ICLR 2025](https://openreview.net/pdf?id=ykuc5q381b)
- [Lost in the Middle, TACL 2024](https://aclanthology.org/2024.tacl-1.9/)
- [LaRA, ICML 2025](https://proceedings.mlr.press/v267/li25dv.html)
- [Rethinking Reasoning in Document Ranking, ICLR 2026](https://arxiv.org/abs/2510.08985)
- [OpenScholar, Nature 2026](https://www.nature.com/articles/s41586-025-10072-4/)
- [ALCE, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.398/)
- [Claimify, ACL 2025](https://aclanthology.org/2025.acl-long.348/)
- [DRUID, ACL 2025](https://aclanthology.org/2025.acl-long.968/)
- [GraphRAG](https://arxiv.org/abs/2404.16130) and [hybrid GraphRAG comparison](https://arxiv.org/abs/2502.11371)

### Provenance and source identity

- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [Memento / RFC 7089](https://www.rfc-editor.org/info/rfc7089)
- [Content-addressed naming / RFC 6920](https://www.rfc-editor.org/info/rfc6920/)
- [BagIt / RFC 8493](https://datatracker.ietf.org/doc/html/rfc8493)
- [RFC 5322 Internet Message Format](https://www.rfc-editor.org/rfc/rfc5322.html)
- [MediaWiki revision table](https://www.mediawiki.org/wiki/Manual%3ARevision_table/en) and [Revisions API](https://www.mediawiki.org/wiki/API%3ARevisions)

### Delivery, operations, and security

- [Discord interactions](https://docs.discord.com/developers/interactions/receiving-and-responding)
- [Discord Gateway/intents](https://docs.discord.com/developers/events/gateway)
- [Discord message resource](https://docs.discord.com/developers/resources/message)
- [Discord rate limits](https://docs.discord.com/developers/topics/rate-limits)
- [NIST agent security red-team summary, 2026](https://www.nist.gov/blogs/caisi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition)
- [OpenTelemetry GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)

## Local inspection limitations

- The inventory was read-only and bounded; it did not fetch missing upstream histories.
- The two wiki copies had identical path/size manifests; a full byte-level identity proof for both complete discussion trees was not completed.
- Mail Message-ID counts use normalization and reveal duplicates, but repeated IDs still need body/hash comparison before canonicalization.
- Current-revision timestamps in the wiki snapshot are not a historical coverage interval.
- Local CLL tags and rendered artifacts have not yet been adjudicated into a complete, authoritative publication catalog.
- Living API documentation, model offerings, and provider contracts can change; re-verify them at procurement and implementation time.
- This report proposes an architecture and experiment sequence. It does not claim that Postgres, a named embedding provider, a reranker, contextual embeddings, or GraphRAG has won the jbomohi evaluation.
