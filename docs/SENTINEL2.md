# Sentinel-2 L2A: the product, and what this package says about it

[docs/FACTS.md](FACTS.md) is the ledger — what is registered, why each fact earns
its row. This document is the explanation: what a Sentinel-2 L2A product actually
*is*, which of its properties bite, and how each one is reached through
[`geofacts.sentinel2`](../src/geofacts/sentinel2.py).

Everything below is witnessed against `MTD_MSIL2A_N0400.xml`, real ESA product
metadata vendored into the package ([`_witnesses/`](../src/geofacts/_witnesses/)),
except where explicitly noted.

## What the product is

Sentinel-2 is a two-satellite optical constellation (S2A/S2B, later S2C) carrying
the MultiSpectral Instrument: 13 bands from the coastal aerosol band at 443 nm to
SWIR at 2190 nm, at three native ground sample distances.

Two processing levels matter:

* **L1C** — top-of-atmosphere reflectance, orthorectified, in UTM/WGS84 tiles of
  110 × 110 km.
* **L2A** — bottom-of-atmosphere (surface) reflectance, produced by Sen2Cor from
  L1C, plus the Scene Classification Layer (SCL) and quality masks.

L2A is what most ML-EO pipelines consume, and it is what this module covers.

Pixels are **`uint16`** — 15-bit unsigned samples in a 16-bit container. They are
not reflectance. They are digital numbers that must be scaled, and the scaling
rule changed in January 2022. That change is the reason this module exists.

```python
from geofacts import sentinel2

sentinel2.explain("dtype").value        # 'uint16'
```

## The radiometry, and the fact that branches

### `boa_add_offset` — the defining case

Surface reflectance is recovered from the stored DN by:

```
reflectance = (DN + BOA_ADD_OFFSET) / BOA_QUANTIFICATION_VALUE
```

`BOA_QUANTIFICATION_VALUE` is `10000` and has always been. `BOA_ADD_OFFSET` is
`-1000` for **processing baseline 04.00 and later**, and does not exist at all
before it — for earlier baselines the formula is simply `DN / 10000`.

ESA introduced the offset so that the DN range could represent slightly negative
reflectances, which surface-reflectance retrieval legitimately produces over dark
water and deep shadow. The consequence for consumers is that the same DN means
two different reflectances depending on which processing produced the file.

The failure is quiet. Apply the offset to pre-04.00 data and every reflectance is
0.1 too low; skip it on post-04.00 data and every reflectance is 0.1 too high.
Both results are in range, plot fine, and train a model that generalises to
nothing.

This is why there is no `S2_BOA_ADD_OFFSET` constant to import. The value is
reachable only by naming the scope:

```python
sentinel2.boa_offset(baseline="04.00")        # -1000
sentinel2.boa_offset(baseline="03.01")        # 0
sentinel2.boa_offset(acquired="2023-06-01")   # -1000
sentinel2.boa_offset()                        # raises ScopeRequired
```

`to_reflectance()` applies it exactly once, on scalars or on anything supporting
arithmetic — numpy arrays included, without importing numpy:

```python
sentinel2.to_reflectance(dn_array, baseline="04.00")
```

### The boundary: `offset_baseline` and `offset_baseline_date`

The switch is baseline **04.00**, which took effect for acquisitions from
**2022-01-25**. `baseline_for(acquired)` resolves a date to a baseline, and
`baseline_has_offset(baseline)` answers the yes/no.

Two caveats worth stating plainly:

* `baseline_for()` is **coarse by construction**. It resolves the one boundary
  that changes the radiometry and is not a baseline history. A product's own
  `PROCESSING_BASELINE` in `MTD_MSIL2A.xml` is always the better authority.
* `offset_baseline_date` is **unwitnessed**. A rollout date is not a property any
  single product's metadata records. It carries a citation and appears in
  `FactTable.unwitnessed()`.

Reprocessing campaigns also mean acquisition date is not a perfect proxy: an old
acquisition reprocessed under a new baseline carries the new convention. Prefer
`baseline=` from metadata whenever you have it.

### Recording the assumption

The point is not that your archive is wrong today — it may well be uniform. The
point is that nothing in your code *records* which convention it was written for,
so nothing fails when the archive changes underneath it:

```python
sentinel2.assert_baseline_consistent(product_metadata, assumes="post-04.00")
```

It reads `PROCESSING_BASELINE` from any mapping and raises `BaselineMismatch`
when the data contradicts the assumption. `assumes` takes a baseline string or
`"pre-04.00"` / `"post-04.00"`.

### Working out which one you assume

`assumes=` is a claim about *your code*, not about the product. Nothing in the
metadata can settle it, which is why the guard asks rather than infers — a value
read off the data would validate the data against itself and never fire.

That puts the burden somewhere real: a guess copied from this README, with your
constants left untouched, passes silently on a matching archive and now reads as
diligence. **A wrong `assumes=` is worse than no guard.** Derive it, in this
order:

**1. Do your constants ever touch a raw DN?** If every comparison happens after
`to_reflectance()`, your thresholds carry no DN-scaling assumption at all — the
offset is applied for you, exactly once, per product. `assumes=` is then a
statement about which archive you expect to be handed, not about your constants,
and the guard is a change-detector on your inputs. This is the position worth
migrating to.

**2. If you threshold raw DN, the constant holds the assumption.** `BOA_ADD_OFFSET`
is `-1000`, so a post-04.00 product encodes the same physical reflectance 1000 DN
higher than a pre-04.00 one. Compare your constant against the reflectance you
believe it represents:

```python
from geofacts.sentinel2 import to_reflectance

to_reflectance(1500, baseline="02.14")   # 0.15   <- pre-04.00 reading
to_reflectance(1500, baseline="04.00")   # 0.05   <- post-04.00 reading
```

Whichever number matches the physical target you tuned for is your answer. Two
shortcuts fall out of the same arithmetic:

* A raw-DN threshold **below 1000** can only have been tuned pre-04.00. Read as
  post-04.00 it decodes to negative reflectance, which no real target produces.
* A threshold that is a round `reflectance × 10000` — `1500` for 0.15, `3000` for
  0.30 — is pre-04.00. The post-04.00 equivalents are offset by 1000 and look
  unrounded (`2500`, `4000`).

**3. If the provenance is genuinely lost**, date the constant. The offset
arrived with baseline 04.00 on **2022-01-25**; a threshold that predates it in
your history, and has not been retuned since, is pre-04.00 whatever the archive
now holds. Failing that, run the threshold over one product whose baseline you
know from its own `PROCESSING_BASELINE` and check whether the mask it produces is
the one you expect — a threshold read under the wrong convention typically
collapses to empty or swallows the scene, rather than degrading subtly.

Record the result at the call site. If step 1 applies, say so in a comment there
too — it is the difference between "we checked" and "we don't have to care".

### Checking the claim, not just recording it

Step 2's first shortcut is decidable without the archive's cooperation, so the
guard will do it for you. Hand it the raw-DN constants your code compares
against:

```python
sentinel2.assert_baseline_consistent(
    product_metadata, assumes="post-04.00", thresholds={"water_dn": 800},
)
# BaselineMismatch: code assumes post-04.00, but raw-DN threshold(s)
# water_dn=800 decode to negative reflectance under that convention ...
```

This is the half of the wrong-`assumes` problem the metadata check cannot reach:
it fires even when the archive matches the claim, because the contradiction is
between the claim and your own constants.

It is a floor, not a proof. `thresholds={"water_dn": 2500}` is consistent with
either convention and passes silently — the high side does not discriminate,
since a large DN decodes to an implausible reflectance under *both*. Steps 1–3
remain the way to actually derive the value; this catches the specific case of a
claim copied over untouched constants. Omit the argument and behaviour is
unchanged.

## Nodata, and why zero is a trap

`Special_Values` in the product metadata declares `NODATA = 0` and
`SATURATED = 65535`.

`0` is the hazard. It is both the nodata sentinel *and* a representable valid
sample — especially post-offset, where a genuinely dark pixel can sit at the
bottom of the range. Two consequences follow, and both have been observed live:

**1. "All bands zero" is not a nodata mask.** A single band legitimately reading
0 in an otherwise valid pixel slips through the heuristic. Downstream
normalisation then converts it into a plausible-looking negative outlier rather
than a masked sample.

```python
sentinel2.is_ambiguous_zero(product="S2_L2A")   # True — always, for L2A
```

**2. Interpolating resampling smears the mask.** Bilinear, cubic, cubic_spline,
lanczos, average and rms all mix neighbouring samples. With `src_nodata`
undeclared, the nodata region is averaged into its valid neighbours and the
result is in-bounds, plausible, and wrong. Only `nearest` is safe without a
declaration.

```python
policy = sentinel2.resample_nodata_policy(product="S2_L2A")
policy.src_nodata        # 0
policy.required_for      # ('bilinear', 'cubic', 'cubic_spline', 'lanczos', 'average', 'rms')
policy.safe_without      # ('nearest',)
warp(**{"src_nodata": policy["src_nodata"], "dst_nodata": policy["dst_nodata"]})

# Or assert it, from production code — not just tests:
sentinel2.assert_nodata_declared(rasterio_profile, resampling="bilinear")
```

`assert_nodata_declared` raises `NodataUndeclared` unless the profile declares
`src_nodata`/`dst_nodata` (or a single `nodata` covering both). This is where a
confirmed live bug was found in a real compute-side repository — the strongest
evidence in the table, which is why nodata gets equal billing with radiometry.

## Shape facts: reading the data at all

These do not branch today. They are scoped anyway, because the discipline is the
product — [`tests/test_no_bare_constants.py`](../tests/test_no_bare_constants.py)
fails the build if any public name becomes a bare constant.

### Band resolutions

| GSD | Bands |
| --- | --- |
| 10 m | B2 (blue), B3 (green), B4 (red), B8 (NIR) |
| 20 m | B5, B6, B7 (red edge), B8A (narrow NIR), B11, B12 (SWIR) |
| 60 m | B1 (coastal aerosol), B9 (water vapour), B10 (cirrus) |

Assuming a uniform 10 m is a common and quiet resampling error — a 20 m band
stacked as if it were 10 m is geometrically wrong by half a pixel everywhere.

Note **B10 has no L2A surface-reflectance image**. The cirrus band is used by the
atmospheric correction and dropped from the L2A output, so a loop over "13 bands"
written against L1C will not find it.

```python
sentinel2.explain("band_resolution_m").value["B8A"]   # 20
```

### The Scene Classification Layer

SCL is a 20 m classification band shipped with every L2A product, with 12 classes:

| Code | Class | | Code | Class |
| --- | --- | --- | --- | --- |
| 0 | `SC_NODATA` | | 6 | `SC_WATER` |
| 1 | `SC_SATURATED_DEFECTIVE` | | 7 | `SC_UNCLASSIFIED` |
| 2 | `SC_DARK_FEATURE_SHADOW` | | 8 | `SC_CLOUD_MEDIUM_PROBA` |
| 3 | `SC_CLOUD_SHADOW` | | 9 | `SC_CLOUD_HIGH_PROBA` |
| 4 | `SC_VEGETATION` | | 10 | `SC_THIN_CIRRUS` |
| 5 | `SC_NOT_VEGETATED` | | 11 | `SC_SNOW_ICE` |

Off-by-one class indices produce a mask that is plausible and wrong — masking
water where you meant cloud shadow. The witness pins these to the product's own
class list.

SCL is 20 m **regardless of the band it will be applied to**, so applying it to a
10 m band is an explicit upsample decision, not a free operation. `nearest` is the
only correct resampling for a categorical band; see the nodata section above for
why the interpolating ones are wrong here for a second, independent reason.

## Introspection

Every fact carries its citation, its scope, and its witness line. `explain()` is
the only path to a raw value, and it costs you an explicit name plus an object
carrying the caveats — use it in error messages and tooling, not to feed
arithmetic:

```python
>>> sentinel2.explain("boa_add_offset")
boa_add_offset = -1000
  scope: baseline >= 04.00 only
  cite:  S2-PDGS-TAS-DI-PSD (PSD 14.x), Sentinel-2 Products Specification Document, BOA_ADD_OFFSET (all 13 bands)
  witness: boa_add_offset = -1000
  note:  BOA reflectance = (DN + BOA_ADD_OFFSET) / QUANTIFICATION_VALUE.

>>> sentinel2.fact_names()
```

## What this is not

Restated from the module docstring, because the framing matters:

* **Not offset bug discovery.** Upstream ARD frequently handles the offset
  already, and a one-line dirname assertion (parse `N05xx`, assert `>= 04.00`)
  covers much of that case with no dependency. What this adds is the nodata
  semantics, the enforced invariant, the citation, and the witness.
* **Not a claim that the offset silently biases model input.** That claim was
  measured by the one evaluator holding real data and came back clean.

## Source documents

* `S2-PDGS-TAS-DI-PSD` — Sentinel-2 Products Specification Document (PSD 14.x),
  the citation behind every fact above.
* The product's own `MTD_MSIL2A.xml`, which is the authority for any specific
  file you hold. The vendored witness is one such file, at baseline 04.00.
