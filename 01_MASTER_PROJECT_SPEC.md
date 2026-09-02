# ORCA — Master Project Specification

**Project:** ORCA — Ocean Reasoning & Collaborative Agents
**SIH Problem Statement:** SIH26176
**Organisation:** ISRO
**Track:** Software
**Domain:** Space Technology / Marine Ecosystem Monitoring / AI Reasoning / Disaster Management
**Document:** 01 of 30
**Version:** 1.0
**Date:** 2026-09-02
**Status:** Design baseline — implementation not yet started

> **Terminology note.** Earlier project material expanded ORCA as *"Marine EcOsystem
> Reasoning with Collaborative Agents"*. The canonical expansion for this documentation
> set is **Ocean Reasoning & Collaborative Agents**. Both refer to the same system.

---

## 1. Executive Summary

India already operates world-class authoritative marine information systems. INCOIS
publishes Potential Fishing Zone advisories, ocean state forecasts and oceanographic
datasets; IMD issues marine weather, cyclone and lightning warnings; ISRO/MOSDAC
distributes satellite ocean products; CMEMS, Argo and other international programmes
provide complementary global coverage.

The gap is **not** data production. The gap is that a fisher, a harbour operator, a
district disaster officer or a marine researcher must independently locate, open,
interpret and mentally cross-correlate several separate portals — each with its own
projection, vocabulary, update cadence, spatial footprint and validity window — and
then reconcile them into a single situational judgement, under time pressure, often in
a language the portals do not speak.

**ORCA is an integration and reasoning layer over those authoritative systems.** It
accepts a natural-language marine question, decomposes it into a retrieval and analysis
plan, calls capability-level tools that wrap each authoritative source, normalises every
returned value into a canonical provenance-carrying representation, aligns everything
spatially and temporally, reasons about it across four *separately maintained* domains
(marine safety, fishing suitability, ecological condition, regulatory constraint), and
returns an evidence-backed conversational answer with a map, explicit uncertainty and a
citation for every material claim.

```
   Existing authoritative marine information systems
   (INCOIS · IMD · MOSDAC/ISRO · CMEMS · Argo · MarineRegions)
                          │
                 ORCA integration layer
                 (source adapters → canonical schema)
                          │
                  capability-oriented tools
                          │
              multi-agent reasoning (LangGraph)
                          │
             evidence-backed conversational answer
```

**ORCA does not replace INCOIS, IMD, ISRO or any official advisory.** It cites them.
Where an official advisory exists, ORCA surfaces it as the authoritative statement and
labels its own synthesis as a derived, non-official interpretation.

---

## 2. Problem Definition

### 2.1 The operational problem

A coastal fisher preparing to sail tomorrow morning needs to know, simultaneously:

| Question | Authoritative holder | Format |
|---|---|---|
| Is there an active fishermen's warning? | IMD | Bulletin text |
| Is a cyclone or squall developing? | IMD | Track / cone products |
| Will lightning occur? | IMD | Lightning products |
| How high will the waves and swell be? | INCOIS OSF / CMEMS | Gridded forecast |
| Which way will the current push the boat? | INCOIS / CMEMS | Gridded forecast |
| Where is fish likely to aggregate? | INCOIS PFZ | Advisory / map layer |
| Is the water anomalously warm? | INCOIS ERDDAP / MOSDAC | Gridded satellite product |
| Is productivity elevated there? | INCOIS ERDDAP (chlorophyll) | Gridded satellite product |
| Is that location inside the EEZ or a restricted area? | Boundary datasets | Vector geometry |

Each answer lives in a different system, at a different resolution, valid over a
different time window, expressed in a different vocabulary, and none of them answers the
actual question that was asked: *"Is tomorrow morning a good time to go fishing, and if
not, why?"*

### 2.2 The technical problem

Turning those nine heterogeneous answers into one defensible answer requires:

1. **Intent understanding** — mapping colloquial, often multilingual, phrasing to a
   formal information need.
2. **Task decomposition** — deciding *which* sources are actually needed for *this*
   question, not retrieving everything blindly.
3. **Autonomous discovery and retrieval** across services with different protocols
   (ERDDAP griddap/tableDAP, OGC WMS, REST JSON, authenticated download APIs).
4. **Normalisation** into one internal representation that can carry both point
   observations and gridded fields, with units, CRS, validity time and quality.
5. **Spatial–temporal alignment** — a 4 km daily satellite composite, a 1/12° 3-hourly
   forecast and a text bulletin covering a named sea area are not directly comparable.
6. **Uncertainty and conflict handling** — sources disagree; some are stale; some are
   unreachable; some require credentials.
7. **Domain-separated reasoning** — high fishing potential and unsafe sea state can be
   true at the same time and must not be averaged into one number.
8. **Explainability** — the user must be able to see *why*, tracing each claim to a
   source, dataset, retrieval time and validity time.

That chain is the ORCA system.

---

## 3. SIH Alignment

| SIH SIH26176 requirement | ORCA response | Primary artifact |
|---|---|---|
| Conversational interaction over heterogeneous marine information | Conversation API + session state + multi-turn context carry-over | `08_API_SPEC.md`, `02_FRONTEND_DESIGN_SPEC.md` |
| Intent detection | `intent_context` graph node; intent taxonomy | `07_LANGGRAPH_WORKFLOW_SPEC.md` |
| Task decomposition | Planner Agent produces an explicit typed plan | `06_AGENT_SPEC.md` |
| Specialised AI agents | 5 agents with disjoint responsibilities | `06_AGENT_SPEC.md` |
| Autonomous data discovery / retrieval / integration | Data Discovery Agent + source adapters + capability tools | `03`, `04`, `06` |
| Spatial–temporal reasoning | Geospatial Analysis Agent; deterministic geo/temporal kernel | `11_GEOSPATIAL_REASONING_SPEC.md` |
| Evidence-backed recommendations | Evidence assembly; claim↔evidence binding | `12_RISK_AND_RECOMMENDATION_SPEC.md` |
| Maps / charts / geospatial visualisation | Map surface with layer control, GeoJSON + raster tiles | `02`, `11` |
| Marine advisories | Advisory synthesis, explicitly labelled non-official | `12` |
| Multilingual, esp. Indian regional languages | Language detection, response-language preservation, terminology lexicon | `13_MULTILINGUAL_AND_ALERTING_SPEC.md` |
| Proactive alerts | Alert engine over subscriptions + geofences | `13` |
| Geofencing | PostGIS geofence evaluation | `11`, `13` |
| Route / safety reasoning | Route corridor sampling (P1) over safety assessment | `11`, `12` |
| Explainability | Provenance-first architecture; evidence panel; run trace | `05`, `20` |
| Modular multi-agent architecture | LangGraph state machine, typed state, isolated tools | `07` |

The full requirement→artifact→test→demo trace is maintained in
`27_REQUIREMENTS_TRACEABILITY_MATRIX.md`.

---

## 4. Target Stakeholders

| Stakeholder | Primary need | ORCA surface |
|---|---|---|
| Coastal / small-vessel fishers | "Is it safe? Is it worth going? Where?" | Mobile conversational view, regional language, PFZ + safety map |
| Fishing cooperatives / boat owners | Fleet-level daily go/no-go, advisory dissemination | Alerts, geofenced subscriptions, shareable advisory cards |
| Harbour / port operators | Sea-state and warning awareness for departures | Desktop operations view, temporal control |
| District / state disaster management officers | Cyclone, warning and exposure context | Warning-first view, human review workflow |
| Marine researchers & students | Cross-source data pulls with provenance | Evidence panel, dataset references, export |
| INCOIS / ISRO analysts | Consistency checking across products, conflict detection | Conflict view, source matrix, audit trail |
| Policy / fisheries administration | Regulatory boundary awareness, aggregated queries | Regulatory assessment, boundary layers |

Fishers are the **primary** stakeholder for the MVP vertical slice; the disaster-officer
role drives the human-review design.

---

## 5. Goals

**G1** Accept a natural-language marine question and return an answer grounded in
authoritative sources, with per-claim provenance.

**G2** Never expose provider-specific APIs, URLs, auth or query syntax to the reasoning
layer; all access flows through capability tools backed by source adapters.

**G3** Represent all retrieved marine data in a single canonical schema capable of
carrying point observations, gridded fields, vector geometry and warning bulletins.

**G4** Keep marine safety, fishing suitability, ecological condition and regulatory
constraint as four separate assessments that are reported separately even when they
disagree.

**G5** Make every failure mode explicit and observable: unavailable source,
authentication required, missing data, stale data, insufficient coverage, conflicting
sources, raster-only availability.

**G6** Support multi-turn conversation with retained spatial/temporal context.

**G7** Support Indian regional languages for both input and output, with response
language preserved from the user's input language.

**G8** Support proactive, geofenced alerts derived from the same tool and assessment
layer as interactive queries.

**G9** Make it possible to reconstruct, after the fact, *why* a recommendation was
produced — from raw source response to final sentence — without exposing model
chain-of-thought.

**G10** Support human review and override for high-impact outputs, with the override
recorded in provenance and audit.

---

## 6. Non-Goals

**NG1** ORCA is **not** a replacement for INCOIS, IMD, MOSDAC or any official advisory
service, and does not issue official advisories.

**NG2** ORCA is not a navigation system. Its boundary and route outputs are advisory
context, not navigational authority, and are not a substitute for official nautical
charts or Notices to Mariners.

**NG3** ORCA does not build new ocean forecast models. It consumes authoritative model
and observation products. Any derived indicator is labelled as derived.

**NG4** ORCA does not claim to eliminate model hallucination. It constrains generation
to retrieved evidence and makes ungrounded claims detectable.

**NG5** ORCA does not perform real-time vessel tracking or surveillance in the MVP.

**NG6** ORCA does not assert legal or regulatory determinations. Boundary and
restricted-area outputs carry source, version and jurisdiction and are advisory.

**NG7** ORCA does not expose model chain-of-thought to users.

---

## 7. Use Cases

### UC-1 — Pre-departure fishing decision (MVP primary)
A fisher near Kochi asks whether tomorrow morning is suitable. ORCA returns separate
safety and fishing-suitability verdicts, a map with PFZ/SST/chlorophyll context, the
governing warnings, and the evidence behind each statement.

### UC-2 — Warning interpretation
"What does the current warning for my area actually mean for a 9 m boat?" ORCA retrieves
the active warning verbatim, cites it, and contextualises it with wave/wind forecasts
without restating it as its own advisory.

### UC-3 — Cyclone situational awareness
A district officer asks for the current cyclone position, forecast track and which
coastal segments fall inside the forecast cone within 48 h. High-impact output → human
review gate.

### UC-4 — Ocean condition explanation
A researcher asks why chlorophyll is elevated off a coastal stretch this week. ORCA
retrieves chlorophyll and SST fields, computes anomalies deterministically, and reports
the observed pattern plus candidate explanations drawn from RAG over scientific
documentation, clearly separated from observation.

### UC-5 — Regulatory / boundary check
"Am I inside the Indian EEZ at 8.1 N, 74.2 E?" ORCA evaluates the point against boundary
geometry and returns the answer with dataset version, jurisdiction and an explicit
advisory disclaimer.

### UC-6 — Proactive geofenced alert
A cooperative registers a fishing ground polygon. When a marine warning or a safety
threshold breach intersects it, ORCA pushes an alert with the triggering evidence.

### UC-7 — Multilingual interaction
The same query is asked in Malayalam; the answer is returned in Malayalam with technical
terms rendered per the marine terminology lexicon and units unchanged.

### UC-8 — Route corridor safety (P1)
"Kochi to Lakshadweep on Thursday — where is it roughest?" ORCA samples the corridor,
evaluates safety at each sample, and highlights the worst segments.

---

## 8. Representative Queries

```
EN  "I'm near Kochi. Is tomorrow morning a good time to go fishing, and if not, why?"
EN  "Is there any warning in force for the Kerala coast right now?"
EN  "Show me sea surface temperature anomaly off Visakhapatnam for the last week."
EN  "Where is chlorophyll highest within 80 km of Mangalore today?"
EN  "Is 8.1N 74.2E inside the Indian EEZ?"
EN  "How rough will it be between Chennai and Port Blair on Friday?"          (P1)
ML  "നാളെ രാവിലെ കൊച്ചിക്ക് അടുത്ത് മീൻ പിടിക്കാൻ പോകാമോ?"
HI  "क्या कल सुबह समुद्र में जाना सुरक्षित है?"
TA  "இன்று சென்னை கடலில் அலை உயரம் எவ்வளவு?"
```

Each representative query is bound to a test case in `15_EVALUATION_AND_TESTING_SPEC.md`.

---

## 9. System Capabilities

| # | Capability | MVP | Notes |
|---|---|---|---|
| C1 | Natural-language marine query understanding | ✅ | intent + entity + context resolution |
| C2 | Location resolution (named place, coordinates, "near me", prior turn) | ✅ | gazetteer + geocoding cache |
| C3 | Time-window resolution ("tomorrow morning", "last week") | ✅ | deterministic, timezone-aware (IST) |
| C4 | Plan generation and tool selection | ✅ | Planner Agent |
| C5 | Parallel multi-source retrieval | ✅ | fan-out over capability tools |
| C6 | Canonical normalisation + provenance capture | ✅ | every value |
| C7 | Spatial/temporal alignment & anomaly computation | ✅ | deterministic kernel |
| C8 | Marine safety assessment | ✅ | rule-based, evidence-bound |
| C9 | Fishing suitability assessment | ✅ | rule-based, evidence-bound |
| C10 | Ecological condition assessment | ⬜ P1 | indicators |
| C11 | Regulatory / boundary assessment | ✅ | point/polygon evaluation |
| C12 | Conflict detection between sources | ✅ | retained, not resolved silently |
| C13 | Evidence assembly + claim binding | ✅ | |
| C14 | Map + layer visualisation | ✅ | vector + raster |
| C15 | RAG over marine/scientific documentation | ⬜ Should-have | `10_RAG_SPEC.md` |
| C16 | Multilingual I/O | ⬜ Should-have (2 languages) | `13` |
| C17 | Proactive geofenced alerts | ⬜ Should-have (prototype) | `13` |
| C18 | Human review / override | ⬜ Should-have | `07`, `12` |
| C19 | Route corridor reasoning | ⬜ Deferred | P1 |
| C20 | Run trace / audit reconstruction | ✅ | `20` |

---

## 10. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          CLIENT (React + MapLibre)                       │
│   conversation │ map │ evidence panel │ layers │ time control │ alerts   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ REST + WebSocket (streamed run events)
┌───────────────────────────────▼──────────────────────────────────────────┐
│                        API LAYER (FastAPI)                               │
│   sessions │ queries │ runs │ evidence │ map data │ alerts │ health      │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────────┐
│                  ORCHESTRATION LAYER (LangGraph)                         │
│   typed state · nodes · conditional routing · retries · interrupts       │
│   Planner · Data Discovery · Geospatial · Risk · Reporting               │
└───────────────┬───────────────────────────────┬──────────────────────────┘
                │                               │
┌───────────────▼──────────────┐   ┌────────────▼───────────────────────┐
│   CAPABILITY TOOL LAYER      │   │  DETERMINISTIC KERNELS             │
│   11 P0 tools, typed schemas │   │  geospatial · temporal · scoring   │
└───────────────┬──────────────┘   └────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────────┐
│   SOURCE ADAPTER LAYER  (auth · query construction · parsing · retry)    │
│   ERDDAP │ IMD │ WMS │ CMEMS │ MarineRegions │ MOSDAC │ NOAA │ Argo      │
└───────────────┬──────────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────────┐
│   AUTHORITATIVE EXTERNAL SOURCES                                         │
└──────────────────────────────────────────────────────────────────────────┘

        PERSISTENCE: PostgreSQL + PostGIS + pgvector │ Redis │ S3/MinIO
        OBSERVABILITY: structured logs · OpenTelemetry traces · audit log
```

Full diagram set: `23_ARCHITECTURE_DIAGRAMS.md`.

### 10.1 Layer responsibilities (strict)

| Layer | Knows about | Must NOT know about |
|---|---|---|
| Agents | capability tool names + schemas, canonical objects | URLs, credentials, ERDDAP/WMS syntax, provider schemas |
| Capability tools | canonical schema, adapter interface, fallback policy | HTTP details of any specific provider |
| Source adapters | one provider's protocol, auth, quirks | ORCA reasoning, assessment logic |
| Deterministic kernels | numbers, geometry, time | LLMs, providers |

---

## 11. Agent Architecture

Five agents, disjoint responsibilities, defined fully in `06_AGENT_SPEC.md`.

| Agent | Nature | Core responsibility |
|---|---|---|
| **Planner Agent** | LLM-driven, schema-constrained | Decompose the resolved query into a typed retrieval/analysis plan; select capability tools; re-plan on validation failure |
| **Data Discovery Agent** | Deterministic orchestration + narrow LLM use | Execute the plan against capability tools, handle fallback, record failure states, assemble the normalised dataset |
| **Geospatial Analysis Agent** | Deterministic kernel + LLM summary | CRS handling, subsetting, masking, interpolation, alignment, anomalies, geofence and boundary evaluation |
| **Risk Assessment Agent** | Rule engine + LLM explanation | Produce four independent domain assessments with evidence references, confidence and uncertainty |
| **Reporting Agent** | LLM generation, evidence-constrained | Compose the user-facing answer, bind claims to evidence, apply language and role formatting |

**Why five and not one.** Each agent has a different failure mode, a different validation
gate and a different determinism profile. Collapsing them removes the ability to validate
retrieval independently of reasoning, to re-plan without re-generating text, or to gate
only the high-impact stage for human review. Additional agents are *not* added for
appearance; anything that is deterministic is a kernel, not an agent.

---

## 12. Data Architecture

```
Source  →  Source Adapter  →  Normalized Data Object  →  Capability Tool  →  Agent
```

**Source adapter** — the only component that holds provider knowledge: base URLs, auth,
rate limits, dataset identifiers, query construction (ERDDAP griddap/tableDAP selectors,
OGC WMS/WFS parameters, REST paths), response parsing (JSON/CSV/NetCDF/GeoTIFF/GML),
retry and circuit-breaker behaviour, and provider-specific error → canonical error code
mapping.

**Normalized data object** — a canonical object (`Observation`, `Forecast`,
`MarineWarning`, `OceanField`, `RasterRef`, `VectorFeature`) carrying unit, CRS,
valid_time, retrieved_at, source, dataset, resolution, quality and `value_kind`.

**Capability tool** — a stable, provider-independent contract (`get_sst`,
`get_wave_conditions`, …) that selects among adapters, applies fallback policy, records
which source actually served the request, and returns an `OrcaEnvelope`.

**Agent** — sees only capability tools and canonical objects.

Source registry: `03_DATA_SOURCE_MATRIX.md`. Tool contracts: `04_ORCA_TOOL_CONTRACTS.md`.
Schema: `05_CANONICAL_DATA_SCHEMA.md`.

### 12.1 Verified data foundation

The data-source audit established (see `03` and `25`):

- **INCOIS ERDDAP — VERIFIED.** DNS, TCP, TLS with valid certificate, HTTP 200, catalogue
  accessible and exposing active datasets including `incois_oceansat2_datasets`
  (CHL, KD490, TSM), the `incois_argo_*` family, `NOAA_AVHRR_AMSR_datasets` (SST and SST
  anomaly) and `ascat_daily_datasets` (wind). ERDDAP is therefore the confirmed
  programmatic ocean-data backbone. Exact dataset selection and query construction remain
  adapter concerns and must not be hard-coded into agents.
- **IMD — AUTH REQUIRED.** Endpoint reachable; unauthenticated request returned HTTP 403.
  This is an authentication requirement, **not** evidence of unavailability. Anonymous
  access must not be claimed.
- **INCOIS GeoServer / WMS — PENDING VERIFICATION.** Public WMS capabilities and
  PFZ/SST/Chl-related layers were identified in the audit, but independent verification
  was blocked because the test network could not resolve `services.incois.gov.in`
  (`curl` reported "Could not resolve host"). The endpoint must **not** be labelled
  broken, and no architectural path may depend exclusively on it.
- **CMEMS — AUTH REQUIRED.** Public site reachable; programmatic access and credentials
  handled in the adapter. Intended primary for waves/currents and fallback for SST/Chl.
- **MarineRegions — CONFIRMED reachable.** Initial source for EEZ/maritime boundaries;
  not the legal authority for every boundary type.
- **MOSDAC — AUTH REQUIRED.** Enhancement source; must not block the MVP.
- **INCOIS OSF/LAS — NO MACHINE INTERFACE ESTABLISHED.** Human-facing services
  identified; no clean public machine-readable interface was established in the audit.
  CMEMS covers the corresponding wave/ocean forecast need.

---

## 13. Reasoning Architecture

ORCA separates five kinds of statement and never blurs them:

| Kind | Produced by | Example |
|---|---|---|
| **Source observation** | adapter, `value_kind: observed` | "Argo profile at 9.2 N 75.8 E, 2026-09-01, 28.6 °C at 5 m" |
| **Source forecast** | adapter, `value_kind: forecast` | "CMEMS Hs 2.4 m valid 2026-09-03T06Z" |
| **Derived metric** | deterministic kernel, `value_kind: derived` | "SST anomaly +1.2 °C vs 10-day mean" |
| **Model prediction** | ML component, `value_kind: model` | (none in MVP) |
| **Agent interpretation** | LLM, `value_kind: interpretation` | "Sea state is marginal for small craft" |
| **Recommendation** | Risk + Reporting | "Safety: UNFAVOURABLE. Fishing: FAVOURABLE." |

### 13.1 Four independent assessment domains

```
             ┌──────────────────────────────────────────────┐
  evidence → │ SAFETY              wind, waves, swell,      │ → verdict + confidence
             │                     lightning, cyclone,      │
             │                     official warnings        │
             ├──────────────────────────────────────────────┤
  evidence → │ FISHING_SUITABILITY PFZ, SST, SST anomaly,   │ → verdict + confidence
             │                     chlorophyll, fronts      │
             ├──────────────────────────────────────────────┤
  evidence → │ ECOLOGICAL          indicators, anomalies,   │ → status + confidence
             │                     HAB-related signals (P1) │
             ├──────────────────────────────────────────────┤
  evidence → │ REGULATORY          EEZ, MPA, restricted,    │ → status + confidence
             │                     operational boundaries   │
             └──────────────────────────────────────────────┘
                              ↓
                    combined narrative, NOT a single score
```

A location may be simultaneously **FAVOURABLE** for fishing and **UNSAFE** to reach.
ORCA must state that explicitly. Collapsing the domains into one "risk score" destroys
the information the user actually needs. Details and thresholds:
`12_RISK_AND_RECOMMENDATION_SPEC.md`.

### 13.2 Deterministic vs generative boundary

| Deterministic (no LLM) | Generative (LLM) |
|---|---|
| Location/time resolution, unit conversion, CRS transforms, subsetting, masking, interpolation, anomaly computation, geofence tests, threshold evaluation, conflict detection, staleness checks, provenance construction | Intent classification, plan generation (schema-constrained), disambiguation questions, evidence-grounded narrative, reasoning summary, translation |

Every number a user sees is produced deterministically. The LLM chooses *what to fetch*
and *how to say it*, never *what the value is*.

---

## 14. Provenance Architecture

Every material value carries a `Provenance` record capable of representing: parameter,
value, unit, location, valid_time, source, dataset, retrieved_at, spatial_resolution,
temporal_resolution, quality, source/product reference, and `value_kind`
(observed | forecast | derived | model | interpretation).

Derived values additionally carry `derivation`: the input provenance IDs, the method
identifier, the method version and its parameters — so any derived number can be
recomputed.

```
raw source response ──(adapter)──> normalized object + Provenance
                                        │
                    ┌───────────────────┼───────────────────┐
             geospatial derivation   assessment          citation
             (inputs + method)      (evidence refs)      (claim binding)
                    └───────────────────┼───────────────────┘
                                        ▼
                            answer sentence ── cites ──> Evidence ──> Provenance
```

The final answer is only allowed to contain material claims that resolve to at least one
`Evidence` item. Unresolvable claims are flagged by the evidence-binding validator; see
`15_EVALUATION_AND_TESTING_SPEC.md` §Provenance correctness.

**Terminology.** ORCA claims *source-grounded generation*, *evidence-backed synthesis*,
*provenance-aware reasoning*, *claim/evidence association* and *uncertainty-aware
output*. It does **not** claim "hallucination-free AI".

---

## 15. Human-in-the-Loop Design

Human review is applied where it changes outcomes, not everywhere.

| Disposition | Condition | Behaviour |
|---|---|---|
| `AUTO_RELEASE` | All required evidence present, no domain verdict is UNSAFE, no unresolved material conflict, confidence ≥ threshold, data not stale beyond policy | Answer returned directly |
| `REVIEW_REQUIRED` | Any of: UNSAFE safety verdict in an operational role context; unresolved CONFLICTING_SOURCES on a safety-relevant variable; confidence below threshold; a governing official warning could not be retrieved; alert fan-out above configured size | Graph interrupts at `human_review`; reviewer approves / edits / rejects |
| `BLOCKED` | Insufficient evidence to make any safety statement, or a hard policy violation | No recommendation issued; ORCA states what is missing |

Overrides are first-class: an override record stores reviewer identity, timestamp,
original assessment, modified assessment, free-text rationale, and is attached to the run
provenance and audit log. The delivered answer indicates that it was human-reviewed.
Auto-generated alerts of severity ≥ configured level follow the same gate.

---

## 16. Multilingual Strategy

- **Detection** — deterministic script/language detection on the input, with an LLM
  fallback for ambiguous romanised input; detected language is stored on the session.
- **Preservation** — the response is generated in the user's input language unless the
  session explicitly overrides it. A language switch mid-conversation is honoured.
- **Pivot architecture** — reasoning and evidence remain in a canonical English internal
  representation; only the final narrative is produced in the target language, from the
  same evidence set, so that translation cannot alter numeric content.
- **Terminology** — a curated marine terminology lexicon (per language) fixes the
  rendering of PFZ, significant wave height, swell, warning classes, place names and
  units. Numbers, units and place coordinates are never translated.
- **Targets** — MVP: English + one Indic language (Malayalam or Hindi, chosen by demo
  region). Roadmap: Tamil, Telugu, Marathi, Odia, Gujarati, Bengali, Kannada.
- **Quality claims** — no translation-quality claim is made without the evaluation
  defined in `13_MULTILINGUAL_AND_ALERTING_SPEC.md` §Evaluation. Untested language pairs
  are labelled PROPOSED.
- **Audio/TTS** — designed but FUTURE; specified as an interface, not a promise.

---

## 17. Alerting Strategy

Alerts reuse the same tools, canonical schema and assessment logic as interactive
queries — they are a scheduled evaluation of a stored subscription, not a parallel code
path.

```
subscription (geofence + role + thresholds + language)
        ↓  scheduler
evaluate assessments over geofence
        ↓
severity classification → deduplicate (fingerprint + cooldown)
        ↓
review gate if severity ≥ threshold
        ↓
channel abstraction (in-app · web push · SMS · email) — pluggable
```

Severity: `INFO | ADVISORY | WATCH | WARNING | CRITICAL`. An alert derived from an
official IMD/INCOIS warning quotes and cites it; an alert derived from ORCA's own
threshold evaluation is explicitly labelled derived. Deduplication, rate limiting and
quiet hours are mandatory; see `13`.

---

## 18. Geospatial Strategy

- **CRS** — EPSG:4326 is the canonical internal CRS; EPSG:3857 only for tiles. Every
  geometry carries its CRS explicitly; transforms are `pyproj`-based and logged.
- **Deterministic kernel** — all subsetting, masking, resampling, interpolation, spatial
  joins, distance/area computation (on an equal-area or geodesic basis, never on raw
  degrees), anomaly computation and geofence tests are pure functions with unit tests.
- **Raster vs vector honesty** — if only a rendered WMS raster is available for PFZ, the
  result is `RASTER_ONLY` and downstream output is labelled raster-derived. ORCA never
  manufactures vector PFZ polygons from imagery or from SST/chlorophyll alone.
- **Alignment** — all fields are aligned to an explicit analysis grid and analysis time
  window; the alignment method and any interpolation are recorded as derivation metadata.
- **Boundaries** — boundary geometry always carries source, dataset version, jurisdiction
  and effective date; outputs are advisory.
- **Visualisation** — vector layers as GeoJSON (RFC 7946, lon/lat order, right-hand rule);
  raster layers as tiles or referenced imagery with an explicit legend and units.

Full specification: `11_GEOSPATIAL_REASONING_SPEC.md`.

---

## 19. Security and Privacy Considerations

- Credential material for IMD, CMEMS and MOSDAC lives only in a secrets manager,
  injected as environment configuration into adapters; never in source, never in logs,
  never in model context.
- Authentication for ORCA users via signed tokens; RBAC roles `fisher`, `operator`,
  `officer`, `analyst`, `reviewer`, `admin` gate review, override and alert-broadcast
  actions.
- Prompt-injection defence: all retrieved content (bulletin text, RAG documents, dataset
  metadata) is treated as **data, not instructions**; tool arguments are schema-validated
  before execution; tools are allow-listed per agent.
- Location data is personal data. Precise user positions are minimised, retention-bounded
  and never forwarded to third-party services beyond what a query requires.
- Audit logs are append-only and cover queries, tool executions, fallbacks, reviews and
  overrides.
- Applicable Indian frameworks (including the Digital Personal Data Protection Act, 2023,
  CERT-In directions, and any ISRO/INCOIS data-use terms) are recorded as
  **considerations requiring legal and organisational confirmation** — no compliance
  claim is made in this documentation set.

Full treatment: `14_SECURITY_PRIVACY_AND_GOVERNANCE.md`.

---

## 20. Assumptions

| ID | Assumption | Status |
|---|---|---|
| A1 | INCOIS ERDDAP remains publicly accessible with the observed datasets | VERIFIED at audit time; monitor |
| A2 | IMD API access can be obtained through registration | AUTH REQUIRED — unconfirmed grant |
| A3 | INCOIS GeoServer/WMS is reachable from an unrestricted network | PENDING VERIFICATION |
| A4 | CMEMS credentials can be obtained for the team | AUTH REQUIRED |
| A5 | MarineRegions EEZ geometry is adequate as an initial boundary source | CONFIRMED for advisory use only |
| A6 | A tool-calling capable LLM is available with acceptable latency | PROPOSED |
| A7 | Demo network permits outbound HTTPS to all P0 sources | PENDING VERIFICATION |
| A8 | Cached/pre-staged data is acceptable for demo fallback if it is labelled | Accepted design decision |

Every assumption is tracked in `25_GAP_AND_VALIDATION_REGISTER.md`.

---

## 21. Constraints

- **C-1** No source may be accessed outside its terms of use; authenticated sources
  require credentials that the team must obtain.
- **C-2** The development network (college campus) cannot resolve some government hosts;
  verification of those endpoints must occur on an unrestricted network.
- **C-3** Interactive query latency budget: p50 ≤ 8 s, p95 ≤ 20 s for a full multi-source
  run (initial engineering target, requires validation).
- **C-4** Satellite ocean-colour and SST products have intrinsic latency (hours to a day)
  and cloud gaps; ORCA cannot present them as real-time.
- **C-5** Team capacity and SIH timeline require an MVP vertical slice, not the full
  system, before evaluation.
- **C-6** No fabricated data may be shown in any demonstration; pre-staged cached data is
  permitted only when visibly labelled as cached with its retrieval time.

---

## 22. Risks (summary)

| Risk | Impact | Primary mitigation |
|---|---|---|
| IMD credentials not granted in time | Loss of warnings/cyclone/lightning | Explicit `AUTH_REQUIRED` degradation; CMEMS/NOAA meteorological fallback for wind; demo shows honest degradation |
| WMS endpoint unverifiable | PFZ layer unavailable | PFZ path designed with raster/vector/absent branches; no exclusive dependency |
| Source disagreement | Wrong recommendation | Conflict retained and surfaced; safety-relevant conflicts escalate |
| Scientific thresholds unvalidated | Misleading advice | All thresholds labelled SCIENTIFIC VALIDATION REQUIRED; verdicts carry confidence |
| Ungrounded generation | Credibility loss | Evidence binding validator; ungrounded claims blocked |
| Demo network failure | Demo failure | Cached-run replay mode, clearly labelled |
| Scope creep | Nothing finished | MVP boundary in `22_MVP_SCOPE.md` is contractual |

Full register with likelihood, detection, owner and status:
`21_RISK_REGISTER.md`.

---

## 23. Phased Implementation Roadmap (summary)

| Phase | Content | Gate |
|---|---|---|
| 0 | Repo, config, CI, logging, DB skeleton | `make dev` runs; health endpoint green |
| 1 | Source adapters (ERDDAP first, then CMEMS, MarineRegions, IMD, WMS) | Live ERDDAP retrieval with recorded provenance |
| 2 | Canonical schema + validators | Round-trip tests pass for all object types |
| 3 | Capability tools (11 P0) | Contract tests + failure-state tests pass |
| 4 | Agents | Each agent independently testable with fixtures |
| 5 | LangGraph orchestration | End-to-end run on the Kochi query |
| 6 | Geospatial reasoning kernel | Deterministic geo tests pass |
| 7 | RAG | Retrieval + citation evaluation |
| 8 | Frontend | Conversation + map + evidence panel |
| 9 | Alerts + multilingual | Geofence alert fires; 2-language round trip |
| 10 | Evaluation | Test matrix executed and reported |
| 11 | Deployment + demo hardening | Rehearsed demo incl. failure and override paths |

Detail: `17_IMPLEMENTATION_ROADMAP.md`. MVP boundary: `22_MVP_SCOPE.md`.

---

## 24. Evaluation Strategy

Five evaluation axes, each with an owning document:

1. **Retrieval correctness** — adapters return what the source actually holds; unit,
   CRS, time and dataset identity are correct. (`15` §adapter tests)
2. **Geospatial/numerical correctness** — deterministic kernels validated against
   independently computed reference values and synthetic fixtures. (`11`, `15`)
3. **Reasoning correctness** — scenario matrix over safety/fishing/ecology/regulatory,
   including cases where domains disagree. (`12`, `15`)
4. **Grounding correctness** — every material claim resolves to evidence; injected
   unsupported claims are detected. (`10`, `15`)
5. **Operational correctness** — failure states, fallbacks, latency, review gates,
   multilingual round-trips. (`13`, `15`, `20`)

No benchmark numbers are asserted anywhere in this documentation set. Any figure carried
over from earlier material is labelled PROPOSED until independently reproduced.

---

## 25. Success Criteria

**MVP success (must all hold):**

- S1 A single natural-language query triggers a Planner-generated plan invoking ≥ 5
  distinct P0 capability tools against ≥ 3 distinct external sources.
- S2 Every value in the answer resolves to a `Provenance` record with source, dataset,
  valid_time and retrieved_at.
- S3 Safety and fishing suitability are reported as separate verdicts, and a scenario in
  which they disagree is demonstrated.
- S4 At least one source failure (`AUTH_REQUIRED` or `SOURCE_UNAVAILABLE`) is handled
  visibly, with the fallback or degradation stated in the answer.
- S5 A map renders the retrieved spatial context with correct CRS and a legend.
- S6 The full run is reconstructible from the audit trail without model chain-of-thought.
- S7 No claim in the answer is presented as an official government advisory unless it is
  a quoted official advisory.

**Stretch success:** RAG citations, one Indic language round-trip, one geofenced alert,
one human override recorded end-to-end.

---

## 26. Future Extensions

- Route optimisation with weather/current routing and boundary constraints.
- Vessel context integration (position, class, capability-aware thresholds).
- Historical comparison and seasonality analysis over multi-year archives.
- Ecological indicator suite and HAB-related signal monitoring (requires scientific
  validation and an authoritative feed).
- MOSDAC EO product integration as a cross-validation source against ERDDAP/CMEMS.
- Offline-tolerant mobile client for low-connectivity coastal use.
- Voice-first interaction with regional-language ASR/TTS.
- Cooperative-level dashboards and fleet advisories.
- Feedback loop capturing observed outcomes to validate suitability thresholds.

---

## 27. Document Set Index

| # | Document | Purpose |
|---|---|---|
| 01 | `01_MASTER_PROJECT_SPEC.md` | This document |
| 02 | `02_FRONTEND_DESIGN_SPEC.md` | Operational UI specification |
| 03 | `03_DATA_SOURCE_MATRIX.md` | Authoritative source registry |
| 04 | `04_ORCA_TOOL_CONTRACTS.md` | P0 capability tool contracts |
| 05 | `05_CANONICAL_DATA_SCHEMA.md` | Internal data model |
| 06 | `06_AGENT_SPEC.md` | Agent definitions |
| 07 | `07_LANGGRAPH_WORKFLOW_SPEC.md` | Orchestration graph |
| 08 | `08_API_SPEC.md` | Backend API |
| 09 | `09_DATABASE_SPEC.md` | Persistence |
| 10 | `10_RAG_SPEC.md` | Scientific-document RAG |
| 11 | `11_GEOSPATIAL_REASONING_SPEC.md` | Geospatial kernel |
| 12 | `12_RISK_AND_RECOMMENDATION_SPEC.md` | Assessment framework |
| 13 | `13_MULTILINGUAL_AND_ALERTING_SPEC.md` | Language + alerts |
| 14 | `14_SECURITY_PRIVACY_AND_GOVERNANCE.md` | Security posture |
| 15 | `15_EVALUATION_AND_TESTING_SPEC.md` | Test framework |
| 16 | `16_DEMO_AND_SIH_PRESENTATION_SPEC.md` | Demo design |
| 17 | `17_IMPLEMENTATION_ROADMAP.md` | Phased plan |
| 18 | `18_REPOSITORY_STRUCTURE.md` | Repo layout |
| 19 | `19_ENVIRONMENT_AND_CONFIGURATION_SPEC.md` | Config + secrets |
| 20 | `20_OBSERVABILITY_AND_AUDIT_SPEC.md` | Logs, traces, audit |
| 21 | `21_RISK_REGISTER.md` | Engineering risks |
| 22 | `22_MVP_SCOPE.md` | MVP boundary |
| 23 | `23_ARCHITECTURE_DIAGRAMS.md` | Diagram set |
| 24 | `24_ENGINEERING_DECISIONS.md` | ADRs |
| 25 | `25_GAP_AND_VALIDATION_REGISTER.md` | Known gaps |
| 26 | `26_SIH_JUDGE_QA.md` | Judge Q&A |
| 27 | `27_REQUIREMENTS_TRACEABILITY_MATRIX.md` | Requirement trace |
| 28 | `28_GLOSSARY.md` | Terminology |
| 29 | `29_QUICKSTART.md` | Developer onboarding |
| 30 | `30_DEFINITION_OF_DONE.md` | Completion criteria |
| — | `DOCUMENTATION_AUDIT.md` | Cross-document audit |
