"""OrcaGraphState and its reducers (07_LANGGRAPH_WORKFLOW_SPEC.md section 3).

Invariant (section 3.1): no node overwrites another node's output. Fields written
by parallel branches use `add`, which is commutative and loses nothing, so a
fan-in is order-independent. Correction is expressed as a new appended record,
never as a mutation, which is what keeps the audit trail complete.
"""
from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict


def last_write(a: Any, b: Any) -> Any:
    """Single-writer fields. A None write does not erase a real value."""
    return b if b is not None else a


def merge_dict(a: dict | None, b: dict | None) -> dict:
    return {**(a or {}), **(b or {})}


def accumulate_budget(a: dict | None, b: dict | None) -> dict:
    """Budget is shared across branches, so numeric fields accumulate."""
    out = dict(a or {})
    for key, value in (b or {}).items():
        if isinstance(value, (int, float)) and isinstance(out.get(key), (int, float)):
            out[key] = out[key] + value
        else:
            out[key] = value
    return out


class OrcaGraphState(TypedDict, total=False):
    # ---- identity -------------------------------------------------------
    run_id: str
    session_id: str
    user_id: str | None
    role: Literal["fisher", "operator", "officer", "analyst", "reviewer", "admin"]

    # ---- input ----------------------------------------------------------
    query_text: str
    language: str
    session_context: dict

    # ---- resolved context (deterministic) -------------------------------
    intent: str
    intent_confidence: float
    resolved_location: dict | None
    resolved_time_window: dict | None
    resolution_notes: Annotated[list, add]
    clarification_needed: str | None

    # ---- planning -------------------------------------------------------
    plan: Any
    plan_version: int
    attempts: int
    unavailable_capabilities: Annotated[list, add]

    # ---- retrieval (fan-in) ---------------------------------------------
    tool_results: Annotated[list, add]
    step_results: Annotated[list, add]
    modifications: Annotated[list, add]
    retrieval_report: Any
    fallbacks_used: Annotated[list, add]

    # ---- validation -----------------------------------------------------
    validation_report: Any
    evidence_gaps: Annotated[list, add]

    # ---- geospatial -----------------------------------------------------
    alignment_report: Any
    derived: Annotated[list, add]
    layers: Annotated[list, add]

    # ---- assessment (fan-in) --------------------------------------------
    assessments: Annotated[list, add]
    conflicts: Annotated[list, add]
    not_evaluated: Annotated[list, add]

    # ---- evidence & output ----------------------------------------------
    evidence: Annotated[list, add]
    claims: Annotated[list, add]
    recommendation: Any
    disposition: str | None
    review_reason: str | None
    human_review: dict | None

    # ---- provenance & observability -------------------------------------
    provenance: Annotated[list, add]
    node_events: Annotated[list, add]
    errors: Annotated[list, add]
    errors_fatal: bool
    budget: Annotated[dict, accumulate_budget]
    trace_id: str
