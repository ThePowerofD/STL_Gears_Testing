"""Spur Gear — boundary value, equivalence partitioning, and negative tests.

This is the deepest functional coverage file in the suite. The Spur Gear has
the same numeric parameters that appear on every other gear, so once you're
happy with the patterns here, copy this file as a template for the others.

Test design techniques demonstrated
-----------------------------------
- Boundary value analysis (BVA): min, min+epsilon, max-epsilon, max
- Equivalence partitioning: one representative from each valid class
- Negative testing: values outside valid ranges
- Decision tables (implicit): hole-type × parameter combinations

Maps to: SPUR-001 .. SPUR-014 in Test_Cases_STLGears.xlsx
"""
import pytest

from utils.stl_validator import is_valid_stl

pytestmark = [pytest.mark.spur]


@pytest.fixture
def spur_form(generator_page):
    """Open the Spur Gear form once per test, with banners dismissed."""
    for _ in range(2):
        if not generator_page.dismiss_banner_if_present():
            break
    generator_page.open_gear_form("Spur Gear")
    return generator_page


# ---------- Happy-path baseline ----------

@pytest.mark.smoke
def test_spur_defaults_download(spur_form, downloads_dir):
    """SPUR-001 — Default parameters produce a valid STL."""
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.select_hole_type("None")
    stl_path = spur_form.download_gear(downloads_dir)
    assert is_valid_stl(stl_path)


# ---------- Module: boundary + negative ----------

@pytest.mark.parametrize(
    "module_value,expect_download",
    [
        (0.1, True),    # SPUR-002 — low boundary, should still work
        (0.5, True),    # SPUR — common small module
        (2.0, True),    # SPUR — typical default
        (10.0, True),   # SPUR — large but valid
        (50.0, True),   # SPUR-003 — high boundary
    ],
    ids=["module=0.1", "module=0.5", "module=2.0", "module=10.0", "module=50.0"],
)
def test_spur_module_valid_values(spur_form, downloads_dir, module_value, expect_download):
    """SPUR — Module across the valid range produces valid STLs (BVA + EP)."""
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.set_parameter("Module", module_value)
    spur_form.select_hole_type("None")
    if expect_download:
        stl_path = spur_form.download_gear(downloads_dir)
        assert is_valid_stl(stl_path), f"STL invalid at module={module_value}"


@pytest.mark.parametrize(
    "module_value",
    [0, -1, -5.5],
    ids=["module=0", "module=-1", "module=-5.5"],
)
def test_spur_module_invalid_values_rejected(spur_form, downloads_dir, module_value):
    """SPUR-004/005 — Negative or zero Module must be rejected (no STL delivered)."""
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.set_parameter("Module", module_value)
    spur_form.select_hole_type("None")
    # Try to download — we EXPECT failure (no STL within timeout)
    from selenium.common.exceptions import TimeoutException
    try:
        spur_form.click_download()
        stl_path = spur_form.wait_for_download(downloads_dir, timeout=8)
        pytest.fail(
            f"Module={module_value} produced an STL ({stl_path.name}); "
            "the form should have rejected this value."
        )
    except TimeoutException:
        # Expected — the app should NOT generate from invalid input
        pass


# ---------- Number of Teeth: boundary + negative ----------

@pytest.mark.parametrize(
    "teeth,expect_valid",
    [
        (6,   True),   # SPUR-006 — low boundary
        (12,  True),   # equivalence class: typical small
        (20,  True),   # default
        (100, True),   # equivalence class: large
        (200, True),   # SPUR-007 — high boundary
    ],
)
def test_spur_teeth_valid(spur_form, downloads_dir, teeth, expect_valid):
    """SPUR-006/007 — Number of Teeth across valid range."""
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.set_parameter("Number of Teeth", teeth)
    spur_form.select_hole_type("None")
    stl_path = spur_form.download_gear(downloads_dir)
    assert is_valid_stl(stl_path)


@pytest.mark.parametrize("teeth", [1, 2, 0, -5])
def test_spur_teeth_invalid_rejected(spur_form, downloads_dir, teeth):
    """SPUR-008 — Number of Teeth below physical minimum must be rejected."""
    from selenium.common.exceptions import TimeoutException
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.set_parameter("Number of Teeth", teeth)
    spur_form.select_hole_type("None")
    try:
        spur_form.click_download()
        spur_form.wait_for_download(downloads_dir, timeout=8)
        pytest.fail(f"Number of Teeth={teeth} should have been rejected.")
    except TimeoutException:
        pass


# ---------- Pressure Angle: equivalence partitioning ----------

@pytest.mark.parametrize("angle", [20, 25, 14.5, 30])
def test_spur_pressure_angle_standard_values(spur_form, downloads_dir, angle):
    """SPUR-009/010 — Standard pressure angles all work."""
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.set_parameter("Pressure Angle", angle)
    spur_form.select_hole_type("None")
    stl_path = spur_form.download_gear(downloads_dir)
    assert is_valid_stl(stl_path)


# ---------- Profile Shift: tooltip says -1 ≤ X ≤ 1 ----------

@pytest.mark.parametrize("x", [-1.0, -0.5, 0, 0.5, 1.0])
def test_spur_profile_shift_in_range(spur_form, downloads_dir, x):
    """SPUR-011 — Profile shift values inside [-1, 1] should generate."""
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.set_parameter("Profile Shift", x)
    spur_form.select_hole_type("None")
    stl_path = spur_form.download_gear(downloads_dir)
    assert is_valid_stl(stl_path), f"STL invalid at X={x}"


@pytest.mark.parametrize("x", [-1.5, 1.5, 2.0, -10])
def test_spur_profile_shift_out_of_range(spur_form, downloads_dir, x):
    """SPUR-012 — Profile shift outside [-1, 1] must be rejected per tooltip spec."""
    from selenium.common.exceptions import TimeoutException
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.set_parameter("Profile Shift", x)
    spur_form.select_hole_type("None")
    try:
        spur_form.click_download()
        spur_form.wait_for_download(downloads_dir, timeout=8)
        pytest.fail(f"Profile Shift={x} should have been rejected (-1 ≤ X ≤ 1).")
    except TimeoutException:
        pass


# ---------- All hole types end-to-end ----------

@pytest.mark.parametrize(
    "hole_type",
    ["None", "Hollow", "Squared", "Hexagonal", "Circular", "Keyway"],
)
def test_spur_all_hole_types_produce_valid_stl(spur_form, downloads_dir, hole_type):
    """HOLE-001..006 — Each hole type produces a valid Spur Gear STL."""
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.select_hole_type(hole_type)
    stl_path = spur_form.download_gear(downloads_dir)
    assert is_valid_stl(stl_path)
