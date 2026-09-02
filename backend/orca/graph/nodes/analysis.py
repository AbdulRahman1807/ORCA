"""geo_reason (07 section 4). Alignment and derivation; continues degraded."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from ...agents.geospatial_agent import GeospatialAgent
from ...schemas.assessment import NotEvaluated
from ...schemas.core import utcnow
from ...schemas.enums import Domain
from ..events import node_event
from ..runtime import runtime_from
from ..state import OrcaGraphState

log = logging.getLogger("orca.graph.analysis")


def _window(state: OrcaGraphState, hours: int = 4) -> tuple[datetime, datetime]:
    """The analysis window, defaulting to now.

    A time-independent question -- "am I inside the EEZ?" -- legitimately
    resolves no window, and the Planner does not ask for one. The analysis frame
    still needs an interval to align against, so it defaults to the present.
    Time-SENSITIVE intents never reach here without a window: the Planner asks
    for one first.
    """
    w = state.get("resolved_time_window") or {}
    if w.get("start_time"):
        start = datetime.fromisoformat(w["start_time"])
        end = (datetime.fromisoformat(w["end_time"]) if w.get("end_time")
               else start + timedelta(hours=hours))
        return start, end
    start = utcnow()
    return start, start + timedelta(hours=hours)


def geo_reason(state: OrcaGraphState, config=None) -> dict:
    started = time.perf_counter()
    rt = runtime_from(config)
    agent = GeospatialAgent(llm=rt.llm, ledger=rt.ledger, budget=rt.budget)
    loc = state.get("resolved_location") or {}
    plan = state.get("plan")
    start, end = _window(state)

    result = agent.analyse(
        list(state.get("tool_results") or []),
        lat=loc.get("lat"), lon=loc.get("lon"),
        window_start=start, window_end=end,
        domains=list(getattr(plan, "domains_required", []) or [Domain.SAFETY]))

    if not result.ok:
        # Degraded, not fatal: assessment can still run on the retrieved values.
        return {"node_events": [node_event("geo_reason", "error", started=started,
                                           summary=result.failure.detail)]}
    report = result.value
    
    # NEW ROUTING LOGIC
    intent = getattr(plan, "intent", "") if plan else ""
    additional_tool_results = []
    
    if intent == "route_optimization" and loc.get("dest_lat") is not None:
        from ...geospatial.routing import a_star_route
        from ...schemas.data import OceanField, DerivedResult
        from ...schemas.core import SpatialRef
        from ...schemas.envelope import OrcaEnvelope
        from ...schemas.core import Provenance, TemporalRef, utcnow
        from ...schemas.enums import EnvelopeStatus
        
        # Flatten tool results properly (they are envelopes)
        fields = []
        for env in (state.get("tool_results") or []):
            if hasattr(env, "data"):
                fields.extend([e for e in env.data if isinstance(e, OceanField)])
                
        # Navigability comes from the composition root, so this module never
        # imports an adapter. Without it, routing is DECLARED UNAVAILABLE rather
        # than run unmasked -- an unmasked route crosses land (F-43).
        navigable = getattr(rt, "navigable", None)
        if navigable is None:
            return {
                "not_evaluated": [NotEvaluated(
                    factor="optimized_route", reason="DATASET_UNAVAILABLE",
                    detail="no navigability mask is configured; a route is not "
                           "offered rather than risk one that crosses land")],
                "node_events": [node_event(
                    "geo_reason", "success", started=started,
                    summary="route requested but no navigability mask configured")],
            }
        try:
            path = a_star_route(
                start_lon=loc["lon"], start_lat=loc["lat"],
                end_lon=loc["dest_lon"], end_lat=loc["dest_lat"],
                fields=fields, is_navigable=navigable
            )
            if not path:
                return {
                    "not_evaluated": [NotEvaluated(
                        factor="optimized_route", reason="NO_DATA",
                        detail="no navigable route was found within the "
                               "snapshot region")],
                    "node_events": [node_event(
                        "geo_reason", "success", started=started,
                        summary="no navigable route found")],
                }
            # The VALUE is the route's length, not its waypoint count: a
            # count says nothing a user could act on.
            from ...geospatial.routing import _km as _leg_km
            length_km = sum(_leg_km(path[i][0], path[i][1], path[i+1][0],
                                    path[i+1][1]) for i in range(len(path) - 1))
            route_evidence = DerivedResult(
                parameter="optimized_route",
                value=round(length_km, 1), unit="km",
                spatial=SpatialRef(kind="linestring", coordinates=path),
                temporal=TemporalRef(valid_time=utcnow()),
                provenance_id="pv-orca-routing-engine-v1",
                detail={"waypoints": len(path),
                        "length_km": round(length_km, 1),
                        "navigability": "MarineRegions EEZ snapshot",
                        "advisory_only": True,
                        "note": "planned in navigable water; not a "
                                "navigational chart and no depth is considered"}
            )
            report.derived.append(route_evidence.provenance_id)
            
            from ...schemas.enums import ValueKind
            from ...geospatial.methods import derivation
            
            route_env = OrcaEnvelope(
                status=EnvelopeStatus.SUCCESS,
                tool="a_star_route",
                data=[route_evidence],
                provenance=[Provenance(
                    provenance_id="pv-orca-routing-engine-v1", 
                    parameter="optimized_route",
                    value_kind=ValueKind.DERIVED,
                    source="orca_internal",
                    source_id="orca-routing-engine-v1",
                    derivation=derivation(
                        "a_star_route",
                        [f"{loc['lat']},{loc['lon']}",
                         f"{loc['dest_lat']},{loc['dest_lon']}"],
                        {"resolution_deg": 0.15,
                         "navigability": "MarineRegions EEZ snapshot"},
                        module="routing")
                )]
            )
            additional_tool_results.append(route_env)
        except Exception as exc:
            # A swallowed failure here meant the user asked for a route, got a
            # safety assessment instead, and was never told routing had failed.
            # There is no straight-line fallback: a straight line between two
            # ports crosses land (F-43).
            log.exception("route planning failed")
            return {
                "alignment_report": report,
                "not_evaluated": [NotEvaluated(
                    factor="optimized_route", reason="ADAPTER_ERROR",
                    detail=f"route planning failed: "
                           f"{type(exc).__name__}: {exc}")],
                "node_events": [node_event(
                    "geo_reason", "error", started=started,
                    summary=f"route planning failed: {type(exc).__name__}")],
            }

    return {
        "alignment_report": report,
        "tool_results": additional_tool_results,
        "node_events": [node_event("geo_reason", "success", started=started,
                                   summary=result.reasoning_summary,
                                   aligned=len(report.aligned),
                                   derived=len(report.derived))],
    }
