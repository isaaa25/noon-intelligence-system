# pipeline/cleaner.py

import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Valid Values ─────────────────────────────────────────────

VALID_STOCK_STATUSES = {"in_stock", "out_of_stock", "limited", "unknown"}
VALID_SOURCES        = {"search", "store"}


# ─── Private Helpers ──────────────────────────────────────────

def _clean_string(value, max_length: int = None) -> Optional[str]:
    """
    Strips whitespace from a string value.
    Returns None if value is None, not a string, or empty after stripping.
    Truncates to max_length if provided.
    """
    if value is None:
        return None
    try:
        cleaned = str(value).strip()
        if not cleaned:
            return None
        if max_length and len(cleaned) > max_length:
            logger.debug(f"Truncating string from {len(cleaned)} to {max_length} chars.")
            cleaned = cleaned[:max_length]
        return cleaned
    except Exception:
        return None


def _clean_decimal(value) -> Optional[Decimal]:
    """
    Converts a value to Decimal for database precision.
    Returns None if conversion fails for any reason.
    Handles float, int, string representations of numbers.
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.debug(f"Could not convert {value!r} to Decimal.")
        return None


def _calculate_discount_pct(
    original: Optional[Decimal],
    current:  Optional[Decimal],
) -> Optional[Decimal]:
    """
    Calculates discount percentage from original and current prices.
    Pre-computed here so dashboard queries never recalculate on the fly.

    Formula: ((original - current) / original) * 100
    Rounded to 2 decimal places.

    Returns None if either price is missing or original is zero.
    """
    if original is None or current is None:
        return None
    if original <= 0:
        return None
    try:
        pct = ((original - current) / original) * Decimal("100")
        return round(pct, 2)
    except (InvalidOperation, ZeroDivisionError):
        return None


def _clean_stock_status(value) -> str:
    """
    Normalizes stock status to one of our four valid values.
    Falls back to "unknown" for anything unrecognized.
    Protects the CheckConstraint in the database.
    """
    if not value:
        return "unknown"
    normalized = str(value).lower().strip()
    if normalized in VALID_STOCK_STATUSES:
        return normalized
    logger.debug(f"Unrecognized stock_status {value!r}. Defaulting to 'unknown'.")
    return "unknown"


def _clean_rating(value) -> Optional[float]:
    """
    Validates rating is within the 0.0 to 5.0 range.
    Noon ratings are always 0-5. Anything outside is a data error.
    Returns None if invalid rather than storing bad data.
    """
    if value is None:
        return None
    try:
        rating = float(value)
        if 0.0 <= rating <= 5.0:
            return rating
        logger.warning(f"Rating {rating} is outside 0-5 range. Setting to None.")
        return None
    except (ValueError, TypeError):
        return None


def _clean_image_url(value) -> Optional[str]:
    """
    Basic URL validation — must start with http.
    We don't download images, just store the URL.
    Returns None if URL looks malformed.
    """
    if not value:
        return None
    url = str(value).strip()
    if url.startswith("http"):
        return url
    logger.debug(f"Invalid image URL {url!r}. Setting to None.")
    return None


def _clean_partner_id(value) -> Optional[str]:
    """
    Validates partner_id format — must match "p-{digits}".
    Returns None if format is wrong.
    Non-critical — seller is still saved, just without store tracking.
    """
    if not value:
        return None
    if re.match(r'^p-\d+$', str(value).strip()):
        return str(value).strip()
    logger.warning(f"Invalid partner_id format {value!r}. Setting to None.")
    return None


def _clean_source(value) -> str:
    """
    Normalizes source field to "search" or "store".
    Falls back to "search" for anything unrecognized.
    """
    if not value:
        return "search"
    normalized = str(value).lower().strip()
    if normalized in VALID_SOURCES:
        return normalized
    return "search"


# ─── Section Cleaners ─────────────────────────────────────────

def _clean_seller_section(raw: dict) -> dict:
    """
    Extracts and cleans seller-related fields.
    Maps to the sellers table.

    Note on store_name uniqueness:
        "unknown" is a valid fallback for missing store names.
        Multiple products with missing store names all map to the
        same "unknown" seller row. The loader handles this with
        ON CONFLICT DO NOTHING to avoid unique constraint violations.
    """
    store_name = _clean_string(raw.get("store_name"), max_length=200)
    if not store_name:
        logger.debug("Missing store_name. Using 'unknown' fallback.")
        store_name = "unknown"

    return {
        "store_name": store_name,
        "store_slug": _clean_partner_id(raw.get("partner_id")),
    }


def _clean_product_section(raw: dict) -> dict:
    """
    Extracts and cleans product identity fields.
    Maps to the products table.
    """
    return {
        "noon_sku":       _clean_string(raw.get("noon_sku")),
        "name":           _clean_string(raw.get("name")),
        "brand":          _clean_string(raw.get("brand"), max_length=200),
        "category": None,
        "subcategory": None,
        "search_keyword": _clean_string(raw.get("search_keyword"), max_length=200),
        "product_url":    raw.get("product_url"),
        "image_url":      _clean_image_url(raw.get("image_url")),
    }


def _clean_snapshot_section(raw: dict) -> dict:
    """
    Extracts and cleans price snapshot fields.
    Maps to the price_snapshots table.

    Discount is calculated here and stored pre-computed.
    Source column records which scraper produced this snapshot.
    """
    current_price  = _clean_decimal(raw.get("current_price"))
    original_price = _clean_decimal(raw.get("original_price"))

    # Extra guard — original must be >= current to be meaningful
    if original_price is not None and current_price is not None:
        if original_price <= current_price:
            logger.warning(
                f"original_price {original_price} < current_price {current_price}. "
                f"Discarding original_price."
            )
            original_price = None

    discount_pct = _calculate_discount_pct(original_price, current_price)

    # review_count — never negative, never None
    raw_count    = raw.get("review_count")
    review_count = max(int(raw_count), 0) if raw_count is not None else 0

    # search_position — must be positive integer or None
    raw_position    = raw.get("search_position")
    search_position = None
    if raw_position is not None:
        try:
            pos = int(raw_position)
            search_position = pos if pos > 0 else None
        except (ValueError, TypeError):
            search_position = None

    return {
        "current_price":   current_price,
        "original_price":  original_price,
        "discount_pct":    discount_pct,
        "currency":        "AED",
        "stock_status":    _clean_stock_status(raw.get("stock_status")),
        "rating":          _clean_rating(raw.get("rating")),
        "review_count":    review_count,
        "is_sponsored":    bool(raw.get("is_ad", False)),
        "search_position": search_position,
        "source":          _clean_source(raw.get("source")),
    }


def _is_valid(product: dict, snapshot: dict) -> bool:
    """
    Determines if a record is worth saving at all.

    Rejection conditions — foundational anchors only:
        - noon_sku missing or empty
        - name missing or empty
        - current_price missing
        - current_price zero or negative

    Everything else degrades gracefully rather than rejecting.
    """
    if not product.get("noon_sku"):
        logger.warning("Rejecting record: missing noon_sku.")
        return False

    if not product.get("name"):
        logger.warning(
            f"Rejecting record: missing name "
            f"| sku: {product.get('noon_sku')}"
        )
        return False

    current_price = snapshot.get("current_price")

    if current_price is None:
        logger.warning(
            f"Rejecting record: missing current_price "
            f"| sku: {product.get('noon_sku')}"
        )
        return False

    if current_price <= 0:
        logger.warning(
            f"Rejecting record: current_price is {current_price} "
            f"| sku: {product.get('noon_sku')}"
        )
        return False

    return True


# ─── Public Interface ─────────────────────────────────────────

def clean_product(raw: dict) -> dict:
    """
    Takes a raw product dict from either scraper and returns a
    structured clean dict ready for the loader.

    Input:  raw dict from search_scraper or store_scraper
    Output: nested dict with seller, product, snapshot sections
            plus a valid flag the loader uses to decide whether to proceed

    The loader uses the output like this:
        if not result["valid"]: skip
        result["seller"]   → sellers table
        result["product"]  → products table
        result["snapshot"] → price_snapshots table

    Never raises — all errors are logged and degrade gracefully.
    Records missing foundational anchors (SKU, name, price) are
    marked invalid. Everything else saves with safe defaults.
    """
    try:
        seller   = _clean_seller_section(raw)
        product  = _clean_product_section(raw)
        snapshot = _clean_snapshot_section(raw)
        valid    = _is_valid(product, snapshot)

        if not valid:
            return {
                "valid":    False,
                "seller":   seller,
                "product":  product,
                "snapshot": snapshot,
            }

        return {
            "valid":    True,
            "seller":   seller,
            "product":  product,
            "snapshot": snapshot,
        }

    except Exception as e:
        logger.error(
            f"Unexpected error in clean_product: {e} "
            f"| raw sku: {raw.get('noon_sku', 'unknown')}"
        )
        return {
            "valid":    False,
            "seller":   {},
            "product":  {},
            "snapshot": {},
        }