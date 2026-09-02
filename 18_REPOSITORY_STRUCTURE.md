# ORCA — Repository Structure

**Document:** 18 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** PROPOSED — IMPLEMENTATION REQUIRED

---

## 1. Organising Principle

The directory tree **is** the architecture. The layering rule from
`01_MASTER_PROJECT_SPEC.md` §10.1 is enforced by import boundaries, not by convention:

```
agents/      may import  tools/, schemas/, geospatial/, assessment/
tools/       may import  adapters/, schemas/, geospatial/
adapters/    may import  schemas/  and nothing else from ORCA
geospatial/  may import  schemas/  only
assessment/  may import  schemas/  only
```

**Enforced rules (CI-checked):**
- No HTTP client, URL literal or credential reference outside `adapters/`.
- `agents/` never imports `adapters/`.
- `geospatial/` and `assessment/` never import an LLM client.
- `schemas/` imports nothing from ORCA.

An import-linter configuration expresses these as contracts; violating one fails the build.
This is what keeps "the Planner must not know API URLs" from decaying into a comment.

---

## 2. Top-Level Tree

```
orca/
├── README.md
├── LICENSE
├── Makefile
├── docker-compose.yml
├── docker-compose.demo.yml
├── .env.example                     ← never .env
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml
├── uv.lock            (or poetry.lock)
├── importlinter.ini                 ← layering contracts
│
├── backend/
├── frontend/
├── config/
├── data/
├── docs/
├── evaluation/
├── scripts/
├── deployment/
└── tests/
```

---

## 3. Backend

```
backend/
├── orca/
│   ├── __init__.py
│   ├── main.py                       FastAPI application factory
│   ├── settings.py                   layered configuration (19_ENVIRONMENT…)
│   │
│   ├── api/                          ── HTTP/WS surface only
│   │   ├── deps.py                   auth, RBAC, pagination dependencies
│   │   ├── errors.py                 canonical code → HTTP mapping
│   │   ├── ws.py                     run event streaming
│   │   └── v1/
│   │       ├── health.py  sessions.py  queries.py  runs.py
│   │       ├── evidence.py  geo.py  alerts.py  review.py  registry.py
│   │
│   ├── schemas/                      ── canonical data model (05)
│   │   ├── envelope.py  spatial.py  temporal.py  provenance.py
│   │   ├── quality.py  uncertainty.py
│   │   ├── observation.py  forecast.py  warning.py  field.py
│   │   ├── raster.py  vector.py  derived.py
│   │   ├── assessment.py  conflict.py  evidence.py  recommendation.py
│   │   ├── errors.py                 canonical error taxonomy
│   │   ├── variables.py              canonical variable + unit registry
│   │   └── api/                      request/response models
│   │
│   ├── adapters/                     ── THE ONLY PLACE WITH PROVIDER KNOWLEDGE
│   │   ├── base.py                   SourceAdapter protocol, retry, breaker
│   │   ├── http.py                   shared client, timeouts, TLS, redaction
│   │   ├── errors.py                 provider error → canonical code mapping
│   │   ├── incois_erddap/            S-01…S-04  (VERIFIED)
│   │   │   ├── adapter.py  queries.py  parsing.py  datasets.py
│   │   ├── imd/                      S-05       (AUTH REQUIRED)
│   │   ├── incois_wms/               S-06       (PENDING VERIFICATION)
│   │   ├── cmems/                    S-07       (AUTH REQUIRED)
│   │   ├── marineregions/            S-08
│   │   ├── mosdac/                   S-09       (AUTH REQUIRED, P1)
│   │   ├── noaa/                     S-11       (PROPOSED)
│   │   └── argo_gdac/                S-12       (PROPOSED)
│   │
│   ├── tools/                        ── capability contracts (04)
│   │   ├── registry.py               per-environment enablement + agent allow-lists
│   │   ├── base.py                   envelope construction, validation, caching
│   │   ├── fallback.py               permitted-code fallback policy
│   │   ├── conflict.py               cross-source conflict detection
│   │   ├── get_weather.py  get_marine_warnings.py  get_cyclone_track.py
│   │   ├── get_lightning.py  get_pfz.py  get_sst.py  get_chlorophyll.py
│   │   ├── get_wave_conditions.py  get_currents.py  get_ocean_observations.py
│   │   ├── get_maritime_boundaries.py
│   │   └── p1/                       search_marine_knowledge.py, get_route_advisory.py …
│   │
│   ├── geospatial/                   ── deterministic kernel (11)
│   │   ├── crs.py  bbox.py  distance.py
│   │   ├── fields.py                 subset, mask, resample, extract, statistics
│   │   ├── interpolation.py  temporal.py  anomaly.py
│   │   ├── geometry.py  geofence.py  boundaries.py
│   │   ├── corridor.py               P1
│   │   ├── layers.py                 layer descriptors, GeoJSON, tiles
│   │   └── methods.py                method id + version registry
│   │
│   ├── assessment/                   ── deterministic rule engine (12)
│   │   ├── domains/ safety.py  fishing.py  ecological.py  regulatory.py
│   │   ├── thresholds.py             loads config/thresholds/*.yaml
│   │   ├── sufficiency.py  confidence.py  conflict_policy.py
│   │   ├── synthesis.py              limiting factor + headline pattern
│   │   └── escalation.py             disposition computation
│   │
│   ├── agents/                       ── judgement layer (06)
│   │   ├── base.py                   budgets, validation, provenance helpers
│   │   ├── planner.py  discovery.py  geospatial_agent.py
│   │   ├── risk.py  reporting.py
│   │   ├── validators/               grounding, numeric fidelity, official-language guard
│   │   └── prompts/                  versioned templates, one directory per agent
│   │
│   ├── graph/                        ── orchestration (07)
│   │   ├── state.py                  OrcaGraphState + reducers
│   │   ├── build.py                  graph assembly
│   │   ├── nodes/                    one module per node
│   │   ├── routing.py                conditional edge functions
│   │   ├── checkpoint.py             PostgreSQL checkpointer wiring
│   │   └── events.py                 node event emission
│   │
│   ├── rag/                          ── document retrieval (10)
│   │   ├── ingest/ fetch.py parse.py chunk.py embed.py index.py
│   │   ├── retrieve/ dense.py lexical.py fusion.py rerank.py filters.py
│   │   ├── citations.py  attribution.py
│   │   └── corpus_manifest.yaml
│   │
│   ├── alerts/                       ── proactive delivery (13B)
│   │   ├── scheduler.py  triggers.py  severity.py  dedupe.py
│   │   ├── channels/ base.py in_app.py web_push.py sms.py email.py
│   │   └── review.py
│   │
│   ├── i18n/                         ── language (13A)
│   │   ├── detect.py  generate.py  gates.py
│   │   └── terms/ en.yaml ml.yaml hi.yaml …
│   │
│   ├── llm/                          ── provider abstraction
│   │   ├── provider.py               LLMProvider protocol
│   │   ├── providers/                one module per provider
│   │   └── usage.py                  token/cost accounting
│   │
│   ├── db/
│   │   ├── models.py  session.py  repositories/  migrations/ (alembic)
│   │
│   ├── storage/  objects.py  cache.py
│   └── observability/  logging.py  tracing.py  metrics.py  audit.py
│
└── pyproject.toml
```

### 3.1 Ownership of key directories

| Directory | Owns | Must not contain |
|---|---|---|
| `adapters/` | All provider knowledge: URLs, auth, query syntax, parsing, provider error mapping | Reasoning, thresholds, LLM calls |
| `tools/` | Capability contracts, fallback policy, caching, envelope construction | HTTP clients, provider URLs |
| `geospatial/` | Every number derived from spatial/temporal data | LLM calls, thresholds, verdicts |
| `assessment/` | Threshold evaluation, verdicts, confidence, escalation | LLM calls, data retrieval |
| `agents/` | Judgement, prompts, output validation | Provider knowledge, numeric computation |
| `graph/` | Control flow, state, checkpoints | Business rules |
| `schemas/` | The canonical model, imported by everything | Any ORCA import |

**The two most important boundaries:** `agents/` cannot import `adapters/` (the Planner
cannot learn about URLs), and `assessment/` cannot import `llm/` (a model cannot change a
verdict). Both are CI-enforced.

---

## 4. Frontend

```
frontend/
├── src/
│   ├── app/            routes, layout shell, providers
│   ├── api/            generated types (from docs/schemas/), client, WS hook
│   ├── components/
│   │   ├── conversation/  ConversationPane QueryInput ContextChips RunProgress
│   │   │                  AnswerNarrative CitationChip ReasoningSummary RunStrip
│   │   ├── assessment/    AssessmentCard VerdictBadge ConfidenceIndicator
│   │   ├── map/           MapCanvas LayerControl MapLegend TimeScrubber
│   │   │                  FeatureInspector
│   │   ├── evidence/      EvidencePanel EvidenceRecord DerivationView ConflictView
│   │   ├── warnings/      OfficialWarningCard SeverityBadge
│   │   ├── alerts/        AlertInbox AlertDetail GeofenceEditor
│   │   ├── review/        ReviewQueue ReviewDetail
│   │   └── common/        FreshnessDot SourceBadge EmptyState ErrorState
│   ├── i18n/           locale files; Indic font stacks
│   ├── hooks/  stores/  styles/  utils/
├── public/
├── tests/              component + e2e (Playwright)
└── package.json
```

**Frontend rules.** No scientific computation, no threshold logic, no direct calls to
external sources. Types are generated from the backend's exported JSON Schemas so the
frontend cannot drift from the canonical model.

---

## 5. Configuration

```
config/
├── sources.yaml             registry projection: ids, roles, statuses, attribution
│                            (endpoints live in environment config, never here)
├── datasets.yaml            dataset ids + captured metadata (written by Phase 1)
├── tools.yaml               per-environment tool enablement + agent allow-lists
├── thresholds/
│   ├── small_craft_v0.1.yaml       status: SCIENTIFIC_VALIDATION_REQUIRED
│   └── fishing_v0.1.yaml           status: SCIENTIFIC_VALIDATION_REQUIRED
├── staleness.yaml           per-parameter cadence and staleness policy
├── tolerances.yaml          per-parameter conflict tolerances
├── alerts.yaml              severity mapping, cooldowns, rate limits
├── i18n.yaml                enabled languages + gate configuration
└── feature_flags.yaml
```

**No secrets in `config/`.** Configuration describes *policy*; environment variables carry
*credentials* (`19_ENVIRONMENT_AND_CONFIGURATION_SPEC.md`).

---

## 6. Data, Docs, Evaluation, Scripts, Deployment

```
data/
├── boundaries/          versioned MarineRegions snapshots (git-ignored; loader script)
├── gazetteer/           coastal place names → coordinates (reviewed, in-repo)
├── landmask/            coarse land mask for validation
└── demo/                pre-staged demo fixtures, each with capture metadata

docs/
├── 01_MASTER_PROJECT_SPEC.md … 30_DEFINITION_OF_DONE.md
├── DOCUMENTATION_AUDIT.md
├── schemas/             generated JSON Schema artifacts
└── adr/                 ADR entries (mirrors 24_ENGINEERING_DECISIONS.md)

evaluation/
├── scenarios/           the §15 test matrix as YAML
├── rag/                 questions + gold passages
├── i18n/                per-language sets + review records
├── baselines/           first measured metrics
└── reports/{date}/      executed results — the ONLY place numbers may be asserted

scripts/
├── load_boundaries.py       MarineRegions → PostGIS with version
├── capture_datasets.py      ERDDAP metadata → config/datasets.yaml + datasets table
├── verify_sources.py        connectivity/auth probe; updates operational status
├── record_fixtures.py       capture upstream responses for tests
├── ingest_corpus.py         RAG ingestion
├── seed_demo.py             pre-stage demo data (writes capture metadata)
└── replay_run.py            offline demo replay from checkpoints

deployment/
├── docker/                  Dockerfile.backend, Dockerfile.frontend
├── compose/                 dev, staging, demo overlays
├── k8s/                     optional manifests
├── nginx/                   TLS termination, rate limiting
└── observability/           dashboards, alert rules
```

`data/demo/` fixtures carry a `capture.json` with source, dataset, retrieval time and a
`pre_staged: true` flag, so the UI can label them. A demo fixture without capture metadata
fails a CI check — this is the mechanism that prevents unlabelled cached data reaching a
demo.

---

## 7. Tests

```
tests/
├── unit/            schemas/ geospatial/ assessment/ i18n/ utils/
├── adapters/        one directory per source + cassettes/
├── tools/           contract tests per capability tool
├── agents/          per-agent tests with fixtures
├── graph/           workflow, routing, interrupt/resume, failure injection
├── api/             endpoint + auth + rate-limit tests
├── rag/             retrieval + citation + injection tests
├── security/        secret scanning, redaction, injection, authorisation
├── e2e/             full scenarios against recorded upstreams
├── fixtures/
│   ├── upstream/{source_id}/    recorded provider responses + capture dates
│   ├── canonical/               canonical objects for downstream tests
│   └── scenarios/               end-to-end scenario inputs
└── conftest.py
```

**Fixture rule.** Files under `fixtures/upstream/` are recorded from live sources and
carry capture metadata. Hand-authored upstream fixtures are prohibited — they would make
the adapter suite test a fiction.

---

## 8. Makefile Targets

```
make dev             docker compose up + migrations + seed
make api             run the backend with reload
make web             run the frontend
make test            full suite
make test-unit       fast suite
make test-live       live smoke against VERIFIED sources (non-blocking)
make lint            format + lint + type-check + import-linter
make schemas         export JSON Schema → docs/schemas/ and regenerate frontend types
make eval            run the evaluation harness → evaluation/reports/<date>/
make verify-sources  connectivity/auth probe → updated operational status
make demo            demo compose overlay + pre-staged fixtures
make replay RUN=…    offline replay of a recorded run
```

---

## 9. Repository Conventions

| Convention | Rule |
|---|---|
| Naming | Tools, schema fields, error codes and node names match the documentation set **exactly** — a rename requires updating the docs in the same PR |
| Docstrings | Every adapter module records its source id, terms-of-use reference and audit status |
| Status markers | `# STATUS: IMPLEMENTATION REQUIRED` / `SCIENTIFIC VALIDATION REQUIRED` comments mirror the documentation labels |
| Commits | Conventional commits; a PR touching a tool contract must update `04_ORCA_TOOL_CONTRACTS.md` |
| Secrets | `.env.example` only; `.env` git-ignored; pre-commit secret scan |
| Generated files | `docs/schemas/` and frontend types are generated, never hand-edited |
| Dependencies | Pinned and locked; additions justified in the PR description |
