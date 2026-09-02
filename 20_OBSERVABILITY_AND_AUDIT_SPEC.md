# ORCA — Observability and Audit Specification

**Document:** 20 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Design defined — IMPLEMENTATION REQUIRED

---

## 1. The Requirement

> It must be possible to reconstruct **why** a recommendation was produced — completely —
> **without** exposing private model chain-of-thought.

That single sentence sets the whole design. Reconstruction is achieved from *artifacts*,
not from the model's internal narration:

```
   raw upstream response          (object storage, retention-bounded)
        ↓ adapter
   canonical object + provenance  (database)
        ↓ kernel
   derived value + derivation     (method, version, inputs, params — recomputable)
        ↓ rule engine
   assessment + drivers + gaps    (threshold ids, evidence ids)
        ↓ evidence assembly
   evidence + claims              (claim ↔ evidence binding)
        ↓ reporting
   answer sentence
```

Every arrow is persisted. A reviewer six months later can replay the chain, recompute the
derived numbers and see exactly which threshold produced which verdict — with no access to
any model's reasoning trace.

---

## 2. Identifier Model

Correlation is only possible if identifiers are consistent everywhere.

| ID | Format | Scope | Appears in |
|---|---|---|---|
| `trace_id` | W3C trace id | One request/run end-to-end | Logs, spans, API error bodies |
| `run_id` | `run-<ULID>` | One query execution (= LangGraph `thread_id`) | Everything |
| `session_id` | `ses-<ULID>` | Conversation | Runs, turns |
| `agent_exec_id` | `ae-<ULID>` | One agent invocation | Agent logs, spans |
| `tool_exec_id` | `te-<ULID>` | One tool call | Tool logs, provenance, object storage keys |
| `step_id` | `s1`, `s2`… | Plan step | Plan, retrieval report, events |
| `provenance_id` | `pv-<ULID>` | One value | Evidence, derivations, layers |
| `evidence_id` | `ev-<ULID>` | One assessment-facing fact | Claims, assessments |
| `claim_id` | `cl-<ULID>` | One answer assertion | Answer, evidence binding |
| `conflict_id` | `cf-<ULID>` | One disagreement | Assessments, review |
| `alert_id` | `alr-<ULID>` | One alert | Delivery records |
| `audit_id` | sequence | One audit row | Hash chain |

**Rule.** `run_id` and `trace_id` are propagated into every log line, span, database row
and object-storage key touched by that run. A log line without `run_id` is a bug.

---

## 3. Structured Logging

JSON only in non-local environments. One event per line.

```json
{"ts":"2026-09-02T11:04:35.312Z","level":"info","logger":"orca.tools.get_sst",
 "event":"tool.finished","run_id":"run-01JBQ7F0AA","trace_id":"01JBQ7F2K9…",
 "span_id":"a1b2c3…","tool_exec_id":"te-01JBQ7F3","step_id":"s5","tool":"get_sst",
 "source_id":"S-02","actual_source":"S-02","fallback_used":false,
 "status":"success","codes":[],"duration_ms":1210,"cache_hit":false,
 "response_bytes":148213,"bbox_area_km2":132400,"coverage_fraction":0.83}
```

### 3.1 Required fields on every line
`ts`, `level`, `logger`, `event`, `run_id` (where applicable), `trace_id`, `env`,
`service`, `version`.

### 3.2 Event taxonomy (closed set)

| Prefix | Events |
|---|---|
| `run.*` | `started`, `completed`, `failed`, `cancelled`, `blocked` |
| `node.*` | `started`, `finished`, `failed`, `retried` |
| `plan.*` | `created`, `replanned`, `clarification_requested` |
| `tool.*` | `started`, `finished`, `failed`, `fallback_used`, `cache_hit`, `rate_limited` |
| `adapter.*` | `request`, `response`, `retry`, `breaker_open`, `breaker_closed` |
| `validation.*` | `object_dropped`, `gap_detected`, `conflict_detected` |
| `geo.*` | `aligned`, `not_aligned`, `derived`, `unsupported_operation` |
| `assess.*` | `verdict`, `insufficient_evidence`, `warning_governing` |
| `review.*` | `required`, `requested`, `decided`, `timed_out` |
| `report.*` | `generated`, `validation_failed`, `template_fallback` |
| `alert.*` | `triggered`, `suppressed`, `dispatched`, `delivery_failed` |
| `llm.*` | `call`, `error`, `budget_exceeded` |
| `security.*` | `auth_failed`, `authz_denied`, `injection_pattern_detected`, `secret_access_failed` |

### 3.3 Never logged

| Prohibited | Reason |
|---|---|
| **Model chain-of-thought / raw reasoning traces** | Design rule; not a user-facing artifact |
| Credentials, tokens, API keys | Redacted by key pattern and value shape |
| Full prompt text containing personal data | Prompt-template **version** is logged instead |
| Precise user coordinates | Truncated to ~2 decimal places (≈ 1 km) in logs; full precision lives only in the database under retention policy |
| Contact details | |
| Full upstream response bodies | Stored in object storage with a reference; not in logs |

### 3.4 Sampling and volume
`INFO` for lifecycle events; `DEBUG` (sampled, off by default in production) for adapter
request/response metadata; `WARNING` for degradations; `ERROR` for capability loss.
Adapter `DEBUG` never includes the response body.

---

## 4. Distributed Tracing

OpenTelemetry spans mirror the graph.

```
run  run-01JBQ7F0AA                                       ├────────────────────────┤ 13.0 s
├─ node.ingest                                            ├┤                        0.02 s
├─ node.intent_context                                    ├──┤                      0.31 s
│  └─ llm.classify_intent          model=<id> tokens=…    ├──┤                      0.28 s
├─ node.plan                                              │  ├────┤                 1.11 s
│  └─ llm.generate_plan            template=planner@v3    │  ├────┤                 1.08 s
├─ node.retrieve                                          │      ├──────────┤       2.70 s
│  ├─ tool.get_marine_warnings     source=S-05            │      ├──┤              0.61 s
│  ├─ tool.get_wave_conditions     source=S-07            │      ├───────┤         1.90 s
│  │  └─ adapter.cmems.request                            │      ├──────┤          1.74 s
│  ├─ tool.get_sst                 source=S-02            │      ├────┤            1.21 s
│  └─ tool.get_lightning           source=S-05 AUTH_REQ   │      ├┤                0.18 s
├─ node.validate                                          │              ├┤        0.08 s
├─ node.geo_reason                                        │               ├───┤    0.81 s
├─ node.assess_safety / fishing / regulatory  (parallel)  │                  ├──┤  0.42 s
├─ node.conflict_resolve                                  │                     ├┤ 0.07 s
├─ node.evidence_assemble                                 │                     ├┤ 0.05 s
├─ node.review_gate                                       │                     ├┤ 0.01 s
├─ node.human_review               (interrupt)            │                     ├──…
└─ node.report                                            │                        ├──┤
```

Span attributes: `run_id`, `node`, `tool`, `source_id`, `fallback_used`, `codes`,
`cache_hit`, `model_id`, `prompt_template_version`, `tokens_in/out`, `attempt`.
Span attributes never carry payload content.

---

## 5. Metrics

### 5.1 Run-level
| Metric | Type | Labels |
|---|---|---|
| `orca_runs_total` | counter | `status`, `intent`, `disposition` |
| `orca_run_duration_seconds` | histogram | `intent` |
| `orca_run_tools_used` | histogram | `intent` |
| `orca_runs_degraded_total` | counter | `reason` |
| `orca_runs_no_verdict_total` | counter | `reason` |

### 5.2 Tool and source
| Metric | Type | Labels |
|---|---|---|
| `orca_tool_calls_total` | counter | `tool`, `status`, `code` |
| `orca_tool_duration_seconds` | histogram | `tool`, `source_id` |
| `orca_fallbacks_total` | counter | `tool`, `primary`, `actual`, `reason` |
| `orca_source_availability` | gauge | `source_id` |
| `orca_breaker_state` | gauge | `source_id` |
| `orca_cache_hits_total` | counter | `tool` |
| `orca_upstream_budget_used` | gauge | `source_id` |

### 5.3 Reasoning quality
| Metric | Type | Labels | Why it matters |
|---|---|---|---|
| `orca_conflicts_detected_total` | counter | `parameter`, `safety_relevant` | Cross-source disagreement rate |
| `orca_insufficient_evidence_total` | counter | `domain`, `missing_factor` | Where coverage is weakest |
| `orca_assessments_total` | counter | `domain`, `verdict`, `confidence` | Verdict distribution |
| `orca_domain_disagreement_total` | counter | `pattern` | **The differentiator, measured** |
| `orca_grounding_failures_total` | counter | `stage` | Ungrounded generation attempts caught |
| `orca_template_fallback_total` | counter | `reason` | Generation reliability |
| `orca_review_required_total` | counter | `reason` | Escalation load |
| `orca_override_total` | counter | `decision` | Human disagreement with ORCA |

`orca_override_total{decision="approved_with_edits"}` and `{decision="rejected"}` are the
most valuable long-run signals in the system: they measure how often ORCA's assessment
needed human correction, and they are the empirical input to threshold validation.

### 5.4 Model usage and cost
| Metric | Labels |
|---|---|
| `orca_llm_calls_total` | `node`, `model_id`, `status` |
| `orca_llm_tokens_total` | `node`, `model_id`, `direction` |
| `orca_llm_cost_micros_total` | `node`, `model_id` |
| `orca_llm_latency_seconds` | `node`, `model_id` |
| `orca_run_budget_exceeded_total` | `budget_type` |

Per-run token and cost totals are stored on `agent_executions`, so cost is attributable to
a specific query — not just an aggregate bill.

### 5.5 Alerts, security, API
`orca_alerts_triggered_total{severity,trigger}`, `orca_alerts_suppressed_total{reason}`,
`orca_alert_delivery_total{channel,status}`, `orca_auth_failures_total`,
`orca_authz_denied_total{role,route}`, `orca_injection_detected_total{surface}`,
`orca_http_requests_total{route,status}`, `orca_rate_limited_total{scope}`.

---

## 6. Provenance as Observability

Provenance is not only a user-facing feature — it is the primary debugging instrument.

```sql
-- Why did this run say 2.4 m?
SELECT p.parameter, p.value_numeric, p.unit, p.valid_time, p.retrieved_at,
       s.name AS source, p.dataset_id, p.fallback_used, p.cache_hit, p.derivation
FROM provenance p JOIN sources s USING (source_id)
WHERE p.run_id = $1 AND p.parameter = 'significant_wave_height';

-- Which threshold produced the verdict?
SELECT domain, verdict, threshold_set, threshold_set_status,
       jsonb_array_elements(drivers) AS driver
FROM assessments WHERE run_id = $1;
```

Debugging a wrong answer therefore starts with data, not with guessing what the model was
thinking — which is the point of the architecture.

---

## 7. Audit Trail

Structure in `09_DATABASE_SPEC.md` §6. Operational properties:

| Property | Detail |
|---|---|
| Append-only | Trigger + role permissions (application role has `INSERT`/`SELECT` only) |
| Hash chain | `row_hash = sha256(prev_hash ‖ canonical(row))`; a verification job runs daily |
| Coverage | Query submission, run completion, review decisions, overrides, alert dispatch, configuration changes, exports, source status changes, auth failures, authz denials |
| Actor | `user` \| `system` \| `agent` \| `scheduler`, with the specific identifier |
| Retention | ≥ 24 months (policy proposal requiring organisational confirmation) |
| Deletion | A user deletion request pseudonymises the actor; rows are never removed |
| Access | `admin` and `analyst` (read-only); every access is itself audited |

### 7.1 Human override audit record

```json
{"audit_id": 88123, "occurred_at": "2026-09-02T11:09:10Z",
 "actor_type": "user", "actor_id": "usr-…", "action": "override.applied",
 "object_type": "assessment", "object_id": "as-safety-01", "run_id": "run-01JBQ7F0AA",
 "details": {"reviewer_role": "officer",
             "trigger_reason": "safety_relevant_conflict",
             "original": {"verdict": "MARGINAL", "confidence": "medium"},
             "revised":  {"verdict": "UNSAFE",   "confidence": "medium"},
             "rationale": "Second forecast source indicates 3.1 m; treating as unsafe for small craft.",
             "conflict_id": "cf-002",
             "review_latency_s": 187},
 "prev_hash": "sha256:…", "row_hash": "sha256:…", "trace_id": "01JBQ7F2K9…"}
```

The original assessment row remains, with `superseded_by` pointing at the override — so
the audit answers both "what did the machine say?" and "what did the human decide?".

---

## 8. Run Reconstruction

`GET /v1/runs/{run_id}/trace` (scope `trace:read`) assembles:

```
RUN run-01JBQ7F0AA · fishing_suitability · en · disposition REVIEW_REQUIRED · 13.0 s
├─ CONTEXT   9.93N 76.26E "near Kochi" · 2026-09-03T00:00Z–04:00Z
├─ PLAN v1   9 steps · domains SAFETY, FISHING_SUITABILITY, REGULATORY
│            model=<id> template=planner@v3 tokens 812/240
├─ RETRIEVAL 9 calls · 6 success · 1 empty · 1 partial · 1 failed · 1 fallback
│   ├─ s1 get_marine_warnings  S-05 empty   NO_ACTIVE_WARNING   0.61 s
│   ├─ s2 get_wave_conditions  S-07 success                     1.90 s  → pv-w13, pv-w14
│   ├─ s4 get_lightning        S-05 error   AUTH_REQUIRED       0.18 s
│   ├─ s6 get_pfz              S-06 partial RASTER_ONLY         2.11 s  → pv-p11
│   └─ …
├─ VALIDATION 41 valid · 2 dropped (missing crs) · 0 required gaps · 1 conflict
├─ GEOSPATIAL frame=point+window · 6 aligned · 1 not aligned (10day_mean)
│              derived: sst_anomaly (pv-d09), current_speed (pv-d10)
│              unsupported: point_in_pfz (RASTER_ONLY)
├─ ASSESSMENT SAFETY=MARGINAL(med) FISHING=FAVOURABLE(med) REGULATORY=PERMITTED(high)
│              thresholds small_craft_v0.1 [SCIENTIFIC_VALIDATION_REQUIRED]
├─ CONFLICT   cf-002 Hs 2.4 (S-07) vs 3.1 (S-11) · Δ0.7 > tol 0.5 · conservative applied
├─ REVIEW     required (safety_relevant_conflict) → officer approved_with_edits @187 s
├─ REPORT     7 claims · all evidence-bound · 1 regeneration · template_fallback=false
└─ AUDIT      6 rows · hash chain verified
```

**Nothing in this reconstruction is model chain-of-thought.** It is plans, tool outcomes,
provenance, derivations, thresholds, conflicts and decisions — all of which are artifacts.

---

## 9. Dashboards

| Dashboard | Panels |
|---|---|
| **Source health** | Availability per source, breaker state, p50/p95 latency, fallback rate, auth-required count, upstream budget usage |
| **Run health** | Runs/min by status, duration percentiles, tools per run, degraded-run rate, no-verdict rate |
| **Reasoning quality** | Verdict distribution by domain, insufficient-evidence rate by missing factor, conflict rate by parameter, domain-disagreement count, grounding failures, template fallbacks |
| **Review** | Queue depth, time-to-decision, decision mix, override rate by domain |
| **Alerts** | Triggered vs suppressed, delivery success by channel, un-reviewed blocked count |
| **Cost** | Tokens and cost by node and model, cost per run, budget-exceeded events |
| **Security** | Auth failures, authz denials, injection detections, rate limiting |

---

## 10. Operational Alerting (on ORCA itself)

| Condition | Severity | Response |
|---|---|---|
| A **VERIFIED** source unavailable > 15 min | high | Investigate; check upstream status; confirm not a local network issue before recording anything |
| Fallback rate > 30 % for a tool over 1 h | medium | Primary source degradation |
| Grounding failure rate rising | high | Prompt/model regression — freeze deployments |
| Template fallback rate > 10 % | medium | Generation reliability problem |
| Review queue depth > threshold, or oldest item > SLA | high | Escalation backlog |
| Un-reviewed alert blocked by timeout | high | Subscribers did not receive a warning |
| Audit hash-chain verification failure | **critical** | Possible tampering; incident response |
| Injection patterns detected above baseline | high | Security review |
| Run p95 above budget | medium | Performance regression |
| Dataset unavailable (upstream rename) | high | Adapter update required |

**Distinguish local from upstream.** A DNS failure on the deployment network must be
classified as a local condition, not recorded as an upstream outage — the same discipline
applied to the WMS finding in `03_DATA_SOURCE_MATRIX.md`.

---

## 11. Client-Facing Observability

The frontend receives a **filtered projection** of the same events
(`08_API_SPEC.md` §7): node names, tool names, source names, outcomes, codes and timings.

Never sent to the client: model identifiers (except to `analyst`), prompt templates, raw
upstream payloads, credentials, chain-of-thought.

The user-facing "why" surface is the evidence panel and the reasoning summary — a concise,
factual statement of what was checked and what drove the verdict, generated from the
assessment record rather than from model narration.

---

## 12. Retention

| Signal | Retention |
|---|---|
| Application logs | 30 days hot, 90 days cold |
| Traces | 7 days full, sampled 30 days |
| Metrics | 15 days raw, 13 months downsampled |
| Run records, provenance, evidence | 12 months |
| Raw upstream payloads | 30 days |
| Audit log | ≥ 24 months, append-only |
| Human reviews | Life of the audit log |

All values are policy proposals requiring organisational confirmation
(`14_SECURITY_PRIVACY_AND_GOVERNANCE.md` §10.3).

---

## 13. Testing Observability

| Test | Assertion |
|---|---|
| Correlation | Every log line emitted during a run carries its `run_id` |
| Redaction | Injected credential-shaped strings never appear in logs |
| Location precision | Coordinates in logs are truncated to ≤ 2 decimal places |
| **No CoT** | No log, span, event, checkpoint or database row contains model reasoning traces (asserted against a model stub that emits a marker string) |
| Reconstruction | A recorded run can be fully reconstructed from database + object store alone |
| Recomputation | Every derived value in a stored run recomputes to the same value from its recorded inputs |
| Audit immutability | `UPDATE`/`DELETE` raises; the hash chain verifies |
| Metric presence | Every documented metric is emitted at least once in the E2E suite |
