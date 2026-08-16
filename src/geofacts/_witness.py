"""The witness protocol.

Every fact in this package carries two independent authorities: a specification
citation (a human-readable pointer to the document) and a *witness* — a real
artifact that declares the same value, machine-checked in CI. A fact with only
a citation is one person's reading of a PDF, which is the defect this project
is named after.

A witness is any callable returning ``dict[str, object]``: a mapping from fact
name to the value the artifact declares. Nothing here is ESA-specific. A team
can check their own constants against their DB schema, an OpenAPI document, or
a spec JSON, which is what makes this a tool rather than a lookup table.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from xml.etree import ElementTree

WitnessFn = Callable[[], "dict[str, object]"]


class Witness(Protocol):
    """Anything that can state what an external artifact declares."""

    def __call__(self) -> dict[str, object]: ...


def from_json(path: str | Path, *, key: str | None = None) -> WitnessFn:
    """Witness backed by a JSON document.

    ``key`` optionally selects a nested object to use as the fact mapping.
    """

    def _read() -> dict[str, object]:
        data = json.loads(Path(path).read_text())
        if key is not None:
            data = data[key]
        if not isinstance(data, dict):
            raise TypeError(f"witness {path} did not yield an object")
        return data

    return _read


ExtractFn = Callable[[ElementTree.Element], "dict[str, object]"]


def text(element: ElementTree.Element | None, path: str | None = None) -> str:
    """Required text content of an element, or a clear error naming what is absent.

    Shared by every XML-backed witness. A witness missing a field it is supposed
    to corroborate is a broken witness, and it must say so loudly rather than
    letting ``None`` slide into the fact table where it would compare unequal to
    everything and produce a confusing failure far from the cause.
    """
    if path is None:
        target = element
    else:
        target = element.find(path) if element is not None else None
    if target is None or target.text is None:
        raise ValueError(f"witness is missing required element {path or '(self)'}")
    return target.text.strip()


def from_xml(path: str | Path, extract: ExtractFn) -> WitnessFn:
    """Witness backed by an XML document and an extraction function.

    The extraction function receives the parsed root element and returns the
    fact mapping. This is the form the Sentinel witnesses use, because product
    metadata is XML and the interesting values are scattered across it.
    """

    def _read() -> dict[str, object]:
        root = ElementTree.parse(Path(path)).getroot()
        return extract(root)

    return _read


def from_mapping(mapping: dict[str, object]) -> WitnessFn:
    """Witness from an in-memory mapping.

    For facts whose authority is a document that cannot be vendored (a paywalled
    standard, a value only stated in prose). Weaker than the others by design:
    it records a transcription rather than checking one, so it is used sparingly
    and the citation carries the weight.
    """

    def _read() -> dict[str, object]:
        return dict(mapping)

    return _read
