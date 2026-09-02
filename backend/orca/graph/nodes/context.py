"""ingest, intent_context and clarify (07 section 4).

`intent_context` resolves location and time DETERMINISTICALLY. When it cannot,
it sets `clarification_needed` and the graph stops before retrieval: a position
ORCA invented would be a fabricated premise for every number that followed.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ...agents.planner import PlannerAgent
from ..events import node_event
from ..runtime import runtime_from
from ..state import OrcaGraphState

IST = ZoneInfo("Asia/Kolkata")

#: A placeholder gazetteer. STATUS: a real deployment needs a proper gazetteer
#: with admin boundaries and alternate spellings; this covers the demo ports and
#: fails closed (asking the user) for anything else.
GAZETTEER: dict[str, tuple[float, float]] = {
    "kochi": (9.93, 76.26), "cochin": (9.93, 76.26),
    "chennai": (13.08, 80.29), "mumbai": (18.94, 72.83),
    "visakhapatnam": (17.69, 83.30), "vizag": (17.69, 83.30),
    "mangalore": (12.87, 74.84), "goa": (15.42, 73.80),
    "kanyakumari": (8.08, 77.55), "tuticorin": (8.76, 78.13),
    "paradip": (20.26, 86.67), "kolkata": (22.57, 88.36),
}

_LATLON = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*[°]?\s*([ns])\s*,?\s*(-?\d+(?:\.\d+)?)\s*[°]?\s*([ew])",
    re.IGNORECASE)


def ingest(state: OrcaGraphState, config=None) -> dict:
    started = time.perf_counter()
    run_id = state.get("run_id") or f"run-{uuid.uuid4().hex[:12]}"
    return {
        "run_id": run_id,
        "trace_id": state.get("trace_id") or run_id,
        "language": state.get("language") or "en",
        "session_context": state.get("session_context") or {},
        "attempts": state.get("attempts", 0),
        "plan_version": state.get("plan_version", 0),
        "node_events": [node_event("ingest", "success", started=started,
                                   summary=f"run {run_id}")],
    }


def _resolve_location(state: OrcaGraphState) -> tuple[dict | None, str]:
    explicit = state.get("resolved_location")
    if explicit and explicit.get("lat") is not None:
        return explicit, "location supplied by the caller"

    text = (state.get("query_text") or "").lower()
    match = _LATLON.search(text)
    if match:
        lat = float(match.group(1)) * (-1 if match.group(2).lower() == "s" else 1)
        lon = float(match.group(3)) * (-1 if match.group(4).lower() == "w" else 1)
        return {"lat": lat, "lon": lon, "label": None}, "coordinates parsed from query"

    for name, (lat, lon) in GAZETTEER.items():
        if re.search(rf"\b{name}\b", text):
            return ({"lat": lat, "lon": lon, "label": f"near {name.title()}"},
                    f"gazetteer match {name!r}")

    carried = (state.get("session_context") or {}).get("resolved_location")
    if carried:
        return carried, "carried from session context"
    return None, "no location in the query, the session or the gazetteer"


def _resolve_window(state: OrcaGraphState, window_hours: int) -> tuple[dict | None, str]:
    explicit = state.get("resolved_time_window")
    if explicit and explicit.get("start_time"):
        return explicit, "window supplied by the caller"

    text = (state.get("query_text") or "").lower()
    now_ist = datetime.now(IST)
    start = None
    if "tomorrow" in text:
        base = now_ist + timedelta(days=1)
        hour = 6 if ("morning" in text or "dawn" in text) else 12
        start = base.replace(hour=hour, minute=0, second=0, microsecond=0)
    elif "tonight" in text or "evening" in text:
        start = now_ist.replace(hour=18, minute=0, second=0, microsecond=0)
    elif "today" in text or "now" in text or "right now" in text:
        start = now_ist
    if start is None:
        return None, "no time expression recognised in the query"
    start_utc = start.astimezone(timezone.utc)
    return ({"start_time": start_utc.isoformat(),
             "end_time": (start_utc + timedelta(hours=window_hours)).isoformat()},
            "parsed from the query, IST to UTC")


def intent_context(state: OrcaGraphState, config=None) -> dict:
    started = time.perf_counter()
    rt = runtime_from(config)
    planner = PlannerAgent(llm=rt.llm, ledger=rt.ledger, budget=rt.budget)

    intent = planner.classify(state.get("query_text") or "")
    location, loc_note = _resolve_location(state)
    window, win_note = _resolve_window(state, rt.window_hours)

    return {
        "intent": intent,
        "intent_confidence": 1.0 if planner._planner_id() == "deterministic" else 0.9,
        "resolved_location": location,
        "resolved_time_window": window,
        "resolution_notes": [loc_note, win_note],
        "node_events": [node_event("intent_context", "success", started=started,
                                   summary=f"intent={intent}; {loc_note}; {win_note}")],
    }


def clarify(state: OrcaGraphState, config=None) -> dict:
    """Terminal. Asks exactly one question rather than guessing a premise."""
    started = time.perf_counter()
    plan = state.get("plan")
    needed = (getattr(plan, "clarification_needed", None)
              or state.get("clarification_needed") or "location")
    questions = {
        "location": "Where are you asking about? A place name or a "
                    "latitude and longitude will do.",
        "time_window": "For when? For example 'tomorrow morning' or a date and time.",
        "intent": "What would you like to know about that sea area — safety, "
                  "fishing conditions, or maritime boundaries?",
    }
    return {
        "clarification_needed": needed,
        "recommendation": {"category": "CLARIFICATION_NEEDED",
                           "headline": questions.get(needed, questions["location"]),
                           "is_official_advisory": False},
        "node_events": [node_event("clarify", "success", started=started,
                                   summary=f"asked for {needed}")],
    }
