"""Dark / Light theme toggle tests.

The toggle is a NEW feature in the refactor; the exact component selector is
not yet known.  find_theme_toggle() tries three strategies in order so that:
  1. Once the dev adds data-testid="theme-toggle", strategy 1 is all we need.
  2. Until then, aria-label and class-based heuristics keep the tests runnable
     against the staging build.

current_theme() inspects the live DOM instead of clicking through the UI to
ask "what theme is active?".  This separation of concerns matters: a test that
uses the toggle to both *change* the theme and *read* the resulting theme is
not actually verifying that the DOM changed — it could be reading stale state.

Maps to:
  THM-001  Toggle visible on Home
  THM-002  Toggle visible on STL generator page
  THM-003  Clicking toggle changes theme
  THM-004  Theme persists across navigation (Home → /generators/3dprint)
  THM-005  Theme persists after page reload (localStorage / cookie check)
  THM-006  Multiple toggles produce no SEVERE browser-console errors
"""
import re

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.theme


# ---------------------------------------------------------------------------
# Module-level helpers — defined here per the spec because they are
# theme-specific utilities, not general page-object primitives.
# ---------------------------------------------------------------------------

def find_theme_toggle(driver):
    """Locate the theme toggle element, trying three selector strategies.

    Why three strategies?
      Strategy 1 (data-testid) is the stable, dev-maintained anchor.  Once the
      component has it, the other two become dead code.
      Strategy 2 (aria-label) targets accessible buttons — most well-built
      toggles have one of these.
      Strategy 3 (class heuristic) is a last resort for frameworks that express
      the control purely via CSS classes.

    We raise RuntimeError rather than letting WebDriverWait raise
    TimeoutException because the failure here is not a *timing* problem —
    the element either exists on the page or it does not.  A RuntimeError
    message can explain the fix directly, which a TimeoutException cannot.
    """
    strategies = [
        # Preferred: once the dev adds this, the others are never reached
        (By.CSS_SELECTOR, "[data-testid='theme-toggle']"),
        # Aria-label patterns — translate() makes the check case-insensitive
        (
            By.XPATH,
            "//*[self::button or self::input or self::label][@aria-label and ("
            "  contains(translate(@aria-label,'DARKLIGHT','darklight'),'dark') or "
            "  contains(translate(@aria-label,'DARKLIGHT','darklight'),'light') or "
            "  contains(translate(@aria-label,'THEME','theme'),'theme')"
            ")]",
        ),
        # Class heuristic: Tailwind, Radix UI, and others use these patterns
        (
            By.XPATH,
            "//*["
            "  contains(@class,'theme') or contains(@class,'dark-mode') or "
            "  contains(@class,'color-mode')"
            "][self::button or self::input[@type='checkbox'] or self::label]",
        ),
    ]

    for locator in strategies:
        try:
            # Short timeout per strategy; we loop rather than waiting 15 s on
            # each one before giving up.
            return WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located(locator)
            )
        except Exception:
            continue  # try next strategy

    raise RuntimeError(
        "Theme toggle not found with any known selector strategy. "
        "To fix: add data-testid='theme-toggle' to the toggle component "
        "in the refactored build, OR update the strategies list in "
        "find_theme_toggle() once the real selector is known."
    )


def current_theme(driver) -> str:
    """Return 'dark' or 'light' by reading the live DOM state.

    Checks three signals in priority order, because different CSS frameworks
    express the active theme differently:

      1. <html data-theme="dark|light">  — explicit, most reliable
      2. class="dark" or class="light" on <html> or <body>  — Tailwind pattern
      3. Computed background-color luminance of <body>  — last resort

    Why luminance?  If the site uses CSS custom properties (--background-color)
    without adding a class or attribute to the root element, the only way to
    observe the theme externally is to measure what the browser actually renders.
    Average RGB < 128 → closer to black → dark theme.
    """
    html_el = driver.find_element(By.TAG_NAME, "html")

    # --- Signal 1: data-theme attribute ---
    data_theme = (html_el.get_attribute("data-theme") or "").lower()
    if data_theme in ("dark", "light"):
        return data_theme

    # --- Signal 2: class-based theme ---
    for tag in ("html", "body"):
        el = driver.find_element(By.TAG_NAME, tag)
        classes = (el.get_attribute("class") or "").lower().split()
        if "dark" in classes:
            return "dark"
        if "light" in classes:
            return "light"

    # --- Signal 3: computed background luminance ---
    # getComputedStyle returns "rgb(r, g, b)" or "rgba(r, g, b, a)"
    rgb_str = driver.execute_script(
        "return window.getComputedStyle(document.body)"
        ".getPropertyValue('background-color');"
    )
    match = re.search(r"rgb[a]?\((\d+),\s*(\d+),\s*(\d+)", rgb_str or "")
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return "dark" if (r + g + b) / 3 < 128 else "light"

    # Cannot determine — assume light (safe default for most sites)
    return "light"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_theme_toggle_visible_on_home(home_page):
    """THM-001 — The theme toggle must be present and visible on the home page.

    If find_theme_toggle raises RuntimeError, the test fails with a message
    that explains exactly what selector to add — more useful than "element not
    found after 15 s".
    """
    toggle = find_theme_toggle(home_page.driver)
    assert toggle.is_displayed(), (
        "Theme toggle element was found in the DOM but is not visible — "
        "check that it is not hidden with display:none or visibility:hidden."
    )


def test_theme_toggle_visible_on_generator(generator_page):
    """THM-002 — The theme toggle must also be visible on the STL generator page.

    Tests that the toggle is part of the shared layout (header/nav), not just
    rendered on the home page.
    """
    toggle = find_theme_toggle(generator_page.driver)
    assert toggle.is_displayed(), (
        "Theme toggle is visible on Home but not on /generators/3dprint — "
        "check that the shared layout component is rendered on all routes."
    )


def test_theme_toggle_changes_theme(home_page):
    """THM-003 — Clicking the toggle must switch the active theme.

    We poll current_theme() with WebDriverWait rather than sleeping, because
    CSS transitions / React re-renders can take a few frames after the click
    before the class/attribute on <html> actually changes.
    """
    driver = home_page.driver
    initial_theme = current_theme(driver)

    find_theme_toggle(driver).click()

    # Poll until the theme flips or we time out.  We use a default-argument
    # closure (b=initial_theme) to capture the value at call time — a plain
    # `lambda d: current_theme(d) != initial_theme` would close over the
    # variable and could see a reassigned value if this code were refactored.
    try:
        WebDriverWait(driver, 5).until(
            lambda d, b=initial_theme: current_theme(d) != b
        )
    except Exception:
        pass  # Will surface in the assert below with a clear message

    assert current_theme(driver) != initial_theme, (
        f"Theme toggle click did not change the theme — "
        f"still '{initial_theme}' after click. "
        "Check that the toggle handler updates the class/data-theme on <html>."
    )


def test_theme_persists_across_navigation(home_page):
    """THM-004 — Dark theme set on Home must survive navigation to /generators/3dprint.

    Theme persistence across routes is typically implemented by reading
    localStorage on every page load.  If the generator page doesn't run that
    init code, it will revert to the default (usually light).
    """
    driver = home_page.driver

    # Ensure we are in dark mode before navigating, regardless of default
    if current_theme(driver) != "dark":
        find_theme_toggle(driver).click()
        WebDriverWait(driver, 5).until(lambda d: current_theme(d) == "dark")

    # Navigate using the same driver session — same browser window, same cookies,
    # same localStorage.  go_to() is inherited from BasePage.
    home_page.go_to("/generators/3dprint")

    # Wait for the generator page to finish loading before reading the theme.
    # We wait for "Spur Gear" text because that is always rendered on that page.
    home_page.find_visible(
        (By.XPATH, "//*[contains(text(),'Spur Gear')]"), timeout=15
    )

    assert current_theme(driver) == "dark", (
        "Theme reverted to light after navigating from Home to /generators/3dprint. "
        "Ensure the layout component reads the theme from localStorage on mount "
        "and applies it before first render."
    )


def test_theme_persists_after_reload(home_page):
    """THM-005 — Dark theme set on Home must survive a full page reload.

    driver.refresh() performs a hard reload (equivalent to pressing F5).
    localStorage and cookies survive; in-memory JS state does not.
    If the theme reverts after reload, the preference is stored only in memory
    and not persisted to localStorage or a cookie.
    """
    driver = home_page.driver

    if current_theme(driver) != "dark":
        find_theme_toggle(driver).click()
        WebDriverWait(driver, 5).until(lambda d: current_theme(d) == "dark")

    driver.refresh()

    # After reload the page must re-hydrate.  Waiting for <body> to be present
    # is a minimal confirmation that the DOM is available for inspection.
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    assert current_theme(driver) == "dark", (
        "Theme reverted to light after a page reload. "
        "Check that the toggle handler calls localStorage.setItem('theme', value) "
        "and that the page init script calls localStorage.getItem('theme') before "
        "first paint to avoid a flash of unstyled / wrong-theme content."
    )


def test_theme_toggle_no_console_errors(home_page):
    """THM-006 — Toggling the theme three times must not produce SEVERE browser errors.

    driver.get_log("browser") returns Chrome's browser console as a list of
    dicts: [{"level": "SEVERE", "message": "...", "timestamp": ...}, ...]
    SEVERE maps to console.error() calls and uncaught JS exceptions — the
    signals most likely to indicate a broken toggle handler.

    Firefox's GeckoDriver does not implement get_log() and raises
    WebDriverException.  We call pytest.skip() on that exception rather than
    failing, because the absence of Chrome log support is not a product defect.
    """
    driver = home_page.driver

    # Read and discard any logs that accumulated before this test started.
    # get_log() is destructive (each call returns and clears the buffer), so
    # we drain it now to get a clean baseline.
    try:
        driver.get_log("browser")
    except Exception:
        pytest.skip(
            "Browser log collection not supported on this browser/driver. "
            "Run with --browser chrome to enable this assertion."
        )

    # Toggle three times — covers both transition directions (light→dark→light→dark)
    for _ in range(3):
        before = current_theme(driver)
        find_theme_toggle(driver).click()
        # Wait for the DOM to actually update before the next click.
        # Without this, rapid clicks can outpace the React/JS state update.
        WebDriverWait(driver, 5).until(
            lambda d, b=before: current_theme(d) != b
        )

    # Collect logs accumulated during the three toggles
    logs = driver.get_log("browser")
    severe_messages = [
        entry["message"] for entry in logs if entry.get("level") == "SEVERE"
    ]

    assert not severe_messages, (
        f"SEVERE browser errors appeared during theme toggling ({len(severe_messages)} error(s)):\n"
        + "\n".join(severe_messages)
    )
