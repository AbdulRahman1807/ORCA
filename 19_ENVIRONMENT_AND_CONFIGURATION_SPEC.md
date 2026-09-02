# ORCA — Environment and Configuration Specification

**Document:** 19 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** PROPOSED — IMPLEMENTATION REQUIRED

---

## 1. Configuration Principles

1. **Secrets never live in source.** No credential, token or key appears in the
   repository, in `config/`, in a container image, in a log, or in model context.
   Enforced by pre-commit secret scanning and a CI gate.
2. **Policy and secrets are separated.** `config/*.yaml` describes *behaviour* (thresholds,
   tolerances, tool enablement, alert cadence) and is version-controlled and reviewable.
   Environment variables carry *credentials and endpoints*.
3. **Configuration is explicit.** No silent defaults for anything that changes behaviour
   materially. A missing required variable fails startup loudly.
4. **Behaviour is inspectable.** The effective configuration (with secrets redacted) is
   available at `/v1/health/config` to `admin`, and is logged once at startup.
5. **A missing credential degrades, never crashes.** Absent IMD credentials must produce
   `AUTH_REQUIRED` at the tool layer — the service still starts and still answers what it
   can.

---

## 2. Configuration Hierarchy

Later layers override earlier ones:

```
1. Code defaults                       (settings.py — safe, conservative)
2. config/*.yaml                       (policy; version-controlled)
3. Environment-specific overlay        (config/environments/{env}.yaml)
4. Environment variables               (credentials, endpoints, infrastructure)
5. Secrets manager                     (production; overrides env vars for secret keys)
6. Runtime feature flags               (config/feature_flags.yaml + admin API)
```

```python
# backend/orca/settings.py  (shape)
class Settings(BaseSettings):
    env: Literal["local","dev","staging","demo","prod"] = "local"
    model_config = SettingsConfigDict(env_prefix="ORCA_", env_file=".env",
                                      case_sensitive=False)
    # required-in-non-local fields have no default → startup fails if absent
```

---

## 3. Environment Variables

### 3.1 Core

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ORCA_ENV` | yes | `local` | `local`\|`dev`\|`staging`\|`demo`\|`prod` |
| `ORCA_LOG_LEVEL` | no | `INFO` | |
| `ORCA_LOG_FORMAT` | no | `json` | `json` in all non-local environments |
| `ORCA_API_HOST` / `ORCA_API_PORT` | no | `0.0.0.0` / `8000` | |
| `ORCA_CORS_ORIGINS` | yes (non-local) | — | Comma-separated |
| `ORCA_BASE_URL` | yes (non-local) | — | Used for absolute layer/tile URLs |
| `ORCA_TIMEZONE_DISPLAY` | no | `Asia/Kolkata` | Presentation only; storage is UTC |

### 3.2 Database, cache, object storage

| Variable | Required | Notes |
|---|---|---|
| `ORCA_DATABASE_URL` | yes | `postgresql+psycopg://user:pass@host:5432/orca` — **secret** |
| `ORCA_DATABASE_POOL_SIZE` / `_MAX_OVERFLOW` | no | Defaults 10 / 20 |
| `ORCA_REDIS_URL` | yes | **secret** if it carries a password |
| `ORCA_S3_ENDPOINT` | yes | MinIO or cloud endpoint |
| `ORCA_S3_BUCKET` | yes | `orca-{env}` |
| `ORCA_S3_ACCESS_KEY` / `ORCA_S3_SECRET_KEY` | yes | **secret** |
| `ORCA_S3_REGION` | no | |
| `ORCA_S3_USE_TLS` | no | `true`; never `false` outside local |

### 3.3 Model provider

| Variable | Required | Notes |
|---|---|---|
| `ORCA_LLM_PROVIDER` | yes | Provider key resolved by the `LLMProvider` abstraction |
| `ORCA_LLM_API_KEY` | yes | **secret** |
| `ORCA_LLM_MODEL_PLANNER` | yes | Model identifier for planning/reporting-class work |
| `ORCA_LLM_MODEL_FAST` | no | Cheaper model for classification/summary nodes |
| `ORCA_LLM_TEMPERATURE` | no | `0` — reproducibility; overriding is a documented decision |
| `ORCA_LLM_TIMEOUT_S` | no | `30` |
| `ORCA_LLM_MAX_RETRIES` | no | `2` |
| `ORCA_LLM_BASE_URL` | no | Self-hosted or proxy endpoints |
| `ORCA_RAG_EMBEDDING_MODEL` | yes (if RAG enabled) | Changing it requires re-embedding |
| `ORCA_RAG_EMBEDDING_DIM` | yes (if RAG enabled) | Must match the migration |
| `ORCA_RERANKER_MODEL` | no | RRF-only if absent, and the limitation is recorded |

> The provider and model identifiers are **configuration**. No provider name is hard-coded
> anywhere in ORCA (`24_ENGINEERING_DECISIONS.md` ADR-012).

### 3.4 External source credentials and endpoints

| Variable | Source | Required | Behaviour if absent |
|---|---|---|---|
| `ORCA_INCOIS_ERDDAP_BASE_URL` | S-01…S-04 | yes | Tool layer cannot function; startup warns |
| `ORCA_IMD_BASE_URL` | S-05 | no | Adapter disabled |
| `ORCA_IMD_API_KEY` | S-05 | no | **`AUTH_REQUIRED` degradation** (expected initial state) |
| `ORCA_INCOIS_WMS_BASE_URL` | S-06 | no | PFZ layer unavailable, reported |
| `ORCA_INCOIS_WMS_LAYERS` | S-06 | no | Layer names as configuration, not code |
| `ORCA_CMEMS_USERNAME` / `ORCA_CMEMS_PASSWORD` | S-07 | no | `AUTH_REQUIRED` for waves/currents |
| `ORCA_CMEMS_DATASET_MAP` | S-07 | no | Path to a variable→dataset mapping file |
| `ORCA_MARINEREGIONS_SNAPSHOT_VERSION` | S-08 | yes | Pinned boundary version |
| `ORCA_MOSDAC_USERNAME` / `ORCA_MOSDAC_PASSWORD` | S-09 | no | Enhancement disabled |
| `ORCA_NOAA_BASE_URL` | S-11 | no | Fallback disabled |
| `ORCA_ARGO_GDAC_BASE_URL` | S-12 | no | Fallback disabled |

**Endpoints are configuration, not code.** A provider changing a base path is a
configuration change plus an adapter test update — never a code change scattered across
the system.

### 3.5 Behaviour limits

| Variable | Default | Cross-reference |
|---|---|---|
| `ORCA_MAX_CONCURRENT_TOOLS` | `6` | `07` §14 |
| `ORCA_MAX_REPLANS` | `2` | `07` §14 |
| `ORCA_RUN_WALL_CLOCK_BUDGET_MS` | `30000` | `07` §14 |
| `ORCA_RUN_TOKEN_BUDGET` | env-specific | `07` §14 |
| `ORCA_MAX_BBOX_AREA_KM2` | `500000` | `14` §8 |
| `ORCA_MAX_TIME_WINDOW_DAYS` | `31` | `14` §8 |
| `ORCA_MAX_TOOL_CALLS_PER_RUN` | `15` | `14` §8 |
| `ORCA_HUMAN_REVIEW_TIMEOUT_S` | `1800` | `07` §9 |
| `ORCA_CACHE_DEFAULT_TTL_S` | `3600` | per-parameter override in `config/staleness.yaml` |

### 3.6 Security and auth

| Variable | Required | Notes |
|---|---|---|
| `ORCA_JWT_PUBLIC_KEY` / `ORCA_JWT_PRIVATE_KEY` | yes (non-local) | **secret**; asymmetric |
| `ORCA_JWT_ISSUER` / `ORCA_JWT_AUDIENCE` | yes (non-local) | |
| `ORCA_ACCESS_TOKEN_TTL_S` | no | `1800` |
| `ORCA_REFRESH_TOKEN_TTL_S` | no | `1209600` |
| `ORCA_OIDC_DISCOVERY_URL` | no | When delegating to an IdP |
| `ORCA_ALLOW_ANONYMOUS_DEMO` | no | `false`; `true` only in `demo` |
| `ORCA_RATE_LIMIT_QUERIES_PER_HOUR` | no | `20` |

### 3.7 Observability

| Variable | Required | Notes |
|---|---|---|
| `ORCA_OTEL_EXPORTER_OTLP_ENDPOINT` | no | Tracing disabled if unset |
| `ORCA_OTEL_SERVICE_NAME` | no | `orca-backend` |
| `ORCA_TRACE_SAMPLE_RATE` | no | `1.0` in dev, lower in production |
| `ORCA_METRICS_ENABLED` | no | `true` |
| `ORCA_AUDIT_HASH_CHAIN_ENABLED` | no | `true`; disabling requires an ADR |

---

## 4. Secrets Management

| Environment | Mechanism |
|---|---|
| `local` | `.env` (git-ignored), created from `.env.example`. **No production credentials, ever** |
| `dev` / `staging` | Orchestrator secrets (Docker/Kubernetes) or a cloud secrets manager |
| `demo` | Dedicated demo credentials, minimal scope, rotated after the event |
| `prod` | Cloud secrets manager with KMS-backed encryption, IAM-scoped, audited access |

**Rules**
- The secret set is enumerated in `deployment/secrets.md` (names and purposes only —
  never values).
- Each adapter can read only its own credential; there is no shared credential object.
- Rotation is documented per source; adapters reload credentials without a restart where
  the provider permits.
- A secret's **absence** is a first-class state that produces `AUTH_REQUIRED`, not a crash.
- Secret access failures are audited.
- `.env.example` lists every variable with a placeholder and a comment, and is the
  authoritative inventory for onboarding.

```bash
# .env.example  (extract)
ORCA_ENV=local
ORCA_DATABASE_URL=postgresql+psycopg://orca:orca@localhost:5432/orca
ORCA_REDIS_URL=redis://localhost:6379/0
ORCA_S3_ENDPOINT=http://localhost:9000
ORCA_S3_BUCKET=orca-local
ORCA_S3_ACCESS_KEY=CHANGE_ME
ORCA_S3_SECRET_KEY=CHANGE_ME

ORCA_LLM_PROVIDER=CHANGE_ME
ORCA_LLM_API_KEY=CHANGE_ME
ORCA_LLM_MODEL_PLANNER=CHANGE_ME

# INCOIS ERDDAP — VERIFIED, no authentication observed for the P0 datasets
ORCA_INCOIS_ERDDAP_BASE_URL=CHANGE_ME

# IMD — AUTH REQUIRED (unauthenticated requests returned HTTP 403).
# Leave unset until credentials are granted; tools will report AUTH_REQUIRED.
# ORCA_IMD_BASE_URL=
# ORCA_IMD_API_KEY=

# INCOIS GeoServer/WMS — PENDING VERIFICATION (host could not be resolved on the
# development network). Set only after verification from an unrestricted network.
# ORCA_INCOIS_WMS_BASE_URL=
# ORCA_INCOIS_WMS_LAYERS=

# CMEMS — AUTH REQUIRED
# ORCA_CMEMS_USERNAME=
# ORCA_CMEMS_PASSWORD=
```

---

## 5. Environment Modes

| Mode | Data sources | Auth | LLM | Fixtures | Purpose |
|---|---|---|---|---|---|
| `local` | Recorded fixtures by default; live ERDDAP opt-in | Dev tokens | Stub or real | Yes | Fast iteration without hitting public services |
| `dev` | Live where credentials exist | Real | Real | Fallback | Shared integration |
| `staging` | Live | Real | Real | No | Pre-demo verification |
| `demo` | Live where reliable + **labelled** pre-staged fallbacks | Anonymous read-only permitted | Real | Yes, labelled | Presentation |
| `prod` | Live | Real, MFA for privileged roles | Real | No | Hypothetical operational use |

**Local mode default is fixtures.** Every developer hammering public government services
during development is both slow and a poor use of public infrastructure; live access is an
explicit opt-in (`ORCA_LOCAL_USE_LIVE=true`).

**Demo mode invariant.** Any pre-staged fixture is surfaced with its capture time and a
"cached" label. A fixture without capture metadata fails a CI check
(`18_REPOSITORY_STRUCTURE.md` §6).

---

## 6. Policy Configuration Files

```yaml
# config/tools.yaml
environments:
  demo:
    enabled: [get_sst, get_chlorophyll, get_ocean_observations, get_maritime_boundaries,
              get_wave_conditions, get_currents, get_marine_warnings, get_pfz]
    disabled:
      get_lightning:     "IMD credentials not available — AUTH_REQUIRED demonstrated"
      get_cyclone_track: "IMD credentials not available"
agent_allow_lists:
  planner:        []                      # emits a plan; executes nothing
  data_discovery: ["*"]                   # every enabled P0 tool
  geospatial:     []                      # kernels only
  risk:           ["search_marine_knowledge"]   # P1, explanatory context only
  reporting:      ["translate_text"]            # P1
```

```yaml
# config/staleness.yaml   (initial engineering parameters)
parameters:
  significant_wave_height: {cadence: PT3H,  stale_after: PT9H,  expired_after: PT24H}
  wind_speed:              {cadence: PT1H,  stale_after: PT6H,  expired_after: PT12H}
  sst:                     {cadence: P1D,   stale_after: P3D,   expired_after: P7D}
  chlorophyll_a:           {cadence: P1D,   stale_after: P5D,   expired_after: P10D}
  pfz_advisory:            {cadence: P1D,   stale_after: P2D,   expired_after: P3D}
  marine_warning:          {cadence: PT3H,  stale_after: PT6H,  expired_after: validity_end}
```

```yaml
# config/tolerances.yaml   (SCIENTIFIC VALIDATION REQUIRED)
significant_wave_height: {absolute: 0.5, relative: 0.20, safety_relevant: true}
wind_speed:              {absolute: 3.0, relative: 0.20, safety_relevant: true}
sst:                     {absolute: 0.5, relative: 0.02, safety_relevant: false}
chlorophyll_a:           {relative: 0.50, safety_relevant: false, scale: log}
current_speed:           {absolute: 0.3, relative: 0.25, safety_relevant: true}
```

Threshold files are described in `12_RISK_AND_RECOMMENDATION_SPEC.md` §13. Every policy
file carries a `status` field so an unvalidated parameter set is visible in the answer.

---

## 7. Feature Flags

```yaml
# config/feature_flags.yaml
rag_enabled:              {default: false, demo: true}
multilingual_enabled:     {default: false, demo: true, languages: [en, ml]}
alerts_enabled:           {default: false, demo: true}
human_review_enabled:     {default: true}
route_advisory_enabled:   {default: false}          # P1
ecological_domain_enabled:{default: false}          # P1
mosdac_enabled:           {default: false}          # P1
voice_enabled:            {default: false}          # FUTURE
offline_replay_mode:      {default: false, demo: true}
anonymous_demo_access:    {default: false, demo: true}
```

| Rule | Detail |
|---|---|
| Default off | Every incomplete capability defaults to disabled |
| Structural effect | A disabled tool is absent from the registry, so the Planner cannot plan it — flags are not merely cosmetic |
| Runtime toggling | `admin` scope only; every change is audited |
| Flag removal | A flag whose feature is complete and stable is removed; permanent flags accumulate into a second configuration system |

---

## 8. Fallback Configuration

```yaml
# config/sources.yaml  (extract — policy only; endpoints live in env vars)
capabilities:
  get_sst:
    primary: S-02
    fallbacks: [S-07, S-11]
    fallback_on: [SOURCE_UNAVAILABLE, TIMEOUT, RATE_LIMITED]
    never_fallback_on: [AUTH_REQUIRED, INVALID_BBOX, INVALID_TIME_WINDOW]
  get_marine_warnings:
    primary: S-05
    fallbacks: []          # an official warning has no substitute
    note: "If unavailable, warning status is reported as unknown."
  get_wave_conditions:
    primary: S-07
    fallbacks: [S-11]
    note: "S-10 (INCOIS OSF/LAS) would be preferred as an Indian-authority primary,
           but no machine-readable interface was established during the audit."
```

**Rules.** A fallback chain is configuration, so a source becoming available (e.g. a
verified INCOIS OSF interface) is a configuration change plus an adapter, not an
architecture change. Every fallback use is recorded in provenance and stated in the answer.

---

## 9. Startup Validation

At boot, ORCA validates and logs (secrets redacted):

```
[startup] env=demo
[startup] database=ok  redis=ok  object_store=ok
[startup] llm_provider=configured  model_planner=<id>  temperature=0
[startup] sources:
          S-02 INCOIS ERDDAP    base_url=set     status=VERIFIED             enabled
          S-05 IMD              credentials=UNSET status=AUTH REQUIRED       degraded
          S-06 INCOIS WMS       base_url=UNSET    status=PENDING VERIFICATION disabled
          S-07 CMEMS            credentials=set   status=AUTH REQUIRED        enabled
          S-08 MarineRegions    snapshot=<version> status=CONFIRMED           enabled
[startup] tools enabled: 8/11   disabled: get_lightning, get_cyclone_track (no IMD creds)
[startup] thresholds: small_craft_v0.1 (SCIENTIFIC_VALIDATION_REQUIRED),
                      fishing_v0.1 (SCIENTIFIC_VALIDATION_REQUIRED)
[startup] flags: rag=on multilingual=on(en,ml) alerts=on review=on replay=on
```

**Fail fast** on: missing required infrastructure variables, a database schema version
mismatch, an embedding dimension mismatch, or an unparseable policy file.
**Warn and degrade** on: missing source credentials, an unconfigured optional source, an
absent reranker.

This banner is also the fastest honest answer to "what is actually working right now?" —
useful in development and on demo day.

---

## 10. Configuration Testing

| Test | Assertion |
|---|---|
| `.env.example` completeness | Every variable read by `settings.py` appears in the example file |
| Required-variable failure | Startup fails with a clear message when a required variable is absent in non-local mode |
| Credential absence | With IMD credentials unset, the service starts and `get_lightning` returns `AUTH_REQUIRED` |
| Secret redaction | Credential-shaped strings never appear in logs or in `/v1/health/config` |
| Flag structural effect | A disabled tool is absent from the Planner's registry |
| Policy validation | Malformed threshold/staleness/tolerance files fail startup |
| Environment isolation | Demo credentials cannot access production storage (deployment-level test) |
| TLS enforcement | `ORCA_S3_USE_TLS=false` is rejected outside `local` |
