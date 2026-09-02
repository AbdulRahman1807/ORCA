# ORCA — Ocean Reasoning & Collaborative Agents

**SIH26176 · ISRO · Software** — an integration and reasoning layer over authoritative
marine information systems (INCOIS, IMD, CMEMS, MarineRegions).

ORCA does **not** replace INCOIS/IMD/ISRO services. It cites them, integrates them,
reasons across them, and says plainly what it does not know.

## Status

Design documents 01–22 are complete (`0*.md`, `1*.md`, `2*.md`).
Implementation is at **Phase 1–6 partial — ~40% of backend logic**.

| Component | State |
|---|---|
| Canonical schema (`schemas/`) | ✅ provenance invariant, error taxonomy, assessment types |
| INCOIS ERDDAP adapter (`adapters/incois_erddap/`) | ✅ live, verified |
| CMEMS adapter (`adapters/cmems/`) | ✅ live — waves, currents, wind via ARCO/Zarr |
| Capability tools (`tools/`) | ✅ 6 of 11 P0 |
| Geospatial kernel (`geospatial/`) | ◐ geodesy, temporal alignment, derivations |
| Assessment engine (`assessment/`) | ✅ thresholds, sufficiency, verdicts, confidence, synthesis |
| Vertical-slice CLI (`cli/`) | ✅ runnable |
| Other adapters (IMD, WMS, MarineRegions) | ⬜ not started |
| Agents, LangGraph, RAG, API, frontend | ⬜ not started |

## Quick start

```bash
python3 -m venv .venv && ./.venv/bin/pip install pydantic httpx certifi truststore pytest
./.venv/bin/python -m pytest tests -q            # 24 offline tests
./.venv/bin/python scripts/capture_datasets.py   # live metadata capture
./.venv/bin/python -m backend.orca.cli.query     # the vertical slice
```

`orca-query` accepts `--lat --lon --label --when`.

## What the slice currently does

1. Queries live INCOIS ERDDAP for temperature, salinity, SST and chlorophyll near a point.
2. Normalises every value into the canonical schema with full provenance — source,
   dataset, published unit, validity time, retrieval time, grid resolution, nearest-node
   distance and valid-cell coverage.
3. Filters evidence by **representativeness**: a 10-day subsurface analysis is refused as
   safety evidence, and archive data is refused for a present-day window.
4. Assesses SAFETY and FISHING_SUITABILITY **independently** against versioned threshold
   sets, applying worst-factor-governs (never averaging), and refuses to issue a verdict
   when a required input is missing.
5. Synthesises a headline that names the limiting factor across domains.

An official marine warning, when present, overrides ORCA's own thresholds — ORCA conveys
and contextualises the authority rather than competing with it.

```bash
# refuses: no wave/wind/warning source for a present-day window
./.venv/bin/python -m backend.orca.cli.query

# produces a real verdict: archive date with genuine SST coverage
./.venv/bin/python -m backend.orca.cli.query --when 2011-06-15T00:30:00
```

## Verified data reality (2026-09-02)

**INCOIS ERDDAP** — access confirmed, but most datasets are historical archives. Only
the Argo analysis products (`incois_argo_10d_VAM`, ends 2026-07-30) carry recent data,
and they are 10-day subsurface means. There is **no current chlorophyll or SST** here.

**CMEMS** — the audit recorded this as AUTH REQUIRED. The ARCO (Zarr) store in fact
served wave and current data **without credentials**, and those products are forecasts
covering tomorrow. This is the first source able to answer a question about the future.
Wind is available too, but as an observation product with no forecast horizon.

Full results, including the incomplete TLS chain, the dataset with a latitude axis in
array indices, and the dataset that vanished mid-session:
[`03_DATA_SOURCE_MATRIX.md` §14](03_DATA_SOURCE_MATRIX.md).

## Layering rule

```
agents/  →  tools/  →  adapters/  →  external source
```

Only `adapters/` knows URLs, credentials and provider query syntax. Agents see capability
contracts and canonical objects, never a provider API.

## Documents

`01_MASTER_PROJECT_SPEC.md` · `02_FRONTEND_DESIGN_SPEC.md` · `03_DATA_SOURCE_MATRIX.md` ·
`04_ORCA_TOOL_CONTRACTS.md` · `05_CANONICAL_DATA_SCHEMA.md` · `06_AGENT_SPEC.md` ·
`07_LANGGRAPH_WORKFLOW_SPEC.md` · `08_API_SPEC.md` · `09_DATABASE_SPEC.md` ·
`10_RAG_SPEC.md` · `11_GEOSPATIAL_REASONING_SPEC.md` ·
`12_RISK_AND_RECOMMENDATION_SPEC.md` · `13_MULTILINGUAL_AND_ALERTING_SPEC.md` ·
`14_SECURITY_PRIVACY_AND_GOVERNANCE.md` · `15_EVALUATION_AND_TESTING_SPEC.md` ·
`16_DEMO_AND_SIH_PRESENTATION_SPEC.md` · `17_IMPLEMENTATION_ROADMAP.md` ·
`18_REPOSITORY_STRUCTURE.md` · `19_ENVIRONMENT_AND_CONFIGURATION_SPEC.md` ·
`20_OBSERVABILITY_AND_AUDIT_SPEC.md` · `21_RISK_REGISTER.md` · `22_MVP_SCOPE.md`

Not yet written: 23–30 (diagrams, ADRs, gap register, judge Q&A, traceability, glossary,
quickstart, definition of done).

**ORCA output is not an official advisory. Follow IMD and INCOIS bulletins.**
