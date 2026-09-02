"""Composition root for the live capability registry.

This is the ONE place that knows which adapter serves which capability. It is in
`tools/` because `tools/` is permitted to import `adapters/`; `agents/` and
`graph/` receive the bound registry and never learn what is behind it
(18_REPOSITORY_STRUCTURE.md section 1).

Capabilities with no source in this environment are registered as UNAVAILABLE
rather than omitted, so the Planner still plans for them and the answer states
what it could not check.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .boundaries import get_maritime_boundaries
from .marine import get_currents, get_wave_conditions, get_weather
from .ocean import get_chlorophyll, get_ocean_observations, get_sst
from .registry import ToolRegistry

#: Capabilities whose source is not yet reachable, and why. Each becomes a
#: declared gap in every answer (03_DATA_SOURCE_MATRIX.md section 7).
UNAVAILABLE: dict[str, str] = {
    "get_marine_warnings": "IMD credentials not granted",
    "get_lightning": "IMD credentials not granted",
    "get_cyclone_track": "IMD credentials not granted",
    "get_pfz": "INCOIS WMS pending network-independent verification",
}


def _when(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def build_live_registry(*, erddap, cmems, boundaries) -> ToolRegistry:
    """Bind already-constructed adapters into a registry.

    Adapters are passed in rather than created here so their lifetime stays with
    the caller's `with` block -- a tool must not close a connection its caller
    is still using.
    """
    r = ToolRegistry()

    r.bind("get_wave_conditions",
           lambda lat, lon, valid_time, **_:
               get_wave_conditions(lat, lon, _when(valid_time), adapter=cmems))
    r.bind("get_currents",
           lambda lat, lon, valid_time, **_:
               get_currents(lat, lon, _when(valid_time), adapter=cmems))
    r.bind("get_weather",
           lambda lat, lon, valid_time, **_:
               get_weather(lat, lon, _when(valid_time), adapter=cmems))
    r.bind("get_ocean_observations",
           lambda lat, lon, valid_time, **_:
               get_ocean_observations(lat, lon, _when(valid_time), adapter=erddap))
    r.bind("get_sst",
           lambda lat, lon, valid_time, **_:
               get_sst(lat, lon, _when(valid_time), adapter=erddap, cmems=cmems))
    r.bind("get_chlorophyll",
           lambda lat, lon, valid_time, **_:
               get_chlorophyll(lat, lon, _when(valid_time), adapter=erddap,
                               cmems=cmems))
    r.bind("get_maritime_boundaries",
           lambda lat, lon, **_: get_maritime_boundaries(lat, lon,
                                                         adapter=boundaries))

    for name, reason in UNAVAILABLE.items():
        r.mark_unavailable(name, reason)
    return r
