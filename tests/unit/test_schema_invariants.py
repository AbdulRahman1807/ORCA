"""Canonical schema invariants (05_CANONICAL_DATA_SCHEMA.md)."""
import pytest
from datetime import datetime, timezone

from backend.orca.schemas.core import (
    BBox, Provenance, SpatialRef, TemporalRef, haversine_km,
)
from backend.orca.schemas.data import Observation
from backend.orca.schemas.enums import EnvelopeStatus, ValueKind
from backend.orca.schemas.envelope import OrcaEnvelope
from backend.orca.schemas.errors import (
    ErrorCode, FALLBACK_CODES, OrcaError, PRESENCE_CODES, status_for,
)

UTC = timezone.utc


def _prov(pid="pv-1", kind=ValueKind.OBSERVED, **kw):
    return Provenance(provenance_id=pid, parameter="sst", value_kind=kind,
                      source="INCOIS ERDDAP", source_id="S-02", **kw)


class TestProvenanceInvariants:
    def test_derived_value_requires_derivation(self):
        with pytest.raises(ValueError, match="SCHEMA_VALIDATION_FAILED"):
            _prov(kind=ValueKind.DERIVED)

    def test_envelope_rejects_unresolved_provenance_id(self):
        obs = Observation(parameter="sst", value=28.4, unit="degC",
                          spatial=SpatialRef.point(9.9, 76.1),
                          temporal=TemporalRef(valid_time=datetime.now(UTC)),
                          provenance_id="pv-missing")
        with pytest.raises(ValueError, match="unresolved provenance_id"):
            OrcaEnvelope(status=EnvelopeStatus.SUCCESS, tool="get_sst", data=[obs])

    def test_envelope_accepts_complete_join(self):
        obs = Observation(parameter="sst", value=28.4, unit="degC",
                          spatial=SpatialRef.point(9.9, 76.1),
                          temporal=TemporalRef(valid_time=datetime.now(UTC)),
                          provenance_id="pv-1")
        env = OrcaEnvelope(status=EnvelopeStatus.SUCCESS, tool="get_sst",
                           data=[obs], provenance=[_prov()])
        assert env.ok


class TestTimeDiscipline:
    def test_naive_datetime_rejected(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            TemporalRef(valid_time=datetime(2026, 9, 3))


class TestErrorSemantics:
    def test_no_active_warning_is_a_result_not_a_failure(self):
        e = OrcaError(code=ErrorCode.NO_ACTIVE_WARNING, subject="marine_warning")
        assert e.severity == "info"
        assert status_for(e.code) is EnvelopeStatus.EMPTY

    def test_auth_required_is_never_retried_or_fallen_back(self):
        assert ErrorCode.AUTH_REQUIRED not in FALLBACK_CODES
        assert not OrcaError(code=ErrorCode.AUTH_REQUIRED).retryable

    def test_no_data_differs_from_source_unavailable(self):
        assert ErrorCode.NO_DATA in PRESENCE_CODES
        assert ErrorCode.SOURCE_UNAVAILABLE not in PRESENCE_CODES
        assert status_for(ErrorCode.NO_DATA) is EnvelopeStatus.EMPTY
        assert status_for(ErrorCode.SOURCE_UNAVAILABLE) is EnvelopeStatus.ERROR

    def test_representation_codes_are_partial_not_error(self):
        assert status_for(ErrorCode.RASTER_ONLY) is EnvelopeStatus.PARTIAL


class TestGeodesy:
    def test_distance_uses_great_circle_not_degrees(self):
        # Kochi -> Kavaratti, independently ~402 km
        d = haversine_km(9.93, 76.26, 10.57, 72.64)
        assert 395 < d < 410

    def test_one_degree_of_longitude_shrinks_with_latitude(self):
        assert haversine_km(0, 0, 0, 1) > haversine_km(60, 0, 60, 1)

    def test_bbox_area_is_not_degree_arithmetic(self):
        b = BBox(min_lat=8, min_lon=75, max_lat=12, max_lon=78)
        naive = 4 * 3 * 111.32 ** 2          # what a degree-based bug would give
        assert abs(b.area_km2() - naive) / naive > 0.005
        assert 140_000 < b.area_km2() < 152_000

    def test_inverted_bbox_rejected(self):
        with pytest.raises(ValueError, match="INVALID_BBOX"):
            BBox(min_lat=12, min_lon=75, max_lat=8, max_lon=78)


class TestSpatialRef:
    def test_out_of_range_point_rejected(self):
        with pytest.raises(ValueError, match="INVALID_LOCATION"):
            SpatialRef.point(lat=95, lon=76)
