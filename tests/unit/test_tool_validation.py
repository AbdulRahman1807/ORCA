"""Tool-layer input validation (04_ORCA_TOOL_CONTRACTS.md section 2.5)."""
import pytest
from datetime import datetime, timedelta, timezone

from backend.orca.schemas.core import BBox
from backend.orca.schemas.errors import ErrorCode
from backend.orca.tools.base import (
    ToolInputError, ToolRun, validate_bbox, validate_point, validate_time_window,
)

UTC = timezone.utc


def test_invalid_location():
    with pytest.raises(ToolInputError) as e:
        validate_point(95.0, 76.0)
    assert e.value.code is ErrorCode.INVALID_LOCATION


def test_oversized_bbox_rejected_before_any_upstream_call():
    with pytest.raises(ToolInputError) as e:
        validate_bbox(BBox(min_lat=-40, min_lon=20, max_lat=40, max_lon=140))
    assert e.value.code is ErrorCode.INVALID_BBOX


def test_inverted_time_window():
    now = datetime.now(UTC)
    with pytest.raises(ToolInputError) as e:
        validate_time_window(now, now - timedelta(hours=1))
    assert e.value.code is ErrorCode.INVALID_TIME_WINDOW


def test_oversized_time_window():
    now = datetime.now(UTC)
    with pytest.raises(ToolInputError) as e:
        validate_time_window(now, now + timedelta(days=60))
    assert e.value.code is ErrorCode.INVALID_TIME_WINDOW


def test_fallback_is_recorded_never_silent():
    run = ToolRun("get_sst", primary_source="S-02")
    run.attempt("S-02", "SOURCE_UNAVAILABLE")
    run.attempt("S-07", "success")
    run.resolved("S-07", fallback_reason="SOURCE_UNAVAILABLE")
    assert run.resolution.fallback_used is True
    assert run.resolution.fallback_reason == "SOURCE_UNAVAILABLE"
    assert [a.source_id for a in run.resolution.attempts] == ["S-02", "S-07"]


def test_primary_success_is_not_marked_as_fallback():
    run = ToolRun("get_sst", primary_source="S-02")
    run.resolved("S-02")
    assert run.resolution.fallback_used is False
