"""CMEMS adapter: store decoding, coordinate handling, error mapping."""
import json
import pathlib
from datetime import datetime, timezone

import numpy as np
import pytest

from backend.orca.adapters.cmems.bindings import BINDINGS
from backend.orca.adapters.cmems.client import canonical_code
from backend.orca.adapters.cmems.store import (
    ZarrError, ZarrStore, decode_time, nearest_index,
)
from backend.orca.schemas.errors import ErrorCode

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures" / "upstream" / "cmems"
UTC = timezone.utc


class _FakeHttp:
    """Serves the recorded .zmetadata; every other key 404s."""

    def __init__(self, meta):
        self._meta = meta

    def get_bytes(self, url):
        if url.endswith("/.zmetadata"):
            return json.dumps(self._meta).encode()
        raise ZarrError("not_found", url.rsplit("/", 1)[-1], 404)


@pytest.fixture
def store():
    meta = json.loads((FIXTURES / "wav_zmetadata.json").read_text())
    return ZarrStore("https://example.invalid/wav.zarr", _FakeHttp(meta))


class TestStoreMetadata:
    def test_array_metadata_is_read_not_assumed(self, store):
        m = store.array("VHM0")
        assert m.shape == (11288, 2041, 4320)
        assert m.chunks == (1, 512, 2048)
        assert m.dims == ("time", "latitude", "longitude")
        assert m.units == "m"

    def test_scale_factor_and_offset_are_honoured(self, store):
        m = store.array("VHM0")
        # CMEMS stores VHM0 as int16 with a 0.01 scale factor. Reading the raw
        # integer as metres would be wrong by two orders of magnitude.
        assert m.dtype == np.dtype("<i2")
        assert m.scale_factor == pytest.approx(0.01, rel=1e-3)
        assert m.add_offset == 0.0

    def test_missing_array_is_reported_not_guessed(self, store):
        with pytest.raises(ZarrError) as e:
            store.array("NOT_A_VARIABLE")
        assert e.value.kind == "not_found"

    def test_omitted_chunk_reads_as_missing_not_zero(self, store):
        # Zarr omits all-fill chunks; the store must return None, never 0.0,
        # which would read as "calm sea" instead of "no data".
        meta = store.array("VHM0")
        assert store._chunk(meta, (0, 0, 0)) is None


class TestCoordinates:
    def test_nearest_index_returns_residual(self):
        coord = np.array([9.0, 9.25, 9.5, 9.75, 10.0])
        i, resid = nearest_index(coord, 9.60)
        assert i == 2 and resid == pytest.approx(-0.10, abs=1e-9)

    def test_decode_time_handles_cf_units(self):
        t = decode_time(np.array([0, 24]), "hours since 1950-01-01")
        assert t[0] == datetime(1950, 1, 1, tzinfo=UTC)
        assert t[1] == datetime(1950, 1, 2, tzinfo=UTC)

    def test_unsupported_time_unit_raises(self):
        with pytest.raises(ZarrError):
            decode_time(np.array([0]), "fortnights since 1950-01-01")


class TestErrorMapping:
    @pytest.mark.parametrize("kind,expected", [
        ("forbidden", ErrorCode.AUTH_REQUIRED),
        ("not_found", ErrorCode.NO_DATA),
        ("unavailable", ErrorCode.SOURCE_UNAVAILABLE),
        ("decode", ErrorCode.ADAPTER_ERROR),
    ])
    def test_store_failures_map_to_canonical_codes(self, kind, expected):
        assert canonical_code(ZarrError(kind, "x")) is expected


class TestBindings:
    def test_wave_height_binds_to_the_verified_dataset(self):
        b = BINDINGS["significant_wave_height"][0]
        assert b.dataset_id == "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i_202411"
        assert b.variable == "VHM0"
        assert b.canonical_unit == "m"

    def test_wind_is_bound_as_an_observation_product(self):
        # The wind product has no forecast horizon. Binding it as a forecast
        # would let a future query silently return yesterday's observation.
        b = BINDINGS["eastward_wind"][0]
        assert "obs-wind" in b.dataset_id
        assert "no forecast horizon" in (b.note or "")

    def test_every_binding_declares_a_canonical_unit(self):
        for param, bs in BINDINGS.items():
            for b in bs:
                assert b.canonical_unit, param


class TestMissingChunkSignalling:
    """404 means absent. 403 must never be silently read as absent.

    On the CMEMS buckets a denied request and a nonexistent key return an
    identical AccessDenied body, and the same chunk has been observed returning
    200 and later 403 within one session. Treating a denial as "no data" would
    silently drop real observations.
    """

    @pytest.mark.parametrize("kind", ["not_found"])
    def test_omitted_chunk_reads_as_absent(self, kind):
        meta = json.loads((FIXTURES / "wav_zmetadata.json").read_text())

        class Http:
            def get_bytes(self, url):
                if url.endswith("/.zmetadata"):
                    return json.dumps(meta).encode()
                raise ZarrError(kind, url.rsplit("/", 1)[-1])

        store = ZarrStore("https://example.invalid/wav.zarr", Http())
        assert store._chunk(store.array("VHM0"), (0, 0, 0)) is None

    def test_denied_chunk_raises_rather_than_reading_as_absent(self):
        meta = json.loads((FIXTURES / "wav_zmetadata.json").read_text())

        class Http:
            def get_bytes(self, url):
                if url.endswith("/.zmetadata"):
                    return json.dumps(meta).encode()
                raise ZarrError("forbidden", "AccessDenied")

        store = ZarrStore("https://example.invalid/wav.zarr", Http())
        with pytest.raises(ZarrError) as e:
            store._chunk(store.array("VHM0"), (0, 0, 0))
        assert e.value.kind == "forbidden"

    def test_metadata_rejection_is_still_an_auth_failure(self):
        class Http:
            def get_bytes(self, url):
                raise ZarrError("forbidden", "denied")

        store = ZarrStore("https://example.invalid/wav.zarr", Http())
        with pytest.raises(ZarrError) as e:
            store.array("VHM0")
        assert e.value.kind == "forbidden"
