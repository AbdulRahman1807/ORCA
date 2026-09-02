# ORCA — Demo and SIH Presentation Specification

**Document:** 16 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** PROPOSED — depends on MVP completion (`22_MVP_SCOPE.md`)

---

## 1. The One Thing the Demo Must Prove

> **NOT:** "we put existing marine data on a map."
> **BUT:** "ORCA turns heterogeneous authoritative marine information into a
> context-aware, provenance-backed reasoning workflow."

Every second of the demo serves that sentence. A judge who has seen ten dashboards must
leave able to say what ORCA does that a dashboard cannot:

1. It **decomposes** a natural question into a retrieval and analysis plan.
2. It **integrates** sources that do not share a projection, cadence, vocabulary or
   validity window.
3. It **separates** safety from productivity and can say they disagree.
4. It **shows its evidence** — every number traceable to source, dataset and time.
5. It **degrades honestly** — missing sources are stated, not hidden.
6. It **defers to authority** — official warnings are quoted, never replaced.

---

## 2. Demo Flow (4 minutes 30 seconds)

| # | Time | Segment | On screen | Said aloud |
|---|---|---|---|---|
| 0 | 0:00–0:30 | **The problem** | Split screen: several separate portals | "A fisher near Kochi needs nine answers from six systems before dawn. Each is in a different format, projection and validity window. None answers the question they actually asked." |
| 1 | 0:30–0:45 | **The question** | Type the query in ORCA | "*I'm near Kochi. Is tomorrow morning a good time to go fishing, and if not, why?*" |
| 2 | 0:45–1:15 | **Decomposition** | Live plan panel: 9 steps, tools named, domains listed | "ORCA's Planner decides what is actually needed — nine capability calls across three domains. Notice it does not fetch everything; ask it about a warning and it fetches one thing." |
| 3 | 1:15–2:00 | **Live retrieval** | Streamed tool checklist with sources, timings, and **one visible failure and one fallback** | "INCOIS ERDDAP — live. CMEMS — live. Boundaries — live. Lightning: the IMD service requires credentials, so it is reported as not evaluated. Wind came from a fallback source, and ORCA says so." |
| 4 | 2:00–2:30 | **Cross-source reasoning** | Alignment panel: grids and windows normalised; derived anomaly | "These products have different grids, cadences and validity windows. ORCA aligns them deterministically and records exactly how — the 10-day analysis is kept as context, not used as tomorrow's forecast." |
| 5 | 2:30–3:00 | **The map** | Layers: PFZ (raster badge), SST, chlorophyll, Hs, EEZ; legends; freshness dots | "Every layer carries its source, its validity time and its freshness. PFZ is badged 'imagery only' because that is what was actually available." |
| 6 | 3:00–3:40 | **The answer** | Two cards side by side: FISHING **FAVOURABLE**, SAFETY **MARGINAL** | "This is the differentiator. Good fishing and marginal safety at the same time — a single risk score would have averaged that into something useless. ORCA names the limiting factor: wave height, not fish." |
| 7 | 3:40–4:00 | **Evidence** | Click a claim → provenance record → derivation chain | "Every number resolves to a source, a dataset, a retrieval time and a validity time. The anomaly shows its inputs and its method. This is why the recommendation exists." |
| 8 | 4:00–4:20 | **Conflict + human review** | Conflict card (2.4 m vs 3.1 m) → review queue → officer approves with rationale | "Two authoritative forecasts disagree materially on a safety variable. ORCA does not pick a winner silently — it keeps both, uses the conservative value and escalates to a human." |
| 9 | 4:20–4:35 | **Multilingual** | Same query in Malayalam → same verdict, same numbers | "Same evidence, same verdict, the user's language. Numbers and official text are never translated away." |
| 10 | 4:35–4:45 | **The boundary** | Disclaimer panel | "ORCA is not an official advisory service and does not replace INCOIS or IMD. It cites them. That line is enforced in the database, not just written in the UI." |

**Total: 4:45.** A 3-minute cut drops segments 4 and 9; a 5-minute cut adds a live
alert firing on a geofence.

---

## 3. Segment Detail

### 3.1 Opening problem (0:00–0:30)
Show the actual fragmentation — a wave forecast, a bulletin, a satellite product, a
boundary map — then the question a person actually asks. Do **not** claim these systems are
inadequate; they are excellent. The gap is integration and reasoning. Judges from ISRO will
respect that framing and will react badly to the opposite.

### 3.2 Planner decomposition (0:45–1:15)
The plan panel must show:
```
intent            fishing_suitability
domains           SAFETY · FISHING_SUITABILITY · REGULATORY
required evidence official_warning_status · wave_conditions · wind_conditions
steps             9 capability calls (tool names, not URLs)
```
Then the **contrast shot**: type "Is there a warning for the Kerala coast right now?" and
show a **one-step** plan. This is the fastest way to prove the Planner is doing real work
rather than always calling everything.

### 3.3 Live retrieval (1:15–2:00)
Rules for this segment:
- At least three sources must be **live** (INCOIS ERDDAP is verified and unauthenticated —
  it is the reliable backbone of the demo).
- At least one failure must be visible and **explained**.
- One fallback must be visible and **stated**.
- If a source is pre-staged for reliability, the UI shows "cached, retrieved at <time>" and
  the presenter says so. **Never present cached data as live.**

### 3.4 Answer (3:00–3:40)
The two-card shot is the money shot. Rehearse landing on it at exactly 3:00 with both
cards visible without scrolling.

### 3.5 Failure/fallback demonstration (built into segment 3)
Do not simulate a failure with a fake button. Use a genuinely unavailable capability —
`get_lightning` without IMD credentials is real, honest, and already true.

### 3.6 Human override (4:00–4:20)
Show: conflict detected → `REVIEW_REQUIRED` → reviewer screen with both values → approve
with rationale → the delivered answer carries "Reviewed by officer at <time>". Then show
the audit record. Roughly 20 seconds; the audit view is what makes it credible.

### 3.7 Multilingual (4:20–4:35)
Show the Malayalam answer beside the English one with the numbers highlighted as identical.
State the hard gate: **numeric fidelity is automatically enforced, and a localised answer
that fails it is never delivered.**

---

## 4. Demo Environment and Reliability

| Concern | Mitigation |
|---|---|
| Venue network blocks a government host | **Rehearsed offline replay mode**: a recorded run replays from checkpoints with a persistent "REPLAY — recorded <date>" banner. Never silently faked |
| A source is slow | Per-tool timeouts are already enforced; the plan shows the timeout as a real outcome |
| IMD credentials unavailable | Already the honest state; the demo *uses* it as the failure segment |
| WMS unverifiable at the venue | PFZ raster path pre-staged and labelled; the three-branch design is explained |
| LLM provider outage | Template-answer fallback demonstrated — a legitimate resilience story |
| Laptop/display failure | Recorded video of the same flow, clearly labelled as a recording |

**Rehearsal requirement:** the full flow is rehearsed end-to-end at least five times,
including at least one run in offline replay mode and one with a deliberately failing
source.

---

## 5. Key Judge Talking Points

Six sentences, memorised:

1. "ORCA is an integration and reasoning layer over INCOIS, IMD, ISRO/MOSDAC and CMEMS —
   it does not replace them, it cites them."
2. "The Planner decomposes the question; nine sources become one answer, and it only
   fetches what the question needs."
3. "Safety and fishing suitability are assessed separately, so ORCA can say 'good fishing,
   unsafe sea' — a single risk score cannot."
4. "Every number is traceable to a source, dataset, retrieval time and validity time; we do
   not claim hallucination-free AI, we claim source-grounded generation with claim-level
   evidence binding and a measured ungrounded-claim rate."
5. "Failures are visible: authentication requirements, unavailable endpoints, raster-only
   products and cross-source conflicts are all reported, never hidden."
6. "We verified INCOIS ERDDAP live — HTTP 200, catalogue accessible, datasets enumerated.
   IMD needs credentials — we saw 403. The WMS endpoint is identified but unverified
   because our campus network could not resolve the host. We are precise about what is
   proven."

Point 6 is disproportionately valuable: **honesty about verification status is itself a
differentiator** in a competition full of over-claiming.

---

## 6. Likely Judge Objections and Precise Answers

| # | Objection | Answer |
|---|---|---|
| 1 | "INCOIS already publishes PFZ. What do you add?" | "We do not reproduce PFZ — we retrieve and cite it, then answer the question the fisher actually asked by combining it with safety, boundaries and conditions, with the evidence attached. INCOIS answers 'where might fish be'; ORCA answers 'should I go tomorrow morning, and why not'." |
| 2 | "Why agents? Why not one prompt with tool calls?" | "Because the stages have different failure modes and different validation gates. Retrieval is validated before reasoning; a validation failure re-plans without regenerating text; only the high-impact stage is gated for human review; and verdicts come from a deterministic rule engine that an LLM cannot alter. One monolithic prompt gives up all four properties." |
| 3 | "Why not just a dashboard?" | "A dashboard requires the user to already know which nine products to open and how to reconcile them. ORCA takes the question and produces the reconciliation, with the evidence. And a dashboard cannot tell you that two authoritative forecasts disagree by 0.7 m on a safety variable." |
| 4 | "What is actually intelligent here?" | "Four things: deciding what to retrieve for this specific question; deciding whether the evidence is sufficient to answer; detecting and handling cross-source conflict; and expressing the result truthfully with citations. The numbers themselves are deterministic — deliberately." |
| 5 | "How do you prevent hallucination?" | "We do not claim to eliminate it. We constrain generation to a fixed evidence set assembled before generation, we validate every material claim against that set, we reject numeric drift, and if validation fails twice we fall back to a deterministic template. We also measure the residual ungrounded-claim rate rather than asserting zero." |
| 6 | "What happens when IMD is unavailable?" | "Warnings are reported as not evaluated — never assumed absent. Wind can fall back to another source with the fallback stated. If a required safety input is missing, ORCA issues no safety verdict: `CANNOT_ADVISE`. Absence of evidence is never treated as evidence of safety." |
| 7 | "What if sources disagree?" | "We keep both, quantify the difference against a per-parameter tolerance, use the conservative value for safety, show both to the user and escalate to human review. We never silently pick a winner." |
| 8 | "Can it work without every API?" | "Yes. Three P0 tools are backed by INCOIS ERDDAP, which we verified as publicly accessible. Every other capability degrades explicitly with a named reason. The architecture has no single point of failure except honesty." |
| 9 | "How do you validate marine recommendations?" | "Two separate answers. Engineering correctness — deterministic kernels tested against reference values, contract tests per adapter, a scenario matrix including disagreement cases. Scientific validity — our thresholds are labelled `SCIENTIFIC VALIDATION REQUIRED` and shown as such in the UI, because they are engineering parameters, not validated science. We are not going to pretend otherwise." |
| 10 | "How do you know your PFZ reasoning is correct?" | "We do not reason about PFZ internals. We retrieve the advisory and cite it. If only imagery is available we say so and refuse point-in-zone tests. If it is unavailable we report SST and chlorophyll as ORCA-derived indicators — explicitly not called PFZ, in any language." |
| 11 | "Are you replacing official advisories?" | "No. ORCA never issues an official advisory; that is enforced by a database constraint and by an output validator, not just by wording. When a warning is in force, ORCA quotes it verbatim, attributes it, and defers to it." |
| 12 | "What is the role of humans?" | "Review where it changes outcomes: unsafe verdicts in operational contexts, unresolved safety-relevant conflicts, low confidence, cyclone output and large alert fan-outs. Not everywhere — universal review trains reviewers to rubber-stamp." |
| 13 | "Why LangGraph?" | "We need typed state with reducers for parallel fan-in, conditional edges that can route backwards for re-planning, durable interrupts for human review that survive a restart, and replayable checkpoints for audit. That is a state machine, and LangGraph gives it to us with persistence." |
| 14 | "What is your MVP?" | "One excellent vertical slice: conversational query → planner decomposition → five-plus live tools across three sources → canonical normalisation with provenance → spatiotemporal alignment → separate safety and fishing assessments → evidence panel and map. Everything else is explicitly deferred and written down." |
| 15 | "What have you actually verified?" | "INCOIS ERDDAP: DNS, TCP, TLS with a valid certificate, HTTP 200, catalogue accessible, datasets enumerated including OceanSat colour, SST/anomaly, Argo products and ASCAT winds. IMD: reachable, 403 unauthenticated — an access requirement, not an outage. CMEMS and MarineRegions: reachable. INCOIS WMS: layers identified, verification pending because our campus network could not resolve the host. That is the complete list." |
| 16 | "What is still theoretical?" | "Everything marked `IMPLEMENTATION REQUIRED`, `PENDING VERIFICATION` or `SCIENTIFIC VALIDATION REQUIRED` in our gap register — including IMD credentials, PFZ vector availability, MOSDAC integration, thresholds, and all multilingual quality claims. It is document 25 and we hand it over as-is." |
| 17 | "How does this scale?" | "Retrieval is cached per parameter cadence, tool calls are idempotent and parallel, the graph is horizontally scalable behind a checkpoint store, geometry lives in PostGIS with spatial indexes, and grids live in object storage rather than rows. The binding constraints are upstream rate limits and satellite product latency, and we budget outbound calls per source specifically to be a good citizen of public infrastructure." |
| 18 | "What if the network is down?" | "Interactive answers require live data; without it ORCA says so rather than guessing. For the demo we have a rehearsed replay mode with a permanent 'recorded' banner. Cached answers in the mobile client always show their retrieval time." |
| 19 | "What makes this SIH-worthy?" | "It addresses every element of SIH26176 — conversational interaction, intent detection, decomposition, specialised agents, autonomous discovery, spatiotemporal reasoning, evidence-backed recommendations, geospatial visualisation, multilingual interaction, proactive alerts, geofencing, explainability — with an architecture that is implementable and honest about what is proven versus proposed. Document 27 traces every requirement to a component, a test and a demo moment." |
| 20 | "Isn't this just an LLM with API calls?" | "The LLM chooses what to fetch and how to say it. It never produces a number and never decides a verdict. Those come from deterministic kernels and a rule engine. If you removed the LLM entirely, ORCA would still produce correct assessments — it would just express them in a template." |

---

## 7. Anti-Patterns to Avoid on Stage

| Do not | Because |
|---|---|
| Say "hallucination-free" | Indefensible; a knowledgeable judge will pursue it |
| Show a single "risk score" | It contradicts the core design and the demo's own message |
| Claim ORCA replaces or improves on INCOIS/IMD | ISRO judges; also untrue |
| Present cached data as live | Fatal to credibility if noticed |
| Quote accuracy numbers not produced by the evaluation harness | Fabricated benchmarks are the fastest way to lose |
| Hide a failed source | The honesty *is* the differentiator |
| Over-explain the architecture before showing the answer | Show the outcome, then the mechanism |
| Call an ORCA-derived indicator "PFZ" | Misrepresents a national product |

---

## 8. Supporting Materials

| Artifact | Purpose |
|---|---|
| One-page architecture diagram | `23_ARCHITECTURE_DIAGRAMS.md` §1, printed |
| Verification status card | The six-line summary from §5 point 6 |
| Gap register | `25_GAP_AND_VALIDATION_REGISTER.md`, handed over as-is |
| Traceability matrix | `27_REQUIREMENTS_TRACEABILITY_MATRIX.md` for the "did you cover everything?" question |
| Judge Q&A | `26_SIH_JUDGE_QA.md`, the long form of §6 |
| Recorded demo video | Failure backup, labelled |

---

## 9. Demo Readiness Checklist

- [ ] Vertical slice runs end-to-end on the Kochi query against live INCOIS ERDDAP
- [ ] ≥ 3 sources live; ≥ 1 genuine failure visible and explained; ≥ 1 fallback stated
- [ ] Two-card disagreement scenario reproducible on demand
- [ ] Evidence panel resolves a claim to a provenance record and a derivation chain
- [ ] Conflict → review → override → audit demonstrated
- [ ] Malayalam (or Hindi) round-trip with numeric-fidelity gate passing
- [ ] Offline replay mode rehearsed with the "recorded" banner visible
- [ ] Every displayed threshold shows its validation status
- [ ] No statement in the script exceeds what `25_GAP_AND_VALIDATION_REGISTER.md` supports
- [ ] Five full rehearsals completed, including one failure-mode run
