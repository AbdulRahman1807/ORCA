# ORCA — Backend API Specification

**Document:** 08 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Design defined — IMPLEMENTATION REQUIRED
**Base URL:** `/v1` · **Framework:** FastAPI · **Media type:** `application/json; charset=utf-8`

---

## 1. Design Rules

1. **The client never talks to an external source.** Every map layer, dataset value and
   bulletin reaches the browser through ORCA, so provenance, attribution, caching and
   access control stay under ORCA's control.
2. **Queries are asynchronous runs.** `POST /queries` returns a `run_id` immediately; the
   client streams events and then fetches the result. A multi-source marine query is not
   a request/response operation.
3. **Evidence is referenced, not inlined.** Answers carry `evidence_ids`; records are
   fetched on demand.
4. **Grid arrays never travel in JSON.** Fields are exposed as tiles, GeoJSON or typed
   binary exports.
5. **Errors are canonical.** Every error body carries a code from
   `05_CANONICAL_DATA_SCHEMA.md` §3.2, plus an i18n message key.
6. **No chain-of-thought is ever serialised.** Stream events are structural only.
7. **All times are UTC ISO-8601 with `Z`.** Localisation happens in the client.

---

## 2. Resource Map

```
/v1
├── /health                     service + dependency health
│   └── /sources                per-source operational status
├── /auth/token                 token issue/refresh
├── /sessions                   conversation sessions
│   └── /{session_id}
│       ├── /queries            submit a query → run
│       └── /turns              conversation history
├── /runs/{run_id}              run status + result
│   ├── /events        (WS)     streamed execution events
│   ├── /evidence               evidence records
│   ├── /provenance             provenance records
│   ├── /assessments            per-domain assessments
│   ├── /conflicts              detected conflicts
│   ├── /layers                 map layer descriptors
│   ├── /trace                  node/tool execution trace
│   ├── /review                 human-review decision
│   └── /cancel                 cancel a running run
├── /geo
│   ├── /features/{layer_id}    GeoJSON
│   ├── /tiles/{layer_id}/{z}/{x}/{y}.png   raster tiles
│   ├── /point                  point inspection across active layers
│   └── /boundaries             boundary lookup / point-in-boundary
├── /alerts                     alert inbox
│   ├── /subscriptions          geofenced subscriptions
│   └── /{alert_id}/ack
├── /review/queue               pending human reviews
├── /tools                      capability registry (analyst/admin)
└── /catalog/sources            source registry projection
```

---

## 3. Authentication and Authorisation

**Scheme.** Bearer tokens (JWT, asymmetric signature). Access token TTL 30 min, refresh
token TTL 14 days, rotation on use.

```http
Authorization: Bearer <access_token>
```

```jsonc
// JWT claims
{"sub":"usr-01J…","role":"officer","org":"ddma-ernakulam",
 "scopes":["query:write","review:decide","alerts:manage"],
 "iat":1789..., "exp":1789..., "jti":"…"}
```

### 3.1 Roles and scopes

| Role | Scopes |
|---|---|
| `fisher` | `query:write`, `alerts:subscribe` |
| `operator` | + `alerts:manage` |
| `officer` | + `review:decide`, `alerts:broadcast` |
| `analyst` | + `data:export`, `trace:read`, `tools:read` |
| `reviewer` | `review:decide`, `runs:read` |
| `admin` | all + `sources:manage`, `config:write` |

### 3.2 Enforcement

| Rule | Behaviour |
|---|---|
| Missing/invalid token | `401` `AUTH_REQUIRED` (ORCA's own auth, distinct from a source's `AUTH_REQUIRED`) |
| Insufficient scope | `403` `FORBIDDEN` |
| A user may read only their own sessions/runs | Enforced at the query layer, not the handler |
| Review decisions require `review:decide` **and** a different `user_id` than the run's owner where the deployment enables separation of duties | `403` |
| Anonymous demo mode | Optional; read-only, rate-limited, no alerts, no review |

---

## 4. Health

### `GET /v1/health`
```json
{"status":"ok","version":"0.1.0","uptime_s":18422,
 "dependencies":{"postgres":"ok","redis":"ok","object_store":"ok","llm_provider":"ok"}}
```
`200` when serving; `503` with the same body shape when a hard dependency is down.

### `GET /v1/health/sources`
Operational (not audit) status of each external source.
```json
{"checked_at":"2026-09-02T11:00:00Z",
 "sources":[
  {"source_id":"S-02","name":"INCOIS ERDDAP","state":"up",
   "last_success":"2026-09-02T10:58:12Z","latency_ms_p50":940,"breaker":"closed"},
  {"source_id":"S-05","name":"IMD","state":"auth_required",
   "last_success":null,"breaker":"closed","detail":"credentials not configured"},
  {"source_id":"S-06","name":"INCOIS GeoServer/WMS","state":"unknown",
   "detail":"pending network-independent verification"},
  {"source_id":"S-07","name":"CMEMS","state":"up","breaker":"closed"}]}
```
`state ∈ up | degraded | down | auth_required | unknown`. `unknown` is used where the
audit status is PENDING VERIFICATION — the API never asserts "down" for an unverified
endpoint.

---

## 5. Sessions

### `POST /v1/sessions`
```json
// request
{"language":"en","role":"fisher",
 "default_location":{"lat":9.93,"lon":76.26},"title":null}
// 201
{"session_id":"ses-01JBQ6…","created_at":"2026-09-02T10:58:00Z",
 "language":"en","role":"fisher"}
```

### `GET /v1/sessions?limit=20&cursor=…`
Cursor-paginated list of the caller's sessions.

### `GET /v1/sessions/{session_id}/turns`
```json
{"session_id":"ses-01JBQ6…",
 "turns":[
   {"turn_id":"trn-1","kind":"user","text":"I'm near Kochi…","language":"en",
    "created_at":"…"},
   {"turn_id":"trn-2","kind":"orca","run_id":"run-01JBQ7F0AA",
    "headline":"Fishing conditions look favourable, but sea state is marginal…",
    "disposition":"AUTO_RELEASE","created_at":"…"}],
 "context":{"location":{"lat":9.93,"lon":76.26,"label":"near Kochi"},
            "time_window":{"start_time":"2026-09-03T00:00:00Z",
                           "end_time":"2026-09-03T04:00:00Z"}}}
```

### `PATCH /v1/sessions/{session_id}`
Update `language`, `role`, `title` or `default_location`.

### `DELETE /v1/sessions/{session_id}`
Soft-delete; retention policy in `09_DATABASE_SPEC.md` §Retention.

---

## 6. Query Execution

### `POST /v1/sessions/{session_id}/queries`

```http
POST /v1/sessions/ses-01JBQ6/queries
Idempotency-Key: 6f2a1c94-…
Content-Type: application/json
```
```json
{
  "text": "I'm near Kochi. Is tomorrow morning a good time to go fishing, and if not, why?",
  "language": null,
  "location_hint": {"lat": 9.93, "lon": 76.26, "accuracy_m": 120, "source": "device"},
  "time_hint": null,
  "options": {"max_wall_clock_ms": 30000, "allow_stale": false,
              "include_layers": true, "detail_level": "standard"}
}
```

`202 Accepted`
```json
{"run_id":"run-01JBQ7F0AA","session_id":"ses-01JBQ6…","status":"accepted",
 "stream_url":"/v1/runs/run-01JBQ7F0AA/events",
 "result_url":"/v1/runs/run-01JBQ7F0AA","accepted_at":"2026-09-02T11:04:30Z"}
```

**Idempotency.** `Idempotency-Key` is required. A repeat with the same key and the same
body returns the original `run_id` with `202` and `Idempotency-Replayed: true`. The same
key with a different body returns `409 IDEMPOTENCY_KEY_REUSE`. Keys are retained 24 h.

**Validation errors** (`422`): `INVALID_LOCATION`, `INVALID_TIME_WINDOW`,
`SCHEMA_VALIDATION_FAILED`, `QUERY_TOO_LONG`.

### `GET /v1/runs/{run_id}`

While running:
```json
{"run_id":"run-01JBQ7F0AA","status":"running","phase":"assess",
 "started_at":"2026-09-02T11:04:30Z","progress":{"tools_total":9,"tools_done":9},
 "partial":{"assessments":[]}}
```

Completed:
```json
{
  "run_id": "run-01JBQ7F0AA",
  "status": "completed",
  "disposition": "AUTO_RELEASE",
  "language": "en",
  "query_text": "I'm near Kochi. Is tomorrow morning a good time to go fishing, and if not, why?",
  "resolved_context": {
    "location": {"lat": 9.93, "lon": 76.26, "label": "near Kochi", "crs": "EPSG:4326"},
    "time_window": {"start_time": "2026-09-03T00:00:00Z", "end_time": "2026-09-03T04:00:00Z",
                    "display_timezone": "Asia/Kolkata"}
  },
  "headline": "Fishing conditions look favourable near Kochi tomorrow morning, but sea state is marginal for small craft.",
  "limiting_factor": {"domain": "SAFETY", "factor": "significant_wave_height"},
  "narrative": "…",
  "reasoning_summary": "Checked official warnings (none active), wave and wind forecasts, PFZ advisory (imagery only), SST and chlorophyll. Wave height is the limiting factor; lightning could not be checked.",
  "assessments": [
    {"assessment_id":"as-safety-01","domain":"SAFETY","verdict":"MARGINAL",
     "confidence":"medium","limiting":true,
     "drivers":[{"factor":"significant_wave_height","value":2.4,"unit":"m",
                 "evidence_id":"ev-014","contribution":"limiting"}],
     "not_evaluated":[{"factor":"lightning","reason":"AUTH_REQUIRED"}]},
    {"assessment_id":"as-fishing-01","domain":"FISHING_SUITABILITY","verdict":"FAVOURABLE",
     "confidence":"medium","drivers":[]},
    {"assessment_id":"as-reg-01","domain":"REGULATORY","verdict":"PERMITTED",
     "confidence":"high","advisory_only":true}
  ],
  "claims": [{"claim_id":"cl-003","text":"Sea state is marginal for small craft.",
              "evidence_ids":["ev-014","ev-015"],"claim_kind":"interpretation"}],
  "evidence_ids": ["ev-011","ev-014","ev-015","ev-021","ev-022"],
  "conflicts": [{"conflict_id":"cf-002","parameter":"significant_wave_height",
                 "values":[2.4,3.1],"unit":"m","material":true,"safety_relevant":true}],
  "not_evaluated": [{"factor":"lightning","reason":"AUTH_REQUIRED","source_id":"S-05"},
                    {"factor":"pfz_geometry","reason":"RASTER_ONLY","source_id":"S-06"}],
  "fallbacks_used": [{"tool":"get_weather","primary":"S-05","actual":"S-11",
                      "reason":"SOURCE_UNAVAILABLE"}],
  "official_content": [],
  "is_official_advisory": false,
  "disclaimer_id": "disc.not_official_advisory",
  "layers": ["ly-sst","ly-chl","ly-hs","ly-pfz","ly-eez"],
  "human_review": null,
  "timing": {"started_at":"…","completed_at":"…","duration_ms":13020},
  "sources_used": ["S-01","S-02","S-03","S-07","S-08","S-11"]
}
```

`status ∈ accepted | running | awaiting_review | completed | blocked | failed | cancelled`

### `POST /v1/runs/{run_id}/cancel`
`202`; the graph is cancelled at the next superstep boundary. In-flight tool calls are
abandoned; partial results are retained for audit.

---

## 7. Streaming Events (WebSocket)

`WS /v1/runs/{run_id}/events?token=<access_token>`

Server→client frames, newline-delimited JSON objects:

```json
{"seq":1,"type":"run.started","run_id":"run-01JBQ7F0AA","at":"…"}
{"seq":2,"type":"node.started","node":"intent_context","at":"…"}
{"seq":3,"type":"context.resolved",
 "location":{"lat":9.93,"lon":76.26,"label":"near Kochi"},
 "time_window":{"start_time":"…","end_time":"…"},"intent":"fishing_suitability"}
{"seq":4,"type":"plan.created","steps":9,
 "tools":["get_marine_warnings","get_wave_conditions","…"],
 "domains":["SAFETY","FISHING_SUITABILITY","REGULATORY"]}
{"seq":5,"type":"tool.started","step_id":"s2","tool":"get_wave_conditions"}
{"seq":6,"type":"tool.finished","step_id":"s2","tool":"get_wave_conditions",
 "outcome":"success","source_id":"S-07","fallback_used":false,"duration_ms":1904}
{"seq":7,"type":"tool.finished","step_id":"s4","tool":"get_lightning",
 "outcome":"failed","codes":["AUTH_REQUIRED"],"duration_ms":180}
{"seq":8,"type":"validation.finished","required_gaps":[],"conflicts":1}
{"seq":9,"type":"node.finished","node":"geo_reason","derived":["sst_anomaly","current_speed"]}
{"seq":10,"type":"assessment.ready","domain":"SAFETY","verdict":"MARGINAL","confidence":"medium"}
{"seq":11,"type":"conflict.detected","conflict_id":"cf-002",
 "parameter":"significant_wave_height","safety_relevant":true}
{"seq":12,"type":"review.required","reason":"safety_relevant_conflict"}
{"seq":13,"type":"answer.delta","text":"Fishing conditions look favourable"}
{"seq":14,"type":"run.completed","run_id":"run-01JBQ7F0AA","status":"completed"}
{"seq":15,"type":"error","code":"SOURCE_UNAVAILABLE","subject":"get_weather","fatal":false}
```

| Rule | Detail |
|---|---|
| Event types are a closed set | `run.started`, `node.started`, `node.finished`, `context.resolved`, `plan.created`, `tool.started`, `tool.finished`, `validation.finished`, `assessment.ready`, `conflict.detected`, `review.required`, `review.decided`, `answer.delta`, `run.completed`, `error`, `heartbeat` |
| No chain-of-thought | `answer.delta` streams only final answer tokens after grounding validation has passed on the completed draft; if validation fails, deltas are discarded and the template answer is sent whole |
| Ordering | `seq` is monotonic; clients must ignore unknown types |
| Resume | `?from_seq=N` replays buffered events (buffer retained for the run's lifetime + 1 h) |
| Heartbeat | Every 15 s |
| Backpressure | Server drops `answer.delta` frames first under pressure; structural events are never dropped |
| SSE fallback | `GET /v1/runs/{run_id}/events/sse` with the same payloads |

---

## 8. Evidence and Provenance

### `GET /v1/runs/{run_id}/evidence?ids=ev-014,ev-015`
```json
{"evidence":[
  {"evidence_id":"ev-014","domain":"SAFETY",
   "statement":"Significant wave height reaches 2.4 m at 06:00 IST near the query point.",
   "parameter":"significant_wave_height","value":2.4,"unit":"m","value_kind":"forecast",
   "provenance_id":"pv-w14","weight":"primary"}]}
```

### `GET /v1/runs/{run_id}/provenance?ids=pv-w14`
Returns full `Provenance` records (`05` §7), including `derivation` where present.

### `GET /v1/runs/{run_id}/provenance/{provenance_id}/chain`
```json
{"provenance_id":"pv-d09",
 "chain":[{"provenance_id":"pv-s21","role":"input","source":"INCOIS ERDDAP",
           "dataset":"NOAA_AVHRR_AMSR_datasets"},
          {"provenance_id":"pv-d09","role":"derived",
           "method":"anomaly_vs_window_mean","method_version":"1.2"}],
 "consumers":[{"evidence_id":"ev-021"},{"claim_id":"cl-005"}]}
```

### `GET /v1/runs/{run_id}/conflicts`
Full `Conflict` objects including both candidate values, tolerance, materiality and the
applied policy.

### `GET /v1/runs/{run_id}/trace`  *(scope `trace:read`)*
Node/tool execution trace: node names, timings, outcomes, source resolution, model
identifiers, prompt-template versions and token counts. **Never** raw prompts containing
user data beyond retention policy, and never model reasoning traces.

---

## 9. Map and Geospatial Endpoints

### `GET /v1/runs/{run_id}/layers`
```json
{"layers":[
 {"layer_id":"ly-hs","parameter":"significant_wave_height","title":"Significant wave height",
  "representation":"raster","type":"raster_tiles",
  "tiles_url":"/v1/geo/tiles/ly-hs/{z}/{x}/{y}.png",
  "legend_url":"/v1/geo/legend/ly-hs","unit":"m","value_range":[0.4,3.6],
  "bbox":{"min_lat":9.4,"min_lon":75.8,"max_lat":10.4,"max_lon":76.7},"crs":"EPSG:4326",
  "valid_time":"2026-09-03T00:30:00Z","retrieved_at":"2026-09-02T11:04:37Z",
  "freshness":"fresh","source":"CMEMS","source_id":"S-07","external_source":true,
  "fallback_used":false,"provenance_id":"pv-w13","attribution":"CMEMS",
  "default_visible":true,"opacity":0.8},
 {"layer_id":"ly-pfz","parameter":"pfz_advisory","title":"PFZ advisory",
  "representation":"raster","type":"raster_tiles",
  "tiles_url":"/v1/geo/tiles/ly-pfz/{z}/{x}/{y}.png",
  "geometry_available":false,"spatial_test_supported":false,
  "notice_id":"notice.pfz_raster_only",
  "source":"INCOIS","source_id":"S-06","valid_time":"2026-09-03T00:00:00Z"},
 {"layer_id":"ly-eez","parameter":"maritime_boundary","representation":"vector",
  "type":"geojson","features_url":"/v1/geo/features/ly-eez",
  "advisory_only":true,"dataset_version":"<product version>","source_id":"S-08"},
 {"layer_id":"ly-lightning","parameter":"lightning_event","type":"unavailable",
  "unavailable_reason":"AUTH_REQUIRED","source_id":"S-05"}]}
```
Unavailable layers are **returned**, not omitted, so the client can list them with a
reason.

### `GET /v1/geo/features/{layer_id}`
RFC 7946 GeoJSON `FeatureCollection`. Each feature carries
`properties.provenance_id`, `properties.source_id`, `properties.valid_time` and, for
boundaries, `properties.advisory_only` and `properties.dataset_version`.
Query params: `bbox`, `simplify` (display only; the response states
`properties.display_simplified: true`).

### `GET /v1/geo/tiles/{layer_id}/{z}/{x}/{y}.png`
Rendered raster tiles (EPSG:3857). Headers: `Cache-Control`, `ETag`,
`X-ORCA-Provenance-Id`, `X-ORCA-Valid-Time`, `X-ORCA-Source-Id`.
`404` outside the layer's bbox; `410` when the run's layer cache has expired.

### `GET /v1/geo/legend/{layer_id}`
```json
{"layer_id":"ly-hs","unit":"m","scale":"linear",
 "stops":[{"value":0,"color":"#…"},{"value":1.5,"color":"#…"},{"value":3.5,"color":"#…"}],
 "label":"Significant wave height (m)","source":"CMEMS"}
```

### `POST /v1/geo/point`
Click-to-inspect across a run's active layers.
```json
// request
{"run_id":"run-01JBQ7F0AA","lat":9.85,"lon":76.10,"valid_time":"2026-09-03T00:30:00Z"}
// 200
{"values":[
  {"parameter":"significant_wave_height","value":2.4,"unit":"m","value_kind":"forecast",
   "provenance_id":"pv-w14","method":"nearest_node","node_distance_km":6.2},
  {"parameter":"sst","value":28.6,"unit":"degC","value_kind":"observed",
   "provenance_id":"pv-s21","method":"bilinear"}],
 "unsupported":[{"parameter":"pfz_advisory","reason":"RASTER_ONLY"}]}
```

### `POST /v1/geo/boundaries`
```json
// request
{"point":{"lat":8.1,"lon":74.2},"boundary_types":["EEZ","marine_protected_area"]}
// 200
{"results":[{"boundary_type":"EEZ","inside":true,"name":"Indian Exclusive Economic Zone",
             "jurisdiction":"India","dataset_version":"<version>",
             "provenance_id":"pv-b01","advisory_only":true}],
 "unavailable":[{"boundary_type":"marine_protected_area","reason":"DATASET_UNAVAILABLE"}],
 "disclaimer_id":"disc.boundary_advisory_only"}
```

---

## 10. Human Review

### `GET /v1/review/queue?status=pending`  *(scope `review:decide`)*
```json
{"items":[{"run_id":"run-01JBQ7F0AA","reason":"safety_relevant_conflict",
           "domain":"SAFETY","verdict":"MARGINAL","confidence":"medium",
           "created_at":"…","age_s":142,"session_id":"ses-…","role":"fisher"}]}
```

### `POST /v1/runs/{run_id}/review`
```json
// request
{"decision":"approved_with_edits",
 "edits":{"headline":"Sea state is marginal to rough; small craft should not sail."},
 "assessment_overrides":[{"assessment_id":"as-safety-01","verdict":"UNSAFE",
                          "confidence":"medium"}],
 "rationale":"Second forecast source indicates 3.1 m; treating as unsafe for small craft."}
// 200
{"run_id":"run-01JBQ7F0AA","status":"running","resumed":true,
 "review":{"reviewer_id":"usr-…","decision":"approved_with_edits",
           "reviewed_at":"…","audit_id":"aud-…"}}
```

Rules: `rationale` is required for every decision; the original assessment is retained and
returned alongside the override; `decision ∈ approved | approved_with_edits | rejected`;
a rejected run returns `status: blocked` with the reviewer's rationale surfaced to the
user; the decision is idempotent per `(run_id, reviewer_id)`.

---

## 11. Alerts

### `POST /v1/alerts/subscriptions`
```json
{"name":"Kochi grounds","geometry":{"type":"Polygon","coordinates":[[[…]]]},
 "domains":["SAFETY"],
 "min_severity":"WATCH",
 "channels":["in_app","push"],
 "language":"ml",
 "quiet_hours":{"start":"22:00","end":"05:00","timezone":"Asia/Kolkata"},
 "active":true}
// 201 → {"subscription_id":"sub-01J…","created_at":"…"}
```
`GET|PATCH|DELETE /v1/alerts/subscriptions/{id}` for management.

### `GET /v1/alerts?status=unread&limit=50`
```json
{"alerts":[
 {"alert_id":"alr-01J…","subscription_id":"sub-01J…","severity":"WARNING",
  "domain":"SAFETY","title":"Wave height above safe threshold for small craft",
  "body":"…","is_official_advisory":false,
  "official_reference":{"warning_id":"<imd bulletin id>","quoted":true},
  "evidence_ids":["ev-201","ev-202"],"run_id":"run-…",
  "triggered_at":"…","valid_from":"…","valid_to":"…",
  "geometry_ref":"/v1/geo/features/ly-alert-01J","acknowledged":false,
  "dedupe_fingerprint":"…","human_reviewed":true}]}
```

### `POST /v1/alerts/{alert_id}/ack`
`200 {"alert_id":"…","acknowledged_at":"…"}`

### `POST /v1/alerts/test`  *(scope `alerts:manage`)*
Dry-run evaluation of a subscription; returns what **would** be sent without sending.

---

## 12. Registry Endpoints

### `GET /v1/tools`  *(scope `tools:read`)*
```json
{"tools":[{"name":"get_sst","priority":"P0","enabled":true,
           "input_schema":{"$ref":"/v1/schemas/get_sst_input"},
           "primary_source":"S-02","fallbacks":["S-07","S-11"],
           "status":"IMPLEMENTATION REQUIRED"}]}
```
This is the same registry the Planner sees — it contains **no** URLs or credentials.

### `GET /v1/catalog/sources`
Projection of `03_DATA_SOURCE_MATRIX.md`: `source_id`, name, organisation, capability,
role, audit status, access class, external flag, attribution string. No endpoints, no
credentials.

---

## 13. Error Model

All non-2xx responses:

```json
{"error":{"code":"AUTH_REQUIRED","message_id":"err.auth_required.lightning",
          "message":"The IMD lightning service requires credentials.",
          "subject":"get_lightning","source_id":"S-05",
          "retryable":false,"trace_id":"01JBQ7F2K9…",
          "details":{"http_status_from_source":403}}}
```

| HTTP | Codes |
|---|---|
| `400` | `SCHEMA_VALIDATION_FAILED`, malformed body |
| `401` | `AUTH_REQUIRED` (ORCA auth) |
| `403` | `FORBIDDEN` |
| `404` | `NOT_FOUND` |
| `409` | `IDEMPOTENCY_KEY_REUSE`, `REVIEW_ALREADY_DECIDED` |
| `410` | `RUN_EXPIRED`, layer cache expired |
| `422` | `INVALID_LOCATION`, `INVALID_BBOX`, `INVALID_TIME_WINDOW`, `QUERY_TOO_LONG` |
| `429` | `RATE_LIMITED` (with `Retry-After`) |
| `499` | `CLIENT_CANCELLED` |
| `500` | `INTERNAL_ERROR` |
| `503` | `SERVICE_UNAVAILABLE` (hard dependency down) |
| `504` | `TIMEOUT` |

**Source failures are not HTTP failures.** A run in which every source failed still
returns `200` with `status: "failed"` and a populated `not_evaluated` list — the API call
succeeded; the retrieval did not. This distinction is deliberate and is asserted in tests.

---

## 14. Rate Limiting

| Scope | Limit (initial engineering parameters) |
|---|---|
| `POST /queries` per user | 20 / hour, burst 5 |
| `POST /queries` per IP (anonymous demo) | 10 / hour |
| Tile requests per user | 600 / min |
| WebSocket connections per user | 5 concurrent |
| Alert subscriptions per user | 20 |
| `POST /geo/point` per user | 120 / min |

Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.
Implementation: Redis token bucket keyed by `(user_id | ip, route_class)`.

**Upstream protection.** ORCA additionally enforces per-source outbound budgets so that a
burst of user queries cannot exceed a provider's acceptable use; when the outbound budget
is exhausted the tool returns `RATE_LIMITED` and the answer states the limitation.

---

## 15. Idempotency and Caching

| Concern | Rule |
|---|---|
| Query submission | `Idempotency-Key` required; 24 h window |
| Review decisions | Idempotent per `(run_id, reviewer_id)`; second differing decision ⇒ `409` |
| Subscription creation | `Idempotency-Key` optional |
| GET responses | `ETag` + `Cache-Control`; runs are immutable once completed (`max-age=3600, immutable`) |
| Tiles | `ETag`, `max-age` derived from the layer's product cadence |
| Tool-level cache | Server-side, keyed by `(tool, normalised args)`; `retrieved_at` is never rewritten by a cache hit; `cache.cache_hit` is exposed in provenance |

---

## 16. Pagination and Conventions

- Cursor pagination: `?limit=&cursor=` → `{"items":[…],"next_cursor":"…"}`. Cursors are
  opaque, signed and expire in 1 h.
- Field selection: `?fields=` on evidence/provenance endpoints.
- All identifiers are ULID-based with a type prefix (`run-`, `ses-`, `ev-`, `pv-`, `alr-`).
- `Accept-Language` sets response localisation for message strings; the answer language
  is set by the session, not the header.
- CORS restricted to configured origins; credentials via bearer token only.
- API version in the path; breaking changes require `/v2`.

---

## 17. Alignment With the Rest of the Architecture

| API surface | Backed by |
|---|---|
| `POST /queries` | `07` graph invocation with `thread_id = run_id` |
| stream events | `07` node events, filtered |
| `/evidence`, `/provenance` | `05` Evidence/Provenance models |
| `/layers`, `/geo/*` | `11` geospatial kernel outputs |
| `/assessments`, `/conflicts` | `12` assessment framework |
| `/review` | `07` `human_review` interrupt + `12` escalation policy |
| `/alerts` | `13` alerting architecture |
| `/health/sources` | `03` source registry + circuit-breaker state |
| `/tools` | `04` tool contracts |
