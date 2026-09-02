"""Adapter metadata parsing and validation, offline against recorded payloads."""
import json
import pathlib

import pytest

from backend.orca.adapters.incois_erddap.client import encode_query
from backend.orca.adapters.incois_erddap.metadata import parse_info

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures" / "upstream" / "incois_erddap"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


class TestQueryEncoding:
    def test_selector_brackets_are_encoded(self):
        # Raw brackets are rejected by the servlet container with an HTML 400
        # before ERDDAP ever parses the query (observed live 2026-09-02).
        out = encode_query("TEMP[(2026-07-30T00:00:00Z)][0:0][(9.5):(9.5)]")
        assert "[" not in out and "]" not in out
        assert "%5B" in out and "%5D" in out

    def test_selector_structure_is_preserved(self):
        out = encode_query("TEMP[(9.5):(9.5)],SAL[0:0]")
        for ch in "(),:":
            assert ch in out


class TestMetadataValidation:
    def test_good_dataset_is_usable_and_units_are_read_not_assumed(self):
        m = parse_info("incois_argo_10d_VAM", _load("info_incois_argo_10d_VAM.json"))
        assert m.usable
        assert m.dim_order == ["time", "ZAX", "latitude", "longitude"]
        assert m.variables["TEMP"].units == "degs"      # NOT assumed to be degC
        assert m.variables["TEMP"].fill_value == -9999.0
        assert m.time_coverage_end.startswith("2026-07-30")

    def test_broken_latitude_axis_is_detected(self):
        # NOAA_AVHRR_datasets publishes latitude as array indices 0..399.
        m = parse_info("NOAA_AVHRR_datasets", _load("info_NOAA_AVHRR_datasets.json"))
        assert m.usable is False
        assert any("not in degrees" in i for i in m.issues)

    def test_archive_dataset_reports_how_far_behind_it_is(self):
        m = parse_info("incois_oceansat2_datasets",
                       _load("info_incois_oceansat2_datasets.json"))
        assert m.days_behind() > 1500          # coverage ends 2020-05-01
