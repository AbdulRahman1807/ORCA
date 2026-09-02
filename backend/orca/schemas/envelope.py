"""Transport wrapper for every capability tool result."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .core import Provenance, utcnow
from .data import Conflict, DataObject
from .enums import EnvelopeStatus
from .errors import ErrorCode, OrcaError, PRESENCE_CODES, status_for

ENVELOPE_VERSION = "1.0"


class SourceAttempt(BaseModel):
    source_id: str
    outcome: str
    duration_ms: int | None = None
    detail: str | None = None


class SourceResolution(BaseModel):
    primary_source: str | None = None
    actual_source: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    attempts: list[SourceAttempt] = Field(default_factory=list)


class Timing(BaseModel):
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class OrcaEnvelope(BaseModel):
    envelope_version: str = ENVELOPE_VERSION
    status: EnvelopeStatus
    tool: str
    request_id: str | None = None
    run_id: str | None = None

    data: list[DataObject] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[Conflict] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[OrcaError] = Field(default_factory=list)

    source_resolution: SourceResolution = Field(default_factory=SourceResolution)
    timing: Timing = Field(default_factory=Timing)
    cache: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _provenance_join_is_complete(self) -> "OrcaEnvelope":
        """Invariant: every data object resolves to exactly one provenance record."""
        known = {p.provenance_id for p in self.provenance}
        missing = sorted(
            {getattr(d, "provenance_id", None) for d in self.data} - known - {None}
        )
        if missing:
            raise ValueError(
                f"SCHEMA_VALIDATION_FAILED: unresolved provenance_id(s): {missing}"
            )
        return self

    # -- construction helpers -------------------------------------------------

    @classmethod
    def failure(cls, tool: str, code: ErrorCode, detail: str = "",
                subject: str | None = None, source_id: str | None = None,
                **kw: Any) -> "OrcaEnvelope":
        err = OrcaError(code=code, detail=detail, subject=subject,
                        source_id=source_id, tool=tool)
        return cls(status=status_for(code), tool=tool, errors=[err], **kw)

    @classmethod
    def empty(cls, tool: str, code: ErrorCode, detail: str = "",
              subject: str | None = None, **kw: Any) -> "OrcaEnvelope":
        assert code in PRESENCE_CODES, "empty() is for presence codes only"
        return cls.failure(tool, code, detail, subject, **kw)

    @property
    def ok(self) -> bool:
        return self.status in (EnvelopeStatus.SUCCESS, EnvelopeStatus.PARTIAL)

    def codes(self) -> list[ErrorCode]:
        return [e.code for e in self.errors]
