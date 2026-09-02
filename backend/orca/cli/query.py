"""ORCA vertical-slice CLI.

Retrieval -> canonical schema -> evidence pool -> independent domain
assessments -> cross-domain synthesis. Every number shown is traceable to a
provenance record, and no verdict is issued without sufficient evidence.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..adapters.cmems.adapter import CmemsAdapter
from ..adapters.incois_erddap.adapter import IncoisErddapAdapter
from ..assessment.engine import EvidencePool, assess_domain
from ..geospatial.derive import derive_from_envelope, derive_ratio_to_local_median
from ..assessment.synthesis import synthesise
from ..schemas.core import SpatialRef
from ..schemas.enums import Domain, Verdict
from ..tools.marine import get_currents, get_wave_conditions
from ..tools.ocean import get_chlorophyll, get_ocean_observations, get_sst

IST = ZoneInfo("Asia/Kolkata")
BAR = "=" * 78

#: Capabilities the vertical slice does not yet have a source for, and why.
#: These are declared so the answer can say what it did not check, rather than
#: silently omitting them.
UNBUILT = {
    "official_warning_status": ("get_marine_warnings", "IMD credentials not granted"),
    "lightning": ("get_lightning", "IMD credentials not granted"),
    "cyclone_distance_km": ("get_cyclone_track", "IMD credentials not granted"),
    "pfz_advisory": ("get_pfz", "INCOIS WMS pending network-independent verification"),
}


def get_wind(lat: float, lon: float, when: datetime, adapter):
    """Wind via CMEMS L4 observations.

    This is an OBSERVATION product with no forecast horizon, so a future query
    correctly yields INSUFFICIENT_COVERAGE rather than an invented value.
    """
    from ..adapters.cmems.client import SOURCE_ID
    from ..tools.base import collect_point_parameters
    return collect_point_parameters(
        "get_weather", ("eastward_wind", "northward_wind"), lat, lon, when,
        lambda sid, p: adapter.fetch_point(p, lat, lon, when), SOURCE_ID)


def _local_ratio(env, cmems, lat: float, lon: float, when: datetime):
    """Express chlorophyll comparatively, against the median of the same field.

    ORCA does not have a validated absolute chlorophyll standard, so the
    assessment factor is a ratio to the local median rather than a raw value.
    """
    from ..adapters.cmems.adapter import CmemsError
    obs = next((d for d in env.data if d.parameter == "chlorophyll_a"), None)
    if obs is None:
        return None, ""
    prov = next((p for p in env.provenance if p.provenance_id == obs.provenance_id),
                None)
    if prov is None or prov.source_id != "S-07":
        return None, ""          # the local field must come from the same source
    try:
        vals, _, _, n = cmems.fetch_local_field("chlorophyll_a", lat, lon, when, 100.0)
        result, rprov = derive_ratio_to_local_median(obs, prov, vals, 100.0, n)
    except (CmemsError, ValueError):
        return None, ""
    return (result, rprov), (
        f"chlorophyll_ratio_to_local_median = {result.value} "
        f"(median {result.detail['local_median']:g} mg m-3 over "
        f"{n} valid cells within 100 km)")


def run(lat: float, lon: float, label: str | None, when: datetime) -> int:
    window_start, window_end = when, when + timedelta(hours=4)
    spatial = SpatialRef.point(lat, lon, label=label)

    print(BAR)
    print("ORCA — Ocean Reasoning & Collaborative Agents   (vertical slice)")
    print(BAR)
    print(f"location    {label + ' ' if label else ''}({lat:.3f} N, {lon:.3f} E)")
    print(f"window      {window_start.astimezone(IST):%d %b %Y %H:%M}"
          f"–{window_end.astimezone(IST):%H:%M} IST")
    print()

    pool = EvidencePool()
    derived_note: list[str] = []
    print("RETRIEVAL")
    with IncoisErddapAdapter() as erddap, CmemsAdapter() as cmems:
        calls = [
            ("get_wave_conditions", lambda: get_wave_conditions(lat, lon, when,
                                                                adapter=cmems)),
            ("get_currents", lambda: get_currents(lat, lon, when, adapter=cmems)),
            ("get_weather", lambda: get_wind(lat, lon, when, cmems)),
            ("get_ocean_observations", lambda: get_ocean_observations(lat, lon, when,
                                                                      adapter=erddap)),
            ("get_sst", lambda: get_sst(lat, lon, when, adapter=erddap, cmems=cmems)),
            ("get_chlorophyll", lambda: get_chlorophyll(lat, lon, when, adapter=erddap,
                                                        cmems=cmems)),
        ]
        for name, call in calls:
            env = call()
            # Speed/direction are derived by the kernel, never by an adapter.
            d_data, d_prov = derive_from_envelope(env)
            if d_data:
                env.data.extend(d_data)
                env.provenance.extend(d_prov)
                derived_note.append(
                    f"{', '.join(x.parameter for x in d_data)} derived from "
                    f"{name} components")
            if name == "get_chlorophyll":
                d, note = _local_ratio(env, cmems, lat, lon, when)
                if d:
                    env.data.extend([d[0]])
                    env.provenance.extend([d[1]])
                    derived_note.append(note)
            pool.ingest(env)
            src = env.source_resolution.actual_source or "-"
            fb = " fallback" if env.source_resolution.fallback_used else ""
            codes = ",".join(sorted({c.value for c in env.codes()})) or "-"
            print(f"  {name:24} {env.status.value:8} {env.timing.duration_ms:>5} ms  "
                  f"{src}{fb}  [{codes}]")
    for factor, (tool, why) in UNBUILT.items():
        pool.add_gap(factor, "NOT_IMPLEMENTED", why, tool)
        print(f"  {tool:24} {'skipped':8} {'':>5}      —  [{why}]")

    if derived_note:
        print("\nDERIVED (deterministic kernel, inputs recorded)")
        for n in derived_note:
            print(f"  • {n}")

    print("\nEVIDENCE RETRIEVED")
    if not pool.candidates:
        print("  (none)")
    for c in pool.candidates:
        print(f"  • {c.parameter} = {c.value:g} {c.unit or ''}".rstrip())
        print(f"      {c.source} / {c.dataset}   valid {c.valid_time:%Y-%m-%d}"
              f"  ({c.representativeness.value})")
        print(f"      provenance {c.provenance_id}"
              + (f"   nearest node {c.node_distance_km:g} km away"
                 if c.node_distance_km else ""))

    print("\nASSESSMENTS   (independent by design; never merged into one score)")
    assessments = []
    for domain in (Domain.SAFETY, Domain.FISHING_SUITABILITY):
        res = assess_domain(domain, pool, window_start=window_start,
                            window_end=window_end, spatial=spatial)
        a = res.assessment
        assessments.append(a)
        print(f"\n  {a.domain.value:22} {a.verdict.value:22} confidence={a.confidence.value}")
        print(f"      thresholds  {a.threshold_set}  [{a.threshold_set_status}]")
        for d in a.drivers:
            mark = ">>" if d.contribution == "limiting" else "  "
            val = f"{d.value:g} {d.unit or ''}".strip() if d.value is not None else "-"
            print(f"      {mark} {d.factor:28} {val:14} {d.band or ''}")
        for n in a.not_evaluated:
            print(f"         not evaluated: {n.factor:24} {n.reason}")
        if a.rationale:
            print(f"      {a.rationale}")

    s = synthesise(assessments)
    print(f"\nANSWER   [{s.category}]")
    print(f"  {s.headline}")
    print(f"  disposition: {s.disposition.value}   confidence: {s.confidence.value}")

    print("\nORCA output is not an official advisory. Follow IMD and INCOIS bulletins.")
    print(BAR)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="orca-query", description="ORCA vertical slice")
    p.add_argument("--lat", type=float, default=9.93)
    p.add_argument("--lon", type=float, default=76.26)
    p.add_argument("--label", default="near Kochi")
    p.add_argument("--when", default=None, help="ISO-8601 UTC; default tomorrow 06:00 IST")
    a = p.parse_args(argv)
    when = (datetime.fromisoformat(a.when).replace(tzinfo=timezone.utc) if a.when
            else (datetime.now(IST) + timedelta(days=1)).replace(
                hour=6, minute=0, second=0, microsecond=0).astimezone(timezone.utc))
    return run(a.lat, a.lon, a.label, when)


if __name__ == "__main__":
    sys.exit(main())
