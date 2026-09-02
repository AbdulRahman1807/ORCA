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

    @property
    def store_url(self) -> str:
        return f"{ARCO_BASE}/{self.arco_path}"


_WAV = "GLOBAL_ANALYSISFORECAST_WAV_001_027"
_WAV_DS = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i_202411"
_WAV_ARCO = f"mdl-arco-time-015/arco/{_WAV}/{_WAV_DS}/timeChunked.zarr"

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
