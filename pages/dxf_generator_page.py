"""Page Object for the Laser Cut DXF Generator (/generators/lasercut).

Why a separate page object instead of reusing GeneratorPage?
-------------------------------------------------------------
The DXF generator produces 2D cut files for laser cutters, not 3D prints.
Differences that matter for tests:

  * URL path: /generators/lasercut  (not /generators/3dprint)
  * Only 3 gear types, not 8
  * No Gear Length field — a laser-cut part has no depth
  * Internal Gear has a "Radial Thickness" field that does not exist on the
    STL generator
  * Downloads land as .dxf files, not .stl files

The locator strategy is intentionally identical to GeneratorPage: descriptive
XPath based on visible text.  When stable data-testids are added by the dev
team, each XPath can be replaced with a CSS [data-testid="…"] selector
without touching any test file.
"""
from __future__ import annotations

from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from .base_page import BasePage


# All valid gear names on this page.  Used both as parametrize values in tests
# and as the guard in open_gear_form() so a typo fails fast with a clear error.
DXF_GEAR_TYPES = ["Internal Gear", "Rack", "Spur Gear"]

# Default parameter values for each field, mirroring what the page ships with.
# Adjust once the refactored page is confirmed live.
DXF_DEFAULT_PARAMETERS: dict[str, int | float] = {
    "Module": 2,
    "Pressure Angle": 20,
    "Number of Teeth": 20,
    "Profile Shift": 0,
    # Radial Thickness: the ring wall surrounding the Internal Gear's teeth.
    # A laser-cut internal gear has no Gear Length, so thickness is the only
    # depth-analog parameter.
    "Radial Thickness": 10,
    # Rack dimensions (width and height describe the 2D cross-section)
    "Rack Height": 20,
    "Rack Width": 10,
}

# Maps each gear type to exactly the fields it exposes.
# Keeping this lookup here (not inside methods) makes it easy to update when
# the site adds or removes fields after the refactor.
_GEAR_FIELDS: dict[str, list[str]] = {
    "Spur Gear": ["Module", "Pressure Angle", "Number of Teeth", "Profile Shift"],
    "Internal Gear": ["Module", "Pressure Angle", "Number of Teeth", "Radial Thickness"],
    "Rack": ["Module", "Pressure Angle", "Number of Teeth", "Rack Height", "Rack Width"],
}


class DxfGeneratorPage(BasePage):
    """Page object for /generators/lasercut."""

    URL_PATH = "/generators/lasercut"

    # The Download button may read "Download DXF", "Download Gear", or
    # "Download Rack" depending on gear type.  We match on "Download" broadly
    # and restrict to interactive elements so we don't accidentally match a
    # heading that happens to contain the word.
    DOWNLOAD_BUTTON = (
        By.XPATH,
        "//*[contains(normalize-space(), 'Download')]"
        "[self::button or self::a or self::input[@type='button' or @type='submit']]",
    )

    # Same XPath strategy as GeneratorPage.START_BUTTON_FOR:
    # find the element whose text matches the gear name, then walk forward to
    # the nearest element whose text contains "Start".
    START_BUTTON_FOR = staticmethod(
        lambda name: (
            By.XPATH,
            f"//*[contains(normalize-space(),'{name}')]"
            f"/following::*[contains(normalize-space(),'Start')][1]",
        )
    )

    @staticmethod
    def _input_near_label(label: str):
        """XPath: the first non-hidden <input> after the element whose text
        contains `label`.  Same pattern as GeneratorPage — explained once here
        so it does not need repeating: the approach is text-proximity rather
        than an explicit <label for="…"> association because the page may not
        use accessible label markup consistently.
        """
        return (
            By.XPATH,
            f"(//*[contains(normalize-space(), '{label}')]"
            f"/following::input[not(@type='hidden')])[1]",
        )

    # ----- Navigation -----

    def open(self) -> "DxfGeneratorPage":
        """Navigate to the DXF generator and wait for at least one gear card."""
        self.go_to(self.URL_PATH)
        # We wait for any of the three expected gear-type labels.  If none
        # appears within 20 s, the page failed to load — fail fast.
        self.find_visible(
            (
                By.XPATH,
                "//*["
                "  contains(text(),'Spur Gear')"
                "  or contains(text(),'Internal Gear')"
                "  or contains(text(),'Rack')"
                "]",
            ),
            timeout=20,
        )
        return self

    # ----- Form interactions -----

    def open_gear_form(self, gear_name: str) -> None:
        """Click the 'Start Design' button for the named DXF gear type.

        Raises ValueError immediately (not TimeoutException) if the gear name
        is not in DXF_GEAR_TYPES, so a typo in a test is caught at the Python
        level rather than as a confusing Selenium timeout.
        """
        if gear_name not in DXF_GEAR_TYPES:
            raise ValueError(
                f"Unknown DXF gear type: {gear_name!r}. "
                f"Valid types: {DXF_GEAR_TYPES}"
            )
        self.click(self.START_BUTTON_FOR(gear_name))

    def set_parameter(self, label: str, value: int | float) -> None:
        """Type a numeric value into the field whose label text contains `label`."""
        self.set_number_input(self._input_near_label(label), value)

    def fill_default_parameters(self, gear_name: str) -> dict:
        """Fill every visible field for `gear_name` with its default value.

        Returns the dict of {field: value} pairs that were actually applied.
        Fields skipped because of TimeoutException are absent from the dict —
        useful for debugging when a field selector doesn't match the live page.
        """
        applied: dict = {}
        for field in _GEAR_FIELDS.get(gear_name, []):
            if field not in DXF_DEFAULT_PARAMETERS:
                continue
            try:
                self.set_parameter(field, DXF_DEFAULT_PARAMETERS[field])
                applied[field] = DXF_DEFAULT_PARAMETERS[field]
            except TimeoutException:
                # Field was not rendered for this gear — skip rather than crash.
                # This can happen legitimately if the refactor changed a field name;
                # the test will still run and may surface a download failure.
                pass
        return applied

    # ----- Download -----

    def click_download(self) -> None:
        """Click the Download button (does not wait for the file to arrive)."""
        self.click(self.DOWNLOAD_BUTTON)

    def download_gear(self, downloads_dir: Path) -> Path:
        """Click Download and block until a .dxf file appears in downloads_dir.

        Raises TimeoutException (from BasePage.wait_for_download) if no file
        arrives within DOWNLOAD_TIMEOUT seconds.  Callers that are *testing
        rejection* should call click_download() + wait_for_download() directly
        and catch TimeoutException themselves rather than calling this method.
        """
        self.click_download()
        # Explicitly pass the .dxf extension — wait_for_download defaults to
        # .stl, which would make the download test silently pass even if the
        # server accidentally served an STL instead of a DXF.
        return self.wait_for_download(downloads_dir, extensions=(".dxf",))
