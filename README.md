# geofacts

Geospatial product facts that you cannot read without saying which product you
have. Zero dependencies, one vendorable file, every fact machine-checked against
real ESA metadata.

```python
from geofacts.sentinel2 import boa_offset

boa_offset(baseline="04.00")      # -1000
boa_offset(baseline="03.01")      #     0   <- the reason this exists
boa_offset()                      # ScopeRequired
```

## What this is for

Sentinel-2 L2A reflectance is `(DN + BOA_ADD_OFFSET) / 10000` — but only for
processing baseline 04.00 and later. Before that the offset is zero. A constant
named `S2_BOA_ADD_OFFSET = -1000` is therefore right for some of your data and
silently wrong for the rest, and nothing about the name tells you which.

This package has no such constant. Every public name is a function that requires
the scope determining the answer, so the call site is forced to record what its
data actually is.

**Two runtime guards, importable from production code — not just tests:**

```python
from geofacts.sentinel2 import assert_baseline_consistent, assert_nodata_declared

# Your thresholds were tuned on pre-04.00 data. Say so, and find out when it changes.
assert_baseline_consistent(product_metadata, assumes="pre-04.00")

# Bilinear resampling with undeclared nodata smears the masked region outward.
assert_nodata_declared(warp_kwargs, resampling="bilinear")
```

`assumes=` is a claim about your code, not about the product, so no library can
infer it for you — and a value copied from this example without checking your own
constants will pass quietly on a matching archive while recording something
false. Pass the raw-DN constants your code actually compares against and the
claim gets checked rather than trusted:

```python
# Rejects the claim if a threshold decodes to negative reflectance under it.
assert_baseline_consistent(product_metadata, assumes="pre-04.00",
                           thresholds={"water_dn": 1500})
```

Work it out first:
[deriving `assumes=`](docs/SENTINEL2.md#working-out-which-one-you-assume).

## Nodata conventions

Post-offset-removal, `0` is both the nodata sentinel and a valid dark pixel.
That ambiguity is the source of two failure modes we have seen confirmed in real
compute-side code:

- An "all bands zero" nodata heuristic lets a **single-band zero** through in an
  otherwise valid pixel, where downstream normalisation turns it into a
  plausible negative outlier rather than a masked sample.
- **Interpolating resampling with no `src_nodata`/`dst_nodata`** averages the
  nodata region into its valid neighbours. The result is in-bounds, in the right
  CRS, and wrong.

```python
from geofacts.sentinel2 import nodata_value, is_ambiguous_zero, resample_nodata_policy

nodata_value(product="S2_L2A")           # 0
is_ambiguous_zero(product="S2_L2A")      # True
resample_nodata_policy(product="S2_L2A") # what a warp call must declare, and why
```

## What this adds over a one-line assertion

Be clear about the honest competitor. If all you need is "reject pre-04.00
scenes", this covers most of it with no dependency at all:

```python
assert int(safe_dir.split("_N")[1][:4]) >= 400   # parse N05xx, assert >= 04.00
```

That is a real alternative and you should use it if it is sufficient. What this
package adds:

1. **The nodata semantics above**, which the dirname tells you nothing about.
2. **An enforced invariant.** Your archive may satisfy the baseline assumption
   today purely by luck of which processing it happens to carry. Nothing in your
   code records that assumption, so nothing fails when the archive changes.
   `assert_baseline_consistent` is that record.
3. **A citation per fact**, so the next maintainer can check the claim.
4. **A witness per fact** — see below.

This is regression protection, not bug discovery. We are not claiming the offset
is silently corrupting your model inputs; when an evaluator with real data
measured that, it came back clean, because upstream ARD had already handled it.

## The witness mechanism

Every fact carries two independent authorities: a specification citation, and a
**witness** — a real product artifact, vendored in the package and checked in CI.

```python
>>> from geofacts.sentinel2 import explain
>>> print(explain("boa_add_offset"))
boa_add_offset = -1000
  scope: baseline >= 04.00 only
  cite:  S2-PDGS-TAS-DI-PSD (PSD 14.x), BOA_ADD_OFFSET (all 13 bands)
  witness: boa_add_offset = -1000
```

A fact the witness does not corroborate is a test failure, not an opinion. This
is what keeps the table from being one person's reading of a PDF asserting its
own assumptions back at you.

[docs/FACTS.md](docs/FACTS.md) lists all 18 registered facts with scope, witness
status, and why each one earns its place — including which facts genuinely branch
on scope and which are there for consistency.

[docs/SENTINEL2.md](docs/SENTINEL2.md) explains the Sentinel-2 L2A product itself
— the radiometry and the `boa_add_offset` branch, the ambiguous nodata zero, band
resolutions and SCL — and how each is reached through the API.

## Your own facts

Nothing here is ESA-specific. The same discipline applies to any load-bearing
constant your team has:

```python
from geofacts import FactTable, witness

MY_FACTS = FactTable("acme-taxonomy")
MY_FACTS.register(
    "domain_code", 14,
    cite="ACME-DD-014 §4.2",
    scope="EU region only",
    witness=witness.from_json("schema/domains.json"),
)
```

Witnesses can be JSON, XML, or any callable returning a mapping — your DB
schema, an OpenAPI document, a spec export.

## Install

```bash
pip install geofacts          # zero dependencies
```

Or vendor the single file, since what this really competes with is copy-paste:

```bash
curl -O https://raw.githubusercontent.com/farzinashouri/geofacts/main/vendored/geofacts.py
```

The single file is generated from the package by `scripts/build_vendored.py` and
CI fails if it has drifted.

## Scope

Sentinel-2 L2A and Sentinel-1 GRD. S1 is **frozen** — ported because the facts
are already witnessed, not extended, because the ML-EO tables below rank ahead
of it.

Roadmap, in the order the evidence supports:

1. **Foundation-model normalisation statistics** (Prithvi, SatMAE, Clay), tagged
   with which radiometric convention each was trained under.
2. **Cloud-mask output conventions** (OmniCloudMask, s2cloudless, Fmask) —
   polarity is inconsistent between producers and an inversion is silent.

## Status

Alpha, and honestly so. This package exists because three independent
evaluations of a larger project converged on the scope-guard idea as the one
piece worth having. Whether that translates into use by anyone is unproven.

**If there are no external adopters by 2026-11-13 — no issue, no dependent, no
vendored copy — this gets archived and the finding published.** That date is
written down here rather than in a private plan so it can actually be honoured.
