"""Canonical parameter -> CMEMS dataset/variable bindings.

Dataset ids and variable names were read from the public CMEMS STAC catalogue
on 2026-09-02, not guessed. Regenerate with scripts/capture_cmems.py.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...schemas.enums import Representativeness as R

ARCO_BASE = "https://s3.waw3-1.cloudferro.com"


@dataclass(frozen=True, slots=True)
class CmemsBinding:
    parameter: str
    product_id: str
    dataset_id: str
    variable: str
    representativeness: R
    canonical_unit: str
    arco_path: str            # bucket/arco/<product>/<dataset>/timeChunked.zarr
    note: str | None = None
    #: Companion variable carrying source-published uncertainty, if any.
    uncertainty_variable: str | None = None
    uncertainty_kind: str | None = None      # std_dev | percent | error

    @property
    def store_url(self) -> str:
        return f"{ARCO_BASE}/{self.arco_path}"


_WAV = "GLOBAL_ANALYSISFORECAST_WAV_001_027"
_WAV_DS = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i_202411"
_WAV_ARCO = f"mdl-arco-time-015/arco/{_WAV}/{_WAV_DS}/timeChunked.zarr"

_SST = "SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001"
_SST_DS = "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
_SST_ARCO = f"mdl-arco-time-045/arco/{_SST}/{_SST_DS}/timeChunked.zarr"

_OC = "OCEANCOLOUR_GLO_BGC_L4_NRT_009_102"
_OC_DS = "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D_202311"
_OC_ARCO = f"mdl-arco-time-044/arco/{_OC}/{_OC_DS}/timeChunked.zarr"

_WIND = "WIND_GLO_PHY_L4_NRT_012_004"
_WIND_DS = "cmems_obs-wind_glo_phy_nrt_l4_0.125deg_PT1H_202207"
_WIND_ARCO = f"mdl-arco-time-050/arco/{_WIND}/{_WIND_DS}/timeChunked.zarr"

_PHY = "GLOBAL_ANALYSISFORECAST_PHY_001_024"
_UV_DS = "cmems_mod_glo_phy_anfc_merged-uv_PT1H-i_202211"
_UV_ARCO = f"mdl-arco-time-015/arco/{_PHY}/{_UV_DS}/timeChunked.zarr"


def _wav(param: str, var: str, unit: str, note: str | None = None) -> CmemsBinding:
    return CmemsBinding(param, _WAV, _WAV_DS, var, R.INSTANTANEOUS, unit,
                        _WAV_ARCO, note)


def _uv(param: str, var: str, unit: str, note: str | None = None) -> CmemsBinding:
    return CmemsBinding(param, _PHY, _UV_DS, var, R.INSTANTANEOUS, unit,
                        _UV_ARCO, note)


def _wind(param: str, var: str, unit: str, note: str | None = None) -> CmemsBinding:
    return CmemsBinding(param, _WIND, _WIND_DS, var, R.HOURLY_MEAN, unit,
                        _WIND_ARCO, note)


BINDINGS: dict[str, list[CmemsBinding]] = {
    # OSTIA publishes analysed_sst in KELVIN. The adapter reads the unit from the
    # store and converts; assuming degC would report ~301 degC for a tropical sea.
    "sst": [
        CmemsBinding("sst", _SST, _SST_DS, "analysed_sst", R.DAILY_COMPOSITE,
                     "degC", _SST_ARCO,
                     note="OSTIA L4 daily analysis; source unit is kelvin",
                     uncertainty_variable="analysis_error",
                     uncertainty_kind="std_dev"),
    ],
    "chlorophyll_a": [
        CmemsBinding("chlorophyll_a", _OC, _OC_DS, "CHL", R.DAILY_COMPOSITE,
                     "mg m-3", _OC_ARCO,
                     note="multi-sensor 4 km gap-free daily L4",
                     uncertainty_variable="CHL_uncertainty",
                     uncertainty_kind="percent"),
    ],
    # Wind is an OBSERVATION product (scatterometer + model L4), not a forecast.
    # It answers "what is the wind now"; it cannot answer "what will it be
    # tomorrow". A wind forecast requires IMD or another NWP source.
    "eastward_wind": [
        _wind("eastward_wind", "eastward_wind", "m s-1",
              "L4 near-real-time analysis; observation product, no forecast horizon"),
    ],
    "northward_wind": [
        _wind("northward_wind", "northward_wind", "m s-1",
              "L4 near-real-time analysis; observation product, no forecast horizon"),
    ],
    "significant_wave_height": [
        _wav("significant_wave_height", "VHM0", "m",
             "spectral significant wave height (Hm0), 3-hourly instantaneous"),
    ],
    "peak_period": [_wav("peak_period", "VTPK", "s")],
    "mean_wave_direction": [_wav("mean_wave_direction", "VMDR", "degree")],
    "swell_height": [
        _wav("swell_height", "VHM0_SW1", "m", "primary swell partition"),
    ],
    "swell_period": [_wav("swell_period", "VTM01_SW1", "s")],
    "max_wave_height": [
        _wav("max_wave_height", "VCMX", "m", "maximum crest height"),
    ],
    "current_u": [_uv("current_u", "utotal", "m s-1",
                      "total surface current incl. tide and Stokes drift")],
    "current_v": [_uv("current_v", "vtotal", "m s-1",
                      "total surface current incl. tide and Stokes drift")],
}

#: Dimension names used by these datasets, in the order the store declares them.
COORD_ALIASES = {"time": "time", "latitude": "latitude", "longitude": "longitude",
                 "elevation": "elevation", "depth": "depth"}
