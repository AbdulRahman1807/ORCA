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
from .pfz import get_pfz
from .ocean import get_chlorophyll, get_ocean_observations, get_sst
from .registry import ToolRegistry

#: Capabilities whose source is not yet reachable, and why. Each becomes a
#: declared gap in every answer (03_DATA_SOURCE_MATRIX.md section 7).
UNAVAILABLE: dict[str, str] = {
    "get_marine_warnings": "IMD credentials not granted",
    "get_lightning": "IMD credentials not granted",
    "get_cyclone_track": "IMD credentials not granted",
    #: get_pfz is bound when an INCOIS WMS adapter is supplied; without one it
    #: is declared unavailable rather than omitted.
    "get_pfz": "INCOIS GeoServer adapter not supplied",
    #: Investigated 2026-09-03, no reachable source (F-31):
    #: UHSLC fast-delivery gauges are ~1 month behind, CMEMS publishes a tide
    #: product for the Arctic only, and the INCOIS TideGauges layer carries
    #: station LOCATIONS, not levels. ORCA will not compute a tide prediction
    #: of its own -- that would be an authoritative-looking invented number.
    #: NOTE: tidal CURRENTS are already covered, because the CMEMS total-current
    #: product includes the tidal component.
    "get_tides": ("no reachable tide-prediction source; UHSLC gauge data is "
                  "~1 month behind and CMEMS covers the Arctic only"),
}


def _when(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def build_live_registry(*, erddap, cmems, boundaries, gfs=None,
                        pfz=None) -> ToolRegistry:
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
               get_weather(lat, lon, _when(valid_time), adapter=cmems, gfs=gfs))
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
    if pfz is not None:
        r.bind("get_pfz",
               lambda lat, lon, valid_time=None, **_:
                   get_pfz(lat, lon, _when(valid_time) if valid_time else None,
                           adapter=pfz))
    r.bind("get_maritime_boundaries",
           lambda lat, lon, **_: get_maritime_boundaries(lat, lon,
                                                         adapter=boundaries))

    for name, reason in UNAVAILABLE.items():
        if not r.is_available(name):
            r.mark_unavailable(name, reason)
    return r
