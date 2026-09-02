# ORCA — Agent Specification

**Document:** 06 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Design defined — IMPLEMENTATION REQUIRED

---

## 1. Agent Philosophy

ORCA has **five** agents. The count is a consequence of the work, not a target.

An ORCA agent exists only where a stage requires **judgement under uncertainty** —
choosing what to retrieve, deciding whether evidence is sufficient, or expressing a
conclusion in language. Everything that can be computed is computed by a **deterministic
kernel**, not by an agent.

```
                     ┌──────────────────────────────────────────┐
                     │   Where judgement is required → AGENT     │
                     │   Where computation suffices  → KERNEL    │
                     └──────────────────────────────────────────┘
```

Two consequences:

1. **No agent produces a number a user sees.** Numbers come from adapters (source values)
   or kernels (derived values). Agents select, assess against explicit rules, and narrate.
2. **No agent is added for architectural appearance.** Alignment, anomaly computation,
   point-in-polygon, unit conversion, staleness checks and threshold evaluation are
   kernel functions with unit tests — not "agents".

| Agent | Judgement it makes | Determinism profile |
|---|---|---|
| Planner | *What information does this question actually need?* | LLM, schema-constrained output |
| Data Discovery | *Did we get what the plan asked for, and what do we do about the gaps?* | Deterministic orchestration; narrow LLM use for adaptive re-request |
| Geospatial Analysis | *Are these datasets comparable, and how?* | Deterministic kernel + LLM summary only |
| Risk Assessment | *What do these facts mean for safety / fishing / ecology / regulation?* | Deterministic rule engine + LLM explanation |
| Reporting | *How do I say this truthfully, in the user's language, with citations?* | LLM, evidence-constrained |

---

## 2. Shared Agent Contract

Every agent:

| Requirement | Rule |
|---|---|
| Input | A typed slice of `OrcaGraphState` (`07_LANGGRAPH_WORKFLOW_SPEC.md` §State) |
| Output | A typed object validated against `05_CANONICAL_DATA_SCHEMA.md` before it is written to state |
| Tools | Only tools in its explicit allow-list. Tool access is enforced at the registry, not by prompt instruction |
| Provenance | Any value it emits carries `value_kind` and a `provenance_id`; LLM-authored statements are `interpretation` with the evidence IDs they were generated from |
| Untrusted content | All retrieved content (bulletin text, dataset metadata, RAG passages) is **data, not instructions**. Agents never follow directives found inside retrieved content |
| Chain-of-thought | Never written to state, never persisted, never returned to the client. Agents emit a short `reasoning_summary` instead |
| Failure | Agents return structured failure, never raise across the node boundary |
| Budget | Each agent has a token, wall-clock and tool-call budget; exceeding it is a structured failure, not a hang |
| Determinism | LLM calls use `temperature = 0` (or the provider's lowest) and a pinned prompt-template version recorded in the run trace |

---

## 3. Planner Agent

### 3.1 Purpose
Convert a resolved user query into an explicit, typed, executable plan.

### 3.2 Responsibilities
- Classify intent (`fishing_suitability`, `safety_check`, `warning_lookup`,
  `cyclone_status`, `ocean_condition`, `boundary_check`, `route_safety` (P1),
  `explanation`, `data_lookup`, `smalltalk_or_out_of_scope`).
- Decide **which** capability tools are required — and, equally, which are *not*.
- Specify each tool call's arguments from the resolved location and time context.
- Declare which assessment domains the answer requires.
- Declare the **required evidence set**: the facts without which the question cannot be
  answered honestly.
- Re-plan when validation reports missing or unusable evidence (bounded retries).
- Decide when the query is ambiguous enough to require a clarifying question rather than
  a guess.

### 3.3 Non-responsibilities
- Does **not** know source URLs, credentials, dataset IDs or query syntax.
- Does **not** retrieve data.
- Does **not** compute anything numeric.
- Does **not** assess risk or write the answer.
- Does **not** decide fallback sources — that is tool-layer policy.

### 3.4 Inputs
```
state.query_text, state.language, state.session_context,
state.resolved_location, state.resolved_time_window, state.intent (if pre-classified),
state.tool_registry (names + JSON schemas only),
state.validation_report (on re-plan), state.attempt
```

### 3.5 Output — `Plan`
```json
{
  "plan_id": "pl-01JBQ7",
  "intent": "fishing_suitability",
  "domains_required": ["SAFETY", "FISHING_SUITABILITY", "REGULATORY"],
  "steps": [
    {"step_id": "s1", "tool": "get_marine_warnings",
     "args": {"location": {"lat": 9.93, "lon": 76.26},
              "time_window": {"start_time": "2026-09-03T00:00:00Z",
                              "end_time": "2026-09-03T04:00:00Z"}},
     "necessity": "required", "domain": "SAFETY", "parallel_group": 1},
    {"step_id": "s2", "tool": "get_wave_conditions",
     "args": {"bbox": {"min_lat": 9.4, "min_lon": 75.8, "max_lat": 10.4, "max_lon": 76.7},
              "time_window": {"start_time": "2026-09-03T00:00:00Z",
                              "end_time": "2026-09-03T04:00:00Z"}},
     "necessity": "required", "domain": "SAFETY", "parallel_group": 1},
    {"step_id": "s6", "tool": "get_pfz",
     "args": {"location": {"lat": 9.93, "lon": 76.26}, "radius_km": 50,
              "valid_time": "2026-09-03T00:00:00Z"},
     "necessity": "preferred", "domain": "FISHING_SUITABILITY", "parallel_group": 1}
  ],
  "required_evidence": ["official_warning_status", "wave_conditions", "wind_conditions"],
  "preferred_evidence": ["pfz_advisory", "chlorophyll_a", "sst", "sst_anomaly", "currents"],
  "analysis": {"align_to": "point_and_window", "derivations": ["sst_anomaly", "current_speed"]},
  "clarification_needed": null,
  "reasoning_summary": "Fishing-suitability question near a named port for a morning window; "
                       "safety inputs are required, productivity inputs are preferred.",
  "plan_version": 1
}
```

`necessity` semantics: `required` — its absence blocks a confident verdict in that domain;
`preferred` — improves the answer; `optional` — context only.

### 3.6 Tools allowed
**None.** The Planner emits a plan; the Data Discovery Agent executes it. This keeps
planning cheap, testable and replayable.

### 3.7 Decision logic
```
intent = classify(query, session_context)

if location unresolved and not inferable from session:
        → clarification_needed = "location"
if time unresolved and intent is time-sensitive:
        → clarification_needed = "time_window"

domains  = DOMAIN_MAP[intent]                     # deterministic table
steps    = union over domains of REQUIRED_TOOLS[domain]
                                  ∩ available tool registry
                                  filtered by relevance to the query
required_evidence = REQUIRED_EVIDENCE[domain]

group steps into parallel_groups by dependency (default: all independent → group 1)
```

`DOMAIN_MAP` and `REQUIRED_TOOLS` are **deterministic tables**, not model choices. The
LLM's judgement is applied to: intent classification, relevance filtering (e.g. omitting
`get_cyclone_track` when no cyclone context exists but retaining it in cyclone season
when a warning is present), argument construction (radius, window width) and
clarification decisions.

### 3.8 Failure handling and escalation
| Condition | Behaviour |
|---|---|
| Intent unclassifiable | `intent = "unknown"`, ask one clarifying question |
| Location/time unresolvable | `clarification_needed` — no tools are executed |
| Plan fails schema validation | Repair once with the validation error; then fail the run with `SCHEMA_VALIDATION_FAILED` |
| Re-plan requested by `validate` | Produce `plan_version + 1` addressing only the reported gaps; max 2 re-plans |
| Re-plan cannot fill a `required` evidence gap | Emit a *degraded* plan and mark the domain `INSUFFICIENT_EVIDENCE` |
| Tool absent from registry | Never planned. If a required capability is unavailable the plan records `unavailable_capabilities` |

### 3.9 Provenance requirements
The plan is persisted with `plan_id`, `plan_version`, model identifier, prompt-template
version and `reasoning_summary`. Prompts and raw model reasoning traces are **not**
persisted as user-facing artifacts.

### 3.10 Example execution
> "Is there any warning in force for the Kerala coast right now?"

```
intent            = warning_lookup
domains_required  = ["SAFETY"]
steps             = [get_marine_warnings(area="Kerala coast", window=now±0)]
required_evidence = ["official_warning_status"]
preferred         = []            ← no SST, no chlorophyll, no PFZ
reasoning_summary = "Direct official-warning lookup; ocean variables are not required."
```
This is the Planner earning its place: nine tools exist, one is used.

---

## 4. Data Discovery Agent

### 4.1 Purpose
Execute the plan against capability tools, obtain the best available evidence, and report
precisely what was and was not obtained.

### 4.2 Responsibilities
- Execute plan steps with the declared concurrency, respecting per-tool timeouts and the
  global run budget.
- Apply tool-layer fallback policy and record `source_resolution` for every call.
- Normalise nothing itself (tools return canonical objects) but **verify** that every
  returned object validates and carries provenance.
- Deduplicate identical requests within a run (cache-aware).
- Classify each step outcome: `satisfied`, `degraded`, `empty`, `failed`.
- Detect cross-source disagreement where the plan requested cross-checking and emit
  `Conflict` objects.
- Decide, within a bounded budget, whether to widen a request (larger radius, wider time
  window, coarser product) when a step returns `NO_DATA` or `INSUFFICIENT_COVERAGE` — and
  record the widening as an explicit modification of the plan.
- Produce the `RetrievalReport` consumed by `validate`.

### 4.3 Non-responsibilities
- Does not choose which capabilities are needed (Planner).
- Does not know provider details (adapters).
- Does not interpret scientific meaning (Risk).
- Does not silently substitute a different variable or source. Widening is allowed and
  recorded; substitution is not.

### 4.4 Inputs
```
state.plan, state.tool_registry, state.budget, state.cache_context
```

### 4.5 Output — `RetrievalReport`
```json
{
  "report_id": "rr-01JBQ7",
  "plan_id": "pl-01JBQ7",
  "results": [
    {"step_id": "s1", "tool": "get_marine_warnings", "outcome": "empty",
     "codes": ["NO_ACTIVE_WARNING"], "envelope_ref": "env-01", "duration_ms": 612},
    {"step_id": "s2", "tool": "get_wave_conditions", "outcome": "satisfied",
     "codes": [], "envelope_ref": "env-02", "duration_ms": 1904},
    {"step_id": "s4", "tool": "get_lightning", "outcome": "failed",
     "codes": ["AUTH_REQUIRED"], "envelope_ref": "env-04", "duration_ms": 180},
    {"step_id": "s6", "tool": "get_pfz", "outcome": "degraded",
     "codes": ["RASTER_ONLY"], "envelope_ref": "env-06", "duration_ms": 2110}
  ],
  "modifications": [
    {"step_id": "s7", "change": "radius_km 50 → 100",
     "reason": "NO_DATA at 50 km due to cloud masking", "applied_at": "…"}
  ],
  "evidence_coverage": {
    "required_satisfied": ["official_warning_status", "wave_conditions"],
    "required_missing": ["wind_conditions"],
    "preferred_missing": ["lightning"]
  },
  "conflicts": ["cf-002"],
  "fallbacks_used": [{"step_id": "s3", "primary": "S-05", "actual": "S-11",
                      "reason": "SOURCE_UNAVAILABLE"}],
  "duration_ms": 3120
}
```

### 4.6 Tools allowed
All P0 capability tools present in the environment's registry — and nothing else.

### 4.7 Decision logic (deterministic core)
```
for group in plan.parallel_groups:
    run steps concurrently (bounded by MAX_CONCURRENT_TOOLS)
    for each step:
        envelope = tool(**args)
        outcome  = classify(envelope.status, envelope.errors)
        if outcome in {empty, degraded} and step.necessity == "required"
           and widening_budget_remains and widening_is_defensible(step, codes):
               retry once with a widened argument set, record the modification
```
`widening_is_defensible` is a table, not a model call: `NO_DATA` on a gridded ocean field
may widen radius or window; `AUTH_REQUIRED` may not widen anything; a warning lookup may
never widen its area (a warning for a different area is a different warning).

**Narrow LLM use.** Only when a `required` step remains unsatisfied after deterministic
widening does the agent ask the model a single constrained question: *given these tool
schemas and this failure, is there a defensible alternative request within the same
capability?* The answer is a schema-constrained argument object; the agent validates it
before use, and any accepted change is recorded in `modifications`.

### 4.8 Failure handling and escalation
| Condition | Behaviour |
|---|---|
| Transient failure (`TIMEOUT`, `SOURCE_UNAVAILABLE`, `RATE_LIMITED`) | Tool-layer retry, then fallback, then record `failed` |
| `AUTH_REQUIRED` | No retry, no fallback; recorded as a capability gap with the source named |
| All steps in a domain fail | Domain flagged for `INSUFFICIENT_EVIDENCE`; run continues for other domains |
| Every step fails | `retrieval_total_failure` → the graph routes to `error_handler` and ORCA reports what it could not reach, with no verdict |
| Budget exhausted | Stops, reports partial coverage honestly |

### 4.9 Example execution
Kochi query: 9 steps dispatched, 6 satisfied, 1 empty (`NO_ACTIVE_WARNING` — a result),
1 degraded (`RASTER_ONLY` PFZ), 1 failed (`AUTH_REQUIRED` lightning), 1 fallback (wind via
NOAA), 1 conflict (Hs 2.4 vs 3.1 m). Total 3.1 s.

---

## 5. Geospatial Analysis Agent

### 5.1 Purpose
Make heterogeneous retrieved data **comparable**, and compute every spatial/temporal
derived quantity.

### 5.2 Responsibilities
- Verify and normalise CRS for every object; reject or transform mismatches.
- Define the **analysis frame**: target grid/point set, target valid time(s), and the
  interpolation rules used to reach it.
- Subset, mask (land, cloud, fill, quality flags) and resample fields.
- Extract point values from fields, recording method and node distance.
- Align products with different `representativeness` and refuse comparisons that are not
  defensible (a monthly analysis is not aligned to a 3-hour window; it is carried as
  context with its representativeness intact).
- Compute derivations: anomalies, current speed/direction, area statistics, gradients and
  fronts (P1), corridor sampling (P1).
- Evaluate geometry predicates: point-in-polygon, distance-to-boundary, geofence
  intersection.
- Produce map-ready layer descriptors (GeoJSON refs, raster tile refs, legends).
- Emit an `AlignmentReport` describing exactly what was aligned and what could not be.

### 5.3 Non-responsibilities
- Does not fetch data.
- Does not decide whether conditions are safe or productive.
- Does not write user-facing prose (it emits a short factual summary only).
- Does not perform geometry operations on a `RasterRef` — it returns
  `VECTOR_UNAVAILABLE` instead.

### 5.4 Inputs
```
state.normalized_data (canonical objects), state.plan.analysis,
state.resolved_location, state.resolved_time_window
```

### 5.5 Output — `AlignmentReport` + `DerivedResult[]`
```json
{
  "report_id": "al-01JBQ7",
  "analysis_frame": {
    "spatial": {"kind": "point", "crs": "EPSG:4326", "coordinates": [76.26, 9.93],
                "context_bbox": {"min_lat": 9.4, "min_lon": 75.8,
                                 "max_lat": 10.4, "max_lon": 76.7}},
    "temporal": {"valid_from": "2026-09-03T00:00:00Z", "valid_to": "2026-09-03T04:00:00Z",
                 "steps": ["2026-09-03T00:00:00Z", "2026-09-03T03:00:00Z"]}
  },
  "aligned": [
    {"parameter": "significant_wave_height", "method": "nearest_node",
     "node_distance_km": 6.2, "time_method": "nearest_step", "time_offset_min": 30,
     "provenance_id": "pv-w14"},
    {"parameter": "sst", "method": "bilinear", "node_distance_km": 4.1,
     "time_method": "daily_composite_of_window", "provenance_id": "pv-s21"}
  ],
  "not_aligned": [
    {"parameter": "temperature_profile", "reason": "representativeness=10day_mean "
     "incompatible with a 4-hour analysis window; retained as context only"}
  ],
  "derived": ["pv-d09", "pv-d10"],
  "geometry_results": [
    {"predicate": "point_in_polygon", "boundary_type": "EEZ", "result": true,
     "provenance_id": "pv-b02"}
  ],
  "unsupported_operations": [
    {"operation": "point_in_pfz", "reason": "RASTER_ONLY", "code": "VECTOR_UNAVAILABLE"}
  ],
  "layers": [{"layer_id": "ly-sst", "type": "raster_tiles", "legend_ref": "…"},
             {"layer_id": "ly-eez", "type": "geojson", "geometry_ref": "orca://geo/eez-ind"}]
}
```

### 5.6 Tools allowed
No external capability tools. It calls **deterministic kernel functions** in
`orca.geospatial.*`, each versioned and unit-tested (`11_GEOSPATIAL_REASONING_SPEC.md`).

### 5.7 Deterministic vs LLM split
| Deterministic (100 % of numbers) | LLM (≤ 3 sentences) |
|---|---|
| CRS transforms, subsetting, masking, resampling, interpolation, anomaly computation, statistics, geometry predicates, temporal alignment, distance/area | A plain-language summary of the spatial situation ("elevated chlorophyll forms a band 30–60 km offshore"), generated **from the computed statistics only** and labelled `interpretation` |

### 5.8 Failure handling
| Condition | Behaviour |
|---|---|
| CRS missing on an object | `SCHEMA_VALIDATION_FAILED`; object excluded, recorded |
| Coverage below threshold after masking | Parameter marked `not_evaluated` with `INSUFFICIENT_COVERAGE` |
| Alignment impossible (representativeness mismatch) | Listed in `not_aligned` with the reason; never force-aligned |
| Geometry operation on raster | `unsupported_operations` + `VECTOR_UNAVAILABLE` |
| Kernel exception | Caught, recorded as `ADAPTER_ERROR`-class internal failure; the affected derivation is omitted, the run continues |

### 5.9 Provenance requirements
Every derived value carries `derivation` with `method`, `method_version`, `inputs` and
`params`. Every alignment operation appears in `AlignmentReport.aligned` so the evidence
panel can state exactly how a point value was obtained from a grid.

---

## 6. Risk Assessment Agent

### 6.1 Purpose
Turn aligned evidence into **four independent domain assessments**, each with verdict,
confidence, drivers, gaps and conflicts.

### 6.2 Responsibilities
- Evaluate the SAFETY, FISHING_SUITABILITY, ECOLOGICAL (P1) and REGULATORY domains
  **separately**, using each domain's rule set and evidence allow-list.
- Enforce evidence sufficiency: a domain with a missing `required` input yields
  `INSUFFICIENT_EVIDENCE`, never a guess.
- Apply per-parameter staleness and representativeness policies.
- Incorporate official warnings as **governing constraints**: an active warning caps the
  safety verdict regardless of favourable model values.
- Apply conflict policy (conservative selection for safety; both values retained).
- Compute confidence from evidence sufficiency, quality flags, lead time, node distance
  and conflicts.
- Set the run `disposition` (`AUTO_RELEASE` / `REVIEW_REQUIRED` / `BLOCKED`).
- Emit `Evidence` objects binding each driver to its provenance.
- Produce a short factual rationale per domain — no chain-of-thought.

### 6.3 Non-responsibilities
- Does not merge domains into a single score. **Ever.**
- Does not fetch or derive data.
- Does not write the final narrative.
- Does not issue official advisories.

### 6.4 Inputs
```
state.aligned_data, state.derived, state.warnings, state.conflicts,
state.plan.domains_required, state.role_context (vessel class if known),
config.threshold_sets
```

### 6.5 Output — `Assessment[]`
Structure per `05_CANONICAL_DATA_SCHEMA.md` §19. One object per requested domain, plus a
`disposition` and the `limiting_factor` across domains.

### 6.6 Tools allowed
`search_marine_knowledge` (P1, RAG) — **explanatory context only**. RAG output may never
change a verdict; it can only add cited background to the rationale. In the MVP the agent
has no tools.

### 6.7 Decision logic
```
DETERMINISTIC RULE ENGINE (no LLM):
  for domain in domains_required:
      inputs   = collect(domain.evidence_allow_list)
      usable   = filter(inputs, staleness_ok ∧ representativeness_ok ∧ quality ≠ invalid)
      if missing(domain.required_inputs, usable):
            verdict = INSUFFICIENT_EVIDENCE
      else:
            verdict = evaluate_rules(domain.threshold_set, usable)   # documented thresholds
      apply governing constraints (official warnings, regulatory prohibitions)
      confidence = confidence_model(evidence_sufficiency, quality, lead_time, conflicts)

LLM (bounded):
  rationale_text = explain(verdict, drivers, gaps)   # ≤ 4 sentences, no new facts
```

The LLM **cannot change a verdict**. Its output is validated: every factual token in the
rationale must correspond to a driver or gap already present in the assessment; otherwise
the rationale is regenerated once and then replaced with a deterministic template.

### 6.8 Failure handling and escalation
| Condition | Behaviour |
|---|---|
| Missing required input | `INSUFFICIENT_EVIDENCE` for that domain, other domains proceed |
| Safety verdict `UNSAFE` in an operational role context | `disposition = REVIEW_REQUIRED` |
| Unresolved material safety-relevant conflict | `disposition = REVIEW_REQUIRED` |
| Confidence `low` on a safety verdict | `disposition = REVIEW_REQUIRED` |
| No safety input at all | `disposition = BLOCKED`; no safety statement issued |
| Regulatory `PROHIBITED` | Surfaced prominently; recommendation cannot suggest the activity |

### 6.9 Provenance requirements
Every driver references an `evidence_id` → `provenance_id`. Every threshold reference
carries `threshold_id`, `threshold_set` version and its validation status (thresholds are
**SCIENTIFIC VALIDATION REQUIRED** until domain-validated).

### 6.10 Example execution
```
SAFETY               MARGINAL   confidence medium
  drivers   Hs 2.4 m (limiting, threshold small_craft_hs_marginal)
            wind 11.3 m/s (supporting, below marginal threshold)
            official warning: none active
  gaps      lightning — AUTH_REQUIRED
  conflicts cf-002 (Hs 2.4 vs 3.1 m) → conservative value used, both reported
FISHING_SUITABILITY  FAVOURABLE confidence medium
  drivers   PFZ advisory intersects area (raster, indicative)
            chlorophyll 0.8 mg/m3 above local median
            sst_anomaly +0.4 degC (derived)
REGULATORY           PERMITTED  confidence high     (inside Indian EEZ; advisory only)
disposition = REVIEW_REQUIRED   (safety-relevant conflict)
limiting_factor = SAFETY / significant_wave_height
```

---

## 7. Reporting Agent

### 7.1 Purpose
Compose the user-facing answer: truthful, cited, in the user's language, at the right
level of detail for the user's role.

### 7.2 Responsibilities
- Compose a headline that leads with the **limiting factor** when domains disagree.
- Write a narrative bound to `Evidence`; emit `Claim` objects with `evidence_ids`.
- State explicitly: what was not evaluated and why; whether a fallback source was used;
  whether data was stale; whether a conflict exists.
- Quote official warnings verbatim, attributed, visually and semantically separated from
  ORCA's own synthesis.
- Apply the non-official-advisory disclaimer to every ORCA-generated recommendation.
- Produce the concise `reasoning_summary` (what was checked, what decided it).
- Localise the narrative into the session language without altering numbers, units,
  coordinates or quoted official text.
- Produce role-appropriate detail (fisher: plain and short; analyst: dataset-level).

### 7.3 Non-responsibilities
- Does not introduce facts. Any statement not traceable to evidence is rejected.
- Does not change verdicts or confidence.
- Does not translate quoted official bulletins in place (it may append a clearly labelled
  translation).
- Does not expose chain-of-thought, prompts, or model identifiers to the user.

### 7.4 Inputs
```
state.assessments, state.evidence, state.conflicts, state.not_evaluated,
state.official_warnings, state.language, state.role, state.layers
```

### 7.5 Output — `Recommendation`
Structure per `05_CANONICAL_DATA_SCHEMA.md` §20, plus `claims[]` and the layer set the
map should display.

### 7.6 Tools allowed
`translate_text` (P1), `search_marine_knowledge` (P1, background only, cited),
`generate_report_document` (P1). None in the MVP beyond the internal localisation
function.

### 7.7 Generation constraints (enforced, not requested)
1. **Evidence binding.** Every material claim must carry ≥ 1 `evidence_id`. A validator
   parses the generated text into claims and rejects unbound material claims.
2. **Numeric fidelity.** Every number in the text must appear in the evidence set with
   the same unit and rounding policy. Numeric drift fails validation.
3. **Official-language guard.** The strings "official", "advisory issued", "warning
   issued" and their localised equivalents are permitted only in a quoted
   `MarineWarning` context.
4. **No absence-of-evidence claims.** "Conditions are safe" is forbidden when a safety
   input is missing; the permitted form is "Sea state appears marginal; lightning could
   not be checked".
5. **Regeneration policy.** One regeneration attempt on validation failure; then fall back
   to a deterministic template answer built directly from assessments and evidence.

### 7.8 Failure handling
| Condition | Behaviour |
|---|---|
| Validation failure ×2 | Deterministic template answer (guaranteed grounded, less fluent) |
| Language model unavailable | Deterministic template answer in the target language via the terminology lexicon |
| Translation unavailable | Answer delivered in English with an explicit notice |
| `disposition = REVIEW_REQUIRED` | The composed answer is held at `human_review`; nothing is delivered until a decision is recorded |

### 7.9 Example output (abridged)
```
Fishing conditions look favourable near Kochi tomorrow morning, but sea state is
marginal for small craft — wave height is the limiting factor, not fish availability.

• Waves: significant wave height around 2.4 m at 06:00 IST [CMEMS, forecast +12.5 h]
  A second forecast source indicates 3.1 m; the more adverse value was used for the
  safety assessment and both are shown.
• Wind: 11 m/s from the west [NOAA — used because the IMD service was unreachable]
• Official warnings: none active for this area at this time [IMD, checked 11:04 IST]
• Fish availability: the PFZ advisory covers your area (imagery only — exact zone
  boundaries are not available), chlorophyll is above the local median, and sea surface
  temperature is 0.4 °C above the 10-day mean [INCOIS ERDDAP].
• Not checked: lightning (the IMD lightning service requires credentials).

This is an ORCA assessment, not an official advisory. Follow IMD and INCOIS bulletins.
```

---

## 8. Agent Interaction

```
        ┌─────────────┐   Plan    ┌───────────────────┐  RetrievalReport
 query →│   PLANNER   │──────────▶│  DATA DISCOVERY   │──────────────────┐
        └─────┬───────┘           └───────────────────┘                  │
              ▲ re-plan                     │ canonical objects          │
              │ (≤2)                        ▼                            │
        ┌─────┴───────┐            ┌───────────────────┐                 │
        │  VALIDATE   │◀───────────│    GEOSPATIAL     │◀────────────────┘
        │   (kernel)  │            │     ANALYSIS      │
        └─────┬───────┘            └─────────┬─────────┘
              │ ok                           │ aligned + derived
              ▼                              ▼
                            ┌───────────────────────────┐
                            │    RISK ASSESSMENT        │
                            │ SAFETY · FISHING ·        │
                            │ ECOLOGICAL · REGULATORY   │
                            └─────────────┬─────────────┘
                                          │ assessments + disposition
                              ┌───────────▼────────────┐
                              │  HUMAN REVIEW (cond.)  │
                              └───────────┬────────────┘
                                          ▼
                              ┌────────────────────────┐
                              │      REPORTING         │
                              └───────────┬────────────┘
                                          ▼   answer + map + evidence
```

Agents never call each other directly. All communication is through typed graph state
(`07_LANGGRAPH_WORKFLOW_SPEC.md`), which makes every hand-off inspectable and replayable.

---

## 9. Agent Capability Matrix

| Capability | Planner | Discovery | Geospatial | Risk | Reporting |
|---|:--:|:--:|:--:|:--:|:--:|
| Calls capability tools | ✗ | ✔ | ✗ | ✗(P1 RAG) | ✗(P1) |
| Calls deterministic kernels | ✗ | ✗ | ✔ | ✔ | ✗ |
| Uses an LLM | ✔ | limited | summary only | rationale only | ✔ |
| Produces numbers | ✗ | ✗ | ✔ | ✗ (evaluates) | ✗ |
| Produces verdicts | ✗ | ✗ | ✗ | ✔ | ✗ |
| Produces user text | ✗ | ✗ | ✗ | ✗ | ✔ |
| Can trigger re-plan | ✔ | signals | signals | ✗ | ✗ |
| Can set `REVIEW_REQUIRED` | ✗ | ✗ | ✗ | ✔ | ✗ |
| Writes provenance | ✔ (plan) | ✔ (retrieval) | ✔ (derivation) | ✔ (evidence) | ✔ (claims) |

---

## 10. Testing Requirements per Agent

| Agent | Key tests |
|---|---|
| Planner | Intent classification set; tool-selection minimality (warning lookup must not plan SST); ambiguity → clarification; re-plan bounded; plan schema validity |
| Data Discovery | Fallback recorded; `AUTH_REQUIRED` never retried; widening rules respected; warning-area widening forbidden; conflict emission; budget enforcement |
| Geospatial | Reference-value tests for every derivation; CRS round-trips; masking correctness; refusal to align incompatible representativeness; raster predicate refusal |
| Risk | Domain independence (favourable fishing + unsafe safety); warning-cap behaviour; insufficient evidence path; conflict conservatism; LLM cannot alter verdict |
| Reporting | Evidence-binding rejection of unbound claims; numeric fidelity; official-language guard; not-evaluated disclosure; localisation preserves numbers |

Full matrix: `15_EVALUATION_AND_TESTING_SPEC.md`.
