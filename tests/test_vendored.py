"""The vendored single file must behave like the package, not merely exist.

Rejector C's line was *"if vendoring is one command, we'd have taken it."* A
vendored file that has silently drifted, or that quietly lost its witness
checking on the way through the generator, is worse than none: it looks
maintained and is not. So the generated file is imported here as a stranger
would import it and put through the same properties as the package.
"""

from __future__ import annotations

import base64
import gzip
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VENDORED = ROOT / "vendored" / "geofacts.py"


def _builder():
    """Import scripts/build_vendored.py as a module."""
    path = ROOT / "scripts" / "build_vendored.py"
    spec = importlib.util.spec_from_file_location("build_vendored", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def vendored(tmp_path_factory):
    """Import the single file from a directory containing nothing else."""
    if not VENDORED.exists():
        pytest.skip("run scripts/build_vendored.py first")
    sandbox = tmp_path_factory.mktemp("vendored")
    shutil.copy(VENDORED, sandbox / "geofacts.py")
    sys.path.insert(0, str(sandbox))
    for name in [n for n in sys.modules if n.startswith("geofacts")]:
        del sys.modules[name]
    try:
        import geofacts as module

        yield module
    finally:
        sys.path.remove(str(sandbox))
        for name in [n for n in sys.modules if n.startswith("geofacts")]:
            del sys.modules[name]


def test_it_has_not_drifted() -> None:
    """CI gate: the committed file matches a fresh build."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_vendored.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_the_gate_ignores_zlib_version_differences() -> None:
    """zlib's output is not byte-stable across versions; the gate must not be.

    CI runs 3.11-3.13 with different zlib builds, so re-compressing the same
    witness legitimately yields different bytes. Drift means the *content*
    changed, never that the compressor did.
    """
    build = _builder()
    fresh = build.build()
    recompressed = build.build(compress=lambda raw: gzip.compress(raw, 1, mtime=0))
    assert recompressed != fresh, "compression level must actually change bytes"
    assert build.drift_reason(recompressed) is None


def test_the_gate_still_catches_real_drift() -> None:
    build = _builder()
    fresh = build.build()
    assert build.drift_reason(fresh) is None
    assert build.drift_reason(fresh.replace("__version__ = ", "__vers1on__ = ")) is not None
    assert build.drift_reason(fresh.replace("_EMBEDDED_WITNESSES", "_X", 1)) is not None


def test_the_gate_catches_a_tampered_witness() -> None:
    """A blob that no longer decompresses to the shipped witness is drift."""
    build = _builder()
    name = build.WITNESSES[0]
    raw = (build.PKG / "_witnesses" / name).read_bytes()
    tampered = base64.b64encode(gzip.compress(raw + b"<!-- edit -->", 9, mtime=0)).decode()
    swapped = build.build(compress=lambda _raw: base64.b64decode(tampered))
    assert build.drift_reason(swapped) is not None


def test_the_guard_survives_the_build(vendored) -> None:
    assert vendored.boa_offset(baseline="04.00") == -1000
    assert vendored.boa_offset(baseline="03.01") == 0
    with pytest.raises(TypeError):
        vendored.boa_offset()


def test_witnesses_are_embedded_and_still_checked(vendored) -> None:
    """The property that makes the table trustworthy must survive vendoring."""
    assert vendored._FACTS_sentinel2.check_witnesses() == []
    assert vendored._FACTS_sentinel1.check_witnesses() == []


def test_runtime_guards_survive_the_build(vendored) -> None:
    with pytest.raises(vendored.NodataUndeclared):
        vendored.assert_nodata_declared({}, resampling="bilinear")
    with pytest.raises(vendored.BaselineMismatch):
        vendored.assert_baseline_consistent(
            {"PROCESSING_BASELINE": "04.00"}, assumes="pre-04.00"
        )


def test_all_three_tables_are_reachable(vendored) -> None:
    """Concatenation must not let one module's _FACTS shadow another's."""
    assert vendored.nodata_value(product="S2_L2A") == 0
    assert vendored.s1_pixel_spacing_m(mode="IW", resolution="GRDH") == 10.0
    assert vendored.common_epsg_equivalent(4326, "EPSG:4326") is True


def test_it_has_no_third_party_imports() -> None:
    """Zero dependencies is the entire adoption argument."""
    source = VENDORED.read_text()
    allowed = {
        "base64", "gzip", "io", "enum", "json", "sys", "re", "argparse",
        "dataclasses", "datetime", "pathlib", "typing", "xml", "__future__",
    }
    offenders = []
    for line in source.splitlines():
        line = line.strip()
        if line.startswith(("import ", "from ")):
            root = line.split()[1].split(".")[0]
            if root not in allowed and not root.startswith("geofacts"):
                offenders.append(line)
    assert not offenders, f"vendored build grew dependencies: {offenders}"
