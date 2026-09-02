"""geo_reason (07 section 4). Alignment and derivation; continues degraded."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from ...agents.geospatial_agent import GeospatialAgent
from ...schemas.core import utcnow
from ...schemas.enums import Domain
from ..events import node_event
from ..runtime import runtime_from
from ..state import OrcaGraphState


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
    return {
        "alignment_report": report,
        "derived": list(report.derived),
        "node_events": [node_event("geo_reason", "success", started=started,
                                   summary=result.reasoning_summary,
                                   aligned=len(report.aligned),
                                   derived=len(report.derived))],
    }
