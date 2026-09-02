# ORCA — Engineering Risk Register

**Document:** 21 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Review cadence:** weekly during implementation; before every demo
**Owners** are named by **role**, not by person, so the register survives team changes.

---

## 1. Scoring

**Likelihood:** `L1` rare · `L2` unlikely · `L3` possible · `L4` likely · `L5` near-certain
**Impact:** `I1` negligible · `I2` minor · `I3` moderate · `I4` major · `I5` severe
**Exposure** = L × I. **≥ 12 = critical**, 8–11 = high, 4–7 = medium, < 4 = low.

**Status:** `OPEN` · `MITIGATING` · `ACCEPTED` · `CLOSED`

**Roles:** DATA (adapters/sources) · BACKEND (tools/graph/API) · GEO (geospatial kernel) ·
REASON (assessment/agents) · FE (frontend) · SEC (security/governance) · LEAD (scope,
schedule, demo).

---

## 2. Risk Summary

| ID | Risk | L | I | Exp | Status | Owner |
|---|---|:--:|:--:|:--:|---|---|
| R-01 | IMD credentials not granted in time | L4 | I4 | **16** | MITIGATING | DATA |
| R-02 | INCOIS WMS remains unverifiable / PFZ vector unavailable | L4 | I3 | **12** | MITIGATING | DATA |
| R-03 | Thresholds are unvalidated engineering parameters | L5 | I4 | **20** | MITIGATING | REASON |
| R-04 | Sources materially disagree | L4 | I3 | **12** | MITIGATING | REASON |
| R-05 | Ungrounded generation reaches a user | L3 | I5 | **15** | MITIGATING | REASON |
| R-06 | Silent geospatial error (CRS/axis/units) | L3 | I5 | **15** | MITIGATING | GEO |
| R-07 | Incorrect safety recommendation acted on | L2 | I5 | **10** | MITIGATING | REASON |
| R-08 | Upstream endpoint/schema change | L4 | I3 | **12** | MITIGATING | DATA |
| R-09 | Stale data presented as current | L3 | I4 | **12** | MITIGATING | BACKEND |
| R-10 | Latency exceeds usable bounds | L3 | I3 | 9 | MITIGATING | BACKEND |
| R-11 | Model-provider outage or degradation | L3 | I3 | 9 | MITIGATING | BACKEND |
| R-12 | Prompt injection via retrieved content | L3 | I4 | **12** | MITIGATING | SEC |
| R-13 | Multilingual error changes meaning | L3 | I4 | **12** | MITIGATING | REASON |
| R-14 | Development network blocks government hosts | L5 | I3 | **15** | MITIGATING | DATA |
| R-15 | Demo-day network or source failure | L3 | I4 | **12** | MITIGATING | LEAD |
| R-16 | Scope creep prevents an MVP | L4 | I5 | **20** | MITIGATING | LEAD |
| R-17 | CMEMS credentials/latency block waves and currents | L3 | I3 | 9 | MITIGATING | DATA |
| R-18 | MOSDAC integration consumes disproportionate effort | L3 | I2 | 6 | MITIGATING | LEAD |
| R-19 | Credential or secret leakage | L2 | I5 | **10** | MITIGATING | SEC |
| R-20 | Excessive load on public infrastructure | L3 | I3 | 9 | MITIGATING | BACKEND |
| R-21 | Alert spam or a false warning broadcast | L2 | I4 | 8 | MITIGATING | BACKEND |
| R-22 | Human-review bottleneck | L3 | I2 | 6 | ACCEPTED | LEAD |
| R-23 | Over-claiming in submission material | L3 | I4 | **12** | MITIGATING | LEAD |
| R-24 | Team capacity / key-person dependency | L3 | I4 | **12** | MITIGATING | LEAD |
| R-25 | Legal/licence uncertainty on data reuse | L3 | I3 | 9 | OPEN | SEC |

---

## 3. Risk Detail

### R-01 · IMD credentials not granted in time · **16 · MITIGATING · DATA**
**Description.** IMD is the primary source for weather, marine warnings, cyclone tracks and
lightning. Unauthenticated access returned HTTP 403; registration outcome and timeline are
outside the team's control.
**Detection.** Adapter returns `AUTH_REQUIRED`; startup banner shows `credentials=UNSET`;
`/v1/health/sources` reports `auth_required`.
**Mitigation.** Adapter is built and tested against the documented contract from Phase 1
and functions in `AUTH_REQUIRED` mode from day one. Registration is a **day-one action**
(`17_IMPLEMENTATION_ROADMAP.md` §2). Wind falls back to NOAA/ASCAT with the fallback
stated. Warnings have **no substitute** — their absence is reported as *unknown warning
status*, never as "no warning".
**Fallback.** The MVP demonstrates honest degradation as a feature: the demo explicitly
shows `get_lightning → AUTH_REQUIRED` and explains it.
**Residual.** Cyclone and lightning capabilities remain unavailable without credentials.
Accepted and documented.

### R-02 · WMS unverifiable / PFZ vector unavailable · **12 · MITIGATING · DATA**
**Description.** The audit identified public WMS capabilities and PFZ-related layers, but
local verification was blocked (DNS could not resolve the host on the campus network). It
is unknown whether PFZ geometry is obtainable or only rendered imagery.
**Detection.** `get_pfz` returns `RASTER_ONLY`, `VECTOR_UNAVAILABLE` or
`SOURCE_UNAVAILABLE`; the branch taken is recorded per call.
**Mitigation.** Three-branch design; **no capability depends exclusively on this endpoint**;
verification from an unrestricted network is a Phase-1 deliverable (V-2); the endpoint is
never labelled broken on the basis of a local DNS failure.
**Fallback.** Fishing suitability degrades to ORCA-derived indicators, explicitly labelled
and never called PFZ.
**Residual.** Point-in-zone questions may remain unanswerable. Stated in the UI.

### R-03 · Unvalidated thresholds · **20 · MITIGATING · REASON**
**Description.** `small_craft_v0.1` and `fishing_v0.1` are engineering parameters, not
validated science. A wrong boundary produces a wrong verdict.
**Detection.** Threshold set id and status are attached to every assessment and displayed;
override metrics measure human disagreement.
**Mitigation.** All thresholds are external configuration with `status:
SCIENTIFIC_VALIDATION_REQUIRED`; the status is shown in the UI and stated in the demo;
every band boundary has a test; the validation path is documented
(`12_RISK_AND_RECOMMENDATION_SPEC.md` §13).
**Fallback.** Conservative defaults; confidence capped; escalation to human review for
adverse verdicts.
**Residual.** High and **accepted for a prototype** — provided the unvalidated status is
never hidden. Claiming validated thresholds would be the actual failure.

### R-04 · Source disagreement · **12 · MITIGATING · REASON**
**Detection.** `CONFLICTING_SOURCES`; `orca_conflicts_detected_total`.
**Mitigation.** Both values retained; per-parameter tolerances; conservative selection for
safety; conflict surfaced in the UI; safety-relevant conflicts escalate to review.
**Fallback.** `insufficient_to_resolve` → `INSUFFICIENT_EVIDENCE` rather than a guess.
**Residual.** Conflict frequency is unknown until measured; the metric exists precisely to
find out.

### R-05 · Ungrounded generation · **15 · MITIGATING · REASON**
**Detection.** Grounding validator; `orca_grounding_failures_total`; RAG ungrounded-claim
metric.
**Mitigation.** Evidence set fixed **before** generation; claim↔evidence binding enforced;
numeric-fidelity check; official-language guard; two regenerations then a deterministic
template; RAG cannot alter verdicts.
**Fallback.** Template answer built directly from assessments and evidence.
**Residual.** Non-zero and **measured**, never claimed to be zero.

### R-06 · Silent geospatial error · **15 · MITIGATING · GEO**
**Description.** CRS confusion, lat/lon axis inversion, degree-based distance, unit
assumption. These fail silently and plausibly — the worst property a bug can have.
**Detection.** Reference tests; round-trip tests; adapter axis-order assertions; range
plausibility checks.
**Mitigation.** Explicit CRS on every object; geodesic computation only; units **read from
dataset metadata**, never assumed; every derivation has a reference test.
**Fallback.** Nearest-node only mode (less precise, always correct).
**Residual.** Medium; mitigated by test discipline that is a Definition-of-Done item.

### R-07 · Incorrect safety recommendation acted on · **10 · MITIGATING · REASON**
**Mitigation.** Non-official labelling enforced structurally; official warnings govern;
`CANNOT_ADVISE` when a required safety input is missing; human review for `UNSAFE` and for
conflicts; disclaimers are reviewed fixed strings; the demo never presents ORCA as an
operational service.
**Fallback.** Defer to official advisories.
**Residual.** Inherent to the domain; the honest position is that ORCA is a prototype and
is labelled as one everywhere.

### R-08 · Upstream endpoint/schema change · **12 · MITIGATING · DATA**
**Detection.** Nightly live smoke tests; `DATASET_UNAVAILABLE`; operational alerting.
**Mitigation.** All provider knowledge isolated in adapters; endpoints and layer names are
configuration; dataset availability re-checked at startup; **no silent substitution**.
**Fallback.** Fallback source with the switch recorded; if none, explicit capability loss.

### R-09 · Stale data presented as current · **12 · MITIGATING · BACKEND**
**Mitigation.** `valid_time` + `retrieved_at` on every value; per-parameter staleness
policy; freshness indicators in the UI; representativeness rules forbid using a monthly
analysis as a next-morning forecast; caches never rewrite `retrieved_at`.
**Fallback.** Stale data used only with an explicit label and reduced confidence.

### R-10 · Latency · 9 · MITIGATING · BACKEND
**Mitigation.** Parallel fan-out; per-tool timeouts; caching by product cadence; streamed
progress so waiting is visible; latency measured against recorded upstreams (ORCA's own
cost) and live (real-world).
**Fallback.** Partial answer with named gaps rather than an unbounded wait.

### R-11 · Model-provider outage · 9 · MITIGATING · BACKEND
**Mitigation.** Provider abstraction; retries; deterministic template answers; assessments
are rule-based and unaffected.
**Fallback.** ORCA answers without generation — less fluent, fully grounded.

### R-12 · Prompt injection · **12 · MITIGATING · SEC**
**Mitigation.** Retrieved content treated as data; structural separation; tool
allow-listing at the registry; models never construct URLs; argument validation; curated
RAG corpus (no open-web ingestion); ingestion screening; output validation; detection
metrics.
**Fallback.** Suspicious content is quoted to the user and flagged, never acted on.

### R-13 · Multilingual meaning error · **12 · MITIGATING · REASON**
**Mitigation.** Pivot architecture (reasoning once, in typed data); four automated hard
gates (numeric fidelity, verdict fidelity, disclaimer presence, reserved terms); reviewed
lexicon per language; native-speaker review before a language is enabled.
**Fallback.** Deterministic template in the target language, or English with an explicit
notice.
**Residual.** Register/nuance errors remain possible until human review is complete —
which is why a language is not enabled before that review.

### R-14 · Development network restrictions · **15 · MITIGATING · DATA**
**Description.** The campus network could not resolve `services.incois.gov.in`; other
government hosts may be similarly affected.
**Detection.** `verify_sources.py`; DNS failures classified as local conditions.
**Mitigation.** Verification performed from an unrestricted network; local development
defaults to recorded fixtures; a DNS failure is **never** recorded as a source outage.
**Fallback.** Fixture-driven development; verification scheduled off-campus.

### R-15 · Demo-day failure · **12 · MITIGATING · LEAD**
**Mitigation.** Rehearsed offline replay mode with a permanent "recorded" banner;
pre-staged fixtures labelled with capture time; recorded video backup; five rehearsals
including one failure-mode run; INCOIS ERDDAP (verified, unauthenticated) as the live
backbone.
**Fallback.** Replay mode, then the recorded video — both explicitly labelled.
**Rule.** Never present cached data as live. A discovered deception costs more than a
visible failure.

### R-16 · Scope creep · **20 · MITIGATING · LEAD**
**Description.** The single most likely cause of project failure. Twenty-plus attractive
features (routes, vessels, MOSDAC, HAB, TTS, SMS, eight languages) compete with one
working vertical slice.
**Detection.** Phase gates; MVP scope document treated as contractual; weekly review
against `22_MVP_SCOPE.md`.
**Mitigation.** Explicit must/should/defer/out-of-scope lists; feature flags default off;
a disabled tool cannot even be planned; anything not in the MVP requires an explicit
scope-change decision recorded in `24_ENGINEERING_DECISIONS.md`.
**Fallback.** Cut to the Phase-5 slice (no frontend polish, no alerts, no multilingual) —
still a complete, defensible demonstration.

### R-17 · CMEMS credentials/latency · 9 · MITIGATING · DATA
**Mitigation.** Registration as a day-one action; waves/currents degrade explicitly;
subsetting requests kept small; NOAA fallback.
**Fallback.** Safety assessment reports `wave_conditions: not_evaluated` and issues no
safety verdict rather than substituting another variable.

### R-18 · MOSDAC effort · 6 · MITIGATING · LEAD
**Mitigation.** Classified as ENHANCEMENT, P1, explicitly not an MVP dependency; if
acquisition latency is unsuitable, representative data is pre-staged and labelled.
**Note.** MOSDAC is strategically valuable for an ISRO-sponsored problem statement, but
scheduling it as a dependency would risk the whole system.

### R-19 · Secret leakage · **10 · MITIGATING · SEC**
**Mitigation.** Pre-commit secret scanning and a CI gate; secrets manager; adapter-only
access; log redaction by key pattern and value shape; credentials never enter model
context; upstream error bodies stored redacted, never rendered.
**Fallback.** Documented rotation procedure per source; incident response in `14` §13.

### R-20 · Load on public infrastructure · 9 · MITIGATING · BACKEND
**Description.** ORCA consumes public government services; abusive traffic would be both a
technical and a relationship failure.
**Mitigation.** Per-source outbound budgets; response caching by product cadence; bbox and
time-window caps; circuit breakers; local development on fixtures by default.
**Fallback.** `RATE_LIMITED` surfaced honestly in the answer.

### R-21 · Alert spam / false warning broadcast · 8 · MITIGATING · BACKEND
**Mitigation.** Deduplication by fingerprint with cooldowns; per-user rate limits; quiet
hours (overridable only by `CRITICAL`); human review required for ORCA-derived
`WARNING`/`CRITICAL`; fan-out size triggers batch review; un-reviewed alerts are **not**
dispatched on review timeout.
**Fallback.** Alerts disabled by feature flag.

### R-22 · Human-review bottleneck · 6 · **ACCEPTED** · LEAD
**Description.** Review gating means some answers wait for a human.
**Mitigation.** Review is scoped to genuinely high-impact cases; queue depth and
time-to-decision are monitored; timeout produces `BLOCKED` with an explanation.
**Acceptance rationale.** For a prototype, blocking an unverified adverse safety
recommendation is preferable to releasing it. Reviewer capacity is an operational
question for any real deployment.

### R-23 · Over-claiming in submission material · **12 · MITIGATING · LEAD**
**Description.** Slides and pitches drift toward "hallucination-free", "real-time",
"validated" and invented accuracy figures.
**Detection.** Pre-submission review of every artifact against
`25_GAP_AND_VALIDATION_REGISTER.md`.
**Mitigation.** Banned-phrase list (`16_DEMO_AND_SIH_PRESENTATION_SPEC.md` §7); the rule
that a number may be stated only if it exists in an `evaluation/reports/` artifact; the
gap register handed over as-is.
**Residual.** Requires discipline under presentation pressure; it is listed as a risk
precisely because it is the easiest one to trip over.

### R-24 · Team capacity / key-person dependency · **12 · MITIGATING · LEAD**
**Mitigation.** Layered architecture allows parallel work; documentation set enables
hand-off; adapters, kernels and frontend are independently testable; conventions in
`18_REPOSITORY_STRUCTURE.md` reduce onboarding cost.
**Fallback.** Cut to the Phase-5 slice per R-16.

### R-25 · Legal/licence uncertainty · 9 · **OPEN** · SEC
**Description.** Data reuse terms, attribution requirements, caching and redistribution
conditions differ per source; Indian regulatory considerations (including the DPDP Act,
2023) require legal confirmation.
**Mitigation.** Every adapter records a terms-of-use reference; no compliance claim is made
anywhere in the documentation; considerations are enumerated in
`14_SECURITY_PRIVACY_AND_GOVERNANCE.md` §10.3.
**Status.** Genuinely open — it requires institutional/legal input the team does not have.
Recording it as open is the correct engineering response.

---

## 4. Top Risks by Exposure

```
R-03  Unvalidated thresholds          ████████████████████  20   mitigate by labelling, never by hiding
R-16  Scope creep                     ████████████████████  20   mitigate by contractual MVP scope
R-01  IMD credentials                 ████████████████      16   mitigate by degradation-as-a-feature
R-05  Ungrounded generation           ███████████████       15   mitigate by validation + measurement
R-06  Silent geospatial error         ███████████████       15   mitigate by reference tests
R-14  Network restrictions            ███████████████       15   mitigate by off-campus verification
```

Four of the six top risks are mitigated by **transparency rather than by engineering** —
labelling unvalidated thresholds, showing degradation, measuring residual ungrounded
generation, and refusing to convert a local DNS failure into a claim about a source. That
is the correct posture for a design-stage system, and it is also what distinguishes an
honest submission from an over-claimed one.

---

## 5. Register Maintenance

| Rule | Detail |
|---|---|
| Review | Weekly during implementation; mandatory before any demo or submission |
| New risks | Added when discovered, with owner and mitigation, before the next gate |
| Closure | A risk closes only with evidence (a passing test, a granted credential, a completed verification) recorded in `25_GAP_AND_VALIDATION_REGISTER.md` |
| Escalation | Any risk reaching exposure ≥ 16 goes to LEAD in the same working day |
| Honesty | A risk is never downgraded because it is inconvenient; `ACCEPTED` requires a written rationale |
