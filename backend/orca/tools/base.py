"""Capability tool machinery.

Tools are the ONLY interface agents see. They validate inputs, select sources,
apply fallback policy and return an OrcaEnvelope. They never contain provider
knowledge (04_ORCA_TOOL_CONTRACTS.md).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from ..schemas.core import BBox, utcnow
from ..schemas.enums import EnvelopeStatus
from ..schemas.envelope import OrcaEnvelope, SourceAttempt, SourceResolution, Timing
from ..schemas.errors import ErrorCode, OrcaError

MAX_BBOX_AREA_KM2 = 500_000.0
MAX_TIME_WINDOW_DAYS = 31


class ToolInputError(Exception):
    def __init__(self, code: ErrorCode, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def validate_point(lat: float | None, lon: float | None) -> None:
    if lat is None or lon is None:
        raise ToolInputError(ErrorCode.INVALID_LOCATION, "lat and lon are required")
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise ToolInputError(ErrorCode.INVALID_LOCATION,
                             f"coordinates out of range: {lat}, {lon}")


def validate_bbox(bbox: BBox) -> None:
    area = bbox.area_km2()
    if area > MAX_BBOX_AREA_KM2:
        raise ToolInputError(
            ErrorCode.INVALID_BBOX,
            f"bbox area {area:,.0f} km2 exceeds the {MAX_BBOX_AREA_KM2:,.0f} km2 cap; "
            f"narrow the request",
        )


def validate_time_window(start: datetime, end: datetime) -> None:
    if start >= end:
        raise ToolInputError(ErrorCode.INVALID_TIME_WINDOW,
                             "start_time must be before end_time")
    if end - start > timedelta(days=MAX_TIME_WINDOW_DAYS):
        raise ToolInputError(
            ErrorCode.INVALID_TIME_WINDOW,
            f"time window exceeds {MAX_TIME_WINDOW_DAYS} days",
        )


class ToolRun:
    """Times a tool call and accumulates source attempts."""

    def __init__(self, tool: str, primary_source: str | None = None):
        self.tool = tool
        self.request_id = f"tr-{uuid.uuid4().hex[:10]}"
        self.started_at = utcnow()
        self._t0 = time.perf_counter()
        self.resolution = SourceResolution(primary_source=primary_source)

    def attempt(self, source_id: str, outcome: str, detail: str | None = None,
                duration_ms: int | None = None) -> None:
        self.resolution.attempts.append(
            SourceAttempt(source_id=source_id, outcome=outcome,
                          detail=detail, duration_ms=duration_ms))

    def resolved(self, source_id: str, *, fallback_reason: str | None = None) -> None:
        self.resolution.actual_source = source_id
        if (self.resolution.primary_source
                and source_id != self.resolution.primary_source):
            self.resolution.fallback_used = True
            self.resolution.fallback_reason = fallback_reason

    def timing(self) -> Timing:
        end = utcnow()
        return Timing(started_at=self.started_at, finished_at=end,
                      duration_ms=int((time.perf_counter() - self._t0) * 1000))

    def envelope(self, status: EnvelopeStatus, **kw: Any) -> OrcaEnvelope:
        return OrcaEnvelope(
            status=status, tool=self.tool, request_id=self.request_id,
            source_resolution=self.resolution, timing=self.timing(), **kw)

    def failure(self, code: ErrorCode, detail: str, subject: str | None = None,
                source_id: str | None = None) -> OrcaEnvelope:
        from ..schemas.errors import status_for
        err = OrcaError(code=code, detail=detail, subject=subject,
                        source_id=source_id, tool=self.tool)
        return self.envelope(status_for(code), errors=[err])


def collect_point_parameters(tool: str, parameters, lat: float, lon: float,
                             valid_time, fetch, source_id: str):
    """Single-source point query (thin wrapper over the multi-source form)."""
    return collect_from_sources(tool, parameters, lat, lon, valid_time,
                                [(source_id, fetch)])


#: Codes that make a result unusable FOR THE REQUESTED TIME, and therefore
#: justify trying the next source. Distinct from transport failures: the primary
#: answered correctly, it simply does not cover what was asked for.
_UNUSABLE_FOR_REQUEST = "unusable_for_request"


def collect_from_sources(tool: str, parameters, lat: float, lon: float,
                         valid_time, sources, *, fallback_on_stale: bool = True):
    """Point query across an ordered list of sources.

    `sources` is [(source_id, fetch), ...] in preference order. For each
    parameter the first source is tried; the next is tried only when the result
    is unusable, and any switch is recorded in `source_resolution` so the answer
    can state which source actually served it.

    Fallback is attempted on transport failure (SOURCE_UNAVAILABLE, TIMEOUT,
    RATE_LIMITED), on NO_DATA, and -- when `fallback_on_stale` -- on results that
    fall outside the requested window. It is NEVER attempted on AUTH_REQUIRED:
    a credential problem is not fixed by silently switching authority.
    """
    from ..schemas.enums import EnvelopeStatus
    from ..schemas.errors import ErrorCode, FALLBACK_CODES, OrcaError

    eligible = set(FALLBACK_CODES) | {ErrorCode.NO_DATA}
    if fallback_on_stale:
        eligible |= {ErrorCode.STALE_DATA, ErrorCode.INSUFFICIENT_COVERAGE}

    primary_id = sources[0][0] if sources else None
    run = ToolRun(tool, primary_source=primary_id)
    try:
        validate_point(lat, lon)
    except ToolInputError as exc:
        return run.failure(exc.code, exc.detail)

    data, provenance, errors, notes = [], [], [], []
    satisfied = 0
    served_by: set[str] = set()

    def _distance_from_request(res) -> float:
        """How far the served value sits from the requested time, in seconds."""
        best = None
        for obs in getattr(res, "observations", []):
            vt = getattr(getattr(obs, "temporal", None), "valid_time", None)
            if vt is None:
                continue
            d = abs((vt - valid_time).total_seconds())
            best = d if best is None else min(best, d)
        return best if best is not None else float("inf")

    for param in parameters:
        attempts: list[tuple[str, object]] = []
        chosen = None
        chosen_distance = float("inf")
        for source_id, fetch in sources:
            try:
                res = fetch(source_id, param)
            except Exception as exc:
                code = getattr(exc, "code", ErrorCode.ADAPTER_ERROR)
                detail = getattr(exc, "detail", str(exc))
                run.attempt(source_id, code.value, detail[:160])
                attempts.append((source_id, OrcaError(
                    code=code, subject=param, tool=tool, detail=detail[:300],
                    source_id=source_id, severity="warning")))
                if code is ErrorCode.AUTH_REQUIRED or code not in eligible:
                    break
                continue

            unusable = any(c in eligible for c in res.codes)
            run.attempt(source_id, "degraded" if unusable else "success",
                        f"{param} via {res.dataset_id}")
            attempts.append((source_id, res))
            if not unusable:
                chosen = (source_id, res)
                break
            # Every source so far is degraded. Keep whichever sits closest to the
            # requested time -- a 2020 archive value is not equivalent to one from
            # last week just because both are flagged stale.
            d = _distance_from_request(res)
            if d < chosen_distance:
                chosen, chosen_distance = (source_id, res), d

        if chosen is None:
            errors.extend(a for _, a in attempts if isinstance(a, OrcaError))
            continue

        source_id, res = chosen
        satisfied += 1
        served_by.add(source_id)
        data.extend(res.observations)
        provenance.extend(res.provenance)

        used_fallback = primary_id is not None and source_id != primary_id
        if used_fallback:
            reason = next((a.code.value for sid, a in attempts
                           if sid == primary_id and isinstance(a, OrcaError)),
                          "unusable for the requested time")
            for pv in res.provenance:
                pv.fallback_used = True
                pv.fallback_reason = reason
            notes.append({"code": "FALLBACK_USED", "subject": param,
                          "detail": f"{primary_id} could not serve {param} "
                                    f"({reason}); used {source_id}"})
        for code in res.codes:
            errors.append(OrcaError(code=code, subject=param, tool=tool,
                                    source_id=source_id, severity="warning",
                                    detail=f"{param} served from {res.dataset_id}"))
        for n in res.notes:
            notes.append({"code": "SOURCE_NOTE", "subject": param, "detail": n})

    if satisfied:
        actual = next(iter(served_by)) if len(served_by) == 1 else ",".join(
            sorted(served_by))
        run.resolved(actual, fallback_reason=(
            "primary could not serve the requested time"
            if primary_id and actual != primary_id else None))

    if satisfied == 0:
        codes = {e.code for e in errors}
        code = (ErrorCode.AUTH_REQUIRED if ErrorCode.AUTH_REQUIRED in codes
                else ErrorCode.DATASET_UNAVAILABLE
                if ErrorCode.DATASET_UNAVAILABLE in codes
                else ErrorCode.NO_DATA if ErrorCode.NO_DATA in codes
                else ErrorCode.SOURCE_UNAVAILABLE)
        env = run.failure(code, f"no data for {list(parameters)} at {lat},{lon}")
        env.errors.extend(errors)
        return env

    degraded = (any(e.code in (ErrorCode.STALE_DATA, ErrorCode.INSUFFICIENT_COVERAGE)
                    for e in errors) or satisfied < len(parameters))
    return run.envelope(
        EnvelopeStatus.PARTIAL if degraded else EnvelopeStatus.SUCCESS,
        data=data, provenance=provenance, errors=errors, warnings=notes,
        quality={"parameters_requested": len(parameters),
                 "parameters_satisfied": satisfied,
                 "sources_used": sorted(served_by)})
