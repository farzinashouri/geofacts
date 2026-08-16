"""Machine-checked geospatial product facts, reachable only with their scope.

Constants like the Sentinel-2 BOA offset are load-bearing for any code that
computes on pixels, and they are conditional: right for one processing baseline
and wrong for another. This package makes that conditionality unavoidable. Every
public name is a callable that requires the scope which determines the answer,
so a call site cannot dereference a value without recording what its data is.

    >>> from geofacts.sentinel2 import boa_offset
    >>> boa_offset(baseline="04.00")
    -1000
    >>> boa_offset(baseline="03.01")
    0
    >>> boa_offset()
    Traceback (most recent call last):
    geofacts.exceptions.ScopeRequired: ...

Every fact carries two authorities: a specification citation and a *witness* —
a real product artifact, vendored and machine-checked in CI — so the table is
not one person's reading of a PDF.

Zero dependencies, permanently. That is the adoption argument, and it is why
this package never imports from ``geocase``.
"""

from __future__ import annotations

from . import _witness as witness
from ._table import FactTable
from ._types import SpecFact
from .exceptions import (
    BaselineMismatch,
    GeospatialSpecError,
    NodataUndeclared,
    ScopeRequired,
    UnknownScope,
)

__version__ = "0.1.0"

__all__ = [
    "FactTable",
    "SpecFact",
    "witness",
    "BaselineMismatch",
    "GeospatialSpecError",
    "NodataUndeclared",
    "ScopeRequired",
    "UnknownScope",
    "__version__",
]
