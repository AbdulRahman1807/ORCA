# ORCA — Risk and Recommendation Specification

**Document:** 12 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Framework defined · thresholds **SCIENTIFIC VALIDATION REQUIRED** — IMPLEMENTATION REQUIRED

---

## 1. The Central Design Rule

> **ORCA does not compute a risk score.**

It computes **four independent assessments** over four different questions, each with its
own evidence set, rules, confidence and verdict vocabulary:

```
┌────────────────────────┬──────────────────────────────────────────────────────┐
│ SAFETY                 │ Can a vessel operate here safely in this window?      │
│ FISHING_SUITABILITY    │ Is fish likely to be available and catchable here?    │
│ ECOLOGICAL             │ What is the environmental condition of this water?    │
│ REGULATORY             │ Is operating here permitted, restricted or prohibited?│
└────────────────────────┴──────────────────────────────────────────────────────┘
```

They interact in the **narrative**, never in the arithmetic. A single blended number
would destroy the one thing the user actually needs:

> *"There is plenty of fish out there tomorrow, and you should not go, because the sea
> will be too rough — the limiting factor is wave height, not fish."*

That sentence is only possible because the two assessments are computed and reported
separately. Averaging them into "moderate risk: 0.62" loses both the recommendation and
the reason.

**Second rule.** ORCA's output is **never** an official advisory
(`is_official_advisory: false`, enforced by a database constraint —
`09_DATABASE_SPEC.md` §3.3). Official warnings are quoted and attributed; ORCA's synthesis
is labelled as ORCA's.

---

## 2. Verdict Vocabulary

| Domain | Verdicts |
|---|---|
| SAFETY | `FAVOURABLE` · `MARGINAL` · `UNFAVOURABLE` · `UNSAFE` · `INSUFFICIENT_EVIDENCE` |
| FISHING_SUITABILITY | `FAVOURABLE` · `MARGINAL` · `UNFAVOURABLE` · `INSUFFICIENT_EVIDENCE` |
| ECOLOGICAL (P1) | `NOMINAL` · `ANOMALOUS` · `DEGRADED` · `INSUFFICIENT_EVIDENCE` |
| REGULATORY | `PERMITTED` · `RESTRICTED` · `PROHIBITED` · `UNKNOWN` |

`UNSAFE` exists only in SAFETY — nothing else in ORCA can make a situation dangerous.
`INSUFFICIENT_EVIDENCE` / `UNKNOWN` are **first-class outcomes**, not error states, and
they appear in the answer as clearly as any verdict.

Confidence: `low` · `medium` · `high`, always accompanied by the factors that produced it.

---

## 3. Assessment Anatomy

Every domain assessment is produced by the same deterministic pipeline:

```
   evidence set
        │  1. FILTER   staleness · representativeness · quality flags
        ▼
   usable evidence
        │  2. SUFFICIENCY  are the domain's required inputs present?
        ▼
   [insufficient] ──▶ INSUFFICIENT_EVIDENCE  (+ list what is missing and why)
        │ sufficient
        ▼
        │  3. RULES     documented thresholds → per-factor states
        ▼
   factor states
        │  4. COMBINE   worst-factor governs (no averaging)
        ▼
   provisional verdict
        │  5. CONSTRAIN official warnings · regulatory prohibitions · conflicts
        ▼
   final verdict
        │  6. CONFIDENCE  from sufficiency, quality, lead time, node distance, conflicts
        ▼
   Assessment { verdict, confidence, drivers[], not_evaluated[], conflicts[] }
```

Steps 1–6 are **deterministic code**. The LLM writes only the prose rationale afterwards,
and cannot alter any field (`06_AGENT_SPEC.md` §6.7).

### 3.1 Evidence filtering rules

| Filter | Rule |
|---|---|
| Staleness | Each parameter has a max age relative to its cadence; beyond it the value is `STALE_DATA` — usable only with an explicit label and reduced confidence |
| Representativeness | Each domain declares which `representativeness` values it accepts (`11` §8.2). A monthly analysis cannot support a next-morning safety verdict |
| Quality | `invalid` is excluded; `suspect` is excluded from the verdict but reported; `degraded` is used with reduced confidence |
| Spatial mismatch | Node distance beyond the per-parameter maximum downgrades quality and is surfaced |
| Coverage | Fields below the minimum coverage fraction are `not_evaluated` rather than summarised from a few valid pixels |

### 3.2 Combination rule — worst factor governs

```python
ORDER = ["FAVOURABLE", "MARGINAL", "UNFAVOURABLE", "UNSAFE"]
verdict = max(factor_states, key=ORDER.index)      # the worst state wins
limiting_factor = the factor that produced it
```

Never averaged, never weighted-summed. Calm wind does not offset dangerous waves. The
factor that produced the verdict is always named — that is what makes the answer
actionable.

---

## 4. SAFETY Assessment

### 4.1 Inputs

| Factor | Tool | Necessity | Accepted representativeness |
|---|---|---|---|
| Official marine warning | `get_marine_warnings` | **required** | `bulletin_period` |
| Significant wave height | `get_wave_conditions` | **required** | `instantaneous`, `hourly_mean` |
| Wind speed / gust | `get_weather` | **required** | `instantaneous`, `hourly_mean` |
| Swell height / period | `get_wave_conditions` | preferred | `instantaneous` |
| Lightning | `get_lightning` | preferred | `instantaneous` |
| Cyclone proximity / track | `get_cyclone_track` | conditional (required if any active system) | `bulletin_period` |
| Surface current speed | `get_currents` (derived) | optional | `instantaneous` |
| Precipitation / visibility proxy | `get_weather` | optional | `instantaneous` |

If **any required factor is missing**, the verdict is `INSUFFICIENT_EVIDENCE` and the
answer states which input was unavailable and why (e.g. *"lightning could not be checked —
the IMD service requires credentials"*).

### 4.2 Governing constraints (applied before thresholds)

| Constraint | Effect |
|---|---|
| An active official warning covering the area/time whose class implies danger to the user's craft | Verdict is capped at `UNSAFE`, regardless of favourable model values. The warning is quoted and attributed |
| An active cyclone whose published forecast cone intersects the area/time | Capped at `UNSAFE`; `disposition = REVIEW_REQUIRED` |
| A warning with an unresolved area (`AMBIGUOUS_AREA`) covering the named region | Verdict capped at `MARGINAL` at best, with the warning text quoted and the ambiguity stated |

**An official warning always outranks ORCA's own threshold evaluation.** ORCA does not
"disagree" with IMD; if the model data look benign under an active warning, ORCA reports
the warning as governing and notes the discrepancy.

### 4.3 Threshold set `small_craft_v0.1`

> **Status: SCIENTIFIC VALIDATION REQUIRED.** These are **initial engineering parameters**
> chosen to make the system implementable and testable. They are configuration, not
> science, and must be reviewed against Indian marine safety guidance and small-craft
> operating practice before any operational use. Every answer citing them exposes the
> threshold set id and its validation status.

| Factor | FAVOURABLE | MARGINAL | UNFAVOURABLE | UNSAFE |
|---|---|---|---|---|
| Significant wave height `Hs` (m) | < 1.5 | 1.5 – 2.5 | 2.5 – 3.5 | ≥ 3.5 |
| Wind speed (m s⁻¹) | < 8 | 8 – 12 | 12 – 17 | ≥ 17 |
| Wind gust (m s⁻¹) | < 11 | 11 – 15 | 15 – 21 | ≥ 21 |
| Swell height (m) | < 1.5 | 1.5 – 2.5 | 2.5 – 3.5 | ≥ 3.5 |
| Swell period (s) with `swell ≥ 1.5 m` | < 10 | 10 – 13 | ≥ 13 | — (long-period swell raises one level) |
| Lightning within 50 km in window | none | detected > 3 h ago | detected < 3 h ago | active alert in force |
| Cyclone distance / cone | > 500 km, no cone | 300–500 km | cone within 48 h | cone intersects window |
| Surface current speed (m s⁻¹) | < 0.5 | 0.5 – 1.0 | 1.0 – 1.5 | ≥ 1.5 |

**Vessel-class parameterisation (P1).** `small_craft` is the default profile. When
`get_vessel_context` exists, thresholds scale by vessel class; the profile used is always
named in the answer. Applying a small-craft threshold to a larger vessel is an
over-caution, and the answer says which profile was applied.

### 4.4 Example
```
Hs 2.4 m        → MARGINAL   (limiting)
wind 11.3 m/s   → MARGINAL
swell 1.2 m     → FAVOURABLE
lightning       → not evaluated (AUTH_REQUIRED)
warning         → none active
cyclone         → none active
──────────────────────────────────────────
verdict = MARGINAL · limiting = significant_wave_height
confidence = medium (one preferred input missing; lead time 12.5 h; node distance 6.2 km)
```

---

## 5. FISHING_SUITABILITY Assessment

### 5.1 Inputs

| Factor | Tool | Necessity | Notes |
|---|---|---|---|
| PFZ advisory | `get_pfz` | **required if available** | The authoritative product; ORCA reports it, never reproduces it |
| Chlorophyll-a | `get_chlorophyll` | preferred | Productivity proxy |
| SST | `get_sst` | preferred | |
| SST anomaly | `get_sst` or derived | preferred | Source-published anomaly preferred over ORCA-derived |
| Thermal front (P1) | derived | optional | SCIENTIFIC VALIDATION REQUIRED |
| Surface currents | `get_currents` | optional | Operational context |

### 5.2 The PFZ rule — the most important rule in this document

1. If a PFZ advisory is available, it is the **primary evidence**, cited to INCOIS.
2. If PFZ is available only as imagery (`RASTER_ONLY`), ORCA reports *"the PFZ advisory
   covers your area (imagery only — exact zone boundaries are not available)"* and does
   **not** perform any point-in-zone test.
3. If PFZ is unavailable, ORCA **must not reconstruct it**. It may report SST and
   chlorophyll conditions as **ORCA-derived indicators**, explicitly labelled as such, and
   must state that the PFZ advisory itself was unavailable.
4. The words "Potential Fishing Zone" and "PFZ" are reserved for the authoritative product.
   ORCA's own indicator is named `orca_productivity_indicator` and is never abbreviated to
   PFZ in any language.

This rule exists because reproducing a national advisory product from raw satellite fields
without the published methodology and validation would be scientifically unsound and would
misrepresent an official product.

### 5.3 Indicator rules `fishing_v0.1`

> **Status: SCIENTIFIC VALIDATION REQUIRED.** Productivity–catchability relationships are
> region-, season- and species-dependent. These are placeholder engineering parameters
> that make the pipeline testable; they must be validated against regional fisheries
> science and, ideally, observed outcomes before operational use.

| Factor | FAVOURABLE | MARGINAL | UNFAVOURABLE |
|---|---|---|---|
| PFZ advisory | area intersects advisory | adjacent (< 25 km) | no advisory covering the area |
| Chlorophyll-a vs local median (same field) | > 1.3 × median | 0.8 – 1.3 × | < 0.8 × |
| SST anomaly (vs stated baseline) | −0.5 … +1.0 °C | ±1.0 … 2.0 °C | > 2.0 °C deviation |
| Thermal front within 20 km (P1) | present | — | absent |
| Chlorophyll coverage fraction | ≥ 0.6 | 0.3 – 0.6 (reduced confidence) | < 0.3 ⇒ not evaluated |

**Combination.** Unlike SAFETY, fishing suitability is **corroborative**: PFZ presence
dominates; secondary indicators raise or lower confidence rather than overriding the
advisory. If PFZ is unavailable, the verdict rests on ORCA-derived indicators alone and
confidence is capped at `medium`.

**Comparative language only.** ORCA says "chlorophyll is above the local median for this
field" — never "chlorophyll is high", which implies an absolute standard ORCA has not
validated.

---

## 6. ECOLOGICAL Assessment (P1)

| Aspect | Detail |
|---|---|
| Question | Is the water in an anomalous or degraded state? |
| Inputs | SST anomaly, chlorophyll anomaly, KD490/TSM (turbidity), persistence of anomalies over time, MPA proximity |
| Verdicts | `NOMINAL` · `ANOMALOUS` · `DEGRADED` · `INSUFFICIENT_EVIDENCE` |
| Status | **P1 · SCIENTIFIC VALIDATION REQUIRED** |
| HAB | Harmful-algal-bloom signalling is **not implemented**. High chlorophyll alone is not a bloom indicator, and ORCA will not imply one. Implementation requires an authoritative feed or a validated methodology and would carry a public-health escalation path |
| Rule | Ecological findings are descriptive, never a health or consumption recommendation |

The domain is specified now so the architecture accommodates it, and is explicitly
excluded from the MVP verdict set.

---

## 7. REGULATORY Assessment

| Aspect | Detail |
|---|---|
| Question | Is operating at this location permitted, restricted or prohibited? |
| Inputs | `get_maritime_boundaries`: EEZ, territorial sea, international boundaries, MPAs, restricted zones |
| Verdicts | `PERMITTED` · `RESTRICTED` · `PROHIBITED` · `UNKNOWN` |
| Determinism | Entirely deterministic — point/area-in-polygon over versioned geometry |
| Coverage honesty | Only boundary types with a configured authoritative source are evaluated. Others return `UNKNOWN` for that type and are listed as not evaluated. An EEZ polygon is never used as a proxy for a fishing regulation zone |
| Version binding | Every result names the dataset, its version and effective date |
| **Advisory only** | Boundary results are advisory context. They are **not** legal determinations and **not** navigational authority. The disclaimer is attached structurally at the API layer, not left to the narrative |
| Escalation | `PROHIBITED` is surfaced prominently and the recommendation cannot suggest the activity at that location |
| Near-boundary | Distance to the boundary is reported so a point 400 m inside is not presented with false confidence given dataset precision |

---

## 8. Cross-Domain Synthesis

The four verdicts are combined only in **language**, by two deterministic rules:

```
limiting_domain = the domain whose verdict most constrains action
                  priority: REGULATORY(PROHIBITED) > SAFETY(UNSAFE)
                          > SAFETY(UNFAVOURABLE) > SAFETY(MARGINAL)
                          > FISHING(UNFAVOURABLE) > …

headline        = state the limiting domain first, then the non-limiting result,
                  then name the limiting factor
```

| Situation | Headline pattern |
|---|---|
| Fishing FAVOURABLE + Safety MARGINAL | "Fishing conditions look favourable, but sea state is marginal — wave height is the limiting factor, not fish availability." |
| Fishing FAVOURABLE + Safety UNSAFE | "Do not go. Conditions are unsafe for small craft, even though fish availability looks good." |
| Fishing UNFAVOURABLE + Safety FAVOURABLE | "It is safe to sail, but there is little indication of good fishing in this area at this time." |
| Regulatory PROHIBITED | "This location falls inside a restricted area (advisory information). Regardless of conditions, operating here is not permitted." |
| Any domain INSUFFICIENT_EVIDENCE | "I cannot assess <domain> because <missing input> was unavailable. Here is what I can say: …" |

**Never produced:** a single combined score, a star rating, a percentage, or a
"go/no-go" that hides which domain drove it.

---

## 9. Confidence Model

Confidence is computed per domain, deterministically, from five factors:

| Factor | Effect |
|---|---|
| Evidence sufficiency | Every required input present and fresh → `high` eligible; any preferred input missing → cap `medium`; any required input missing → `INSUFFICIENT_EVIDENCE` |
| Data quality | Any `suspect` or `degraded` driver → −1 level |
| Forecast lead time | > 24 h → −1 level; > 48 h → −2 levels |
| Spatial mismatch | Node distance > 1.5 × grid spacing → −1 level |
| Conflicts | Any material conflict on a driver → −1 level; safety-relevant → also `REVIEW_REQUIRED` |

```
start = high
apply modifiers → clamp to {low, medium, high}
```

Confidence is always shown with **its reasons**: *"medium — lightning could not be
checked, and two wave forecasts disagree by 0.7 m"*. No numeric confidence is displayed;
false precision is worse than a qualitative label
(`02_FRONTEND_DESIGN_SPEC.md` §12).

---

## 10. Conflict Policy

| Policy | When | Behaviour |
|---|---|---|
| `retain_both_and_use_conservative` | Safety-relevant parameter | The more adverse value drives the verdict; both are reported; `REVIEW_REQUIRED` |
| `retain_both_and_report` | Non-safety parameter, material conflict | Both reported; confidence reduced; verdict from the primary-authority value |
| `prefer_primary_authority` | Documented, non-material difference within tolerance | Primary used; the alternative is recorded in provenance |
| `insufficient_to_resolve` | Conflict prevents any defensible verdict | `INSUFFICIENT_EVIDENCE` for that domain |

**Materiality tolerances** (initial engineering parameters, **SCIENTIFIC VALIDATION
REQUIRED**): `Hs` ± 0.5 m or 20 %; wind ± 3 m s⁻¹ or 20 %; SST ± 0.5 °C; chlorophyll
± 50 % (log-distributed); current speed ± 0.3 m s⁻¹.

The losing value is **never deleted**. Both remain in `conflicts` and in the evidence
panel with their sources.

---

## 11. Recommendation Categories

The delivered `Recommendation` carries a category derived from the assessment set:

| Category | Condition |
|---|---|
| `PROCEED_WITH_CONTEXT` | No domain worse than FAVOURABLE/MARGINAL, no prohibition |
| `PROCEED_WITH_CAUTION` | SAFETY MARGINAL, or a material conflict on a safety driver |
| `ADVISE_AGAINST` | SAFETY UNFAVOURABLE |
| `DO_NOT_PROCEED` | SAFETY UNSAFE, or REGULATORY PROHIBITED |
| `CANNOT_ADVISE` | Any required safety input missing → no safety statement is issued |
| `DEFER_TO_OFFICIAL` | An active official warning governs; ORCA quotes it and adds context only |

`DEFER_TO_OFFICIAL` is important: when IMD has issued a warning, ORCA's job is to
**convey and contextualise** it, not to produce a competing judgement.

---

## 12. Escalation and Human Review

`review_gate` (`07_LANGGRAPH_WORKFLOW_SPEC.md` §7) computes the disposition:

| Disposition | Conditions (any) |
|---|---|
| `AUTO_RELEASE` | All required evidence present · no `UNSAFE` verdict · no material safety-relevant conflict · confidence ≥ medium on issued verdicts · no data beyond staleness policy |
| `REVIEW_REQUIRED` | SAFETY `UNSAFE` for an operational role · material safety-relevant conflict unresolved · confidence `low` on a safety verdict · an active governing warning could not be retrieved while other data suggest benign conditions · cyclone-related output · alert fan-out above the configured size · REGULATORY `PROHIBITED` in a broadcast context |
| `BLOCKED` | No safety input at all for a safety-relevant question · a hard policy violation (e.g. a request to issue an official advisory) |

**Where review is deliberately NOT inserted:** routine informational lookups, data
queries, definition questions, single-domain ocean-condition reports with complete
evidence, and any `AUTO_RELEASE` case. Inserting review everywhere would make the system
unusable and would train reviewers to rubber-stamp — the opposite of a safety control.

### 12.1 Override representation
An override never mutates the original assessment. It inserts a new assessment with
`superseded_by` set on the original, plus a `human_reviews` record containing reviewer
identity, role, decision, rationale (required), pre- and post-review artifacts, and
timing. The provenance chain gains an `interpretation` record attributed to the reviewer,
so an audit can distinguish machine and human judgement
(`09_DATABASE_SPEC.md` §5, `20_OBSERVABILITY_AND_AUDIT_SPEC.md`).

Delivered answers that passed review are marked `Reviewed by <role> at <time>`.

---

## 13. Parameter Governance

Every numeric threshold in this document is:

1. **Configuration**, not a code constant — versioned in
   `config/thresholds/{set_id}.yaml`;
2. **Identified** in output by `threshold_set` id and version;
3. **Labelled** with its validation status (`SCIENTIFIC VALIDATION REQUIRED` until
   reviewed);
4. **Traceable** — each threshold record carries a `rationale` field and, once validated,
   a `validation_reference`;
5. **Tested** — the boundary of every threshold has a test case in the scenario matrix
   (`15_EVALUATION_AND_TESTING_SPEC.md`).

```yaml
# config/thresholds/small_craft_v0.1.yaml
set_id: small_craft_v0.1
status: SCIENTIFIC_VALIDATION_REQUIRED
applies_to: {vessel_class: small_craft}
rationale: >
  Initial engineering parameters selected to make the assessment pipeline implementable
  and testable. Not derived from a validated study. Requires review against Indian marine
  safety guidance and regional small-craft operating practice before operational use.
factors:
  significant_wave_height:
    unit: m
    bands: {favourable: [0, 1.5], marginal: [1.5, 2.5],
            unfavourable: [2.5, 3.5], unsafe: [3.5, null]}
```

**Validation path.** Thresholds move from `SCIENTIFIC_VALIDATION_REQUIRED` to `VALIDATED`
only via: (a) alignment with published official guidance, with the reference recorded, or
(b) a documented review by a qualified domain reviewer, or (c) retrospective validation
against observed outcomes. Until then, every answer that uses them says so.

---

## 14. What ORCA Will Not Do

| Prohibited | Why |
|---|---|
| Emit a single combined risk score | Destroys the safety/productivity distinction that is the point of the system |
| Present its recommendation as an official advisory | It is not one; structurally prevented |
| Reconstruct a PFZ advisory from raw fields | Misrepresents a national product; scientifically unsound without the published methodology |
| Say "conditions are safe" when a safety input is missing | Absence of evidence is not evidence of safety |
| Silently pick a winner between conflicting sources | Hides the disagreement that the user needs to know about |
| Use a monthly analysis for a next-morning verdict | Temporal misrepresentation |
| Infer a harmful algal bloom from chlorophyll | Not a validated indicator; public-health implications |
| Issue a navigational route or treat boundaries as legal truth | Not a navigation system; charts and NtM remain authoritative |
| Display numeric confidence percentages | False precision on a qualitative judgement |
