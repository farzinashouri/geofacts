"""The fact registry.

Values live here, private, keyed by name. Public modules expose *callables* that
consult this table after the caller has supplied the scope that determines which
value applies. Nothing in the public surface hands back a number without first
being told the context that makes the number correct.

``FactTable`` is also the extensibility surface (§1.4): a team registers their
own facts with their own citations and witnesses, and gets the same guard
discipline for their own domain.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from ._types import SpecFact
from ._witness import WitnessFn
from .exceptions import UnknownScope

F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")


@dataclass(frozen=True)
class _Entry:
    name: str
    value: Any
    cite: str
    scope: str
    witness: WitnessFn | None
    witness_key: str | None
    notes: tuple[str, ...]


class FactTable:
    """A named collection of spec facts, their citations, and their witnesses.

    Registration records a value; it does not expose one. The only way a caller
    reads a value is through a guard function that requires the scope.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._entries: dict[str, _Entry] = {}

    def register(
        self,
        name: str,
        value: Any,
        *,
        cite: str,
        scope: str,
        witness: WitnessFn | None = None,
        witness_key: str | None = None,
        notes: tuple[str, ...] = (),
    ) -> None:
        """Record a fact. ``witness_key`` defaults to ``name``."""
        if name in self._entries:
            raise ValueError(f"fact {name!r} is already registered in {self.name!r}")
        self._entries[name] = _Entry(
            name=name,
            value=value,
            cite=cite,
            scope=scope,
            witness=witness,
            witness_key=witness_key if witness_key is not None else name,
            notes=notes,
        )

    def get(self, name: str) -> Any:
        """Read a registered value. Private by convention — guards call this."""
        try:
            return self._entries[name].value
        except KeyError:
            raise UnknownScope(f"{self.name!r} has no fact named {name!r}") from None

    def get_as(self, name: str, kind: type[T]) -> T:
        """Read a registered value, asserting its type.

        Guard functions declare concrete return types; this keeps that promise
        checkable instead of laundering every value through ``Any``.
        """
        value = self.get(name)
        if not isinstance(value, kind):
            raise TypeError(
                f"fact {name!r} is {type(value).__name__}, not {kind.__name__}"
            )
        return value

    def explain(self, name: str) -> SpecFact:
        """Return the citation, scope and witness line for *name*."""
        try:
            entry = self._entries[name]
        except KeyError:
            raise UnknownScope(f"{self.name!r} has no fact named {name!r}") from None
        witness_line = None
        if entry.witness is not None:
            declared = entry.witness()
            if entry.witness_key in declared:
                witness_line = f"{entry.witness_key} = {declared[entry.witness_key]!r}"
        return SpecFact(
            name=entry.name,
            value=entry.value,
            cite=entry.cite,
            scope=entry.scope,
            witness=witness_line,
            notes=entry.notes,
        )

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def check_witnesses(self) -> list[str]:
        """Verify every witnessed fact against its artifact.

        Returns a list of human-readable disagreements; empty means every fact
        that claims a witness is corroborated by it. This is what the fidelity
        test drives, and it is the reason the guard is not circular.
        """
        problems: list[str] = []
        for entry in self._entries.values():
            if entry.witness is None:
                continue
            declared = entry.witness()
            if entry.witness_key not in declared:
                problems.append(
                    f"{entry.name}: witness does not declare {entry.witness_key!r}"
                )
                continue
            if declared[entry.witness_key] != entry.value:
                problems.append(
                    f"{entry.name}: table says {entry.value!r}, "
                    f"witness says {declared[entry.witness_key]!r}"
                )
        return problems

    def unwitnessed(self) -> tuple[str, ...]:
        """Facts with no witness. Every one is a liability; keep the list short."""
        return tuple(
            sorted(n for n, e in self._entries.items() if e.witness is None)
        )

    def guard(
        self, *, cite: str, scope: str, witness: WitnessFn | None = None
    ) -> Callable[[F], F]:
        """Decorator registering a guard function's metadata (§1.4).

        The decorated function keeps its own body; this attaches the citation so
        ``explain`` and error messages can reach it, and so a team's own guards
        participate in the same witness checking.
        """

        def _decorate(fn: F) -> F:
            self.register(
                fn.__name__,
                value=None,
                cite=cite,
                scope=scope,
                witness=witness,
            )
            fn.__geofacts_cite__ = cite  # type: ignore[attr-defined]
            fn.__geofacts_scope__ = scope  # type: ignore[attr-defined]
            return fn

        return _decorate
