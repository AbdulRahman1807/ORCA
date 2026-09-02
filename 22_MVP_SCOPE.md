# ORCA — MVP Scope

**Document:** 22 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** **CONTRACTUAL** — changes require a recorded decision in `24_ENGINEERING_DECISIONS.md`

---

## 1. The MVP Thesis

> **One excellent end-to-end vertical slice that proves the architecture's
> differentiator — not a thin version of every feature.**

The differentiator is **not** "marine data on a map". It is:

```
   conversational marine query
            ↓
   planner decomposition                    ← the system decides what to fetch
            ↓
   multiple authoritative data sources      ← heterogeneous, real, some failing
            ↓
   spatial / temporal normalisation         ← deterministic, recorded
            ↓
   safety + fishing suitability reasoning   ← SEPARATE, may disagree
            ↓
   provenance / evidence                    ← every number traceable
            ↓
   map + natural-language answer            ← with honest gaps
```

If a judge sees that chain work once, on a real query, against real sources, with a real
failure handled honestly — the architecture is proven. Adding routes, vessels, eight
languages and MOSDAC before that chain works proves nothing and risks everything
(`21_RISK_REGISTER.md` R-16).

**Equally important:** the MVP is not a static dashboard. A dashboard cannot decompose a
question, cannot detect that two forecasts disagree, cannot state which input was
unavailable, and cannot say "good fishing, unsafe sea".

---

## 2. The MVP Query

> **"I'm near Kochi. Is tomorrow morning a good time to go fishing, and if not, why?"**

Plus one contrast query proving the Planner is selective:

> **"Is there any warning in force for the Kerala coast right now?"** → a **one-step** plan.

---

## 3. MUST-HAVE (the MVP is not complete without these)

### 3.1 Conversation and context
| # | Requirement | Acceptance |
|---|---|---|
| M-01 | Accept a natural-language marine query in English | Query submitted via API and UI |
| M-02 | Deterministic location resolution (named coastal place + coordinates) | "near Kochi" → 9.93 N, 76.26 E with the gazetteer entry recorded |
| M-03 | Deterministic time-window resolution, IST-aware | "tomorrow morning" → an explicit UTC window shown to the user |
| M-04 | Ambiguity produces one clarifying question, never a guess | Ambiguous place name does not trigger retrieval |
| M-05 | Multi-turn context carry-over | "what about Thursday?" reuses the location |

### 3.2 Planning
| # | Requirement | Acceptance |
|---|---|---|
| M-06 | Planner produces a typed, validated plan | Plan persisted and visible in the run trace |
| M-07 | Plan is **selective** | Warning lookup plans one tool; fishing query plans ≥ 5 |
| M-08 | Bounded re-plan on evidence gaps | Re-plan fires at most twice |

### 3.3 Retrieval
| # | Requirement | Acceptance |
|---|---|---|
| M-09 | ≥ 5 P0 capability tools implemented and callable | Contract tests pass |
| M-10 | ≥ 3 distinct external sources reached live in one run | INCOIS ERDDAP + CMEMS + MarineRegions (ERDDAP is the verified, unauthenticated backbone) |
| M-11 | Parallel fan-out with partial-failure tolerance | One failing tool does not stall the run |
| M-12 | Explicit failure states surfaced | `AUTH_REQUIRED`, `RASTER_ONLY`, `NO_ACTIVE_WARNING`, `SOURCE_UNAVAILABLE` all demonstrable |
| M-13 | Fallback recorded and stated | `fallback_used` in provenance **and** in the answer text |
| M-14 | No silent substitution | Asserted by test for wave/SST and PFZ/vector cases |

### 3.4 Canonical data and provenance
| # | Requirement | Acceptance |
|---|---|---|
| M-15 | All retrieved data normalised to the canonical schema | Validation at every boundary |
| M-16 | Every value carries full provenance | Source, dataset, unit, valid_time, retrieved_at, resolution, quality |
| M-17 | Derived values carry a recomputable derivation | Method, version, inputs, params |
| M-18 | Provenance chain queryable end-to-end | `GET /runs/{id}/provenance/{pid}/chain` returns the chain |

### 3.5 Geospatial and temporal reasoning
| # | Requirement | Acceptance |
|---|---|---|
| M-19 | CRS normalisation with explicit CRS everywhere | Round-trip tests pass |
| M-20 | Geodesic bbox/distance (never degree arithmetic) | Reference tests at multiple latitudes |
| M-21 | Masking + honest coverage reporting | Cloud-masked chlorophyll reports `coverage_fraction` |
| M-22 | Point extraction with recorded method and node distance | Present in provenance |
| M-23 | Temporal alignment with representativeness rules | A monthly product is refused for a 4-hour window |
| M-24 | One derived indicator (SST anomaly vs a stated baseline) | Labelled `derived`, baseline named |
| M-25 | Point-in-polygon boundary evaluation | EEZ containment with dataset version and `advisory_only` |

### 3.6 Reasoning
| # | Requirement | Acceptance |
|---|---|---|
| M-26 | **SAFETY and FISHING_SUITABILITY assessed separately** | Two independent verdicts, always |
| M-27 | REGULATORY assessed deterministically | `PERMITTED`/`RESTRICTED`/`UNKNOWN` with version |
| M-28 | **A disagreement scenario is demonstrable** | FAVOURABLE fishing + MARGINAL/UNSAFE safety |
| M-29 | Limiting factor named | Headline states which factor governs |
| M-30 | Evidence sufficiency enforced | Missing required input ⇒ `INSUFFICIENT_EVIDENCE`, never a guess |
| M-31 | Official warnings govern and are quoted verbatim | `DEFER_TO_OFFICIAL` path works |
| M-32 | Conflict detection with both values retained | `CONFLICTING_SOURCES` surfaced |
| M-33 | Qualitative confidence with stated reasons | No numeric confidence anywhere |
| M-34 | Thresholds external, versioned, status-labelled | `SCIENTIFIC VALIDATION REQUIRED` visible in the UI |

### 3.7 Output
| # | Requirement | Acceptance |
|---|---|---|
| M-35 | Evidence-bound narrative | Every material claim carries `evidence_ids` |
| M-36 | Numeric fidelity enforced | Numeric drift fails validation |
| M-37 | Non-official-advisory labelling | Enforced by validator **and** DB constraint |
| M-38 | "Not evaluated" list with reasons | Rendered in card and narrative |
| M-39 | Concise reasoning summary, no chain-of-thought | Asserted by test |
| M-40 | Deterministic template fallback | Works with the LLM provider disabled |

### 3.8 Interface
| # | Requirement | Acceptance |
|---|---|---|
| M-41 | Conversation pane with streamed run progress | Node/tool events only |
| M-42 | Map with ≥ 4 layers, legends, source and freshness badges | SST, chlorophyll, waves, EEZ (+ PFZ where available) |
| M-43 | Assessment cards per domain | Verdict, confidence, drivers, gaps |
| M-44 | Evidence panel L1→L2→L3 | Claim → provenance record → derivation |
| M-45 | Unavailable layers listed with reasons | Never silently omitted |
| M-46 | Loading/error/empty states for every canonical code | Distinct copy for `NO_DATA` vs `SOURCE_UNAVAILABLE` |
| M-47 | Desktop layout complete; mobile readable | Verdict visible without scrolling on mobile |

### 3.9 Platform
| # | Requirement | Acceptance |
|---|---|---|
| M-48 | Run persistence and reconstruction | Full trace from DB + object store |
| M-49 | Structured logging with `run_id` correlation | Every line carries it |
| M-50 | Audit log append-only with hash chain | Immutability test passes |
| M-51 | No secrets in source; startup degrades on missing credentials | Startup banner shows the honest state |
| M-52 | Scenario test matrix executing normal/edge/failure/high-risk cases | `evaluation/reports/` artifact exists |

---

## 4. SHOULD-HAVE (target, but the MVP ships without them)

| # | Item | Value | Cut rule |
|---|---|---|---|
| S-01 | Human review + override end-to-end (UI + audit) | Proves the HITL design; strong demo moment | Cut UI, keep API + audit |
| S-02 | RAG over 30–60 curated documents with citations | Explains *meaning*, cites methodology | Cut entirely; report "documentation context unavailable" |
| S-03 | One Indic language (Malayalam or Hindi) with the four hard gates | Directly addresses an SIH requirement | Cut to English only |
| S-04 | One geofenced alert firing with evidence | Proves proactive capability | Cut to in-app only, or cut entirely |
| S-05 | `get_pfz` live via WMS | Strongest fishing evidence | Depends on V-2 verification; degrade to derived indicators |
| S-06 | `get_weather` / `get_marine_warnings` live via IMD | Completes the safety picture | Depends on credentials; degrade explicitly |
| S-07 | Web push channel | Realistic delivery | In-app only |
| S-08 | Analyst dataset inspector / export | Useful for researchers | Cut |

**Cut order under time pressure:** S-08 → S-07 → S-04 → S-02 → S-03 → S-01.
S-05 and S-06 are not schedule decisions — they depend on external verification and
credentials.

---

## 5. DEFERRED (designed, not built in the MVP)

| Item | Why deferred | Where specified |
|---|---|---|
| Route corridor advisory | Needs stable safety assessment first; adds a large UI surface | `11` §14, `12` |
| Vessel context and class-aware thresholds | Requires a vessel model and validated per-class thresholds | `12` §4.3 |
| Historical comparison | Requires multi-year archive handling | `04` §6 |
| Ecological domain / indicators | **SCIENTIFIC VALIDATION REQUIRED** | `12` §6 |
| MOSDAC integration | Auth + latency + parsing effort; enhancement only | `03` S-09 |
| Cyclone track (live) | Depends on IMD credentials | `04` §3.3 |
| Additional Indic languages | Each needs lexicon review + native evaluation | `13` §A8 |
| TTS / voice input | FUTURE; no quality basis yet | `13` §A7 |
| SMS / email channels | Provider, cost and regulatory considerations | `13` §B7 |
| Report document export | Straightforward but not differentiating | `04` §6 |
| Multi-tenant / organisation features | Not needed to prove the architecture | — |

---

## 6. EXPLICITLY OUT OF SCOPE

| Item | Reason |
|---|---|
| **Replacing or duplicating INCOIS/IMD/ISRO services** | ORCA is an integration and reasoning layer. It cites authorities |
| **Issuing official advisories** | Structurally prevented (validator + DB constraint) |
| **Reproducing the PFZ product from raw fields** | Scientifically unsound without the published methodology; misrepresents a national product |
| **Navigation-grade routing or charting** | Charts and Notices to Mariners remain authoritative |
| **Legal determinations from boundary data** | Advisory context only |
| **Real-time AIS / vessel surveillance** | Privacy and policy implications; not needed |
| **HAB prediction or any health/consumption advice** | Requires validated methodology and a public-health escalation path |
| **New ocean forecast models** | ORCA consumes authoritative products |
| **Offline on-device inference** | Out of scope for a server-backed system |
| **Any accuracy claim not produced by the evaluation harness** | Fabricated benchmarks are prohibited project-wide |

---

## 7. MVP Data Reality

What the MVP can actually rely on, from `03_DATA_SOURCE_MATRIX.md`:

| Capability | Source | Status | MVP behaviour |
|---|---|---|---|
| `get_sst` | INCOIS ERDDAP | **VERIFIED** | **Live** |
| `get_chlorophyll` | INCOIS ERDDAP | **VERIFIED** | **Live** |
| `get_ocean_observations` | INCOIS ERDDAP | **VERIFIED** | **Live** |
| `get_maritime_boundaries` | MarineRegions | **CONFIRMED** | **Live** (preloaded snapshot) |
| `get_wave_conditions` | CMEMS | AUTH REQUIRED | Live with credentials; otherwise `AUTH_REQUIRED` — **and no safety verdict is issued** |
| `get_currents` | CMEMS | AUTH REQUIRED | Same |
| `get_pfz` | INCOIS WMS | PENDING VERIFICATION | Three branches; degrade to labelled ORCA-derived indicators |
| `get_weather` | IMD | AUTH REQUIRED | Fallback for wind; degradation stated |
| `get_marine_warnings` | IMD | AUTH REQUIRED | **No substitute**; status reported as unknown |
| `get_lightning` | IMD | AUTH REQUIRED | Not evaluated; stated |
| `get_cyclone_track` | IMD | AUTH REQUIRED | Not evaluated; stated |

**Guaranteed floor.** Four capabilities are backed by verified or confirmed sources with
no authentication. The vertical slice is demonstrable on that floor alone — with
`INSUFFICIENT_EVIDENCE` for safety, which is itself an honest and defensible outcome that
demonstrates the evidence-sufficiency design.

**Target state.** With CMEMS credentials, the full disagreement scenario (favourable
fishing + marginal safety) becomes demonstrable. **Obtaining CMEMS credentials is
therefore the highest-value single action for the MVP.**

---

## 8. MVP Definition of Done

- [ ] The Kochi query runs end-to-end against **live** INCOIS ERDDAP
- [ ] ≥ 5 capability tools invoked; ≥ 3 external sources reached
- [ ] SAFETY and FISHING_SUITABILITY returned as separate verdicts
- [ ] A disagreement scenario is reproducible on demand
- [ ] Every number in the answer resolves to provenance
- [ ] One derived value shows a recomputable derivation chain
- [ ] A failure (`AUTH_REQUIRED` or `SOURCE_UNAVAILABLE`) is visible and explained
- [ ] A fallback is used and stated
- [ ] The contrast query produces a one-step plan
- [ ] The map shows ≥ 4 layers with source and freshness badges
- [ ] Unavailable layers are listed with reasons
- [ ] Threshold validation status is visible
- [ ] No claim is presented as an official advisory
- [ ] The full run is reconstructible without chain-of-thought
- [ ] The scenario matrix has been executed and a report artifact exists

---

## 9. What the MVP Deliberately Does Not Prove

Stated openly, so nobody is asked to believe more than the evidence supports:

- **Scientific validity of thresholds.** Labelled `SCIENTIFIC VALIDATION REQUIRED`.
- **Translation quality beyond the automated hard gates.** Requires native review per
  language.
- **Operational reliability at scale.** Load characteristics are targets, not measurements.
- **Availability of IMD / WMS / MOSDAC data.** Blocked on credentials and verification.
- **Real-world recommendation accuracy.** Would require outcome data over a season.

These are tracked in `25_GAP_AND_VALIDATION_REGISTER.md` and handed over unedited.
