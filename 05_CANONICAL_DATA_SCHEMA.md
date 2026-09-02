# ORCA — Canonical Data Schema

**Document:** 05 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Schema defined — IMPLEMENTATION REQUIRED

---

## 1. Purpose and Principles

Every value that enters ORCA's reasoning layer is represented in this canonical model,
regardless of which provider it came from or what format it arrived in. Agents, the
geospatial kernel, the assessment engine and the API all operate on these types.

**P1 — One representation.** ERDDAP NetCDF, CMEMS NetCDF, IMD JSON, WMS imagery and
MarineRegions polygons all normalise to the same object family.

**P2 — Provenance is not optional.** Every object carrying a value carries a
`provenance_id`. An object without resolvable provenance is invalid and is rejected by
the validator.

**P3 — Point and grid are equal citizens.** The model represents a single Argo profile
value and a 41×31 SST grid with the same envelope, provenance and quality semantics.

**P4 — Kind is explicit.** `value_kind` distinguishes `observed`, `forecast`, `derived`,
`model` and `interpretation`. No consumer may guess.

**P5 — Units and CRS are always explicit.** No implicit °C, no implicit metres, no
implicit EPSG:4326.

**P6 — Derivations are reproducible.** A derived value records its inputs, method,
method version and parameters.

**Implementation.** Pydantic v2 models in `backend/orca/schemas/`, with JSON Schema
exported to `docs/schemas/` for the frontend and for contract tests.

---

## 2. Type Index

| Type | Role |
|---|---|
| `OrcaEnvelope` | Transport wrapper for every tool/agent result |
| `SpatialRef` | Where a value applies |
| `TemporalRef` | When a value applies |
| `Provenance` | Where a value came from |
| `QualityMetadata` | How good it is |
| `Uncertainty` | How uncertain it is |
| `Observation` | A measured value |
| `Forecast` | A predicted value with lead time |
| `MarineWarning` | An official warning bulletin |
| `OceanField` | A gridded field |
| `RasterRef` | A reference to rendered/gridded imagery |
| `VectorFeature` | Geometry with attributes |
| `DerivedResult` | A computed value with derivation |
| `Assessment` | A per-domain verdict |
| `Conflict` | A material disagreement between sources |
| `Evidence` | An assessment/claim-facing view of a value |
| `Claim` | A sentence-level assertion bound to evidence |
| `Recommendation` | The composed user-facing output |
| `OrcaError` | A canonical failure record |

---

## 3. Enumerations

```python
ValueKind      = "observed" | "forecast" | "derived" | "model" | "interpretation"
Representation = "point" | "grid" | "raster" | "vector" | "bulletin"
EnvelopeStatus = "success" | "partial" | "empty" | "error"
QualityFlag    = "nominal" | "degraded" | "suspect" | "invalid" | "unknown"
Freshness      = "fresh" | "aging" | "stale" | "expired"
Domain         = "SAFETY" | "FISHING_SUITABILITY" | "ECOLOGICAL" | "REGULATORY"
Verdict        = "FAVOURABLE" | "MARGINAL" | "UNFAVOURABLE" | "UNSAFE" | "INSUFFICIENT_EVIDENCE"
RegStatus      = "PERMITTED" | "RESTRICTED" | "PROHIBITED" | "UNKNOWN"
Confidence     = "low" | "medium" | "high"
Disposition    = "AUTO_RELEASE" | "REVIEW_REQUIRED" | "BLOCKED"
Severity       = "INFO" | "ADVISORY" | "WATCH" | "WARNING" | "CRITICAL"
```

### 3.1 Canonical variable registry (extract)

Variable names are fixed at the ORCA boundary; adapters map provider names onto them.

| Canonical name | Canonical unit | Typical `value_kind` | Primary tool |
|---|---|---|---|
| `sst` | `degC` | observed | `get_sst` |
| `sst_anomaly` | `degC` | observed \| derived | `get_sst` |
| `chlorophyll_a` | `mg m-3` | observed | `get_chlorophyll` |
| `kd490` | `m-1` | observed | `get_chlorophyll` |
| `tsm` | `mg L-1` | observed | `get_chlorophyll` |
| `significant_wave_height` | `m` | forecast | `get_wave_conditions` |
| `peak_period` | `s` | forecast | `get_wave_conditions` |
| `mean_wave_direction` | `degree` | forecast | `get_wave_conditions` |
| `swell_height` | `m` | forecast | `get_wave_conditions` |
| `swell_period` | `s` | forecast | `get_wave_conditions` |
| `current_u` / `current_v` | `m s-1` | forecast | `get_currents` |
| `current_speed` / `current_direction` | `m s-1` / `degree` | derived | kernel |
| `wind_speed` / `wind_gust` | `m s-1` | observed \| forecast | `get_weather` |
| `wind_direction` | `degree` | observed \| forecast | `get_weather` |
| `precipitation` | `mm` | observed \| forecast | `get_weather` |
| `air_temperature` | `degC` | observed \| forecast | `get_weather` |
| `temperature` (sea, at depth) | `degC` | observed | `get_ocean_observations` |
| `salinity` | `1e-3` (PSU-equivalent, as published) | observed | `get_ocean_observations` |
| `pfz_advisory` | — | observed | `get_pfz` |
| `marine_warning_status` | — | observed | `get_marine_warnings` |
| `lightning_event` | — | observed | `get_lightning` |
| `point_in_boundary` | boolean | derived | `get_maritime_boundaries` |

Directions are meteorological/oceanographic per the source and the convention is recorded
in `Provenance.notes` (wind "from", current "towards") — the adapter must record which.

### 3.2 Canonical error codes

| Code | Class | Envelope status | Retry | Meaning |
|---|---|---|---|---|
| `SOURCE_UNAVAILABLE` | availability | error | yes | Source unreachable (DNS/TCP/TLS/5xx) |
| `AUTH_REQUIRED` | availability | error | **no** | Credentials missing/invalid (e.g. 401/403) |
| `DATASET_UNAVAILABLE` | availability | error | no | Dataset/layer/product missing or renamed |
| `NO_DATA` | presence | empty | no | Valid query, nothing to return |
| `NO_ACTIVE_WARNING` | presence | empty | no | No warning in force — a **result** |
| `NO_ACTIVE_CYCLONE` | presence | empty | no | No cyclone in force — a **result** |
| `NO_BOUNDARIES_FOUND` | presence | empty | no | No boundary intersects the request |
| `STALE_DATA` | quality | partial | no | Beyond the parameter's staleness policy |
| `INSUFFICIENT_COVERAGE` | quality | partial | no | Partial spatial/temporal/valid-pixel coverage |
| `RASTER_ONLY` | representation | partial | no | Imagery only; no geometry |
| `VECTOR_UNAVAILABLE` | representation | partial | no | Geometry requested, not obtainable |
| `CONFLICTING_SOURCES` | cross-source | partial | no | Material disagreement, both retained |
| `AMBIGUOUS_AREA` | cross-source | partial | no | Affected area not resolvable to geometry |
| `INVALID_LOCATION` | input | error | no | Coordinates out of range/unusable |
| `INVALID_BBOX` | input | error | no | Malformed or oversized bbox |
| `INVALID_TIME_WINDOW` | input | error | no | Malformed or oversized time window |
| `SCHEMA_VALIDATION_FAILED` | internal | error | no | Object failed canonical validation |
| `ADAPTER_ERROR` | internal | error | maybe | Unexpected adapter failure |
| `TIMEOUT` | internal | error | yes | Budget exceeded |
| `RATE_LIMITED` | internal | error | yes (backoff) | Provider throttling |

---

## 4. Common Envelope — `OrcaEnvelope`

```json
{
  "envelope_version": "1.0",
  "status": "success",
  "tool": "get_sst",
  "request_id": "tr-01JBQ7F2K9",
  "run_id": "run-01JBQ7F0AA",
  "data": [],
  "provenance": [],
  "quality": {},
  "conflicts": [],
  "warnings": [],
  "errors": [],
  "source_resolution": {
    "primary_source": "S-02",
    "actual_source": "S-02",
    "fallback_used": false,
    "fallback_reason": null,
    "attempts": [{"source_id": "S-02", "outcome": "success", "duration_ms": 1180}]
  },
  "timing": {"started_at": "2026-09-02T11:04:34.1Z",
             "finished_at": "2026-09-02T11:04:35.3Z", "duration_ms": 1180},
  "cache": {"cache_hit": false, "ttl_s": 3600}
}
```

| Field | Semantics |
|---|---|
| `envelope_version` | Schema version; consumers reject unknown majors |
| `status` | See `EnvelopeStatus`. `empty` is **not** a failure |
| `data` | Heterogeneous array of canonical data objects |
| `provenance` | One record per `provenance_id` referenced in `data` |
| `quality` | Envelope-level roll-up (coverage, freshness, worst flag) |
| `conflicts` | `Conflict[]` if cross-source disagreement was detected |
| `warnings` | Non-fatal notices (`FALLBACK_USED`, `LOCATION_ON_LAND`, …) |
| `errors` | `OrcaError[]`; present even when `status` is `empty`/`partial` |
| `source_resolution` | Which source was asked, which answered, and why |

**Invariant.** For every `d ∈ data`, `d.provenance_id` resolves to exactly one entry in
`provenance`. Violation ⇒ `SCHEMA_VALIDATION_FAILED`.

---

## 5. Spatial Model — `SpatialRef`

Four spatial shapes, one type. CRS is always explicit; internal canonical CRS is
EPSG:4326 with lon/lat ordering (GeoJSON convention).

```json
{ "kind": "point", "crs": "EPSG:4326", "coordinates": [76.26, 9.93] }
```
```json
{ "kind": "bbox", "crs": "EPSG:4326",
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0} }
```
```json
{ "kind": "grid", "crs": "EPSG:4326",
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
  "shape": [41, 31], "lat_step": 0.1, "lon_step": 0.1,
  "origin": "upper_left", "lat_ascending": false }
```
```json
{ "kind": "geometry", "crs": "EPSG:4326",
  "geometry": {"type": "Polygon", "coordinates": [[[75.0,8.0],[78.0,8.0],[78.0,12.0],[75.0,12.0],[75.0,8.0]]]} }
```

Optional fields on any `SpatialRef`:

| Field | Semantics |
|---|---|
| `depth_m` | Depth of validity (0 = surface); positive downward |
| `nearest_node_distance_km` | Distance from the requested point to the served grid node |
| `area_description` | Human/source description ("Kerala coast", "sea area off Kochi") when geometry is unavailable |
| `representation` | `point \| grid \| raster \| vector \| bulletin` |

**Rules.** Degrees are never used for distance or area; geodesic (`pyproj.Geod`) or an
equal-area projection is used and the method is recorded. Any transform is logged with
source and target CRS.

---

## 6. Temporal Model — `TemporalRef`

```json
{
  "valid_time": "2026-09-03T00:30:00Z",
  "valid_from": "2026-09-03T00:00:00Z",
  "valid_to": "2026-09-03T03:00:00Z",
  "reference_time": "2026-09-02T12:00:00Z",
  "lead_time_h": 12.5,
  "temporal_resolution": "PT3H",
  "representativeness": "instantaneous",
  "retrieved_at": "2026-09-02T11:04:31Z",
  "timezone_display": "Asia/Kolkata"
}
```

| Field | Semantics |
|---|---|
| `valid_time` | The instant the value applies to (required) |
| `valid_from` / `valid_to` | Validity interval for interval-valid products (warnings, daily composites, 10-day analyses) |
| `reference_time` | Forecast cycle / analysis reference (model run time) |
| `lead_time_h` | `valid_time − reference_time` in hours; null for observations |
| `temporal_resolution` | ISO-8601 duration as published |
| `representativeness` | `instantaneous \| hourly_mean \| daily_composite \| 10day_mean \| monthly_mean \| bulletin_period` |
| `retrieved_at` | When ORCA fetched it (never rewritten by caching) |

**Rule.** `representativeness` is what prevents a monthly analysis being used as a
next-morning forecast. The assessment engine enforces a per-domain allow-list of
acceptable representativeness values (`12_RISK_AND_RECOMMENDATION_SPEC.md`).

**Freshness** is computed as a function of `valid_time`, `retrieved_at`, `now` and the
per-parameter cadence policy, and is stored in `QualityMetadata.freshness`.

---

## 7. Provenance Model — `Provenance`

```json
{
  "provenance_id": "pv-s21",
  "parameter": "sst",
  "value_kind": "observed",
  "unit": "degC",
  "spatial": { "kind": "grid", "crs": "EPSG:4326", "…": "…" },
  "temporal": { "valid_time": "2026-09-02T00:00:00Z", "…": "…" },

  "source": "INCOIS ERDDAP",
  "source_id": "S-02",
  "organisation": "INCOIS (MoES)",
  "dataset": "NOAA_AVHRR_AMSR_datasets",
  "dataset_version": null,
  "product_reference": "<published product/dataset reference>",
  "access_method": "ERDDAP griddap",
  "external_source": false,

  "retrieved_at": "2026-09-02T11:04:35Z",
  "request_fingerprint": "sha256:9f2c…",
  "response_bytes": 148213,
  "cache_hit": false,

  "spatial_resolution": "<as published>",
  "temporal_resolution": "<as published>",
  "quality": { "flag": "nominal", "basis": "source-provided", "coverage_fraction": 0.83 },

  "fallback_used": false,
  "fallback_reason": null,
  "derivation": null,
  "notes": "wind direction convention not applicable",
  "licence_reference": "<source terms-of-use reference>"
}
```

### 7.1 `derivation` (required when `value_kind = "derived"`)

```json
{
  "method": "anomaly_vs_window_mean",
  "method_version": "1.2",
  "inputs": ["pv-s21", "pv-s22"],
  "params": {"window": "P10D", "aggregation": "mean", "mask": "cloud_flagged"},
  "computed_at": "2026-09-02T11:04:40Z",
  "code_reference": "orca.geospatial.anomaly:anomaly_vs_window_mean"
}
```

**Rules.**
- A derived value must be recomputable from `inputs` + `method` + `params`.
- `inputs` are provenance IDs, never inlined copies.
- `interpretation` values (LLM-authored statements) carry a `derivation` whose `inputs`
  are the evidence IDs they were generated from and whose `method` is
  `llm_synthesis` with the prompt template id and model identifier — but **never** the
  model's chain-of-thought.

### 7.2 Provenance chain

```
pv-s21 (observed SST field, ERDDAP)
   └─> pv-d09 (derived sst_anomaly, method anomaly_vs_window_mean v1.2)
          └─> ev-014 (Evidence for FISHING_SUITABILITY)
                 └─> cl-003 (Claim: "SST is 0.4 °C above the 10-day mean")
                        └─> answer sentence #2
```

---

## 8. Quality Model — `QualityMetadata`

```json
{
  "flag": "nominal",
  "basis": "source-provided",
  "freshness": "fresh",
  "staleness_s": 39600,
  "coverage_fraction": 0.83,
  "masked_reason": "cloud/fill",
  "nearest_node_distance_km": 6.2,
  "lead_time_h": 19,
  "representativeness_match": true,
  "validation_checks": [
    {"check": "range_check", "result": "pass", "detail": "-2..40 degC"},
    {"check": "coverage_min", "result": "pass", "detail": "0.83 >= 0.60"}
  ]
}
```

| Field | Semantics |
|---|---|
| `flag` | Worst quality state for this value |
| `basis` | `source-provided` \| `orca-computed` \| `unknown` — never claim a source flag ORCA invented |
| `freshness` | Derived state (see §6) |
| `coverage_fraction` | Valid (unmasked) fraction of the requested area/time |
| `nearest_node_distance_km` | Spatial mismatch between request and served node |
| `representativeness_match` | Whether the product's representativeness is acceptable for the requesting domain |
| `validation_checks` | Explicit list of checks run and their outcome |

Quality **never** silently removes data. A `suspect` or `invalid` value is retained with
its flag; the assessment engine decides whether to use it and records that decision.

---

## 9. Uncertainty Model — `Uncertainty`

Four independent uncertainty types, never merged into one number:

```json
{
  "value_uncertainty": {"type": "std_dev", "value": 0.3, "unit": "degC",
                        "basis": "source-provided"},
  "spatial_uncertainty": {"nearest_node_distance_km": 6.2,
                          "grid_spacing_km": 9.0, "basis": "orca-computed"},
  "temporal_uncertainty": {"lead_time_h": 19, "representativeness": "instantaneous",
                           "staleness_s": 0},
  "evidence_sufficiency": {"required": ["wind","waves","warnings","lightning"],
                           "available": ["wind","waves","warnings"],
                           "missing": ["lightning"],
                           "missing_reason": {"lightning": "AUTH_REQUIRED"}}
}
```

**Rules.**
- `value_uncertainty` is populated **only** when the source publishes it. ORCA does not
  invent error bars.
- `evidence_sufficiency` is the dominant driver of assessment confidence in the MVP,
  because most sources do not publish per-value uncertainty.
- Confidence exposed to users is a three-level qualitative label with the contributing
  factors listed. No false-precision percentages.

---

## 10. Observation Model — `Observation`

A measured value at a point (and optionally a depth).

```json
{
  "type": "Observation",
  "parameter": "temperature",
  "value": 28.63,
  "unit": "degC",
  "value_kind": "observed",
  "spatial": {"kind": "point", "crs": "EPSG:4326",
              "coordinates": [75.82, 9.21], "depth_m": 5.0},
  "temporal": {"valid_time": "2026-09-01T06:12:00Z",
               "representativeness": "instantaneous",
               "retrieved_at": "2026-09-02T11:04:36Z"},
  "quality": {"flag": "nominal", "basis": "source-provided"},
  "uncertainty": null,
  "platform": {"type": "argo_float", "identifier": "<platform id if published>"},
  "provenance_id": "pv-o07"
}
```

---

## 11. Forecast Model — `Forecast`

A predicted value; identical to `Observation` except `value_kind = "forecast"` and the
temporal block carries `reference_time` and `lead_time_h`.

```json
{
  "type": "Forecast",
  "parameter": "significant_wave_height",
  "value": 2.4,
  "unit": "m",
  "value_kind": "forecast",
  "spatial": {"kind": "point", "crs": "EPSG:4326", "coordinates": [76.10, 9.85],
              "nearest_node_distance_km": 6.2},
  "temporal": {"valid_time": "2026-09-03T00:30:00Z",
               "reference_time": "2026-09-02T12:00:00Z",
               "lead_time_h": 12.5, "temporal_resolution": "PT3H",
               "representativeness": "instantaneous",
               "retrieved_at": "2026-09-02T11:04:37Z"},
  "quality": {"flag": "nominal", "basis": "source-provided", "freshness": "fresh"},
  "provenance_id": "pv-w14"
}
```

---

## 12. Warning Model — `MarineWarning`

Official bulletins are a distinct type because they are quoted, not computed.

```json
{
  "type": "MarineWarning",
  "warning_id": "<issuing-office bulletin id>",
  "warning_type": "fishermen",
  "severity": "WARNING",
  "issuing_office": "IMD <office>",
  "issued_at": "2026-09-02T03:00:00Z",
  "valid_from": "2026-09-02T03:00:00Z",
  "valid_to": "2026-09-04T03:00:00Z",
  "affected_area": {"kind": "geometry", "crs": "EPSG:4326",
                    "geometry": {"type": "MultiPolygon", "coordinates": []}},
  "area_description": "Along and off Kerala coast",
  "area_resolved": true,
  "text_verbatim": "<bulletin text exactly as issued>",
  "language": "en",
  "bulletin_reference": "<url or document id>",
  "value_kind": "observed",
  "is_official": true,
  "provenance_id": "pv-wn1"
}
```

**Rules.**
- `text_verbatim` is stored and quoted **unmodified**. Any ORCA paraphrase is a separate
  `interpretation` object referencing this warning.
- `is_official: true` is set **only** for content retrieved from an official issuing
  authority. ORCA-generated advisories always carry `is_official: false`.
- If the affected area cannot be resolved to geometry, `area_resolved` is `false`, the
  envelope carries `AMBIGUOUS_AREA`, and no polygon is fabricated.
- A `MarineWarning` never carries a numeric "risk value".

---

## 13. Gridded Data — `OceanField`

The canonical representation for any gridded scientific field.

```json
{
  "type": "OceanField",
  "parameter": "sst",
  "unit": "degC",
  "value_kind": "observed",
  "spatial": {"kind": "grid", "crs": "EPSG:4326",
              "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
              "shape": [41, 31], "lat_step": 0.1, "lon_step": 0.1,
              "origin": "upper_left", "lat_ascending": false, "depth_m": 0},
  "temporal": {"valid_time": "2026-09-02T00:00:00Z",
               "representativeness": "daily_composite",
               "temporal_resolution": "P1D",
               "retrieved_at": "2026-09-02T11:04:35Z"},
  "values_ref": "orca://fields/f-3391",
  "values_inline": null,
  "fill_value": null,
  "mask_ref": "orca://fields/f-3391/mask",
  "summary": {"min": 27.1, "max": 29.8, "mean": 28.6, "median": 28.7,
              "p10": 27.9, "p90": 29.4, "count_valid": 1041, "count_total": 1271,
              "coverage_fraction": 0.819},
  "quality": {"flag": "nominal", "basis": "source-provided", "coverage_fraction": 0.819,
              "masked_reason": "cloud/fill"},
  "provenance_id": "pv-s21"
}
```

| Field | Semantics |
|---|---|
| `values_ref` | Pointer to the array payload in object storage / cache. **Grid arrays never travel inside JSON responses.** |
| `values_inline` | Small grids only (≤ configured cell count), for tests and debugging |
| `mask_ref` | Validity mask; masked cells are excluded from `summary` |
| `summary` | Deterministically computed statistics over valid cells only |

**Point extraction** from a field produces an `Observation`/`Forecast` with
`value_kind` preserved and `derivation` recording the interpolation method
(`nearest_node` or `bilinear`) and the node distance — extraction is a derivation, not a
free operation.

---

## 14. Raster Reference — `RasterRef`

For rendered imagery (e.g. WMS `GetMap`) where **no numeric values are available**.

```json
{
  "type": "RasterRef",
  "parameter": "pfz_advisory",
  "representation": "raster",
  "value_kind": "observed",
  "raster_uri": "orca://layers/pfz/2026-09-03/tiles/{z}/{x}/{y}.png",
  "source_request": {"service": "WMS", "version": "1.3.0", "layer": "<layer name>",
                     "crs": "EPSG:4326", "time": "2026-09-03"},
  "spatial": {"kind": "bbox", "crs": "EPSG:4326",
              "bbox": {"min_lat": 9.4, "min_lon": 75.8, "max_lat": 10.4, "max_lon": 76.7}},
  "temporal": {"valid_time": "2026-09-03T00:00:00Z", "retrieved_at": "2026-09-02T11:04:39Z"},
  "legend_uri": "orca://layers/pfz/2026-09-03/legend.json",
  "numeric_values_available": false,
  "geometry_available": false,
  "provenance_id": "pv-p11"
}
```

**Rule.** A `RasterRef` may be **displayed** and **cited**, but never spatially tested,
measured or converted to geometry. Any consumer attempting a spatial predicate against a
`RasterRef` must fail with `VECTOR_UNAVAILABLE` rather than approximating.

---

## 15. Vector Geometry — `VectorFeature`

```json
{
  "type": "VectorFeature",
  "feature_id": "eez-ind",
  "parameter": "maritime_boundary",
  "boundary_type": "EEZ",
  "name": "Indian Exclusive Economic Zone",
  "jurisdiction": "India",
  "attributes": {"mrgid": "<identifier as published>", "area_km2": null},
  "geometry_ref": "orca://geo/eez-ind",
  "geometry_inline": null,
  "spatial": {"kind": "geometry", "crs": "EPSG:4326"},
  "temporal": {"valid_from": "<effective date>", "valid_to": null,
               "retrieved_at": "2026-09-02T11:04:40Z"},
  "dataset_version": "<product version>",
  "advisory_only": true,
  "value_kind": "observed",
  "provenance_id": "pv-b01"
}
```

Geometry is delivered to clients as RFC 7946 GeoJSON (lon/lat, right-hand winding).
Large geometries are referenced, not inlined; simplification is applied for display only
and is recorded (`display_simplification_tolerance`), never used for predicates.

---

## 16. Derived Result — `DerivedResult`

```json
{
  "type": "DerivedResult",
  "parameter": "sst_anomaly",
  "value": 0.42,
  "unit": "degC",
  "value_kind": "derived",
  "spatial": {"kind": "point", "crs": "EPSG:4326", "coordinates": [76.10, 9.85]},
  "temporal": {"valid_time": "2026-09-02T00:00:00Z"},
  "derivation": {
    "method": "anomaly_vs_window_mean",
    "method_version": "1.2",
    "inputs": ["pv-s21", "pv-s22"],
    "params": {"window": "P10D", "aggregation": "mean", "mask": "cloud_flagged"},
    "computed_at": "2026-09-02T11:04:41Z",
    "code_reference": "orca.geospatial.anomaly:anomaly_vs_window_mean"
  },
  "quality": {"flag": "nominal", "basis": "orca-computed"},
  "provenance_id": "pv-d09"
}
```

Standard MVP derivations: `sst_anomaly`, `current_speed`/`current_direction`,
`field_point_extraction`, `field_area_statistics`, `spatiotemporal_alignment`,
`point_in_polygon`, `distance_to_feature`, `corridor_sampling` (P1). Each has a
registered method id, version, unit test and reference fixture
(`11_GEOSPATIAL_REASONING_SPEC.md`).

---

## 17. Conflict Model — `Conflict`

```json
{
  "conflict_id": "cf-002",
  "parameter": "significant_wave_height",
  "spatial": {"kind": "point", "crs": "EPSG:4326", "coordinates": [76.10, 9.85]},
  "temporal": {"valid_time": "2026-09-03T00:30:00Z"},
  "candidates": [
    {"provenance_id": "pv-w14", "source_id": "S-07", "value": 2.4, "unit": "m"},
    {"provenance_id": "pv-w31", "source_id": "S-11", "value": 3.1, "unit": "m"}
  ],
  "delta": {"absolute": 0.7, "relative": 0.29},
  "tolerance": {"absolute": 0.5, "relative": 0.20,
                "basis": "initial engineering parameter — SCIENTIFIC VALIDATION REQUIRED"},
  "material": true,
  "safety_relevant": true,
  "resolution": {
    "policy": "retain_both_and_use_conservative",
    "used_provenance_id": "pv-w31",
    "rationale": "Safety-relevant parameter; the more adverse value is used for the "
                 "safety assessment while both values are reported.",
    "human_review_required": true
  }
}
```

**Rules.**
- Both values are always retained and both are shown.
- `resolution.policy` is one of `retain_both_and_report`,
  `retain_both_and_use_conservative` (safety domain), `prefer_primary_authority`
  (documented, non-safety), `insufficient_to_resolve`.
- A material, safety-relevant conflict sets the run disposition to `REVIEW_REQUIRED`.
- ORCA never deletes the losing value from the record.

---

## 18. Evidence and Claim

`Evidence` is the assessment-facing view of a value; `Claim` is a sentence-level assertion
in the answer.

```json
{
  "type": "Evidence",
  "evidence_id": "ev-014",
  "domain": "SAFETY",
  "statement": "Significant wave height reaches 2.4 m at 06:00 IST near the query point.",
  "parameter": "significant_wave_height",
  "value": 2.4,
  "unit": "m",
  "value_kind": "forecast",
  "provenance_id": "pv-w14",
  "supports": ["threshold:small_craft_hs_marginal"],
  "weight": "primary"
}
```

```json
{
  "type": "Claim",
  "claim_id": "cl-003",
  "text": "Sea state is marginal for small craft tomorrow morning.",
  "claim_kind": "interpretation",
  "evidence_ids": ["ev-014", "ev-015"],
  "domain": "SAFETY",
  "confidence": "medium",
  "official_source": false
}
```

**Binding rule.** Every material claim in a delivered answer must reference ≥ 1
`evidence_id`. The evidence-binding validator rejects an answer containing an unbound
material claim (`15_EVALUATION_AND_TESTING_SPEC.md` §Grounding).

---

## 19. Assessment Model — `Assessment`

One per domain. Never merged.

```json
{
  "type": "Assessment",
  "assessment_id": "as-safety-01",
  "domain": "SAFETY",
  "verdict": "MARGINAL",
  "confidence": "medium",
  "spatial": {"kind": "point", "crs": "EPSG:4326", "coordinates": [76.26, 9.93]},
  "temporal": {"valid_from": "2026-09-03T00:00:00Z", "valid_to": "2026-09-03T04:00:00Z"},
  "drivers": [
    {"factor": "significant_wave_height", "value": 2.4, "unit": "m",
     "threshold_id": "small_craft_hs_marginal", "contribution": "limiting",
     "evidence_id": "ev-014"},
    {"factor": "wind_speed", "value": 11.3, "unit": "m s-1",
     "threshold_id": "small_craft_wind_ok", "contribution": "supporting",
     "evidence_id": "ev-015"}
  ],
  "not_evaluated": [{"factor": "lightning", "reason": "AUTH_REQUIRED"}],
  "official_warning_status": {"status": "none_active", "evidence_id": "ev-011"},
  "uncertainty": { "evidence_sufficiency": {"missing": ["lightning"]} },
  "threshold_set": {"id": "small_craft_v0.1",
                    "status": "SCIENTIFIC VALIDATION REQUIRED"},
  "conflicts": ["cf-002"],
  "disposition": "REVIEW_REQUIRED",
  "value_kind": "interpretation",
  "provenance_id": "pv-as1"
}
```

---

## 20. Recommendation Model — `Recommendation`

The composed, user-facing result. It **contains** assessments; it does not replace them.

```json
{
  "type": "Recommendation",
  "recommendation_id": "rc-01JBQ7",
  "run_id": "run-01JBQ7F0AA",
  "query_text": "I'm near Kochi. Is tomorrow morning a good time to go fishing, and if not, why?",
  "language": "en",
  "resolved_context": {
    "location": {"kind": "point", "crs": "EPSG:4326", "coordinates": [76.26, 9.93],
                 "label": "near Kochi"},
    "time_window": {"valid_from": "2026-09-03T00:00:00Z", "valid_to": "2026-09-03T04:00:00Z",
                    "display": "03 Sep 05:30–09:30 IST"}
  },
  "assessments": ["as-safety-01", "as-fishing-01", "as-regulatory-01"],
  "headline": "Fishing conditions look favourable, but sea state is marginal for small craft.",
  "limiting_factor": {"domain": "SAFETY", "factor": "significant_wave_height"},
  "narrative": "…",
  "claims": ["cl-001", "cl-002", "cl-003"],
  "reasoning_summary": "Checked official warnings (none active), wave and wind forecasts, "
                       "PFZ advisory (imagery only), SST and chlorophyll. Wave height is "
                       "the limiting factor; lightning could not be checked.",
  "official_content": [{"warning_id": null, "quoted": false}],
  "is_official_advisory": false,
  "disclaimer_id": "disc.not_official_advisory",
  "confidence": "medium",
  "disposition": "REVIEW_REQUIRED",
  "human_review": null,
  "evidence_ids": ["ev-011", "ev-014", "ev-015", "ev-021", "ev-022"],
  "conflicts": ["cf-002"],
  "not_evaluated": [{"factor": "lightning", "reason": "AUTH_REQUIRED"},
                    {"factor": "pfz_geometry", "reason": "RASTER_ONLY"}],
  "generated_at": "2026-09-02T11:04:44Z"
}
```

`human_review`, when present:

```json
{
  "reviewer_id": "usr-…", "reviewer_role": "officer",
  "decision": "approved_with_edits",
  "reviewed_at": "2026-09-02T11:09:10Z",
  "original_headline": "…", "edited_headline": "…",
  "rationale": "Wave conflict resolved in favour of the more adverse forecast.",
  "audit_id": "aud-…"
}
```

**Rule.** `is_official_advisory` is `false` for every ORCA-generated recommendation. Only
quoted `MarineWarning` content carries official status, and it is attributed to its
issuing office.

---

## 21. Error Model — `OrcaError`

```json
{
  "code": "AUTH_REQUIRED",
  "severity": "error",
  "subject": "lightning",
  "detail": "IMD lightning endpoint requires credentials; request returned 403.",
  "source_id": "S-05",
  "tool": "get_lightning",
  "occurred_at": "2026-09-02T11:04:33Z",
  "retryable": false,
  "user_message_id": "err.auth_required.lightning",
  "trace_id": "01JBQ7F2K9…"
}
```

| Field | Semantics |
|---|---|
| `severity` | `info` (e.g. `NO_ACTIVE_WARNING`) \| `warning` (degradation) \| `error` (capability lost) |
| `subject` | What was being retrieved — carries the specificity that legacy per-tool codes had |
| `user_message_id` | i18n key; user-facing text is never the raw code |
| `retryable` | Drives the retry/replan policy in the graph |

---

## 22. Point vs Grid — Worked Comparison

Same parameter, same provenance discipline, two representations.

```json
// POINT — nearest-node extraction from a field
{"type": "Forecast", "parameter": "significant_wave_height", "value": 2.4, "unit": "m",
 "spatial": {"kind": "point", "coordinates": [76.10, 9.85], "crs": "EPSG:4326",
             "nearest_node_distance_km": 6.2},
 "temporal": {"valid_time": "2026-09-03T00:30:00Z", "lead_time_h": 12.5},
 "value_kind": "forecast", "provenance_id": "pv-w14"}
```
```json
// GRID — the field it was extracted from
{"type": "OceanField", "parameter": "significant_wave_height", "unit": "m",
 "spatial": {"kind": "grid", "crs": "EPSG:4326", "shape": [49, 37],
             "lat_step": 0.083, "lon_step": 0.083, "bbox": {"…": "…"}},
 "temporal": {"valid_time": "2026-09-03T00:30:00Z", "lead_time_h": 12.5},
 "values_ref": "orca://fields/f-4102",
 "summary": {"min": 1.1, "max": 3.3, "mean": 2.2, "coverage_fraction": 1.0},
 "value_kind": "forecast", "provenance_id": "pv-w13"}
```

The point's provenance records the extraction as a derivation from `pv-w13`, so the
evidence panel can show *"extracted from the CMEMS wave field by nearest-node, 6.2 km"*.

---

## 23. Versioning and Validation

- `envelope_version` follows semantic versioning; a major bump requires a migration note
  in `24_ENGINEERING_DECISIONS.md`.
- Every object is validated on construction (adapter output), on tool return, on graph
  state write and on API serialisation. Validation failure ⇒ `SCHEMA_VALIDATION_FAILED`,
  logged with the offending field path; the run continues in degraded mode rather than
  emitting an unvalidated value.
- JSON Schema artifacts are generated into `docs/schemas/` and consumed by frontend types
  and contract tests, so the frontend cannot drift from the backend model.
- Round-trip tests (`Python object → JSON → Python object`) are required for every type
  (`15_EVALUATION_AND_TESTING_SPEC.md`).
