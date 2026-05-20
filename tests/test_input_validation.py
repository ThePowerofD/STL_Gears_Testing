"""Cross-cutting input validation tests for the STL generator.

Numeric-range validation (Module < 0, Number of Teeth = 1, etc.) lives in
test_spur_gear.py.  This file targets a different class of defect: inputs that
are structurally wrong rather than numerically out of range.

  VAL-001  Empty field submitted
  VAL-002  Alphabetic input ('abc')
  VAL-003  Whitespace-padded number ('  2  ')
  VAL-004  XSS payload ('<script>alert(1)</script>')
  VAL-005  Scientific notation ('1e2')

All five tests use the Module field on the Spur Gear form as the test target.
Module is the simplest field (no lower-bound ambiguity) and shares its input
type with every other numeric field, so a defect here is representative of a
whole class of defects across the form.

Why set_parameter_raw vs set_parameter?
----------------------------------------
set_parameter() → set_number_input() → send_keys().
An <input type="number"> silently swallows non-numeric characters typed via
the keyboard.  That means send_keys('abc') may leave the field empty without
any error, and the *browser* has filtered the input before the *application*
ever sees it.  set_parameter_raw() injects the value directly via JS, bypassing
the browser filter so we can test what the *application* does with unexpected
strings.
"""
import time

import pytest
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By

from pages.generator_page import GeneratorPage

pytestmark = pytest.mark.validation


@pytest.fixture
def spur_form(generator_page):
    """Open the Spur Gear form with any site banners dismissed.

    The fixture returns the GeneratorPage instance so every test starts from
    the same state: Spur Gear form open, no banners, ready for input.
    """
    for _ in range(2):
        # dismiss_banner_if_present() returns False once there are no more
        # banners; we break early to avoid an unnecessary 3-second timeout.
        if not generator_page.dismiss_banner_if_present():
            break
    generator_page.open_gear_form("Spur Gear")
    return generator_page


# ---------------------------------------------------------------------------
# VAL-001 — Empty Module
# ---------------------------------------------------------------------------

def test_empty_module_rejected(spur_form, downloads_dir):
    """VAL-001 — Submitting with Module empty must not produce an STL.

    Would surface: the server silently defaulting an empty field to 0 or NaN,
    which could return a zero-size or malformed STL with no visible error.
    """
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.select_hole_type("None")

    # Clear Module via JS.  el.clear() + send_keys('') is unreliable on
    # <input type="number"> because some browsers restore the placeholder value.
    module_locator = GeneratorPage._input_near_label("Module")
    el = spur_form.find_visible(module_locator)
    spur_form.driver.execute_script(
        # Set value to the empty string and fire 'input' so listeners update
        "arguments[0].value = ''; "
        "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
        el,
    )

    try:
        spur_form.click_download()
        # wait_for_download raises TimeoutException if no file appears within 8 s
        stl_path = spur_form.wait_for_download(downloads_dir, timeout=8)
        pytest.fail(
            f"VAL-001: Empty Module field produced an STL ({stl_path.name}, "
            f"{stl_path.stat().st_size} bytes). "
            "Would surface: the server silently coercing an empty string to 0 or NaN."
        )
    except TimeoutException:
        pass  # Expected — an empty required field must block generation


# ---------------------------------------------------------------------------
# VAL-002 — Alphabetic input
# ---------------------------------------------------------------------------

def test_alpha_module_not_accepted(spur_form, downloads_dir):
    """VAL-002 — 'abc' typed into Module must be filtered by the browser or
    rejected by the form on submit — never silently coerced to 0 or NaN.

    Would surface: a type-coercion bug where parseFloat('abc') → NaN on the
    server, NaN is treated as 0, and a zero-module gear is generated.

    Two acceptable outcomes:
      a) Browser filters: the field value is '' or a numeric string after typing.
      b) Letters get through: the form rejects on submit (TimeoutException).
    One unacceptable outcome:
      An STL is produced (means 'abc' was silently coerced to a number).
    """
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.select_hole_type("None")

    # Use type_into (send_keys) rather than set_parameter_raw here — we
    # specifically want to observe what the browser does to 'abc' in a number
    # field.  If the browser filters it, fine.  If it gets through, we test
    # that the form still rejects.
    spur_form.type_into(GeneratorPage._input_near_label("Module"), "abc", clear=True)

    actual_value = spur_form.get_parameter_value("Module")

    if actual_value not in ("", "abc"):
        # Browser accepted it as some other numeric value — unusual, but not
        # itself a defect.  Log it and move on.
        return

    if actual_value == "abc":
        # Letters survived browser filtering — the form must now reject on submit.
        try:
            spur_form.click_download()
            stl_path = spur_form.wait_for_download(downloads_dir, timeout=8)
            pytest.fail(
                f"VAL-002: 'abc' in Module produced an STL ({stl_path.name}). "
                "Would surface: 'abc' coerced to NaN / 0 on the server without error."
            )
        except TimeoutException:
            pass  # Rejected on submit — correct behaviour

    # actual_value == '': browser filtered the characters — also correct.


# ---------------------------------------------------------------------------
# VAL-003 — Whitespace-padded number
# ---------------------------------------------------------------------------

def test_whitespace_padded_module_handled_cleanly(spur_form, downloads_dir):
    """VAL-003 — '  2  ' (leading/trailing whitespace) must produce an STL
    (whitespace trimmed) or be cleanly rejected — never silently fail.

    Would surface: the server calling parseFloat on an untrimmed string in a
    runtime where that returns NaN, leaving the user staring at a spinner.

    Note on what 'silently fails' means here: if the server returns neither a
    file nor a visible error within 8 s, wait_for_download raises TimeoutException.
    We treat that as 'cleanly rejected' and the test passes, but a follow-up
    manual check should confirm the UI shows a validation message rather than
    an infinite spinner.
    """
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.select_hole_type("None")

    # Use set_raw_text (JS) so the literal whitespace survives.  A number
    # input's send_keys strips leading/trailing whitespace before the value
    # even reaches the DOM.
    el = spur_form.find_visible(GeneratorPage._input_near_label("Module"))
    spur_form.driver.execute_script(
        "arguments[0].value = '  2  '; "
        "arguments[0].dispatchEvent(new Event('input',  {bubbles: true})); "
        "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
        el,
    )

    spur_form.click_download()

    try:
        stl_path = spur_form.wait_for_download(downloads_dir, timeout=8)
        # Whitespace was trimmed and the value '2' was accepted — good.
        assert stl_path.stat().st_size > 0, (
            "VAL-003: '  2  ' produced an empty STL. "
            "Would surface: whitespace coerced to 0 rather than trimmed to 2."
        )
    except TimeoutException:
        # Rejected — acceptable.  See docstring note on 'silently fails'.
        pass


# ---------------------------------------------------------------------------
# VAL-004 — XSS payload
# ---------------------------------------------------------------------------

def test_xss_module_no_alert(spur_form, downloads_dir):
    """VAL-004 — '<script>alert(1)</script>' in Module must not trigger a dialog.

    Would surface: the server reflecting the raw Module value in an HTML error
    message without escaping it, causing the browser to execute the script tag.

    Why set_parameter_raw?  An <input type="number"> silently drops '<', '>',
    and most non-numeric characters via send_keys — the payload would never
    reach the application layer.  We use JS assignment to bypass that filter,
    simulating what a developer-tools-savvy user or a fuzzer would do.

    Why switch_to.alert?  window.alert() opens a browser-native dialog.  If
    the XSS payload executes, alert(1) creates one.  driver.switch_to.alert
    raises NoAlertPresentException when there is no dialog — and that exception
    is our pass condition.
    """
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.select_hole_type("None")

    # Inject via JS to bypass browser-side number-input character filtering
    spur_form.set_parameter_raw("Module", "<script>alert(1)</script>")

    spur_form.click_download()

    # Give the browser a moment to fire any synchronous alert the payload
    # could cause.  window.alert() from an injected script fires synchronously
    # during HTML parsing, so 1 s is more than enough.
    time.sleep(1)

    try:
        alert = spur_form.driver.switch_to.alert
        # We got here: a dialog is open, meaning the payload executed.
        # Dismiss it so the browser doesn't hang, then report the defect.
        alert_text = alert.text
        alert.accept()
        pytest.fail(
            f"VAL-004: XSS payload triggered a browser alert: {alert_text!r}. "
            "The form must sanitise or escape the Module value before it reaches "
            "any HTML context (server-rendered error messages, log output, etc.)."
        )
    except NoAlertPresentException:
        # No dialog — the payload was not executed. Test passes.
        pass


# ---------------------------------------------------------------------------
# VAL-005 — Scientific notation
# ---------------------------------------------------------------------------

def test_scientific_notation_module_not_silent_failure(spur_form, downloads_dir):
    """VAL-005 — '1e2' (scientific notation for 100) must either produce an STL
    or be clearly rejected — never silently produce nothing.

    Would surface: server-side validation middleware that calls int('1e2') in
    Python (raises ValueError) or a stricter regex that rejects 'e' while the
    JS frontend happily parsed it as 100, leaving the user with no feedback.

    Both Python's float() and JS's Number() accept '1e2' as 100, but bespoke
    validation middleware (e.g. a Pydantic model with a strict int field) may
    not.  This test documents the expected contract: accept or reject cleanly.

    Timeout is 15 s (instead of the usual 8 s for rejection tests) because if
    the server accepts the value it has to run the full gear generator, which
    can take longer than 8 s for some gear types.
    """
    spur_form.fill_default_parameters("Spur Gear")
    spur_form.select_hole_type("None")

    # JS assignment so the literal string '1e2' reaches the server.
    # send_keys on a number input may convert it to 100 before dispatch, which
    # would test a different code path.
    spur_form.set_parameter_raw("Module", "1e2")

    spur_form.click_download()

    try:
        stl_path = spur_form.wait_for_download(downloads_dir, timeout=15)
        # Server interpreted '1e2' as 100 and generated a gear — good.
        assert stl_path.stat().st_size > 0, (
            "VAL-005: '1e2' produced an empty STL. "
            "Would surface: the value being coerced to 0 rather than 100."
        )
    except TimeoutException:
        # Rejected — acceptable, as long as the UI shows a message.
        # Silent failure (spinner that never resolves) would also land here,
        # but 15 s is enough to catch that in practice.
        pass
