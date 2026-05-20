"""DXF Laser Cut Generator — smoke and validation tests.

Covers the three gear types exposed at /generators/lasercut:
  Internal Gear, Rack, Spur Gear

Two concerns are tested here:
  1. Smoke — happy-path download: does each gear type produce a non-empty .dxf?
  2. Validation — does the Internal Gear form reject non-positive Radial Thickness?

The TimeoutException-as-expected pattern (used in the rejection tests) is the
same one established in test_spur_gear.py: click Download, wait up to 8 s for
a file to appear, and treat a timeout as the *expected* outcome.  If a file
DOES arrive, the test fails via pytest.fail() with an explanation.

Maps to:
  DXF-001  Internal Gear   default download
  DXF-002  Rack            default download
  DXF-003  Spur Gear       default download
  DXFSP-001 Spur Gear      Number of Teeth = 6 (low boundary)
  DXFIN-001 Internal Gear  Radial Thickness = 0  → rejected
  DXFIN-002 Internal Gear  Radial Thickness = -3 → rejected
"""
import pytest
from selenium.common.exceptions import TimeoutException

from pages.dxf_generator_page import DXF_GEAR_TYPES

# Every test in this file is tagged dxf.  Smoke tests are additionally tagged
# smoke so they're included in the minimal "must-pass" run: pytest -m smoke.
pytestmark = pytest.mark.dxf


@pytest.fixture
def dxf_form(dxf_generator_page):
    """The DXF generator page with any site banners dismissed.

    We attempt to dismiss banners twice because the page can show two at once
    (e.g. a cookie notice on top of a promotional banner).  This mirrors the
    pattern used by test_generator_smoke.py for the STL generator.
    """
    for _ in range(2):
        if not dxf_generator_page.dismiss_banner_if_present():
            break
    return dxf_generator_page


# ---------------------------------------------------------------------------
# Smoke: one download per gear type (DXF-001, DXF-002, DXF-003)
# ---------------------------------------------------------------------------

@pytest.mark.smoke
@pytest.mark.parametrize("gear_type", DXF_GEAR_TYPES)
def test_dxf_default_download_per_gear_type(dxf_form, downloads_dir, gear_type):
    """DXF-001/002/003 — Default parameters produce a non-empty .dxf file.

    This is the DXF equivalent of test_default_download_per_gear_type in
    test_generator_smoke.py.  We do not validate the DXF content (no
    equivalent of stl_validator exists yet) — asserting non-zero size is
    the minimum meaningful check.
    """
    dxf_form.open_gear_form(gear_type)
    dxf_form.fill_default_parameters(gear_type)

    dxf_path = dxf_form.download_gear(downloads_dir)

    # Confirm the extension is actually .dxf.  If the server suddenly serves
    # an .stl or a .zip, wait_for_download would time out (because it looks
    # for .dxf specifically), but this assertion is a readable explanation of
    # what we required.
    assert dxf_path.suffix.lower() == ".dxf", (
        f"Expected a .dxf file for {gear_type}, got: {dxf_path.name}"
    )
    assert dxf_path.stat().st_size > 0, (
        f"Downloaded file for {gear_type} is empty (0 bytes) — "
        "the server may have returned an error body instead of a real DXF."
    )


# ---------------------------------------------------------------------------
# Smoke: boundary value — low tooth count (DXFSP-001)
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_dxf_spur_low_tooth_count(dxf_form, downloads_dir):
    """DXFSP-001 — Spur Gear with Number of Teeth = 6 (low boundary) must succeed.

    6 is the practical minimum for involute gear geometry.  If the refactored
    validator is too strict (e.g. minimum raised to 10) this test will fail and
    alert the team.
    """
    dxf_form.open_gear_form("Spur Gear")
    dxf_form.fill_default_parameters("Spur Gear")
    # Override the default (20) with the low boundary value
    dxf_form.set_parameter("Number of Teeth", 6)

    dxf_path = dxf_form.download_gear(downloads_dir)

    assert dxf_path.stat().st_size > 0, (
        "Spur Gear with Number of Teeth=6 produced an empty file — "
        "the generator may have silently failed on the low boundary."
    )


# ---------------------------------------------------------------------------
# Validation: Radial Thickness must be rejected when ≤ 0 (DXFIN-001/002)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "thickness,case_id",
    [
        (0,  "DXFIN-001"),
        (-3, "DXFIN-002"),
    ],
    ids=["radial_thickness=0", "radial_thickness=-3"],
)
def test_dxf_internal_radial_thickness_invalid_rejected(
    dxf_form, downloads_dir, thickness, case_id
):
    """DXFIN-001/002 — Radial Thickness ≤ 0 must be rejected (no .dxf within 8 s).

    Radial Thickness defines the physical wall of the ring gear.  Zero or
    negative thickness has no geometric meaning and should be caught by the
    form's validator before the generator runs.

    Why TimeoutException as the *expected* outcome?  We don't know the exact
    error-message selector yet, so we can't assert "an error banner appeared".
    Instead we assert the weaker but still meaningful property: no file was
    produced.  If a file does appear, the generator accepted a physically
    impossible input — that is the bug we are catching.
    """
    dxf_form.open_gear_form("Internal Gear")
    dxf_form.fill_default_parameters("Internal Gear")
    dxf_form.set_parameter("Radial Thickness", thickness)

    try:
        dxf_form.click_download()
        # wait_for_download raises TimeoutException after 8 s if no .dxf appears
        dxf_path = dxf_form.wait_for_download(downloads_dir, extensions=(".dxf",), timeout=8)
        # If we get here, the generator produced a file — that is the defect
        pytest.fail(
            f"[{case_id}] Radial Thickness={thickness} produced a DXF file "
            f"({dxf_path.name}, {dxf_path.stat().st_size} bytes). "
            "The form should have rejected this value before calling the generator."
        )
    except TimeoutException:
        # No file arrived — the form behaved correctly
        pass
