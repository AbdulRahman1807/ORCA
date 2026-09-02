"""Canonical parameter -> ERDDAP dataset/variable bindings.

Bindings are DATA, not logic. Agents never see this file; they ask for a
canonical parameter and the adapter decides which dataset serves it.

Every binding records what the product actually represents in time, because a
10-day analysis must never be presented as a next-morning forecast
(11_GEOSPATIAL_REASONING_SPEC.md section 8.2).
"""
from __future__ import annotations

from dataclasses import dataclass

from ...schemas.enums import Representativeness as R


@dataclass(frozen=True, slots=True)
class Binding:
    parameter: str          # canonical ORCA parameter name
    dataset_id: str
    variable: str           # variable name as published by the dataset
    representativeness: R
    depth_axis: str | None = None      # ZAX / depth / zlev, if the dataset has one
    canonical_unit: str | None = None  # expected unit, for a fidelity check
    note: str | None = None


#: Ordered by preference. The adapter tries each in turn and records which one
#: served the request; it never silently substitutes a different PARAMETER.
BINDINGS: dict[str, list[Binding]] = {
    "temperature": [
        Binding("temperature", "incois_argo_10d_VAM", "TEMP", R.TEN_DAY_MEAN,
                depth_axis="ZAX", canonical_unit="degC",
                note="Argo variational-analysis field; published unit is 'degs'"),
        Binding("temperature", "incois_argo_10day_McCreary", "T_ANALYZED", R.TEN_DAY_MEAN,
                depth_axis="ZAX", canonical_unit="degC",
                note="Kessler-McCreary objective analysis"),
        Binding("temperature", "incois_argo_mnt_VAM", "TEMP", R.MONTHLY_MEAN,
                depth_axis="ZAX", canonical_unit="degC"),
    ],
    "salinity": [
        Binding("salinity", "incois_argo_10d_VAM", "SAL", R.TEN_DAY_MEAN,
                depth_axis="ZAX", canonical_unit="PSU"),
        Binding("salinity", "incois_argo_10day_McCreary", "S_ANALYZED", R.TEN_DAY_MEAN,
                depth_axis="ZAX", canonical_unit="PSU"),
        Binding("salinity", "incois_argo_mnt_VAM", "SAL", R.MONTHLY_MEAN,
                depth_axis="ZAX", canonical_unit="PSU"),
    ],
    "sst": [
        Binding("sst", "NOAA_AVHRR_AMSR_datasets", "sst", R.DAILY_COMPOSITE,
                depth_axis="zlev", canonical_unit="degC",
                note="ARCHIVE ONLY: coverage ends 2011-10-04"),
    ],
    "sst_anomaly": [
        Binding("sst_anomaly", "NOAA_AVHRR_AMSR_datasets", "anom", R.DAILY_COMPOSITE,
                depth_axis="zlev", canonical_unit="degC",
                note="ARCHIVE ONLY: coverage ends 2011-10-04"),
    ],
    "chlorophyll_a": [
        Binding("chlorophyll_a", "incois_oceansat2_datasets", "CHL", R.DAILY_COMPOSITE,
                canonical_unit="mg m-3",
                note="ARCHIVE ONLY: coverage ends 2020-05-01"),
    ],
    "kd490": [
        Binding("kd490", "incois_oceansat2_datasets", "KD490", R.DAILY_COMPOSITE,
                canonical_unit="m-1", note="ARCHIVE ONLY"),
    ],
    "tsm": [
        Binding("tsm", "incois_oceansat2_datasets", "TSM", R.DAILY_COMPOSITE,
                canonical_unit="mg L-1", note="ARCHIVE ONLY"),
    ],
    "wind_speed": [
        Binding("wind_speed", "ascat_daily_datasets", "wind_speed", R.DAILY_COMPOSITE,
                depth_axis="depth", canonical_unit="m s-1",
                note="ARCHIVE ONLY: coverage ends 2023-05-21"),
    ],
    "eastward_wind": [
        Binding("eastward_wind", "ascat_daily_datasets", "eastward_wind", R.DAILY_COMPOSITE,
                depth_axis="depth", canonical_unit="m s-1", note="ARCHIVE ONLY"),
    ],
    "northward_wind": [
        Binding("northward_wind", "ascat_daily_datasets", "northward_wind",
                R.DAILY_COMPOSITE, depth_axis="depth", canonical_unit="m s-1",
                note="ARCHIVE ONLY"),
    ],
    "mixed_layer_depth": [
        Binding("mixed_layer_depth", "incois_valueadded_products_datasets", "MLD",
                R.TEN_DAY_MEAN, canonical_unit="m", note="ARCHIVE ONLY; unit unpublished"),
    ],
}

#: Unit strings as published by INCOIS, mapped to ORCA canonical units.
#: Units are READ from dataset metadata; this table only normalises spelling.
UNIT_ALIASES: dict[str, str] = {
    "degs": "degC",
    "degree_C": "degC",
    "degrees C": "degC",
    "Degree C": "degC",
    "degrees_C": "degC",
    "PSU": "PSU",
    "psu": "PSU",
    "mg/m3": "mg m-3",
    "meter-1": "m-1",
    "mg/L": "mg L-1",
    "m/s": "m s-1",
    "METERS": "m",
    "meters": "m",
    "m": "m",
}


def canonical_unit(published: str | None) -> str | None:
    if published is None:
        return None
    return UNIT_ALIASES.get(published.strip(), published.strip())
