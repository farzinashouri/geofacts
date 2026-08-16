# The fact table, and why each fact is in it

Every registered fact costs something: a citation someone has to keep honest, a
witness someone has to keep passing, and a line of public API someone has to
keep scoped. This document says what is registered and what each one is *for*,
so that the table can be argued with rather than merely trusted.

The package registers **18 facts** across three modules — 10 for Sentinel-2 L2A,
6 for Sentinel-1 GRD, 2 cross-sensor. They are not all here for the same reason.

## Why-categories

| Category | Meaning | Count |
| --- | --- | --- |
| **Branching** | The scope argument changes the returned value. A bare constant is right for some of your data and wrong for the rest. | 3 |
| **Hazard** | The value is stable, but using it naively causes a specific, silent, in-bounds-wrong result. The fact exists to carry the warning. | 4 |
| **Boundary** | Defines where a branching fact switches. Load-bearing only in service of a branching fact. | 1 |
| **Shape** | Structural facts (dtypes, resolutions, class codes) that a caller needs to consume the data at all. Scoped for consistency and future-proofing, not because they branch today. | 10 |

Branching facts are the thesis. Hazard facts are the strongest evidence.
Shape facts are the discipline held consistently so the table cannot decay into
an unscoped lookup dict — [`tests/test_no_bare_constants.py`](../tests/test_no_bare_constants.py)
enforces that mechanically.

## Sentinel-2 L2A

Source: [`src/geospatial_spec/sentinel2.py`](../src/geospatial_spec/sentinel2.py).
Witness: `MTD_MSIL2A_N0400.xml`, real ESA product metadata, vendored and checked in CI.
For what the product *is* and why these facts bite, see [SENTINEL2.md](SENTINEL2.md).

| Fact | Value | Scope | Witnessed | Why | Why it is here |
| --- | --- | --- | --- | --- | --- |
| `boa_add_offset` | `-1000` | baseline >= 04.00 only | ✅ | **Branching** | The defining case. Reflectance is `(DN + offset) / 10000` from baseline 04.00 onward, and `DN / 10000` before it. A constant named `S2_BOA_ADD_OFFSET` is silently wrong for half a mixed archive and its name says nothing about which half. Reached only via `boa_offset(baseline=…)`; calling bare raises `ScopeRequired`. |
| `offset_baseline` | `"04.00"` | products acquired from 2022-01-25 | ✅ | **Boundary** | The baseline at which the offset appears. Exists so `baseline_has_offset()` compares against a cited, witnessed value instead of a literal buried in a comparison. |
| `offset_baseline_date` | `2022-01-25` | acquisition date at which 04.00 took effect | ❌ | **Branching** | Lets a caller supply `acquired=` instead of a baseline, for the common case where the acquisition date is at hand and the metadata is not. Deliberately coarse: it resolves the one boundary that changes the radiometry, and does not pretend to be a full baseline history. **Unwitnessed** — a rollout date is not recorded in any single product's metadata. |
| `nodata` | `0` | all L2A baselines | ✅ | **Hazard** | Post-offset-removal, `0` is both the nodata sentinel and a representable valid dark pixel. This ambiguity is the root of both confirmed failure modes below. |
| `quantification` | `10000` | all L2A baselines | ✅ | **Shape** | DN per unit reflectance. Stable across baselines, but exposed through `quantification(baseline=…)` so no call site can scale without also stating the baseline it is scaling — which is where the offset question belongs anyway. |
| `saturated` | `65535` | all L2A baselines | ✅ | **Shape** | The other special value. Registered alongside `nodata` so a caller masking specials has both from one authority. |
| `dtype` | `uint16` | all L2A baselines | ✅ | **Shape** | 15-bit unsigned samples in a 16-bit container. Needed to read at all; also the reason `65535` is available as a sentinel. |
| `band_resolution_m` | 13 bands, 10/20/60 m | native resolution per physical band | ✅ | **Shape** | Per-band native GSD. Assuming a uniform 10 m is a common and quiet resampling error. Note B10 (cirrus) has no L2A surface-reflectance image. |
| `scl_classes` | 12 classes, 0–11 | L2A SCL band, 20 m | ✅ | **Shape** | Scene-classification codes. Off-by-one class indices produce a mask that is plausible and wrong; the witness pins them to the product's own class list. |
| `scl_resolution_m` | `20` | L2A SCL band | ✅ | **Shape** | SCL is 20 m regardless of the band it will be applied to, so applying it to a 10 m band requires an explicit upsample decision. |

### Derived guards (not facts, but the point of the facts)

| Function | Why | What it protects |
| --- | --- | --- |
| `is_ambiguous_zero(product=…)` | **Hazard** | An "all bands zero" nodata heuristic lets a *single-band* zero through in an otherwise valid pixel; downstream normalisation then turns it into a plausible negative outlier rather than a masked sample. |
| `resample_nodata_policy(product=…)` | **Hazard** | Returns the requirement — `src_nodata`/`dst_nodata`, which resamplers need it, which are safe without, and why — rather than a recommendation. |
| `assert_nodata_declared(profile, resampling=…)` | **Hazard** | Runtime guard, importable from production. Interpolating resampling with undeclared nodata averages the masked region into its valid neighbours. Confirmed live in a real compute-side repository. |
| `assert_baseline_consistent(metadata, assumes=…)` | **Branching** | The enforced-invariant argument. Your archive may satisfy your baseline assumption today purely by luck of which processing it carries; nothing in your code *records* that assumption, so nothing fails when the archive changes. This is that record. |

## Sentinel-1 GRD — frozen

Source: [`src/geospatial_spec/sentinel1.py`](../src/geospatial_spec/sentinel1.py).
Witness: `s1a-iw-grd-vv-annotation.xml`.

**Frozen by decision, not neglect.** Three evaluated codebases treated SAR as
dead weight, and the one compute-side adopter ranked the ML-EO tables ahead of
it. It stays because the facts are already witnessed and correct.

| Fact | Value | Scope | Witnessed | Why | Why it is here |
| --- | --- | --- | --- | --- | --- |
| `pixel_value` | `"Detected"` | GRD measurement files | ✅ | **Hazard** | The load-bearing S1 fact. GRD pixels are detected amplitude — *not* dB, *not* calibrated backscatter. Treating stored DNs as sigma0 is wrong by a calibration LUT; treating linear sigma0 as dB is wrong by a logarithm. Both produce plausible-looking numbers. |
| `iw_grdh_pixel_spacing_m` | `10.0` | IW GRDH (high resolution) only | ✅ | **Branching** | GRDH is 10 m and GRDM is 40 m — a factor of four. A bare constant is right for one and silently wrong for the other, so `pixel_spacing_m()` requires both `mode=` and `resolution=`. The witness fails loudly if range and azimuth spacing ever disagree, rather than silently picking one. |
| `product_type` | `"GRD"` | IW GRDH products | ✅ | **Shape** | Identifies what the frozen table actually covers; `pixel_value_convention()` rejects anything else rather than answering for SLC. |
| `output_pixels` | `"16 bit Unsigned Integer"` | IW GRDH products | ✅ | **Shape** | The spec's own wording, kept verbatim so the witness can match the annotation text. |
| `dtype` | `uint16` | IW GRDH products | ✅ | **Shape** | The programmatic form of the above. |
| `dual_pol` | `("VV", "VH")` | IW dual-pol (1SDV) products | ❌ | **Shape** | Channel order for 1SDV. Scoped because single-pol products carry one channel, not two. **Unwitnessed** — the vendored annotation is a single-polarisation file and cannot corroborate a pair. |

## Cross-sensor commons

Source: [`src/geospatial_spec/common.py`](../src/geospatial_spec/common.py).
Kept deliberately small — a "common" module is where scope creep starts.

| Fact | Value | Scope | Witnessed | Why | Why it is here |
| --- | --- | --- | --- | --- | --- |
| `interpolating_resamplers` | bilinear, cubic, cubic_spline, lanczos, average, rms, mode | resampling of data carrying a nodata sentinel | ❌ | **Hazard** | Any kernel touching more than one source sample mixes neighbours, so an undeclared nodata region is averaged into valid data. `nearest` is the only safe default. **Unwitnessed** — this is a property of GDAL's algorithms, not of any product artifact. |
| `epsg_axis_order_authority` | `"authority-defined"` | EPSG codes interpreted per authority, not per library default | ❌ | **Hazard** | EPSG:4326 is lat,lon by authority; most raster libraries present lon,lat. A round-trip through `int` vs `str` EPSG can silently change which convention a library applies. **Unwitnessed** — a registry convention, with no product artifact to check against. |

`normalise_epsg()` exists for a specific live failure: `int(GetAuthorityCode(…))`
when the authority code is absent, which yields `"EPSG:None"` or crashes far from
the cause. It raises instead. `epsg_equivalent(4326, "EPSG:4326")` is `True`
where direct `==` is `False` — the silent identity mismatch that guards.

## The unwitnessed list

Four of the 18 facts carry a citation but no witness: `offset_baseline_date`,
`dual_pol`, `interpolating_resamplers`, and `epsg_axis_order_authority`. Facts
registered via `witness.from_mapping` would count as weakly witnessed —
transcription, not verification — though none currently are.

This is tracked, not hidden — `FactTable.unwitnessed()` returns it, and it is the
liability list. Each is unwitnessed for a stated structural reason: a rollout
date, a library's algorithm set, and a registry convention are not properties any
single product artifact can corroborate. A fact that *could* be witnessed and is
not should be treated as a defect.

## Where the table goes next

Sentinel-1 is frozen. The roadmap, in the order the evidence supports:

1. **Foundation-model normalisation statistics** (Prithvi, SatMAE, Clay), tagged
   with which radiometric convention each was trained under. Genuinely
   *branching* — the same model has different correct statistics depending on
   whether its training data carried the offset.
2. **Cloud-mask output conventions** (OmniCloudMask, s2cloudless, Fmask).
   Polarity is inconsistent between producers and an inversion is silent. Also
   branching.

Both add facts in the category the thesis rests on, which is why they rank ahead
of extending S1 with more shape facts.
