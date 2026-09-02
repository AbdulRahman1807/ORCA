# ORCA — Geospatial Reasoning Specification

**Document:** 11 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Design defined — IMPLEMENTATION REQUIRED

---

## 1. Principle: Everything Here Is Deterministic

Every operation in this document is a **pure function** implemented in
`backend/orca/geospatial/`, unit-tested against reference values, versioned, and recorded
in provenance as a `derivation`. No LLM participates in any calculation.

```
   ┌──────────────────────────────────────────────────────────────┐
   │  DETERMINISTIC (this document)                               │
   │  CRS · subsetting · masking · interpolation · alignment ·    │
   │  anomalies · statistics · geometry predicates · geofencing · │
   │  distance/area · clustering · corridor sampling              │
   ├──────────────────────────────────────────────────────────────┤
   │  GENERATIVE (elsewhere)                                      │
   │  a ≤3-sentence plain-language summary of computed results    │
   └──────────────────────────────────────────────────────────────┘
```

The Geospatial Analysis Agent (`06_AGENT_SPEC.md` §5) orchestrates these functions; it
does not implement them.

**Library baseline.** `pyproj` (CRS/geodesy), `shapely` 2.x (geometry), `geopandas`
(vector tables), `xarray` + `netCDF4` (gridded data), `rasterio` (raster I/O),
`numpy`/`scipy` (numerics), PostGIS (indexed spatial queries at scale).

---

## 2. CRS Handling

| Rule | Detail |
|---|---|
| Canonical internal CRS | **EPSG:4326** (WGS 84), coordinates ordered **lon, lat** in geometry payloads |
| Display CRS | **EPSG:3857** for web tiles only; never used for computation |
| Metric operations | Never performed in degrees. Distance/area use geodesic computation (`pyproj.Geod`, WGS 84 ellipsoid) or a local equal-area projection — the choice is recorded |
| Local projections | For area-heavy work in Indian waters, an equal-area projection appropriate to the extent is selected by a documented rule and recorded in the derivation |
| Explicit CRS | Every `SpatialRef` carries `crs`. An object without CRS is invalid (`SCHEMA_VALIDATION_FAILED`), never assumed |
| Axis order | Handled at the adapter boundary. Sources declaring EPSG:4326 in lat/lon order (common in OGC 1.3.0) are normalised, and the normalisation is asserted by a test |
| Antimeridian | Bounding boxes crossing ±180° are split into two boxes; Indian-Ocean extents do not require this, but the guard exists |
| Datum | Only WGS 84 is used. A source publishing another datum is transformed by `pyproj` and the transform is logged |

```python
def normalize_crs(geom, src_crs: str, dst_crs: str = "EPSG:4326") -> tuple[Geometry, dict]:
    """Returns (geometry, derivation_record). Raises on unknown CRS — never guesses."""
```

---

## 3. Spatial Normalisation

Every retrieved object is normalised before analysis:

| Step | Function | Notes |
|---|---|---|
| CRS transform | `normalize_crs` | Records source and target CRS |
| Longitude convention | `normalize_longitude` | 0–360 → −180–180 where the source uses the former |
| Coordinate ordering | `normalize_axis_order` | Adapter-level, asserted by tests |
| Grid orientation | `normalize_grid_orientation` | Latitude ascending vs descending is made explicit in `SpatialRef` |
| Depth axis | `normalize_depth` | Positive downward, metres; the actual returned level is recorded, never silently changed |
| Units | `convert_unit` | To the canonical unit registry (`05` §3.1); unconvertible units are an error, not a guess |

---

## 4. Bounding Boxes

```python
def bbox_from_point_radius(lat, lon, radius_km) -> BBox      # geodesic, not degree padding
def bbox_intersect(a, b) -> BBox | None
def bbox_area_km2(b) -> float                                # geodesic
def bbox_validate(b, max_area_km2) -> None                   # INVALID_BBOX on failure
def bbox_expand(b, factor) -> BBox                           # used by Discovery widening
```

`bbox_from_point_radius` computes the radius geodesically: at 10 °N a 50 km radius spans
≈ 0.45° of latitude but ≈ 0.46° of longitude, and the difference grows with latitude.
Naive degree padding is a correctness bug and is explicitly forbidden; a unit test asserts
the geodesic result at several latitudes.

**Caps.** A configured maximum bbox area (default 500 000 km², an initial engineering
parameter) prevents an accidental whole-ocean request. Exceeding it returns
`INVALID_BBOX`, not a silently truncated query.

---

## 5. Raster and Grid Handling

### 5.1 Representation
Gridded data lives in `OceanField` with the array in object storage
(`05_CANONICAL_DATA_SCHEMA.md` §13). In-process it is an `xarray.DataArray` with named
coordinates (`lat`, `lon`, `time`, optional `depth`).

### 5.2 Operations

| Operation | Function | Rules |
|---|---|---|
| Subset | `subset_field(field, bbox, time_window, depth)` | Uses coordinate selection, never index arithmetic |
| Mask | `apply_masks(field, masks)` | Land, cloud/fill, quality-flag, plausibility-range masks; each mask's effect is counted |
| Coverage | `coverage_fraction(field)` | Valid cells ÷ requested cells; the honesty metric for satellite products |
| Resample | `resample_field(field, target_grid, method)` | `nearest` or `bilinear`; **never** upsampled beyond the source resolution without recording it |
| Point extract | `extract_point(field, lat, lon, method)` | Returns value + `node_distance_km` + method |
| Statistics | `field_statistics(field)` | min/max/mean/median/p10/p90 over **valid cells only** |
| Gradient (P1) | `spatial_gradient(field)` | Front detection input; magnitude per km, geodesically scaled |

### 5.3 Masking rules
1. Masked cells are **excluded** from statistics, never treated as zero.
2. Every mask records how many cells it removed.
3. If `coverage_fraction` falls below the per-parameter minimum (default 0.6, an initial
   engineering parameter), the field is marked `INSUFFICIENT_COVERAGE` and the parameter
   is reported as *not evaluated* rather than summarised from a sliver of valid pixels.
4. **No gap filling by default.** Interpolation across a cloud gap is an opt-in operation
   that produces `value_kind: derived` with the method recorded and a quality flag.

### 5.4 Rendered rasters
A `RasterRef` (rendered WMS imagery, e.g. a raster-only PFZ layer) supports **display and
citation only**. Any spatial predicate against a `RasterRef` returns
`VECTOR_UNAVAILABLE`. Reading pixel colours to infer zone geometry is explicitly
forbidden — a colour-mapped image is not data.

---

## 6. Vector Handling

| Operation | Function | Notes |
|---|---|---|
| Validity | `ensure_valid(geom)` | `shapely.make_valid`; invalid input geometry is repaired and the repair recorded |
| Winding | `normalize_winding(geom)` | RFC 7946 right-hand rule for GeoJSON output |
| Simplify | `simplify_for_display(geom, tol)` | **Display only.** Predicates always use full geometry; simplified output is flagged `display_simplified: true` |
| Buffer | `buffer_geodesic(geom, km)` | Projected buffer via a local equal-area CRS, then back-transformed — never `shapely.buffer` in degrees |
| Predicates | `contains`, `intersects`, `distance_to` | Full-precision geometry |
| Union/diff | `union`, `difference` | For area aggregation |

**Indexing.** Boundary and geofence geometries are held in PostGIS with GiST indexes;
point-in-polygon and intersection tests run in the database, not in Python, once the
dataset exceeds trivial size.

---

## 7. Interpolation

| Method | When | Recorded as |
|---|---|---|
| `nearest_node` | Default for point extraction from a coarse grid; safest for forecast fields | `method: nearest_node`, `node_distance_km` |
| `bilinear` | Smooth continuous fields (SST) where the point lies well inside the grid | `method: bilinear` |
| `time_nearest` | Point-in-time extraction from a discrete forecast sequence | `time_offset_min` |
| `time_linear` | Only for continuous variables and only within one time step | `method: time_linear` |
| *(none)* | Categorical/advisory products (PFZ zones, warning classes) | Interpolation is **forbidden**; the nearest valid product is used and labelled |

**Rules.**
- Every extraction records `node_distance_km`; if it exceeds the per-parameter maximum
  (default: 1.5 × grid spacing), quality is downgraded and the distance is surfaced.
- Interpolation never crosses a land mask or a mask boundary.
- Categorical fields are never interpolated — averaging advisory classes is meaningless.

---

## 8. Temporal Alignment

The hardest correctness problem in ORCA: a daily satellite composite, a 3-hourly forecast,
a 10-day analysis and a bulletin valid for 48 hours are not naturally comparable.

### 8.1 Analysis frame
The Geospatial Analysis Agent defines one **analysis frame** per run:
```json
{"spatial": {"kind":"point","coordinates":[76.26,9.93],"crs":"EPSG:4326",
             "context_bbox": {"…":"…"}},
 "temporal": {"valid_from":"2026-09-03T00:00:00Z","valid_to":"2026-09-03T04:00:00Z",
              "steps":["2026-09-03T00:00:00Z","2026-09-03T03:00:00Z"]}}
```

### 8.2 Alignment rules by representativeness

| Product representativeness | Alignment to a 4-hour window | Allowed for |
|---|---|---|
| `instantaneous` (3-hourly forecast) | Nearest step, or linear within one step | All domains |
| `hourly_mean` | Nearest hour | All domains |
| `daily_composite` (satellite SST/Chl) | The composite covering the window's date, labelled as a daily composite | FISHING_SUITABILITY, ECOLOGICAL. **Not** as a safety forecast |
| `10day_mean` / `monthly_mean` | **Not aligned.** Carried as background context with its own validity | Context only |
| `bulletin_period` (warnings) | Included if the validity interval intersects the window | SAFETY (governing) |

**Rule.** A product whose representativeness is incompatible with the analysis window
appears in `AlignmentReport.not_aligned` with the reason and is **never** force-fitted.
This is what stops a monthly analysis becoming "tomorrow morning's temperature".

### 8.3 Functions
```python
def align_temporal(objects, frame) -> tuple[list[Aligned], list[NotAligned]]
def nearest_time_step(times, target) -> tuple[datetime, float]   # (step, offset_min)
def interval_intersects(a_from, a_to, b_from, b_to) -> bool
def staleness_seconds(valid_time, now, representativeness) -> float
```

---

## 9. Spatial Joins

| Join | Function | Use |
|---|---|---|
| Point → polygon | `point_in_polygon(point, polygons)` | EEZ/MPA containment, geofence membership |
| Point → nearest feature | `nearest_feature(point, features)` | Distance to a boundary or a warning area |
| Polygon → grid | `zonal_statistics(polygon, field)` | Mean chlorophyll inside a PFZ polygon (only when PFZ is **vector**) |
| Grid → grid | `align_grids(a, b, target)` | Cross-variable comparison (SST vs chlorophyll) |
| Track → grid | `sample_along_line(line, field, spacing_km)` | Route corridor sampling (P1) |

`zonal_statistics` requires vector geometry. Called with a `RasterRef` it raises
`VECTOR_UNAVAILABLE` — the PFZ raster-only branch is enforced here, not only documented.

---

## 10. Anomaly Computation

```python
def anomaly_vs_window_mean(field, history_fields, window="P10D",
                           aggregation="mean", mask="cloud_flagged") -> DerivedResult
def anomaly_vs_climatology(field, climatology, period) -> DerivedResult   # P1
```

| Concern | Rule |
|---|---|
| Baseline identity | The baseline is explicit: which dataset, which window, which aggregation. Recorded in `derivation.params` |
| Not a climatology | A 10-day mean is **not** a climatological anomaly. It is labelled `anomaly_vs_window_mean`, and the answer says "above the 10-day mean", never "above normal" |
| True climatology | Requires a multi-year baseline product. Until one is integrated and validated, climatological anomaly is **SCIENTIFIC VALIDATION REQUIRED / FUTURE**. If the source publishes its own anomaly (e.g. an SST anomaly variable), that value is used as `observed` and preferred over any ORCA computation |
| Masking | The same mask applies to the field and the baseline; mismatched masks are a correctness bug and are asserted against |
| Coverage | Anomaly is computed only where both the field and the baseline have valid cells; the resulting coverage is reported |

---

## 11. Clustering and Feature Detection (P1)

| Feature | Method | Status |
|---|---|---|
| Chlorophyll patches | Connected-component labelling above a threshold, minimum area filter | P1 · SCIENTIFIC VALIDATION REQUIRED |
| Thermal fronts | Gradient magnitude above a threshold, thinned | P1 · SCIENTIFIC VALIDATION REQUIRED |
| Lightning clusters | DBSCAN on strike points with geodesic distance | P1 |
| Eddies | Not implemented | FUTURE |

Every detected feature is `value_kind: derived` with its method, threshold and version.
Thresholds are configuration and are labelled unvalidated until domain review. **Detected
features are never presented as PFZ** — that distinction is explicit in the output type
and in the UI label.

---

## 12. Geofencing

```python
def evaluate_geofence(geofence_geom, condition_geoms, condition_values) -> GeofenceResult
```

| Aspect | Rule |
|---|---|
| Storage | PostGIS `GEOGRAPHY(POLYGON, 4326)` with a GiST index |
| Trigger test | `ST_Intersects` for area conditions (warning polygons); point-in-polygon for position; threshold evaluation over the geofence's grid cells for field conditions |
| Field aggregation | Configurable: `max`, `mean` or `area_fraction_above_threshold`. For safety, `max` is the default — the worst condition inside the fence governs |
| Partial intersection | A warning polygon that only partially covers the geofence still triggers, and the alert states the overlap fraction |
| Ambiguous warning areas | A warning with `area_resolved = false` triggers **all** subscriptions in the named region with an explicit "area described as '<text>'" note; it never triggers silently and never fabricates a polygon |
| Buffer | Optional geodesic buffer per subscription (default 0) |
| Evaluation cadence | Scheduled per `13_MULTILINGUAL_AND_ALERTING_SPEC.md`; each evaluation is a normal run and is fully provenanced |

---

## 13. Maritime Boundaries

| Rule | Detail |
|---|---|
| Storage | Preloaded, versioned snapshots in `boundaries` (`09_DATABASE_SPEC.md` §4.2) |
| Predicate | Full-precision `ST_Contains` / `ST_Intersects` in PostGIS |
| Version binding | Every result records `dataset_version` and `effective_date`; historical runs remain reproducible against the geometry they used |
| Advisory only | `advisory_only = true` on every boundary result; the disclaimer is attached at the API layer, not left to the narrative |
| Coverage honesty | A boundary type with no configured authoritative source returns `DATASET_UNAVAILABLE` for that type. An EEZ polygon is never used as a proxy for a fishing regulation zone or a restricted area |
| Disputed geometry | Overlapping claims are returned as multiple features with their sources; ORCA does not adjudicate |
| Near-boundary reporting | Distance to the nearest boundary is reported alongside containment, so a point 400 m inside a boundary is not presented with false confidence given dataset precision |

---

## 14. Route Constraints (P1)

```python
def sample_corridor(origin, destination, spacing_km=10, buffer_km=5) -> list[SamplePoint]
def evaluate_corridor(samples, fields, thresholds) -> list[SegmentAssessment]
```

| Rule | Detail |
|---|---|
| Path | Great-circle by default; a routing graph is FUTURE |
| Sampling | Fixed geodesic spacing; each sample is a full safety evaluation |
| Segment verdict | The **worst** sample in a segment governs the segment |
| Boundary crossings | Reported separately from safety, with the crossed boundary type and dataset version |
| Temporal | Optionally time-aware (estimated position over time given a speed); if the speed is unknown, all samples use one time and the answer says so |
| Disclaimer | Route output is advisory context; it is **not** a navigational route and does not replace official charts or Notices to Mariners |

---

## 15. Visualisation Layers

| Layer type | Production | Delivery |
|---|---|---|
| Scalar field (SST, Chl, Hs) | Colour-mapped from the masked field with a fixed, unit-labelled scale | Raster tiles + legend |
| Vector field (currents, wind) | Decimated arrows or streamlines derived from `u`/`v` | GeoJSON or a tiled vector layer |
| Advisory raster (PFZ raster-only) | Passed through with the source legend | Raster tiles, flagged `geometry_available: false` |
| Zones/boundaries | Full geometry, simplified for display only | GeoJSON |
| Warning areas | Polygon if resolved; otherwise a labelled region marker with the area description | GeoJSON |
| Cyclone track/cone | Line + polygon exactly as published; a cone is never synthesised | GeoJSON |
| Points (lightning, observations) | Clustered above a density threshold | GeoJSON |

Every layer descriptor carries `provenance_id`, `source_id`, `valid_time`,
`retrieved_at`, `representation`, `fallback_used` and `attribution`
(`08_API_SPEC.md` §9), so the client can render source and freshness badges without extra
calls.

---

## 16. GeoJSON Conventions

| Convention | Rule |
|---|---|
| Standard | RFC 7946 |
| CRS | WGS 84 implied; a `crs` member is not emitted, but `properties.crs` records it for clarity |
| Order | `[longitude, latitude]` |
| Winding | Exterior rings counter-clockwise, holes clockwise |
| Precision | 6 decimal places (≈ 0.1 m) — more is false precision |
| Properties | `provenance_id`, `source_id`, `valid_time`, `value_kind`, `unit` (if valued), `advisory_only` (boundaries), `display_simplified` |
| Size | Large collections are paginated by bbox or served as vector tiles; a single response is capped |
| Time | Times as ISO-8601 UTC strings in properties; no ad-hoc time encoding |

---

## 17. Determinism, Versioning and Testing

Every function in this document is registered with a **method id and version** used in
`derivation.method` / `method_version`.

| Test class | Examples |
|---|---|
| Reference-value | Geodesic distance Kochi→Kavaratti against an independently computed value; bbox-from-radius at 5°N, 15°N, 25°N |
| Round-trip | CRS transform 4326→3857→4326 within tolerance; GeoJSON serialise/parse |
| Property-based | Point-in-polygon consistency under geometry simplification (must not change containment for points beyond the tolerance distance) |
| Masking | Statistics over a field with known masked cells equal the hand-computed values |
| Interpolation | Nearest-node and bilinear against hand-computed values on a synthetic grid |
| Alignment refusal | A monthly product is refused for a 4-hour safety window |
| Representation guard | `zonal_statistics` on a `RasterRef` raises `VECTOR_UNAVAILABLE` |
| Anomaly | Anomaly against a synthetic baseline equals the analytic result; masked-cell mismatch is detected |
| Regression | Method-version changes require an updated fixture and a changelog entry |

**No geospatial computation may be introduced without a reference test.** This is a
Definition-of-Done item (`30_DEFINITION_OF_DONE.md`).
