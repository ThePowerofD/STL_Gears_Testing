"""Page Object for the 3D Print Generator (/generators/3dprint).

The page exposes 8 gear-type cards. Each card has a 'Start Design' control that
opens a form below. The forms share many parameters (Module, Pressure Angle,
Number of Teeth, Gear Length, Profile Shift) plus type-specific fields.

NOTE ON LOCATORS
----------------
This module purposely uses descriptive, text-based XPath locators so it stays
readable even before we know the exact HTML structure of the refactored build.
When the dev provides stable test IDs (data-testid="…"), replace each tuple
in `_GEAR_FORMS` with the test-id selector — that single edit will update every
test that touches that field.
"""
from __future__ import annotations

from pathlib import Path

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)
from selenium.webdriver.common.by import By

from .base_page import BasePage


# Default values used in smoke tests, mirroring what the legacy site appears
# to ship with. Tweak per gear once defaults are confirmed.
DEFAULT_PARAMETERS = {
    "Module": 2,
    "Pressure Angle": 20,
    "Number of Teeth": 20,
    "Gear Length": 10,
    "Profile Shift": 0,
    "Helix Angle": 20,
    "Outer Diameter": 80,
    "Rack Height": 10,
    "Rack Width": 10,
    "Rack Length": 100,
    "Wheel Number of Teeth": 30,
    "Pinion Number of Teeth": 10,
}


HOLE_TYPES = ["None", "Hollow", "Squared", "Hexagonal", "Circular", "Keyway"]
GEAR_TYPES = [
    "Double Helical Gear",
    "Spur Gear",
    "Helical Gear",
    "Internal Double Helical Gear",
    "Internal Spur Gear",
    "Internal Helical Gear",
    "Rack",
    "90° Bevel Gears",
]

# Maps human-readable parameter labels to the real HTML name= attribute used
# by the live STL generator. Discovered by inspecting the rendered DOM — the
# page does not use accessible <label for="…"> markup, so text-proximity XPath
# is unreliable. Update this map (not test code) if the dev renames a field.
_STL_FIELD_NAMES: dict[str, str] = {
    "Module":                 "modulo",
    "Pressure Angle":         "ap",
    "Number of Teeth":        "z",
    "Gear Length":            "height",
    "Profile Shift":          "x",
    "Helix Angle":            "ah",
    "Outer Diameter":         "outDiam",
    "Rack Height":            "height",
    "Rack Width":             "width",
    "Rack Length":            "RackL",
    "Wheel Number of Teeth":  "z",
    "Pinion Number of Teeth": "z2",
}


class GeneratorPage(BasePage):
    URL_PATH = "/generators/3dprint"

    # ----- Page-level locators -----
    PAGE_HEADING = (By.XPATH, "//*[contains(translate(., 'D', 'd'), 'design your own')]")
    GEAR_CARD = staticmethod(
        lambda name: (
            By.XPATH,
            f"//*[self::h2 or self::h3 or self::div or self::a]"
            f"[contains(normalize-space(), '{name}')]"
            f"/ancestor-or-self::*[.//*[contains(normalize-space(),'Start')]][1]",
        )
    )
    START_BUTTON_FOR = staticmethod(
        lambda name: (
            By.XPATH,
            f"//*[contains(normalize-space(),'{name}')]/following::*[contains(normalize-space(),'Start')][1]",
        )
    )
    # Download button: the page renders BOTH a <button> and an <a> with the
    # same "Download Gear" / "Download Rack" text — we restrict to interactive
    # tags and resolve the visible one via click_visible().
    DOWNLOAD_BUTTON = (
        By.XPATH,
        "//*[self::button or self::a or self::input[@type='button' or @type='submit']]"
        "[contains(normalize-space(), 'Download Gear')"
        " or contains(normalize-space(), 'Download Rack')]",
    )

    @staticmethod
    def _hole_type_radio(hole_type: str):
        """Locator for the clickable hole-type control.

        The hole-type UI uses styled <label class="groupbutton"> elements as
        buttons — the underlying radio input is display:none and never
        clickable directly. Bevel exposes two such groups (wheel + pinion),
        each with its own copy of every label; select_hole_type() clicks
        every visible match so both groups get set in one call.
        """
        return (
            By.XPATH,
            f"//label[contains(@class, 'groupbutton')]"
            f"[normalize-space()='{hole_type}']",
        )

    # ----- Actions -----
    def open(self) -> "GeneratorPage":
        self.go_to(self.URL_PATH)
        # Any gear card should be present after load
        self.find_visible((By.XPATH, "//*[contains(text(), 'Spur Gear')]"), timeout=20)
        return self

    def open_gear_form(self, gear_name: str) -> None:
        """Click 'Start Design' for the named gear type."""
        if gear_name not in GEAR_TYPES:
            raise ValueError(f"Unknown gear: {gear_name!r}. Known: {GEAR_TYPES}")
        self.click(self.START_BUTTON_FOR(gear_name))

    @staticmethod
    def _name_for(label: str) -> str:
        try:
            return _STL_FIELD_NAMES[label]
        except KeyError as exc:
            raise KeyError(
                f"No name= mapping for parameter {label!r}. "
                f"Add it to _STL_FIELD_NAMES in pages/generator_page.py."
            ) from exc

    def _input_locator(self, label: str):
        """Locator for the (possibly duplicated) <input name='…'> for `label`."""
        return (By.XPATH, f"//input[@name='{self._name_for(label)}']")

    def set_parameter(self, label: str, value) -> None:
        """Type `value` into the field labeled `label`. Number-input safe."""
        self.set_input_by_name(self._name_for(label), value)

    def set_parameter_raw(self, label: str, value: str) -> None:
        """Force an arbitrary string into a labeled field via JavaScript.

        Use this instead of set_parameter when you deliberately want to bypass
        browser-side number-input filtering — for example, when testing how the
        application handles XSS payloads or scientific notation ('1e2') that the
        browser might silently discard before the value even reaches the DOM.
        """
        # Resolve to the visible input (same gear-section scoping logic as
        # set_input_by_name) before set_raw_text rewrites its value via JS.
        el = self.find_first_visible(self._input_locator(label))
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input',  {bubbles: true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            el,
            str(value),
        )

    def get_parameter_value(self, label: str) -> str:
        """Return the current string value of the field labeled `label`."""
        el = self.find_first_visible(self._input_locator(label))
        return el.get_attribute("value") or ""

    def fill_default_parameters(self, gear_name: str) -> dict:
        """Set a sensible default for every visible field for this gear.
        Returns the dict of parameters actually applied (handy for assertions).
        """
        applied: dict = {}
        common = ["Module", "Pressure Angle", "Number of Teeth",
                  "Gear Length", "Profile Shift"]
        helical_extra = ["Helix Angle"]
        internal_extra = ["Outer Diameter"]
        rack_fields = ["Module", "Pressure Angle", "Rack Height",
                       "Rack Width", "Number of Teeth"]
        bevel_fields = ["Module", "Pressure Angle",
                        "Wheel Number of Teeth", "Pinion Number of Teeth"]

        if gear_name == "Rack":
            fields = rack_fields
        elif gear_name == "90° Bevel Gears":
            fields = bevel_fields
        elif gear_name.startswith("Internal"):
            fields = [f for f in common if f != "Profile Shift"] + internal_extra
            if "Helical" in gear_name:
                fields += helical_extra
        else:
            fields = list(common)
            if "Helical" in gear_name:
                fields += helical_extra

        for f in fields:
            if f not in DEFAULT_PARAMETERS:
                continue
            # Deliberately no try/except: if a field this gear claims to need
            # is not visible, that is a real failure (form didn't open, the
            # site renamed it, etc.). Silently swallowing it previously caused
            # the form to submit empty and the Download to time out — a much
            # worse failure mode than a clear error here.
            self.set_parameter(f, DEFAULT_PARAMETERS[f])
            applied[f] = DEFAULT_PARAMETERS[f]
        return applied

    def select_hole_type(self, hole_type: str) -> None:
        """Select the named hole type on whichever hole-type group(s) are
        visible on the current form.

        Why click EVERY visible match: the Bevel form exposes both
        wheel_hole_type and pinion_hole_type radio groups; if we only set one,
        the form is incomplete and the download silently never happens.
        Single-group gears (Spur, Helical, Bevel sub-cases) just see one
        match and behave as before.
        """
        if hole_type not in HOLE_TYPES:
            raise ValueError(f"Unknown hole type: {hole_type!r}")
        locator = self._hole_type_radio(hole_type)
        matches = [el for el in self.driver.find_elements(*locator)
                   if el.is_displayed()]
        if not matches:
            raise TimeoutException(
                f"No visible hole-type radio for {hole_type!r}"
            )
        for el in matches:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", el
            )
            try:
                el.click()
            except ElementClickInterceptedException:
                # Some radios are wrapped in styled labels that intercept;
                # JS click bypasses the overlay.
                self.driver.execute_script("arguments[0].click();", el)

    def click_download(self) -> None:
        # click_visible (not click): the page renders two copies of the
        # Download button, only one of which is actually interactive at a time.
        self.click_visible(self.DOWNLOAD_BUTTON)

    def download_gear(self, downloads_dir: Path) -> Path:
        """Click Download Gear and return the path to an .stl file.

        Most gear types deliver a plain .stl. The Bevel Gear page produces a
        PAIR (wheel + pinion) bundled as a .zip — confirmed against the live
        site, which names it e.g. `StraightBevelPair_M2_Pa20_Zw30_Zp10.zip`.
        For tests that just need any valid STL we extract the first .stl
        member of the archive and return its path. Tests that need to assert
        on the zip contents directly can call click_download() + wait_for_download
        themselves with extensions=('.zip',).
        """
        self.click_download()
        file_path = self.wait_for_download(
            downloads_dir, extensions=(".stl", ".zip")
        )
        if file_path.suffix.lower() != ".zip":
            return file_path

        import zipfile
        with zipfile.ZipFile(file_path) as zf:
            stl_members = [m for m in zf.namelist() if m.lower().endswith(".stl")]
            if not stl_members:
                raise RuntimeError(
                    f"Downloaded archive {file_path.name} contains no .stl"
                )
            zf.extract(stl_members[0], path=downloads_dir)
        return downloads_dir / stl_members[0]

    # ----- Convenience composite -----
    def smoke_download(self, gear_name: str, downloads_dir: Path,
                       hole_type: str = "None") -> Path:
        """Open the form, set defaults, pick hole type, click download, return file path."""
        self.open_gear_form(gear_name)
        self.fill_default_parameters(gear_name)
        if hole_type in HOLE_TYPES and gear_name not in (
            "Internal Spur Gear",
            "Internal Helical Gear",
            "Internal Double Helical Gear",
            "Rack",
        ):
            # Hole-type sub-form only applies to external gears & bevel
            try:
                self.select_hole_type(hole_type)
            except TimeoutException:
                pass
        return self.download_gear(downloads_dir)
