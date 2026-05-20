"""Site navigation tests — header, links, footer, banners.

Maps to: NAV-001 .. NAV-010 in Test_Cases_STLGears.xlsx
"""
import pytest

pytestmark = pytest.mark.navigation


@pytest.mark.smoke
def test_home_loads(home_page):
    """NAV — Home page loads with expected sections (STL/DXF/GF Generator)."""
    assert "STLGears" in home_page.title()
    assert home_page.is_present(home_page.SECTION_STL)
    assert home_page.is_present(home_page.SECTION_DXF)
    assert home_page.is_present(home_page.SECTION_GF)


@pytest.mark.smoke
def test_nav_home_link(generator_page, base_url):
    """NAV-002 — 'Home' link from the generator page returns to /."""
    generator_page.click(generator_page.NAV_HOME if False else (
        "xpath", "//a[normalize-space()='Home']"
    ))
    # Allow either exact base URL or base URL with trailing slash
    current = generator_page.current_url().rstrip("/")
    assert current == base_url.rstrip("/"), (
        f"Expected to land on {base_url!r}, got {current!r}"
    )


@pytest.mark.smoke
def test_nav_to_3dprint(home_page, base_url):
    """NAV-004 — Generators → 3D Printing link lands on /generators/3dprint."""
    home_page.click_try_3dprint()
    assert "/generators/3dprint" in home_page.current_url()


def test_footer_privacy_link_exists(home_page):
    """NAV-009a — Privacy Notice link exists in footer."""
    assert home_page.is_present(home_page.FOOTER_PRIVACY)


def test_footer_cookies_link_exists(home_page):
    """NAV-009b — Cookies link exists in footer."""
    assert home_page.is_present(home_page.FOOTER_COOKIES)


def test_banner_dismiss_if_present(generator_page):
    """NAV-010 — Banner dismiss button works (when banner shown)."""
    # Banner may or may not be present; test only enforces correctness when it is.
    if generator_page.is_present(generator_page.BANNER_CLOSE, timeout=2):
        generator_page.dismiss_banner_if_present()
        # After dismissal, the close-button locator should no longer match
        assert not generator_page.is_present(generator_page.BANNER_CLOSE, timeout=2)
