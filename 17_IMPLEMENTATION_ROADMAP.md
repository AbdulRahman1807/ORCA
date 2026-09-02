# ORCA — Implementation Roadmap

**Document:** 17 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** PROPOSED — Phase 0 not yet started

---

## 1. Sequencing Principle

Phases are ordered so that **the riskiest unknowns are resolved earliest** and so that a
demonstrable vertical slice exists as early as possible.

```
Phase 0  foundation ─────────────┐
Phase 1  adapters ───────────────┤  ← the two highest-risk phases
Phase 2  canonical schema        │     (external dependency + credentials)
Phase 3  capability tools        │
Phase 4  agents                  │
Phase 5  LangGraph  ◀════════════╧═══ MVP VERTICAL SLICE COMPLETE HERE
Phase 6  geospatial reasoning
Phase 7  RAG
Phase 8  frontend        ◀═══════════ DEMONSTRABLE PRODUCT
Phase 9  alerts + multilingual
Phase 10 evaluation
Phase 11 deployment + demo hardening
```

**The MVP does not require all eleven phases.** A working, honest, demonstrable ORCA
exists after Phase 8 (with Phase 6 partially complete). Phases 9–11 harden and extend it.
See `22_MVP_SCOPE.md`.

Phases 2 and 3 partly overlap Phase 1 (schema is designed against the first real adapter
response, not before it). Phase 6 begins during Phase 3 because tools need point
extraction immediately.

---

## Phase 0 — Foundation

**Objectives.** A repository that runs, tests, lints and logs from day one.

**Dependencies.** None.

**Deliverables**
- Repository structure per `18_REPOSITORY_STRUCTURE.md`
- Python 3.11 project (dependency + lock management), `Makefile` targets
- Docker Compose: PostgreSQL 16 + PostGIS + pgvector, Redis, MinIO
- Alembic baseline migration (extensions + core tables)
- FastAPI skeleton with `/v1/health`
- Structured logging with run/trace correlation; OpenTelemetry wiring
- Configuration loader with environment layering (`19_ENVIRONMENT_AND_CONFIGURATION_SPEC.md`)
- CI: format, lint, type-check, unit tests, secret scanning
- `LLMProvider` abstraction with a stub implementation

**Acceptance criteria**
- `make dev` brings the stack up; `/v1/health` returns `200` with all dependencies `ok`
- `make test` passes on an empty suite; CI green on a PR
- Secret scanner blocks a deliberately committed dummy credential
- No credential exists in the repository

**Risks.** Environment drift across team machines → pinned Compose + lockfiles.
**Fallback.** Local PostgreSQL/Redis without Docker, documented in `29_QUICKSTART.md`.

---

## Phase 1 — Source Adapters

**Objectives.** Reach real data, and convert every verification unknown into a recorded
fact.

**Dependencies.** Phase 0.

**Deliverables (in build order)**
1. **INCOIS ERDDAP adapter** (S-01…S-04) — **VERIFIED source, build first**
   - griddap/tableDAP query construction, response parsing (CSV/JSON/NetCDF)
   - **Dataset metadata capture** into the `datasets` table: variable names, units,
     coordinate conventions, grid spacing, time step, fill values, valid ranges
     (closes verification backlog V-1, `03_DATA_SOURCE_MATRIX.md` §11)
2. **MarineRegions loader** (S-08) — versioned PostGIS snapshot + spatial index
3. **CMEMS adapter** (S-07) — credential acquisition, product identification, subsetting
4. **IMD adapter** (S-05) — built against the documented contract; **must function in
   `AUTH_REQUIRED` mode from day one**, so the degradation path is real, not theoretical
5. **INCOIS WMS adapter** (S-06) — after network-independent verification (V-2); implements
   all three branches (vector / `RASTER_ONLY` / unavailable)
6. Adapter test harness: cassette recording, replay, golden query strings

**Acceptance criteria**
- A live ERDDAP retrieval returns parsed values with complete provenance
- `datasets` rows populated with **read**, not assumed, metadata for every P0 dataset
- MarineRegions point-in-polygon returns correct containment with dataset version
- IMD adapter returns `AUTH_REQUIRED` cleanly without credentials; a credentialed test
  exists but is skipped when credentials are absent
- Every adapter maps 401/403/5xx/empty/rename to the correct canonical code
- No credential appears in logs or returned objects (asserted by test)
- Verification backlog items V-1…V-5 are either closed or explicitly re-recorded as open

**Risks**
| Risk | Mitigation |
|---|---|
| IMD credentials not granted | Adapter works in `AUTH_REQUIRED` mode; wind falls back; warnings degrade explicitly |
| WMS still unverifiable | Three-branch design; PFZ never a blocking dependency |
| CMEMS credentials delayed | ERDDAP-backed tools carry the MVP; waves/currents deferred within the slice |
| ERDDAP dataset changes | Startup dataset check + `DATASET_UNAVAILABLE`; nightly smoke test |

**Fallback.** The MVP slice is defined so that it works with **ERDDAP + MarineRegions
alone**, degrading everything else explicitly.

---

## Phase 2 — Canonical Schema

**Objectives.** One internal representation, validated everywhere.

**Dependencies.** Phase 1 (schema is finalised against real responses).

**Deliverables**
- Pydantic v2 models for every type in `05_CANONICAL_DATA_SCHEMA.md`
- Canonical variable registry and unit conversion table
- Error taxonomy with legacy→canonical mapping
- JSON Schema export to `docs/schemas/`
- Validation at adapter output, tool return, state write and API serialisation
- Round-trip and negative tests for every type

**Acceptance criteria**
- Round-trip tests pass for all types
- An object missing `provenance_id`, `crs` or `unit` is rejected
- A grid array cannot be serialised inline beyond the configured cell cap
- Frontend types are generated from the exported schemas

**Risks.** Over-engineering before real data is understood.
**Mitigation.** Schema work follows the first two adapters, not precedes them.
**Fallback.** Schema versioning allows a `1.1` iteration without breaking stored runs.

---

## Phase 3 — Capability Tools

**Objectives.** Eleven stable, provider-independent contracts.

**Dependencies.** Phases 1–2.

**Deliverables**
- 11 P0 tools per `04_ORCA_TOOL_CONTRACTS.md`
- Tool registry with per-environment enablement (a disabled tool cannot be planned)
- Fallback policy engine (permitted codes only; never on `AUTH_REQUIRED`)
- Redis response cache with per-parameter TTL; `retrieved_at` preserved
- Conflict detection for cross-checked parameters
- Contract tests including every failure state

**Acceptance criteria**
- Every tool returns a valid `OrcaEnvelope` for success, partial, empty and error cases
- `get_wave_conditions` with no wave source fails rather than substituting another variable
- `get_pfz` raster branch disables spatial predicates
- Fallback usage is recorded and retrievable
- `NO_ACTIVE_WARNING` is `status: "empty"` with provenance, not an error

**Risks.** Tool logic drifting into provider specifics.
**Mitigation.** A lint rule/test asserts that no HTTP client or URL literal appears outside
`adapters/`.
**Fallback.** Tools backed by unavailable sources ship in permanent degradation mode.

---

## Phase 4 — Agents

**Objectives.** Five agents, independently testable.

**Dependencies.** Phase 3.

**Deliverables**
- Planner (schema-constrained plan output; deterministic domain/tool tables)
- Data Discovery (execution, widening rules, conflict emission, retrieval report)
- Geospatial Analysis (orchestrating Phase 6 kernels)
- Risk Assessment (deterministic rule engine + bounded rationale)
- Reporting (evidence-constrained generation + validators + template fallback)
- Prompt templates, versioned; `temperature = 0`
- Per-agent test suites with fixtures (`06_AGENT_SPEC.md` §10)

**Acceptance criteria**
- Planner minimality test passes (warning lookup plans one tool)
- Risk Agent produces disagreeing verdicts in the designed scenario
- An adversarial rationale cannot change a verdict (mutation test)
- Reporting rejects an unbound claim and falls back to a template after two failures
- Each agent runs standalone from fixtures without a graph

**Risks.** LLM non-determinism in planning.
**Mitigation.** Temperature 0, schema constraints, deterministic tables for domain/tool
mapping, plan-diff tests.
**Fallback.** A deterministic rule-based planner for the fixed demo intents, used only if
LLM planning proves unstable — recorded as a documented degradation.

---

## Phase 5 — LangGraph Orchestration  ◀ **MVP vertical slice completes here**

**Objectives.** The end-to-end reasoning workflow.

**Dependencies.** Phase 4.

**Deliverables**
- `OrcaGraphState` with reducers
- All nodes and conditional routing per `07_LANGGRAPH_WORKFLOW_SPEC.md`
- `Send`-based fan-out for retrieval and assessment
- Validation gate, bounded re-plan, error handler
- PostgreSQL checkpointer; run persistence into `runs`/`tool_executions`/`provenance`
- Human-review interrupt node (API surface may lag)
- Node event stream

**Acceptance criteria**
- The Kochi query runs end-to-end and produces separate SAFETY and FISHING assessments
- One tool failure does not stall the fan-in
- Total failure produces no verdict
- Re-plan fires once and is bounded
- Interrupt/resume survives a process restart
- The full run is reconstructible from the database
- No chain-of-thought is persisted anywhere

**Risks.** Fan-in stalls on a failed branch; state reducer conflicts.
**Mitigation.** Branch guard (a failed domain still appends an assessment); append-only
reducers for all parallel-written fields.
**Fallback.** Sequential execution mode behind a flag (slower, same semantics).

---

## Phase 6 — Geospatial Reasoning

**Objectives.** Correct, reproducible spatial and temporal computation.
*(Starts during Phase 3; completes here.)*

**Dependencies.** Phases 2–3.

**Deliverables**
- CRS normalisation, geodesic bbox/distance/area
- Subsetting, masking, coverage, resampling, point extraction
- Temporal alignment with representativeness rules
- Anomaly computation with explicit baseline
- Geometry predicates, geofence evaluation, boundary handling
- Layer descriptor and GeoJSON/tile generation
- Reference tests for every method (`11_GEOSPATIAL_REASONING_SPEC.md` §17)

**Acceptance criteria**
- Every derivation has a reference test and a registered method version
- A monthly product is refused for a 4-hour safety window
- A raster predicate raises `VECTOR_UNAVAILABLE`
- Masked cells never contribute as zeros
- Geodesic bbox correct at multiple latitudes

**Risks.** Silent CRS/axis-order errors — the classic geospatial failure.
**Mitigation.** Explicit CRS everywhere, round-trip tests, adapter-level axis-order
assertions.
**Fallback.** Nearest-node only (no interpolation) — less precise, always correct, and
labelled.

---

## Phase 7 — RAG

**Objectives.** Cited documentation context.

**Dependencies.** Phases 0, 2. Independent of Phases 4–6.

**Deliverables**
- Curated corpus manifest; ingestion pipeline; chunking; embeddings
- pgvector + tsvector hybrid retrieval with RRF; filters; reranking
- `search_marine_knowledge` tool; citation objects; claim attribution
- Evaluation set (≥ 50 questions for the MVP) and CI gates

**Acceptance criteria**
- Quote fidelity 100 %; ungrounded material claims 0 on the evaluation set
- Insufficient retrieval produces a decline, not a guess
- Superseded documents excluded from default retrieval
- RAG cannot alter a verdict (structural test)
- Injection corpus produces no instruction-following

**Risks.** Licence uncertainty; corpus effort underestimated.
**Mitigation.** Manifest-driven ingestion with a licence field; start with 30 documents.
**Fallback.** RAG disabled by flag; ORCA reports "documentation context unavailable" —
the MVP does not depend on it.

---

## Phase 8 — Frontend  ◀ **demonstrable product**

**Objectives.** The operational conversational interface.

**Dependencies.** Phase 5 (+ Phase 6 for layers).

**Deliverables**
- React + TypeScript app; generated API types
- Conversation pane with streamed run progress
- MapLibre map: layers, legends, freshness/source/representation badges, time scrubber
- Assessment cards; evidence panel (L1/L2/L3); conflict view
- Official-warning presentation distinct from ORCA synthesis
- Loading/error/empty states for every canonical code
- Mobile layout; accessibility baseline

**Acceptance criteria**
- The Kochi query is answerable from the UI with map and evidence
- Unavailable layers are listed with reasons, not hidden
- A claim resolves to a provenance record and a derivation chain in ≤ 2 clicks
- Every severity/verdict/freshness state has an icon and text label
- Mobile: verdict visible without scrolling
- No chain-of-thought reaches the client (asserted in the event-stream test)

**Risks.** Frontend scope creep; map performance with large geometries.
**Mitigation.** Component inventory is fixed in `02_FRONTEND_DESIGN_SPEC.md` §22;
display simplification + tiling.
**Fallback.** Desktop-only for the demo; mobile layout deferred.

---

## Phase 9 — Alerts and Multilingual

**Objectives.** Proactive delivery and regional-language interaction.

**Dependencies.** Phases 5, 8.

**Deliverables**
- Geofence storage/editor; subscriptions; scheduler
- Trigger evaluation, severity classification, deduplication, rate limiting, quiet hours
- Channel abstraction with `in_app` (+ `web_push` if time permits)
- Alert review gate for ORCA-derived `WARNING`/`CRITICAL`
- Language detection; pivot generation; terminology lexicon for one Indic language
- Four automated language hard gates

**Acceptance criteria**
- A geofenced alert fires on a real threshold breach with evidence attached
- Duplicate suppression verified by fingerprint
- An ORCA-derived warning cannot be dispatched un-reviewed
- Malayalam/Hindi round-trip passes all four hard gates
- Native-speaker review recorded before the language is enabled

**Risks.** Terminology quality; alert spam; SMS regulatory/cost issues.
**Mitigation.** Lexicon review gate; conservative cooldowns; SMS deferred.
**Fallback.** In-app alerts only; English + one language.

---

## Phase 10 — Evaluation

**Objectives.** Measure, don't claim.

**Dependencies.** Phases 5–9.

**Deliverables**
- Scenario matrix from `15_EVALUATION_AND_TESTING_SPEC.md` §15 as executable YAML
- Failure-injection suite; latency benchmarks; provenance-correctness suite
- Baseline metrics recorded in `evaluation/baselines/`
- First execution report in `evaluation/reports/<date>/`

**Acceptance criteria**
- All normal, edge, failure and high-risk cases execute and pass
- Baselines recorded; regression gates active in CI
- **Every number used in any presentation traces to a report artifact**

**Risks.** Evaluation deferred until it is too late to act on results.
**Mitigation.** The scenario matrix is written during Phase 4 and run continuously from
Phase 5.
**Fallback.** A reduced but honest matrix, with unexecuted cases explicitly listed.

---

## Phase 11 — Deployment and Demo Hardening

**Objectives.** A demo that cannot fail dishonestly.

**Dependencies.** All previous.

**Deliverables**
- Deployment configuration (compose or single-node orchestration), TLS, secrets
- Backup + restore rehearsal
- Offline replay mode with a permanent "recorded" banner
- Demo dataset pre-staging, labelled as cached with retrieval times
- Dashboards: source health, run latency, fallback rate, review queue
- Rehearsed demo per `16_DEMO_AND_SIH_PRESENTATION_SPEC.md`
- Final documentation pass and gap-register update

**Acceptance criteria**
- Five full rehearsals, one in replay mode, one with a deliberately failing source
- Restore from backup verified
- No unlabelled cached data anywhere in the demo path
- Gap register current as of the submission date

**Risks.** Venue network; last-minute changes.
**Mitigation.** Feature freeze 72 h before; replay mode; recorded video backup.
**Fallback.** Recorded video, clearly labelled as a recording.

---

## 2. Critical Path and Parallelism

```
P0 ──▶ P1 ──▶ P2 ──▶ P3 ──▶ P4 ──▶ P5 ──▶ P8 ──▶ P11        ← critical path
        │             └────▶ P6 ──┘        │
        │                                  ├──▶ P9
        └──────────────────▶ P7 ───────────┘
                                    P10 runs continuously from P5
```

| Can proceed in parallel | With |
|---|---|
| P7 (RAG) | P3–P6 — different data, different people |
| P8 (frontend shell + map) | P4–P5, against fixture responses |
| P10 (scenario authoring) | P4 onward |
| Credential acquisition (IMD, CMEMS, MOSDAC) | **Start on day 1 of Phase 0** — lead time is the risk, not effort |

**Day-one actions regardless of phase:** start IMD registration, start CMEMS registration,
start MOSDAC registration, and run the WMS verification from an unrestricted network.
These are lead-time items; nothing about the code schedule changes them.

---

## 3. Phase Gate Summary

| Phase | Gate that must be green to proceed |
|---|---|
| 0 | Stack runs; CI green; secret scanning active |
| 1 | Live ERDDAP retrieval with full provenance; dataset metadata captured |
| 2 | Round-trip validation for every schema type |
| 3 | All 11 tools return valid envelopes incl. failure states |
| 4 | Each agent passes its suite standalone |
| 5 | End-to-end run with separated assessments and full persistence |
| 6 | Every derivation has a reference test |
| 7 | RAG hard gates pass |
| 8 | UI answers the Kochi query with map and evidence |
| 9 | Alert fires with evidence; language hard gates pass |
| 10 | Scenario matrix executed; baselines recorded |
| 11 | Rehearsals complete; replay mode verified |

---

## 4. Explicit Non-Requirements for the MVP

The following are **not** required before a demonstrable ORCA exists:

route optimisation · vessel context · MOSDAC integration · historical comparison ·
ecological indicators · HAB signalling · TTS/ASR · SMS/email channels · more than two
languages · every P0 tool live (degradation is acceptable and demonstrated) · a fully
validated threshold set (validation status is displayed instead) · offline mobile ·
multi-tenant deployment.

Attempting these before Phase 8 is the single most likely cause of project failure
(`21_RISK_REGISTER.md` R-16).
