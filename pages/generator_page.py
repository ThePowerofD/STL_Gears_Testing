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

from selenium.common.exceptions import TimeoutException
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
    DOWNLOAD_BUTTON = (By.XPATH, "//*[contains(normalize-space(), 'Download Gear') "
                                 "or contains(normalize-space(), 'Download Rack')]")

    # Parameter inputs — text-label-based until test IDs are available
    @staticmethod
    def _input_near_label(label: str):
        # Finds the first <input> whose label or preceding text matches `label`
        return (
            By.XPATH,
            f"(//*[contains(normalize-space(), '{label}')]"
            f"/following::input[not(@type='hidden')])[1]",
        )

    @staticmethod
    def _hole_type_option(value: str):
        return (
            By.XPATH,
            f"//label[contains(normalize-space(), '{value}')]"
            f" | //input[@value='{value}']"
            f" | //*[normalize-space()='{value}' and (self::button or self::span)]",
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

    def set_parameter(self, label: str, value) -> None:
        """Type `value` into the field labeled `label`. Number-input safe."""
        loc = self._input_near_label(label)
        self.set_number_input(loc, value)

    def set_parameter_raw(self, label: str, value: str) -> None:
        """Force an arbitrary string into a labeled field via JavaScript.

        Use this instead of set_parameter when you deliberately want to bypass
        browser-side number-input filtering — for example, when testing how the
        application handles XSS payloads or scientific notation ('1e2') that the
        browser might silently discard before the value even reaches the DOM.
        """
        self.set_raw_text(self._input_near_label(label), value)

    def get_parameter_value(self, label: str) -> str:
        """Return the current string value of the field labeled `label`.

        Handy for asserting that the browser filtered out illegal characters
        (e.g. typing 'abc' into a number field should leave the field empty).
        """
        return self.get_input_value(self._input_near_label(label))

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
            if f in DEFAULT_PARAMETERS:
                try:
                    self.set_parameter(f, DEFAULT_PARAMETERS[f])
                    applied[f] = DEFAULT_PARAMETERS[f]
                except TimeoutException:
                    # Field may not be present for this gear; skip silently
                    pass
        return applied

    def select_hole_type(self, hole_type: str) -> None:
        if hole_type not in HOLE_TYPES:
            raise ValueError(f"Unknown hole type: {hole_type!r}")
        self.click(self._hole_type_option(hole_type))

    def click_download(self) -> None:
        self.click(self.DOWNLOAD_BUTTON)

    def download_gear(self, downloads_dir: Path) -> Path:
        """Click Download Gear and wait until an .stl file lands in downloads_dir."""
        self.click_download()
        return self.wait_for_download(downloads_dir, extensions=(".stl",))

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
