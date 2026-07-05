"""
Handicap Scraper Module - Clean version (NO caching, NO Streamlit dependencies)
"""
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

HANDICAPS_URL = "https://www.handicaps.co.za/login"
HEADLESS = True  # Streamlit cannot show visible browsers


# ================================================================================
# INTERNAL: LOGIN
# ================================================================================
def _login_and_get_page(p, username, password):
    """Login and return (browser, page)."""

    browser = p.chromium.launch(headless=HEADLESS)
    page = browser.new_page()

    logger.info("Navigating to login page...")
    page.goto(HANDICAPS_URL, timeout=60000)

    # Login fields
    page.fill("#MemNo", username)
    page.fill("#Password", password)
    page.click("button.dg-login-signup__btn")

    # Wait for dashboard search box
    try:
        page.get_by_role("textbox", name="Search by name or Mem No.").wait_for(timeout=30000)
    except PlaywrightTimeoutError:
        page.wait_for_selector("input[placeholder*='Search']", timeout=30000)

    logger.info("Login successful.")
    return browser, page


# ================================================================================
# INTERNAL: SEARCH BOX
# ================================================================================
def _fill_search_box(page, membership_number):
    """Fill the search box using the correct selector."""
    try:
        box = page.get_by_role("textbox", name="Search by name or Mem No.")
        box.fill(membership_number)
    except Exception:
        page.fill("input[placeholder*='Search']", membership_number)

    page.wait_for_timeout(1200)  # allow Vue to fetch + render


# ================================================================================
# INTERNAL: EXTRACT NAME + INDEX
# ================================================================================
def _extract_name_and_index(page, fallback_name=None):
    """Extract name + handicap index from Vue-rendered DOM."""

    try:
        page.wait_for_selector("a[data-bind*='Name']", timeout=20000)
        page.wait_for_selector("span[data-bind*='HandicapIndexText']", timeout=20000)
    except PlaywrightTimeoutError:
        logger.warning("Vue did not render any results.")
        return fallback_name, None

    # --- Name ---
    raw_name = (
        page.locator("a[data-bind*='Name']")
        .first.inner_text()
        .strip()
    )

    if "," in raw_name:
        last, first = raw_name.split(",", 1)
        name = f"{first.strip()} {last.strip()}"
    else:
        name = raw_name

    # --- Handicap Index ---
    index_text = (
        page.locator("span[data-bind*='HandicapIndexText']")
        .first.inner_text()
        .strip()
    )

    handicap_index = None if index_text.lower() == "pending" else index_text

    return name, handicap_index


# ================================================================================
# PUBLIC: SCRAPE HANDICAP
# ================================================================================
def scrape_handicap_pw(username, password, membership_number, fallback_name=None):
    """
    Scrape a single member's name + handicap index.
    Returns (name, index) or (fallback_name, None) on failure.
    """

    try:
        with sync_playwright() as p:
            browser, page = _login_and_get_page(p, username, password)

            _fill_search_box(page, membership_number)

            name, index = _extract_name_and_index(page, fallback_name=fallback_name)

            browser.close()
            return name, index

    except Exception as e:
        logger.error(f"Scrape error for {membership_number}: {e}")
        return fallback_name, None
