"""Derived quantities.

Derivations happen HERE, not in adapters, so that every computed number carries
a recomputable derivation record naming its inputs, method and version
(05_CANONICAL_DATA_SCHEMA.md section 16).
"""
from __future__ import annotations

import hashlib

from ..schemas.core import Provenance, QualityMetadata, SpatialRef, TemporalRef, utcnow
from ..schemas.data import DerivedResult
from ..schemas.enums import QualityFlag, ValueKind
from .geometry import vector_magnitude_direction
from .methods import derivation

#: (u parameter, v parameter) -> (speed parameter, direction parameter, convention)
VECTOR_PAIRS = {
    ("current_u", "current_v"): ("current_speed", "current_direction", "towards"),
    ("eastward_wind", "northward_wind"): ("wind_speed", "wind_direction", "from"),
}


def _pid(*parts: str) -> str:
    return "pv-" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:10]


def derive_vector_pair(u_obs, u_prov: Provenance, v_obs, v_prov: Provenance):
    """Speed and direction from two components.

    Returns ([DerivedResult], [Provenance]). Both results reference the input
    provenance ids, so the numbers can be recomputed from the record alone.
    """
    key = (u_obs.parameter, v_obs.parameter)
    if key not in VECTOR_PAIRS:
        raise ValueError(f"no vector pairing registered for {key}")
    speed_param, dir_param, convention = VECTOR_PAIRS[key]

    speed, bearing = vector_magnitude_direction(u_obs.value, v_obs.value,
                                                convention=convention)
    spatial: SpatialRef = u_obs.spatial
    temporal: TemporalRef = u_obs.temporal
    inputs = [u_prov.provenance_id, v_prov.provenance_id]
    quality = QualityMetadata(
        flag=(QualityFlag.SUSPECT
              if QualityFlag.SUSPECT in (u_obs.quality.flag, v_obs.quality.flag)
              else QualityFlag.NOMINAL),
        basis="orca-computed",
        nearest_node_distance_km=u_obs.quality.nearest_node_distance_km,
        lead_time_h=u_obs.quality.lead_time_h,
        freshness=u_obs.quality.freshness,
    )

    out_data, out_prov = [], []
    for param, value, unit in ((speed_param, round(speed, 4), u_obs.unit),
                               (dir_param, round(bearing, 2), "degree")):
        d = derivation("vector_magnitude_direction", inputs,
                       {"convention": convention, "u": u_obs.parameter,
                        "v": v_obs.parameter, "component": param},
                       module="derive")
        pid = _pid(param, *inputs)
        out_prov.append(Provenance(
            provenance_id=pid, parameter=param, value_kind=ValueKind.DERIVED,
            unit=unit, spatial=spatial, temporal=temporal,
            source=u_prov.source, source_id=u_prov.source_id,
            organisation=u_prov.organisation, dataset=u_prov.dataset,
            access_method=u_prov.access_method,
            external_source=u_prov.external_source,
            retrieved_at=utcnow(), quality=quality, derivation=d,
            notes=f"derived from {u_obs.parameter} and {v_obs.parameter}",
            licence_reference=u_prov.licence_reference))
        out_data.append(DerivedResult(
            parameter=param, value=value, unit=unit, spatial=spatial,
            temporal=temporal, quality=quality, provenance_id=pid,
            detail={"convention": convention}))
    return out_data, out_prov


def derive_from_envelope(env):
    """Find vector pairs in an envelope and derive speed/direction for each."""
    prov = {p.provenance_id: p for p in env.provenance}
    by_param = {d.parameter: d for d in env.data if hasattr(d, "value")}
    data, provenance = [], []
    for (u_name, v_name) in VECTOR_PAIRS:
        u, v = by_param.get(u_name), by_param.get(v_name)
        if u is None or v is None or u.value is None or v.value is None:
            continue
        d, p = derive_vector_pair(u, prov[u.provenance_id], v, prov[v.provenance_id])
        data.extend(d)
        provenance.extend(p)
    return data, provenance


def derive_ratio_to_local_median(obs, obs_prov: Provenance, local_values,
                                 radius_km: float, cell_count: int):
    """Express a value as a ratio to the local median of the same field.

    Comparative, not absolute: ORCA states "above the local median for this
    field", never "high", which would imply a standard it has not validated.
    """
    import numpy as np

    median = float(np.median(local_values))
    if median <= 0:
        raise ValueError("local median is not positive; ratio is undefined")
    ratio = float(obs.value) / median

    param = f"{obs.parameter.replace('_a', '')}_ratio_to_local_median"
    if obs.parameter == "chlorophyll_a":
        param = "chlorophyll_ratio_to_local_median"

    d = derivation("ratio_to_local_median", [obs_prov.provenance_id],
                   {"statistic": "median", "radius_km": radius_km,
                    "valid_cells": cell_count, "median": round(median, 6),
                    "unit": obs.unit},
                   module="derive")
    pid = _pid(param, obs_prov.provenance_id, str(round(median, 6)))
    quality = QualityMetadata(
        flag=obs.quality.flag, basis="orca-computed",
        nearest_node_distance_km=obs.quality.nearest_node_distance_km,
        freshness=obs.quality.freshness)
    quality.add_check("local_sample_size", "pass" if cell_count >= 50 else "fail",
                      f"{cell_count} valid cells within {radius_km:g} km")

    prov = Provenance(
        provenance_id=pid, parameter=param, value_kind=ValueKind.DERIVED,
        unit="ratio", spatial=obs.spatial, temporal=obs.temporal,
        source=obs_prov.source, source_id=obs_prov.source_id,
        organisation=obs_prov.organisation, dataset=obs_prov.dataset,
        access_method=obs_prov.access_method,
        external_source=obs_prov.external_source, retrieved_at=utcnow(),
        quality=quality, derivation=d,
        notes=(f"{obs.parameter} relative to the median of {cell_count} valid "
               f"cells within {radius_km:g} km"),
        licence_reference=obs_prov.licence_reference)
    result = DerivedResult(
        parameter=param, value=round(ratio, 4), unit="ratio",
        spatial=obs.spatial, temporal=obs.temporal, quality=quality,
        provenance_id=pid,
        detail={"local_median": round(median, 6), "radius_km": radius_km,
                "valid_cells": cell_count})
    return result, prov
