"""Introspection types.

``SpecFact`` is deliberately *not* how facts are read. It is what
:func:`geospatial_spec.explain` returns — a description of a fact, carrying its
citation and the witness line that corroborates it, for tooling and error
messages.

The distinction is the product. A fact you can read as ``FACTS[0].value`` is a
bare constant wearing a dataclass, and a call site can dereference it without
answering the question the guard exists to force ("does my data carry the
offset?"). So ``SpecFact`` is a *return value*, never a module-level constant,
and it is never the path by which a caller obtains a number to compute with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SpecFact:
    """A fact, its authority, and the witness that corroborates it.

    Returned by :func:`geospatial_spec.explain`. The ``value`` field is present
    because an explanation without the value is useless to a human reading an
    error message — but reaching it requires having already called ``explain``
    with the scope that identifies *which* fact applies, which is the same
    question the guard functions force. It is an explanation, not an accessor.
    """

    name: str
    value: Any
    cite: str
    scope: str
    witness: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        parts = [f"{self.name} = {self.value!r}", f"  scope: {self.scope}", f"  cite:  {self.cite}"]
        if self.witness:
            parts.append(f"  witness: {self.witness}")
        parts.extend(f"  note:  {n}" for n in self.notes)
        return "\n".join(parts)
