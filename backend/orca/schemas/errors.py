"""Canonical error taxonomy. See 05_CANONICAL_DATA_SCHEMA.md section 3.2."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from .enums import EnvelopeStatus


class ErrorCode(StrEnum):
    # availability
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    DATASET_UNAVAILABLE = "DATASET_UNAVAILABLE"
    # presence (valid outcomes, not failures)
    NO_DATA = "NO_DATA"
    NO_ACTIVE_WARNING = "NO_ACTIVE_WARNING"
    NO_ACTIVE_CYCLONE = "NO_ACTIVE_CYCLONE"
    NO_BOUNDARIES_FOUND = "NO_BOUNDARIES_FOUND"
    # quality
    STALE_DATA = "STALE_DATA"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
    # representation
    RASTER_ONLY = "RASTER_ONLY"
    VECTOR_UNAVAILABLE = "VECTOR_UNAVAILABLE"
    # cross-source
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    AMBIGUOUS_AREA = "AMBIGUOUS_AREA"
    # input
    INVALID_LOCATION = "INVALID_LOCATION"
    INVALID_BBOX = "INVALID_BBOX"
    INVALID_TIME_WINDOW = "INVALID_TIME_WINDOW"
    # internal
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    ADAPTER_ERROR = "ADAPTER_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"


#: Codes that mean "we reached the source, it just had nothing for you".
PRESENCE_CODES = frozenset({
    ErrorCode.NO_DATA,
    ErrorCode.NO_ACTIVE_WARNING,
    ErrorCode.NO_ACTIVE_CYCLONE,
    ErrorCode.NO_BOUNDARIES_FOUND,
})

#: Codes for which a retry can plausibly succeed.
RETRYABLE_CODES = frozenset({
    ErrorCode.SOURCE_UNAVAILABLE,
    ErrorCode.TIMEOUT,
    ErrorCode.RATE_LIMITED,
})

#: Codes for which a FALLBACK SOURCE may be attempted.
#: AUTH_REQUIRED is deliberately absent: a credential problem is not fixed by
#: swapping authority, and doing so silently would be misleading.
FALLBACK_CODES = frozenset({
    ErrorCode.SOURCE_UNAVAILABLE,
    ErrorCode.TIMEOUT,
    ErrorCode.RATE_LIMITED,
})

_STATUS_BY_CODE = {
    ErrorCode.STALE_DATA: EnvelopeStatus.PARTIAL,
    ErrorCode.INSUFFICIENT_COVERAGE: EnvelopeStatus.PARTIAL,
    ErrorCode.RASTER_ONLY: EnvelopeStatus.PARTIAL,
    ErrorCode.VECTOR_UNAVAILABLE: EnvelopeStatus.PARTIAL,
    ErrorCode.CONFLICTING_SOURCES: EnvelopeStatus.PARTIAL,
    ErrorCode.AMBIGUOUS_AREA: EnvelopeStatus.PARTIAL,
}

#: Legacy per-tool codes from 04_ORCA_TOOL_CONTRACTS.md v0.1 -> canonical.
LEGACY_CODE_MAP = {
    "STALE_WARNING": ErrorCode.STALE_DATA,
    "STALE_TRACK": ErrorCode.STALE_DATA,
    "STALE_PRODUCT": ErrorCode.STALE_DATA,
    "NO_LIGHTNING_DATA": ErrorCode.NO_DATA,
    "NO_OBSERVATIONS": ErrorCode.NO_DATA,
    "NO_PFZ_FOR_TIME": ErrorCode.NO_DATA,
    "BOUNDARY_DATASET_UNAVAILABLE": ErrorCode.DATASET_UNAVAILABLE,
    "AMBIGUOUS_AFFECTED_AREA": ErrorCode.AMBIGUOUS_AREA,
}


def status_for(code: ErrorCode) -> EnvelopeStatus:
    """Envelope status implied by a code, in isolation."""
    if code in PRESENCE_CODES:
        return EnvelopeStatus.EMPTY
    return _STATUS_BY_CODE.get(code, EnvelopeStatus.ERROR)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OrcaError(BaseModel):
    code: ErrorCode
    severity: str = "error"          # info | warning | error
    subject: str | None = None       # what was being retrieved
    detail: str = ""
    source_id: str | None = None
    tool: str | None = None
    occurred_at: datetime = Field(default_factory=_now)
    user_message_id: str | None = None

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE_CODES

    def model_post_init(self, _ctx) -> None:
        if self.code in PRESENCE_CODES and self.severity == "error":
            # "no warning in force" is a result, not a failure.
            object.__setattr__(self, "severity", "info")
