# STLGears.com — Selenium Automation Suite

End-to-end tests for the STLGears.com 3D Print gear generator, written in Python with Selenium WebDriver and pytest. Follows the Page Object Model (POM) so tests stay readable and locators live in one place.

This is the automation companion to the Test Plan and Test Case Matrix in the parent folder. The cases here cover the **smoke** layer (the must-pass scenarios for every release) plus a parametrized boundary suite for the Spur Gear form. Treat it as a foundation — grow it as you execute manual tests and find regressions worth automating.

## Why these tests?

The 3D Print page has 8 gear types × 6 hole types × 5+ numeric parameters. Manually re-testing every combination after each refactor commit is unrealistic. The suite focuses on:

1. **Smoke** — page loads, navigation works, each gear type downloads a valid STL with defaults.
2. **Spur Gear boundary testing** — most thorough numeric coverage on the simplest gear (good template for the others).
3. **Cross-browser switch** — run any test against Chrome, Firefox, or Edge via a CLI flag.
4. **Migration sanity** — separate test file pointed at staging URL once available.

## Project structure

```
selenium-tests/
├── README.md                   ← you are here
├── requirements.txt            ← Python dependencies
├── pytest.ini                  ← pytest configuration
├── conftest.py                 ← shared fixtures (driver, URLs, downloads dir)
├── pages/                      ← Page Object Model classes
│   ├── __init__.py
│   ├── base_page.py            ← shared helpers (wait, click, type)
│   ├── home_page.py            ← Home page locators & actions
│   └── generator_page.py       ← 3D Print generator page
├── tests/                      ← test files (one per concern)
│   ├── __init__.py
│   ├── test_navigation.py      ← header/nav/footer
│   ├── test_generator_smoke.py ← happy path per gear type
│   ├── test_spur_gear.py       ← parametrized boundary tests
│   └── test_migration.py       ← post-migration sanity checks
├── utils/
│   ├── __init__.py
│   └── stl_validator.py        ← lightweight STL file sanity check
└── reports/                    ← HTML reports & downloaded STLs (gitignored)
```

## Prerequisites

* **Python 3.10+**
* **Chrome, Firefox, or Edge** installed locally (whichever you plan to run against)
* The matching WebDriver is fetched automatically by `webdriver-manager` — you don't need to install it manually.

## Setup

```bash
cd selenium-tests
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
```

## Running tests

```bash
# Full suite, Chrome, headless (default)
pytest

# Visible browser (useful when developing tests)
pytest --headed

# Switch browser
pytest --browser firefox
pytest --browser edge

# Run only the smoke tests
pytest -m smoke

# Run only the Spur Gear file
pytest tests/test_spur_gear.py

# Generate an HTML report
pytest --html=reports/report.html --self-contained-html

# Point at staging instead of production
BASE_URL=https://staging.stlgears.com pytest
# or
pytest --base-url https://staging.stlgears.com
```

## Markers

Defined in `pytest.ini`:

* `smoke` — minimum set that must pass for every build.
* `spur`, `helical`, `dh`, `internal`, `rack`, `bevel` — per gear type.
* `migration` — host-migration sanity tests (run against staging).
* `slow` — anything that downloads large STLs or runs Lighthouse.

## Adding a new test

1. Add or update a locator in `pages/generator_page.py`.
2. Add a method to the page object that performs the action.
3. Write the test in `tests/`. Keep it small — one assertion per concern.

Example — testing a new gear type:

```python
def test_internal_helical_default_download(generator_page, downloads_dir):
    generator_page.open_gear_form("Internal Helical Gear")
    generator_page.fill_default_parameters("Internal Helical Gear")
    stl_path = generator_page.download_gear(downloads_dir)
    assert stl_path.exists()
    assert stl_path.stat().st_size > 0
```

## Notes on the download flow

The download fixture configures the browser to send STL files to `reports/downloads/<test_name>/`. The `wait_for_download` helper polls that folder until a new file appears or the timeout fires. This is more reliable than relying on the browser's native download bar across Chrome/Firefox/Edge.

## What's intentionally NOT here yet

* No CI workflow (add `.github/workflows/ci.yml` when ready to run on every push).
* No visual-regression tooling — pair with Percy or Playwright's screenshot diff once the UI stabilizes.
* No load tests — out of scope; pair with k6 or Locust if needed.
* No accessibility scans — see the axe-core integration in the to-do at the bottom of this file.

## To-do / suggested next steps

* Add `pytest-axe` or run `axe-core` against the page for automated WCAG checks.
* Capture Lighthouse JSON in CI and threshold the scores.
* Add a regression test for each defect filed during manual testing (don't fix-without-test).
* Build a small test data factory for boundary values (currently inline in the test).

## Resources

* Selenium WebDriver docs: https://www.selenium.dev/documentation/
* pytest docs: https://docs.pytest.org/
* Page Object Model background: https://martinfowler.com/bliki/PageObject.html
