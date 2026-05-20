"""Smoke tests — for every gear type, the default download path must work.

This is the layer you'd run on every commit. If any of these fail, the build
is not shippable, regardless of what the rest of the suite says.

Maps to: GEN-001, GEN-002, SPUR-001, HEL-001, DH-001, ISP-001, IHEL-001,
         IDH-001, RACK-001, BEV-001 in Test_Cases_STLGears.xlsx
"""
import pytest

from pages.generator_page import GEAR_TYPES
from utils.stl_validator import is_valid_stl, summarize_stl

pytestmark = pytest.mark.smoke


@pytest.fixture(autouse=True)
def _dismiss_banners(generator_page):
    """Banners can cover Start Design buttons; dismiss before each test."""
    # Dismiss up to two banners (page can show more than one at a time)
    for _ in range(2):
        if not generator_page.dismiss_banner_if_present():
            break


@pytest.mark.parametrize("gear_type", GEAR_TYPES)
def test_default_download_per_gear_type(generator_page, downloads_dir, gear_type):
    """Each gear type produces a downloadable, parseable STL with defaults."""
    stl_path = generator_page.smoke_download(gear_type, downloads_dir, hole_type="None")
    assert stl_path.exists(), f"STL file not produced for {gear_type}"
    assert is_valid_stl(stl_path), f"STL for {gear_type} failed validation"

    summary = summarize_stl(stl_path)
    # Sanity: a real gear should have hundreds of triangles minimum
    assert summary.triangle_count >= 100, (
        f"Triangle count suspiciously low for {gear_type}: "
        f"{summary.triangle_count}"
    )
    # Bounding box must have non-zero volume in all axes for a gear
    extents = [mx - mn for mn, mx in zip(summary.bbox_min, summary.bbox_max)]
    assert all(e > 0 for e in extents), (
        f"Degenerate bounding box for {gear_type}: extents={extents}"
    )


def test_spur_with_each_hole_type(generator_page, downloads_dir):
    """Spur Gear must work with every hole type variant (None excluded — tested above)."""
    for hole in ("Hollow", "Squared", "Hexagonal", "Circular", "Keyway"):
        # Re-open the form each time to reset state
        generator_page.open()
        for _ in range(2):
            if not generator_page.dismiss_banner_if_present():
                break
        stl_path = generator_page.smoke_download(
            "Spur Gear", downloads_dir, hole_type=hole
        )
        assert is_valid_stl(stl_path), f"Spur Gear / {hole} hole failed validation"
