# scraper/search_scraper.py

import logging
from typing import Optional
from urllib.parse import quote_plus

from patchright.async_api import BrowserContext, Page

from config import settings
from scraper.utils import (
    random_delay,
    build_product_url,
    safe_float,
    safe_int,
    extract_partner_id,
)

logger = logging.getLogger(__name__)


# ─── Sort Options ────────────────────────────────────────────

SORT_OPTIONS = {
    "recommended":   {"by": "recommended",   "dir": "desc"},
    "price_asc":    {"by": "price",        "dir": "asc"},
    "price_desc":   {"by": "price",        "dir": "desc"},
    "new_arrivals": {"by": "new_arrivals", "dir": "desc"},
    "best_rated":   {"by": "best_rated",   "dir": "desc"},
}

BASE_SEARCH_URL  = "https://www.noon.com/uae-en/search/"
API_URL_FRAGMENT = "mp-customer-catalog-api"


# ─── URL Builder ─────────────────────────────────────────────

def build_search_url(keyword: str, page: int, sort_by: str) -> str:
    """
    Builds the full Noon search page URL.
    Uses quote_plus to safely encode any keyword including
    special characters like &, %, /, +, #.
    """
    sort          = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["recommended"])
    encoded       = quote_plus(keyword)

    return (
        f"{BASE_SEARCH_URL}"
        f"?q={encoded}"
        f"&sort%5Bby%5D={sort['by']}"
        f"&sort%5Bdir%5D={sort['dir']}"
        f"&page={page}"
    )


# ─── Product Extractor ───────────────────────────────────────

def extract_product(
    hit:         dict,
    index:       int,
    page_number: int,
    keyword:     str,
) -> Optional[dict]:
    """
    Extracts and maps a single product hit from the API response.
    Uses safe casting throughout — never raises on bad API data.
    Returns None if the product is missing critical fields.
    """
    try:
        # ── Core identifiers ──────────────────────────────────
        noon_sku = hit.get("sku")
        url_slug = hit.get("url")

        if not noon_sku or not url_slug:
            logger.warning(
                f"Skipping hit with missing SKU or URL: "
                f"{hit.get('name', 'unknown')}"
            )
            return None

        # ── Pricing ───────────────────────────────────────────
        # safe_float handles "", None, "N/A", unexpected types
        current_price  = safe_float(hit.get("sale_price"))
        original_price = safe_float(hit.get("price"))

        # No current price = product is unusable
        if current_price is None:
            logger.warning(f"Skipping product with no price: {noon_sku}")
            return None

        # If original equals current there is no real discount
        if original_price is not None and original_price == current_price:
            original_price = None

        # ── Stock Status ──────────────────────────────────────
        is_buyable   = hit.get("is_buyable", False)
        stock_status = "in_stock" if is_buyable else "out_of_stock"

        # ── Ratings ───────────────────────────────────────────
        product_rating = hit.get("product_rating")
        rating         = None
        review_count   = 0

        if product_rating is not None:
            rating       = safe_float(product_rating.get("value"))
            review_count = safe_int(product_rating.get("count")) or 0

        # ── Search Position ───────────────────────────────────
        search_position = ((page_number - 1) * 50) + index + 1

        # ── Partner ID ────────────────────────────────────────
        # Extracted from assets.logo URL — non-critical field
        # Used for store-level tracking via store_scraper
        logo_url   = hit.get("assets", {}).get("logo", "")
        partner_id = extract_partner_id(logo_url)

        return {
            # Product identity
            "noon_sku":       noon_sku,
            "name":           hit.get("name", "").strip(),
            "brand":          hit.get("brand", "").strip() or None,
            "url_slug":       url_slug,
            "product_url":    build_product_url(url_slug, noon_sku),
            "image_url":      hit.get("image_url"),

            # Seller
            "store_name":     hit.get("store_name", "unknown").strip() or "unknown",
            "partner_id":     partner_id,

            # Pricing
            "current_price":  current_price,
            "original_price": original_price,

            # Stock
            "stock_status":   stock_status,

            # Ratings
            "rating":         rating,
            "review_count":   review_count,

            # Search metadata
            "is_ad":            bool(hit.get("is_ad", False)),
            "search_position":  search_position,
            "search_keyword":   keyword,
        }

    except Exception as e:
        logger.error(
            f"Unexpected error extracting product: {e} "
            f"| sku: {hit.get('sku', 'unknown')}"
        )
        return None


# ─── Single Page Scraper ─────────────────────────────────────

async def scrape_page(
    context:     BrowserContext,
    keyword:     str,
    page_number: int,
    sort_by:     str,
    total_pages: int,
) -> tuple[list[dict], Optional[int]]:
    """
    Scrapes a single search results page.

    Returns:
        Tuple of:
            - list of extracted product dicts (may be empty)
            - nbPages from API response (None if not captured)
    """
    url  = build_search_url(keyword, page_number, sort_by)
    page: Page = await context.new_page()

    logger.info(
        f"[{keyword}] Scraping page {page_number}/{total_pages} "
        f"| sort: {sort_by}"
    )

    try:
        # ── Network Interception ──────────────────────────────
        # Listener registered BEFORE goto — prevents race condition.
        # The browser fires the API call during page load.
        # expect_response catches it the moment it arrives.
        async with page.expect_response(
            lambda r: (
                API_URL_FRAGMENT in r.url
                and r.request.method == "GET"
            ),
            timeout=15000,
        ) as response_info:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

        captured   = await response_info.value
        json_data  = await captured.json()

        # ── Pagination guard ──────────────────────────────────
        nb_pages = json_data.get("nbPages")
        nb_hits  = json_data.get("nbHits", 0)

        if nb_hits == 0:
            logger.warning(
                f"[{keyword}] Page {page_number} returned zero hits."
            )
            return [], nb_pages

        hits = json_data.get("hits", [])

        if not hits:
            logger.warning(
                f"[{keyword}] Hits array empty on page {page_number}."
            )
            return [], nb_pages

        # ── Extract each product ──────────────────────────────
        products = []
        for index, hit in enumerate(hits):
            product = extract_product(hit, index, page_number, keyword)
            if product is not None:
                products.append(product)

        logger.info(
            f"[{keyword}] Page {page_number}: "
            f"{len(products)}/{len(hits)} products extracted."
        )

        return products, nb_pages

    except Exception as e:
        logger.error(
            f"[{keyword}] Failed to scrape page {page_number}: {e}"
        )
        return [], None

    finally:
        # Always close — cookies stay at context level
        await page.close()


# ─── Main Search Scraper ─────────────────────────────────────

async def scrape_search(
    context: BrowserContext,
    keyword: str,
    pages:   int = None,
    sort_by: str = "recommended",
) -> list[dict]:
    """
    Scrapes multiple pages of Noon search results for a keyword.

    Deduplicates by noon_sku across all pages — sponsored listings
    frequently appear again as organic results further down.

    Args:
        context : Patchright browser context
        keyword : search term e.g. "iphone 15 pro max"
        pages   : number of pages (defaults to config value)
        sort_by : key from SORT_OPTIONS

    Returns:
        Flat deduplicated list of raw product dicts.
    """
    if pages is None:
        pages = settings.PAGES_PER_KEYWORD

    if sort_by not in SORT_OPTIONS:
        logger.warning(
            f"Unknown sort_by '{sort_by}'. Falling back to 'recommended'."
        )
        sort_by = "recommended"

    all_products: list[dict] = []
    seen_skus:    set[str]   = set()

    for page_number in range(1, pages + 1):

        products, nb_pages = await scrape_page(
            context     = context,
            keyword     = keyword,
            page_number = page_number,
            sort_by     = sort_by,
            total_pages = pages,
        )

        # ── Deduplicate across pages ──────────────────────────
        for product in products:
            sku = product["noon_sku"]
            if sku in seen_skus:
                logger.debug(f"Duplicate SKU skipped: {sku}")
                continue
            seen_skus.add(sku)
            all_products.append(product)

        # ── Early stop ────────────────────────────────────────
        if nb_pages is not None and page_number >= nb_pages:
            logger.info(
                f"[{keyword}] Reached last available page "
                f"({page_number}/{nb_pages}). Stopping."
            )
            break

        if page_number < pages:
            await random_delay()

    logger.info(
        f"[{keyword}] Complete. "
        f"Total unique products: {len(all_products)}"
    )

    return all_products