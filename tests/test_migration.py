"""Migration sanity tests — HTTP-level checks for the host migration.

These don't drive a browser; they just hit the staging URL with `requests` and
assert the basics: HTTPS, status codes, security headers, asset availability.

Run only against the staging/migrated host:

    BASE_URL=https://staging.stlgears.com pytest -m migration

Maps to: MIG-001 .. MIG-010 in Test_Cases_STLGears.xlsx
"""
from urllib.parse import urlparse

import pytest
import requests

pytestmark = pytest.mark.migration

REQUEST_TIMEOUT = 10  # seconds


# ----- Helpers -----
def _http_url(https_url: str) -> str:
    """Convert https://host/path to http://host/path for redirect checks."""
    parsed = urlparse(https_url)
    return f"http://{parsed.netloc}{parsed.path or '/'}"


# ----- Tests -----
def test_https_redirect(base_url):
    """MIG-003 — HTTP requests are redirected to HTTPS."""
    if not base_url.startswith("https://"):
        pytest.skip("base_url is not HTTPS; redirect test only applies to HTTPS sites")

    http_url = _http_url(base_url)
    resp = requests.get(http_url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
    assert resp.status_code in (301, 302, 307, 308), (
        f"Expected redirect from HTTP, got {resp.status_code}"
    )
    location = resp.headers.get("Location", "")
    assert location.startswith("https://"), (
        f"Redirect target is not HTTPS: {location!r}"
    )


def test_canonical_urls_return_200(base_url):
    """MIG-006 — All canonical URLs return 200 OK."""
    paths = [
        "/",
        "/generators/3dprint",
        "/generators/lasercut",
        "/theory",
        "/contact",
    ]
    for path in paths:
        url = base_url.rstrip("/") + path
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        assert resp.status_code == 200, (
            f"{url} returned {resp.status_code}, expected 200"
        )


def test_security_headers_present(base_url):
    """MIG-009 — Critical security headers are set."""
    resp = requests.get(base_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)

    # Inspected headers — case-insensitive lookup
    headers = {k.lower(): v for k, v in resp.headers.items()}

    soft_warnings = []
    if "strict-transport-security" not in headers:
        soft_warnings.append("Missing HSTS (Strict-Transport-Security)")
    if "x-content-type-options" not in headers:
        soft_warnings.append("Missing X-Content-Type-Options")
    if "content-security-policy" not in headers:
        soft_warnings.append("Missing Content-Security-Policy")

    if soft_warnings:
        # Migration tests should surface these as test failures, but with a
        # clear message so the dev can decide which to address pre-launch.
        pytest.fail("Security header issues:\n  - " + "\n  - ".join(soft_warnings))


def test_robots_txt_accessible(base_url):
    """MIG — robots.txt is reachable."""
    resp = requests.get(base_url.rstrip("/") + "/robots.txt",
                        timeout=REQUEST_TIMEOUT, allow_redirects=True)
    # 404 acceptable only if the site explicitly doesn't ship one;
    # 200 with a non-empty body is the happy path.
    if resp.status_code == 404:
        pytest.skip("Site does not ship a robots.txt")
    assert resp.status_code == 200
    assert len(resp.text.strip()) > 0


def test_sitemap_xml_accessible(base_url):
    """MIG — sitemap.xml is reachable, if shipped."""
    resp = requests.get(base_url.rstrip("/") + "/sitemap.xml",
                        timeout=REQUEST_TIMEOUT, allow_redirects=True)
    if resp.status_code == 404:
        pytest.skip("Site does not ship a sitemap.xml")
    assert resp.status_code == 200
    assert "<urlset" in resp.text or "<sitemapindex" in resp.text


def test_footer_pdfs_accessible(base_url):
    """MIG-017/018 — Privacy Notice and Cookies PDFs reachable."""
    # Production PDF paths observed during baseline. Update if the refactor
    # introduces new filenames; consider asking the dev for a canonical list.
    base = base_url.rstrip("/")
    pdf_candidates = [
        f"{base}/static/STLGearsApp/docs/PrivacyNotice.e17caa4d5182.pdf",
        f"{base}/static/STLGearsApp/docs/Cookies.ad43d77dbbfe.pdf",
    ]
    failures = []
    for pdf_url in pdf_candidates:
        try:
            resp = requests.head(pdf_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                failures.append(f"{pdf_url} -> {resp.status_code}")
        except requests.RequestException as e:
            failures.append(f"{pdf_url} -> {e}")
    if failures:
        pytest.fail("PDF asset(s) not reachable:\n  - " + "\n  - ".join(failures))


@pytest.mark.parametrize("path", [
    "/",
    "/generators/3dprint",
    "/theory",
])
def test_no_server_errors(base_url, path):
    """MIG — Core pages don't return 5xx."""
    resp = requests.get(base_url.rstrip("/") + path,
                        timeout=REQUEST_TIMEOUT, allow_redirects=True)
    assert resp.status_code < 500, (
        f"{path} returned server error {resp.status_code}"
    )
