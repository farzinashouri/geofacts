# Vendored witness metadata

Real product metadata files against which `geocase.synth.spec` constants are
machine-checked (`tests/synth/test_spec_fidelity.py`). These are *witnesses*,
not fixtures: they are never inputs to graded code, and they must never be
edited — an edited witness is no longer an authority.

| File | Product | Source |
|---|---|---|
| `MTD_MSIL2A_N0400.xml` | `S2B_MSIL2A_20220413T150759_N0400_R025_T33XWJ_20220414T082126.SAFE` (processing baseline 04.00) | Copernicus Sentinel-2 data 2022, retrieved 2026-08-12 via the stactools-packages/sentinel2 test corpus (`tests/data-files/`) |
| `s1a-iw-grd-vv-annotation.xml` | `S1A_IW_GRDH_1SDV_20210809T173953_20210809T174018_039156_049F13_6FF8.SAFE`, VV annotation | Copernicus Sentinel-1 data 2021, retrieved 2026-08-12 via the stactools-packages/sentinel1 test corpus (`tests/data-files/grd/`) |

License: Copernicus Sentinel data is free and open
(https://sentinels.copernicus.eu/ — Legal notice on the use of Copernicus
Sentinel Data and Service Information); redistribution with attribution is
permitted. Contains modified Copernicus Sentinel data 2021–2022 (unmodified
metadata files, redistributed verbatim).
