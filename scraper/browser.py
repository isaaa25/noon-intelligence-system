# scraper/browser.py

import logging
from patchright.async_api import async_playwright

logger = logging.getLogger(__name__)


# ─── Browser ─────────────────────────────────────────────────

async def get_browser():
    """
    Launches a Patchright Chromium browser instance.
    Returns (playwright_instance, browser).
    Caller is responsible for closing both after use.

    Usage:
        playwright, browser = await get_browser()
        # ... do work ...
        await browser.close()
        await playwright.stop()
    """
    playwright = await async_playwright().start()

    # Note: We omit --disable-blink-features=AutomationControlled
    # because Patchright natively handles automation masking at the binary level.
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",  # Common addition for headless server stability
        ],
    )

    logger.info("Patchright Chromium browser successfully launched.")
    return playwright, browser


# ─── Context ─────────────────────────────────────────────────

async def get_context(browser, header: dict):
    """
    Creates a fresh browser context with a realistic fingerprint.
    Each scrape run or individual keyword profile should get a fresh context.
    
    Pass one header dict from your ScrapeOps pool.
    """
    user_agent = header.get(
        "user-agent",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )

    context = await browser.new_context(
        user_agent=user_agent,

        # Realistic desktop screen viewport
        viewport={"width": 1280, "height": 800},

        # UAE locale — ensures Noon defaults to local currency and settings
        locale="en-AE",

        # Dubai timezone
        timezone_id="Asia/Dubai",

        # Dubai geolocation used by Noon to assess localized vendor availability
        geolocation={"latitude": 25.2048, "longitude": 55.2708},
        permissions=["geolocation"],

        # Regional headers specific to Noon's platform behavior.
        # We avoid global content type headers (like 'accept') to prevent HTML requests from failing.
        extra_http_headers={
            "accept-language": header.get("accept-language", "en-AE,en-US;q=0.9,en;q=0.8"),
            "x-locale": "en-ae",
            "x-platform": "web",
            "x-mp-country": "ae",
            "x-content": "desktop",
        },
    )

    logger.info(f"Browser context generated successfully [UA: {user_agent[:45]}...]")
    return context