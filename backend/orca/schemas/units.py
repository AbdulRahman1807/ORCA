"""Unit normalisation.

Units are READ from the source and converted explicitly. Nothing is assumed:
OSTIA publishes sea surface temperature in kelvin, and treating it as degrees
Celsius would report ~301 degC for a tropical sea.
"""
from __future__ import annotations

from typing import Callable

#: Spelling variants seen across sources -> ORCA canonical unit strings.
ALIASES: dict[str, str] = {
    "degrees C": "degC", "degrees_C": "degC", "degree_C": "degC",
    "Degree C": "degC", "degs": "degC", "celsius": "degC", "C": "degC",
    "kelvin": "K", "Kelvin": "K", "degK": "K",
    "milligram m-3": "mg m-3", "mg/m3": "mg m-3", "mg m^-3": "mg m-3",
    "meter-1": "m-1", "m^-1": "m-1",
    "mg/L": "mg L-1",
    "m/s": "m s-1", "m s^-1": "m s-1", "metre second-1": "m s-1",
    "METERS": "m", "meters": "m", "metres": "m",
    "PSU": "PSU", "psu": "PSU", "1e-3": "PSU",
    "degrees": "degree", "deg": "degree",
    "seconds": "s", "second": "s",
    "percent": "%",
}

#: (from, to) -> conversion. Only exact, lossless physical conversions belong here.
CONVERSIONS: dict[tuple[str, str], Callable[[float], float]] = {
    ("K", "degC"): lambda v: v - 273.15,
    ("degC", "K"): lambda v: v + 273.15,
}


class UnitError(ValueError):
    """Raised when a value cannot be expressed in the requested unit.

    Deliberately fatal: silently returning an unconverted number would put a
    kelvin temperature into a Celsius threshold comparison.
    """


def canonical(unit: str | None) -> str | None:
    if unit is None:
        return None
    u = unit.strip()
    return ALIASES.get(u, u)


def convert(value: float, from_unit: str | None, to_unit: str | None) -> float:
    """Convert a value between canonical units."""
    f, t = canonical(from_unit), canonical(to_unit)
    if f is None or t is None or f == t:
        return value
    fn = CONVERSIONS.get((f, t))
    if fn is None:
        raise UnitError(f"no conversion from {f!r} to {t!r}")
    return fn(value)


def convertible(from_unit: str | None, to_unit: str | None) -> bool:
    f, t = canonical(from_unit), canonical(to_unit)
    return f is None or t is None or f == t or (f, t) in CONVERSIONS
