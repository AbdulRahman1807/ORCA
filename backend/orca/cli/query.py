"""ORCA vertical-slice CLI.

Runs the implemented part of the pipeline against live INCOIS ERDDAP and prints
an evidence-backed report. It reports what it can support and refuses what it
cannot -- see 12_RISK_AND_RECOMMENDATION_SPEC.md.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..adapters.incois_erddap.adapter import IncoisErddapAdapter
from ..schemas.enums import Domain, Freshness, Verdict
from ..schemas.errors import ErrorCode
from ..tools.ocean import get_chlorophyll, get_ocean_observations, get_sst

IST = ZoneInfo("Asia/Kolkata")

#: Inputs SAFETY requires before any safety statement may be issued.
SAFETY_REQUIRED = ("significant_wave_height", "wind_speed", "official_warning_status")
#: Tools that would supply them, and why they are not yet available.
SAFETY_GAPS = {
    "significant_wave_height": ("get_wave_conditions", "CMEMS credentials not configured"),
    "wind_speed": ("get_weather", "IMD credentials not granted (HTTP 403 unauthenticated)"),
    "official_warning_status": ("get_marine_warnings", "IMD credentials not granted"),
}

BAR = "=" * 78


def _fmt_place(lat: float, lon: float, label: str | None) -> str:
    return f"{label} ({lat:.3f} N, {lon:.3f} E)" if label else f"{lat:.3f} N, {lon:.3f} E"


def run(lat: float, lon: float, label: str | None, when: datetime) -> int:
    print(BAR)
    print("ORCA — Ocean Reasoning & Collaborative Agents   (vertical slice)")
    print(BAR)
    print(f"location    {_fmt_place(lat, lon, label)}")
    print(f"time window {when.astimezone(IST):%d %b %Y %H:%M} IST "
          f"({when:%Y-%m-%dT%H:%MZ})")
    print()

    envelopes = []
    with IncoisErddapAdapter() as adapter:
        print("RETRIEVAL")
        for name, fn in (("get_ocean_observations", get_ocean_observations),
                         ("get_sst", get_sst),
                         ("get_chlorophyll", get_chlorophyll)):
            env = fn(lat, lon, when, adapter=adapter)
            envelopes.append(env)
            src = env.source_resolution.actual_source or "-"
            fb = " (fallback)" if env.source_resolution.fallback_used else ""
            print(f"  {name:24} {env.status.value:8} {env.timing.duration_ms:>5} ms  "
                  f"source={src}{fb}")

    print("\nEVIDENCE")
    any_data = False
    for env in envelopes:
        for obs in env.data:
            any_data = True
            prov = next(p for p in env.provenance if p.provenance_id == obs.provenance_id)
            q = obs.quality
            print(f"  • {obs.parameter} = {obs.value} {obs.unit or ''}")
            print(f"      source     {prov.source} / {prov.dataset}")
            print(f"      valid      {obs.temporal.valid_time:%Y-%m-%d %H:%MZ}"
                  f"  ({obs.temporal.representativeness.value})")
            print(f"      retrieved  {prov.retrieved_at:%Y-%m-%d %H:%M:%SZ}")
            print(f"      location   {obs.spatial.lat} N, {obs.spatial.lon} E"
                  + (f", {obs.spatial.depth_m:g} m depth" if obs.spatial.depth_m else "")
                  + f"  ({q.nearest_node_distance_km} km from your position)")
            print(f"      quality    freshness={q.freshness.value if q.freshness else '?'}"
                  f"  valid-cell coverage={q.coverage_fraction:.0%}"
                  if q.coverage_fraction is not None else
                  f"      quality    freshness={q.freshness.value if q.freshness else '?'}")
            print(f"      provenance {prov.provenance_id}")
    if not any_data:
        print("  (none)")

    print("\nNOT EVALUATED")
    stale = []
    for env in envelopes:
        for e in env.errors:
            if e.code is ErrorCode.STALE_DATA:
                stale.append(e.subject)
            elif e.severity != "info":
                print(f"  • {e.subject or env.tool}: {e.code.value} — {e.detail[:70]}")
    for param, (tool, why) in SAFETY_GAPS.items():
        print(f"  • {param}: {tool} unavailable — {why}")

    print("\nASSESSMENTS  (domains are independent and are never merged)")
    print(f"  {Domain.SAFETY.value:22} {Verdict.INSUFFICIENT_EVIDENCE.value}")
    print(f"      No safety verdict is issued. Required inputs are missing:")
    for p in SAFETY_REQUIRED:
        print(f"        - {p} ({SAFETY_GAPS[p][1]})")
    print(f"      Absence of evidence is not evidence of safety.")

    print(f"\n  {Domain.FISHING_SUITABILITY.value:22} {Verdict.INSUFFICIENT_EVIDENCE.value}")
    if stale:
        print(f"      Retrieved data exist but are not valid for the requested time:")
        for env in envelopes:
            for obs in env.data:
                age_d = (when - obs.temporal.valid_time).days
                print(f"        - {obs.parameter}: valid {obs.temporal.valid_time:%Y-%m-%d}"
                      f", {age_d:,} days before the requested window"
                      f" ({obs.temporal.representativeness.value})")
        print("      A 10-day/monthly analysis and multi-year archives cannot support a")
        print("      next-morning suitability verdict (representativeness rule).")
    print("      The INCOIS PFZ advisory is the authoritative product for this question;")
    print("      it is not reachable here (INCOIS WMS pending verification).")

    print("\nWHAT THIS RUN DEMONSTRATES")
    print("  - live retrieval from an authoritative source, with full provenance")
    print("  - units, resolution and validity read from the server, never assumed")
    print("  - staleness and spatial mismatch surfaced rather than hidden")
    print("  - domain separation, and refusal to issue a verdict without evidence")
    print()
    print("ORCA output is not an official advisory. Follow IMD and INCOIS bulletins.")
    print(BAR)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="orca-query", description="ORCA vertical slice")
    p.add_argument("--lat", type=float, default=9.93)
    p.add_argument("--lon", type=float, default=76.26)
    p.add_argument("--label", default="near Kochi")
    p.add_argument("--when", default=None,
                   help="ISO-8601 UTC; default = tomorrow 06:00 IST")
    a = p.parse_args(argv)
    when = (datetime.fromisoformat(a.when).replace(tzinfo=timezone.utc) if a.when
            else (datetime.now(IST) + timedelta(days=1)).replace(
                hour=6, minute=0, second=0, microsecond=0).astimezone(timezone.utc))
    return run(a.lat, a.lon, a.label, when)


if __name__ == "__main__":
    sys.exit(main())
