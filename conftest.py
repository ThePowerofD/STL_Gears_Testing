"""
Shared pytest fixtures for the STLGears.com Selenium suite.

Fixtures provided
-----------------
driver          : a Selenium WebDriver for the chosen browser (function-scoped).
base_url        : the URL under test (defaults to production, override via --base-url or BASE_URL env).
downloads_dir   : per-test temporary download directory; auto-cleaned.
home_page       : a HomePage instance pre-navigated to the home URL.
generator_page  : a GeneratorPage instance pre-navigated to /generators/3dprint.

CLI options
-----------
--browser={chrome,firefox,edge}   browser to drive (default: chrome)
--headed                          show the browser window (default: headless)
--base-url=<url>                  base URL to test against (default: production)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from pages.dxf_generator_page import DxfGeneratorPage
from pages.generator_page import GeneratorPage
from pages.home_page import HomePage

DEFAULT_BASE_URL = "https://www.stlgears.com"
REPORTS_DIR = Path(__file__).parent / "reports"
DOWNLOADS_ROOT = REPORTS_DIR / "downloads"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"


# ----- CLI options -----
def pytest_addoption(parser):
    parser.addoption(
        "--browser",
        action="store",
        default="chrome",
        choices=["chrome", "firefox", "edge"],
        help="Browser to use for tests",
    )
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run with a visible browser window (default: headless)",
    )
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="Base URL under test (overrides BASE_URL env var)",
    )


# ----- Session setup -----
@pytest.fixture(scope="session", autouse=True)
def _prepare_reports():
    REPORTS_DIR.mkdir(exist_ok=True)
    DOWNLOADS_ROOT.mkdir(exist_ok=True)
    SCREENSHOTS_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """Resolved in this order: --base-url flag > BASE_URL env > production."""
    return (
        request.config.getoption("--base-url")
        or os.environ.get("BASE_URL")
        or DEFAULT_BASE_URL
    )


# ----- Downloads directory (per test) -----
@pytest.fixture
def downloads_dir(request) -> Path:
    """Fresh download folder per test; cleaned afterward."""
    name = request.node.name.replace("[", "_").replace("]", "").replace("/", "_")
    path = DOWNLOADS_ROOT / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    # Keep on failure for triage; remove on success
    if not request.node.rep_call.failed:  # type: ignore[attr-defined]
        shutil.rmtree(path, ignore_errors=True)


# ----- Driver factory -----
def _build_chrome(headed: bool, download_dir: Path) -> webdriver.Chrome:
    opts = ChromeOptions()
    if not headed:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def _build_firefox(headed: bool, download_dir: Path) -> webdriver.Firefox:
    opts = FirefoxOptions()
    if not headed:
        opts.add_argument("-headless")
    opts.add_argument("--width=1366")
    opts.add_argument("--height=900")
    opts.set_preference("browser.download.folderList", 2)
    opts.set_preference("browser.download.dir", str(download_dir))
    opts.set_preference("browser.download.useDownloadDir", True)
    opts.set_preference(
        "browser.helperApps.neverAsk.saveToDisk",
        "application/sla,application/octet-stream,model/stl",
    )
    opts.set_preference("pdfjs.disabled", True)
    service = FirefoxService(GeckoDriverManager().install())
    return webdriver.Firefox(service=service, options=opts)


def _build_edge(headed: bool, download_dir: Path) -> webdriver.Edge:
    opts = EdgeOptions()
    if not headed:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1366,900")
    opts.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
        },
    )
    service = EdgeService(EdgeChromiumDriverManager().install())
    return webdriver.Edge(service=service, options=opts)


@pytest.fixture
def driver(request, downloads_dir):
    """Per-test WebDriver. Browser chosen via --browser. Headless by default."""
    browser = request.config.getoption("--browser")
    headed = request.config.getoption("--headed")

    if browser == "chrome":
        drv = _build_chrome(headed, downloads_dir)
    elif browser == "firefox":
        drv = _build_firefox(headed, downloads_dir)
    elif browser == "edge":
        drv = _build_edge(headed, downloads_dir)
    else:
        raise ValueError(f"Unsupported browser: {browser}")

    drv.set_page_load_timeout(30)
    drv.implicitly_wait(0)  # we prefer explicit waits
    yield drv
    drv.quit()


# ----- Page object fixtures -----
@pytest.fixture
def home_page(driver, base_url) -> HomePage:
    page = HomePage(driver, base_url)
    page.open()
    return page


@pytest.fixture
def generator_page(driver, base_url) -> GeneratorPage:
    page = GeneratorPage(driver, base_url)
    page.open()
    return page


@pytest.fixture
def dxf_generator_page(driver, base_url) -> DxfGeneratorPage:
    """DxfGeneratorPage pre-navigated to /generators/lasercut.

    Mirrors the generator_page fixture exactly.  The driver is the same
    function-scoped instance so it shares the same browser session (and
    therefore the same localStorage, cookies, and download directory).
    """
    page = DxfGeneratorPage(driver, base_url)
    page.open()
    return page


# ----- Screenshot on failure hook -----
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)

    if rep.when == "call" and rep.failed:
        drv = item.funcargs.get("driver")
        if drv is not None:
            name = item.name.replace("[", "_").replace("]", "").replace("/", "_")
            path = SCREENSHOTS_DIR / f"{name}.png"
            try:
                drv.save_screenshot(str(path))
                print(f"\nScreenshot saved: {path}")
            except Exception as e:
                print(f"\nFailed to save screenshot: {e}")
