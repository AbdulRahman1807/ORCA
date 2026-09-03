# ORCA — Frontend Rebuild Brief (React)

**Document:** 23 of 30 · **Date:** 2026-09-03
**Status:** Brief for a rebuild. The current UI works; this describes replacing it.

---

## 1. What exists, and why replace it

`backend/orca/api/static/` — 1,182 lines of vanilla JS served at `/ui/`:

| File | Lines | What it does |
|---|---|---|
| `index.html` | 248 | markup + all CSS |
| `app.js` | 737 | chat, SSE trace, verdict cards, gauges, map layers, provenance |
| `wind.js` | 197 | canvas particle layer for vector fields |

It was written against a same-day deadline: no build step, no framework, plain
DOM. **It works** — every path in §6 is verified live. It is not a good place to
keep building: rendering is string concatenation, there is no component
boundary, and state is module-level `let`.

**Do not treat this as legacy to be ignored.** It encodes nine defects already
found and fixed (§7). Re-deriving those costs a day and some of them are
correctness bugs, not cosmetics.

---

## 2. Read these first, in this order

1. **`02_FRONTEND_DESIGN_SPEC.md`** — the authoritative design. 20 sections:
   information architecture, desktop and mobile layout, conversation, map,
   evidence panel, recommendation cards, warnings, freshness, uncertainty,
   route, PFZ, temporal controls, multilingual, accessibility, role views,
   loading/error/empty states, human review. **This brief does not replace it.**
2. **`IMPLEMENTATION_LOG.md` §21** — what the current UI does and every bug it hit.
3. **`12_RISK_AND_RECOMMENDATION_SPEC.md` §5** — the language rules. The UI can
   violate these as easily as the backend can.
4. The running API: `GET /docs` (FastAPI's generated reference).

---

## 3. The API contract

Base URL is the same origin. Start the server with:

```bash
./.venv/bin/uvicorn backend.orca.api.main:app --port 8000 --reload
```

| Endpoint | Purpose |
|---|---|
| `POST /v1/chat` | `{query, thread_id?, lat?, lon?, language?}` → full answer |
| `POST /v1/chat/stream` | same body → **SSE**: `start`, `node`×N, `result`, `error` |
| `GET /v1/health` | liveness, tools bound, whether an LLM is configured |
| `GET /v1/health/sources` | all 12 capabilities: available, description, unavailable_reason |
| `GET /v1/field/{name}` | `wind`, `current` (vector), `chlorophyll`, `sst`, `waves` (scalar) |
| `GET /v1/fields` | field catalogue |
| `GET /v1/boundaries` | maritime geometry as GeoJSON, bbox-filtered |
| `GET /v1/boundaries/layers` | snapshot layers and version |
| `GET /v1/runs/{thread}` | replay a thread's last state |
| `GET /v1/runs/{thread}/provenance?provenance_id=` | the provenance chain |

### 3.1 The answer projection

`POST /v1/chat` and the SSE `result` event both return:

```
thread_id, language, intent,
resolved_location {lat, lon, label, dest_lat?, dest_lon?},
resolved_time_window {start_time, end_time},
resolution_notes[], clarification_needed,
plan { domains[], required_evidence[], steps[{step_id, tool, necessity}],
       unavailable[{evidence, tool, reason}], reasoning_summary },
assessments[ { domain, verdict, confidence, rationale,
               drivers[{factor, value, unit, band, contribution}],
               not_evaluated[{factor, reason, detail}],
               missing_required[], verdict_capped_by[], limiting_factor } ],
evidence[{evidence_id, domain, statement, parameter, value, unit,
          value_kind, provenance_id, weight}],
alerts[{kind, boundary_type, severity, distance_km, inside, name,
        dataset_version, advisory_only}],
map_layers[{id, type, name, data /* GeoJSON Feature */}],
claims[], not_evaluated[], disposition, recommendation, trace[]
```

### 3.2 SSE shape

```
event: start   data: {"thread_id": "..."}
event: node    data: {node, status, duration_ms, summary, tool?, source?,
                      codes?, fallback_used?}
event: result  data: <the projection above>
event: error   data: {"error": "..."}
```

Events are separated by a blank line. **Every** node event is emitted, including
all parallel `tool_exec` events in one superstep — that fan-out is the point
(F-56).

### 3.3 Field shape

```
field, label, kind: "scalar"|"vector", unit,
lats[], lons[],
values[][]            // scalar; null where masked
u[][], v[][], speed[][]  // vector; null where masked
range {min, max},
cells {total, valid, coverage},
valid_time, source, source_id, dataset, advisory_only
```

---

## 4. Rules the interface inherits

These are not style preferences. Each one exists because breaking it makes ORCA
state something untrue, which is the failure the whole system is built to avoid.

**A hole stays a hole.** A `null` cell is masked — land, cloud, or no
observation. Render it transparent. Drawing it as `0` paints a calm, empty sea
over data that was never collected. Always show `cells.coverage`.

**A layer that fails is absent, not empty.** Say so, with the reason. An empty
map reads as calm water.

**The map never gates the answer.** Render text first, draw the map after, in a
boundary that cannot propagate. Three separate bugs came from violating this
(F-51, F-52, F-53).

**Never invent a scale.** The API returns a driver's *band*, not the band edges.
The current gauge places the pin inside its band rather than at an absolute
position, because a made-up axis would be a made-up fact. If you want true
gauges, add band edges to the API first.

**Advisory only.** Every boundary, route and PFZ carries `advisory_only: true`
and a `dataset_version`. Show both. The disclaimer is not decoration.

**Never claim safety that was not assessed.** If `verdict_capped_by` is
non-empty the verdict is a *ceiling*, not a measurement. Say so.

**Words matter per domain.** A boolean is containment in REGULATORY
(inside/outside) and presence elsewhere (present/absent). "EEZ absent" is a
different and false claim (F-59).

**Show what was not checked.** `not_evaluated` and `plan.unavailable` are
first-class content, not an error state.

---

## 5. Recommended stack

- **React + TypeScript + Vite.** Type the API projection in §3.1 — most UI bugs
  here were shape mismatches.
- **MapLibre GL** via `react-map-gl`. Keep the map in one component that owns
  its own readiness; do not let it suspend the tree.
- **deck.gl** if you want `TripsLayer` (animated route) and `HeatmapLayer` for
  less custom canvas work. Optional — the existing `wind.js` is framework-free
  and can be lifted as-is into a `useEffect`.
- **TanStack Query** for the REST calls; SSE stays a hand-rolled `fetch` +
  `ReadableStream` reader (see `app.js` `ask()` — the chunk-boundary handling is
  correct and worth copying).
- **Serve the build from FastAPI's existing static mount**, or run Vite
  separately — CORS is already `*`.

**Component boundaries that matter:** `<Conversation>`, `<AgentTrace>`,
`<VerdictCard>`, `<ThresholdGauge>`, `<EvidenceList>`, `<ProvenancePanel>`,
`<MapCanvas>`, `<FieldLayer>`, `<LayerBar>`, `<SourceHealth>`, `<Legend>`.

---

## 6. Component status

Tiers are from the visual plan. **Done** means verified live in a browser.

### Tier 1 — showstoppers

| # | Component | Status | Notes |
|---|---|---|---|
| 1 | Animated wind / current particles | **Done** | `wind.js`: bilinear sampling, speed-coloured trails, respawn on a hole. Both `wind` and `current`. Lift as-is. |
| 2 | Live agent trace | **Done, as a timeline** | SSE-driven, all nodes incl. parallel fan-out, per-node source/codes/timing. **Not** a DAG layout — a vertical list. A real node-graph is the upgrade. |
| 3 | Chlorophyll field | **Partial** | Heatmap with holes and coverage % done. **Missing:** the local-median contour ring that would make D-6's comparative reasoning visible. |

### Tier 2 — over data the API already returns

| # | Component | Status | Notes |
|---|---|---|---|
| 4 | Threshold band gauges | **Partial** | Four bands drawn, pin positioned, limiting factor marked. Bands are **equal width** and the pin sits at its band's centre, because the API does not return band edges. Real gauges need `04`-style edges added to the projection. |
| 5 | Temporal alignment strip | **Not started** | Highest-value remaining item. Shows each source's validity window against the analysis window; explains why 2011 SST is rejected and 2-day-old chlorophyll accepted. Data is in `evidence[].value_kind` + provenance `temporal`; may need the projection widening. |
| 6 | Provenance chain | **Done, flat** | Click an evidence id → source, dataset, access method, derivation with method+version+inputs. **Not** an animated L1→L2→L3 tree. |
| 7 | Source health | **Done, as a list** | 12 capabilities, 8 available, 4 with reasons. **Not** the constellation visual. |
| 8 | Route ribbon | **Partial** | Animated dashes + glow + fit-to-bounds done. **Missing:** corridor tinted by wave height along the path. |
| 9 | Geofence proximity | **Partial** | Alert cards with distance, dataset version, advisory-only. **Missing:** range rings drawn on the map. |
| 10 | Disagreement panel | **Not started** | Cards are independent and never merged, but divergence gets no special treatment. This is demo segment 6 — worth building when a real disagreement is reachable. |

### Tier 3 — texture

| Component | Status |
|---|---|
| Dark nautical theme | **Done** |
| Bathymetry basemap (Esri Ocean, key-free, fallback chain) | **Done** |
| Animated caustics | **Done** |
| Glassmorphism panels | **Done** |
| Monospace provenance ids | **Done** |
| Responsive / narrow-screen stacking | **Done** |
| Freshness dots decaying with age | **Not started** |
| Confidence as visual uncertainty (blur/opacity rather than a badge) | **Not started** |

### Roughly

**Tier 1 ~80 %** · **Tier 2 ~45 %** · **Tier 3 ~75 %**.
Everything essential to a demo works. What is missing is depth, not function:
the temporal alignment strip (#5) and true threshold gauges (#4) are the two
that would most change how the reasoning reads.

---

## 7. Traps already hit — do not re-derive these

| ID | Trap |
|---|---|
| **F-51** | A remote raster source in the **initial** MapLibre style stalls `style.load` forever if tiles are blocked, so nothing initialises. Start with an empty style; add the basemap after. |
| **F-52** | `map.on('load')` waits for **tiles**, not the style. Poll `isStyleLoaded()`. |
| **F-53** | `addSource` on an unloaded style throws and, uncaught, replaced the entire answer with "Request failed". Isolate map calls. |
| **F-56** | Emitting only the newest `node_event` per superstep collapses a seven-tool parallel fan-out to one line. Emit all. |
| **F-57** | Auto-opening the trace panel covered the clarifying question; the user concluded nothing had been asked. When `clarification_needed` is set, get the trace out of the way, focus the input, and hint the expected answer. |
| **F-58** | A capped verdict's `limiting_factor` is the capping factor, but drivers may still carry a stale `contribution: "limiting"` — fixed backend-side; assert the card and headline agree. |
| **F-59** | Boolean rendering must be domain-aware (§4). |
| — | Serve UI assets `no-store`. A stale bundle is indistinguishable from a bug. |
| — | MapLibre needs a real basemap host: CARTO, Esri and OSM all work without a key; **Mapbox does not** — if you see "API key required", `mapbox-gl` got loaded instead of `maplibre-gl`. |

---

## 8. Verification checklist

The rebuild is complete when all of these pass in a real browser:

- [ ] Fishing query → 3 independent verdict cards, gauges, alerts, evidence
- [ ] All seven tools appear individually in the trace
- [ ] `plan a route` → visible question, focused input, trace not covering it
- [ ] Answering it → route drawn, no waypoint on land
- [ ] Three-turn conversation carries location and **does not** accumulate verdicts
- [ ] A Malayalam query answers in Malayalam with numbers and IMD/INCOIS intact
- [ ] Chlorophyll layer shows holes; legend reports ~50 % coverage near Kochi
- [ ] With the network to tile hosts blocked, chat and verdicts still work
- [ ] `verdict_capped_by` present → no driver marked limiting; ceiling stated
- [ ] REGULATORY booleans read inside/outside
