# ORCA — Capability Tool Contracts

**Document:** 04 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Supersedes:** `04_ORCA_TOOL_CONTRACTS.md` v0.1
**Status:** Contracts defined — IMPLEMENTATION REQUIRED

---

## 1. Purpose

This document defines the capability-level tools exposed to ORCA's agents.

```
Agent  →  Capability Tool  →  Source Adapter  →  Data Source
```

Agents call capability tools. Capability tools call source adapters. Only source adapters
know URLs, credentials, query syntax and provider schemas.

**The Planner sees this and nothing more:**

```
get_weather              get_sst                    get_ocean_observations
get_marine_warnings      get_chlorophyll            get_maritime_boundaries
get_cyclone_track        get_wave_conditions
get_lightning            get_currents
get_pfz
```

It must **not** need to know: API URLs, authentication mechanisms, ERDDAP selector
syntax, WMS request parameters, CMEMS product identifiers, or any provider response
format. Those belong to adapters (`03_DATA_SOURCE_MATRIX.md`).

---

## 2. Contract Conventions

### 2.1 Common input types

| Type | Shape |
|---|---|
| `Point` | `{"lat": 9.93, "lon": 76.26}` — EPSG:4326, decimal degrees |
| `BBox` | `{"min_lat":…, "min_lon":…, "max_lat":…, "max_lon":…}` — EPSG:4326 |
| `TimeWindow` | `{"start_time": "<ISO-8601 UTC>", "end_time": "<ISO-8601 UTC>"}` |
| `Radius` | `radius_km: number` (used with `Point` to form an implicit bbox) |
| `variables` | array of canonical variable names (`05_CANONICAL_DATA_SCHEMA.md` §Variable registry) |

All times crossing a tool boundary are **UTC ISO-8601 with an explicit `Z`**. IST is a
presentation concern only.

### 2.2 Common output envelope

Every capability tool returns an `OrcaEnvelope`:

```json
{
  "status": "success | partial | empty | error",
  "tool": "get_sst",
  "request_id": "tr-01J…",
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
    "attempts": []
  },
  "timing": {"started_at": "…", "finished_at": "…", "duration_ms": 1180}
}
```

| `status` | Meaning |
|---|---|
| `success` | Requested information obtained |
| `partial` | Some of the request satisfied (`INSUFFICIENT_COVERAGE`, subset of variables) |
| `empty` | Query valid, source reachable, nothing to return (`NO_DATA`, `NO_ACTIVE_WARNING`, `NO_ACTIVE_CYCLONE`) — **not a failure** |
| `error` | Request could not be satisfied (`SOURCE_UNAVAILABLE`, `AUTH_REQUIRED`, `INVALID_BBOX`, …) |

### 2.3 Provenance requirement

Every element of `data` has a corresponding entry in `provenance`, joined by
`provenance_id`. Minimum fields:

```json
{
  "provenance_id": "pv-7c1",
  "parameter": "significant_wave_height",
  "value": 2.4,
  "unit": "m",
  "value_kind": "forecast",
  "location": {"type": "Point", "coordinates": [76.10, 9.85], "crs": "EPSG:4326"},
  "valid_time": "2026-09-03T00:30:00Z",
  "source": "CMEMS",
  "source_id": "S-07",
  "dataset": "<dataset id as published>",
  "product_reference": "<product reference>",
  "retrieved_at": "2026-09-02T11:04:31Z",
  "spatial_resolution": "<as published>",
  "temporal_resolution": "<as published>",
  "quality": {"flag": "nominal", "basis": "source-provided"},
  "external_source": true,
  "fallback_used": false,
  "request_fingerprint": "sha256:…"
}
```

Derived values additionally carry `derivation` (inputs, method, method version, params).

### 2.4 Canonical failure states

```
SOURCE_UNAVAILABLE   AUTH_REQUIRED        DATASET_UNAVAILABLE   NO_DATA
NO_ACTIVE_WARNING    NO_ACTIVE_CYCLONE    STALE_DATA            INSUFFICIENT_COVERAGE
INVALID_LOCATION     INVALID_BBOX         INVALID_TIME_WINDOW   RASTER_ONLY
VECTOR_UNAVAILABLE   CONFLICTING_SOURCES  AMBIGUOUS_AREA        NO_BOUNDARIES_FOUND
ADAPTER_ERROR        SCHEMA_VALIDATION_FAILED                   TIMEOUT   RATE_LIMITED
```

Legacy per-tool codes from v0.1 map as: `STALE_WARNING`/`STALE_TRACK`/`STALE_PRODUCT` →
`STALE_DATA`; `NO_LIGHTNING_DATA`/`NO_OBSERVATIONS`/`NO_PFZ_FOR_TIME` → `NO_DATA`;
`BOUNDARY_DATASET_UNAVAILABLE` → `DATASET_UNAVAILABLE`; `AMBIGUOUS_AFFECTED_AREA` →
`AMBIGUOUS_AREA`. Semantics are unchanged; the subject is carried in `errors[].subject`.

### 2.5 Universal validation rules

Applied by the tool layer **before** any adapter call:

| Rule | Failure |
|---|---|
| `-90 ≤ lat ≤ 90`, `-180 ≤ lon ≤ 180` | `INVALID_LOCATION` |
| `min_lat < max_lat`, `min_lon < max_lon`, bbox area ≤ configured max | `INVALID_BBOX` |
| `start_time < end_time`; window ≤ configured max span | `INVALID_TIME_WINDOW` |
| Forecast horizon within the product's published range | `INSUFFICIENT_COVERAGE` |
| Point/bbox is over water for ocean variables (land-mask pre-check) | warning `LOCATION_ON_LAND` (not fatal; the mask may be coarse) |
| Requested variables ∈ variable registry | `SCHEMA_VALIDATION_FAILED` |

### 2.6 Universal adapter responsibilities

Every adapter must: hold base URL and credentials from configuration only; construct
provider-specific queries; enforce timeouts, retries with jittered backoff and a circuit
breaker; parse the provider response; convert units to canonical units; convert
coordinates to EPSG:4326; map provider errors to canonical codes; build `Provenance`;
never raise a provider-specific exception across the tool boundary; and never substitute
a different variable or dataset than the one requested.

---

## 3. P0 Capability Tool Contracts

---

## 3.1 `get_weather()`

**Purpose.** Retrieve near-surface weather observations and/or forecasts relevant to a
marine query (wind is the safety-critical variable).

**Inputs**

```json
{
  "location": {"lat": 9.93, "lon": 76.26},
  "time_window": {"start_time": "2026-09-03T00:00:00Z", "end_time": "2026-09-03T12:00:00Z"},
  "variables": ["wind_speed", "wind_direction", "wind_gust", "precipitation", "air_temperature"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `location` | `Point` \| `BBox` | yes | Point resolved to nearest supported station/grid node |
| `time_window` | `TimeWindow` | yes | Past window ⇒ observations; future ⇒ forecast |
| `variables` | string[] | no | Default: wind_speed, wind_direction, precipitation, air_temperature |

**Primary source** S-05 IMD — **AUTH REQUIRED**.
**Fallback** S-11 NOAA (PROPOSED). **Secondary cross-check** S-04 ASCAT daily wind
(VERIFIED) — used for conflict detection, never as a silent substitute for a forecast.

**Adapter responsibility.** IMD authentication and endpoint selection; mapping IMD
station/area identifiers to coordinates; distinguishing observation vs forecast records;
unit conversion to m/s (wind) and mm (precipitation); mapping 403 → `AUTH_REQUIRED`.

**Normalized output.** Array of `Observation` / `Forecast` objects with
`parameter`, `value`, `unit`, `location`, `valid_time`, `value_kind`, plus a `lead_time_h`
for forecasts.

**Quality metadata.** `flag` (nominal/degraded/suspect), `basis`, `nearest_node_distance_km`,
`lead_time_h`, `staleness_s`.

**Failure states.** `AUTH_REQUIRED`, `SOURCE_UNAVAILABLE`, `NO_DATA`, `STALE_DATA`,
`INVALID_LOCATION`, `INSUFFICIENT_COVERAGE`, `RATE_LIMITED`, `TIMEOUT`.

**Fallback conditions.** Fallback is attempted only on `SOURCE_UNAVAILABLE`, `TIMEOUT` or
`RATE_LIMITED` — **never** on `AUTH_REQUIRED` (a credential problem is not fixed by a
different source, and silently swapping authority is misleading). Any fallback sets
`fallback_used = true` with the reason, and the Reporting Agent must state it.

**Validation rules.** §2.5 plus: forecast horizon ≤ product max; gust ≥ speed if both
present (else `quality.flag = suspect`).

**Example response (fallback used)**

```json
{
  "status": "success",
  "tool": "get_weather",
  "data": [
    {"type": "Forecast", "parameter": "wind_speed", "value": 11.3, "unit": "m s-1",
     "valid_time": "2026-09-03T06:00:00Z", "lead_time_h": 19,
     "location": {"type": "Point", "coordinates": [76.25, 9.90], "crs": "EPSG:4326"},
     "value_kind": "forecast", "provenance_id": "pv-a01"},
    {"type": "Forecast", "parameter": "wind_direction", "value": 268, "unit": "degree",
     "valid_time": "2026-09-03T06:00:00Z", "value_kind": "forecast", "provenance_id": "pv-a02"}
  ],
  "source_resolution": {
    "primary_source": "S-05", "actual_source": "S-11",
    "fallback_used": true, "fallback_reason": "SOURCE_UNAVAILABLE",
    "attempts": [{"source_id": "S-05", "outcome": "SOURCE_UNAVAILABLE", "duration_ms": 5000},
                 {"source_id": "S-11", "outcome": "success", "duration_ms": 820}]
  },
  "warnings": [{"code": "FALLBACK_USED", "detail": "IMD unreachable; NOAA used for wind forecast"}],
  "errors": []
}
```

---

## 3.2 `get_marine_warnings()`

**Purpose.** Retrieve **official** marine/coastal warnings in force for a location and
time window.

**Inputs**

```json
{
  "location": {"lat": 9.93, "lon": 76.26},
  "time_window": {"start_time": "2026-09-03T00:00:00Z", "end_time": "2026-09-04T00:00:00Z"},
  "warning_types": ["fishermen", "coastal", "port", "cyclone", "high_wave", "swell_surge"]
}
```

**Primary source** S-05 IMD. **Fallback** INCOIS warning/advisory services **only where
the deployment has explicitly authorised an equivalent official channel**.

> **There is no scientific substitute for an official warning.** A general weather
> forecast must never be converted into a "warning". If no official channel is reachable,
> the tool returns `SOURCE_UNAVAILABLE` and ORCA must say the warning status is unknown.

**Adapter responsibility.** Retrieve bulletins; retain **verbatim text** for quoting;
parse issue time, validity window, issuing office, warning type and severity; attempt to
resolve the affected area to geometry (named sea area / district polygon lookup) and emit
`AMBIGUOUS_AREA` when it cannot.

**Normalized output.** `MarineWarning` objects: `warning_id`, `warning_type`,
`severity`, `issued_at`, `valid_from`, `valid_to`, `issuing_office`, `affected_area`
(geometry **or** `area_description` + `AMBIGUOUS_AREA`), `text_verbatim`, `language`,
`bulletin_reference`.

**Failure states.** `AUTH_REQUIRED`, `SOURCE_UNAVAILABLE`, `NO_ACTIVE_WARNING`,
`STALE_DATA`, `AMBIGUOUS_AREA`, `TIMEOUT`.

**`NO_ACTIVE_WARNING` is a successful, meaningful result** (`status: "empty"`), reported
as *"No active marine warning found for this area at this time (IMD, checked <time>)"* —
never as silence and never as "conditions are safe".

**Validation rules.** Warning is included only if its validity window intersects the
requested window and its affected area intersects the requested location/bbox (or the
area is ambiguous, in which case it is included **and flagged**).

**Example response (no warning in force)**

```json
{
  "status": "empty",
  "tool": "get_marine_warnings",
  "data": [],
  "errors": [{"code": "NO_ACTIVE_WARNING", "severity": "info",
              "detail": "No warning intersecting 9.93N 76.26E for 2026-09-03T00Z–2026-09-04T00Z",
              "subject": "marine_warning"}],
  "provenance": [{"provenance_id": "pv-w00", "parameter": "marine_warning_status",
                  "value": "none_active", "value_kind": "observed",
                  "source": "IMD", "source_id": "S-05",
                  "valid_time": "2026-09-03T00:00:00Z",
                  "retrieved_at": "2026-09-02T11:04:33Z"}],
  "source_resolution": {"primary_source": "S-05", "actual_source": "S-05", "fallback_used": false}
}
```

---

## 3.3 `get_cyclone_track()`

**Purpose.** Retrieve active tropical cyclone systems, observed positions and official
forecast track/intensity relevant to a region and time window.

**Inputs**

```json
{
  "location": {"lat": 9.93, "lon": 76.26},
  "radius_km": 500,
  "time_window": {"start_time": "2026-09-02T00:00:00Z", "end_time": "2026-09-06T00:00:00Z"},
  "include": ["track", "cone", "wind_radii"]
}
```

**Primary source** S-05 IMD (the authority for the North Indian Ocean basin).
**Fallback** a deployment-configured authoritative alternative basin agency; using it
must be flagged, because cyclone naming/intensity conventions differ between agencies.

**Adapter responsibility.** Retrieve track products; normalise intensity classification
and record the **classification scheme name**; convert positions to EPSG:4326; convert
cone/wind-radii products to polygons where the source supplies them (never synthesised).

**Normalized output.** `system_id`, `name`, `basin`, `current_position` + `valid_time`,
`observed_track[]`, `forecast_track[]` (position, valid_time, lead_time_h, intensity,
`intensity_scheme`), `cone_geometry` (if supplied), `wind_radii` (if supplied),
`advisory_reference`, `issued_at`.

**Failure states.** `AUTH_REQUIRED`, `SOURCE_UNAVAILABLE`, `NO_ACTIVE_CYCLONE`,
`STALE_DATA`, `INVALID_LOCATION`, `TIMEOUT`.

**Rules.** The forecast cone is **never synthesised** from track points — if the source
does not publish a cone, `cone_geometry` is null and downstream reasoning must not draw
one. Any cyclone-related output is high-impact and routes to `REVIEW_REQUIRED` for
operational roles (`12_RISK_AND_RECOMMENDATION_SPEC.md`).

---

## 3.4 `get_lightning()`

**Purpose.** Retrieve lightning observations/alerts relevant to a marine area and time.

**Inputs**

```json
{
  "location": {"lat": 9.93, "lon": 76.26},
  "radius_km": 100,
  "time_window": {"start_time": "2026-09-03T00:00:00Z", "end_time": "2026-09-03T12:00:00Z"}
}
```

**Primary source** S-05 IMD. **Fallback** none configured. If IMD is unavailable, the
lightning input to the safety assessment is **absent**, and that absence is reported.

**Adapter responsibility.** Distinguish strike observations from area alerts; retain the
detection/alert time; convert to EPSG:4326 points or alert polygons.

**Normalized output.** For observations: `event_time`, `location`, `stroke_type` /
`intensity` if published, `detection_network`. For alerts: `alert_area`, `valid_from`,
`valid_to`, `severity`.

**Failure states.** `AUTH_REQUIRED`, `SOURCE_UNAVAILABLE`, `NO_DATA`, `STALE_DATA`,
`INSUFFICIENT_COVERAGE`, `TIMEOUT`.

**Rules.** Lightning observations are inherently retrospective; forecast lightning risk
must not be inferred from strike history by this tool. If lightning data is missing, the
safety assessment records `lightning: not_evaluated` and lowers confidence rather than
assuming absence of risk.

---

## 3.5 `get_pfz()`

**Purpose.** Retrieve Potential Fishing Zone advisory information for an area and time.

**Inputs**

```json
{
  "location": {"lat": 9.93, "lon": 76.26},
  "radius_km": 50,
  "valid_time": "2026-09-03T00:00:00Z",
  "prefer_representation": "vector"
}
```

**Primary source** S-06 INCOIS GeoServer/WMS — **PENDING VERIFICATION** (the audit
identified public WMS capabilities and PFZ-related layers; independent verification was
deferred because the test network could not resolve the host).
**Fallback** a configured INCOIS PFZ product/download path or another explicitly
authorised PFZ source.

**Three explicit branches — the adapter must report which one occurred:**

| Branch | Condition | Output | Code |
|---|---|---|---|
| Vector | WFS / `GetFeatureInfo` yields geometry + attributes | `VectorFeature[]` with PFZ attributes | — |
| Raster | Only `GetMap` imagery available | `RasterRef` (tile/image reference, bbox, CRS, legend) | `RASTER_ONLY` |
| Absent | Nothing retrievable for the requested time | empty | `NO_DATA` / `SOURCE_UNAVAILABLE` |

**Adapter responsibility.** WMS/WFS request construction, `TIME` dimension handling,
CRS declaration, layer-name configuration, capability caching, and setting
`representation` explicitly on every returned object.

**Normalized output.** PFZ geometry **or** raster reference; advisory issue time and
validity; advisory reference/bulletin id; associated ocean variables **only if the source
publishes them with the advisory**.

**Failure states.** `SOURCE_UNAVAILABLE`, `RASTER_ONLY`, `VECTOR_UNAVAILABLE`, `NO_DATA`,
`STALE_DATA`, `INVALID_LOCATION`, `TIMEOUT`.

**Hard rules.**

1. `get_pfz` **must not manufacture PFZ zones** from SST and chlorophyll. A PFZ advisory
   is a published product of a specific methodology; ORCA is not authorised to reproduce
   it. ORCA may report SST/chlorophyll conditions separately as its own derived
   indicators, clearly labelled as ORCA-derived and **not** as PFZ.
2. When `RASTER_ONLY`, point-in-zone questions must be answered as
   *"PFZ is available only as imagery for this date; exact zone boundaries cannot be
   tested"* — never approximated by reading pixel colours as geometry.
3. PFZ validity is per-advisory; an advisory outside the requested time returns `NO_DATA`,
   not the nearest advisory, unless the caller explicitly sets `allow_nearest_advisory`.

**Example response (raster-only)**

```json
{
  "status": "partial",
  "tool": "get_pfz",
  "data": [{
    "type": "RasterRef", "parameter": "pfz_advisory",
    "representation": "raster",
    "raster_uri": "orca://layers/pfz/2026-09-03/tiles/{z}/{x}/{y}.png",
    "bbox": {"min_lat": 9.4, "min_lon": 75.8, "max_lat": 10.4, "max_lon": 76.7},
    "crs": "EPSG:4326",
    "legend_uri": "orca://layers/pfz/2026-09-03/legend.json",
    "valid_time": "2026-09-03T00:00:00Z",
    "value_kind": "observed",
    "provenance_id": "pv-p11"
  }],
  "errors": [{"code": "RASTER_ONLY", "severity": "warning",
              "detail": "WMS GetMap only; no vector geometry available for PFZ layer",
              "subject": "pfz"}],
  "quality": {"geometry_available": false, "spatial_test_supported": false}
}
```

---

## 3.6 `get_sst()`

**Purpose.** Retrieve sea-surface temperature (and SST anomaly where published) for an
area and time.

**Inputs**

```json
{
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
  "time_window": {"start_time": "2026-09-01T00:00:00Z", "end_time": "2026-09-03T00:00:00Z"},
  "variables": ["sst", "sst_anomaly"],
  "aggregation": "none"
}
```

`aggregation ∈ {none, mean, max, min}` over the time window; when not `none` the result is
`value_kind: derived` with a derivation record.

**Primary source** S-02 INCOIS ERDDAP `NOAA_AVHRR_AMSR_datasets` — **VERIFIED**.
**Fallback** S-07 CMEMS, then S-11 NOAA. **Cross-check** S-09 MOSDAC (P1).

**Adapter responsibility.** ERDDAP griddap selector construction (lat/lon/time ranges,
stride), response format selection, fill/NaN handling, unit confirmation from dataset
metadata (do not assume °C — read it), and mapping of empty grids to `NO_DATA`.

**Normalized output.** `OceanField` (grid) or `Observation[]` (points): `sst` values with
unit, grid coordinates, `valid_time`, plus `sst_anomaly` when the dataset publishes it.
**If anomaly is not published, ORCA computes it deterministically** in the Geospatial
Analysis Agent and labels it `value_kind: derived` with the climatology/window used — the
tool itself never fabricates an anomaly.

**Failure states.** `SOURCE_UNAVAILABLE`, `DATASET_UNAVAILABLE`, `NO_DATA`, `STALE_DATA`,
`INSUFFICIENT_COVERAGE`, `INVALID_BBOX`, `TIMEOUT`.

**Validation rules.** SST outside −2 … 40 °C ⇒ `quality.flag = suspect` and the value is
excluded from assessment; cloud/fill-flagged cells are masked, and the masked fraction is
reported in `quality.coverage_fraction`; if coverage < configured minimum ⇒
`INSUFFICIENT_COVERAGE` with `status: "partial"`.

**Example response**

```json
{
  "status": "success",
  "tool": "get_sst",
  "data": [{
    "type": "OceanField", "parameter": "sst", "unit": "degC",
    "grid": {"crs": "EPSG:4326",
             "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
             "shape": [41, 31], "lat_step": 0.1, "lon_step": 0.1},
    "valid_time": "2026-09-02T00:00:00Z",
    "value_kind": "observed",
    "values_ref": "orca://fields/f-3391",
    "summary": {"min": 27.1, "max": 29.8, "mean": 28.6, "coverage_fraction": 0.83},
    "provenance_id": "pv-s21"
  }],
  "provenance": [{"provenance_id": "pv-s21", "parameter": "sst",
                  "source": "INCOIS ERDDAP", "source_id": "S-02",
                  "dataset": "NOAA_AVHRR_AMSR_datasets",
                  "valid_time": "2026-09-02T00:00:00Z",
                  "retrieved_at": "2026-09-02T11:04:35Z",
                  "spatial_resolution": "<as published>", "temporal_resolution": "<as published>",
                  "unit": "degC", "value_kind": "observed",
                  "quality": {"flag": "nominal", "basis": "source-provided",
                              "coverage_fraction": 0.83},
                  "external_source": false, "fallback_used": false}],
  "quality": {"coverage_fraction": 0.83, "masked_reason": "cloud/fill"},
  "errors": []
}
```

---

## 3.7 `get_chlorophyll()`

**Purpose.** Retrieve chlorophyll-a (and, where published, KD490 / TSM) for productivity
and ecological reasoning.

**Inputs**

```json
{
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
  "time_window": {"start_time": "2026-09-01T00:00:00Z", "end_time": "2026-09-03T00:00:00Z"},
  "variables": ["chlorophyll_a", "kd490", "tsm"]
}
```

**Primary source** S-01 INCOIS ERDDAP `incois_oceansat2_datasets` — **VERIFIED**
(variables observed in the catalogue: `CHL` mg/m³, `KD490` m⁻¹, `TSM` mg/L).
**Fallback** S-07 CMEMS ocean colour. **Cross-check** S-09 MOSDAC (P1).

**Adapter responsibility.** As for `get_sst`, plus: ocean-colour products are heavily
cloud-affected — the adapter must report `coverage_fraction` honestly and must not
gap-fill. Any gap-filling is a Geospatial Analysis Agent operation, labelled `derived`.

**Normalized output.** `OceanField` per variable with unit as published,
`coverage_fraction`, valid time, grid definition.

**Failure states.** `SOURCE_UNAVAILABLE`, `DATASET_UNAVAILABLE`, `NO_DATA`, `STALE_DATA`,
`INSUFFICIENT_COVERAGE`, `INVALID_BBOX`, `TIMEOUT`.

**Validation rules.** Chlorophyll ≤ 0 ⇒ masked as invalid; extreme values (> configured
ceiling, typically coastal turbidity artefacts) ⇒ `quality.flag = suspect` and excluded
from summary statistics unless the caller opts in; if `coverage_fraction` is below the
configured minimum, the fishing assessment must treat chlorophyll as *not evaluated*
rather than using a sparse mean.

---

## 3.8 `get_wave_conditions()`

**Purpose.** Retrieve wave and swell conditions for marine safety and route reasoning.

**Inputs**

```json
{
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
  "time_window": {"start_time": "2026-09-03T00:00:00Z", "end_time": "2026-09-03T12:00:00Z"},
  "variables": ["significant_wave_height", "peak_period", "mean_direction",
                "swell_height", "swell_period", "swell_direction"]
}
```

**Primary source** S-07 CMEMS — **AUTH REQUIRED**. **Fallback** S-11 NOAA wave products.
**Note** S-10 INCOIS OSF/LAS would be the preferred Indian-authority primary, but **no
machine-readable interface was established during the audit**; if one is confirmed later
it becomes primary and CMEMS becomes fallback (`03_DATA_SOURCE_MATRIX.md` S-10).

**Adapter responsibility.** CMEMS authentication, product/dataset selection per variable,
subsetting request construction, NetCDF parsing, forecast-cycle identification
(reference time vs valid time), unit normalisation to metres/seconds/degrees.

**Normalized output.** `OceanField`/`Forecast` per variable with `lead_time_h`,
`forecast_reference_time`, grid definition, unit.

**Failure states.** `AUTH_REQUIRED`, `SOURCE_UNAVAILABLE`, `DATASET_UNAVAILABLE`,
`NO_DATA`, `STALE_DATA`, `INSUFFICIENT_COVERAGE`, `INVALID_BBOX`, `TIMEOUT`.

**Hard rule.** **SST, wind or any other variable can never substitute for wave height.**
If no wave source is available, the safety assessment records
`wave_conditions: not_evaluated`, lowers confidence, and the answer states that sea state
could not be assessed.

**Validation rules.** `Hs ≥ 0`; `swell_height ≤ Hs` within tolerance else
`quality.flag = suspect`; `peak_period` within a plausible band else suspect; if two wave
sources are queried and `Hs` differs by more than the configured tolerance, emit
`CONFLICTING_SOURCES` with both values retained.

---

## 3.9 `get_currents()`

**Purpose.** Retrieve surface (and, where available, subsurface) current velocity.

**Inputs**

```json
{
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
  "time_window": {"start_time": "2026-09-03T00:00:00Z", "end_time": "2026-09-03T12:00:00Z"},
  "depth_m": 0
}
```

**Primary source** S-07 CMEMS. **Secondary** S-03 INCOIS ERDDAP where a suitable active
dataset is confirmed (dataset confirmation is a Phase-1 verification item, V-1).

**Adapter responsibility.** Depth-level selection and reporting of the **actual** depth
returned (never silently returning a different level); vector component naming (`uo`/`vo`
→ canonical `current_u` / `current_v`); unit normalisation to m/s.

**Normalized output.** `current_u`, `current_v` fields; magnitude and direction are
**derived** by the Geospatial Analysis Agent (`value_kind: derived`, method
`vector_magnitude_direction v1`), not by the adapter, so the derivation is traceable.

**Failure states.** `AUTH_REQUIRED`, `SOURCE_UNAVAILABLE`, `DATASET_UNAVAILABLE`,
`NO_DATA`, `STALE_DATA`, `INSUFFICIENT_COVERAGE`, `INVALID_BBOX`, `TIMEOUT`.

**Validation rules.** Requested vs returned depth difference must be reported in
`quality.depth_offset_m`; magnitudes above a configured plausibility ceiling ⇒ suspect.

---

## 3.10 `get_ocean_observations()`

**Purpose.** Retrieve oceanographic observations and analysis fields (temperature,
salinity and related variables, including subsurface) for deeper multi-variable
reasoning and in-situ evidence.

**Inputs**

```json
{
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
  "time_window": {"start_time": "2026-08-24T00:00:00Z", "end_time": "2026-09-02T00:00:00Z"},
  "variables": ["temperature", "salinity"],
  "depth_range_m": {"min": 0, "max": 200}
}
```

**Primary source** S-03 INCOIS ERDDAP — **VERIFIED** catalogue entries:
`incois_argo_10day_McCreary`, `incois_argo_10d_VAM`, `incois_argo_mnt_McCreary`,
`incois_argo_mnt_VAM`. **Fallback** S-12 Argo GDAC, S-07 CMEMS depending on variable and
latency tolerance.

**Adapter responsibility.** Dataset selection per requested variable and time cadence
(10-day vs monthly products have different validity semantics — the adapter must record
which product served the request and its temporal representativeness); depth axis
handling; distinguishing **analysis fields** from **individual profiles**
(`value_kind: observed` vs `derived`/`model` as the product documentation states).

**Normalized output.** `Observation[]` (profiles) or `OceanField[]` (analysis grids) with
depth, variable, unit, valid time and product cadence.

**Failure states.** `SOURCE_UNAVAILABLE`, `DATASET_UNAVAILABLE`, `NO_DATA`, `STALE_DATA`,
`INSUFFICIENT_COVERAGE`, `INVALID_BBOX`, `TIMEOUT`.

**Rules.** A 10-day or monthly analysis product must **never** be presented as today's
conditions. The temporal representativeness (`temporal_resolution` + `valid_time` span)
must be carried through to the answer, and the Risk Assessment Agent must not use a
monthly field to make a next-morning safety statement.

---

## 3.11 `get_maritime_boundaries()`

**Purpose.** Retrieve maritime/regulatory boundary geometry relevant to a query area.

**Inputs**

```json
{
  "bbox": {"min_lat": 8.0, "min_lon": 75.0, "max_lat": 12.0, "max_lon": 78.0},
  "boundary_types": ["EEZ", "territorial_sea", "international_boundary",
                     "marine_protected_area", "restricted_zone"],
  "point_test": {"lat": 8.1, "lon": 74.2}
}
```

**Primary source** S-08 MarineRegions (EEZ and related) — **CONFIRMED reachable**, held
as a preloaded, versioned PostGIS snapshot for query-time performance.
**Additional sources** required per boundary type: MPA (S-15 Protected Planet, P2);
territorial sea, contiguous zone and restricted/operational zones require their own
authoritative sources — **not yet identified** (`25_GAP_AND_VALIDATION_REGISTER.md`).

**Adapter responsibility.** Snapshot loading and versioning; CRS normalisation; spatial
index maintenance; geometry simplification for display **only** (never for the
point-in-polygon test); returning the dataset version and effective date with every
feature.

**Normalized output.** `VectorFeature[]`: `geometry`, `boundary_type`, `name`,
`identifier`, `jurisdiction`, `dataset_version`, `effective_date`, `source`. If
`point_test` is supplied, an additional `DerivedResult` gives the containment answer per
boundary type with the method and dataset version used.

**Failure states.** `SOURCE_UNAVAILABLE`, `DATASET_UNAVAILABLE`, `NO_BOUNDARIES_FOUND`,
`STALE_DATA`, `INVALID_BBOX`.

**Hard rules.**

1. Boundary output is **advisory context**, never navigational or legal truth. Every
   response carries `advisory_only: true` and the required disclaimer text id.
2. A boundary type with no configured authoritative source returns
   `DATASET_UNAVAILABLE` for that type — it is never approximated from a different
   boundary type (an EEZ polygon is not a fishing regulation zone).
3. Disputed or overlapping boundaries are returned as multiple features with their
   respective sources; ORCA does not adjudicate.

**Example response (point test)**

```json
{
  "status": "success",
  "tool": "get_maritime_boundaries",
  "data": [
    {"type": "VectorFeature", "boundary_type": "EEZ", "name": "Indian Exclusive Economic Zone",
     "jurisdiction": "India", "dataset_version": "<product version>",
     "effective_date": "<release date>", "geometry_ref": "orca://geo/eez-ind",
     "advisory_only": true, "provenance_id": "pv-b01"},
    {"type": "DerivedResult", "parameter": "point_in_boundary",
     "value": true, "value_kind": "derived",
     "derivation": {"method": "point_in_polygon", "method_version": "1.0",
                    "inputs": ["pv-b01"], "params": {"crs": "EPSG:4326"}},
     "detail": {"point": [74.2, 8.1], "boundary_type": "EEZ"},
     "provenance_id": "pv-b02"}
  ],
  "errors": [{"code": "DATASET_UNAVAILABLE", "severity": "warning",
              "subject": "restricted_zone",
              "detail": "No authoritative restricted-zone dataset configured"}],
  "status_note": "advisory only — not for navigation"
}
```

---

## 4. Cross-Tool Rules

### 4.1 No silent fallback

```json
"source_resolution": {
  "primary_source": "S-02", "actual_source": "S-07",
  "fallback_used": true, "fallback_reason": "SOURCE_UNAVAILABLE",
  "attempts": [{"source_id": "S-02", "outcome": "SOURCE_UNAVAILABLE"},
               {"source_id": "S-07", "outcome": "success"}]
}
```

The Reporting Agent **must** surface `fallback_used` in the answer, e.g.
*"Ocean-current data came from CMEMS because the INCOIS dataset was unreachable."*

### 4.2 No silent substitution

- SST cannot substitute for wave height.
- A general weather forecast cannot become an official marine warning.
- A PFZ raster cannot become vector PFZ geometry.
- A monthly analysis field cannot become a next-morning forecast.
- A different dataset cannot silently replace a requested dataset.

### 4.3 Staleness

Tools expose `valid_time` and `retrieved_at`; the **reasoning layer** decides
acceptability using per-parameter staleness policies
(`12_RISK_AND_RECOMMENDATION_SPEC.md`). Tools flag `STALE_DATA` but do not unilaterally
discard data.

### 4.4 Conflicting sources

When a tool queries more than one source (cross-check mode) and values differ beyond the
per-parameter tolerance, it returns **both** values plus a `Conflict` object and the
`CONFLICTING_SOURCES` code. Neither the tool nor the Planner silently picks a winner;
`conflict_resolve` applies documented policy and, for safety-relevant parameters,
escalates to human review.

### 4.5 Missing data vs unavailable source

`NO_DATA` — source reached, query valid, nothing to return.
`SOURCE_UNAVAILABLE` — source could not be reached.
These produce different user-facing statements and different confidence effects.

### 4.6 Caching and idempotency

Every tool call is keyed by `(tool, normalised_args)`. Responses are cached with a
per-parameter TTL derived from the product cadence. A cache hit is recorded in provenance
(`cache_hit: true`, original `retrieved_at` preserved — the cache never rewrites
retrieval time). Tool calls are side-effect free and therefore safe to retry.

### 4.7 Timeouts and retries

Per-tool timeout budget (initial engineering parameters, require validation):
warnings/weather 5 s; gridded ocean fields 12 s; boundary point test 2 s. Two retries
with jittered exponential backoff for transient failures only; `AUTH_REQUIRED` and
`INVALID_*` are never retried. A circuit breaker opens per source after a configured
consecutive-failure count and short-circuits to `SOURCE_UNAVAILABLE`.

---

## 5. Contract Status Table

| Tool | Priority | Primary | Fallback | Source status | MVP-live | Contract status |
|---|---|---|---|---|---|---|
| `get_weather` | P0 | S-05 IMD | S-11 NOAA | AUTH REQUIRED | degraded | Defined · IMPLEMENTATION REQUIRED |
| `get_marine_warnings` | P0 | S-05 IMD | authorised official channel only | AUTH REQUIRED | degraded | Defined · IMPLEMENTATION REQUIRED |
| `get_cyclone_track` | P0 | S-05 IMD | configured authority | AUTH REQUIRED | degraded | Defined · IMPLEMENTATION REQUIRED |
| `get_lightning` | P0 | S-05 IMD | none | AUTH REQUIRED | degraded | Defined · IMPLEMENTATION REQUIRED |
| `get_pfz` | P0 | S-06 INCOIS WMS | configured PFZ path | PENDING VERIFICATION | conditional | Defined · IMPLEMENTATION REQUIRED |
| `get_sst` | P0 | S-02 ERDDAP | CMEMS / NOAA | **VERIFIED** | **yes** | Defined · IMPLEMENTATION REQUIRED |
| `get_chlorophyll` | P0 | S-01 ERDDAP | CMEMS | **VERIFIED** | **yes** | Defined · IMPLEMENTATION REQUIRED |
| `get_wave_conditions` | P0 | S-07 CMEMS | NOAA | AUTH REQUIRED | yes w/ creds | Defined · IMPLEMENTATION REQUIRED |
| `get_currents` | P0 | S-07 CMEMS | S-03 ERDDAP | AUTH REQUIRED | yes w/ creds | Defined · IMPLEMENTATION REQUIRED |
| `get_ocean_observations` | P0 | S-03 ERDDAP | Argo GDAC / CMEMS | **VERIFIED** | **yes** | Defined · IMPLEMENTATION REQUIRED |
| `get_maritime_boundaries` | P0 | S-08 MarineRegions | local snapshot | **CONFIRMED** | **yes** | Defined · IMPLEMENTATION REQUIRED |

---

## 6. P1 / FUTURE Tools (not callable by the MVP Planner)

| Tool | Purpose | Status |
|---|---|---|
| `search_marine_knowledge` | RAG over marine/scientific documentation with citations | P1 · `10_RAG_SPEC.md` |
| `get_route_advisory` | Corridor sampling + per-segment safety | P1 |
| `get_vessel_context` | Vessel class/capability-aware thresholds | FUTURE |
| `get_historical_comparison` | Multi-year comparison for a variable and area | P1 |
| `get_ecological_indicators` | Ecological/anomaly indicators | P1 · SCIENTIFIC VALIDATION REQUIRED |
| `get_habitat_species_info` | Habitat/species reference | FUTURE |
| `send_notification` | Channel-abstracted alert delivery | P1 · `13` |
| `translate_text` / `synthesize_speech` | Language services | P1 / FUTURE · `13` |
| `generate_report_document` | Exportable report artifact | P1 |

These are **not** promoted to P0. The Planner's tool registry is environment-configured,
and a tool absent from the registry cannot be planned.

---

## 7. Worked Example — the Kochi query

> "I'm near Kochi. Is tomorrow morning a good time to go fishing, and if not, why?"

Planner-selected calls (see `06_AGENT_SPEC.md` and `07_LANGGRAPH_WORKFLOW_SPEC.md`):

```
resolve location  → 9.93 N, 76.26 E  (deterministic, gazetteer)
resolve time      → 2026-09-03 05:30–09:30 IST = 2026-09-03T00:00Z–04:00Z

parallel:
  get_marine_warnings(point, window)        → NO_ACTIVE_WARNING (empty, valid)
  get_weather(point, window)                → wind forecast (or AUTH_REQUIRED)
  get_lightning(point, r=100, window)       → AUTH_REQUIRED → not evaluated
  get_wave_conditions(bbox, window)         → Hs, Tp, swell (CMEMS)
  get_currents(bbox, window)                → u, v (CMEMS)
  get_sst(bbox, 3-day window)               → SST field (ERDDAP)
  get_chlorophyll(bbox, 3-day window)       → CHL field (ERDDAP)
  get_pfz(point, r=50, valid_time)          → RASTER_ONLY
  get_maritime_boundaries(bbox, point_test) → EEZ containment (MarineRegions)

then: align → derive (anomaly, current magnitude) → assess SAFETY and
      FISHING_SUITABILITY separately → conflicts → evidence → answer
```

The answer distinguishes observed facts, forecast facts, derived indicators, agent
interpretation, uncertainty and provenance — and never presents its fishing
recommendation as an official government advisory.

---

## 8. Related Documents

`03_DATA_SOURCE_MATRIX.md` (sources) · `05_CANONICAL_DATA_SCHEMA.md` (object model) ·
`06_AGENT_SPEC.md` (callers) · `12_RISK_AND_RECOMMENDATION_SPEC.md` (consumers) ·
`15_EVALUATION_AND_TESTING_SPEC.md` (contract tests).
