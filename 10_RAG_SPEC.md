# ORCA — Scientific Document RAG Specification

**Document:** 10 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** PROPOSED · SHOULD-HAVE for MVP — IMPLEMENTATION REQUIRED

---

## 1. Role of RAG in ORCA

RAG in ORCA is **not** the answer engine. Live authoritative data answers *what the
conditions are*. RAG answers *what the conditions mean, how a product is defined, and
what guidance says* — and it does so with citations.

```
     "Is the sea safe tomorrow?"        → capability tools (live data)   ← NOT RAG
     "What does a PFZ advisory mean?"   → RAG over methodology docs
     "Why is chlorophyll elevated?"     → live data + RAG for mechanism
     "What is the small-craft guidance?"→ RAG over official guidance     ← quoted
```

**Hard boundary.** RAG output may **never** change an assessment verdict. Verdicts come
from live data evaluated against documented thresholds. RAG may add cited explanatory
context to a rationale, define a term, or surface official guidance text. This boundary
is enforced structurally: the Risk Assessment Agent's verdict function does not take RAG
passages as an input (`06_AGENT_SPEC.md` §6.6).

**No hallucination claim.** RAG reduces ungrounded generation by constraining the model to
retrieved passages and by rejecting unsupported claims at validation. It does not
eliminate hallucination. ORCA claims *source-grounded generation with claim/evidence
association*, and measures the residual ungrounded rate (§14).

---

## 2. Corpus Types

| Corpus | Content | Authority tier | Use |
|---|---|---|---|
| `methodology` | Published descriptions of products ORCA consumes (PFZ methodology, SST/ocean-colour product documentation, forecast model descriptions) | official / institutional | Explain what a product means and its limits |
| `dataset_docs` | ERDDAP dataset metadata pages, CMEMS product user manuals, variable definitions and conventions | official | Ground unit, resolution and convention statements |
| `advisory_guidance` | Published safety/advisory guidance relevant to small craft and coastal operations | official | Quoted guidance; never paraphrased as ORCA's own rule |
| `glossary` | Marine and oceanographic terminology, including regional-language equivalents | institutional | Terminology consistency across languages |
| `scientific_literature` | Peer-reviewed literature on PFZ methodology, ocean fronts, productivity, regional oceanography | peer_reviewed | Mechanism explanations |
| `sop` | ORCA's own operating procedures, threshold rationales, validation records | internal | Explain ORCA's own methodology to analysts |

**Acquisition rule.** Only documents ORCA is licensed to store and quote are ingested.
Each document records `licence_reference`; anything without a clear basis is excluded, and
the exclusion is recorded rather than silently skipped.

---

## 3. Ingestion Pipeline

```
 discover ──▶ fetch ──▶ verify ──▶ parse ──▶ segment ──▶ enrich ──▶ chunk ──▶ embed ──▶ index
    │           │         │          │          │           │         │         │        │
 manifest    checksum  licence   PDF/HTML/   sections   metadata   token    model    pgvector
  or URL      + dedupe  check     XML/txt    + tables   extraction  windows  batch   + tsvector
```

| Stage | Detail |
|---|---|
| **Discover** | A reviewed `corpus_manifest.yaml` lists documents with URI, corpus, authority tier and licence reference. **No open-web crawling.** |
| **Fetch** | Retrieve, record `checksum`, store the original in object storage (`docs/{document_id}/`) |
| **Verify** | Reject on checksum mismatch with a previously ingested version; register the change as a new `version` |
| **Parse** | PDF → text + layout (page numbers, headings, tables preserved as structured blocks); HTML → readable text with heading hierarchy; scanned PDFs require OCR and are flagged `ocr: true` with lower retrieval weight |
| **Segment** | Split by document structure (heading path), not by raw character offset |
| **Enrich** | Extract title, publisher, publication date, version, language, section path, page range, figure/table captions |
| **Chunk** | See §5 |
| **Embed** | Batch embedding with the configured model; `embedding_model` recorded per chunk |
| **Index** | pgvector HNSW (cosine) + PostgreSQL `tsvector` GIN, in the same transaction |

Ingestion is **idempotent** per `(document_uri, checksum)`. Re-ingesting an unchanged
document is a no-op; a changed document creates a new version and marks the previous one
`superseded_by`.

---

## 4. Document Metadata

```json
{
  "document_id": "doc-01J…",
  "title": "<document title>",
  "corpus": "methodology",
  "source_org": "INCOIS",
  "publisher": "<publisher>",
  "document_uri": "<canonical url or identifier>",
  "object_uri": "s3://orca-prod/docs/doc-01J…/original.pdf",
  "published_at": "2024-06-01",
  "version": "v2",
  "language": "en",
  "authority_tier": "official",
  "licence_reference": "<terms reference>",
  "status": "active",
  "superseded_by": null,
  "checksum": "sha256:…",
  "ingested_at": "2026-09-02T09:00:00Z",
  "ocr": false
}
```

`authority_tier ∈ official | peer_reviewed | institutional | other` drives reranking
priority and what may be quoted as guidance.

---

## 5. Chunking Strategy

| Parameter | Value | Rationale |
|---|---|---|
| Primary unit | Section (heading path) | Scientific documents are structurally meaningful |
| Target size | 400–800 tokens | Fits reranker context; preserves a full argument |
| Overlap | 15 % (≈ 60–120 tokens) | Preserves cross-boundary context |
| Hard maximum | 1 200 tokens | Long sections are split at paragraph boundaries |
| Minimum | 80 tokens | Shorter fragments merge into the neighbouring chunk |
| Tables | Kept whole where possible; serialised as Markdown with the caption prepended | A split table is uninterpretable |
| Figures | Caption + surrounding paragraph become a chunk; the image is referenced, not embedded | |
| Formulas | Retained as text; flagged `contains_formula` | |

Each chunk carries a **contextual header** prepended before embedding (not stored in the
displayed text):

```
[<document title> · <section path> · <publisher> · <published_at>]
<chunk text>
```

This measurably improves retrieval for fragments whose meaning depends on their section,
and it costs nothing at query time.

All values above are **initial engineering parameters requiring validation** against the
retrieval evaluation set (§14).

---

## 6. Embeddings

| Concern | Decision |
|---|---|
| Model | Configured via `RAG_EMBEDDING_MODEL`; accessed through the provider abstraction. **Not** hard-coded |
| Dimension | Fixed by the model; the `doc_chunks.embedding` column dimension is a migration-level decision |
| Multilingual | The MVP corpus is predominantly English. Non-English documents are embedded with a multilingual-capable model or, if unavailable, retrieved lexically only — and that limitation is recorded, not hidden |
| Normalisation | L2-normalised; cosine distance |
| Versioning | `embedding_model` per chunk. A model change requires a full re-embedding migration; mixed-model indexes are forbidden |
| Batching | Configurable batch size with retry; ingestion failures leave the document `status = 'partial'` and are retried, never partially indexed silently |

---

## 7. Retrieval Architecture

```
                       query (+ run context: parameter, region, time, language)
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
              ┌───────────────────┐          ┌────────────────────┐
              │  DENSE retrieval  │          │ LEXICAL retrieval  │
              │  pgvector HNSW    │          │ tsvector / BM25-ish│
              │  top_k = 30       │          │  top_k = 30        │
              └─────────┬─────────┘          └─────────┬──────────┘
                        └──────────────┬───────────────┘
                                       ▼
                          ┌──────────────────────────┐
                          │  FUSION  (RRF, k=60)     │
                          └────────────┬─────────────┘
                                       ▼
                          ┌──────────────────────────┐
                          │  METADATA FILTERING      │  corpus · authority · language
                          │  (pre- or post-filter)   │  status=active · date bounds
                          └────────────┬─────────────┘
                                       ▼
                          ┌──────────────────────────┐
                          │  RERANKING  → top_n = 6  │  cross-encoder or LLM reranker
                          └────────────┬─────────────┘
                                       ▼
                          ┌──────────────────────────┐
                          │  THRESHOLD GATE          │  min score, min passages
                          └────────────┬─────────────┘
                                       ▼
                     passages + citations  →  Reporting / Risk rationale
```

### 7.1 Hybrid rationale
Dense retrieval handles paraphrase ("why is the water greener?" → "chlorophyll
concentration"); lexical retrieval handles exact identifiers that embeddings blur
(`KD490`, `incois_oceansat2_datasets`, a bulletin number). Marine documentation is full of
exact identifiers, so lexical retrieval is not optional.

### 7.2 Reciprocal Rank Fusion
`score(d) = Σ_r 1 / (k + rank_r(d))`, `k = 60`, applied over the dense and lexical rank
lists. RRF is used rather than score blending because dense and lexical scores are not
comparable quantities.

### 7.3 Filters

| Filter | Source | Effect |
|---|---|---|
| `corpus` | Query intent | A terminology question searches `glossary` first |
| `authority_tier` | Query kind | Guidance questions restrict to `official` |
| `status = 'active'` | Always | Superseded documents are excluded from default retrieval |
| `language` | Session | Prefer the user's language; fall back to English with a note |
| `published_at` | Query | Excludes documents outside a requested period |
| `region_tags` | Run context | Prefers Indian-Ocean-specific material over global material |

### 7.4 Reranking
A cross-encoder reranker (or, if unavailable, an LLM reranker with a fixed rubric) scores
each fused candidate against the query. Top 6 passages proceed. The reranker's model
identity and version are recorded per query in `rag_queries.retrieved`.

---

## 8. Citation Mapping

Every retrieved passage becomes a citable object:

```json
{
  "citation_id": "ct-014",
  "chunk_id": "chk-…",
  "document_id": "doc-01J…",
  "document_title": "<title>",
  "publisher": "<publisher>",
  "authority_tier": "official",
  "section_path": "3.2 Advisory generation",
  "page_from": 14, "page_to": 15,
  "published_at": "2024-06-01",
  "version": "v2",
  "quote": "<verbatim span actually used, ≤ 40 words>",
  "document_uri": "<link>",
  "retrieval": {"dense_rank": 3, "lexical_rank": 11, "rrf": 0.031, "rerank_score": 0.82}
}
```

**Rules.**
1. A RAG-derived statement in an answer must reference ≥ 1 `citation_id`.
2. The cited `quote` must be a **verbatim span** from the chunk. A quote that does not
   appear verbatim in the chunk fails validation.
3. Citations render in the same evidence panel as data provenance, visually distinguished
   as *document evidence* rather than *measurement evidence*
   (`02_FRONTEND_DESIGN_SPEC.md` §7).
4. RAG-derived claims carry `claim_kind: "interpretation"` (or `"quote"`) and
   `official_source: true` only when the underlying document is `authority_tier: official`
   **and** the text is quoted rather than paraphrased.

---

## 9. Claim / Evidence Association

```
generated sentence
      │  claim segmentation (deterministic: sentence + clause splitting)
      ▼
   Claim { text, claim_kind }
      │  attribution: each claim → supporting passages
      ▼
   supported?  ── no ──▶  drop the claim OR regenerate (once) OR mark "not established"
      │ yes
      ▼
   Claim.citation_ids = [ct-…]
```

**Attribution method (MVP).** An entailment check: for each claim, the top passages are
scored for whether they support it. Implemented first as an LLM check with a strict rubric
(`supported | partially_supported | unsupported`) at `temperature = 0`, with the
possibility of replacing it with an NLI model later. The check runs on the **generated
claim**, not on the model's reasoning.

**Failure handling.**
- `unsupported` claim ⇒ removed from the answer; if it was material, the answer states
  that the point could not be established from available documentation.
- `partially_supported` ⇒ retained with a hedge and the citation, or dropped if it is a
  safety-relevant statement.
- Systematic unsupported rates are tracked as a quality metric (§14).

---

## 10. Confidence Thresholds

| Gate | Initial parameter | Behaviour below threshold |
|---|---|---|
| Minimum rerank score for a usable passage | 0.35 | Passage discarded |
| Minimum passages to answer a documentation question | 2 | Answer states that documentation was insufficient |
| Minimum top-1 rerank score to make a definitional statement | 0.55 | ORCA declines to define rather than guessing |
| Maximum passage age for `advisory_guidance` before a staleness notice | 24 months | Answer carries a "guidance may have been updated" notice |

All thresholds are **initial engineering parameters requiring validation** against the
evaluation set. They are configuration, not code constants.

---

## 11. Stale and Superseded Documents

| Situation | Behaviour |
|---|---|
| A document has `superseded_by` | Excluded from default retrieval; retrievable only in an explicit historical query, and the answer says which version it is |
| `published_at` older than the corpus staleness policy | Retrieved, but the citation carries `stale: true` and the answer notes the publication date |
| Document withdrawn | `status = 'withdrawn'`; excluded entirely; existing citations to it in stored runs are marked withdrawn at read time, not deleted (runs remain reproducible) |
| Checksum change on re-fetch | New version ingested; old version marked superseded; a diff summary is recorded |

**Rule.** ORCA never silently upgrades an old citation to a new document version. A stored
run cites what it actually used.

---

## 12. RAG as a Capability Tool

RAG is exposed to agents as one capability tool, consistent with
`04_ORCA_TOOL_CONTRACTS.md`:

```json
// search_marine_knowledge  (P1)
{
  "query": "How is a Potential Fishing Zone advisory generated?",
  "corpora": ["methodology", "scientific_literature"],
  "authority_min": "institutional",
  "language": "en",
  "top_n": 6,
  "context": {"region": "Arabian Sea", "parameters": ["chlorophyll_a", "sst"]}
}
```
```json
// response
{
  "status": "success",
  "tool": "search_marine_knowledge",
  "data": [{"type": "Passage", "citation_id": "ct-014", "text": "…",
            "rerank_score": 0.82, "value_kind": "observed",
            "provenance_id": "pv-rag-014"}],
  "quality": {"passages": 4, "top_score": 0.82, "corpora_searched": ["methodology"]},
  "errors": []
}
```

Failure states: `NO_DATA` (nothing above threshold), `DATASET_UNAVAILABLE` (corpus not
ingested), `SOURCE_UNAVAILABLE` (vector store down), `TIMEOUT`.
Provenance for a passage records `document_id`, `version`, `section_path`, `retrieved_at`
and the retrieval scores — the same discipline as measurement provenance.

---

## 13. Prompt-Injection Defence

Retrieved passages are **untrusted data**.

| Defence | Implementation |
|---|---|
| Structural separation | Passages are placed in a delimited data region; the system prompt states that content inside it is reference material, never instruction |
| Instruction stripping | Ingestion flags chunks containing imperative patterns aimed at an assistant; flagged chunks are down-weighted and logged |
| Tool isolation | The RAG-consuming path has **no tool access**. A passage cannot cause a retrieval, a state write or an external call |
| Output validation | Grounding validation runs after generation; an injected instruction that produced an unsupported claim is caught there |
| Corpus control | Curated manifest only; no open-web ingestion, which removes the main injection vector |
| Monitoring | Injection-pattern hits are counted and alerted on (`20_OBSERVABILITY_AND_AUDIT_SPEC.md`) |

---

## 14. Evaluation

A fixed evaluation set of ≥ 100 questions across the corpora, each with a reference answer
and a set of acceptable supporting passages, curated by the team and reviewed against
source documents. **No benchmark results are asserted in this documentation set** — the
harness is defined; the numbers must be produced by running it
(`15_EVALUATION_AND_TESTING_SPEC.md`).

### 14.1 Retrieval metrics
| Metric | Definition |
|---|---|
| Recall@k | Fraction of questions whose gold passage appears in the top k (k = 5, 10, 30) |
| MRR | Mean reciprocal rank of the first gold passage |
| nDCG@10 | Graded relevance |
| Fusion lift | Recall@10 of hybrid vs dense-only and lexical-only |
| Filter precision | Fraction of retrieved passages satisfying the intended filters |

### 14.2 Generation metrics
| Metric | Definition |
|---|---|
| Citation precision | Cited passages that actually support their claim |
| Citation recall | Material claims that carry a citation |
| **Ungrounded claim rate** | Material claims with no supporting passage — the headline honesty metric |
| Quote fidelity | Quoted spans appearing verbatim in the cited chunk (target: 100 %, hard-enforced) |
| Refusal correctness | Questions with insufficient evidence where ORCA correctly declines |
| Answer faithfulness | Human-rated agreement with the cited source |

### 14.3 Adversarial set
- Questions whose answer is genuinely absent from the corpus (must decline).
- Questions whose answer exists only in a superseded document (must flag the version).
- Questions phrased with false premises (must correct rather than comply).
- Passages containing injected instructions (must not be followed).
- Near-duplicate passages differing in one number (must cite the right one).

### 14.4 Regression policy
The evaluation set runs in CI on every change to chunking, embedding model, retrieval
parameters or prompts. A drop beyond the configured tolerance in Recall@10, citation
precision or ungrounded claim rate fails the build.

---

## 15. Mitigations Against Ungrounded Generation

Layered, because no single measure is sufficient:

1. **Retrieve before generating** — no documentation answer without retrieved passages.
2. **Threshold gates** — below-threshold retrieval produces a decline, not a guess.
3. **Constrained generation** — the prompt supplies passages and forbids outside
   knowledge for factual claims.
4. **Claim-level attribution** — each generated claim is checked against passages.
5. **Verbatim quote enforcement** — quotes are string-matched against the chunk.
6. **Deterministic fallback** — repeated validation failure yields a template answer built
   from the passages themselves.
7. **Separation of concerns** — RAG cannot alter verdicts, so an ungrounded documentation
   statement can never make an unsafe recommendation appear safe.
8. **Measurement** — the residual ungrounded rate is measured and reported, not claimed to
   be zero.

> ORCA's claim is precise: **source-grounded generation with claim/evidence association
> and a measured ungrounded-claim rate.** Not "hallucination-free".

---

## 16. MVP Scope for RAG

| Item | MVP |
|---|---|
| Corpora | `methodology`, `dataset_docs`, `glossary` (~30–60 curated documents) |
| Retrieval | Hybrid dense + lexical with RRF |
| Reranking | Enabled if a reranker is available; otherwise RRF-only, and the limitation is recorded |
| Citations | Mandatory |
| Claim attribution | Enabled for RAG-derived claims |
| Evaluation set | ≥ 50 questions for the MVP; ≥ 100 for the full system |
| Multilingual corpus | Deferred; regional-language glossary terms only |
| Agentic multi-hop retrieval | FUTURE |

RAG is a **should-have** for the MVP: the vertical slice must work without it, and the
system degrades to "documentation context unavailable" rather than failing
(`22_MVP_SCOPE.md`).
