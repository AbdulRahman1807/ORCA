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
    """Shared body for point-query capability tools.

    `fetch(parameter) -> result` must return an object with `.observations`,
    `.provenance`, `.codes`, `.notes` and `.dataset_id`, and raise an exception
    carrying a canonical `.code` on failure.
    """
    from ..schemas.enums import EnvelopeStatus
    from ..schemas.errors import ErrorCode, OrcaError

    run = ToolRun(tool, primary_source=source_id)
    try:
        validate_point(lat, lon)
    except ToolInputError as exc:
        return run.failure(exc.code, exc.detail)

    data, provenance, errors, notes = [], [], [], []
    satisfied = 0

    for param in parameters:
        try:
            res = fetch(param)
        except Exception as exc:                       # adapters raise typed errors
            code = getattr(exc, "code", ErrorCode.ADAPTER_ERROR)
            detail = getattr(exc, "detail", str(exc))
            run.attempt(source_id, code.value, detail[:160])
            errors.append(OrcaError(code=code, subject=param, tool=tool,
                                    detail=detail[:300], source_id=source_id,
                                    severity="warning"))
            continue

        satisfied += 1
        data.extend(res.observations)
        provenance.extend(res.provenance)
        run.attempt(source_id, "success", f"{param} via {res.dataset_id}")
        for code in res.codes:
            errors.append(OrcaError(code=code, subject=param, tool=tool,
                                    source_id=source_id, severity="warning",
                                    detail=f"{param} served from {res.dataset_id}"))
        for n in res.notes:
            notes.append({"code": "SOURCE_NOTE", "subject": param, "detail": n})

    if satisfied:
        run.resolved(source_id)

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
                 "parameters_satisfied": satisfied})
