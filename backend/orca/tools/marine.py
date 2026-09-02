"""Wave and current capability tools, backed by CMEMS.

Implements the P0 contracts get_wave_conditions and get_currents
(04_ORCA_TOOL_CONTRACTS.md sections 3.8, 3.9).
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from ..adapters.cmems.adapter import CmemsAdapter
from ..adapters.cmems.client import SOURCE_ID
from ..schemas.envelope import OrcaEnvelope
from .base import collect_point_parameters

WAVE_VARIABLES = ("significant_wave_height", "peak_period", "swell_height",
                  "swell_period", "mean_wave_direction")
CURRENT_VARIABLES = ("current_u", "current_v")


def get_wave_conditions(lat: float, lon: float, valid_time: datetime, *,
                        variables: Sequence[str] = WAVE_VARIABLES,
                        adapter: CmemsAdapter | None = None) -> OrcaEnvelope:
    """P0. Wave and swell conditions for marine safety reasoning.

    Note: no other variable may substitute for wave height. If this tool cannot
    answer, the safety assessment records wave conditions as not evaluated and
    issues no safety verdict.
    """
    own = adapter is None
    adapter = adapter or CmemsAdapter()
    try:
        return collect_point_parameters(
            "get_wave_conditions", variables, lat, lon, valid_time,
            lambda p: adapter.fetch_point(p, lat, lon, valid_time), SOURCE_ID)
    finally:
        if own:
            adapter.close()


def get_currents(lat: float, lon: float, valid_time: datetime, *,
                 variables: Sequence[str] = CURRENT_VARIABLES,
                 adapter: CmemsAdapter | None = None) -> OrcaEnvelope:
    """P0. Surface current velocity components.

    Speed and direction are DERIVED by the geospatial kernel, not by the
    adapter, so the derivation is traceable.
    """
    own = adapter is None
    adapter = adapter or CmemsAdapter()
    try:
        return collect_point_parameters(
            "get_currents", variables, lat, lon, valid_time,
            lambda p: adapter.fetch_point(p, lat, lon, valid_time), SOURCE_ID)
    finally:
        if own:
            adapter.close()
