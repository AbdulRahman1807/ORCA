"""Per-parameter staleness policy (config/staleness.yaml)."""
from __future__ import annotations

import pathlib
from functools import lru_cache

import yaml

CONFIG = pathlib.Path(__file__).resolve().parents[3] / "config" / "staleness.yaml"


@lru_cache(maxsize=1)
def _policy() -> dict:
    if not CONFIG.is_file():
        return {"defaults": {"usable_age_days": 0.5}, "parameters": {}}
    return yaml.safe_load(CONFIG.read_text()) or {}


def usable_age_days(factor: str) -> float:
    p = _policy()
    entry = (p.get("parameters") or {}).get(factor)
    if entry and "usable_age_days" in entry:
        return float(entry["usable_age_days"])
    return float((p.get("defaults") or {}).get("usable_age_days", 0.5))
