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
    # Radial Thickness: the ring wall surrounding the Internal Gear's teeth.
    # A laser-cut internal gear has no Gear Length, so thickness is the only
    # depth-analog parameter.
    "Radial Thickness": 10,
    "Rack Height": 20,
}

# Maps each gear type to exactly the fields it exposes on the live DXF page.
# Confirmed against the rendered DOM (probe_form.py) — Profile Shift and
# Rack Width do NOT exist on /generators/lasercut, so they were removed.
_GEAR_FIELDS: dict[str, list[str]] = {
    "Spur Gear":     ["Module", "Pressure Angle", "Number of Teeth"],
    "Internal Gear": ["Module", "Pressure Angle", "Number of Teeth", "Radial Thickness"],
    "Rack":          ["Module", "Pressure Angle", "Number of Teeth", "Rack Height"],
}

# Friendly label -> real HTML name= attribute on the DXF generator. The page
# does not use accessible <label for="…"> markup, so we identify inputs by
# their `name` and pick the visible one (each gear renders its own section).
_DXF_FIELD_NAMES: dict[str, str] = {
    "Module":           "modulo",
    "Pressure Angle":   "ap",
    "Number of Teeth":  "z",
    "Radial Thickness": "rt",
    "Rack Height":      "H",
}


class DxfGeneratorPage(BasePage):
    """Page object for /generators/lasercut."""

    URL_PATH = "/generators/lasercut"

    # The Download button may read "Download DXF", "Download Gear", or
    # "Download Rack" depending on gear type.  We match on "Download" broadly
    # and restrict to interactive elements so we don't accidentally match a
    # heading that happens to contain the word.
    # The DXF page renders both a <button> and an <a> with "Download DXF"
    # text — only one is actually clickable at a time. click_visible() picks
    # the one currently displayed, sidestepping element_to_be_clickable's
    # tendency to fixate on a hidden first match.
    DOWNLOAD_BUTTON = (
        By.XPATH,
        "//*[self::button or self::a or self::input[@type='button' or @type='submit']]"
        "[contains(normalize-space(), 'Download')]",
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
    def _name_for(label: str) -> str:
        try:
            return _DXF_FIELD_NAMES[label]
        except KeyError as exc:
            raise KeyError(
                f"No name= mapping for parameter {label!r}. "
                f"Add it to _DXF_FIELD_NAMES in pages/dxf_generator_page.py."
            ) from exc

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
        """Set the field labeled `label` to `value`, scoped to the visible form."""
        self.set_input_by_name(self._name_for(label), value)

    def fill_default_parameters(self, gear_name: str) -> dict:
        """Fill every visible field for `gear_name` with its default value.

        Raises if a required field is missing from the page — silent skip was
        the original bug that caused empty-form submissions and timed-out
        downloads.
        """
        applied: dict = {}
        for field in _GEAR_FIELDS.get(gear_name, []):
            if field not in DXF_DEFAULT_PARAMETERS:
                continue
            self.set_parameter(field, DXF_DEFAULT_PARAMETERS[field])
            applied[field] = DXF_DEFAULT_PARAMETERS[field]
        return applied

    # ----- Download -----

    def click_download(self) -> None:
        """Click the Download button (does not wait for the file to arrive)."""
        # click_visible handles the <button>/<a> duplicate render — see locator note.
        self.click_visible(self.DOWNLOAD_BUTTON)

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
