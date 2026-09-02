"""Dataset metadata capture and validation for INCOIS ERDDAP.

Units, resolutions and coordinate conventions are READ from the server, never
assumed (04_ORCA_TOOL_CONTRACTS.md section 2.6). This module also runs sanity
checks that catch datasets whose published axes are unusable.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ...schemas.errors import ErrorCode
from .client import ErddapClient, ErddapError

_NVALUES = re.compile(r"nValues=(\d+)")
_SPACING = re.compile(r"averageSpacing=([\d.]+)")
_EVEN = re.compile(r"evenlySpaced=(\w+)")


@dataclass(slots=True)
class AxisMeta:
    name: str
    n_values: int | None = None
    average_spacing: str | None = None
    evenly_spaced: bool | None = None
    units: str | None = None


@dataclass(slots=True)
class VariableMeta:
    name: str
    dtype: str | None = None
    units: str | None = None
    long_name: str | None = None
    fill_value: float | None = None
    standard_name: str | None = None


@dataclass(slots=True)
class DatasetMeta:
    dataset_id: str
    title: str | None = None
    institution: str | None = None
    dim_order: list[str] = field(default_factory=list)
    axes: dict[str, AxisMeta] = field(default_factory=dict)
    variables: dict[str, VariableMeta] = field(default_factory=dict)
    time_coverage_start: str | None = None
    time_coverage_end: str | None = None
    lat_min: float | None = None
    lat_max: float | None = None
    lon_min: float | None = None
    lon_max: float | None = None
    lat_resolution: str | None = None
    lon_resolution: str | None = None
    issues: list[str] = field(default_factory=list)
    usable: bool = True
    captured_at: str = ""

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["axes"] = {k: asdict(v) for k, v in self.axes.items()}
        d["variables"] = {k: asdict(v) for k, v in self.variables.items()}
        return d

    @property
    def coverage_end_dt(self) -> datetime | None:
        if not self.time_coverage_end:
            return None
        return datetime.fromisoformat(self.time_coverage_end.replace("Z", "+00:00"))

    def days_behind(self, now: datetime | None = None) -> float | None:
        end = self.coverage_end_dt
        if end is None:
            return None
        return ((now or datetime.now(timezone.utc)) - end).total_seconds() / 86400.0


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_info(dataset_id: str, payload: dict[str, Any]) -> DatasetMeta:
    t = payload["table"]
    ix = {c: i for i, c in enumerate(t["columnNames"])}
    meta = DatasetMeta(dataset_id=dataset_id,
                       captured_at=datetime.now(timezone.utc).isoformat())

    for row in t["rows"]:
        rtype = row[ix["Row Type"]]
        var = row[ix["Variable Name"]]
        attr = row[ix["Attribute Name"]]
        val = row[ix["Value"]]

        if rtype == "dimension":
            meta.dim_order.append(var)
            nv = _NVALUES.search(val or "")
            sp = _SPACING.search(val or "")
            ev = _EVEN.search(val or "")
            meta.axes[var] = AxisMeta(
                name=var,
                n_values=int(nv.group(1)) if nv else None,
                average_spacing=sp.group(1) if sp else None,
                evenly_spaced=(ev.group(1) == "true") if ev else None,
            )
        elif rtype == "variable" and var != "NC_GLOBAL":
            meta.variables[var] = VariableMeta(name=var, dtype=row[ix["Data Type"]])
        elif rtype == "attribute":
            if var == "NC_GLOBAL":
                match attr:
                    case "title": meta.title = val
                    case "institution": meta.institution = val
                    case "time_coverage_start": meta.time_coverage_start = val
                    case "time_coverage_end": meta.time_coverage_end = val
                    case "geospatial_lat_min": meta.lat_min = _f(val)
                    case "geospatial_lat_max": meta.lat_max = _f(val)
                    case "geospatial_lon_min": meta.lon_min = _f(val)
                    case "geospatial_lon_max": meta.lon_max = _f(val)
                    case "geospatial_lat_resolution": meta.lat_resolution = val
                    case "geospatial_lon_resolution": meta.lon_resolution = val
            elif var in meta.variables:
                v = meta.variables[var]
                match attr:
                    case "units": v.units = val
                    case "long_name": v.long_name = val
                    case "standard_name": v.standard_name = val
                    case "_FillValue": v.fill_value = _f(val)
            elif var in meta.axes and attr == "units":
                meta.axes[var].units = val

    _validate(meta)
    return meta


def _validate(meta: DatasetMeta) -> None:
    """Sanity checks. A dataset that fails these is marked unusable, not guessed at."""
    if meta.lat_min is not None and not (-90.0 <= meta.lat_min <= 90.0):
        meta.issues.append(
            f"latitude axis is not in degrees (geospatial_lat_min={meta.lat_min}); "
            f"the axis appears to publish array indices"
        )
    if meta.lat_max is not None and not (-90.0 <= meta.lat_max <= 90.0):
        meta.issues.append(
            f"latitude axis is not in degrees (geospatial_lat_max={meta.lat_max}); "
            f"the axis appears to publish array indices"
        )
    if meta.lon_min is not None and not (-180.0 <= meta.lon_min <= 360.0):
        meta.issues.append(f"longitude axis out of range (min={meta.lon_min})")
    for v in meta.variables.values():
        if v.units is None:
            meta.issues.append(f"variable {v.name!r} publishes no units")
    if not meta.time_coverage_end:
        meta.issues.append("no time_coverage_end published")
    meta.usable = not any("axis is not in degrees" in i for i in meta.issues)


def fetch_dataset_ids(client: ErddapClient) -> list[str]:
    r = client.get_json("info/index.json", "page=1&itemsPerPage=1000")
    t = r.payload["table"]
    i = t["columnNames"].index("Dataset ID")
    return [row[i] for row in t["rows"] if row[i] != "allDatasets"]


def fetch_dataset_meta(client: ErddapClient, dataset_id: str) -> DatasetMeta:
    r = client.get_json(f"info/{dataset_id}/index.json")
    return parse_info(dataset_id, r.payload)


def capture_all(client: ErddapClient) -> dict[str, DatasetMeta]:
    out: dict[str, DatasetMeta] = {}
    for ds in fetch_dataset_ids(client):
        try:
            out[ds] = fetch_dataset_meta(client, ds)
        except ErddapError as exc:
            m = DatasetMeta(dataset_id=ds, usable=False,
                            captured_at=datetime.now(timezone.utc).isoformat())
            m.issues.append(f"metadata capture failed: {exc.code.value}")
            out[ds] = m
    return out
