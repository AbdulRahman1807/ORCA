"""INCOIS ERDDAP source adapter.

Turns provider responses into canonical ORCA objects with full provenance.
Nothing above this layer knows that ERDDAP exists.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ...schemas.core import (
    Provenance, QualityMetadata, SpatialRef, TemporalRef, haversine_km, utcnow,
)
from ...schemas.data import Observation
from ...schemas.enums import Freshness, QualityFlag, ValueKind
from ...schemas.errors import ErrorCode
from .bindings import BINDINGS, Binding, canonical_unit
from .client import ORGANISATION, SOURCE_NAME, ErddapClient, ErddapError
from .metadata import DatasetMeta, fetch_dataset_meta

log = logging.getLogger("orca.adapters.incois_erddap")

SOURCE_ID = "S-01..S-04"
ACCESS_METHOD = "ERDDAP griddap"

#: Freshness thresholds are expressed as multiples of the product's own cadence,
#: so a monthly product is not called "stale" for being three weeks old.
_CADENCE_DAYS = {
    "10day_mean": 10.0, "monthly_mean": 30.0, "daily_composite": 1.0,
    "3day_mean": 3.0, "weekly_mean": 7.0, "instantaneous": 0.25,
}


class DatasetNotUsable(ErddapError):
    def __init__(self, dataset_id: str, issues: list[str]):
        super().__init__(
            ErrorCode.DATASET_UNAVAILABLE,
            f"{dataset_id} failed metadata validation: {'; '.join(issues)}",
        )


@dataclass(slots=True)
class PointResult:
    observations: list[Observation]
    provenance: list[Provenance]
    codes: list[ErrorCode]
    notes: list[str]
    dataset_id: str | None = None


class IncoisErddapAdapter:
    def __init__(self, client: ErddapClient | None = None):
        self._client = client or ErddapClient()
        self._owns_client = client is None
        self._meta_cache: dict[str, DatasetMeta] = {}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "IncoisErddapAdapter":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- metadata --------------------------------------------------------------

    def meta(self, dataset_id: str) -> DatasetMeta:
        if dataset_id not in self._meta_cache:
            m = fetch_dataset_meta(self._client, dataset_id)
            if not m.usable:
                raise DatasetNotUsable(dataset_id, m.issues)
            self._meta_cache[dataset_id] = m
        return self._meta_cache[dataset_id]

    # -- query construction ----------------------------------------------------

    @staticmethod
    def _axis_spacing(meta: DatasetMeta, axis: str, default: float) -> float:
        a = meta.axes.get(axis)
        try:
            return float(a.average_spacing) if a and a.average_spacing else default
        except ValueError:
            return default

    def _build_selector(self, meta: DatasetMeta, binding: Binding, *,
                        time_expr: str, lat_lo: float, lat_hi: float,
                        lon_lo: float, lon_hi: float,
                        depth_expr: str) -> str:
        """Assemble a griddap selector honouring the dataset's own dimension order."""
        parts: list[str] = []
        for dim in meta.dim_order:
            low = dim.lower()
            if low == "time":
                parts.append(f"[{time_expr}]")
            elif low in ("zax", "depth", "zlev"):
                parts.append(f"[{depth_expr}]")
            elif low.startswith("lat"):
                parts.append(f"[({lat_lo}):({lat_hi})]")
            elif low.startswith("lon"):
                parts.append(f"[({lon_lo}):({lon_hi})]")
            else:
                parts.append("[0:0]")  # unknown singleton axis
        return binding.variable + "".join(parts)

    # -- public API ------------------------------------------------------------

    def fetch_point(self, parameter: str, lat: float, lon: float,
                    valid_time: datetime, *, depth_m: float | None = None,
                    search_radius_deg: float | None = None) -> PointResult:
        """Nearest-node value for a canonical parameter at a point and time."""
        bindings = BINDINGS.get(parameter)
        if not bindings:
            raise ErddapError(ErrorCode.DATASET_UNAVAILABLE,
                              f"no INCOIS ERDDAP binding for parameter {parameter!r}")

        codes: list[ErrorCode] = []
        notes: list[str] = []
        last_err: ErddapError | None = None

        for binding in bindings:
            try:
                return self._fetch_one(binding, lat, lon, valid_time,
                                       depth_m, search_radius_deg, codes, notes)
            except ErddapError as exc:
                last_err = exc
                notes.append(f"{binding.dataset_id}: {exc.code.value}")
                # Try the next dataset for the SAME parameter. This is a dataset
                # fallback within one source -- never a parameter substitution.
                continue

        raise last_err or ErddapError(ErrorCode.NO_DATA, "no binding produced data")

    def _fetch_one(self, binding: Binding, lat: float, lon: float,
                   valid_time: datetime, depth_m: float | None,
                   search_radius_deg: float | None,
                   codes: list[ErrorCode], notes: list[str]) -> PointResult:
        meta = self.meta(binding.dataset_id)

        # -- time: never extrapolate. If the request is beyond coverage we take
        #    the latest available slice and say so with STALE_DATA.
        end = meta.coverage_end_dt
        requested = valid_time
        stale = False
        if end is not None and valid_time > end:
            stale = True
            time_expr = "last"
            notes.append(
                f"{binding.dataset_id} coverage ends {end.date()}; requested "
                f"{valid_time.date()} -- using latest available slice"
            )
        else:
            time_expr = f"({valid_time.strftime('%Y-%m-%dT%H:%M:%SZ')})"

        # -- space: pad by one grid cell so an off-node request still resolves
        lat_sp = self._axis_spacing(meta, self._axis_named(meta, "lat"), 1.0)
        lon_sp = self._axis_spacing(meta, self._axis_named(meta, "lon"), 1.0)
        pad_lat = search_radius_deg or max(lat_sp, 0.25) * 1.5
        pad_lon = search_radius_deg or max(lon_sp, 0.25) * 1.5

        depth_expr = "[0:0]"
        if binding.depth_axis:
            depth_expr = "0:0" if depth_m is None else f"({depth_m})"
        selector = self._build_selector(
            meta, binding,
            time_expr=time_expr,
            lat_lo=round(lat - pad_lat, 4), lat_hi=round(lat + pad_lat, 4),
            lon_lo=round(lon - pad_lon, 4), lon_hi=round(lon + pad_lon, 4),
            depth_expr=(depth_expr.strip("[]") if binding.depth_axis else "0:0"),
        )

        resp = self._client.get_json(f"griddap/{binding.dataset_id}.json", selector)
        table = resp.payload["table"]
        cols = table["columnNames"]
        units_pub = dict(zip(cols, table.get("columnUnits", [None] * len(cols))))
        ix = {c: i for i, c in enumerate(cols)}

        var_col = binding.variable
        lat_col = self._col_named(cols, "lat")
        lon_col = self._col_named(cols, "lon")
        time_col = self._col_named(cols, "time")
        depth_col = next((c for c in cols
                          if c.lower() in ("zax", "depth", "zlev")), None)

        fill = meta.variables.get(var_col).fill_value if var_col in meta.variables else None

        best: tuple[float, list[Any]] | None = None
        total = masked = 0
        for row in table["rows"]:
            total += 1
            v = row[ix[var_col]]
            if v is None or (fill is not None and abs(v - fill) < 1e-6):
                masked += 1
                continue
            d = haversine_km(lat, lon, row[ix[lat_col]], row[ix[lon_col]])
            if best is None or d < best[0]:
                best = (d, row)

        coverage = (total - masked) / total if total else 0.0
        if best is None:
            raise ErddapError(
                ErrorCode.NO_DATA,
                f"{binding.dataset_id}.{var_col}: {total} cells returned, all masked "
                f"(fill value or land)",
            )

        dist, row = best
        actual_time = datetime.fromisoformat(str(row[ix[time_col]]).replace("Z", "+00:00"))
        published_unit = units_pub.get(var_col) or (
            meta.variables[var_col].units if var_col in meta.variables else None)
        unit = canonical_unit(published_unit)

        if stale:
            codes.append(ErrorCode.STALE_DATA)
        if coverage < 1.0:
            notes.append(f"coverage {coverage:.0%} of returned cells were valid")

        pid = self._provenance_id(binding, selector)
        quality = QualityMetadata(
            flag=QualityFlag.NOMINAL,
            basis="source-provided",
            coverage_fraction=round(coverage, 4),
            masked_reason="fill value / land" if masked else None,
            nearest_node_distance_km=round(dist, 2),
            freshness=self._freshness(actual_time, binding),
            staleness_s=(utcnow() - actual_time).total_seconds(),
            representativeness_match=None,
        )
        quality.add_check("unit_read_from_metadata", "pass", f"published={published_unit!r}")
        quality.add_check("nearest_node", "pass", f"{dist:.2f} km from request")
        if stale:
            quality.add_check("time_within_coverage", "fail",
                              f"requested {requested.date()} > coverage end {end.date()}")

        spatial = SpatialRef.point(
            lat=row[ix[lat_col]], lon=row[ix[lon_col]],
            depth_m=(row[ix[depth_col]] if depth_col else None),
            nearest_node_distance_km=round(dist, 2),
        )
        temporal = TemporalRef(
            valid_time=actual_time,
            representativeness=binding.representativeness,
            temporal_resolution=meta.axes.get("time", None).average_spacing
            if meta.axes.get("time") else None,
            retrieved_at=utcnow(),
        )
        prov = Provenance(
            provenance_id=pid,
            parameter=binding.parameter,
            value_kind=ValueKind.OBSERVED,
            unit=unit,
            spatial=spatial,
            temporal=temporal,
            source=SOURCE_NAME,
            source_id=SOURCE_ID,
            organisation=ORGANISATION,
            dataset=binding.dataset_id,
            product_reference=meta.title,
            access_method=ACCESS_METHOD,
            external_source=False,
            retrieved_at=utcnow(),
            request_fingerprint=f"sha256:{hashlib.sha256(resp.url.encode()).hexdigest()[:16]}",
            response_bytes=resp.bytes,
            spatial_resolution=f"lat {lat_sp} deg, lon {lon_sp} deg",
            temporal_resolution=(meta.axes["time"].average_spacing
                                 if "time" in meta.axes else None),
            quality=quality,
            notes=binding.note,
        )
        obs = Observation(
            parameter=binding.parameter,
            value=float(row[ix[var_col]]),
            unit=unit,
            spatial=spatial,
            temporal=temporal,
            quality=quality,
            provenance_id=pid,
        )
        return PointResult([obs], [prov], codes, notes, binding.dataset_id)

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _axis_named(meta: DatasetMeta, prefix: str) -> str:
        for name in meta.axes:
            if name.lower().startswith(prefix):
                return name
        return prefix

    @staticmethod
    def _col_named(cols: Iterable[str], prefix: str) -> str:
        for c in cols:
            if c.lower().startswith(prefix):
                return c
        raise ErddapError(ErrorCode.ADAPTER_ERROR, f"no {prefix} column in response")

    @staticmethod
    def _freshness(valid_time: datetime, binding: Binding) -> Freshness:
        cadence = _CADENCE_DAYS.get(binding.representativeness.value, 1.0)
        age_d = (utcnow() - valid_time).total_seconds() / 86400.0
        if age_d <= cadence * 1.5:
            return Freshness.FRESH
        if age_d <= cadence * 3:
            return Freshness.AGING
        if age_d <= cadence * 30:
            return Freshness.STALE
        return Freshness.EXPIRED

    @staticmethod
    def _provenance_id(binding: Binding, selector: str) -> str:
        h = hashlib.sha256(f"{binding.dataset_id}|{selector}".encode()).hexdigest()[:10]
        return f"pv-{h}"
