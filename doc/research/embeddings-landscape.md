# Embeddings, Rerankers and Search Stores for a Lojban Research Assistant — Landscape as of August 2026

Prepared 2026-08-26. Scope: cloud embedding providers, rerankers, lexical/learned-sparse options, vector/search stores for a solo developer with ~1–5M chunks, cost model, and versioning practice. The corpus is mostly English discussion *about* Lojban with Lojban words/phrases quoted inline, plus some pure-Lojban text.

Legend: **[V]** = verified against a primary or vendor source fetched today (URL + date given); **[S]** = from a secondary/aggregator source, plausible but not vendor-confirmed; **[I]** = my inference or arithmetic. Prices are USD per 1M input tokens unless noted. Anything marked "preview" or with a 2024/2025 source date may be stale.

---

## 1. Cloud embedding models (mid-2026)

### 1.1 Comparison table

| Provider / model | Max input | Dims (default; options) | Quantized outputs | Price /1M tok | Batch | Multilingual claim | Contextual-chunk variant | Code / domain variants | Notes |
|---|---|---|---|---|---|---|---|---|---|
| **Voyage `voyage-4-large`** [V] | 32K | 1024; 256/512/2048 | float, int8, uint8, binary, ubinary | $0.12 | −33% | "best general-purpose & multilingual" | `voyage-context-4` ($0.12, 32K/chunk, 120K/doc with auto-chunk) | `voyage-code-4` $0.12; `-law-2`, `-finance-2` | MoE; all 4-series share one embedding space (mix query/doc models). First 200M tokens free. Released 2026-01-15. |
| Voyage `voyage-4` [V] | 32K | same | same | $0.06 | −33% | yes | (shared space) | | 8M TPM base tier |
| Voyage `voyage-4-lite` [V] | 32K | same | same | $0.02 | −33% | yes | | | 16M TPM base tier |
| Voyage `voyage-4-nano` [V] | 32K | 1024 | float | open weights | — | yes | | | Open-weight, same space as 4-series → local query embedding possible |
| **Google `gemini-embedding-2`** [V spec / S price] | 8,192 | 3072; 128–3072 (MRL, auto-normalised) | float only (MRL truncation) | $0.20 [S] | 50% off [V] | "100+ languages"; MMTEB 69.9 [V, arXiv 2605.27295] | none | none (task via prompt instruction) | Natively multimodal. GA 2026-05-20 [S]; `gemini-embedding-001` (2,048 ctx, $0.15) still available; spaces incompatible. |
| **OpenAI `text-embedding-3-large`** [S, stable since 2024] | 8,191 | 3072; MRL truncation | float only | $0.13 | 50% (24h) | yes (no explicit count) | none | none | `-3-small` $0.02. No successor announced as of Aug 2026; MMTEB 58.96 (low vs 2026 peers). |
| **Cohere `embed-v4.0`** [V] | 128K [S] | 1536; 256/512/1024 | float, int8, uint8, binary, ubinary | $0.12 [S] | — | "100+ languages" [V] | none | none | Multimodal (images $0.47/M image tokens). Bedrock/Azure availability. |
| **Jina `jina-embeddings-v5-text-small`** [V] | 32K | 1024; 32–1024 MRL | float | token packs (reseller ~$0.02–0.05) [S] | — | 32 trained / 93 supported; MMTEB 67.0 | late-chunking on older v3; not stated for v5 | `jina-code-embeddings` | 0.6B on Qwen3 backbone, CC-BY-NC weights (paid API for commercial). Rate limits: 500 RPM / 2M TPM paid. Released 2026-02-18. |
| **Mistral `mistral-embed`** [S] | 8,192 | 1024 | float | $0.10 | — | limited | none | `codestral-embed-2505` $0.15 (batch −50%) | Not competitive on MMTEB; skip. |
| **Amazon Titan Text Embeddings v2** [V] | 8K | 1024; 256/512 | float, binary | $0.02 | — | 100+ langs [S] | none | none | Cheap Bedrock default. `amazon.nova-2-multimodal-embeddings` $0.14/M, 8K ctx, multimodal [S]. |
| **NVIDIA** `llama-embed-nemotron-8b` / NeMo Retriever NIMs [S] | 32K [S] | 4096 | — | free dev API on build.nvidia.com; self-host NIM | — | MMTEB 69.46 | none | | Open weights; hosted only as NIM containers or catalog trial, not a production pay-per-token API. |
| **Qwen3-Embedding-8B** (open, Apache-2.0) [V] | 32K | 4096; user-defined ≤4096 | float | $0.01 via OpenRouter (DeepInfra/Nebius/SiliconFlow) [V]; Alibaba `text-embedding-v4` (64–2048 dims) [S] | — | 100+ languages; MMTEB 70.58 (#2 open) | none | | Best price/quality on paper; hosted-provider reliability varies. |

Sources: Voyage pricing/models/rate-limits docs (fetched 2026-08-26): https://docs.voyageai.com/docs/pricing , https://docs.voyageai.com/docs/embeddings , https://docs.voyageai.com/docs/contextualized-chunk-embeddings , https://docs.voyageai.com/docs/rate-limits ; Voyage 4 announcement https://blog.voyageai.com/2026/01/15/voyage-4/ (2026-01-15; 403 on fetch, summary via OpenRouter/EmbeddingCost); Gemini docs https://ai.google.dev/gemini-api/docs/embeddings (model updated Apr 2026) and https://embeddingcost.com/google (Jul 2026); Gemini Embedding 2 paper https://arxiv.org/abs/2605.27295 (2026-05-26); Cohere https://docs.cohere.com/docs/embeddings and https://embeddingcost.com/cohere (Jul 2026); Jina https://jina.ai/models/jina-embeddings-v5-text-small/ , https://arxiv.org/abs/2602.15547 ; OpenAI https://embeddingcost.com/openai (Aug 2026); Mistral https://mistral.ai/news/codestral-embed/ ; Titan https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-titan-text-embeddings-v2.html ; Nova MME https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-nova-multimodal-embeddings ; NVIDIA https://build.nvidia.com/nvidia/llama-3_2-nv-embedqa-1b-v2/modelcard ; Qwen3 https://openrouter.ai/qwen/qwen3-embedding-8b , https://arxiv.org/pdf/2506.05176 .

### 1.2 Standing on MTEB / MMTEB (multilingual, task-mean)

Snapshot from a leaderboard mirror dated 2026-05-17 (https://www.codesota.com/benchmarks/mteb) [S]: KaLM-Embedding-Gemma3-12B 72.32 (open) > Qwen3-Embedding-8B 70.58 (open) > Seed1.6-embedding 70.26 (API, ByteDance) > llama-embed-nemotron-8b 69.46 > Qwen3-Embedding-4B 69.45 > gemini-embedding-001 68.37 > … > text-embedding-3-large 58.96 > voyage-3.5 58.46. Gemini Embedding 2 reports 69.9 in its paper [V]. Voyage does not submit 4-series to MMTEB; Voyage's own claims (~100 in-house datasets) put voyage-4-large ahead of Gemini/OpenAI, and a third-party domain benchmark (legal/support/healthcare nDCG@3, updated 2026-08-17, https://aimultiple.com/embedding-models) [S] ranks voyage-3.5 0.943 ≈ voyage-4-large 0.942 > gemini-embedding-2 0.932 > voyage-4-lite 0.921 > qwen3-8b 0.890 > openai-3-large 0.810. Caveat: MMTEB rewards models trained on MMTEB-like data, and none of these numbers say anything about Lojban (§2).

### 1.3 Batch, rate limits, and "contextualized chunk" support

- **Voyage** [V]: batch −33% (free credits do not apply to batch). Base limits 2,000 RPM; TPM 3M (4-large / context-4), 8M (voyage-4), 16M (4-lite); ×2 at ≥$100 spent, ×3 at ≥$1,000. `voyage-context-4` is the only hosted "contextualized chunk" model: you send `List[List[str]]` (chunks grouped per document, or let the backend auto-chunk, default 512 tokens, up to 120K tokens per document) and each chunk vector encodes document-wide context *without* prepending text; billing is per chunk token, so there is no 2× token inflation. voyage-context-3's launch post (2025-07-23) claimed +14% over OpenAI-3-large and +6.8% over Anthropic-style contextual retrieval on chunk-level retrieval [S].
- **Gemini** [V]: Batch API at 50% price; batch enqueued-token caps 500K/5M/10M for tiers 1–3 — small, so a 250M-token corpus needs many batch jobs or synchronous calls. Live RPM/TPM only visible in AI Studio. No contextual-chunk mode.
- **OpenAI** [S]: batch 50% off, 24h window. No contextual mode.
- **Cohere** [S]: trial keys 100 calls/min; no batch discount published. No contextual mode.
- **Jina** [V]: paid 500 RPM / 2M TPM. Late chunking existed for v3; not advertised for v5.
- **Voyage ownership** [V]: MongoDB acquired Voyage AI in Feb 2025 ($220M); Voyage models are sold standalone and via MongoDB Atlas, Bedrock, Azure and Vertex Model Garden (2026-01-15). Anthropic is a customer and recommends Voyage in its docs; there is no Anthropic ownership. https://www.mongodb.com/press/mongodb-announces-acquisition-of-voyage-ai

---

## 2. Out-of-distribution languages: what is known

**Direct evidence about Lojban in embedding models: essentially none.** [V] The one explicit mention I could verify is negative: the LASER paper (Artetxe & Schwenk, TACL 2019, https://aclanthology.org/Q19-1038.pdf) built its Tatoeba evaluation on "93 languages after discarding several constructed languages with little practical use (Klingon, Kotava, Lojban, Toki Pona, and Volapük)". No MMTEB task covers Lojban; I found no MMTEB task list entry for Esperanto either, though Esperanto is in FLORES-200/NLLB-style data so multilingual E5/BGE-M3/Qwen3 have seen it [I]. Data scale for pretraining exposure [V, fetched today]: Tatoeba has 17,486 Lojban sentences vs 820,853 Esperanto, 78,713 Toki Pona, 44,312 Klingon; Lojban Wikipedia has 1,359 articles. Lojban is therefore "seen but tiny" for every LLM-backbone embedder (Qwen3, Gemini, Jina v5, voyage-4 MoE) and effectively unseen for BERT-era encoders.

**Code-switched text is a measured weakness.** [V] "Code-Switching Information Retrieval: Benchmarks, Analysis, and the Limits of Current Retrievers" (arXiv 2604.17632, 2026-04-19) evaluated e5, bge-m3, Arctic, Qwen3-Embedding, jina-reranker-v3, bge-reranker-v2-m3, Qwen3-Reranker, ColBERTv2 and BM25: even query-side switching costs 3–15 nDCG@10 points; on the 11-task CS-MTEB suite drops reach 27%, worst in reranking; multilingual models degrade less than English-centric ones but are not immune; lexicon-based vocabulary expansion helps only partially. Embedding-interpolation work (arXiv 2606.13537, Jun 2026) likewise reports inconsistent behaviour across monolingual vs mixed queries and that code-switched training data improves robustness. Our corpus (English sentences with embedded Lojban tokens) is exactly this regime, except the embedded language is one the model barely knows — expect the Lojban tokens to be fragmented into 2–5 subword pieces each and to contribute weak, noisy signal to the dense vector [I].

**Low-resource adaptation works.** [V] "Bootstrapping Embeddings for Low Resource Languages" (arXiv 2603.01732, 2026-03-17) shows synthetic triplets with cross-lingual LoRA (anchors in the target language, positives/negatives in English) lift STS from 66.8 to 72.3 on mmBERT for African/Asian low-resource languages. Domain fine-tuning with synthetic queries on a 1B NV-EmbedQA model gave +7 nDCG@1 (Cisco/NVIDIA recipe, 2025) [S].

### 2.1 Mitigations practitioners use in 2026, ranked for this corpus [I unless noted]

1. **Hybrid retrieval with exact-token BM25** — non-negotiable here. Lojban terms (`cmavo`, `gismu`, `lujvo`, `ko'a`, `la'o`) are near-unique tokens; BM25 matches them exactly regardless of the embedder's ignorance. Anthropic's Contextual Retrieval post (2024-09-19) [V] measured contextual embeddings alone −35% retrieval failures, + contextual BM25 −49%, + reranking −67%.
2. **Contextualized chunks** — either `voyage-context-4` (no extra tokens) or LLM-written chunk context (Anthropic's recipe; ~$1/M document tokens with caching in 2024, cheaper now with gpt-5-nano/Flash-Lite [I]). For forum/mailing-list threads, prepending thread title, date and the Lojban words defined in the thread is high-value.
3. **Glossing before embedding** — augment each chunk (and query) with English glosses of Lojban words from jbovlaste, e.g. `klama (come/go)`. This converts an OOD-token problem into an in-distribution one and is cheap (dictionary lookup, no LLM). Keep the raw Lojban for BM25.
4. **LLM query expansion / multi-query** — rewrite user questions into (a) an English paraphrase, (b) the likely Lojban terms, (c) a "hypothetical answer" (HyDE). Literature warns HyDE underperforms plain dense retrieval where factual precision matters (arXiv 2511.19349; 2604.01733) [S]; use it as one extra query in RRF, not the only one.
5. **Fine-tune an open embedder** on in-domain pairs (synthetic queries from an LLM + real Q/A threads). Candidates: Qwen3-Embedding-0.6B/4B, jina-v5-text-small (non-commercial license!), voyage-4-nano (open weights, but fine-tuning breaks compatibility with hosted voyage-4 vectors). Only worth it if the empirical test below shows dense retrieval failing on Lojban-bearing queries.
6. **Rerank** with a multilingual cross-encoder; zerank-2 explicitly advertises code-switching robustness [V], though CS-IR paper found rerankers most fragile — measure.

### 2.2 Minimal empirical test (do this before committing)

- Build **150–300 labelled queries** in three buckets: (A) English questions about Lojban grammar/usage; (B) English queries containing Lojban tokens ("how does `ku'i` differ from `.i` ..."); (C) pure-Lojban queries. Label 1–3 relevant chunks each, half from an LLM-assisted pass, half hand-checked from real forum questions with known answers.
- Embed a **50–100k-chunk sample** with each candidate (Voyage 4-large / context-4, gemini-embedding-2, Qwen3-8B hosted, plus BM25); Voyage's 200M free tokens cover this many times over.
- Report **Recall@10/20 and nDCG@10 per bucket** for BM25, dense, RRF hybrid, hybrid+reranker. Also log tokens-per-Lojban-word for each tokenizer (tiktoken vs Qwen vs Gemini) — fragmentation ratio is a cheap predictor of trouble.
- Decision rule: pick the dense model with the best bucket-B/C hybrid nDCG; if all dense models are within noise on B/C, pick on price and let BM25 carry the Lojban tokens.

---

## 3. Rerankers (2026)

| Reranker | Type | Context | Languages | Price | Notes / sources |
|---|---|---|---|---|---|
| **Cohere `rerank-v4.0-pro`** [V name, S price] | cross-encoder API | 32K per doc | 100+ | $0.0025 / search (1 query × ≤100 docs) | Released 2025-12-11; `rerank-v4.0-fast` $0.002/search (2026-04-06); `rerank-3.5` ~$0.001–0.002/search (conflicting secondary sources). Per-search pricing is cheap at 10k queries/mo but opaque for long docs. https://docs.cohere.com/docs/rerank-overview , https://openrouter.ai/cohere/rerank-4-pro |
| **Voyage `rerank-2.5`** [V] | cross-encoder, instruction-following | 32K per pair (query ≤8K) | multilingual | $0.05/M tokens; `-lite` $0.02/M | 200M free tokens; 2M TPM base (4M lite). https://docs.voyageai.com/docs/pricing , https://blog.voyageai.com/2025/08/11/rerank-2-5/ |
| **ZeroEntropy `zerank-2`** [V] | cross-encoder, instruction-following, calibrated scores | not stated | 100+, claims code-switching (Spanglish/Hinglish) robustness | $0.025/M tokens; 2.5MB/min rate limit | Released 2025-11-18; `zerank-1-small` Apache-2.0. **Flag:** pricing page now says ZeroEntropy is joining Notion — verify continued API availability. https://www.zeroentropy.dev/pricing |
| **Jina `jina-reranker-v3`** [V] | listwise "last-but-not-late" 0.6B | 131K, ≤64 docs/call | 93 (trained 24); BEIR 62.1, MIRACL 66.5 | token packs (~$0.05/M via resellers [S]); 10M free tokens | CC-BY-NC weights; released 2025-10-01. https://jina.ai/models/jina-reranker-v3/ |
| **Mixedbread `mxbai-rerank-large-v2`** [S] | cross-encoder 1.5B (also 0.5B base) | 32K | 100+ | Apache-2.0 self-host; hosted via Mixedbread ($20/mo plan) or Together/Featherless | https://huggingface.co/mixedbread-ai/mxbai-rerank-large-v2 |
| **Qwen3-Reranker 0.6B/4B/8B** [S] | pointwise generative, open (Apache-2.0) | 32K | 100+ | self-host (or DeepInfra-style hosts) | Strongest open option; hosted availability varies. https://arxiv.org/pdf/2506.05176 |
| **bge-reranker-v2-m3** [S] | cross-encoder 568M, MIT | 8K | multilingual | self-host | Proven baseline; jina-v3 reports +5.4% over it. |
| **LLM-as-reranker** [S prices, I costs] | pointwise/listwise prompt | model ctx | any | gpt-5-nano $0.05 in / $0.40 out; Gemini 2.5 Flash-Lite $0.10/$0.40; Gemini 3.5 Flash-Lite $0.30/$2.50; Claude Haiku 4.5 $1/$5 | Per query, 20 passages × 300 tokens ≈ 6K in + ~100 out: gpt-5-nano ≈ $0.00034/query (~$3.4/10k queries), Flash-Lite 2.5 ≈ $0.0006. Comparable in cost to dedicated rerankers but 10–100× slower; industry guidance (ZeroEntropy, Redis, TDS 2026) keeps cross-encoders as the default and reserves LLM reranking for high-value flows or when you need reasoning about *why* a Lojban passage answers the question. |

For this corpus, the practical choice is between rerank-2.5 (cheap, 32K) and zerank-2 (cheapest, code-switching claim, but ownership transition); run both in the §2.2 test. Cohere's per-search billing works out to $10–25/mo at 10k queries — fine too.

---

## 4. Learned sparse vs BM25

- **Hosted learned-sparse options** [V/S]: Pinecone `pinecone-sparse-english-v0` (DeepImpact-style, **English**); Elastic ELSER (**English-only**; Elastic recommends multilingual-E5 dense for other languages); OpenSearch neural-sparse v3 (English) and `opensearch-neural-sparse-encoding-multilingual-v1` (Apache-2.0, BERT-uncased, 15 MIRACL languages, avg nDCG@10 0.629 vs BM25 0.305 on MIRACL; released 2024-11-07); Qdrant offers BM25, SPLADE++ and miniCOIL through built-in inference; Vespa and Milvus treat sparse as first-class.
- **Why they don't help here** [I]: learned sparse models add *expansion terms* from a natural-language vocabulary. Lojban words are not in those vocabularies, so they get no useful expansions — and, worse, BERT wordpieces of `ko'a` may collide with unrelated fragments. The literature's own caveat is that "BM25 handles out-of-vocabulary terms (product codes, error strings) better than SPLADE" [S, premai.io 2026]. SPLADE-family is a quality upgrade for rich English prose; for the Lojban tokens BM25 is strictly better.
- **BM25 is still the default lexical leg in 2026** [S, multiple: turbopuffer docs, Zilliz, PremAI, HF "Past and Present of Sparse Retrieval"]. What matters is tokenization:
  - SQLite FTS5 `unicode61` treats apostrophes as separators (`ko'a` → `ko`,`a`) [V, https://www.sqlite.org/fts5.html]; fix with `tokenize = "unicode61 tokenchars ''''"` and consider adding `.` so `.i` survives, or normalise Lojban apostrophes to `h` (an accepted orthographic variant) at index and query time [I].
  - Tantivy/LanceDB `simple` tokenizer also splits on non-alphanumerics; LanceDB exposes `ascii_folding`, `lower_case`, stemmers (for 18 natural languages — disable for Lojban) and an `ngram` tokenizer [V, https://docs.lancedb.com/search/full-text-search]. Pre-normalising text is easier than writing a custom tokenizer.
  - Do **not** stem or stop-word the Lojban fields; do keep a separate English field with stemming. Two BM25 fields with different analyzers, fused by RRF, is the pattern.

---

## 5. Vector / search stores for 1–5M chunks (solo developer)

### 5.1 Facts gathered

- **pgvector** 0.8.x [V]: HNSW/IVFFlat, `halfvec` (2 B/dim) and `bit` binary vectors, iterative index scans for filtered queries (0.8.0, 2024-10). Build memory for 5M×1024 HNSW is several GB; fine on a 16 GB VM. Postgres BM25 via **ParadeDB `pg_search`** (Tantivy-based) or **VectorChord-BM25**; VectorChord (RaBitQ-based) reports 1,565 inserts/s vs pgvector 246 and higher QPS at >95% recall [S, vectorchord.ai docs]. pgvectorscale (Timescale) is the other accelerator [S].
- **SQLite + sqlite-vec + FTS5** [V]: sqlite-vec is still pre-1.0 (0.1.x alpha), **brute-force only — no ANN index**; metadata columns/filtering added Nov 2024. Community reports ~1M chunks with hybrid results <50 ms on commodity hardware [S]; at 2–5M×1024 float32 a brute-force scan is 8–20 GB/query — only workable with binary or Matryoshka-256 vectors plus rescoring [I]. FTS5 gives BM25 natively.
- **LanceDB** [V]: Rust core with Python/TS/Rust SDKs at 1.0; vector + BM25 FTS + SQL filters in one file/object-store dataset; automatic dataset versioning, tags, time-travel ("git for tables") — the only embedded store with index versioning built in. Hybrid fusion/reranking done client-side (RRF/rerankers in SDK).
- **Qdrant** [V]: Query API (≥1.10) with prefetch, RRF/DBSF fusion, sparse vectors, BM25/SPLADE/miniCOIL inference, named vectors (≥1.18 used for zero-downtime model migration); Cloud free tier 0.5 vCPU/1 GB/4 GB (too small for 2M×1024 float, OK with int8/binary + on-disk); paid from ~$0.014/h/node [S].
- **Weaviate** [V]: BM25+vector hybrid native; Cloud free sandbox 100k objects; Flex from $45/mo, $0.00465/1M dims·mo (2M×1024 = 2.05B dims ≈ $9.5/mo + storage) [I].
- **Milvus** [V docs]: BM25 full-text + hybrid since 2.5; Milvus Lite (embedded Python) support for FTS not documented — verify. Heavier ops than needed.
- **Chroma** [V]: `$contains`/regex document filters only, **no BM25 ranking**; Chroma Cloud $2.50/GiB written, $0.33/GiB-mo [S]. Not a hybrid store.
- **turbopuffer** [V]: object-storage-backed, BM25 + hybrid + sparse + namespace branching; $16/mo minimum (cut from $64 in Jun 2026), queries $1/PB scanned; typical 100M-vector bills $500–2,000/mo vs Pinecone $5–20k [S]. Cheap for a 2M-vector namespace (tens of $/mo at most) [I].
- **Pinecone** [S]: $50/mo min Standard; $0.33/GB-mo, $4/M WU, $16/M RU; free Starter 2 GB; sparse index preview (English model) and hosted rerankers. Serverless "read units" make 10k queries/mo trivial but the minimum dominates.
- **Cloudflare Vectorize** [V]: 20M vectors/index, **1,536 dims max, float32 only**, 10 KiB metadata, 10 metadata indexes, topK ≤100; pricing $0.05 per 100M stored dims, $0.01/M queried dims — 2M×1024 stored ≈ $1/mo [I]. **AI Search (ex-AutoRAG)** [V release notes]: hybrid BM25+vector (2026-04-16), reranking (2025-10-28), BYO embeddings via AI Gateway (2025-09-25), built-in Vectorize index and included storage/indexing (2026-06-18). Lock-in: Workers AI embeddings or AI Gateway-routed providers; chunking is theirs.
- **Elasticsearch/OpenSearch** [S]: best-in-class lexical control, BBQ binary quantization GA in 9.0, ELSER/E5 built in; cheapest Elastic Cloud hosted ≈ $25–40/mo, serverless $0.09/VCU-h + $0.047/GB-mo; self-host needs JVM tuning. OpenSearch self-host is free but heavy.
- **Typesense / Meilisearch** [S]: both Rust (Meilisearch) / C++ (Typesense) keyword engines with hybrid vector search and built-in auto-embedders (OpenAI, Cohere, Mistral, HF, REST/user-provided); Meilisearch `semanticRatio` fusion, vector compression. Great DX for a search UI, weaker for RAG-style top-k over millions of long chunks (Meilisearch memory-maps and prefers <10M docs [I]).
- **Vespa** [V license]: Apache-2.0, first-class BM25 + dense + sparse + ONNX rerankers; Vespa Cloud pricing not extractable today; self-host is a multi-container JVM system — overkill for one developer [I].
- **Tantivy / Quickwit** [V]: Tantivy (Rust Lucene) is the BM25 engine under LanceDB, pg_search and Quickwit; Quickwit joined Datadog (2025) with re-licensing to Apache-2.0 and continued releases [S]. Fine as an embedded BM25 library in a Rust service.

### 5.2 Recommendation matrix

| Store | Monthly cost @2M chunks | Ops burden | Hybrid in one system | Metadata filtering | Index versioning | Rust | Python | TS | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Postgres + pgvector (+VectorChord/pg_search) | $0 self-host / $15–40 managed | medium (one DB you already know) | yes with pg_search or VectorChord-BM25; else app-side | excellent (SQL) | manual (table per model, view swap) | good (sqlx) | good | good | **Default if you already run Postgres** |
| SQLite + sqlite-vec + FTS5 | $0 | very low | yes (RRF in SQL) | good | file copy per model | good (rusqlite) | good | good (better-sqlite3) | Great ≤1M chunks or with binary/MRL vectors; brute-force KNN beyond that |
| LanceDB | $0 (local/S3) | low | yes (FTS + vector, fuse in SDK) | good (SQL filters) | **built-in versions/tags** | **native** | good | good | **Best fit for a Rust stack; versioning solves §7 cheaply** |
| Qdrant (self-host or Cloud) | $0 self / ~$25–60 Cloud | low–medium | yes (BM25/sparse+dense, RRF/DBSF) | good | named vectors, aliases | good (official crate) | good | good | Best "proper" hybrid vector DB; named-vector migration is elegant |
| turbopuffer | ≥$16 | none | yes | good | namespace branching | REST | SDK | SDK | Cheapest managed with real BM25; vendor lock-in low |
| Weaviate Cloud | ≥$45 | none | yes | good | aliases | ok | good | good | Fine, pricier |
| Cloudflare Vectorize + D1/R2 (+AI Search) | ~$1–5 (+Workers Paid $5) | none | Vectorize alone: no BM25 (D1 FTS5 or AI Search hybrid) | 10 indexed fields, 64 B each | manual (new index) | wasm/Workers | REST | **native** | Attractive for a Workers/TS deployment; 1,536-dim cap and metadata limits are the constraints |
| Pinecone | ≥$50 | none | sparse-dense (English sparse model) | good | index per model | REST | good | good | Minimum too high for this scale |
| Elastic/OpenSearch | $25–200 managed; self-host heavy | high | yes, best lexical control | excellent | aliases (best practice) | REST | good | good | Only if you want Lucene-grade analyzers |
| Meilisearch / Typesense | $0 self / cloud from ~$30 | low | yes (auto-embedders) | good | index swap | REST | good | good | Best for a search-box UI, not RAG top-k at 5M long chunks |
| Chroma | $0 / usage | low | **no BM25** | ok | collection per model | no | good | good | Skip |
| Milvus / Vespa | $0 self | high | yes | good | aliases | ok | good | ok | Over-engineered for one developer |

---

## 6. Cost model (worked example) [I, using verified list prices]

Assumptions: 1 GB text ≈ 250M tokens; ~2M chunks of ~125 tokens (or 5M shorter chunks); 10k queries/month × ~50 tokens; reranking top-50 × ~300 tokens = 150M tokens/month.

| Item | Voyage `voyage-4-large` | Google `gemini-embedding-2` | Cohere `embed-v4` | (ref.) OpenAI 3-large | (ref.) Qwen3-8B hosted |
|---|---|---|---|---|---|
| Plain one-time embed, 250M tok | $30 (→ **$6** after 200M free) | $50 (batch $25) | $30 | $32.50 (batch $16.25) | $2.50 |
| With prepended LLM context (~2× tokens = 500M) | $60 (batch $40; ≈$36 after free) | $100 (batch $50) | $60 | $65 (batch $32.50) | $5 |
| Contextual via `voyage-context-4` (no doubling; ~5% overlap) | **≈$31 (→ ~$8 after free)** | n/a | n/a | n/a | n/a |
| LLM context generation for 2M chunks (~80 output + cached-doc input tokens each) | gpt-5-nano ≈ $70–150; Gemini 2.5 Flash-Lite ≈ $100–200; Haiku 4.5 ≈ $500–1,000 — only if not using context-4 | | | | |
| Queries, 0.5M tok/mo | $0.06 | $0.10 | $0.06 | $0.07 | $0.005 |
| Reranking 150M tok/mo | rerank-2.5 $7.50 (lite $3) | — | rerank-4-fast $20 / pro $25 (per-search) | — | zerank-2 $3.75; jina-v3 ≈ $7.50 |
| **Year-1 total, contextual + rerank** | **≈ $100–130** | ≈ $150–250 | ≈ $300–400 | ≈ $150–250 | ≈ $60–100 |

Take-away: embedding is a one-off tens-of-dollars problem at this scale; the free tiers (Voyage 200M tokens, Jina 10M rerank tokens) cover the entire evaluation. Re-embedding on a model upgrade costs about the same each time, so the decision is quality-driven, not cost-driven.

**Storage for vectors** (2M × 1024 dims; ×2.5 for 5M):

| Format | Bytes/vector | 2M chunks | 5M chunks | Recall note |
|---|---|---|---|---|
| float32 | 4,096 | 8.2 GB | 20.5 GB | reference |
| float16 / `halfvec` | 2,048 | 4.1 GB | 10.2 GB | ~no loss [S] |
| int8 | 1,024 | 2.0 GB | 5.1 GB | ~1–2% loss, Voyage/Cohere emit int8 natively [S] |
| binary (1 bit/dim) | 128 | 256 MB | 640 MB | needs oversample + float/int8 rescoring; Voyage claims binary-512 ≈ OpenAI float-3072 [S] |
| MRL 256-dim float32 | 1,024 | 2.0 GB | 5.1 GB | ~95% of full-dim quality (OpenAI/Voyage claims) [S] |

Add ~1.3–1.6× for an HNSW graph (pgvector/Qdrant) and the raw text (1 GB) plus metadata.

---

## 7. Embedding versioning and migration practice [V sources, I synthesis]

- **Store provenance on every vector**: `model_id` (e.g. `voyage-4-large@2026-01`), `dims`, `dtype`, `input_type` (query/document), `chunker_version`, `context_strategy` (`context-4` | `llm-prefix-v2` | `none`), `embedded_at`. Put it in a column/payload *and* in the index/collection name (`chunks_v4l_1024_int8_2026-08`). Different models — and different versions of one model — are geometrically incompatible; Gemini explicitly says 001→2 embeddings must be regenerated [V].
- **Keep the source text and chunk boundaries next to the vectors** (Qdrant's tutorial makes this the precondition for re-embedding without touching the origin DB) [V].
- **Migration patterns** (Qdrant 2026 tutorial; tianpan.co 2026-04-09; Milvus/levelop guides): (1) blue-green — new collection/table, dual-write, background re-embed, alias/view swap, instant rollback; (2) named vectors — add `vec_v5` alongside `vec_v4` on the same point, backfill, flip the `using` parameter, drop old (Qdrant ≥1.18; pgvector: a second column; LanceDB: a new column + dataset version tag); (3) lazy — re-embed on access, route queries to both indexes with RRF during the window; (4) drift-adapter — train a small linear/MLP map from new-model query space into the old document space, reported 95–99% recovery [S] — a stopgap for query-side upgrades only.
- **Voyage-specific advantage** [V]: all voyage-4 models share one space, so you can upgrade *query* embedding from `4-lite` to `4-large` (or move query embedding on-device with open-weight `voyage-4-nano`) without re-embedding documents; a future voyage-5 will presumably not be compatible.
- **Eval gate**: keep the §2.2 labelled set as a regression suite; re-run on every model/chunker change; migrate only on a clear win (>3–5% nDCG on the Lojban buckets) or vendor deprecation. Log per-query model id so A/B routing and rollback are trivial.
- **LanceDB** gives you table versions/tags for free, which is the cheapest way to snapshot "index as of model X" without duplicating infrastructure [V].

---

## 8. Recommendation for this project

**Embedding**: Start with **Voyage `voyage-context-4`** (contextualized chunks, $0.12/M, 200M free tokens, int8/binary outputs, 32K chunk / 120K document context) as the primary dense model, with `voyage-4-large` as the non-contextual fallback in the same family. Rationale: (a) contextual chunk embedding without token doubling directly addresses thread-style discussions where a chunk's meaning depends on the surrounding thread; (b) shared embedding space across the 4-series plus open-weight `voyage-4-nano` gives cheap/offline query embedding and painless intra-family upgrades; (c) native int8/binary halves storage; (d) 200M free tokens make the full corpus embedding almost free. Run **`gemini-embedding-2`** (strongest published multilingual/MMTEB score among APIs, 8K context, but $0.20/M, no quantized output, small batch caps) and **Qwen3-Embedding-8B hosted** ($0.01/M, top open MMTEB) as challengers in the empirical test; Cohere v4 and OpenAI 3-large are not worth the slot unless Bedrock/Azure procurement dictates.

**Lexical leg**: BM25 with two analyzers (English stemmed; Lojban raw with apostrophe-preserving tokenizer or `'`→`h` normalisation), plus a dictionary-gloss augmentation field. Skip learned sparse (English-centric vocabularies, no Lojban expansions).

**Fusion + rerank**: RRF over {dense, BM25-en, BM25-jbo, optional LLM-expanded query}, then `rerank-2.5` (or `zerank-2` if it stays available) on top-50; LLM reranking only for the final answer's citations.

**Store**: for a Rust stack, **LanceDB** (vector + Tantivy BM25 + versioning, zero ops); for Python, **Postgres + pgvector (+ pg_search or VectorChord-BM25)** if Postgres already exists, otherwise LanceDB; for a Cloudflare/TypeScript deployment, **Vectorize (1,024-dim int8-derived float or MRL-1024) + D1 FTS5** or simply AI Search's hybrid mode if you accept its chunking. SQLite+sqlite-vec is fine up to ~1M chunks or with binary vectors.

**Verify empirically** (§2.2): per-bucket recall on Lojban-token queries; tokenizer fragmentation of Lojban words; whether `context-4` beats `4-large`+LLM-prefix on threads; whether reranking helps or hurts on bucket C (code-switch papers say rerankers are the most fragile stage); zerank-2 availability post-Notion; Gemini batch caps for a 250M-token backfill.

---

## Sources (fetched 2026-08-26 unless noted)

- Voyage pricing https://docs.voyageai.com/docs/pricing ; models https://docs.voyageai.com/docs/embeddings ; contextual chunks https://docs.voyageai.com/docs/contextualized-chunk-embeddings ; rate limits https://docs.voyageai.com/docs/rate-limits ; model table https://www.mongodb.com/docs/voyageai/models/ ; Voyage 4 post https://blog.voyageai.com/2026/01/15/voyage-4/ (2026-01-15); voyage-context-3 post https://blog.voyageai.com/2025/07/23/voyage-context-3/ (2025-07-23); rerank-2.5 post https://blog.voyageai.com/2025/08/11/rerank-2-5/ (2025-08-11); MongoDB acquisition https://www.mongodb.com/press/mongodb-announces-acquisition-of-voyage-ai (2025-02-24).
- Gemini embeddings https://ai.google.dev/gemini-api/docs/embeddings ; rate limits https://ai.google.dev/gemini-api/docs/rate-limits ; pricing mirror https://embeddingcost.com/google (Jul 2026); paper https://arxiv.org/abs/2605.27295 (2026-05-26).
- OpenAI pricing mirrors https://embeddingcost.com/openai , https://www.cloudzero.com/blog/openai-pricing/ (Aug 2026); original launch https://openai.com/index/new-embedding-models-and-api-updates/ (2024-01).
- Cohere https://docs.cohere.com/docs/embeddings ; https://docs.cohere.com/docs/rerank-overview ; https://embeddingcost.com/cohere (Jul 2026); https://openrouter.ai/cohere/rerank-4-pro ; Bedrock note https://aws.amazon.com/about-aws/whats-new/2025/10/coheres-embed-v4-multimodal-embeddings-bedrock (2025-10).
- Jina https://jina.ai/embeddings/ ; https://jina.ai/models/jina-embeddings-v5-text-small/ ; https://arxiv.org/abs/2602.15547 (2026-02); https://jina.ai/models/jina-reranker-v3/ (2025-10-01).
- Mistral https://mistral.ai/news/codestral-embed/ (2025-05). Amazon https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-titan-text-embeddings-v2.html ; https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-nova-multimodal-embeddings . NVIDIA https://build.nvidia.com/nvidia/llama-3_2-nv-embedqa-1b-v2/modelcard . Qwen3 https://openrouter.ai/qwen/qwen3-embedding-8b ; https://arxiv.org/pdf/2506.05176 (2025-06); https://www.alibabacloud.com/help/en/model-studio/embedding .
- Leaderboards/benchmarks https://www.codesota.com/benchmarks/mteb (2026-05-17); https://aimultiple.com/embedding-models (2026-08-17); https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html (2026-03-20); MMTEB https://arxiv.org/abs/2502.13595 (2025-02).
- OOD/code-switching: LASER https://aclanthology.org/Q19-1038.pdf (TACL 2019, quote verified from PDF); CS-IR https://arxiv.org/html/2604.17632v1 (2026-04-19); embedding interpolation https://arxiv.org/html/2606.13537v1 (2026-06); bootstrapping low-resource https://arxiv.org/html/2603.01732v2 (2026-03-17); Tatoeba stats https://tatoeba.org/en/stats/sentences_by_language ; Lojban Wikipedia https://jbo.wikipedia.org/wiki/Special:Statistics ; Anthropic Contextual Retrieval https://www.anthropic.com/engineering/contextual-retrieval (2024-09-19); HyDE caveats https://arxiv.org/pdf/2511.19349 , https://arxiv.org/html/2604.01733v1 ; NVIDIA/Cisco fine-tuning https://blogs.cisco.com/ai/fine-tuning-embedding-models-for-enterprise-retrieval-a-practical-guide-with-nvidia-nemotron-recipe .
- Rerankers: ZeroEntropy https://www.zeroentropy.dev/articles/zerank-2-advanced-instruction-following-multilingual-reranker (2025-11-18), https://www.zeroentropy.dev/pricing ; LLM-vs-cross-encoder https://zeroentropy.dev/articles/should-you-use-llms-for-reranking-a-deep-dive-into-pointwise-listwise-and-cross-encoders/ , https://redis.io/blog/top-reranking-models-rag-accuracy/ ; Mixedbread https://huggingface.co/mixedbread-ai/mxbai-rerank-large-v2 ; LLM prices https://www.aipricing.guru/blog/ai-api-pricing-comparison-2026/ (2026-08-19), https://ai.google.dev/gemini-api/docs/pricing .
- Sparse: https://www.pinecone.io/learn/sparse-retrieval/ ; https://docs.pinecone.io/models/pinecone-sparse-english-v0 ; https://www.elastic.co/docs/explore-analyze/machine-learning/nlp/ml-nlp-elser ; https://huggingface.co/opensearch-project/opensearch-neural-sparse-encoding-multilingual-v1 (2024-11-07); https://opensearch.org/blog/advancing-search-with-opensearch-v3-neural-sparse-models-and-a-multilingual-retrieval-model/ ; https://www.premai.io/blog/hybrid-search-for-rag-bm25-splade-and-vector-search-combined/ ; https://huggingface.co/blog/yjoonjang/the-past-and-present-of-sparse-retrieval .
- Stores: pgvector https://www.postgresql.org/about/news/pgvector-080-released-2952 (2024-10), https://jkatz05.com/post/postgres/pgvector-scalar-binary-quantization/ ; VectorChord https://docs.vectorchord.ai/vectorchord/benchmark/pgvectorscale.html ; sqlite-vec https://github.com/asg017/sqlite-vec/releases , https://alexgarcia.xyz/blog/2024/sqlite-vec-hybrid-search/index.html ; FTS5 https://www.sqlite.org/fts5.html ; LanceDB https://docs.lancedb.com/search/full-text-search , https://github.com/lance-format/lance ; Qdrant https://qdrant.tech/documentation/concepts/hybrid-queries/ , https://qdrant.tech/documentation/tutorials-operations/embedding-model-migration/ , https://qdrant.tech/cloud/ ; Weaviate https://weaviate.io/pricing ; Milvus https://milvus.io/docs/full-text-search.md ; Chroma https://docs.trychroma.com/docs/querying-collections/full-text-search , https://docs.trychroma.com/cloud/pricing ; turbopuffer https://turbopuffer.com/pricing , https://turbopuffer.com/docs/pricing-log (Jun/Aug 2026 entries), https://turbopuffer.com/docs/hybrid ; Pinecone https://docs.pinecone.io/guides/manage-cost/understanding-cost ; Cloudflare https://developers.cloudflare.com/vectorize/platform/limits/ , https://developers.cloudflare.com/vectorize/platform/pricing/ , https://developers.cloudflare.com/ai-search/platform/release-note/ (2026-04-16 hybrid, 2026-06-18 pricing); Elastic https://www.elastic.co/blog/whats-new-elastic-search-9-0-0 , https://www.elastic.co/pricing/serverless-search ; Meilisearch https://www.meilisearch.com/docs/capabilities/hybrid_search/overview ; Typesense https://typesense.org/docs/latest/api/vector-search.html ; Vespa https://github.com/vespa-engine/vespa ; Tantivy/Quickwit https://github.com/quickwit-oss/tantivy , https://quickwit.io/blog/quickwit-joins-datadog .
- Versioning: https://tianpan.co/blog/2026-04-09-embedding-models-production-versioning-index-drift (2026-04-09); https://milvus.io/ai-quick-reference/how-do-you-version-and-manage-changes-in-embedding-models ; https://levelop.dev/blog/vector-embedding-models-generation-versioning-drift .
