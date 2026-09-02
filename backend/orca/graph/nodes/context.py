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
    
    # Detect language from query text if not provided
    from ...i18n.detect import detect_language
    lang = state.get("language")
    if not lang:
        lang = detect_language(state.get("query_text") or "")
        
    return {
        "run_id": run_id,
        "trace_id": state.get("trace_id") or run_id,
        "language": lang,
        "session_context": state.get("session_context") or {},
        "attempts": state.get("attempts", 0),
        "plan_version": state.get("plan_version", 0),
        "node_events": [node_event("ingest", "success", started=started,
                                   summary=f"run {run_id}")],
    }


def _resolve_location(state: OrcaGraphState) -> tuple[dict | None, str]:
    """Origin, plus a destination when the query names one."""
    # The destination is settled FIRST, then excluded from origin matching:
    # in "plan a route to Mumbai" the only place named is the far end, and
    # treating it as the origin would route from the destination to itself.
    _, dest_key = _route_endpoints(state, (state.get("query_text") or "").lower())
    origin, note = _resolve_origin(state, exclude=dest_key)
    if origin is None or origin.get("dest_lat") is not None or not dest_key:
        return origin, note
    dlat, dlon = GAZETTEER[dest_key]
    if (dlat, dlon) != (origin.get("lat"), origin.get("lon")):
        origin = {**origin, "dest_lat": dlat, "dest_lon": dlon,
                  "label": f"{origin.get('label') or 'here'} to {dest_key.title()}"}
        note = f"{note}; destination {dest_key!r}"
    return origin, note


def _resolve_origin(state: OrcaGraphState,
                    exclude: str | None = None) -> tuple[dict | None, str]:
    explicit = state.get("resolved_location")
    if explicit and explicit.get("lat") is not None:
        return explicit, "location supplied by the caller"

    text = (state.get("query_text") or "").lower()
    
    # -- route endpoints ---------------------------------------------------
    # Accepts "from A to B" and bare "to B" (origin = wherever else resolves),
    # matches multi-word gazetteer names, and reads the user's own script.
    origin_key, dest_key = _route_endpoints(state, text)
    if dest_key and origin_key:
        olat, olon = GAZETTEER[origin_key]
        dlat, dlon = GAZETTEER[dest_key]
        return ({"lat": olat, "lon": olon, "dest_lat": dlat, "dest_lon": dlon,
                 "label": f"{origin_key.title()} to {dest_key.title()}"},
                f"route {origin_key!r} to {dest_key!r}")

    # A place written in the user's own script resolves through the language's
    # own lexicon; the Latin gazetteer is still tried, because people mix scripts.
    lang = state.get("language") or "en"
    if lang != "en":
        from ...i18n.generate import native_place
        key = native_place(lang, state.get("query_text") or "")
        if key and key in GAZETTEER and key != exclude:
            lat, lon = GAZETTEER[key]
            return ({"lat": lat, "lon": lon, "label": f"near {key.title()}"},
                    f"gazetteer match {key!r} via {lang} lexicon")

    for name, (lat, lon) in GAZETTEER.items():
        if name != exclude and re.search(rf"\b{name}\b", text):
            return ({"lat": lat, "lon": lon, "label": f"near {name.title()}"},
                    f"gazetteer match {name!r}")

    carried = (state.get("session_context") or {}).get("resolved_location")
    if carried:
        return carried, "carried from session context"
    return None, "no location in the query, the session or the gazetteer"


def _route_endpoints(state, text: str) -> tuple[str | None, str | None]:
    """(origin_key, destination_key) as gazetteer keys, either may be None.

    Substring matching handles multi-word names; the language's own place
    lexicon handles native scripts.
    """
    lang = state.get("language") or "en"
    raw = state.get("query_text") or ""

    def find(fragment: str) -> str | None:
        frag = fragment.lower()
        hit = max((k for k in GAZETTEER if k in frag), key=len, default=None)
        if hit:
            return hit
        if lang != "en":
            from ...i18n.generate import native_place
            return native_place(lang, fragment)
        return None

    m = re.search(r"\bfrom\s+(.{2,40}?)\s+to\s+(.{2,40}?)\s*[?.!]?$", text)
    if m:
        o, d = find(m.group(1)), find(m.group(2))
        if d:
            return (o if o != d else None), d

    m = re.search(r"\bto\s+(.{2,40}?)\s*[?.!]?$", text)
    if m:
        d = find(m.group(1))
        if d:
            return None, d

    # Native scripts rarely use "from/to"; take two distinct places in order.
    if lang != "en":
        from ...i18n.generate import section
        found = [(raw.find(native), key)
                 for native, key in section(lang, "place").items()
                 if native in raw]
        found.sort()
        if len(found) >= 2 and found[0][1] != found[1][1]:
            return found[0][1], found[1][1]
    return None, None


def _resolve_window(state: OrcaGraphState, window_hours: int) -> tuple[dict | None, str]:
    explicit = state.get("resolved_time_window")
    if explicit and explicit.get("start_time"):
        return explicit, "window supplied by the caller"

    text = (state.get("query_text") or "").lower()
    lang = state.get("language") or "en"
    if lang != "en":
        # Fold the native time words into the same English keys the rules below
        # already understand, so there is one set of rules, not one per language.
        from ...i18n.generate import native_time
        text = text + " " + " ".join(sorted(native_time(lang, state.get("query_text") or "")))

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

    intent = planner.classify(state.get("query_text") or "",
                              language=state.get("language") or "en")
    if intent in ("unknown", "smalltalk_or_out_of_scope"):
        carried_intent = (state.get("session_context") or {}).get("intent")
        if carried_intent:
            intent = carried_intent

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
        "destination": "Where would you like to sail to? Name a port and I will "
                       "plan a route that stays in navigable water.",
    }
    return {
        "clarification_needed": needed,
        "recommendation": {"category": "CLARIFICATION_NEEDED",
                           "headline": questions.get(needed, questions["location"]),
                           "is_official_advisory": False},
        "node_events": [node_event("clarify", "success", started=started,
                                   summary=f"asked for {needed}")],
    }
