"""Sentinel-1 GRD facts, as guards.

**Frozen.** This module ports the S1 facts across and is deliberately not
extended. Three evaluated codebases treated SAR as dead weight, and the one
compute-side adopter ranked the ML-EO tables (normalisation statistics, cloud
mask conventions) ahead of it. It stays because the facts are already witnessed
and correct, not because it is where the next work goes.

The load-bearing fact here is that GRD pixels are *detected amplitude* — not
dB, not calibrated backscatter. Code that treats stored DNs as sigma0 is wrong
by a calibration LUT, and code that treats linear sigma0 as dB is wrong by a
logarithm; both produce plausible-looking numbers.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from . import _witness as witness
from ._table import FactTable
from ._types import SpecFact
from .exceptions import ScopeRequired, UnknownScope

__all__ = [
    "pixel_spacing_m",
    "pixel_value_convention",
    "is_calibrated",
    "dual_pol_channels",
    "explain",
    "fact_names",
]

_WITNESS_DIR = Path(__file__).parent / "_witnesses"
_ANNOTATION = _WITNESS_DIR / "s1a-iw-grd-vv-annotation.xml"


def _annotation_facts(root: ElementTree.Element) -> dict[str, object]:
    rng = float(witness.text(next(root.iter("rangePixelSpacing"))))
    azi = float(witness.text(next(root.iter("azimuthPixelSpacing"))))
    return {
        "product_type": witness.text(root, "adsHeader/productType"),
        "pixel_value": witness.text(next(root.iter("pixelValue"))),
        "output_pixels": witness.text(next(root.iter("outputPixels"))),
        # Range and azimuth spacing are equal for GRDH; if a product ever
        # disagreed, the fact would no longer be a single number and the
        # witness check must fail rather than silently pick one.
        "iw_grdh_pixel_spacing_m": rng if rng == azi else (rng, azi),
        "polarisation": witness.text(root, "adsHeader/polarisation"),
        "dtype": "uint16",
    }


_ANNOTATION_WITNESS = witness.from_xml(_ANNOTATION, _annotation_facts)

_FACTS = FactTable("sentinel1-grd")
_S1_SPEC = "S1-RS-MDA-52-7441, Sentinel-1 Product Specification"

_FACTS.register(
    "product_type", "GRD",
    cite=f"{_S1_SPEC}, adsHeader/productType",
    scope="IW GRDH products",
    witness=_ANNOTATION_WITNESS,
)
_FACTS.register(
    "pixel_value", "Detected",
    cite=f"{_S1_SPEC}, imageInformation/pixelValue",
    scope="GRD measurement files",
    witness=_ANNOTATION_WITNESS,
    notes=(
        "Detected amplitude, NOT dB and NOT calibrated backscatter. Calibrated "
        "sigma0 is derived via the calibration LUT, never the stored DN.",
    ),
)
_FACTS.register(
    "output_pixels", "16 bit Unsigned Integer",
    cite=f"{_S1_SPEC}, imageInformation/outputPixels",
    scope="IW GRDH products",
    witness=_ANNOTATION_WITNESS,
)
_FACTS.register(
    "dtype", "uint16",
    cite=f"{_S1_SPEC}, 16-bit unsigned samples",
    scope="IW GRDH products",
    witness=_ANNOTATION_WITNESS,
)
_FACTS.register(
    "iw_grdh_pixel_spacing_m", 10.0,
    cite=f"{_S1_SPEC}, range/azimuthPixelSpacing",
    scope="IW GRDH (high resolution) only",
    witness=_ANNOTATION_WITNESS,
    notes=("GRDM (medium resolution) is 40 m; this fact does not cover it.",),
)
_FACTS.register(
    "dual_pol", ("VV", "VH"),
    cite=f"{_S1_SPEC}, 1SDV product polarisations",
    scope="IW dual-pol (1SDV) products",
    witness=None,
)

_MODES = {"IW"}
_RESOLUTIONS = {"GRDH"}


def pixel_spacing_m(*, mode: str | None = None, resolution: str | None = None) -> float:
    """Pixel spacing for the identified product.

    Scoped because GRDH and GRDM differ by a factor of four; a bare constant
    would be right for one and silently wrong for the other.
    """
    if mode is None or resolution is None:
        raise ScopeRequired(
            "pixel_spacing_m() requires mode= and resolution= (e.g. "
            "mode='IW', resolution='GRDH'). GRDH is 10 m and GRDM is 40 m."
        )
    if mode not in _MODES or resolution not in _RESOLUTIONS:
        raise UnknownScope(
            f"unsupported mode={mode!r}/resolution={resolution!r}; this frozen "
            f"table covers {sorted(_MODES)} x {sorted(_RESOLUTIONS)} only"
        )
    return _FACTS.get_as("iw_grdh_pixel_spacing_m", float)


def pixel_value_convention(*, product_type: str | None = None) -> str:
    """What the stored DNs actually represent for *product_type*."""
    if product_type is None:
        raise ScopeRequired(
            "pixel_value_convention() requires product_type= (e.g. 'GRD'). "
            "The stored value differs between GRD (detected amplitude) and "
            "SLC (complex)."
        )
    if product_type != _FACTS.get("product_type"):
        raise UnknownScope(
            f"this frozen table covers GRD only, not {product_type!r}"
        )
    return _FACTS.get_as("pixel_value", str)


def is_calibrated(*, product_type: str | None = None) -> bool:
    """Whether stored DNs are calibrated backscatter for *product_type*.

    False for GRD: the stored value is detected amplitude, and sigma0 must be
    derived through the calibration LUT. Scoped rather than a bare ``False`` so
    that adding SLC or a calibrated derivative later cannot silently change the
    answer for existing call sites.
    """
    return pixel_value_convention(product_type=product_type) != "Detected"


def dual_pol_channels(*, product_class: str | None = None) -> tuple[str, ...]:
    """Polarisation channels for a product class (``'1SDV'``)."""
    if product_class is None:
        raise ScopeRequired(
            "dual_pol_channels() requires product_class= (e.g. '1SDV'). "
            "Single-pol products carry one channel, not two."
        )
    if product_class != "1SDV":
        raise UnknownScope(f"this frozen table covers 1SDV only, not {product_class!r}")
    return _FACTS.get_as("dual_pol", tuple)


def explain(name: str) -> SpecFact:
    """Return the citation, scope and witness line for a fact."""
    return _FACTS.explain(name)


def fact_names() -> tuple[str, ...]:
    return _FACTS.names()
