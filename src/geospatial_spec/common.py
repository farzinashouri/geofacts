"""Cross-sensor conventions.

Facts that are not specific to one mission but still conditional enough that a
bare constant gets them wrong. Kept deliberately small — this package's scope
discipline is Sentinel-2 and Sentinel-1, and a "common" module is where scope
creep starts.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._table import FactTable
from ._types import SpecFact
from .exceptions import ScopeRequired, UnknownScope

__all__ = [
    "is_interpolating",
    "normalise_epsg",
    "epsg_equivalent",
    "assert_nodata_policy",
    "explain",
    "fact_names",
]

_FACTS = FactTable("common")

_FACTS.register(
    "interpolating_resamplers",
    ("bilinear", "cubic", "cubic_spline", "lanczos", "average", "rms", "mode"),
    cite="GDAL warp resampling algorithms; any kernel touching >1 source sample",
    scope="resampling of data carrying a nodata sentinel",
    witness=None,
    notes=(
        "These mix neighbouring samples, so an undeclared nodata region is "
        "averaged into valid neighbours. 'nearest' is the only safe default.",
    ),
)
_FACTS.register(
    "epsg_axis_order_authority",
    "authority-defined",
    cite="OGC 08-015r2 / EPSG registry axis order",
    scope="EPSG codes interpreted per authority, not per library default",
    witness=None,
    notes=(
        "EPSG:4326 is lat,lon by authority; most raster libraries present "
        "lon,lat. A round-trip through int vs str EPSG can silently change "
        "which convention a library applies.",
    ),
)


def is_interpolating(resampling: str) -> bool:
    """True if *resampling* mixes multiple source samples per output pixel.

    The nodata question follows directly: an interpolating resampler needs its
    nodata declared, a nearest-neighbour one does not.
    """
    return resampling in _FACTS.get("interpolating_resamplers")


def normalise_epsg(code: Any) -> str:
    """Normalise an EPSG code to canonical ``"EPSG:NNNN"`` form.

    Accepts ``4326``, ``"4326"``, ``"EPSG:4326"``, ``"epsg:4326"``. Raises on
    ``None`` rather than producing ``"EPSG:None"`` — the live failure this
    exists for is ``int(GetAuthorityCode(...))`` when the authority code is
    absent, which crashes far from the cause.
    """
    if code is None:
        raise UnknownScope(
            "EPSG code is None. A CRS with no authority code cannot be "
            "normalised; handle the unprojected/custom-CRS case explicitly "
            "rather than coercing None."
        )
    text = str(code).strip()
    if not text:
        raise UnknownScope("EPSG code is empty")
    if ":" in text:
        authority, _, number = text.partition(":")
        if authority.upper() != "EPSG":
            raise UnknownScope(f"not an EPSG code: {code!r}")
        text = number
    if not text.isdigit():
        raise UnknownScope(f"EPSG code {code!r} is not numeric")
    return f"EPSG:{int(text)}"


def epsg_equivalent(a: Any, b: Any) -> bool:
    """Whether two EPSG references denote the same code across str/int forms.

    ``epsg_equivalent(4326, "EPSG:4326")`` is True. Direct ``==`` between those
    is False, which is the silent identity mismatch this guards.
    """
    return normalise_epsg(a) == normalise_epsg(b)


def assert_nodata_policy(
    profile: Mapping[str, Any], *, resampling: str | None = None
) -> None:
    """Sensor-agnostic form of the nodata guard.

    Raises :class:`ScopeRequired` if *resampling* is not supplied — the answer
    depends entirely on it. For Sentinel-2 specifically, prefer
    :func:`geospatial_spec.sentinel2.assert_nodata_declared`, which knows the
    sentinel value as well as the policy.
    """
    if resampling is None:
        raise ScopeRequired(
            "assert_nodata_policy() requires resampling=; whether nodata must "
            "be declared depends on whether the kernel interpolates."
        )
    if not is_interpolating(resampling):
        return
    declared = any(
        profile.get(key) is not None
        for key in ("nodata", "src_nodata", "dst_nodata")
    )
    if not declared:
        from .exceptions import NodataUndeclared

        raise NodataUndeclared(
            f"{resampling} interpolates across samples but this profile "
            f"declares no nodata. The masked region will be averaged into its "
            f"valid neighbours, in-bounds and plausible."
        )


def explain(name: str) -> SpecFact:
    """Return the citation, scope and witness line for a fact."""
    return _FACTS.explain(name)


def fact_names() -> tuple[str, ...]:
    return _FACTS.names()
