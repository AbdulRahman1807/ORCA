#!/usr/bin/env python3
"""Capture live INCOIS ERDDAP dataset metadata into config/datasets.json.

Phase 1 deliverable (17_IMPLEMENTATION_ROADMAP.md): resolutions, units and
coordinate conventions are recorded from the server, never assumed.
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.orca.adapters.incois_erddap.client import ErddapClient
from backend.orca.adapters.incois_erddap.metadata import capture_all

OUT = pathlib.Path(__file__).resolve().parents[1] / "config" / "datasets.json"


def main() -> int:
    with ErddapClient() as client:
        metas = capture_all(client)

    now = datetime.now(timezone.utc)
    payload = {
        "source_id": "S-01..S-04",
        "source": "INCOIS ERDDAP",
        "captured_at": now.isoformat(),
        "dataset_count": len(metas),
        "datasets": {k: v.to_json() for k, v in sorted(metas.items())},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))

    rows = []
    for ds, m in metas.items():
        behind = m.days_behind(now)
        rows.append((behind if behind is not None else 9e9, ds, m, behind))
    rows.sort()

    print(f"captured {len(metas)} datasets -> {OUT}\n")
    print(f"{'dataset':36} {'coverage ends':12} {'behind':>9}  {'usable':6} issues")
    print("-" * 100)
    for _, ds, m, behind in rows:
        end = (m.time_coverage_end or "?")[:10]
        b = f"{behind:,.0f} d" if behind is not None else "?"
        flag = "yes" if m.usable else "NO"
        note = m.issues[0][:44] if m.issues else ""
        print(f"{ds:36} {end:12} {b:>9}  {flag:6} {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
