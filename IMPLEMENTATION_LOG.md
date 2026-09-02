# ORCA — Implementation Log

**Session:** 2026-09-02 · **Phase:** design set → Phase 1–6 partial
**State at end of session:** ~55% of backend logic · 5,760 lines implementation ·
1,348 lines tests · 122 tests passing (0.25 s, all offline)

*Session 2 added the MarineRegions boundary adapter and the REGULATORY domain
(§10). Everything above §10 describes the state after session 1 and is still
current except where §10 says otherwise.*

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
| Phase 4 — agents | **Not started** |
| Phase 5 — LangGraph | **Not started** |
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
section it owns (D-17).

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

`AUTH REQUIRED` holds for the subsetting/download services, **not** for the ARCO object
store. Datasets bound (ids read from the public STAC catalogue, not guessed):

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

### D-12 · Upstream fixtures are recorded, never hand-authored
`tests/fixtures/upstream/` carries capture dates. A hand-written fixture would make the
adapter suite test a fiction.

---

## 5. Deviations From the Design Documents

| Document | Deviation | Reason |
|---|---|---|
| `03` §5/§7 — CMEMS `AUTH REQUIRED` | ARCO store needs no credentials | Verified live; recorded in §15 |
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

**O-5 · The boundary implication table needs legal review** (D-17). It encodes the
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
| CMEMS credentials | **not needed** for current use | — |
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
4. **IMD adapter** — build to spec now so it works the day credentials arrive; it
   already degrades correctly.
5. **Documents 23–30** — diagrams, ADRs (fold in §4 and §10.3 above), gap register,
   judge Q&A, traceability, glossary, quickstart, definition of done.
6. **Boundary follow-ups** (small, from §10.2): widen the snapshot region east of 90 E
   so Andaman and Nicobar positions can be answered; get the VLIZ licence review done
   (`14` §"terms"); find a source for restricted/naval zones, which is the one gap that
   could turn a `PERMITTED` into something else.

---

## 9. How to Run

```bash
python3 -m venv .venv
./.venv/bin/pip install pydantic httpx certifi truststore numcodecs numpy pyyaml pytest

./.venv/bin/python -m pytest tests -q                 # 122 offline tests
./.venv/bin/python scripts/capture_datasets.py        # live INCOIS metadata capture
./.venv/bin/python -m scripts.capture_boundaries      # live MarineRegions snapshot
./.venv/bin/python -m backend.orca.cli.query          # vertical slice, live
./.venv/bin/python -m backend.orca.cli.query --when 2011-06-15T00:30:00
./.venv/bin/python -m backend.orca.cli.query --lat 7.00 --lon 79.30 --label "west of Colombo"
```

**Run `capture_boundaries` first.** `data/boundaries/` is git-ignored
(`18_REPOSITORY_STRUCTURE.md` §6), so a fresh clone has no boundary geometry and
`get_maritime_boundaries` returns `DATASET_UNAVAILABLE` naming the script — which is the
correct degradation, not a bug. The capture takes about 35 s and writes 7.2 MB. Pin a
snapshot with `ORCA_MARINEREGIONS_SNAPSHOT_VERSION` so a deployment cannot drift onto
newer geometry unnoticed.

The archive-date invocation targets a date inside ERDDAP's archive coverage and shows the
pipeline producing a verdict from historical data — useful for demonstrating the
reasoning path independently of current data availability. The Colombo invocation shows
`REGULATORY = RESTRICTED` overriding a safety refusal in the headline.

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

| ID | Finding |
|---|---|
| **F-13** | The layers declare `urn:ogc:def:crs:EPSG::4326`, so CQL `BBOX` is read **latitude first**. The first capture asked for the Indian Ocean and got Svalbard and the Russian Arctic — a plausible-looking, entirely wrong, non-empty result. |
| **F-15** | `eez_12nm` and `eez_24nm` are **bands from the baseline, not nested discs**. 5 NM offshore is inside the territorial sea and outside the contiguous zone; 20 NM offshore is the reverse. Treating them as nested is wrong in both directions. |
| **F-16** | `eez_internal_waters` publishes **nothing for Sri Lanka**. "Outside every internal-waters polygon" there is a gap in the source, not a fact about the point, and is downgraded to *not evaluated for this jurisdiction* (D-16). |
| **F-17** | The service publishes **no version field** — only a release year inside the layer title. The capture parses it and **fails** rather than writing geometry that cannot be cited. |

### 10.3 Design decisions

#### D-13 · A versioned local snapshot, not a query-time WFS call
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

#### D-14 · Coverage is a declared region, and outside it the answer is refusal
**Context.** A snapshot holds the features intersecting a bbox. Outside that bbox,
"inside no boundary" is indistinguishable from "we did not look".
**Decision.** The snapshot records its region. A query outside it returns
`INSUFFICIENT_COVERAGE` and no containment result at all.
**Rationale.** Same principle as D-3: *could not check* must never become *nothing
found*. The failure this prevents is a vessel being told it is in international waters
because the snapshot stopped at 90 E.

#### D-15 · Boundary types are evaluated independently; the worst governs
**Context.** F-15 — the zones are bands, not a hierarchy.
**Decision.** Each type is tested separately and mapped through a configured implication
(`home` / `foreign` / `none`); the most constraining outcome governs. Never averaged,
never inferred from a neighbouring type.
**Consequence.** Inside a foreign territorial sea is `PROHIBITED` even though the
surrounding EEZ alone would be `RESTRICTED`.

#### D-16 · A layer with no feature for this jurisdiction cannot say "outside"
**Context.** F-16.
**Decision.** After containment, the adapter checks whether the governing EEZ's
sovereign appears at all in each other layer. If not, that type is flagged and the
assessment lists it as `INSUFFICIENT_COVERAGE`, not as unconstrained.
**Rationale.** The error is asymmetric: an unchecked internal-waters polygon can only
make the answer more restrictive, never less. Reporting it as "outside" would understate
a restriction, which is the direction that gets someone arrested.

#### D-17 · The geometry is a fact; what it means is a legal judgement, and they live apart
**Context.** "Inside another state's EEZ ⇒ needs authorisation" is not something an
adapter should assert, and not something an engineer should encode as a constant.
**Decision.** The adapter reports only what the source publishes — sovereign, territory,
ISO code, distance. `config/boundaries.yaml` carries the implication table, marked
`LEGAL_REVIEW_REQUIRED`, and `assessment/jurisdiction.py` reads it. The adapter and the
assessment read different sections of the same file and do not import each other.
**Consequence.** Every regulatory answer surfaces `LEGAL_REVIEW_REQUIRED`, exactly as
threshold-based answers surface `SCIENTIFIC_VALIDATION_REQUIRED`.

#### D-18 · An unevaluated boundary type is named in every answer
**Context.** `04` §3.11 rule 2 — an EEZ polygon is not a fishing regulation zone.
**Decision.** `boundary_types` defaults to every type ORCA has a policy for, including
the four with no source (MPA, restricted zone, fishing regulation zone, seasonal
closure). Each returns `DATASET_UNAVAILABLE` and appears under `not_evaluated`.
**Rationale.** An answer that quietly omitted restricted zones would read as "you are
clear". A `PERMITTED` verdict with unchecked restrictions is therefore capped at medium
confidence — an unchecked naval exercise area can only make things worse.

#### D-19 · A regulatory constraint outranks a safety refusal in the headline
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
| `04` §3.11 / `09` §4.2 — PostGIS snapshot | Flat `.npz` arrays + JSON manifest | D-13; no PostGIS in the project yet. The interface is unchanged and the store is swappable |
| `06` §476 — `REGULATORY PERMITTED confidence high` | `PERMITTED` is capped at **medium** while restriction-bearing types are unevaluated | D-18 |
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
* **East of 90 E is uncovered** by the default snapshot (F-18).

---

**ORCA output is not an official advisory. Follow IMD and INCOIS bulletins.**
