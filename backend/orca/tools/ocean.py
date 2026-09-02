"""Ocean-variable capability tools backed by INCOIS ERDDAP.

Implements the P0 contracts get_ocean_observations, get_sst and get_chlorophyll
(04_ORCA_TOOL_CONTRACTS.md sections 3.6, 3.7, 3.10).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from ..adapters.incois_erddap.adapter import IncoisErddapAdapter
from ..adapters.incois_erddap.client import ErddapError
from ..schemas.enums import EnvelopeStatus
from ..schemas.envelope import OrcaEnvelope
from ..schemas.errors import ErrorCode, OrcaError
from .base import ToolInputError, ToolRun, validate_point

PRIMARY_SOURCE = "S-01..S-04"


def _collect(tool: str, parameters: Sequence[str], lat: float, lon: float,
             valid_time: datetime, adapter: IncoisErddapAdapter,
             depth_m: float | None = None) -> OrcaEnvelope:
    run = ToolRun(tool, primary_source=PRIMARY_SOURCE)
    try:
        validate_point(lat, lon)
    except ToolInputError as exc:
        return run.failure(exc.code, exc.detail)

    data: list[Any] = []
    provenance: list[Any] = []
    errors: list[OrcaError] = []
    notes: list[dict[str, Any]] = []
    satisfied = 0

    for param in parameters:
        try:
            res = adapter.fetch_point(param, lat, lon, valid_time, depth_m=depth_m)
        except ErddapError as exc:
            run.attempt(PRIMARY_SOURCE, exc.code.value, exc.detail[:160])
            errors.append(OrcaError(code=exc.code, subject=param, tool=tool,
                                    detail=exc.detail[:300], source_id=PRIMARY_SOURCE,
                                    severity="warning"))
            continue

        satisfied += 1
        data.extend(res.observations)
        provenance.extend(res.provenance)
        run.attempt(PRIMARY_SOURCE, "success", f"{param} via {res.dataset_id}")
        for code in res.codes:
            errors.append(OrcaError(
                code=code, subject=param, tool=tool, source_id=PRIMARY_SOURCE,
                severity="warning",
                detail=f"{param} served from {res.dataset_id}"))
        for n in res.notes:
            notes.append({"code": "SOURCE_NOTE", "subject": param, "detail": n})

    if satisfied:
        run.resolved(PRIMARY_SOURCE)

    if satisfied == 0:
        # Every requested parameter failed. Prefer the most specific code.
        codes = {e.code for e in errors}
        code = (ErrorCode.DATASET_UNAVAILABLE if ErrorCode.DATASET_UNAVAILABLE in codes
                else ErrorCode.NO_DATA if ErrorCode.NO_DATA in codes
                else ErrorCode.SOURCE_UNAVAILABLE)
        env = run.failure(code, f"no data for {list(parameters)} at {lat},{lon}")
        env.errors.extend(errors)
        return env

    degraded = any(e.code in (ErrorCode.STALE_DATA, ErrorCode.INSUFFICIENT_COVERAGE)
                   for e in errors) or satisfied < len(parameters)
    status = EnvelopeStatus.PARTIAL if degraded else EnvelopeStatus.SUCCESS

    return run.envelope(
        status, data=data, provenance=provenance, errors=errors, warnings=notes,
        quality={"parameters_requested": len(parameters),
                 "parameters_satisfied": satisfied},
    )


def get_ocean_observations(lat: float, lon: float, valid_time: datetime, *,
                           variables: Sequence[str] = ("temperature", "salinity"),
                           depth_m: float | None = 5.0,
                           adapter: IncoisErddapAdapter | None = None) -> OrcaEnvelope:
    """P0. Oceanographic observations/analysis fields for multi-variable reasoning."""
    own = adapter is None
    adapter = adapter or IncoisErddapAdapter()
    try:
        return _collect("get_ocean_observations", variables, lat, lon,
                        valid_time, adapter, depth_m)
    finally:
        if own:
            adapter.close()


def get_sst(lat: float, lon: float, valid_time: datetime, *,
            include_anomaly: bool = True,
            adapter: IncoisErddapAdapter | None = None) -> OrcaEnvelope:
    """P0. Sea-surface temperature.

    NOTE (verified 2026-09-02): the only INCOIS ERDDAP SST datasets currently
    loaded are archives ending 2011-10-04. `NOAA_AVHRR_datasets`, which carried
    data to 2026-08-11, publishes a latitude axis in array indices rather than
    degrees AND dropped out of the server catalogue during testing. This tool
    therefore returns archive data flagged STALE_DATA rather than substituting a
    near-surface Argo temperature, which would be a different parameter.
    """
    params = ["sst", "sst_anomaly"] if include_anomaly else ["sst"]
    own = adapter is None
    adapter = adapter or IncoisErddapAdapter()
    try:
        return _collect("get_sst", params, lat, lon, valid_time, adapter, None)
    finally:
        if own:
            adapter.close()


def get_chlorophyll(lat: float, lon: float, valid_time: datetime, *,
                    variables: Sequence[str] = ("chlorophyll_a",),
                    adapter: IncoisErddapAdapter | None = None) -> OrcaEnvelope:
    """P0. Chlorophyll-a for productivity reasoning.

    NOTE (verified 2026-09-02): `incois_oceansat2_datasets` coverage ends
    2020-05-01 and `IRS_chlorophyll_datasets` ends 2006-03-21. No current
    chlorophyll source exists on this ERDDAP; results are archive data flagged
    STALE_DATA and must not drive a present-day suitability verdict.
    """
    own = adapter is None
    adapter = adapter or IncoisErddapAdapter()
    try:
        return _collect("get_chlorophyll", variables, lat, lon, valid_time,
                        adapter, None)
    finally:
        if own:
            adapter.close()
