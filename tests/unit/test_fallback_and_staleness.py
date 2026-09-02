"""Multi-source fallback and per-parameter staleness policy."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.orca.assessment.staleness import usable_age_days
from backend.orca.geospatial.temporal import Alignment, align
from backend.orca.schemas.core import Provenance, SpatialRef, TemporalRef
from backend.orca.schemas.data import Observation
from backend.orca.schemas.enums import Domain, Representativeness as R, ValueKind
from backend.orca.schemas.errors import ErrorCode
from backend.orca.tools.base import collect_from_sources

UTC = timezone.utc
WIN_START = datetime(2026, 9, 3, 0, 30, tzinfo=UTC)
WIN_END = datetime(2026, 9, 3, 4, 30, tzinfo=UTC)


class _Result:
    def __init__(self, value, valid_time, codes=(), dataset="ds"):
        pid = f"pv-{dataset}"
        spatial = SpatialRef.point(9.93, 76.26)
        temporal = TemporalRef(valid_time=valid_time,
                               representativeness=R.DAILY_COMPOSITE)
        self.observations = [Observation(parameter="sst", value=value, unit="degC",
                                         spatial=spatial, temporal=temporal,
                                         provenance_id=pid)]
        self.provenance = [Provenance(provenance_id=pid, parameter="sst",
                                      value_kind=ValueKind.OBSERVED, unit="degC",
                                      source=dataset, source_id=dataset,
                                      spatial=spatial, temporal=temporal)]
        self.codes = list(codes)
        self.notes = []
        self.dataset_id = dataset


class _Fail(Exception):
    def __init__(self, code):
        self.code = code
        self.detail = code.value


class TestFallbackSelection:
    def test_healthy_primary_is_used_and_not_marked_as_fallback(self):
        env = collect_from_sources(
            "get_sst", ["sst"], 9.93, 76.26, WIN_START,
            [("S-A", lambda sid, p: _Result(28.0, WIN_START, dataset="A")),
             ("S-B", lambda sid, p: _Result(27.0, WIN_START, dataset="B"))])
        assert env.source_resolution.fallback_used is False
        assert env.data[0].value == 28.0

    def test_unusable_primary_falls_back_and_records_it(self):
        env = collect_from_sources(
            "get_sst", ["sst"], 9.93, 76.26, WIN_START,
            [("S-A", lambda sid, p: _Result(28.0, datetime(2011, 10, 4, tzinfo=UTC),
                                            [ErrorCode.STALE_DATA], "A")),
             ("S-B", lambda sid, p: _Result(27.7, WIN_START, dataset="B"))])
        assert env.source_resolution.fallback_used is True
        assert env.data[0].value == 27.7
        assert any(w["code"] == "FALLBACK_USED" for w in env.warnings)
        assert env.provenance[0].fallback_used is True

    def test_when_all_sources_are_stale_the_closest_in_time_wins(self):
        """A 2011 archive is not equivalent to last week's value."""
        env = collect_from_sources(
            "get_sst", ["sst"], 9.93, 76.26, WIN_START,
            [("S-A", lambda sid, p: _Result(28.0, datetime(2011, 10, 4, tzinfo=UTC),
                                            [ErrorCode.STALE_DATA], "A")),
             ("S-B", lambda sid, p: _Result(27.7, WIN_START - timedelta(days=2),
                                            [ErrorCode.STALE_DATA], "B"))])
        assert env.data[0].value == 27.7

    def test_auth_required_never_triggers_a_fallback(self):
        """A credential problem is not fixed by silently switching authority."""
        calls = []

        def primary(sid, p):
            calls.append(sid)
            raise _Fail(ErrorCode.AUTH_REQUIRED)

        def secondary(sid, p):
            calls.append(sid)
            return _Result(27.7, WIN_START, dataset="B")

        env = collect_from_sources("get_sst", ["sst"], 9.93, 76.26, WIN_START,
                                   [("S-A", primary), ("S-B", secondary)])
        assert calls == ["S-A"]
        assert env.status.value == "error"
        assert ErrorCode.AUTH_REQUIRED in env.codes()


class TestStalenessPolicy:
    def test_ageing_is_asymmetric(self):
        """A value informs the period after it, never the period before it."""
        vt = WIN_START + timedelta(days=3)          # measured AFTER the window
        d = align(vt, R.DAILY_COMPOSITE, window_start=WIN_START, window_end=WIN_END,
                  domain=Domain.FISHING_SUITABILITY, usable_age_days=4.0)
        assert d.alignment is Alignment.OUT_OF_WINDOW

    def test_ocean_colour_tolerance_admits_a_three_day_old_composite(self):
        vt = WIN_START - timedelta(days=3)
        d = align(vt, R.DAILY_COMPOSITE, window_start=WIN_START, window_end=WIN_END,
                  domain=Domain.FISHING_SUITABILITY,
                  usable_age_days=usable_age_days("chlorophyll_ratio_to_local_median"))
        assert d.usable_as_primary

    def test_wind_tolerance_rejects_a_two_day_old_observation(self):
        """An old wind observation cannot describe a future window."""
        vt = WIN_START - timedelta(days=2)
        d = align(vt, R.HOURLY_MEAN, window_start=WIN_START, window_end=WIN_END,
                  domain=Domain.SAFETY, usable_age_days=usable_age_days("wind_speed"))
        assert not d.usable_as_primary

    def test_policy_falls_back_to_a_default(self):
        assert usable_age_days("a_parameter_with_no_policy") == pytest.approx(0.5)
