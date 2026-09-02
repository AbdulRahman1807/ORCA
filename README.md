# ORCA — Ocean Reasoning & Collaborative Agents

**SIH26176 · ISRO · Software** — an integration and reasoning layer over authoritative
marine information systems (INCOIS, IMD, CMEMS, MarineRegions).

ORCA does **not** replace INCOIS/IMD/ISRO services. It cites them, integrates them,
reasons across them, and says plainly what it does not know.

## Status

Design documents 01–22 are complete (`0*.md`, `1*.md`, `2*.md`).
Implementation is at **Phase 1 — source adapters**.

| Component | State |
|---|---|
| Canonical schema (`schemas/`) | ✅ core types, provenance invariant, error taxonomy |
| INCOIS ERDDAP adapter (`adapters/incois_erddap/`) | ✅ live, verified |
| Capability tools | ✅ `get_ocean_observations`, `get_sst`, `get_chlorophyll` |
| Vertical-slice CLI | ✅ runnable |
| Other adapters (IMD, CMEMS, WMS, MarineRegions) | ⬜ not started |
| Agents, LangGraph, API, frontend | ⬜ not started |

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
3. Surfaces staleness, spatial mismatch and missing capabilities instead of hiding them.
4. Keeps SAFETY and FISHING_SUITABILITY separate, and **refuses to issue either verdict**
   when the required evidence is absent.

## Verified data reality (2026-09-02)

Live testing confirmed ERDDAP **access** but corrected the **currency** of its data:
most datasets are historical archives. Only the Argo analysis products
(`incois_argo_10d_VAM`, ends 2026-07-30) carry recent data, and they are 10-day
subsurface means. There is **no current chlorophyll or SST** source on this server.

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
