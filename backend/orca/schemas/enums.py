"""Canonical enumerations. See docs 05_CANONICAL_DATA_SCHEMA.md."""
from enum import StrEnum


class ValueKind(StrEnum):
    OBSERVED = "observed"
    FORECAST = "forecast"
    DERIVED = "derived"
    MODEL = "model"
    INTERPRETATION = "interpretation"


class Representation(StrEnum):
    POINT = "point"
    GRID = "grid"
    RASTER = "raster"
    VECTOR = "vector"
    BULLETIN = "bulletin"


class EnvelopeStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    EMPTY = "empty"     # valid query, nothing to return -- NOT a failure
    ERROR = "error"


class QualityFlag(StrEnum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    SUSPECT = "suspect"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class Freshness(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    EXPIRED = "expired"


class Representativeness(StrEnum):
    """What a value actually represents in time.

    This is the field that stops a 10-day analysis being used as a
    next-morning forecast. See 11_GEOSPATIAL_REASONING_SPEC.md section 8.2.
    """
    INSTANTANEOUS = "instantaneous"
    HOURLY_MEAN = "hourly_mean"
    DAILY_COMPOSITE = "daily_composite"
    THREE_DAY_MEAN = "3day_mean"
    WEEKLY_MEAN = "weekly_mean"
    TEN_DAY_MEAN = "10day_mean"
    MONTHLY_MEAN = "monthly_mean"
    BULLETIN_PERIOD = "bulletin_period"


class Domain(StrEnum):
    SAFETY = "SAFETY"
    FISHING_SUITABILITY = "FISHING_SUITABILITY"
    ECOLOGICAL = "ECOLOGICAL"
    REGULATORY = "REGULATORY"


class Verdict(StrEnum):
    FAVOURABLE = "FAVOURABLE"
    MARGINAL = "MARGINAL"
    UNFAVOURABLE = "UNFAVOURABLE"
    UNSAFE = "UNSAFE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RegulatoryStatus(StrEnum):
    PERMITTED = "PERMITTED"
    RESTRICTED = "RESTRICTED"
    PROHIBITED = "PROHIBITED"
    UNKNOWN = "UNKNOWN"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Disposition(StrEnum):
    AUTO_RELEASE = "AUTO_RELEASE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
