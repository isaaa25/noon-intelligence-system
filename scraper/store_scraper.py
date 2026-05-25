# scraper/store_scraper.py

import logging
from typing import Optional
from urllib.parse import urlencode
import re

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


# ─── Constants ───────────────────────────────────────────────

STORE_BASE_URL   = "https://www.noon.com/uae-en"
API_URL_FRAGMENT = "mp-customer-catalog-api"

SORT_OPTIONS = {
    "recommended": {"by": "recommended", "dir": "desc"},
    "price_asc":  {"by": "price",      "dir": "asc"},
    "price_desc": {"by": "price",      "dir": "desc"},
    "new_arrivals":{"by": "new_arrivals","dir": "desc"},
    "best_rated": {"by": "best_rated", "dir": "desc"},
}


# ─── URL Builder ─────────────────────────────────────────────

def build_store_url(partner_id: str, page: int, sort_by: str) -> str:
    """
    Builds the browser-facing store page URL.
    Patchright navigates here — the page's JS fires the store API call.
    We intercept that API call, not this URL directly.

    Example:
        partner_id = "p-49644"
        page       = 2
        sort_by    = "recommended"
        result     = "https://www.noon.com/uae-en/p-49644/?sort%5Bby%5D=popularity&..."
    """
    sort   = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["recommended"])
    params = {
        "sort[by]":  sort["by"],
        "sort[dir]": sort["dir"],
        "page":      page,
    }
    return f"{STORE_BASE_URL}/{partner_id}/?{urlencode(params)}"


# ─── Keyword Relevance Filter ─────────────────────────────────

def is_relevant(product_name: str, keywords: list[str]) -> bool:
    """
    Checks whether a product is relevant to any of our tracked keywords.
    Uses word boundary matching to prevent partial word false positives.

    Examples:
        keyword "phone" → matches "phone case"     ✓
        keyword "phone" → no match "headphones"    ✓
        keyword "iphone 15" → matches "Apple iPhone 15 Pro Max 256GB" ✓
        keyword "iphone 15" → matches "Case for iPhone 15"  ✓ (acceptable)

    Returns True if any keyword matches. False if none match.
    """
    if not product_name or not keywords:
        return False

    name_lower = product_name.lower()

    return any(
        re.search(rf"\b{re.escape(keyword.lower())}\b", name_lower)
        for keyword in keywords
    )

# ─── Product Extractor ───────────────────────────────────────

def extract_product_from_store(
    hit:        dict,
    index:      int,
    page_number: int,
    partner_id: str,
) -> Optional[dict]:
    """
    Extracts and maps a single product hit from the store API response.

    Almost identical to search_scraper's extract_product with two differences:
        1. No search_keyword field — this came from store browsing not a search
        2. No search_position field — position in a store page is not meaningful
        3. partner_id is passed in directly — already known from the store URL

    Returns None if product is missing critical fields.
    Never raises — safe casting throughout.
    """
    try:
        # ── Core identifiers ──────────────────────────────────
        noon_sku = hit.get("sku")
        url_slug = hit.get("url")

        if not noon_sku or not url_slug:
            logger.warning(
                f"[Store:{partner_id}] Skipping hit with missing SKU or URL: "
                f"{hit.get('name', 'unknown')}"
            )
            return None

        # ── Pricing ───────────────────────────────────────────
        current_price  = safe_float(hit.get("sale_price"))
        original_price = safe_float(hit.get("price"))

        if current_price is None:
            logger.warning(
                f"[Store:{partner_id}] Skipping product with no price: {noon_sku}"
            )
            return None

        # No real discount if both prices are equal
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

        # ── Partner ID ────────────────────────────────────────
        # We already know the partner_id from the store URL.
        # But we also extract from logo URL as a cross-check.
        # If logo gives a different ID something is wrong — log it.
        logo_url           = hit.get("assets", {}).get("logo", "")
        extracted_partner  = extract_partner_id(logo_url)

        if extracted_partner and extracted_partner != partner_id:
            logger.warning(
                f"[Store:{partner_id}] Partner ID mismatch — "
                f"URL says {partner_id}, logo says {extracted_partner}. "
                f"Using URL value."
            )

        return {
            # Product identity
            "noon_sku":      noon_sku,
            "name":          hit.get("name", "").strip(),
            "brand":         hit.get("brand", "").strip() or None,
            "url_slug":      url_slug,
            "product_url":   build_product_url(url_slug, noon_sku),
            "image_url":     hit.get("image_url"),

            # Seller — from the store we already know who this is
            "store_name":    hit.get("store_name", "unknown").strip() or "unknown",
            "partner_id":    partner_id,

            # Pricing
            "current_price":  current_price,
            "original_price": original_price,

            # Stock
            "stock_status":   stock_status,

            # Ratings
            "rating":         rating,
            "review_count":   review_count,

            # Store metadata
            # No search_position or search_keyword — not applicable here
            "is_ad":          bool(hit.get("is_ad", False)),
            "source":         "store",   # marks origin for loader awareness
        }

    except Exception as e:
        logger.error(
            f"[Store:{partner_id}] Unexpected error extracting product: {e} "
            f"| sku: {hit.get('sku', 'unknown')}"
        )
        return None


# ─── Single Store Page Scraper ────────────────────────────────

async def scrape_store_page(
    context:     BrowserContext,
    partner_id:  str,
    page_number: int,
    total_pages: int,
    sort_by:     str = "popularity",
) -> tuple[list[dict], Optional[int], Optional[int]]:
    """
    Scrapes a single page of a seller's store.

    Returns:
        Tuple of:
            - list of extracted raw product dicts (may be empty)
            - nbPages from API response (None if not captured)
            - nbHits from API response (None if not captured)

        nbHits is returned from page 1 only and used by the
        orchestrator (scrape_store) to decide max_pages dynamically.
        On subsequent pages it's redundant but we return it anyway
        for consistency — caller ignores it after page 1.
    """
    url  = build_store_url(partner_id, page_number, sort_by)
    page: Page = await context.new_page()

    logger.info(
        f"[Store:{partner_id}] Scraping page {page_number}/{total_pages}"
    )

    try:
        # ── Network Interception ──────────────────────────────
        # Same pattern as search_scraper — listener before navigation.
        # The store page fires the store API call during load.
        # We intercept that response directly.
        async with page.expect_response(
            lambda r: (
                API_URL_FRAGMENT in r.url
                and r.request.method == "GET"
            ),
            timeout=15000,
        ) as response_info:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

        captured  = await response_info.value
        json_data = await captured.json()

        # ── Read pagination metadata ──────────────────────────
        nb_pages = json_data.get("nbPages")
        nb_hits  = json_data.get("nbHits", 0)

        if nb_hits == 0:
            logger.warning(
                f"[Store:{partner_id}] Page {page_number} returned zero hits."
            )
            return [], nb_pages, nb_hits

        hits = json_data.get("hits", [])

        if not hits:
            logger.warning(
                f"[Store:{partner_id}] Hits array empty on page {page_number}."
            )
            return [], nb_pages, nb_hits

        # ── Extract each product ──────────────────────────────
        products = []
        for index, hit in enumerate(hits):
            product = extract_product_from_store(
                hit         = hit,
                index       = index,
                page_number = page_number,
                partner_id  = partner_id,
            )
            if product is not None:
                products.append(product)

        logger.info(
            f"[Store:{partner_id}] Page {page_number}: "
            f"{len(products)}/{len(hits)} products extracted."
        )

        return products, nb_pages, nb_hits

    except Exception as e:
        logger.error(
            f"[Store:{partner_id}] Failed to scrape page {page_number}: {e}"
        )
        return [], None, None

    finally:
        await page.close()


# ─── Main Store Scraper ───────────────────────────────────────

async def scrape_store(
    context:    BrowserContext,
    partner_id: str,
    keywords:   list[str],
    max_pages:  int = None,
    sort_by:    str = "popularity",
) -> list[dict]:
    """
    Scrapes a seller's store page and returns only keyword-relevant products.

    The scraper is deliberately dumb about page limits.
    max_pages is decided by the orchestrator (main.py) based on nbHits.
    If max_pages is not provided, it falls back to STORE_PAGES_LARGE from config.

    Page 1 is always scraped first to read nbHits and nbPages.
    The orchestrator already decided max_pages before calling this,
    but we still respect nbPages from the API as a hard ceiling —
    never request a page that doesn't exist.

    Deduplicates by noon_sku across all pages.
    Filters by keyword relevance after extraction.

    Args:
        context    : Patchright browser context
        partner_id : seller store ID e.g. "p-49644"
        keywords   : list of tracked keywords e.g. ["iphone 15", "iphone 15 pro max"]
        max_pages  : maximum pages to scrape (set by orchestrator)
        sort_by    : sort order — default popularity surfaces best sellers first

    Returns:
        Flat deduplicated list of keyword-relevant raw product dicts.
        Empty list if store is unreachable or no relevant products found.
    """
    if max_pages is None:
        max_pages = settings.STORE_PAGES_LARGE

    if sort_by not in SORT_OPTIONS:
        logger.warning(
            f"[Store:{partner_id}] Unknown sort_by '{sort_by}'. "
            f"Falling back to 'popularity'."
        )
        sort_by = "popularity"

    all_products:    list[dict] = []
    seen_skus:       set[str]   = set()
    actual_max_pages: int        = max_pages  # may be lowered after page 1

    for page_number in range(1, max_pages + 1):

        # ── Respect the actual ceiling ────────────────────────
        # actual_max_pages gets updated after page 1
        # when we know the real nbPages from the API
        if page_number > actual_max_pages:
            logger.info(
                f"[Store:{partner_id}] Stopping — reached page ceiling "
                f"({actual_max_pages})."
            )
            break

        products, nb_pages, nb_hits = await scrape_store_page(
            context     = context,
            partner_id  = partner_id,
            page_number = page_number,
            total_pages = actual_max_pages,
            sort_by     = sort_by,
        )

        # ── After page 1 — update ceiling from real API data ──
        # We now know nb_pages (actual pages available in this store)
        # and nb_hits (total products in store).
        # Orchestrator already set max_pages based on nb_hits,
        # but nb_pages is the hard ceiling — never exceed it.
        if page_number == 1 and nb_pages is not None:
            actual_max_pages = min(max_pages, nb_pages)
            logger.info(
                f"[Store:{partner_id}] Store has {nb_hits} products "
                f"across {nb_pages} pages. "
                f"Will scrape up to {actual_max_pages} pages."
            )

        # ── Keyword filter + deduplication ────────────────────
        relevant_on_page = 0

        for product in products:
            sku  = product["noon_sku"]
            name = product["name"]

            # Deduplication first — cheaper than relevance check
            if sku in seen_skus:
                logger.debug(f"[Store:{partner_id}] Duplicate SKU skipped: {sku}")
                continue

            # Keyword relevance filter
            if not is_relevant(name, keywords):
                logger.debug(
                    f"[Store:{partner_id}] Not relevant to keywords: {name[:60]}"
                )
                continue

            seen_skus.add(sku)
            all_products.append(product)
            relevant_on_page += 1

        logger.info(
            f"[Store:{partner_id}] Page {page_number}: "
            f"{relevant_on_page} relevant products kept."
        )

        # ── Early stop — no more pages available ──────────────
        if nb_pages is not None and page_number >= nb_pages:
            logger.info(
                f"[Store:{partner_id}] Reached last available page "
                f"({page_number}/{nb_pages}). Stopping."
            )
            break

        # ── Delay between pages ───────────────────────────────
        if page_number < actual_max_pages:
            await random_delay()

    logger.info(
        f"[Store:{partner_id}] Complete. "
        f"Total relevant products collected: {len(all_products)}"
    )

    return all_products