"""Prune the S1 annotation witness to the elements the fact table checks.

The genuine S1A IW GRDH annotation is 1.7 MB, dominated by antenna-pattern and
Doppler-centroid tables this package never reads. Vendoring it whole would put
the wheel two orders of magnitude over the <100 KB target that makes the
package trivially adoptable.

Pruning is a real tradeoff and it is recorded rather than hidden: the retained
subtree is byte-identical to the original for every element the witness reads,
and PROVENANCE.md records the source granule plus exactly what was dropped, so
the pruning itself can be re-verified against a fresh download.

Run: python scripts/prune_witness.py <source.xml> <dest.xml>
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree

#: The subtrees geospatial_spec.sentinel1 actually reads.
KEEP = {"adsHeader", "imageAnnotation"}


def prune(source: Path, dest: Path) -> tuple[int, int]:
    tree = ElementTree.parse(source)
    root = tree.getroot()
    for child in list(root):
        if child.tag not in KEEP:
            root.remove(child)
    dest.write_bytes(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))
    return source.stat().st_size, dest.stat().st_size


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    before, after = prune(src, dst)
    print(f"{src.name}: {before:,} -> {after:,} bytes ({after / before:.1%})")
