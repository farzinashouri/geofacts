"""Exceptions.

These are part of the public surface precisely because the package's value is
in what it *refuses* to answer. ``ScopeRequired`` is raised when a caller asks
for a scoped fact without supplying the scope; the other two are raised by the
runtime guards, which are importable from production code, not just tests.
"""

from __future__ import annotations

__all__ = [
    "GeospatialSpecError",
    "ScopeRequired",
    "BaselineMismatch",
    "NodataUndeclared",
    "UnknownScope",
]


class GeospatialSpecError(Exception):
    """Base class for every error this package raises."""


class ScopeRequired(GeospatialSpecError, TypeError):
    """A scoped fact was requested without the scope that determines it.

    Subclasses :class:`TypeError` because that is what a caller who wrote
    ``boa_offset()`` expects to catch, and because the mistake is genuinely a
    call-signature error.
    """


class BaselineMismatch(GeospatialSpecError):
    """Data's declared processing baseline contradicts what the code assumes.

    Raised by :func:`geofacts.sentinel2.assert_baseline_consistent`.
    The message names the offset the calling code's thresholds are wrong by,
    because "mismatch" alone does not tell a maintainer what to change.
    """


class NodataUndeclared(GeospatialSpecError):
    """A resampling or read profile omits the nodata declaration it needs.

    Raised by :func:`geofacts.sentinel2.assert_nodata_declared`. The
    live bug this exists for: bilinear resampling with neither ``src_nodata``
    nor ``dst_nodata`` set smears a nodata region into its valid neighbours,
    silently and in-bounds.
    """


class UnknownScope(GeospatialSpecError, ValueError):
    """The scope supplied is syntactically valid but not one this table knows."""
