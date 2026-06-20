"""Page Object for the Home page (/)."""
from selenium.webdriver.common.by import By

from .base_page import BasePage


class HomePage(BasePage):
    URL_PATH = "/"

    # Locators — keep them here so tests don't care about CSS structure
    LOGO = (By.CSS_SELECTOR, "a[href='/'] img")
    NAV_HOME = (By.XPATH, "//a[normalize-space()='Home']")
    NAV_GENERATORS = (By.XPATH, "//*[contains(normalize-space(), 'Generators')]")
    NAV_THEORY = (By.XPATH, "//a[normalize-space()='Theory']")
    NAV_CONTACT = (By.XPATH, "//a[normalize-space()='Contact']")
    NAV_DEVBLOG = (By.XPATH, "//a[contains(@href, 'ko-fi.com')]")

    LINK_3DPRINT = (By.XPATH, "//a[contains(@href, '/generators/3dprint')]")
    LINK_LASERCUT = (By.XPATH, "//a[contains(@href, '/generators/lasercut')]")

    SECTION_STL = (By.XPATH, "//*[contains(text(), 'STL Gear Generator')]")
    SECTION_DXF = (By.XPATH, "//*[contains(text(), 'DXF Gear Generator')]")
    SECTION_GF = (By.XPATH, "//*[contains(text(), 'GF Gear Generator')]")

    FOOTER_PRIVACY = (By.XPATH, "//a[contains(text(), 'Privacy Notice')]")
    FOOTER_COOKIES = (By.XPATH, "//a[contains(text(), 'Cookies')]")

    BANNER_CLOSE = (By.XPATH, "//*[normalize-space()='✕' or normalize-space()='×']")

    # ----- Actions -----
    def open(self) -> "HomePage":
        self.go_to(self.URL_PATH)
        self.find(self.SECTION_STL)
        return self

    def click_try_3dprint(self) -> None:
        # 'Try it out' under STL section — the href matches several anchors
        # on the page (navbar + hero CTA + section CTA + footer), some of which
        # may be off-screen or hidden behind a responsive menu. click_visible
        # picks whichever copy is currently displayed.
        self.click_visible(self.LINK_3DPRINT)

    def click_try_lasercut(self) -> None:
        self.click_visible(self.LINK_LASERCUT)

    def dismiss_banner_if_present(self) -> bool:
        if self.is_present(self.BANNER_CLOSE, timeout=2):
            self.click(self.BANNER_CLOSE)
            return True
        return False
