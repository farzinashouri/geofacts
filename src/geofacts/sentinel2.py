"""Sentinel-2 L2A facts, as guards.

Every public name here is a callable. There is no ``S2_BOA_ADD_OFFSET`` to
import, and that is the point: the offset is reachable only by supplying a
baseline or an acquisition date, so the call site is forced to answer "does my
data carry the offset?" rather than dereferencing a number that is right for
some products and wrong for others.

Two framings this module deliberately does **not** use:

* It is not offset *bug discovery*. Upstream ARD frequently handles the offset
  already, and a one-line dirname assertion (parse ``N05xx``, assert
  ``>= 04.00``) covers much of that case with no dependency. What this adds is
  the nodata semantics below, the enforced invariant, the citation, and the
  witness.
* It is not a claim that the offset "silently biases model input". That claim
  was measured by the one evaluator holding real data and came back clean.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from . import _witness as witness
from ._table import FactTable
from ._types import SpecFact
from .exceptions import BaselineMismatch, NodataUndeclared, ScopeRequired, UnknownScope

__all__ = [
    # radiometry — every one requires the scope
    "boa_offset",
    "quantification",
    "to_reflectance",
    # nodata conventions — equal billing, stronger evidence
    "nodata_value",
    "is_ambiguous_zero",
    "resample_nodata_policy",
    "assert_nodata_declared",
    # runtime guards, importable from production
    "assert_baseline_consistent",
    # baseline helpers
    "parse_baseline",
    "baseline_for",
    "baseline_has_offset",
    # introspection
    "explain",
    "fact_names",
]

_WITNESS_DIR = Path(__file__).parent / "_witnesses"
_MTD = _WITNESS_DIR / "MTD_MSIL2A_N0400.xml"


def _mtd_facts(root: ElementTree.Element) -> dict[str, object]:
    """Extract the L2A facts this module claims from real product metadata."""
    offsets = [int(witness.text(e)) for e in root.iter("BOA_ADD_OFFSET")]
    special = {
        witness.text(e, "SPECIAL_VALUE_TEXT"): int(
            witness.text(e, "SPECIAL_VALUE_INDEX")
        )
        for e in root.iter("Special_Values")
    }
    resolutions = {
        e.attrib["physicalBand"]: int(witness.text(e, "RESOLUTION"))
        for e in root.iter("Spectral_Information")
    }
    scl = {
        int(witness.text(e, "SCENE_CLASSIFICATION_INDEX")): witness.text(
            e, "SCENE_CLASSIFICATION_TEXT"
        )
        for e in root.iter("Scene_Classification_ID")
    }
    return {
        "offset_baseline": witness.text(next(root.iter("PROCESSING_BASELINE"))),
        "quantification": int(witness.text(next(root.iter("BOA_QUANTIFICATION_VALUE")))),
        "boa_add_offset": offsets[0] if len(set(offsets)) == 1 else offsets,
        "boa_add_offset_band_count": len(offsets),
        "nodata": special.get("NODATA"),
        "saturated": special.get("SATURATED"),
        "band_resolution_m": resolutions,
        "scl_classes": scl,
        "scl_resolution_m": 20,
        "dtype": "uint16",
    }


_MTD_WITNESS = witness.from_xml(_MTD, _mtd_facts)

#: Private. Values live here; the public surface is functions only.
_FACTS = FactTable("sentinel2-l2a")

_PSD = "S2-PDGS-TAS-DI-PSD (PSD 14.x), Sentinel-2 Products Specification Document"

_FACTS.register(
    "offset_baseline",
    "04.00",
    cite=f"{_PSD}, L2A radiometric offset introduced with baseline 04.00",
    scope="products acquired from 2022-01-25",
    witness=_MTD_WITNESS,
    notes=("Earlier baselines encode reflectance as DN / 10000 with no offset.",),
)
_FACTS.register(
    "offset_baseline_date",
    date(2022, 1, 25),
    cite=f"{_PSD}; ESA baseline 04.00 rollout",
    scope="acquisition date at which baseline 04.00 took effect",
    witness=None,
    notes=("Dated, not universal: the answer is 0 before this date.",),
)
_FACTS.register(
    "quantification",
    10000,
    cite=f"{_PSD}, BOA_QUANTIFICATION_VALUE",
    scope="all L2A baselines",
    witness=_MTD_WITNESS,
)
_FACTS.register(
    "boa_add_offset",
    -1000,
    cite=f"{_PSD}, BOA_ADD_OFFSET (all 13 bands)",
    scope="baseline >= 04.00 only",
    witness=_MTD_WITNESS,
    notes=("BOA reflectance = (DN + BOA_ADD_OFFSET) / QUANTIFICATION_VALUE.",),
)
_FACTS.register(
    "nodata",
    0,
    cite=f"{_PSD}, Special_Values NODATA",
    scope="all L2A baselines",
    witness=_MTD_WITNESS,
    notes=(
        "0 is also a representable valid dark pixel post-offset-removal, "
        "so this sentinel is ambiguous. See is_ambiguous_zero.",
    ),
)
_FACTS.register(
    "saturated",
    65535,
    cite=f"{_PSD}, Special_Values SATURATED",
    scope="all L2A baselines",
    witness=_MTD_WITNESS,
)
_FACTS.register(
    "dtype",
    "uint16",
    cite=f"{_PSD}, 15-bit unsigned samples in a 16-bit container",
    scope="all L2A baselines",
    witness=_MTD_WITNESS,
)
_FACTS.register(
    "band_resolution_m",
    {
        "B1": 60, "B2": 10, "B3": 10, "B4": 10, "B5": 20, "B6": 20, "B7": 20,
        "B8": 10, "B8A": 20, "B9": 60, "B10": 60, "B11": 20, "B12": 20,
    },
    cite=f"{_PSD}, Spectral_Information RESOLUTION",
    scope="native resolution per physical band, metres",
    witness=_MTD_WITNESS,
    notes=("B10 (cirrus) has no L2A surface-reflectance image.",),
)
_FACTS.register(
    "scl_classes",
    {
        0: "SC_NODATA", 1: "SC_SATURATED_DEFECTIVE", 2: "SC_DARK_FEATURE_SHADOW",
        3: "SC_CLOUD_SHADOW", 4: "SC_VEGETATION", 5: "SC_NOT_VEGETATED",
        6: "SC_WATER", 7: "SC_UNCLASSIFIED", 8: "SC_CLOUD_MEDIUM_PROBA",
        9: "SC_CLOUD_HIGH_PROBA", 10: "SC_THIN_CIRRUS", 11: "SC_SNOW_ICE",
    },
    cite=f"{_PSD}, Scene_Classification_List",
    scope="L2A SCL band, 20 m",
    witness=_MTD_WITNESS,
)
_FACTS.register(
    "scl_resolution_m",
    20,
    cite=f"{_PSD}, SCL band resolution",
    scope="L2A SCL band",
    witness=_MTD_WITNESS,
)

_PRODUCTS = {"S2_L2A", "S2_L1C"}


# ------------------------------------------------------------------ baselines


def parse_baseline(baseline: str) -> tuple[int, int]:
    """Parse an ``NN.NN`` processing-baseline string into a comparable tuple."""
    try:
        major, minor = baseline.split(".")
        return int(major), int(minor)
    except (ValueError, AttributeError):
        raise UnknownScope(
            f"baseline {baseline!r} is not in NN.NN form (e.g. '04.00')"
        ) from None


def baseline_for(acquired: date | datetime | str) -> str:
    """The processing baseline in effect for an acquisition date.

    Coarse by construction: it resolves the one boundary that changes the
    radiometry, 2022-01-25. It is not a full baseline history and does not
    pretend to be — a product's own metadata is always the better authority.
    """
    if isinstance(acquired, str):
        acquired = date.fromisoformat(acquired[:10])
    elif isinstance(acquired, datetime):
        acquired = acquired.date()
    boundary = _FACTS.get_as("offset_baseline_date", date)
    return _FACTS.get_as("offset_baseline", str) if acquired >= boundary else "03.01"


def baseline_has_offset(baseline: str) -> bool:
    """True if *baseline* products carry the BOA_ADD_OFFSET (>= 04.00)."""
    return parse_baseline(baseline) >= parse_baseline(
        _FACTS.get_as("offset_baseline", str)
    )


def _resolve(baseline: str | None, acquired: date | datetime | str | None, fn: str) -> str:
    if baseline is None and acquired is None:
        raise ScopeRequired(
            f"{fn}() requires baseline= or acquired=. The answer differs by "
            f"product: baseline >= 04.00 carries the BOA offset, earlier "
            f"baselines do not. Supply the scope so the call site records "
            f"which convention its data is in."
        )
    if baseline is not None and acquired is not None:
        raise ScopeRequired(f"{fn}() takes baseline= or acquired=, not both")
    return baseline if baseline is not None else baseline_for(acquired)  # type: ignore[arg-type]


# --------------------------------------------------------------- radiometry


def boa_offset(
    *,
    baseline: str | None = None,
    acquired: date | datetime | str | None = None,
) -> int:
    """The BOA additive offset for the product identified by the scope.

    >>> boa_offset(baseline="04.00")
    -1000
    >>> boa_offset(baseline="03.01")
    0

    Raises :class:`ScopeRequired` when called bare. That is the feature.
    """
    resolved = _resolve(baseline, acquired, "boa_offset")
    return _FACTS.get_as("boa_add_offset", int) if baseline_has_offset(resolved) else 0


def quantification(
    *,
    baseline: str | None = None,
    acquired: date | datetime | str | None = None,
) -> int:
    """The quantification value (DN per unit reflectance) for the product."""
    _resolve(baseline, acquired, "quantification")
    return _FACTS.get_as("quantification", int)


def to_reflectance(
    dn: Any,
    *,
    baseline: str | None = None,
    acquired: date | datetime | str | None = None,
) -> Any:
    """Convert L2A DNs to surface reflectance, applying the offset exactly once.

    Works on scalars and on anything supporting arithmetic (numpy arrays
    included) without importing numpy — this package has zero dependencies.
    """
    resolved = _resolve(baseline, acquired, "to_reflectance")
    offset = boa_offset(baseline=resolved)
    return (dn + offset) / _FACTS.get_as("quantification", int)


# ------------------------------------------------------------------- nodata
# Equal billing with radiometry, and on stronger evidence: this is where a
# confirmed live bug was found in a real compute-side repository.


def nodata_value(*, product: str, baseline: str | None = None) -> int:
    """The declared nodata sentinel for *product*."""
    if product not in _PRODUCTS:
        raise UnknownScope(f"unknown product {product!r}; known: {sorted(_PRODUCTS)}")
    return _FACTS.get_as("nodata", int)


def is_ambiguous_zero(*, product: str, baseline: str | None = None) -> bool:
    """True when 0 is both the nodata sentinel and a representable valid value.

    For L2A this is always true, and it is the reason an all-bands-zero
    heuristic is unsafe: a single band legitimately reading 0 in a valid pixel
    slips through, and downstream normalisation turns it into a plausible-looking
    negative outlier rather than a masked sample.
    """
    if product not in _PRODUCTS:
        raise UnknownScope(f"unknown product {product!r}; known: {sorted(_PRODUCTS)}")
    return nodata_value(product=product, baseline=baseline) == 0


@dataclass(frozen=True)
class ResampleNodataPolicy:
    """What a resampling call must declare for a product to be safe.

    Supports both attribute access and ``policy["src_nodata"]``, since callers
    frequently want to splat it straight into warp kwargs.
    """

    src_nodata: int
    dst_nodata: int
    required_for: tuple[str, ...]
    safe_without: tuple[str, ...]
    reason: str

    def __getitem__(self, key: str) -> object:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key) from None


def resample_nodata_policy(*, product: str) -> ResampleNodataPolicy:
    """What a resampling call must declare for *product* to be safe.

    Returns the requirement, not a recommendation: any interpolating resampler
    (bilinear, cubic, lanczos) mixes neighbouring samples, so an undeclared
    nodata region is averaged into its valid neighbours and the result is
    in-bounds, plausible, and wrong.
    """
    if product not in _PRODUCTS:
        raise UnknownScope(f"unknown product {product!r}; known: {sorted(_PRODUCTS)}")
    nodata = _FACTS.get_as("nodata", int)
    return ResampleNodataPolicy(
        src_nodata=nodata,
        dst_nodata=nodata,
        required_for=("bilinear", "cubic", "cubic_spline", "lanczos", "average", "rms"),
        safe_without=("nearest",),
        reason=(
            "Interpolating resamplers average nodata into valid neighbours when "
            "src_nodata is undeclared, smearing the masked region outward."
        ),
    )


def assert_nodata_declared(
    profile: Mapping[str, Any],
    *,
    product: str = "S2_L2A",
    resampling: str = "bilinear",
) -> None:
    """Runtime guard: raise unless *profile* declares nodata for *resampling*.

    Importable from production code, not just tests. ``profile`` is any mapping
    — a rasterio profile, a dict of kwargs about to be passed to a warp call,
    or your own config object's ``__dict__``.
    """
    policy = resample_nodata_policy(product=product)
    if resampling in policy.safe_without:
        return
    if resampling not in policy.required_for:
        raise UnknownScope(
            f"unknown resampling {resampling!r}; "
            f"known: {sorted(set(policy.required_for) | set(policy.safe_without))}"
        )
    missing = [
        key
        for key in ("src_nodata", "dst_nodata")
        if profile.get(key) is None and profile.get(key.replace("_", "")) is None
    ]
    # A profile may declare a single 'nodata' that covers both ends.
    if missing and profile.get("nodata") is not None:
        missing = []
    if missing:
        raise NodataUndeclared(
            f"{resampling} resampling of {product} with {', '.join(missing)} "
            f"undeclared. {policy.reason} Declare nodata="
            f"{nodata_value(product=product)} on both ends, or resample with "
            f"'nearest'."
        )


# ------------------------------------------------------------ runtime guards


def assert_baseline_consistent(
    metadata: Mapping[str, Any],
    *,
    assumes: str,
    thresholds: Mapping[str, float] | None = None,
    key: str = "PROCESSING_BASELINE",
) -> None:
    """Runtime guard: raise if data's baseline contradicts what the code assumes.

    ``assumes`` is the convention the calling code was written for: either a
    baseline string (``"04.00"``) or one of ``"pre-04.00"`` / ``"post-04.00"``.

    This is the enforced-invariant framing. The team may well satisfy the
    invariant already — by luck of which processing their archive happens to
    carry. What they do not have is anything in their code that *records* the
    assumption, so nothing fails when the archive changes underneath it.

    ``assumes`` describes the calling code, not the product, so it cannot be
    inferred here: a value read off ``metadata`` would check the data against
    itself and never fire. That makes a wrong ``assumes`` worse than no guard —
    it passes silently on a matching archive and reads as verified. Derive it
    before writing it down: if every threshold goes through
    :func:`to_reflectance` first, the code carries no DN-scaling assumption and
    ``assumes`` is only a claim about the expected archive; if the code compares
    raw DNs, decode one threshold under both conventions and keep the reading
    that matches the target it was tuned for. A raw-DN threshold below 1000 can
    only be pre-04.00. See ``docs/SENTINEL2.md``.

    ``thresholds`` turns part of that derivation into a check. Pass the raw-DN
    constants the calling code compares against — ``{"water_dn": 1500}`` — and
    each is decoded under the claimed convention and rejected if the result is
    not a reflectance any real target produces. This is the half of the wrong-
    ``assumes`` problem that is decidable without the archive's cooperation:
    it fires on a matching archive, where the metadata check cannot.
    """
    declared = metadata.get(key)
    if declared is None:
        raise BaselineMismatch(
            f"metadata has no {key!r}; cannot verify the code's assumption "
            f"({assumes!r}). Supply the product's declared baseline."
        )
    declared = str(declared).strip()
    data_has_offset = baseline_has_offset(declared)

    if assumes in ("pre-04.00", "post-04.00"):
        code_has_offset = assumes == "post-04.00"
    else:
        code_has_offset = baseline_has_offset(assumes)

    # Check the claim against the caller's own constants before checking it
    # against the data: this half does not need the archive to disagree.
    if thresholds:
        offset = _FACTS.get_as("boa_add_offset", int) if code_has_offset else 0
        impossible = {
            name: dn for name, dn in thresholds.items() if dn + offset < 0
        }
        if impossible:
            listed = ", ".join(
                f"{name}={dn:g}" for name, dn in sorted(impossible.items())
            )
            raise BaselineMismatch(
                f"code assumes {assumes}, but raw-DN threshold(s) {listed} decode "
                f"to negative reflectance under that convention "
                f"(BOA_ADD_OFFSET {offset}). A threshold below {-offset:d} can "
                f"only have been tuned pre-04.00; either the assumption or the "
                f"constants are stale."
            )

    if data_has_offset != code_has_offset:
        offset = _FACTS.get_as("boa_add_offset", int)
        raise BaselineMismatch(
            f"product declares {declared}; this code assumes {assumes} DN scaling. "
            f"Threshold constants tuned on "
            f"{'pre' if not code_has_offset else 'post'}-04.00 data are off by "
            f"BOA_ADD_OFFSET ({offset})."
        )


# ------------------------------------------------------------- introspection


def explain(name: str) -> SpecFact:
    """Return the citation, scope and witness line for a fact.

    The only path to a raw value, and it costs you an explicit name plus an
    object that carries the caveats. Use it in error messages and tooling, not
    to feed arithmetic.
    """
    return _FACTS.explain(name)


def fact_names() -> tuple[str, ...]:
    """Every fact name this module registers."""
    return _FACTS.names()
