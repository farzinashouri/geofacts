# Vendored witness metadata

Real product metadata against which the fact tables in `geofacts` are
machine-checked (`tests/test_spec_fidelity.py`). These are *witnesses*, not
fixtures: they are never inputs to graded code, and their retained content must
never be edited — an edited witness is no longer an authority.

| File | Product | Source |
|---|---|---|
| `MTD_MSIL2A_N0400.xml` | `S2B_MSIL2A_20220413T150759_N0400_R025_T33XWJ_20220414T082126.SAFE` (processing baseline 04.00) | Copernicus Sentinel-2 data 2022, retrieved 2026-08-12 via the stactools-packages/sentinel2 test corpus (`tests/data-files/`) |
| `s1a-iw-grd-vv-annotation.xml` | `S1A_IW_GRDH_1SDV_20210809T173953_20210809T174018_039156_049F13_6FF8.SAFE`, VV annotation | Copernicus Sentinel-1 data 2021, retrieved 2026-08-12 via the stactools-packages/sentinel1 test corpus (`tests/data-files/grd/`) |

## Pruning — what was dropped and why

`MTD_MSIL2A_N0400.xml` is vendored **verbatim**, unmodified.

`s1a-iw-grd-vv-annotation.xml` is **pruned**, by `scripts/prune_witness.py`, from
1,726,361 bytes to 12,214 bytes (0.7%). This package targets <100 KB installed,
because competing with copy-paste means being trivially cheap to vendor, and the
full annotation is 17× that budget on its own.

Retained, byte-identical to the original: `adsHeader` and `imageAnnotation` —
every element any fact is checked against.

Dropped: `qualityInformation`, `generalAnnotation`, `dopplerCentroid`,
`antennaPattern`, `geolocationGrid`, `coordinateConversion`, `swathMerging`,
`swathTiming`. None is read by this package.

The pruning is reproducible and therefore re-verifiable: download the source
granule named above and re-run `scripts/prune_witness.py` on its VV annotation;
the result must be byte-identical to the vendored file. A witness you cannot
re-derive from the original is a transcription, which is the failure mode this
mechanism exists to prevent.

## License

Copernicus Sentinel data is free and open
(https://sentinels.copernicus.eu/ — Legal notice on the use of Copernicus
Sentinel Data and Service Information); redistribution with attribution is
permitted. Contains modified Copernicus Sentinel data 2021–2022: the Sentinel-2
metadata file is redistributed unmodified; the Sentinel-1 annotation is
redistributed with non-referenced subtrees removed as described above.
