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
from .base import collect_point_parameters

PRIMARY_SOURCE = "S-01..S-04"


def _collect(tool: str, parameters: Sequence[str], lat: float, lon: float,
             valid_time: datetime, adapter: IncoisErddapAdapter,
             depth_m: float | None = None) -> OrcaEnvelope:
    return collect_point_parameters(
        tool, parameters, lat, lon, valid_time,
        lambda p: adapter.fetch_point(p, lat, lon, valid_time, depth_m=depth_m),
        PRIMARY_SOURCE)


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
