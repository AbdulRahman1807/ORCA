# ORCA — Database and Persistence Specification

**Document:** 09 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Design defined — IMPLEMENTATION REQUIRED

---

## 1. Storage Strategy

ORCA separates four kinds of state, because they have different size, mutability,
query and retention characteristics.

| Tier | Technology | Holds | Why |
|---|---|---|---|
| **Relational + spatial** | PostgreSQL 16 + PostGIS 3.4 | Sessions, runs, agent/tool executions, provenance, evidence, assessments, conflicts, boundaries, geofences, alerts, users, audit, overrides | Referential integrity, spatial indexing, transactional audit |
| **Vector** | pgvector (same PostgreSQL instance) | RAG document chunks + embeddings | Avoids a second datastore for the MVP; metadata filtering happens in SQL alongside the vectors |
| **Object storage** | S3 / MinIO | Gridded arrays, NetCDF/GeoTIFF payloads, rendered tiles, raw source responses, export artifacts | Large binary payloads must never live in rows |
| **Cache / ephemeral** | Redis | Tool-response cache, rate limits, idempotency keys, WebSocket event buffer, session working context | TTL-bound, reconstructible, non-authoritative |

**Rule.** A grid array never enters a table. Rows store an `object_uri`; the bytes live in
object storage. A row is the *record of* a value; the object is the value.

**Rule.** Anything in Redis must be reconstructible. Losing Redis degrades performance,
never correctness.

---

## 2. Schema Overview

```
                     ┌──────────┐        ┌──────────────┐
                     │  users   │───────▶│   sessions   │
                     └────┬─────┘        └──────┬───────┘
                          │                     │
                          │                     ▼
                          │              ┌──────────────┐
                          │              │    turns     │
                          │              └──────┬───────┘
                          │                     ▼
                          │              ┌──────────────┐
                          │              │     runs     │◀───── graph checkpoints
                          │              └──────┬───────┘
        ┌─────────────────┼─────────────────────┼───────────────────┐
        ▼                 ▼                     ▼                   ▼
 ┌─────────────┐  ┌──────────────┐      ┌──────────────┐    ┌──────────────┐
 │ agent_execs │  │  tool_execs  │      │ assessments  │    │ conflicts    │
 └─────────────┘  └──────┬───────┘      └──────┬───────┘    └──────────────┘
                         ▼                     ▼
                  ┌──────────────┐      ┌──────────────┐
                  │  provenance  │◀─────│   evidence   │
                  └──────┬───────┘      └──────┬───────┘
                         ▼                     ▼
                  ┌──────────────┐      ┌──────────────┐
                  │ data_objects │      │    claims    │
                  └──────────────┘      └──────────────┘

 reference/spatial:  sources · datasets · boundaries · geofences
 operational:        alerts · alert_subscriptions · human_reviews · audit_log
 rag:                documents · doc_chunks(vector) · rag_queries
```

---

## 3. Core Tables

### 3.1 `users`
```sql
CREATE TABLE users (
  user_id        TEXT PRIMARY KEY,                     -- usr-<ULID>
  external_id    TEXT UNIQUE,
  display_name   TEXT,
  role           TEXT NOT NULL CHECK (role IN
                   ('fisher','operator','officer','analyst','reviewer','admin')),
  org            TEXT,
  language       TEXT NOT NULL DEFAULT 'en',           -- BCP-47
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at   TIMESTAMPTZ,
  status         TEXT NOT NULL DEFAULT 'active',
  deleted_at     TIMESTAMPTZ
);
```
No credentials are stored here; authentication is delegated to the identity provider and
only the subject identifier is retained (`14_SECURITY_PRIVACY_AND_GOVERNANCE.md`).

### 3.2 `sessions` / `turns`
```sql
CREATE TABLE sessions (
  session_id       TEXT PRIMARY KEY,                   -- ses-<ULID>
  user_id          TEXT REFERENCES users(user_id),
  title            TEXT,
  language         TEXT NOT NULL DEFAULT 'en',
  role_context     TEXT,
  default_location GEOGRAPHY(POINT, 4326),
  context          JSONB NOT NULL DEFAULT '{}',        -- carried location/time/topic
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at       TIMESTAMPTZ
);

CREATE TABLE turns (
  turn_id     TEXT PRIMARY KEY,                        -- trn-<ULID>
  session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  seq         INT  NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('user','orca','system','clarification')),
  text        TEXT,
  language    TEXT,
  run_id      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (session_id, seq)
);
```

### 3.3 `runs`
```sql
CREATE TABLE runs (
  run_id            TEXT PRIMARY KEY,                  -- run-<ULID>, = LangGraph thread_id
  session_id        TEXT NOT NULL REFERENCES sessions(session_id),
  user_id           TEXT REFERENCES users(user_id),
  query_text        TEXT NOT NULL,
  language          TEXT NOT NULL,
  intent            TEXT,
  intent_confidence REAL,
  resolved_location GEOGRAPHY(POINT, 4326),
  resolved_bbox     GEOGRAPHY(POLYGON, 4326),
  time_window       TSTZRANGE,
  status            TEXT NOT NULL,                     -- accepted|running|awaiting_review|
                                                       -- completed|blocked|failed|cancelled
  disposition       TEXT,                              -- AUTO_RELEASE|REVIEW_REQUIRED|BLOCKED
  plan              JSONB,
  plan_version      INT DEFAULT 1,
  headline          TEXT,
  narrative         TEXT,
  reasoning_summary TEXT,
  limiting_domain   TEXT,
  limiting_factor   TEXT,
  confidence        TEXT,
  is_official_advisory BOOLEAN NOT NULL DEFAULT FALSE,
  not_evaluated     JSONB NOT NULL DEFAULT '[]',
  fallbacks_used    JSONB NOT NULL DEFAULT '[]',
  sources_used      TEXT[] NOT NULL DEFAULT '{}',
  idempotency_key   TEXT,
  trace_id          TEXT,
  started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at      TIMESTAMPTZ,
  duration_ms       INT,
  error             JSONB,
  CONSTRAINT is_official_advisory_must_be_false CHECK (is_official_advisory = FALSE)
);

CREATE INDEX ON runs (session_id, started_at DESC);
CREATE INDEX ON runs (status) WHERE status IN ('running','awaiting_review');
CREATE INDEX ON runs USING GIST (resolved_location);
CREATE UNIQUE INDEX ON runs (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
```

The `CHECK` constraint is deliberate: it makes it structurally impossible for ORCA to
persist one of its own outputs as an official advisory. Official content lives only in
`data_objects` as quoted `MarineWarning` records with `is_official = true`.

### 3.4 `agent_executions`
```sql
CREATE TABLE agent_executions (
  agent_exec_id   TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  agent           TEXT NOT NULL CHECK (agent IN
                    ('planner','data_discovery','geospatial','risk','reporting')),
  node            TEXT NOT NULL,
  attempt         INT NOT NULL DEFAULT 1,
  status          TEXT NOT NULL,                       -- success|degraded|failed
  input_ref       TEXT,                                -- object_uri (state slice snapshot)
  output_ref      TEXT,
  reasoning_summary TEXT,
  model_id        TEXT,
  prompt_template_version TEXT,
  tokens_in       INT, tokens_out INT, cost_micros BIGINT,
  started_at      TIMESTAMPTZ NOT NULL,
  finished_at     TIMESTAMPTZ,
  duration_ms     INT,
  error           JSONB
);
CREATE INDEX ON agent_executions (run_id, started_at);
```

**Not stored:** prompts containing raw user location beyond retention policy, and model
chain-of-thought. `reasoning_summary` is the short, user-safe summary only.

### 3.5 `tool_executions`
```sql
CREATE TABLE tool_executions (
  tool_exec_id     TEXT PRIMARY KEY,
  run_id           TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  step_id          TEXT,
  tool             TEXT NOT NULL,
  args             JSONB NOT NULL,
  args_fingerprint TEXT NOT NULL,                      -- sha256 of normalised args
  primary_source   TEXT REFERENCES sources(source_id),
  actual_source    TEXT REFERENCES sources(source_id),
  fallback_used    BOOLEAN NOT NULL DEFAULT FALSE,
  fallback_reason  TEXT,
  status           TEXT NOT NULL,                      -- success|partial|empty|error
  codes            TEXT[] NOT NULL DEFAULT '{}',
  attempts         JSONB NOT NULL DEFAULT '[]',
  cache_hit        BOOLEAN NOT NULL DEFAULT FALSE,
  raw_response_ref TEXT,                               -- object_uri (retention-bounded)
  response_bytes   BIGINT,
  started_at       TIMESTAMPTZ NOT NULL,
  finished_at      TIMESTAMPTZ,
  duration_ms      INT
);
CREATE INDEX ON tool_executions (run_id);
CREATE INDEX ON tool_executions (tool, started_at DESC);
CREATE INDEX ON tool_executions (actual_source, status);
```

`raw_response_ref` preserves the exact upstream payload for a bounded window, which is
what makes "reconstruct why this recommendation was made" genuinely possible rather than
aspirational.

### 3.6 `provenance`
```sql
CREATE TABLE provenance (
  provenance_id      TEXT PRIMARY KEY,                 -- pv-<ULID>
  run_id             TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  tool_exec_id       TEXT REFERENCES tool_executions(tool_exec_id),
  parameter          TEXT NOT NULL,
  value_kind         TEXT NOT NULL CHECK (value_kind IN
                       ('observed','forecast','derived','model','interpretation')),
  value_numeric      DOUBLE PRECISION,
  value_json         JSONB,
  unit               TEXT,
  geom               GEOGRAPHY(GEOMETRY, 4326),
  depth_m            REAL,
  valid_time         TIMESTAMPTZ,
  valid_from         TIMESTAMPTZ,
  valid_to           TIMESTAMPTZ,
  reference_time     TIMESTAMPTZ,
  lead_time_h        REAL,
  representativeness TEXT,
  source_id          TEXT REFERENCES sources(source_id),
  dataset_id         TEXT REFERENCES datasets(dataset_id),
  product_reference  TEXT,
  retrieved_at       TIMESTAMPTZ NOT NULL,
  spatial_resolution TEXT,
  temporal_resolution TEXT,
  quality            JSONB NOT NULL DEFAULT '{}',
  uncertainty        JSONB,
  derivation         JSONB,                            -- method, version, inputs[], params
  external_source    BOOLEAN NOT NULL DEFAULT FALSE,
  fallback_used      BOOLEAN NOT NULL DEFAULT FALSE,
  cache_hit          BOOLEAN NOT NULL DEFAULT FALSE,
  request_fingerprint TEXT,
  data_object_id     TEXT REFERENCES data_objects(data_object_id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON provenance (run_id);
CREATE INDEX ON provenance USING GIST (geom);
CREATE INDEX ON provenance (parameter, valid_time DESC);
CREATE INDEX ON provenance USING GIN (derivation jsonb_path_ops);
```

**Derivation graph queries** (recursive CTE over `derivation->'inputs'`) reconstruct the
full chain from a claim back to raw source responses — the mechanism behind
`GET /v1/runs/{id}/provenance/{pid}/chain`.

### 3.7 `data_objects`
Metadata rows for payloads held in object storage.
```sql
CREATE TABLE data_objects (
  data_object_id TEXT PRIMARY KEY,
  run_id         TEXT REFERENCES runs(run_id) ON DELETE SET NULL,
  kind           TEXT NOT NULL,   -- grid|raster_tiles|geojson|netcdf|raw_response|export|warning_text
  object_uri     TEXT NOT NULL,   -- s3://…
  content_type   TEXT,
  bytes          BIGINT,
  checksum       TEXT,
  parameter      TEXT,
  bbox           GEOGRAPHY(POLYGON, 4326),
  valid_time     TIMESTAMPTZ,
  representation TEXT,            -- point|grid|raster|vector|bulletin
  is_official    BOOLEAN NOT NULL DEFAULT FALSE,
  expires_at     TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON data_objects USING GIST (bbox);
CREATE INDEX ON data_objects (expires_at) WHERE expires_at IS NOT NULL;
```

### 3.8 `evidence`, `claims`, `assessments`, `conflicts`
```sql
CREATE TABLE evidence (
  evidence_id   TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  domain        TEXT NOT NULL,
  statement     TEXT NOT NULL,
  parameter     TEXT,
  value_numeric DOUBLE PRECISION,
  unit          TEXT,
  value_kind    TEXT NOT NULL,
  provenance_id TEXT NOT NULL REFERENCES provenance(provenance_id),
  weight        TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE claims (
  claim_id     TEXT PRIMARY KEY,
  run_id       TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  text         TEXT NOT NULL,
  claim_kind   TEXT NOT NULL,          -- observation|forecast|derived|interpretation|quote
  domain       TEXT,
  confidence   TEXT,
  official_source BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE claim_evidence (
  claim_id    TEXT REFERENCES claims(claim_id) ON DELETE CASCADE,
  evidence_id TEXT REFERENCES evidence(evidence_id) ON DELETE CASCADE,
  PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE assessments (
  assessment_id  TEXT PRIMARY KEY,
  run_id         TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  domain         TEXT NOT NULL CHECK (domain IN
                   ('SAFETY','FISHING_SUITABILITY','ECOLOGICAL','REGULATORY')),
  verdict        TEXT NOT NULL,
  confidence     TEXT NOT NULL,
  drivers        JSONB NOT NULL DEFAULT '[]',
  not_evaluated  JSONB NOT NULL DEFAULT '[]',
  threshold_set  TEXT,
  threshold_set_status TEXT,
  uncertainty    JSONB,
  geom           GEOGRAPHY(GEOMETRY, 4326),
  valid_from     TIMESTAMPTZ,
  valid_to       TIMESTAMPTZ,
  superseded_by  TEXT REFERENCES assessments(assessment_id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_id, domain, created_at)
);

CREATE TABLE conflicts (
  conflict_id     TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  parameter       TEXT NOT NULL,
  candidates      JSONB NOT NULL,        -- [{provenance_id, source_id, value, unit}]
  delta           JSONB NOT NULL,
  tolerance       JSONB NOT NULL,
  material        BOOLEAN NOT NULL,
  safety_relevant BOOLEAN NOT NULL,
  policy          TEXT NOT NULL,
  used_provenance_id TEXT REFERENCES provenance(provenance_id),
  rationale       TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Override discipline.** A human override never mutates an assessment row. It inserts a
new row and sets `superseded_by` on the original, so both versions survive.

---

## 4. Reference and Spatial Tables

### 4.1 `sources` / `datasets`
```sql
CREATE TABLE sources (
  source_id      TEXT PRIMARY KEY,        -- S-01 … S-18 (matches 03_DATA_SOURCE_MATRIX)
  name           TEXT NOT NULL,
  organisation   TEXT NOT NULL,
  access_class   TEXT,                    -- A..F
  audit_status   TEXT NOT NULL,           -- VERIFIED|CONFIRMED|AUTH REQUIRED|PENDING VERIFICATION|…
  role           TEXT,                    -- PRIMARY|FALLBACK|SECONDARY|ENHANCEMENT|CONTEXT
  external_source BOOLEAN NOT NULL DEFAULT FALSE,
  attribution    TEXT NOT NULL,
  licence_reference TEXT,
  operational_state TEXT,                 -- up|degraded|down|auth_required|unknown
  breaker_state  TEXT DEFAULT 'closed',
  last_success_at TIMESTAMPTZ,
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE datasets (
  dataset_id        TEXT PRIMARY KEY,     -- e.g. incois_oceansat2_datasets
  source_id         TEXT NOT NULL REFERENCES sources(source_id),
  title             TEXT,
  variables         JSONB NOT NULL DEFAULT '[]',   -- [{name, canonical, unit}]
  spatial_resolution TEXT,
  temporal_resolution TEXT,
  coverage_bbox     GEOGRAPHY(POLYGON, 4326),
  coverage_time     TSTZRANGE,
  representativeness TEXT,
  verified_at       TIMESTAMPTZ,
  metadata          JSONB NOT NULL DEFAULT '{}',
  status            TEXT NOT NULL DEFAULT 'unverified'
);
```
`datasets` is populated by the **dataset-metadata capture** task in Phase 1
(`03_DATA_SOURCE_MATRIX.md` §V-1). Until a row is verified, its resolution fields stay
null rather than being guessed.

### 4.2 `boundaries`
```sql
CREATE TABLE boundaries (
  boundary_id     TEXT PRIMARY KEY,
  boundary_type   TEXT NOT NULL,          -- EEZ|territorial_sea|international_boundary|
                                          -- marine_protected_area|restricted_zone
  name            TEXT,
  jurisdiction    TEXT,
  source_id       TEXT NOT NULL REFERENCES sources(source_id),
  dataset_version TEXT NOT NULL,
  effective_date  DATE,
  geom            GEOGRAPHY(MULTIPOLYGON, 4326) NOT NULL,
  geom_simplified GEOGRAPHY(MULTIPOLYGON, 4326),      -- display only
  attributes      JSONB NOT NULL DEFAULT '{}',
  advisory_only   BOOLEAN NOT NULL DEFAULT TRUE,
  loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON boundaries USING GIST (geom);
CREATE INDEX ON boundaries (boundary_type, dataset_version);
```
Boundaries are **preloaded snapshots**, versioned. A new release inserts new rows; old
rows are retained so historical runs remain reproducible against the geometry they
actually used. `advisory_only` defaults to `TRUE` and is never set false in the MVP.

### 4.3 `geofences`
```sql
CREATE TABLE geofences (
  geofence_id TEXT PRIMARY KEY,
  user_id     TEXT REFERENCES users(user_id),
  name        TEXT NOT NULL,
  geom        GEOGRAPHY(POLYGON, 4326) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  active      BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ON geofences USING GIST (geom) WHERE active;
```

---

## 5. Alerts and Review

```sql
CREATE TABLE alert_subscriptions (
  subscription_id TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES users(user_id),
  geofence_id  TEXT NOT NULL REFERENCES geofences(geofence_id),
  domains      TEXT[] NOT NULL,
  min_severity TEXT NOT NULL,
  channels     TEXT[] NOT NULL,
  language     TEXT NOT NULL DEFAULT 'en',
  quiet_hours  JSONB,
  active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
  alert_id        TEXT PRIMARY KEY,
  subscription_id TEXT REFERENCES alert_subscriptions(subscription_id),
  run_id          TEXT REFERENCES runs(run_id),
  severity        TEXT NOT NULL,
  domain          TEXT NOT NULL,
  title           TEXT NOT NULL,
  body            TEXT NOT NULL,
  language        TEXT NOT NULL,
  is_official_advisory BOOLEAN NOT NULL DEFAULT FALSE,
  official_reference JSONB,
  evidence_ids    TEXT[] NOT NULL DEFAULT '{}',
  geom            GEOGRAPHY(GEOMETRY, 4326),
  dedupe_fingerprint TEXT NOT NULL,
  human_reviewed  BOOLEAN NOT NULL DEFAULT FALSE,
  triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_from      TIMESTAMPTZ, valid_to TIMESTAMPTZ,
  delivered_at    TIMESTAMPTZ, acknowledged_at TIMESTAMPTZ,
  delivery_status JSONB NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX ON alerts (subscription_id, dedupe_fingerprint, valid_from);
CREATE INDEX ON alerts USING GIST (geom);

CREATE TABLE human_reviews (
  review_id     TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES runs(run_id),
  alert_id      TEXT REFERENCES alerts(alert_id),
  reviewer_id   TEXT NOT NULL REFERENCES users(user_id),
  reviewer_role TEXT NOT NULL,
  trigger_reason TEXT NOT NULL,
  decision      TEXT NOT NULL CHECK (decision IN
                  ('approved','approved_with_edits','rejected','timed_out')),
  rationale     TEXT NOT NULL,
  original      JSONB NOT NULL,          -- pre-review recommendation + assessments
  revised       JSONB,
  requested_at  TIMESTAMPTZ NOT NULL,
  decided_at    TIMESTAMPTZ,
  latency_s     INT,
  audit_id      TEXT
);
CREATE INDEX ON human_reviews (run_id);
CREATE INDEX ON human_reviews (decision, decided_at DESC);
```

---

## 6. Audit Log

```sql
CREATE TABLE audit_log (
  audit_id     BIGSERIAL PRIMARY KEY,
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor_type   TEXT NOT NULL,    -- user|system|agent|scheduler
  actor_id     TEXT,
  action       TEXT NOT NULL,    -- query.submitted|run.completed|review.decided|
                                 -- override.applied|alert.dispatched|source.status_changed|
                                 -- config.changed|data.exported|auth.failed
  object_type  TEXT NOT NULL,
  object_id    TEXT,
  run_id       TEXT,
  details      JSONB NOT NULL DEFAULT '{}',
  prev_hash    TEXT,
  row_hash     TEXT NOT NULL,    -- sha256(prev_hash || canonical(row))
  trace_id     TEXT
);
CREATE INDEX ON audit_log (occurred_at DESC);
CREATE INDEX ON audit_log (run_id);
CREATE INDEX ON audit_log (action, occurred_at DESC);
```

**Append-only.** Enforced by a `BEFORE UPDATE OR DELETE` trigger that raises, plus
role-level permissions (the application role holds `INSERT` and `SELECT` only). The hash
chain makes silent tampering detectable.

---

## 7. Graph Checkpoints

LangGraph's PostgreSQL checkpointer owns its own tables (`checkpoints`,
`checkpoint_writes`, `checkpoint_blobs`) keyed by `thread_id = run_id`.

| Property | Decision |
|---|---|
| Backend | PostgreSQL (same instance, separate schema `langgraph`) |
| Why not Redis | Human review may be pending for hours; checkpoints must survive restarts and be auditable |
| Retention | 30 days for completed runs; indefinite while `awaiting_review` |
| Relationship to `runs` | `runs` is the queryable projection; checkpoints are the replay substrate. Both are written; neither is derived from the other at read time |

---

## 8. RAG Tables

```sql
CREATE TABLE documents (
  document_id   TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  corpus        TEXT NOT NULL,          -- methodology|glossary|advisory_guidance|
                                        -- dataset_docs|scientific_literature|sop
  source_org    TEXT,
  publisher     TEXT,
  document_uri  TEXT,
  object_uri    TEXT,
  published_at  DATE,
  version       TEXT,
  language      TEXT NOT NULL DEFAULT 'en',
  authority_tier TEXT NOT NULL,         -- official|peer_reviewed|institutional|other
  licence_reference TEXT,
  superseded_by TEXT REFERENCES documents(document_id),
  status        TEXT NOT NULL DEFAULT 'active',   -- active|stale|withdrawn
  ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  checksum      TEXT
);

CREATE TABLE doc_chunks (
  chunk_id     TEXT PRIMARY KEY,
  document_id  TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
  seq          INT NOT NULL,
  text         TEXT NOT NULL,
  tokens       INT,
  section_path TEXT,
  page_from    INT, page_to INT,
  embedding    VECTOR(1024),            -- dimension fixed by the configured model
  embedding_model TEXT NOT NULL,
  tsv          TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
  metadata     JSONB NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON doc_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON doc_chunks USING GIN (tsv);
CREATE INDEX ON doc_chunks (document_id, seq);

CREATE TABLE rag_queries (
  rag_query_id TEXT PRIMARY KEY,
  run_id       TEXT REFERENCES runs(run_id),
  query_text   TEXT NOT NULL,
  filters      JSONB,
  retrieved    JSONB NOT NULL,          -- [{chunk_id, dense, lexical, rerank, used}]
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
Embedding dimension is set by the configured model and is a migration-level decision; a
model change requires a re-embedding migration, not an in-place column change.

---

## 9. Object Storage Layout

```
s3://orca-{env}/
├── raw/{yyyy}/{mm}/{dd}/{source_id}/{tool_exec_id}.{ext}     raw upstream payloads
├── fields/{run_id}/{field_id}.npz                            gridded arrays + mask
├── tiles/{layer_id}/{z}/{x}/{y}.png                          rendered raster tiles
├── geo/{layer_id}.geojson                                    vector layers
├── warnings/{warning_id}.json                                verbatim official bulletins
├── docs/{document_id}/{filename}                             RAG source documents
├── exports/{user_id}/{export_id}.{ext}                       user exports
└── demo/{scenario_id}/…                                      pre-staged demo fixtures
```

| Prefix | Retention | Notes |
|---|---|---|
| `raw/` | 30 days (configurable) | Enables audit reconstruction; the largest volume |
| `fields/` | Run retention | Referenced by `values_ref` |
| `tiles/` | 7 days | Regenerable from `fields/` |
| `warnings/` | 1 year | Official content is retained longer for audit |
| `docs/` | Indefinite | Corpus |
| `demo/` | Indefinite | Labelled as pre-staged; never presented as live |

Server-side encryption at rest; bucket policies deny public access; object URIs are never
handed to clients directly — access flows through ORCA endpoints with authorisation.

---

## 10. Redis Usage

| Key pattern | Purpose | TTL |
|---|---|---|
| `tool:{tool}:{args_fingerprint}` | Tool response cache | Per-parameter, from product cadence |
| `idem:{user_id}:{key}` | Idempotency records | 24 h |
| `rate:{scope}:{id}` | Token buckets | Window |
| `events:{run_id}` | WebSocket event buffer | Run lifetime + 1 h |
| `session:ctx:{session_id}` | Hot conversation context | 24 h |
| `breaker:{source_id}` | Circuit-breaker state | Cool-down |
| `lock:alerts:{subscription_id}` | Alert evaluation lock | 60 s |

Cache entries store the original `retrieved_at`; a cache hit never rewrites retrieval
time, and sets `cache_hit = true` in provenance.

---

## 11. Retention and Privacy

| Data | Default retention | Rationale |
|---|---|---|
| Sessions, turns | 12 months, user-deletable | Conversation history |
| Runs, assessments, evidence, provenance | 12 months | Explainability and audit |
| Raw source responses | 30 days | Audit reconstruction vs storage cost |
| Precise user location | 90 days, then coarsened to ~10 km | Location is personal data (`14`) |
| Audit log | 24 months minimum, append-only | Governance |
| Human reviews | Life of the audit log | Accountability |
| Alerts | 12 months | |
| Graph checkpoints | 30 days after completion | Replay window |
| Demo fixtures | Indefinite | Labelled pre-staged |

Retention values are **initial policy proposals requiring organisational and legal
confirmation**; applicable Indian frameworks (including the DPDP Act, 2023) are identified
as considerations in `14_SECURITY_PRIVACY_AND_GOVERNANCE.md`, not as compliance claims.

Deletion: a user deletion request soft-deletes sessions/turns, anonymises `runs.user_id`
and precise locations, and **retains** audit rows with the actor pseudonymised — an
append-only audit log cannot be selectively rewritten.

---

## 12. Migrations, Backup and Operations

- **Migrations**: Alembic, forward-only, reviewed. PostGIS and pgvector extensions are
  created in the initial migration. Every migration is reversible in staging or
  documented as irreversible.
- **Backups**: nightly base backup + WAL archiving; object storage versioning enabled;
  restore rehearsal is a Definition-of-Done item (`30`).
- **Indexes**: every spatial column has a GiST index; hot query paths
  (`runs(session_id, started_at)`, `tool_executions(tool, started_at)`,
  `provenance(run_id)`) are indexed and verified with `EXPLAIN` in load tests.
- **Partitioning** (P1): `tool_executions`, `provenance` and `audit_log` partitioned
  monthly once volume warrants.
- **Roles**: `orca_app` (DML on operational tables, INSERT+SELECT on `audit_log`),
  `orca_ro` (analyst reads), `orca_migrate` (DDL). No application component uses a
  superuser role.
- **PII in logs**: forbidden. Location values in application logs are truncated to
  reduced precision (`20_OBSERVABILITY_AND_AUDIT_SPEC.md`).

---

## 13. Key Queries

```sql
-- Reconstruct the provenance chain behind a claim
WITH RECURSIVE chain AS (
  SELECT p.* FROM provenance p
  JOIN evidence e USING (provenance_id)
  JOIN claim_evidence ce USING (evidence_id)
  WHERE ce.claim_id = $1
  UNION ALL
  SELECT p2.* FROM provenance p2
  JOIN chain c ON p2.provenance_id = ANY (
        SELECT jsonb_array_elements_text(c.derivation->'inputs'))
)
SELECT * FROM chain;

-- Which runs used a fallback source in the last 24 h, and why
SELECT run_id, tool, primary_source, actual_source, fallback_reason, started_at
FROM tool_executions
WHERE fallback_used AND started_at > now() - interval '24 hours'
ORDER BY started_at DESC;

-- Alert subscriptions intersecting an active warning polygon
SELECT s.subscription_id, s.user_id
FROM alert_subscriptions s
JOIN geofences g USING (geofence_id)
WHERE s.active AND g.active
  AND ST_Intersects(g.geom, ST_GeogFromText($1));

-- Domain disagreement (the differentiator, measured)
SELECT r.run_id,
       max(a.verdict) FILTER (WHERE a.domain='SAFETY')              AS safety,
       max(a.verdict) FILTER (WHERE a.domain='FISHING_SUITABILITY') AS fishing
FROM runs r JOIN assessments a USING (run_id)
GROUP BY r.run_id
HAVING max(a.verdict) FILTER (WHERE a.domain='SAFETY') IN ('UNSAFE','UNFAVOURABLE')
   AND max(a.verdict) FILTER (WHERE a.domain='FISHING_SUITABILITY') = 'FAVOURABLE';
```
