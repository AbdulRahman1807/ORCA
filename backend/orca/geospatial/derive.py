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
