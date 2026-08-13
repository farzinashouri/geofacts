"""Machine-check every fact against real product metadata.

The mechanism that makes this package a tool rather than a lookup table: a
hand-written "spec-accurate" constant is only worth depending on if it is
verified against the actual authority, not the author's reading of a PDF. The
witnesses under ``src/geospatial_spec/_witnesses/`` are genuine ESA product
metadata (see PROVENANCE.md); each test asserts that a registered fact matches
what a real granule declares.

A disagreement here means the package would ship the defect it exists to
prevent, so these tests are not optional and the witnesses are not editable.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import pytest

import geospatial_spec.sentinel1 as s1
import geospatial_spec.sentinel2 as s2
from geospatial_spec.exceptions import BaselineMismatch, NodataUndeclared, ScopeRequired

WITNESSES = Path(s2.__file__).parent / "_witnesses"


@pytest.fixture(scope="module")
def mtd():
    return ElementTree.parse(WITNESSES / "MTD_MSIL2A_N0400.xml").getroot()


@pytest.fixture(scope="module")
def annotation():
    return ElementTree.parse(WITNESSES / "s1a-iw-grd-vv-annotation.xml").getroot()


# ------------------------------------------------ the table checks itself


def test_every_s2_fact_agrees_with_its_witness() -> None:
    assert s2._FACTS.check_witnesses() == []


def test_every_s1_fact_agrees_with_its_witness() -> None:
    assert s1._FACTS.check_witnesses() == []


def test_unwitnessed_facts_are_few_and_declared() -> None:
    """Every unwitnessed fact is a liability; the list is allowed but pinned."""
    assert s2._FACTS.unwitnessed() == ("offset_baseline_date",)
    assert s1._FACTS.unwitnessed() == ("dual_pol",)


# ------------------------------------------------------------- S2, directly


def test_witness_is_the_offset_baseline(mtd) -> None:
    assert next(mtd.iter("PROCESSING_BASELINE")).text == s2._FACTS.get("offset_baseline")


def test_boa_add_offset_all_13_bands(mtd) -> None:
    offsets = [int(e.text) for e in mtd.iter("BOA_ADD_OFFSET")]
    assert len(offsets) == 13
    assert set(offsets) == {s2.boa_offset(baseline="04.00")}


def test_quantification_value(mtd) -> None:
    declared = int(next(mtd.iter("BOA_QUANTIFICATION_VALUE")).text)
    assert declared == s2.quantification(baseline="04.00")


def test_special_values_nodata_and_saturated(mtd) -> None:
    declared = {
        e.find("SPECIAL_VALUE_TEXT").text: int(e.find("SPECIAL_VALUE_INDEX").text)
        for e in mtd.iter("Special_Values")
    }
    assert declared["NODATA"] == s2.nodata_value(product="S2_L2A")
    assert declared["SATURATED"] == s2.explain("saturated").value


def test_band_resolutions_match_spectral_information(mtd) -> None:
    declared = {
        e.attrib["physicalBand"]: int(e.find("RESOLUTION").text)
        for e in mtd.iter("Spectral_Information")
    }
    assert declared == s2.explain("band_resolution_m").value


def test_scl_classes_match_scene_classification_list(mtd) -> None:
    declared = {
        int(e.find("SCENE_CLASSIFICATION_INDEX").text): e.find(
            "SCENE_CLASSIFICATION_TEXT"
        ).text
        for e in mtd.iter("Scene_Classification_ID")
    }
    assert declared == s2.explain("scl_classes").value


# ------------------------------------------------------------- S1, directly


def test_grd_product_type(annotation) -> None:
    assert annotation.findtext("adsHeader/productType") == s1.explain("product_type").value


def test_grd_pixels_are_detected_amplitude_not_db(annotation) -> None:
    assert next(annotation.iter("pixelValue")).text == s1.pixel_value_convention(
        product_type="GRD"
    )
    assert s1.is_calibrated(product_type="GRD") is False


def test_grd_output_pixels_are_uint16(annotation) -> None:
    assert next(annotation.iter("outputPixels")).text == s1.explain("output_pixels").value


def test_iw_grdh_pixel_spacing(annotation) -> None:
    rng = float(next(annotation.iter("rangePixelSpacing")).text)
    azi = float(next(annotation.iter("azimuthPixelSpacing")).text)
    assert rng == azi == s1.pixel_spacing_m(mode="IW", resolution="GRDH")


def test_witness_polarisation_is_in_dual_pol_set(annotation) -> None:
    assert annotation.findtext("adsHeader/polarisation") in s1.dual_pol_channels(
        product_class="1SDV"
    )


# --------------------------------------------------- the guard property itself


def test_offset_requires_scope() -> None:
    with pytest.raises(ScopeRequired):
        s2.boa_offset()
    with pytest.raises(ScopeRequired):
        s2.boa_offset(baseline="04.00", acquired="2022-03-01")


def test_offset_is_zero_before_the_dated_change() -> None:
    """Trap 3 promoted to the product: baseline 04.00 is a *dated* change."""
    assert s2.boa_offset(baseline="04.00") == -1000
    assert s2.boa_offset(baseline="03.01") == 0
    assert s2.boa_offset(acquired="2022-03-01") == -1000
    assert s2.boa_offset(acquired="2021-06-01") == 0
    assert s2.boa_offset(acquired=date(2022, 1, 25)) == -1000
    assert s2.boa_offset(acquired=date(2022, 1, 24)) == 0


def test_to_reflectance_applies_the_offset_exactly_once() -> None:
    assert s2.to_reflectance(3000, baseline="04.00") == pytest.approx(0.2)
    assert s2.to_reflectance(2000, baseline="03.01") == pytest.approx(0.2)


def test_s1_guards_require_scope() -> None:
    with pytest.raises(ScopeRequired):
        s1.pixel_spacing_m()
    with pytest.raises(ScopeRequired):
        s1.pixel_value_convention()
    with pytest.raises(ScopeRequired):
        s1.dual_pol_channels()


# ----------------------------------------------------------- nodata surface


def test_zero_is_ambiguous_for_l2a() -> None:
    assert s2.nodata_value(product="S2_L2A") == 0
    assert s2.is_ambiguous_zero(product="S2_L2A") is True


def test_resample_policy_names_both_ends() -> None:
    policy = s2.resample_nodata_policy(product="S2_L2A")
    assert policy["src_nodata"] == 0 and policy["dst_nodata"] == 0
    assert "bilinear" in policy["required_for"]
    assert "nearest" in policy["safe_without"]


def test_assert_nodata_declared_catches_the_live_bug() -> None:
    """Bilinear with neither end declared is the confirmed smearing bug."""
    with pytest.raises(NodataUndeclared):
        s2.assert_nodata_declared({}, resampling="bilinear")
    # Declared on both ends: fine.
    s2.assert_nodata_declared(
        {"src_nodata": 0, "dst_nodata": 0}, resampling="bilinear"
    )
    # A single profile-level nodata covers both.
    s2.assert_nodata_declared({"nodata": 0}, resampling="bilinear")
    # Nearest neighbour does not interpolate, so it is safe undeclared.
    s2.assert_nodata_declared({}, resampling="nearest")


# ------------------------------------------------------------ runtime guard


def test_assert_baseline_consistent_fires_on_mismatch() -> None:
    post = {"PROCESSING_BASELINE": "04.00"}
    pre = {"PROCESSING_BASELINE": "03.01"}

    with pytest.raises(BaselineMismatch, match="off by"):
        s2.assert_baseline_consistent(post, assumes="pre-04.00")
    with pytest.raises(BaselineMismatch):
        s2.assert_baseline_consistent(pre, assumes="post-04.00")

    s2.assert_baseline_consistent(post, assumes="post-04.00")
    s2.assert_baseline_consistent(pre, assumes="pre-04.00")
    s2.assert_baseline_consistent(post, assumes="04.00")


def test_assert_baseline_consistent_refuses_to_guess() -> None:
    with pytest.raises(BaselineMismatch, match="no 'PROCESSING_BASELINE'"):
        s2.assert_baseline_consistent({}, assumes="04.00")
