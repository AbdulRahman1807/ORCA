"""Threshold set loading.

Thresholds are CONFIGURATION, not code constants. Every set carries a
validation status that is surfaced in the answer
(12_RISK_AND_RECOMMENDATION_SPEC.md section 13).
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml

from ..schemas.enums import Domain

CONFIG_DIR = pathlib.Path(__file__).resolve().parents[3] / "config" / "thresholds"

#: Band names in order of increasing severity. The worst band governs.
BAND_ORDER = ("favourable", "marginal", "unfavourable", "unsafe")


@dataclass(frozen=True, slots=True)
class FactorSpec:
    name: str
    unit: str | None
    higher_is_worse: bool
    bands: dict[str, tuple[float | None, float | None]]

    def band_for(self, value: float) -> str | None:
        """Return the band a value falls in. Bands are [low, high)."""
        for band in BAND_ORDER:
            rng = self.bands.get(band)
            if rng is None:
                continue
            lo, hi = rng
            if (lo is None or value >= lo) and (hi is None or value < hi):
                return band
        return None


@dataclass(frozen=True, slots=True)
class ThresholdSet:
    set_id: str
    domain: Domain
    status: str
    rationale: str
    required_factors: tuple[str, ...]
    preferred_factors: tuple[str, ...]
    optional_factors: tuple[str, ...]
    min_usable_factors: int
    factors: dict[str, FactorSpec]
    validation_reference: str | None = None

    @property
    def validated(self) -> bool:
        return self.status.upper().startswith("VALIDATED")


def _spec(name: str, raw: dict[str, Any]) -> FactorSpec:
    bands = {b: (tuple(v) if v else (None, None)) for b, v in (raw.get("bands") or {}).items()}
    unknown = set(bands) - set(BAND_ORDER)
    if unknown:
        raise ValueError(f"factor {name!r}: unknown band(s) {sorted(unknown)}")
    return FactorSpec(name=name, unit=raw.get("unit"),
                      higher_is_worse=bool(raw.get("higher_is_worse", True)),
                      bands=bands)  # type: ignore[arg-type]


@lru_cache(maxsize=8)
def load(set_id: str, config_dir: str | None = None) -> ThresholdSet:
    path = pathlib.Path(config_dir or CONFIG_DIR) / f"{set_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"threshold set {set_id!r} not found at {path}")
    raw = yaml.safe_load(path.read_text())
    for key in ("set_id", "domain", "status", "factors"):
        if key not in raw:
            raise ValueError(f"{path.name}: missing required key {key!r}")
    if raw["set_id"] != set_id:
        raise ValueError(f"{path.name}: set_id {raw['set_id']!r} != filename {set_id!r}")
    return ThresholdSet(
        set_id=raw["set_id"],
        domain=Domain(raw["domain"]),
        status=raw["status"],
        rationale=(raw.get("rationale") or "").strip(),
        required_factors=tuple(raw.get("required_factors") or ()),
        preferred_factors=tuple(raw.get("preferred_factors") or ()),
        optional_factors=tuple(raw.get("optional_factors") or ()),
        min_usable_factors=int(raw.get("min_usable_factors", 0)),
        factors={k: _spec(k, v) for k, v in raw["factors"].items()},
        validation_reference=raw.get("validation_reference"),
    )
