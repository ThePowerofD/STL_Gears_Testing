"""
Shared base class for all Page Objects.

Wraps the common Selenium patterns we use everywhere:
  - explicit waits (no implicit waits)
  - safe click that scrolls into view first
  - type / clear helper
  - JS-fueled scroll
  - wait_for_download helper for the STL download tests
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 30
Locator = tuple[str, str]


class BasePage:
    """Common helpers shared by every page object."""

    def __init__(self, driver: WebDriver, base_url: str):
        self.driver = driver
        self.base_url = base_url.rstrip("/")

    # ----- waits -----
    def wait(self, timeout: int = DEFAULT_TIMEOUT) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout)

    def find(self, locator: Locator, timeout: int = DEFAULT_TIMEOUT) -> WebElement:
        return self.wait(timeout).until(EC.presence_of_element_located(locator))

    def find_visible(self, locator: Locator, timeout: int = DEFAULT_TIMEOUT) -> WebElement:
        return self.wait(timeout).until(EC.visibility_of_element_located(locator))

    def find_clickable(self, locator: Locator, timeout: int = DEFAULT_TIMEOUT) -> WebElement:
        return self.wait(timeout).until(EC.element_to_be_clickable(locator))

    def find_all(self, locator: Locator, timeout: int = DEFAULT_TIMEOUT) -> list[WebElement]:
        return self.wait(timeout).until(EC.presence_of_all_elements_located(locator))

    def is_present(self, locator: Locator, timeout: int = 2) -> bool:
        try:
            self.find(locator, timeout=timeout)
            return True
        except TimeoutException:
            return False

    # ----- actions -----
    def click(self, locator: Locator, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Click after scrolling element into view; retry once on intercept/staleness."""
        for attempt in (1, 2):
            try:
                el = self.find_clickable(locator, timeout=timeout)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", el
                )
                el.click()
                return
            except (ElementClickInterceptedException, StaleElementReferenceException):
                if attempt == 2:
                    raise
                time.sleep(0.3)

    def find_first_visible(self, locator: Locator,
                           timeout: int = DEFAULT_TIMEOUT) -> WebElement:
        """Return the first matching element that is currently displayed.

        Why: locators on this site frequently match multiple elements where
        only one is visible — e.g. each gear type has its own form section
        rendered with display:none, and the Download button renders as both
        a <button> and an <a> sibling. EC.element_to_be_clickable only tests
        the first match it finds, so a hidden duplicate causes it to time out
        even though a clickable copy exists. This helper scans matches until
        it finds one is_displayed() returns True for.
        """
        end = time.time() + timeout
        while time.time() < end:
            try:
                for el in self.driver.find_elements(*locator):
                    if el.is_displayed():
                        return el
            except StaleElementReferenceException:
                pass
            time.sleep(0.2)
        raise TimeoutException(
            f"No visible element matched {locator} within {timeout}s"
        )

    def click_visible(self, locator: Locator,
                      timeout: int = DEFAULT_TIMEOUT) -> None:
        """Click the first VISIBLE element matching locator.

        Use this instead of click() when a locator may match hidden duplicates
        (Download buttons, gear-section inputs). Falls back to a JS click if
        the native click is intercepted twice.
        """
        for attempt in (1, 2, 3):
            try:
                el = self.find_first_visible(locator, timeout=timeout)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", el
                )
                if attempt < 3:
                    el.click()
                else:
                    self.driver.execute_script("arguments[0].click();", el)
                return
            except (ElementClickInterceptedException, StaleElementReferenceException):
                if attempt == 3:
                    raise
                time.sleep(0.3)

    def set_input_by_name(self, name: str, value) -> None:
        """Fill the first VISIBLE <input name='…'> with `value`.

        Why this rather than text-proximity XPath: the gear pages render all
        gear-type forms in the same DOM (display:none for inactive ones), so
        an input name like 'modulo' or 'z' appears multiple times. is_displayed()
        is the only reliable way to pick the input that belongs to the
        currently-open form.

        The JS pre-clear + dispatchEvent('input'/'change') pattern is required
        because the page uses framework-bound number inputs that ignore native
        clear() and won't recalculate previews unless 'change' fires.
        """
        el = self.find_first_visible((By.XPATH, f"//input[@name='{name}']"))
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});"
            "arguments[0].focus();"
            "arguments[0].value = '';"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            el,
        )
        el.send_keys(str(value))
        self.driver.execute_script(
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));"
            "arguments[0].blur();",
            el,
        )

    def type_into(self, locator: Locator, value: str | int | float,
                  clear: bool = True, timeout: int = DEFAULT_TIMEOUT) -> None:
        el = self.find_visible(locator, timeout=timeout)
        if clear:
            el.clear()
        el.send_keys(str(value))

    def set_number_input(self, locator: Locator, value: float) -> None:
        """For HTML5 number inputs that can be picky about clear()."""
        el = self.find_visible(locator)
        # Most reliable cross-browser way to fully reset a number field:
        self.driver.execute_script(
            "arguments[0].value = ''; "
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            el,
        )
        el.send_keys(str(value))

    def set_raw_text(self, locator: Locator, value: str) -> None:
        """Force an arbitrary string into a field via JavaScript.

        Why not send_keys? An <input type="number"> silently drops non-numeric
        characters typed via the keyboard, so payloads like 'abc' or
        '<script>alert(1)</script>' would never reach the input value.
        Direct assignment bypasses browser-side type filtering and lets us test
        what the *application* does when it receives unexpected input — the real
        security / robustness question.
        """
        el = self.find_visible(locator)
        self.driver.execute_script(
            "arguments[0].value = arguments[1]; "
            # Fire both input and change so any framework listeners pick it up
            "arguments[0].dispatchEvent(new Event('input',  {bubbles: true})); "
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            el,
            str(value),
        )

    def get_input_value(self, locator: Locator, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Return the current value attribute of an input field.

        Useful for asserting that a browser-side number input silently filtered
        a non-numeric keystroke (value will be '' or a numeric string, never
        the raw typed text).
        """
        el = self.find_visible(locator, timeout=timeout)
        return el.get_attribute("value") or ""

    def dismiss_banner_if_present(self) -> bool:
        """Dismiss a cookie / promotional banner if one is visible.

        Returns True if a banner was found and its close button was clicked,
        False if the page had no recognisable banner.

        Why this lives in BasePage: both the STL generator page and the DXF
        generator page can show the same site-wide banners, so the helper is
        shared rather than duplicated in each page object.
        """
        # XPath looks for a close/accept button that is a *descendant* of a
        # recognisable banner container.  The ancestor check prevents us from
        # accidentally clicking unrelated close buttons elsewhere on the page.
        BANNER_CLOSE = (
            By.XPATH,
            "//*["
            "  @aria-label='Close' or @aria-label='Dismiss' or @aria-label='Accept'"
            "  or contains(@class,'close') or contains(@class,'dismiss')"
            "][ancestor::*["
            "  contains(@class,'banner') or contains(@class,'cookie')"
            "  or contains(@class,'notice') or contains(@id,'banner')"
            "  or contains(@id,'cookie')"
            "]]",
        )
        try:
            self.click(BANNER_CLOSE, timeout=3)
            return True
        except TimeoutException:
            return False

    def go_to(self, path: str) -> None:
        url = self.base_url if path in ("", "/") else f"{self.base_url}/{path.lstrip('/')}"
        self.driver.get(url)

    # ----- assertions / queries -----
    def current_url(self) -> str:
        return self.driver.current_url

    def title(self) -> str:
        return self.driver.title

    def has_console_errors(self) -> list[str]:
        """Chrome-only: return any 'SEVERE' browser-log entries."""
        try:
            logs = self.driver.get_log("browser")
        except Exception:
            return []
        return [entry["message"] for entry in logs if entry.get("level") == "SEVERE"]

    # ----- download helper -----
    def wait_for_download(
        self,
        downloads_dir: Path,
        extensions: Iterable[str] = (".stl",),
        timeout: int = DOWNLOAD_TIMEOUT,
    ) -> Path:
        """Poll the downloads dir until a finished file with one of the extensions appears.

        Browsers write a *.crdownload / *.part / *.download placeholder during the
        transfer, so we explicitly wait for it to disappear.
        """
        end = time.time() + timeout
        wanted = tuple(ext.lower() for ext in extensions)
        partial_suffixes = (".crdownload", ".part", ".download", ".tmp")

        while time.time() < end:
            files = list(downloads_dir.iterdir())
            partials = [f for f in files if f.name.endswith(partial_suffixes)]
            completed = [f for f in files if f.suffix.lower() in wanted]
            if completed and not partials:
                # Pick the most recent
                return max(completed, key=lambda f: f.stat().st_mtime)
            time.sleep(0.3)

        raise TimeoutException(
            f"No file matching {wanted} appeared in {downloads_dir} within {timeout}s"
        )
