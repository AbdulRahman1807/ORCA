# Recorded upstream fixtures — CMEMS (S-07)

Captured live on **2026-09-02**.

| File | Source |
|---|---|
| `wav_zmetadata.json` | `.zmetadata` of the ARCO store for `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i_202411` |
| `dataset_wav.json` | STAC `dataset.stac.json` for the same dataset |

**Access note.** Both the STAC catalogue and the ARCO object store answered
unauthenticated requests, including real data chunks (`VHM0/0.0.0` → HTTP 200,
521 KB). The audit recorded CMEMS as AUTH REQUIRED; that remains true of the
subsetting/download services, but not of the ARCO store as accessed here.
