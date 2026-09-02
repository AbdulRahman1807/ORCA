# Recorded upstream fixtures — INCOIS ERDDAP (S-01..S-04)

Captured live on **2026-09-02** from `https://erddap.incois.gov.in/erddap`.

| File | Why it is kept |
|---|---|
| `info_incois_argo_10d_VAM.json` | The only P0 dataset with current coverage (ends 2026-07-30) |
| `info_incois_oceansat2_datasets.json` | Chlorophyll archive; coverage ends 2020-05-01 |
| `info_NOAA_AVHRR_datasets.json` | Publishes latitude as array indices 0–399; regression fixture for the broken-axis validator. This dataset also dropped out of the server catalogue during the same session. |

Fixtures are **recorded, never hand-authored** (18_REPOSITORY_STRUCTURE.md §7).
Re-capture with `scripts/capture_datasets.py` if older than 90 days.
