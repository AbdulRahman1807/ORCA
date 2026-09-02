# ORCA — Implementation Log

**Session:** 2026-09-02 · **Phase:** design set → Phase 1–6 partial
**State at end of session:** ~70% of backend logic · 8,769 lines implementation ·
2,140 lines tests · 248 tests passing (0.9 s, all offline)

*Session 2 added the MarineRegions boundary adapter and the REGULATORY domain
(§10). Session 3 added the five agents, the LangGraph orchestration and the LLM
provider abstraction (§11). Everything above §10 describes the state after
session 1 and is still current except where §10 and §11 say otherwise.*

This document records what was built, why, and the decisions taken while building it.
It is the handover artifact: read this before resuming.

---

## 1. What This Session Covered

| Phase | Outcome |
|---|---|
| Documentation | Design documents **01–22** written (23–30 not started) |
| Phase 0 — foundation | Repo, venv, package layout, test harness |
| Phase 1 — adapters | **INCOIS ERDDAP**, **CMEMS** and **MarineRegions** adapters, all live and verified |
| Phase 2 — canonical schema | Complete, with structural invariants enforced |
| Phase 3 — capability tools | **7 of 11 P0 tools** |
| Phase 4 — agents | **All five built** (Planner, Discovery, Geospatial, Risk, Reporting) |
| Phase 5 — LangGraph | **Graph running end to end**, incl. durable human review |
| Phase 6 — geospatial kernel | Geodesy, temporal alignment, derivations, containment (~65 %) |
| — assessment engine | Thresholds, sufficiency, verdicts, confidence, synthesis, REGULATORY (~90 %) |

**Milestones reached.** A live, evidence-backed positive verdict from current data —
`FISHING_SUITABILITY = FAVOURABLE`, driven by a chlorophyll ratio derived from CMEMS
ocean colour — while `SAFETY` correctly refuses for want of an official warning source.

Then, in session 2, a second fully evidenced domain: `REGULATORY`, decided by
point-in-polygon against versioned MarineRegions geometry. A position 60 km inside the
Sri Lankan EEZ returns `RESTRICTED` with the boundary, its dataset version and the
distance to the edge — and that constraint is stated even when safety cannot be
assessed, because it holds whatever the weather does.

---

## 2. Code Map

```
backend/orca/
├── schemas/          819 lines   canonical model
│   ├── enums.py                  value kinds, verdicts, domains, representativeness
│   ├── errors.py                 canonical error taxonomy + legacy mapping
│   ├── core.py                   SpatialRef, TemporalRef, Provenance, Quality, BBox
│   ├── data.py                   Observation, Forecast, OceanField, RasterRef, …
│   ├── assessment.py             Evidence, Claim, Assessment, Recommendation
│   ├── envelope.py               OrcaEnvelope + provenance-join invariant
│   └── units.py                  unit aliases + explicit conversion
├── adapters/        2590 lines   THE ONLY PLACE WITH PROVIDER KNOWLEDGE
│   ├── incois_erddap/            client, metadata capture + validation, bindings, adapter
│   ├── cmems/                    store (Zarr v2 reader), client, bindings, adapter
│   └── marineregions/            WFS client, snapshot writer/reader, boundary adapter
├── tools/            487 lines   capability contracts + multi-source fallback
│   ├── base.py                   validation, ToolRun, collect_from_sources
│   ├── ocean.py                  get_ocean_observations, get_sst, get_chlorophyll
│   ├── marine.py                 get_wave_conditions, get_currents
│   └── boundaries.py             get_maritime_boundaries
├── geospatial/       622 lines   deterministic kernel
│   ├── geometry.py               geodesic distance/bbox, vector magnitude+direction
│   ├── topology.py               ray casting, holes, antimeridian, edge distance
│   ├── temporal.py               representativeness gate, alignment, freshness
│   ├── derive.py                 vector pairs, ratio-to-local-median
│   └── methods.py                method id + version registry
├── assessment/      1015 lines   deterministic rule engine (no LLM)
│   ├── thresholds.py             YAML threshold sets with validation status
│   ├── staleness.py              per-parameter usable-age policy
│   ├── jurisdiction.py           home/foreign placement + boundary implications
│   ├── engine.py                 sufficiency → bands → worst-factor → confidence
│   ├── regulatory.py             containment → PERMITTED/RESTRICTED/PROHIBITED/UNKNOWN
│   └── synthesis.py              cross-domain headline, limiting factor
└── cli/query.py      227 lines   vertical slice runner

config/    datasets.json (captured) · boundaries.yaml · thresholds/*.yaml ·
           staleness.yaml · tls/
data/      boundaries/<version>/  captured snapshots — GIT-IGNORED, regenerate
scripts/   capture_datasets.py · capture_boundaries.py
tests/     unit/ adapters/ fixtures/upstream/{incois_erddap,cmems,marineregions}/
```

**Layering rule.** `agents → tools → adapters → source`. Nothing above `adapters/`
knows a URL, a credential, ERDDAP selector syntax or that Zarr exists. This was
maintained throughout and should be enforced by an import-linter contract when
`agents/` lands (`18_REPOSITORY_STRUCTURE.md` §1). `assessment/` does not import
from `adapters/` either: both read `config/boundaries.yaml`, each taking the
section it owns (D-18).

---

## 3. Findings That Changed the Project

These came from touching live services. Several contradict the original data audit.
Full detail: `03_DATA_SOURCE_MATRIX.md` §14–15.

### 3.1 INCOIS ERDDAP — access confirmed, currency corrected

The audit called it a *"confirmed viable programmatic ocean-data backbone."* Access is
confirmed. **Most datasets are historical archives.**

| Dataset | Coverage ends | Verdict |
|---|---|---|
| `incois_argo_10d_VAM` / `10day_McCreary` | 2026-07-30 | current; 10-day subsurface means |
| `incois_argo_mnt_*` | 2026-07-15 | current; monthly |
| `NOAA_AVHRR_AMSR_datasets` (SST) | 2011-10-04 | archive |
| `incois_oceansat2_datasets` (CHL) | 2020-05-01 | archive |
| `ascat_daily_datasets` (wind) | 2023-05-21 | archive |

| ID | Finding |
|---|---|
| **F-1** | **Incomplete TLS chain.** The server sends only its leaf certificate; the `GlobalSign RSA OV SSL CA 2018` intermediate is absent (`openssl s_client -showcerts` → chain length 1). macOS/curl succeed via AIA fetching; `certifi` and any Linux container **fail**. Handled with the OS trust store plus a runtime-generated bundle. Verification is never disabled. |
| **F-2** | `NOAA_AVHRR_datasets` — the only current SST source (to 2026-08-11) — publishes **latitude as array indices 0–399** despite `units=degrees_north`. Unusable. |
| **F-3** | That same dataset **dropped out of the catalogue mid-session** (19 → 18 datasets). Datasets can disappear at runtime. |
| **F-4** | `AMSR2_3day_Global` fails the same axis check and reports coverage ending 1915. |
| **F-5** | Raw ERDDAP selectors are rejected by the **servlet container** with an HTML 400 before ERDDAP parses them; `[` `]` must be percent-encoded. |
| **F-6** | **No current chlorophyll source** on this ERDDAP. |
| **F-7** | The 1° Argo grid puts the nearest valid node **96 km** from Kochi; coastal cells are null. |

### 3.2 CMEMS — the audit's `AUTH REQUIRED` status was wrong for our path

| Endpoint | Unauthenticated |
|---|---|
| STAC catalogue | **200** — 307 products enumerated |
| ARCO store `.zmetadata` | **200** |
| ARCO data chunk `VHM0/0.0.0` | **200**, 521,648 bytes |

`AUTH REQUIRED` appeared not to hold for the ARCO object store. **This was later shown
to be only partly true — see §3.3.** Datasets bound (ids read from the public STAC
catalogue, not guessed):

| Capability | Dataset | Coverage |
|---|---|---|
| waves | `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i_202411` | → **2026-09-12** (forecast) |
| currents | `cmems_mod_glo_phy_anfc_merged-uv_PT1H-i_202211` | → **2026-09-11** (forecast) |
| SST | `METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2` (OSTIA) | → 2026-09-01 |
| chlorophyll | `cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D_202311` | → 2026-08-31 |
| wind | `cmems_obs-wind_glo_phy_nrt_l4_0.125deg_PT1H_202207` | → 2026-09-01 |

**The wave and current products are forecasts covering tomorrow.** This is the only
source in the project that can answer a question about the future. **Wind is an
observation product with no forecast horizon** — a wind forecast still requires IMD or
another NWP source.

| ID | Finding |
|---|---|
| **F-8** | Coastal cells are land-masked in the wave model; Kochi returns nothing. Nearest valid ocean cell is 10.3 km offshore. |
| **F-9** | `VHM0` is `int16` with `scale_factor = 0.01`; raw reads are wrong by 100×. |
| **F-10** | Zarr **omits all-fill chunks**. A missing chunk must read as *no data*, never `0.0` — which would present as a calm sea. |
| **F-11** | No scalar wind speed is published, only components. |
| **F-12** | OSTIA publishes SST in **kelvin**. Assuming °C reports ~301 °C for a tropical sea. |

### 3.3 CMEMS access is only partly reliable without credentials — correction to §3.2

Late in the session, data chunks that had returned 200 began returning `403
AccessDenied`. End-of-session state:

| Product | Bucket | Data chunk | Across the session |
|---|---|---|---|
| Waves, currents (analysis/forecast) | `arco-time-015` | **200** | reliable throughout |
| SST (OSTIA) | `arco-time-045` | **403** | worked, then intermittent |
| Chlorophyll, wind (observation L4) | `arco-time-044/050` | **403** | worked, then denied |

| ID | Finding |
|---|---|
| **F-13** | A denied request and a nonexistent key return an **identical** `AccessDenied` body (verified with a deliberately nonsensical key). Status and body **cannot distinguish "missing chunk" from "denied"** — a real ambiguity, because Zarr legitimately omits all-fill chunks. |
| **F-14** | The same chunk returned 200 early and 403 later, pointing to throttling or an egress quota rather than a static policy. |

**This invalidates the §3.2 correction.** The audit's original `AUTH REQUIRED` was closer
to correct. Forecast products are usable unauthenticated today; observation products are
not reliable. **Obtaining CMEMS credentials is now a priority action.**

The system behaved correctly under the change without any code alteration: it returned
`AUTH_REQUIRED`, did not retry, did not silently substitute, fell back to the INCOIS
archive, flagged it `STALE_DATA`, and issued `INSUFFICIENT_EVIDENCE` rather than a
verdict. That is the designed behaviour working under an unplanned upstream change.

---

## 4. Design Decisions

ADR-style. `24_ENGINEERING_DECISIONS.md` was never written; this section partially
serves that purpose until it is.

### D-1 · A focused Zarr v2 reader instead of xarray + zarr + fsspec
**Context.** CMEMS publishes ARCO (Zarr) stores over HTTP.
**Decision.** ~200 lines reading the v2 layout directly, with `numcodecs` for blosc.
**Alternatives.** `xarray + zarr + fsspec + aiohttp`.
**Rationale.** A point query costs 2–3 chunk fetches. The full stack brings an async
layer and much looser control over error mapping — and every failure here must become a
canonical ORCA code. Chunk caching and windowed reads were straightforward to add.
**Consequences.** We own the decode path (scale/offset, fill, chunk-omission), which is
covered by tests. If CMEMS moves to Zarr v3 this needs revisiting — `zarr.json` already
returns 403 while `.zmetadata` returns 200.

### D-2 · TLS: OS trust store, then a generated bundle; never disable verification
**Context.** F-1 — a source that works on a laptop would fail in a container.
**Decision.** `truststore` first, then a bundle of certifi roots + the tracked 1.5 kB
intermediate, generated at runtime and invalidated by mtime.
**Rationale.** Vendoring a copy of certifi's root store would go stale silently.
Disabling verification was never an option for a system that cites authorities.

### D-3 · Presence-based factors come from the tool *outcome*, not a sentinel value
**Context.** `official_warning_status` is not a number. Encoding "no warning" as `0.0`
made it indistinguishable from "we could not check".
**Decision.** `EvidencePool.status` is populated from the envelope: `NO_ACTIVE_WARNING`
→ `{active: False, checked: True}`; `AUTH_REQUIRED` leaves it unset.
**Consequence.** "Could not check" can never become "nothing in force". A test asserts
this (`test_unchecked_warnings_do_not_become_no_warning`).

### D-4 · Time-aware source selection, not first-match fallback
**Context.** INCOIS SST ends 2011; CMEMS is current. Both flag `STALE_DATA` for a
future query.
**Decision.** Try the primary; fall back on transport failure, `NO_DATA`, or
unusability for the requested time. When *every* source is degraded, take the one whose
`valid_time` is closest to the request. Never fall back on `AUTH_REQUIRED`.
**Rationale.** A 2011 archive value is not equivalent to last week's just because both
are flagged stale. A credential problem is not fixed by silently switching authority.
**Consequence.** The switch is recorded in `source_resolution`, on each `Provenance`,
and stated in the answer.

### D-5 · Ageing is asymmetric and configured per parameter
**Context.** A cadence-derived symmetric window refused a 3-day-old ocean-colour
composite that is normal input to a productivity judgement.
**Decision.** A value informs the period *after* its valid time, never before.
`config/staleness.yaml` sets `usable_age_days` per parameter: wind 0.25 d, ocean colour
4.0 d.
**Rationale.** Different variables age at different rates for different purposes. A
two-day-old wind observation says nothing about tomorrow; a phytoplankton field persists.
**Status.** The numbers are mine and are labelled `SCIENTIFIC_VALIDATION_REQUIRED`.
They need domain review.

### D-6 · Chlorophyll is expressed comparatively, never absolutely
**Context.** `12_RISK_AND_RECOMMENDATION_SPEC.md` §5.3 forbids "chlorophyll is high" —
it implies a standard ORCA has not validated.
**Decision.** The assessment factor is `chlorophyll_ratio_to_local_median`, computed
over valid cells within 100 km of the point (877 cells in the Kochi run), with a full
derivation record.
**Consequence.** This is what produced the first live verdict. It also means fishing
suitability needs a *field*, not a point — the adapter grew `fetch_local_field`.

### D-7 · Units are read from the source and converted explicitly
**Context.** F-12 (kelvin), plus INCOIS publishing `degs`, `Degree C`, `milligram m-3`.
**Decision.** `schemas/units.py` with an alias table and an explicit conversion
registry. An impossible conversion **raises**.
**Rationale.** Silently returning an unconverted number would put a kelvin value into a
Celsius threshold comparison. Failing loudly is correct.

### D-8 · Derivations belong to the kernel, never to adapters
**Context.** CMEMS publishes wind and current components but no scalar speed.
**Decision.** `geospatial/derive.py` computes speed/direction and ratios, each carrying
`method`, `method_version`, input provenance ids and params.
**Rationale.** A derived number must be recomputable from its record. Putting the
arithmetic in an adapter would bury it under provider-specific code.

### D-9 · Search outward for the nearest valid ocean cell
**Context.** F-8 — Kochi's cell is land-masked in the wave model.
**Decision.** Search outward to a configurable radius (default 60 km), return the
nearest valid cell, flag `INSUFFICIENT_COVERAGE`, and report the distance.
**Rationale.** A fisher is offshore anyway. Reporting "no data" for a coastal query
would be technically true and practically useless — but the offset must be visible.

### D-10 · Structural guards in the schema, not conventions in prose
Enforced at construction: only `SAFETY` may return `UNSAFE`; `REGULATORY` must use its
own vocabulary; a derived value without a derivation record is rejected; an envelope
with an unresolved `provenance_id` is rejected; a material claim without evidence is
rejected; a `Recommendation` cannot be marked as an official advisory.
**Rationale.** These are the project's core promises. A promise enforced by a validator
survives refactoring; one written in a document does not.

### D-11 · Gaps are scoped per domain
A missing wave forecast is a `SAFETY` gap. Listing it under `FISHING_SUITABILITY` is
noise, and a factor that produced a usable driver is not simultaneously "not evaluated".

### D-13 · `403` is a failure, never "no data"
**Context.** F-13. Zarr omits all-fill chunks, so a missing chunk is normal and must read
as absent. On the CMEMS buckets a missing key returns `403 AccessDenied` — identical to a
genuine denial.
**Decision.** `404` reads as absent. `403` raises.
**Alternative considered and rejected.** Treating `403` as absent. I implemented this
first, because it made chlorophyll work again — then reverted it. The two cases are
indistinguishable, so the heuristic would silently discard real observations, and a
land-masked or denied sea would read as a calm one.
**Consequences.** Availability is lower: a throttled chunk fails the query instead of
degrading. Correctness is preserved, which is the right trade for a system that makes
safety statements. Credentials remove the ambiguity entirely.

### D-12 · Upstream fixtures are recorded, never hand-authored
`tests/fixtures/upstream/` carries capture dates. A hand-written fixture would make the
adapter suite test a fiction.

---

## 5. Deviations From the Design Documents

| Document | Deviation | Reason |
|---|---|---|
| `03` §5/§7 — CMEMS `AUTH REQUIRED` | Partly wrong in both directions: forecast products need no credentials, observation products are unreliable without them | §15.5; the audit was closer to correct than my first correction |
| `03` §5 — ERDDAP "viable backbone" | True for access, not currency | Verified live; recorded in §14 |
| `22` §7 — "guaranteed floor" of 4 live capabilities | Both weaker (ERDDAP archives) and stronger (CMEMS unauthenticated) than recorded | §15.4 |
| `04` §3.7 — chlorophyll bands | Factor is a ratio to local median, not a raw value | `12` §5.3 forbids absolute language |
| `11` §8.2 — cadence-derived validity | Replaced by asymmetric, per-parameter policy | D-5 |
| `18` §1 — import-linter contracts | Not yet configured | `agents/` does not exist yet |

---

## 6. Open Decisions Needing Input

**O-1 · `official_warning_status` is a required safety input, so no safety verdict is
possible without IMD credentials.** This follows `12` §4.1 and is the most defensible
position — a warning cannot be synthesised from model fields. But it means the demo
cannot show a safety verdict at all until credentials arrive. The alternative is to
allow a verdict with warning status explicitly "unknown", capped at `MARGINAL`.
*Current behaviour: spec-compliant refusal.*

**O-2 · Threshold values are unvalidated.** `small_craft_v0.1` and `fishing_v0.1` are
engineering parameters, surfaced in every answer as
`SCIENTIFIC_VALIDATION_REQUIRED`. They need review against Indian marine safety guidance.

**O-3 · Staleness tolerances are unvalidated** (D-5).

**O-6 · A narrow intent still triggers a full domain assessment.** The Planner
narrows `warning_lookup` to `official_warning_status` alone and plans one
capability — but the SAFETY *domain* still evaluates against the whole
`small_craft_v0.1` required set, so the answer lists `significant_wave_height`
and `wind_speed` as `NOT_RETRIEVED` when they were deliberately never requested.
The output is truthful and the refusal is correct, but it reads as noise: it
reports absence for things nobody asked for.

Two defensible resolutions. (a) A warning lookup should report warning status
and issue **no** SAFETY verdict at all — the user asked a lookup question, not
for an assessment. (b) `not_evaluated` should distinguish *not planned* from
*planned and not retrieved*, which is a smaller change and keeps the domain
assessment intact.

*Current behaviour: (b) is not implemented; everything unplanned shows as
`NOT_RETRIEVED`.* This needs a product decision about what a lookup question
should return.

**O-5 · The boundary implication table needs legal review** (D-18). It encodes the
ordinary reading of UNCLOS for a fishing vessel — a coastal state controls fishing in its
own EEZ, foreign vessels need authorisation. It does **not** encode bilateral agreements,
traditional fishing rights, the India–Sri Lanka arrangements, or any licence a particular
vessel holds. It is surfaced in every answer as `LEGAL_REVIEW_REQUIRED`. The alternative
— returning `UNKNOWN` for every foreign jurisdiction until a lawyer has signed off — is
defensible but throws away the domain's most useful output.
*Current behaviour: the reading is applied and its status is stated.*

**O-4 · `NOAA_AVHRR_datasets` calibration.** Its latitude axis could be calibrated
against `NOAA_AVHRR_AMSR_datasets` over their overlapping period (1981–2011), which
would recover a current INCOIS SST source. The dataset was unloaded from the server
when attempted. Worth retrying.

---

## 7. Credential and Verification Backlog

| Item | Status | Blocks |
|---|---|---|
| IMD registration | not started | warnings, cyclone, lightning, wind forecast — and therefore **any safety verdict** |
| INCOIS WMS verification from an unrestricted network | not done | PFZ |
| **CMEMS credentials** | **priority — not started** | reliable SST, chlorophyll, wind; removes the 403 ambiguity (F-13) |
| MOSDAC registration | not started | P1 enhancement only |
| VLIZ / MarineRegions licence review | not started | nothing — CC-BY 4.0 attribution is carried; `14` §"terms" still wants a review |
| Legal review of the boundary implication table | not started | nothing — the table is applied and labelled `LEGAL_REVIEW_REQUIRED` (O-5) |
| A source for restricted / naval zones and MPAs | none identified | the one gap that could turn a `PERMITTED` into something else (§10.5) |

IMD is the critical path. Everything else degrades explicitly.

---

## 8. Next Steps

1. ~~**MarineRegions → `REGULATORY` verdict.**~~ **Done — see §10.**
2. **Agents + LangGraph.** 25 % of remaining backend weight, no external dependencies,
   and the architectural differentiator. The CLI currently hardcodes the orchestration
   a Planner is meant to decide. Needs an LLM provider configured. **This is now the
   critical path for everything that is not credential-blocked.**
3. **Geospatial completion** — field masking, GeoJSON output, geofencing. The
   containment kernel (`topology.py`) landed with §10; geofencing can reuse it directly.
5. **IMD adapter** — build to spec now so it works the day credentials arrive; it
   already degrades correctly.
6. **Documents 23–30** — diagrams, ADRs (fold in §4 and §10.3 above), gap register,
   judge Q&A, traceability, glossary, quickstart, definition of done.
6. **Boundary follow-ups** (small, from §10.2): widen the snapshot region east of 90 E
   so Andaman and Nicobar positions can be answered; get the VLIZ licence review done
   (`14` §"terms"); find a source for restricted/naval zones, which is the one gap that
   could turn a `PERMITTED` into something else.

---

## 9. How to Run

```bash
python3 -m venv .venv
./.venv/bin/pip install pydantic httpx certifi truststore numcodecs numpy pyyaml \
                        pytest langgraph

./.venv/bin/python -m pytest tests -q          # 248 offline tests, no network, no LLM

./.venv/bin/python scripts/capture_boundaries.py   # REQUIRED once: boundary snapshot
./.venv/bin/python scripts/capture_datasets.py     # live INCOIS metadata capture
```

`data/boundaries/` is git-ignored, so a fresh clone must run
`capture_boundaries.py` before the REGULATORY domain can decide anything; the
adapter says exactly that when the snapshot is absent.

**Ask ORCA a question** — a Planner decides what to retrieve:

```bash
./.venv/bin/python -m backend.orca.cli.ask "is it good for fishing near Kochi tomorrow morning?"
./.venv/bin/python -m backend.orca.cli.ask "am I inside the Indian EEZ near Kochi?"
./.venv/bin/python -m backend.orca.cli.ask "is there a warning in force right now?"
```

Watch the PLAN block change between them: the fishing question plans six tools
and declares five gaps, the boundary question plans one, and the warning lookup
plans **none** — its only source needs credentials — and says so.

**The fixed vertical slice** (hardcoded orchestration, retained for comparison
until it is retired — §8 step 3):

```bash
./.venv/bin/python -m backend.orca.cli.query
./.venv/bin/python -m backend.orca.cli.query --when 2011-06-15T00:30:00
```

The second invocation targets a date inside ERDDAP's archive coverage and shows
the pipeline producing a verdict from historical data — useful for demonstrating
the reasoning path independently of current data availability.

**No LLM is required.** With `ORCA_LLM_PROVIDER` unset, ORCA plans from
deterministic tables and answers from a grounded template (D-21). Setting it
(see `.env.example`) adds fluency; it cannot change a number or a verdict.

**ORCA output is not an official advisory. Follow IMD and INCOIS bulletins.**

---

## 10. Session 2 — MarineRegions and the REGULATORY Domain

This was §8 step 1. It is the only domain that needs no forecast, no credentials and no
network at query time, which is why it was taken next.

### 10.1 What was built

| Piece | What it does |
|---|---|
| `geospatial/topology.py` | Even-odd ray casting with hole exclusion, antimeridian normalisation, geodesic distance to the nearest boundary edge, and a flat ring index with per-ring bbox prefiltering. 245 lines, no geometry dependency. |
| `adapters/marineregions/` | WFS 2.0 client (capture only), snapshot writer and reader, and the boundary adapter. 932 lines. |
| `tools/boundaries.py` | `get_maritime_boundaries` — the 7th P0 tool. |
| `assessment/jurisdiction.py` | Home-vs-foreign placement and the configured implication table. |
| `assessment/regulatory.py` | Containment → `PERMITTED` / `RESTRICTED` / `PROHIBITED` / `UNKNOWN`. |
| `scripts/capture_boundaries.py` | Live capture → `data/boundaries/<version>/`. |
| `config/boundaries.yaml` | Source, snapshot region, per-type sources, and the implication table with its validation status. |

56 new tests (122 total, 0.25 s, all offline). Two recorded upstream fixtures — real
national polygons, 48 kB — plus a capabilities excerpt.

**Live behaviour, verified this session.** 60 km inside the Sri Lankan EEZ →
`RESTRICTED`, high confidence, with the feature name, `v12 (2023)` and the distance to
the edge. 2.3 km from the India–Sri Lanka boundary in Palk Bay → `PERMITTED` but
confidence capped at medium and the proximity stated. Beyond every EEZ → `UNKNOWN`, not
`PERMITTED`. East of 90 E → `INSUFFICIENT_COVERAGE`, refusing rather than answering.
A boundary query costs 12–20 ms against 458,706 vertices.

### 10.2 Findings

Full detail in `03_DATA_SOURCE_MATRIX.md` §16. The four that changed the design:

*Numbering note.* These findings were authored as F-13–F-18 on the feature branch,
which collided with the CMEMS `403` findings (§3.3) already holding F-13/F-14 on
`main`. The MarineRegions set was renumbered **+2 to F-15–F-20** on merge; the CMEMS
pair keeps F-13/F-14 because D-13 and §7 cite them. Read PR #1 accordingly.

| ID | Finding |
|---|---|
| **F-15** | The layers declare `urn:ogc:def:crs:EPSG::4326`, so CQL `BBOX` is read **latitude first**. The first capture asked for the Indian Ocean and got Svalbard and the Russian Arctic — a plausible-looking, entirely wrong, non-empty result. |
| **F-17** | `eez_12nm` and `eez_24nm` are **bands from the baseline, not nested discs**. 5 NM offshore is inside the territorial sea and outside the contiguous zone; 20 NM offshore is the reverse. Treating them as nested is wrong in both directions. |
| **F-18** | `eez_internal_waters` publishes **nothing for Sri Lanka**. "Outside every internal-waters polygon" there is a gap in the source, not a fact about the point, and is downgraded to *not evaluated for this jurisdiction* (D-17). |
| **F-19** | The service publishes **no version field** — only a release year inside the layer title. The capture parses it and **fails** rather than writing geometry that cannot be cited. |

### 10.3 Design decisions

#### D-14 · A versioned local snapshot, not a query-time WFS call
**Context.** `04` §3.11 specifies a preloaded, versioned PostGIS snapshot. There is no
PostGIS in this project yet.
**Decision.** Capture to `data/boundaries/<version>/`: a manifest with provenance and
per-feature attributes, plus one flattened `.npz` of full-precision geometry per layer.
**Rationale.** Version binding is the point. A run that said "inside the Indian EEZ" in
March must still be checkable in September against the geometry it actually used, and a
live WFS call cannot promise that. It also means the REGULATORY domain keeps working
when the network does not.
**Consequences.** `data/boundaries/` is git-ignored, so a fresh clone must run the
capture; the adapter says exactly that when the snapshot is absent. Loading is 2 ms.

#### D-15 · Coverage is a declared region, and outside it the answer is refusal
**Context.** A snapshot holds the features intersecting a bbox. Outside that bbox,
"inside no boundary" is indistinguishable from "we did not look".
**Decision.** The snapshot records its region. A query outside it returns
`INSUFFICIENT_COVERAGE` and no containment result at all.
**Rationale.** Same principle as D-3: *could not check* must never become *nothing
found*. The failure this prevents is a vessel being told it is in international waters
because the snapshot stopped at 90 E.

#### D-16 · Boundary types are evaluated independently; the worst governs
**Context.** F-17 — the zones are bands, not a hierarchy.
**Decision.** Each type is tested separately and mapped through a configured implication
(`home` / `foreign` / `none`); the most constraining outcome governs. Never averaged,
never inferred from a neighbouring type.
**Consequence.** Inside a foreign territorial sea is `PROHIBITED` even though the
surrounding EEZ alone would be `RESTRICTED`.

#### D-17 · A layer with no feature for this jurisdiction cannot say "outside"
**Context.** F-18.
**Decision.** After containment, the adapter checks whether the governing EEZ's
sovereign appears at all in each other layer. If not, that type is flagged and the
assessment lists it as `INSUFFICIENT_COVERAGE`, not as unconstrained.
**Rationale.** The error is asymmetric: an unchecked internal-waters polygon can only
make the answer more restrictive, never less. Reporting it as "outside" would understate
a restriction, which is the direction that gets someone arrested.

#### D-18 · The geometry is a fact; what it means is a legal judgement, and they live apart
**Context.** "Inside another state's EEZ ⇒ needs authorisation" is not something an
adapter should assert, and not something an engineer should encode as a constant.
**Decision.** The adapter reports only what the source publishes — sovereign, territory,
ISO code, distance. `config/boundaries.yaml` carries the implication table, marked
`LEGAL_REVIEW_REQUIRED`, and `assessment/jurisdiction.py` reads it. The adapter and the
assessment read different sections of the same file and do not import each other.
**Consequence.** Every regulatory answer surfaces `LEGAL_REVIEW_REQUIRED`, exactly as
threshold-based answers surface `SCIENTIFIC_VALIDATION_REQUIRED`.

#### D-19 · An unevaluated boundary type is named in every answer
**Context.** `04` §3.11 rule 2 — an EEZ polygon is not a fishing regulation zone.
**Decision.** `boundary_types` defaults to every type ORCA has a policy for, including
the four with no source (MPA, restricted zone, fishing regulation zone, seasonal
closure). Each returns `DATASET_UNAVAILABLE` and appears under `not_evaluated`.
**Rationale.** An answer that quietly omitted restricted zones would read as "you are
clear". A `PERMITTED` verdict with unchecked restrictions is therefore capped at medium
confidence — an unchecked naval exercise area can only make things worse.

#### D-20 · A regulatory constraint outranks a safety refusal in the headline
**Context.** `synthesise` answered a safety-input gap with `CANNOT_ADVISE` before
looking at any other domain, which would have buried a `RESTRICTED` or `PROHIBITED`
result — and today safety *always* refuses, for want of IMD credentials.
**Decision.** Regulatory constraints are settled first, per `12` §8's priority order.
The headline then adds that conditions could not be assessed, and the disposition stays
`BLOCKED`.
**Rationale.** A boundary holds whatever the weather does. Naming it is useful even when
nothing else can be said.

### 10.4 Deviations from the design documents

| Document | Deviation | Reason |
|---|---|---|
| `04` §3.11 / `09` §4.2 — PostGIS snapshot | Flat `.npz` arrays + JSON manifest | D-14; no PostGIS in the project yet. The interface is unchanged and the store is swappable |
| `06` §476 — `REGULATORY PERMITTED confidence high` | `PERMITTED` is capped at **medium** while restriction-bearing types are unevaluated | D-19 |
| `12` §11 — category table | No category is defined for `REGULATORY RESTRICTED`; mapped to `PROCEED_WITH_CAUTION` | Needing another state's authorisation is neither a prohibition nor "proceed with context" |
| `04` §3.11 — `international_boundary` as a boundary type | Not configured. `eez_boundaries` is a **line** layer; containment is undefined for it | Distance to the nearest EEZ edge already answers "how far am I from the line", and is reported |

### 10.5 What this domain still cannot do

* **No restricted or naval zones, no MPAs, no fishing regulation zones, no seasonal
  closures.** These are the restrictions most likely to bite, and none has a configured
  source. Every answer says so.
* **The monsoon fishing ban is not a polygon.** It is a dated legal instrument issued per
  state, and no boundary dataset can express it.
* **Bilateral arrangements are not encoded** — including the India–Sri Lanka
  arrangements, which is exactly the water where the geometry is most useful.
* **No vessel context.** A licence, a registration or a permitted gear type would change
  the answer, and ORCA holds none of it.
* **No land mask.** "Outside every EEZ" is equally true of the high seas and of a street
  in Kochi. The domain says so in the evidence statement rather than picking one — but a
  coarse land mask (`18` §6 already reserves `data/landmask/`) would let it distinguish
  them, and that is worth doing.
* **East of 90 E is uncovered** by the default snapshot (F-20).

---

**ORCA output is not an official advisory. Follow IMD and INCOIS bulletins.**

---

## 11. Session 3 — Agents and the LangGraph Orchestration

Phase 4 and Phase 5. The CLI previously hardcoded the orchestration a Planner is
meant to decide; it no longer has to.

### 11.1 What was built

```
backend/orca/
├── llm/              ~260 lines   provider abstraction
│   ├── provider.py               LLMProvider protocol, registry, UnavailableProvider
│   ├── providers/                one module per provider (lazy SDK import)
│   └── usage.py                  token ledger + budget enforcement
├── agents/          ~1180 lines   judgement layer
│   ├── base.py                   budgets, AgentResult, structured failure
│   ├── contracts.py              Plan, RetrievalReport, ValidationReport, AlignmentReport
│   ├── planner.py                intent, domain/evidence tables, plan + re-plan
│   ├── discovery.py              step execution, widening policy, coverage report
│   ├── geospatial_agent.py       alignment + derivation, AlignmentReport
│   ├── risk.py                   per-domain assessment + validated rationale
│   ├── reporting.py              narrative, claims, template fallback
│   └── validators/grounding.py   numeric fidelity, official language, absence guard
├── graph/           ~1100 lines   orchestration
│   ├── state.py                  OrcaGraphState + reducers
│   ├── runtime.py                OrcaRuntime carried through config, not state
│   ├── routing.py                conditional edges, Send fan-out
│   ├── build.py                  graph assembly
│   ├── events.py                 node events (never chain-of-thought)
│   └── nodes/                    context, planning, retrieval, validation,
│                                 analysis, assessment, delivery
├── tools/registry.py             catalogue + per-environment enablement
├── tools/live.py                 composition root binding adapters
└── cli/ask.py                    graph-driven CLI
```

`config/` gains nothing; `.env.example` was added (it was specified in `19` but
missing).

### 11.2 The central decision: ORCA runs without a model

**D-21 · No LLM is required, and the deterministic path is first-class.**
**Context.** Phase 4 needs "an LLM provider configured" and none is. Making the
agents depend on one would have made the whole reasoning layer untestable
offline and undemonstrable without a key.
**Decision.** `LLMProvider` resolves from `ORCA_LLM_PROVIDER`; when nothing is
configured it returns an `UnavailableProvider` whose `available` is `False`.
Every agent consults `use_llm()` and takes a deterministic path otherwise.
**Rationale.** The specification *already* mandates a deterministic fallback at
every LLM site — plan repair (`06` §3.8), template rationale (§6.7), template
answer (§7.8). Making those the default rather than the exception costs nothing
and means an unconfigured deployment produces a complete, grounded, less fluent
answer instead of no answer.
**Consequence.** All 248 tests are offline and model-free. Configuring a model
changes fluency; it cannot change a number or a verdict, and tests assert that.

### 11.3 Where the LLM is allowed to act, and what constrains it

| Site | What the model may do | What stops it doing harm |
|---|---|---|
| Planner intent | Classify into one of nine intents | Enum-constrained; keyword classifier otherwise |
| Planner relevance | **Narrow** the preferred-evidence list | May only select from the list; cannot touch `required`, cannot reach a tool |
| Geospatial summary | Rephrase computed statistics | Given only the statistics; no other input exists |
| Risk rationale | Phrase the engine's verdict | Rejected if it introduces a number or uses reserved official language; engine text stands |
| Reporting narrative | Compose the answer | Numeric fidelity, official-language and absence-as-safety validators; two failures fall to template |

`DOMAIN_MAP` and the evidence requirements are **tables**, and the evidence
tables are read from `config/thresholds/*.yaml` rather than restated — so a
factor added to a threshold set is planned for automatically and the Planner
cannot drift out of step with what the engine will demand.

### 11.4 Findings

| ID | Finding |
|---|---|
| **F-21** | **Re-planning for an unfillable gap is an infinite-ish loop of identical requests.** The first live run re-planned twice for `official_warning_status` (no source at all) and `wind_speed` (tool already answered with stale data), re-issuing the same calls and inflating the evidence count 17 → 23 → 29 with duplicates. A gap is only worth re-planning if some tool yielding it is **available and not yet attempted**; `ValidationReport.actionable_gaps` now carries that, and an unfillable gap degrades the domain instead (`06` §3.8). |
| **F-22** | **`07` §5 routes `BLOCKED` to `finalize`, which delivers the user nothing.** §8's degradation ladder requires BLOCKED to produce "no verdict, explicit statement of what could not be reached". Deviation recorded: BLOCKED routes to `report`, which composes the explanation over assessments that are all `INSUFFICIENT_EVIDENCE`. The grounding validators forbid it from asserting safety, so it explains without ever concluding. |
| **F-23** | A time-independent question ("am I inside the EEZ?") legitimately resolves **no** time window, and the Planner correctly does not ask for one — but the analysis frame still needs an interval. `_window` defaults to the present; time-sensitive intents never reach it without a window because the Planner asks first. |
| **F-24** | The chlorophyll local-median ratio was derived in the **CLI**, reaching into the CMEMS adapter. `agents/` may never do that, so the derivation moved into `get_chlorophyll` (`tools/` may import both `adapters/` and `geospatial/`). One code path now, and every consumer of the capability gets the same evidence. |

### 11.5 Design decisions

*Numbering note.* Session 2 had reused **D-13**, which session 1 already used for
the CMEMS `403` decision, and its block then collided with session 3's. Resolved
on merge: session 1 keeps D-1–D-13, session 2 shifted to **D-14–D-20**, session 3
takes **D-21–D-25**. Cross-references were updated with them.

**D-22 · The registry is the seam that keeps `agents/` away from `adapters/`.**
It carries a CATALOGUE of pure metadata (name, args schema, evidence yielded) —
all the Planner may see — plus callables bound by the composition root in
`tools/live.py`. A test asserts the plan contains no URL, dataset id or
credential string.

**D-23 · A capability with no source is *declared*, not omitted.**
`mark_unavailable` keeps the tool in the catalogue so the Planner still plans
for it and the answer states what it could not check. This is what produces
"nine tools exist, one is used, four are declared unavailable".

**D-24 · Live objects travel in graph *config*, not graph *state*.**
The registry, provider and budget are not serialisable and must not be
checkpointed. `OrcaRuntime` moves through `config["configurable"]["orca"]`,
which keeps state to plain data that can be replayed for audit.

**D-25 · A branch that fails hard still appends an assessment.**
A missing branch would stall the LangGraph superstep, so a failed domain appends
`INSUFFICIENT_EVIDENCE` (or `UNKNOWN` for REGULATORY, which has its own
vocabulary). The join count always matches the dispatch count.

### 11.6 Deviations from the design documents

| Document | Deviation | Reason |
|---|---|---|
| `07` §5 — `BLOCKED` → `finalize` | Routes to `report` instead | F-22; §8 requires BLOCKED to explain itself |
| `07` §4 — `nodes/` one module per node | Grouped by stage (7 modules, 16 nodes) | A file holding three ten-line functions is harder to follow than one holding the stage |
| `07` §14 — PostgreSQL checkpointer | `MemorySaver` in tests; no persistence yet | `09_DATABASE_SPEC.md` is not implemented; the interrupt/resume contract is exercised and survives a rebuilt graph |
| `06` §4.7 — LLM re-request on an unsatisfied step | Not implemented | F-21 showed the deterministic widening already covers the cases we have; adding a model call to re-ask an unavailable source would be waste |
| `07` §5 — separate `retrieve` dispatcher node | Dispatch is the conditional edge out of `plan` | Matches §5's own `add_conditional_edges("plan", dispatch_tools, ...)` |

### 11.7 What the graph does that the vertical slice did not

Running the same question through `cli.ask` rather than `cli.query`:

* **The plan changes with the question.** "Is there a warning in force?" plans
  **zero** tools of eleven and declares the one gap; "am I inside the EEZ?" plans
  one; the fishing question plans six and declares five gaps.
* **An unresolved location asks instead of assuming.** No retrieval happens.
* **Domains fan out and rejoin** by `Send`, so only requested domains run.
* **An official warning holds the answer at `human_review`** as a durable
  interrupt; nothing is delivered until a decision is recorded, and the state
  survives the process being rebuilt.

### 11.8 What this layer still cannot do

* **No conflict detection.** `conflict_resolve` is a declared seam that finds
  nothing, because the tool layer selects one source per parameter. Real
  cross-checking needs a second source per capability.
* **No checkpointer persistence.** Interrupt/resume works in-process; surviving
  a real restart needs `09_DATABASE_SPEC.md`.
* **No `ECOLOGICAL` domain** and no P1 RAG, translation or route tools.
* **The gazetteer is a 12-entry placeholder.** Anything outside it asks the user
  rather than guessing, which is the right failure but a narrow one.
* **No import-linter in CI.** The contracts are asserted by
  `tests/unit/test_import_boundaries.py` (80 assertions) rather than at build
  time.
