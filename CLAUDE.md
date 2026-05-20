# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

End-to-end Selenium test suite for **STLGears.com**, a site with two gear generators:

- **STL generator** — `/generators/3dprint`, 8 gear types, downloads `.stl`
- **DXF generator** — `/generators/lasercut`, 3 gear types, downloads `.dxf`

The site is being refactored. Two refactor-driven additions need ongoing coverage: a **Dark/Light theme toggle** and **stricter input validation**.

## Running the suite

```bash
# from Test_Suite/
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

pytest                          # full suite, Chrome, headless
pytest --headed                 # visible browser (dev mode)
pytest --browser firefox        # also: chrome, edge
pytest -m smoke                 # CI subset
pytest --collect-only -q        # discovery only — never executes
pytest --base-url https://staging.stlgears.com   # point at another env
```

## Architecture

Page Object Model. Layers:

- `pages/base_page.py` — primitives every page object uses (`click`, `set_number_input`, `wait_for_download`, `set_raw_text`, `dismiss_banner_if_present`). Add cross-cutting helpers here.
- `pages/generator_page.py` — STL generator domain actions (`open_gear_form`, `fill_default_parameters`).
- `pages/dxf_generator_page.py` — same shape, DXF generator.
- `conftest.py` — fixtures (`driver`, `downloads_dir`, `generator_page`, `dxf_generator_page`, `home_page`).
- `tests/` — one file per concern; `pytestmark` at file level sets the topic marker.

## Conventions — do not break these

- **Use explicit waits, never implicit.** `driver.implicitly_wait(0)` is set in `conftest.py` on purpose. Use `WebDriverWait` / the `find_*` helpers in `BasePage`.
- **All markers must be declared in `pytest.ini`.** `--strict-markers` is on; an undeclared marker fails collection. When adding a new test category, add the marker first.
- **Locator logic stays in page objects, not test files.** If a test needs a new field, add a method to the page object — don't inline an XPath.
- **Negative tests use the `TimeoutException`-as-expected pattern.** See `test_spur_gear.py::test_spur_module_invalid_values_rejected` for the canonical shape: `click_download()` + `wait_for_download(timeout=8)` inside `try`, `pytest.fail()` if a file arrives, `pass` in `except TimeoutException`.
- **For non-numeric input on number fields, use `set_parameter_raw` / `set_raw_text` (JS injection), not `send_keys`.** An `<input type="number">` silently drops `<`, letters, whitespace, etc. typed via `send_keys`, so the payload never reaches the application. JS assignment bypasses that filter — required for XSS, whitespace, and scientific-notation tests.
- **Per-test downloads dir is automatic.** The `downloads_dir` fixture creates and cleans `reports/downloads/<test_name>/`. Don't write to other locations.
- **One marker per file is the topic; `@pytest.mark.smoke` is additive.** Set the topic with `pytestmark = pytest.mark.<topic>` at module level; mark individual tests with `@pytest.mark.smoke` when they belong in the minimum-passing set.

## Test patterns to mirror

- **Style template:** `tests/test_spur_gear.py`. Module docstring maps to test-case IDs, `pytestmark` at top, parametrize with descriptive `ids=`, one assertion per concern.
- **Cross-cutting smoke:** `tests/test_generator_smoke.py`. Parametrize over an enum-like constant (`GEAR_TYPES`) from the page object.
- **Banner-dismiss fixture pattern:** loop calling `dismiss_banner_if_present()` up to 2× because the site can stack banners.

## Known quirks

- `driver.get_log("browser")` is **Chrome-only**. Firefox's GeckoDriver raises `WebDriverException`. Tests that need console logs should `pytest.skip(...)` on that exception, not fail.
- Default download timeout is 30 s (`base_page.DOWNLOAD_TIMEOUT`); negative tests use 8 s explicitly because we *want* a fast failure when nothing should arrive.
- The empty `selenium-tests/` and `selenium-tests-stlgears/` directories at the project root are leftover scaffold and can be deleted; nothing imports from them.
- `dismiss_banner_if_present()` lives on `BasePage` so both generators inherit it.

## Adding a new test

1. If the test target is a new field, add the parameter to the relevant page object first.
2. If it's a new test category, add the marker to `pytest.ini`.
3. Write the test in `tests/`. Match the style of `test_spur_gear.py`.
4. Run `pytest --collect-only -q` to confirm discovery before attempting execution.
5. Map the test to its ID in `Test_Cases_STLGears.xlsx` (in the parent folder) in the docstring.

## What's intentionally not here

- No CI workflow yet (`.github/workflows/`).
- No `stl_validator` equivalent for DXF files — DXF tests assert non-zero file size only.
- No accessibility scans (planned: pytest-axe).
- No visual regression (planned: Percy or Playwright screenshot diff).
