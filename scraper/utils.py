# scraper/utils.py

import asyncio
import random
import re
import logging
from typing import Optional
import httpx

from config import settings

logger = logging.getLogger(__name__)


# ─── ScrapeOps Header Pool ───────────────────────────────────

async def fetch_header_pool(num_results: int = 10) -> list[dict]:
    """
    Hit ScrapeOps once at startup.
    Returns a list of realistic browser header dicts.
    Store the result in memory — never call this per request.
    """
    url = "https://headers.scrapeops.io/v1/browser-headers"
    params = {
        "api_key": settings.SCRAPEOPS_API_KEY,
        "num_results": num_results,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            headers_list = data.get("result", [])

            if not headers_list:
                logger.warning(
                    "ScrapeOps returned empty headers. "
                    "Check your API key or quota."
                )
                return []

            logger.info(f"Fetched {len(headers_list)} headers from ScrapeOps.")
            return headers_list

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch headers from ScrapeOps: {e}")
        return []


def get_random_header(header_pool: list[dict]) -> dict:
    """
    Pick one random header dict from the in-memory pool.
    Pure function — no API call, no side effects.
    Falls back to a basic header if pool is empty.
    """
    if not header_pool:
        logger.warning("Header pool is empty. Using fallback header.")
        return {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
    return random.choice(header_pool)


# ─── Delay ───────────────────────────────────────────────────

async def random_delay() -> None:
    """
    Async sleep for a random duration between DELAY_MIN and DELAY_MAX.
    Always await this between requests — never skip it.
    """
    delay = random.uniform(settings.DELAY_MIN, settings.DELAY_MAX)
    logger.debug(f"Sleeping for {delay:.2f}s")
    await asyncio.sleep(delay)


# ─── Retry ───────────────────────────────────────────────────

async def retry(func, retries: int = None, *args, **kwargs):
    """
    Retries any async function with exponential backoff.

    Usage:
        result = await retry(some_async_func, 3, arg1, arg2, kwarg=value)

    On total failure returns None — never raises.
    Caller is responsible for handling None return.
    """
    if retries is None:
        retries = settings.MAX_RETRIES

    for attempt in range(1, retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            wait = 2 ** attempt  # 2s, 4s, 8s
            logger.warning(
                f"Attempt {attempt}/{retries} failed for "
                f"{func.__name__}: {e}. Retrying in {wait}s..."
            )
            await asyncio.sleep(wait)

    logger.error(
        f"All {retries} attempts failed for {func.__name__}. "
        f"Returning None."
    )
    return None


# ─── URL Builder ─────────────────────────────────────────────

def build_product_url(url_slug: str, sku: str) -> str:
    """
    Constructs a full Noon product URL from the url slug and SKU.
    Both values come directly from the search API response.

    Example:
        url_slug = "apple-iphone-15-pro-max-256gb"
        sku      = "N12345678V"
        result   = "https://www.noon.com/uae-en/apple-iphone-15-pro-max-256gb/N12345678V/p/"
    """
    base = "https://www.noon.com/uae-en"
    return f"{base}/{url_slug}/{sku}/p/"


# ─── Safe Type Casting ───────────────────────────────────────

def safe_float(value) -> Optional[float]:
    """
    Safely converts any value to float.
    Returns None if conversion fails for any reason.

    Handles: None, empty string "", "N/A", "AED 99", unexpected types.
    Never raises — always returns float or None.

    Usage:
        price = safe_float(hit.get("sale_price"))
        if price is None:
            # handle missing price explicitly
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.debug(f"safe_float: could not convert {value!r} to float.")
        return None


def safe_int(value) -> Optional[int]:
    """
    Safely converts any value to int.
    Returns None if conversion fails for any reason.

    Handles: None, empty string "", "N/A", float strings like "3.0".
    Never raises — always returns int or None.

    Usage:
        count = safe_int(hit.get("review_count")) or 0
        # the `or 0` gives you a safe default when None is returned
    """
    if value is None:
        return None
    try:
        # handle "3.0" style strings by converting via float first
        return int(float(value))
    except (ValueError, TypeError):
        logger.debug(f"safe_int: could not convert {value!r} to int.")
        return None


# ─── Partner ID Extractor ────────────────────────────────────

def extract_partner_id(logo_url: str) -> Optional[str]:
    """
    Extracts the Noon seller partner ID from their logo URL.

    The search API does not return seller IDs directly.
    However, the assets.logo URL always contains the numeric partner ID.
    We extract it and construct the standard "p-{id}" format.

    Example:
        logo_url = "https://p.nooncdn.com/reviews-partners/partner_assets/49644/logo_ae_..."
        returns  = "p-49644"

    Returns None if the URL is empty, None, or the pattern is not found.
    This is non-critical — a product without a partner ID is still saved,
    just without store-level tracking capability.
    """
    if not logo_url:
        return None

    match = re.search(r'partner_assets/(\d+)/', logo_url)
    if match:
        return f"p-{match.group(1)}"

    logger.debug(f"extract_partner_id: no partner ID found in URL: {logo_url!r}")
    return None