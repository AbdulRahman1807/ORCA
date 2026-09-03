"""Gridded fields for map rendering.

A capability tool like any other: agents and the API ask for a field by
canonical name and never learn which provider serves it.

The one rule that matters here is that **a masked cell reaches the client as
`null`**, never as zero. A land-masked wave cell or a cloud-masked chlorophyll
cell drawn as 0.0 would paint a calm, empty sea over missing data -- F-10 and
D-3 restated in pixels. The response reports how many cells are valid so a
renderer can say "partial coverage" rather than implying a complete picture.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np

#: Canonical field name -> what it is and where it comes from.
FIELDS: dict[str, dict[str, Any]] = {
    "wind": {"kind": "vector", "source": "gfs", "unit": "m s-1",
             "components": ("eastward_wind", "northward_wind"),
             "label": "Wind at 10 m"},
    "current": {"kind": "vector", "source": "cmems", "unit": "m s-1",
                "components": ("current_u", "current_v"),
                "label": "Surface current"},
    "chlorophyll": {"kind": "scalar", "source": "cmems", "unit": "mg m-3",
                    "parameter": "chlorophyll_a", "label": "Chlorophyll-a"},
    "sst": {"kind": "scalar", "source": "cmems", "unit": "degC",
            "parameter": "sst", "label": "Sea surface temperature"},
    "waves": {"kind": "scalar", "source": "cmems", "unit": "m",
              "parameter": "significant_wave_height",
              "label": "Significant wave height"},
}


class FieldError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _clean(a: np.ndarray) -> list:
    """NaN -> None. A hole must stay a hole all the way to the canvas."""
    return [[None if (v is None or (isinstance(v, float) and math.isnan(v)))
             else round(float(v), 4) for v in row] for row in np.atleast_2d(a)]


def get_field(name: str, lat: float, lon: float, valid_time: datetime, *,
              radius_km: float = 300.0, cmems=None, gfs=None) -> dict:
    spec = FIELDS.get(name)
    if spec is None:
        raise FieldError("DATASET_UNAVAILABLE",
                         f"no field named {name!r}; known: {sorted(FIELDS)}")

    if spec["source"] == "gfs":
        if gfs is None:
            raise FieldError("DATASET_UNAVAILABLE", "no GFS adapter supplied")
        lats, lons, blocks, actual = gfs.fetch_grid(
            list(spec["components"]), lat, lon, valid_time, radius_km=radius_km)
        u = np.asarray(blocks[spec["components"][0]], dtype="f8")
        v = np.asarray(blocks[spec["components"][1]], dtype="f8")
        source, source_id = "NOAA NCEP GFS", "S-11"
        dataset = "ncep_global"
    else:
        if cmems is None:
            raise FieldError("DATASET_UNAVAILABLE", "no CMEMS adapter supplied")
        if spec["kind"] == "vector":
            la, lo, ub, binding, actual = cmems.fetch_grid(
                spec["components"][0], lat, lon, valid_time, radius_km=radius_km)
            _, _, vb, _, _ = cmems.fetch_grid(
                spec["components"][1], lat, lon, valid_time, radius_km=radius_km)
            lats, lons, u, v = list(la), list(lo), np.asarray(ub), np.asarray(vb)
            dataset = binding.dataset_id
        else:
            la, lo, block, binding, actual = cmems.fetch_grid(
                spec["parameter"], lat, lon, valid_time, radius_km=radius_km)
            lats, lons, u, v = list(la), list(lo), np.asarray(block), None
            dataset = binding.dataset_id
        source, source_id = "CMEMS", "S-07"

    primary = u if v is None else np.sqrt(u ** 2 + v ** 2)
    valid = int(np.sum(~np.isnan(primary)))
    if valid == 0:
        raise FieldError("NO_DATA", f"{name}: no valid cells in this area")

    out: dict[str, Any] = {
        "field": name,
        "label": spec["label"],
        "kind": spec["kind"],
        "unit": spec["unit"],
        "lats": [round(float(x), 4) for x in lats],
        "lons": [round(float(x), 4) for x in lons],
        "valid_time": actual.isoformat(),
        "source": source,
        "source_id": source_id,
        "dataset": dataset,
        # A renderer must be able to say "partial coverage" rather than imply a
        # complete picture; masked cells are null, never zero.
        "cells": {"total": int(primary.size), "valid": valid,
                  "coverage": round(valid / primary.size, 3)},
        "range": {"min": round(float(np.nanmin(primary)), 4),
                  "max": round(float(np.nanmax(primary)), 4)},
        "advisory_only": True,
    }
    if spec["kind"] == "vector":
        out["u"] = _clean(u)
        out["v"] = _clean(v)
        out["speed"] = _clean(primary)
    else:
        out["values"] = _clean(u)
    return out
