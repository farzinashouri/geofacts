"""The make-or-break property, enforced mechanically (Plan 20 trap 1).

The one feature three independent evaluations called defensible is that a
scoped fact cannot be dereferenced without its scope. That property erodes the
first time someone wants ``S2_BOA_ADD_OFFSET`` for an f-string, and code review
will not reliably catch it — a new module-level constant looks like every other
line in a diff.

So it is a test. Every public name in every public module must be a callable, an
exception class, or an enum. If this test fails, the package has stopped being
what it is for.
"""

from __future__ import annotations

import enum
import importlib
import inspect
import pkgutil

import pytest

import geospatial_spec

#: Public modules a user is expected to import from.
PUBLIC_MODULES = [
    "geospatial_spec",
    "geospatial_spec.sentinel2",
    "geospatial_spec.sentinel1",
    "geospatial_spec.common",
    "geospatial_spec.exceptions",
]


def _public_names(module) -> list[str]:
    exported = getattr(module, "__all__", None)
    if exported is not None:
        return list(exported)
    return [n for n in dir(module) if not n.startswith("_")]


def _is_permitted(obj) -> bool:
    """Callables, exception classes and enums may be public. Values may not.

    Enum *members* are values and are rejected; enum *classes* are permitted,
    since reaching a member still requires naming it.
    """
    if isinstance(obj, enum.Enum):
        return False
    if inspect.isclass(obj):
        return True  # classes are constructors, i.e. callables
    if inspect.ismodule(obj):
        return True
    return callable(obj)


@pytest.mark.parametrize("module_name", PUBLIC_MODULES)
def test_public_surface_exposes_no_bare_values(module_name: str) -> None:
    module = importlib.import_module(module_name)
    offenders = []
    for name in _public_names(module):
        obj = getattr(module, name)
        if name == "__version__":
            continue  # a version string is metadata, not a spec fact
        if not _is_permitted(obj):
            offenders.append(f"{module_name}.{name} = {obj!r}")
    assert not offenders, (
        "Public names must be callable, an exception, an enum, or a module. "
        "A bare value lets a call site dereference a fact without supplying "
        "the scope that makes it correct:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("module_name", PUBLIC_MODULES)
def test_no_public_numeric_or_string_constants(module_name: str) -> None:
    """The specific regression: a fact re-exported as a number or string."""
    module = importlib.import_module(module_name)
    offenders = [
        f"{module_name}.{name}"
        for name in _public_names(module)
        if name != "__version__"
        and isinstance(getattr(module, name), (int, float, str, bytes, tuple, list, dict, set))
    ]
    assert not offenders, (
        "These public names are plain data and must become guard functions: "
        + ", ".join(offenders)
    )


def test_the_offset_is_not_importable_by_any_obvious_name() -> None:
    """Trap 1, named directly: the value that started this must stay unreachable."""
    import geospatial_spec.sentinel2 as s2

    forbidden = [
        "S2_BOA_ADD_OFFSET", "BOA_ADD_OFFSET", "OFFSET", "S2_OFFSET",
        "S2_BOA_QUANTIFICATION_VALUE", "QUANTIFICATION_VALUE",
        "S2_NODATA", "NODATA", "FACTS",
    ]
    present = [name for name in forbidden if hasattr(s2, name)]
    assert not present, f"bare constants have re-entered the public surface: {present}"


def test_every_submodule_is_covered_by_this_test() -> None:
    """A new public module must not escape the check by being new."""
    discovered = {
        f"geospatial_spec.{m.name}"
        for m in pkgutil.iter_modules(geospatial_spec.__path__)
        if not m.name.startswith("_")
    }
    uncovered = discovered - set(PUBLIC_MODULES)
    assert not uncovered, (
        f"new public modules are not covered by the bare-constant check: "
        f"{sorted(uncovered)}. Add them to PUBLIC_MODULES."
    )


def test_facts_are_reachable_only_through_explain() -> None:
    """``explain`` is the sole path to a raw value, and it costs an explicit name."""
    import geospatial_spec.sentinel2 as s2

    fact = s2.explain("boa_add_offset")
    assert fact.value == -1000
    assert fact.cite and fact.scope
    # And it carries the caveat, which a bare constant cannot.
    assert "04.00" in fact.scope
