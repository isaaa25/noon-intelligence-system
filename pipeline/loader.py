# pipeline/loader.py

import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from config import settings
from pipeline.models import (
    Seller,
    Product,
    PriceSnapshot,
    PriceAlert,
    ScrapeLog,
)

logger = logging.getLogger(__name__)


# ─── Seller ───────────────────────────────────────────────────

def upsert_seller(session: Session, clean_seller: dict) -> int:
    
    store_name = clean_seller["store_name"]
    store_slug = clean_seller.get("store_slug")

    stmt = (
        pg_insert(Seller)
        .values(
            store_name=store_name,
            store_slug=store_slug,
            is_client=False,
            is_tracked=False,
        )
        .on_conflict_do_nothing(index_elements=["store_name"])
    )
    session.execute(stmt)

    # Single-threaded safe.
    # If scaled to concurrent workers, Worker B could hit ON CONFLICT
    # DO NOTHING before Worker A commits, making this SELECT return empty.
    # Fix when scaling: wrap in retry loop or pre-cache seller IDs in main.py.
    seller = session.execute(
        text("SELECT id FROM sellers WHERE store_name = :name"),
        {"name": store_name},
    ).fetchone()

    if seller is None:
        raise RuntimeError(
            f"Failed to get seller_id for store_name='{store_name}'. "
            f"This should never happen."
        )

    return seller.id


# ─── Product ──────────────────────────────────────────────────

def upsert_product(
    session:     Session,
    clean_product: dict,
    seller_id:   int,
) -> tuple[int, bool]:
    """
    Gets or creates a product row by noon_sku.

    On conflict (product already exists):
        Updates last_seen_at, is_active, and seller_id.
        last_seen_at — proves the product is still live on Noon.
        is_active    — reactivates products that previously disappeared.
        seller_id    — captures if product transferred between sellers.

    Uses PostgreSQL xmax trick to detect insert vs update in one
    atomic query without a second round-trip.
        xmax = 0  → row was freshly inserted (new product)
        xmax != 0 → row was updated (existing product)

    Returns:
        Tuple of (product_id, is_new)
        is_new = True  → first time we've ever seen this product
        is_new = False → product existed before this run
    """
    stmt = (
        pg_insert(Product)
        .values(
            noon_sku       = clean_product["noon_sku"],
            seller_id      = seller_id,
            name           = clean_product["name"],
            brand          = clean_product.get("brand"),
            category       = clean_product.get("category"),
            subcategory    = clean_product.get("subcategory"),
            search_keyword = clean_product.get("search_keyword"),
            product_url    = clean_product.get("product_url"),
            image_url      = clean_product.get("image_url"),
            is_active      = True,
        )
        .on_conflict_do_update(
            index_elements=["noon_sku"],
            set_={
                "last_seen_at": text("NOW()"),
                "is_active":    True,
                "seller_id":    seller_id,
            },
        )
        .returning(
            Product.id,
            # xmax = 0 means freshly inserted row
            # xmax != 0 means this was an update
            text("(xmax = 0) AS is_new"),
        )
    )

    result = session.execute(stmt).fetchone()

    if result is None:
        raise RuntimeError(
            f"Failed to upsert product with sku='{clean_product['noon_sku']}'."
        )
        

    return result[0], bool(result[1])


# ─── Latest Snapshot ──────────────────────────────────────────

def get_latest_snapshot(session: Session, product_id: int) -> Optional[PriceSnapshot]:
    stmt = (
        select(PriceSnapshot)
        .where(PriceSnapshot.product_id == product_id)
        .order_by(PriceSnapshot.scraped_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()

# ─── Change Detection ─────────────────────────────────────────

def _has_changed(
    previous: Optional[PriceSnapshot],
    clean_snapshot: dict,
) -> bool:
    """
    Determines whether a new snapshot should be inserted.

    Only two fields trigger a new snapshot:
        1. current_price changed
        2. stock_status changed

    Rating, review_count, search_position are deliberately excluded.
    These fields change constantly in small amounts and would generate
    thousands of low-value snapshots daily if used as change signals.

    If no previous snapshot exists this is the first scrape
    for this product — always insert.
    """
    if previous is None:
        return True

    price_changed = (
        Decimal(str(previous.current_price)) !=
        Decimal(str(clean_snapshot["current_price"]))
    )

    stock_changed = (
        previous.stock_status != clean_snapshot["stock_status"]
    )

    return price_changed or stock_changed


# ─── Snapshot ─────────────────────────────────────────────────

def insert_snapshot(
    session:        Session,
    clean_snapshot: dict,
    product_id:     int,
) -> int:
    """
    Inserts a new price snapshot row.
    Always inserts — never updates.
    Caller is responsible for calling _has_changed first.

    Returns the new snapshot's integer primary key.
    """
    snapshot = PriceSnapshot(
        product_id     = product_id,
        current_price  = clean_snapshot["current_price"],
        original_price = clean_snapshot.get("original_price"),
        discount_pct   = clean_snapshot.get("discount_pct"),
        currency       = clean_snapshot.get("currency", "AED"),
        stock_status   = clean_snapshot["stock_status"],
        rating         = clean_snapshot.get("rating"),
        review_count   = clean_snapshot.get("review_count", 0),
        is_sponsored   = clean_snapshot.get("is_sponsored", False),
        search_position= clean_snapshot.get("search_position"),
        source         = clean_snapshot.get("source", "search"),
        scraped_at     = datetime.now(timezone.utc),
    )

    session.add(snapshot)
    session.flush()  # assigns snapshot.id without committing

    return snapshot.id


# ─── Alert Detection ──────────────────────────────────────────

def check_and_create_alerts(
    session:        Session,
    product_id:     int,
    clean_snapshot: dict,
    previous:       Optional[PriceSnapshot],
) -> int:
    """
    Compares the new snapshot against the previous one and creates
    alerts for significant changes.

    Two completely independent alert branches:

    Branch 1 — Price alerts (threshold-based)
        Uses abs(change_pct) so both drops AND hikes trigger alerts.
        alert_type = "price_drop"     if price went down
        alert_type = "price_increase" if price went up

    Branch 2 — Stock alerts (always fire, no threshold)
        Going out of stock or coming back in stock is always significant.
        alert_type = "out_of_stock"   if went from in_stock to out_of_stock
        alert_type = "back_in_stock"  if went from out_of_stock to in_stock

    Returns count of alerts created in this call.
    """
    if previous is None:
        # First snapshot — nothing to compare against
        return 0

    alerts_created = 0
    current_price  = Decimal(str(clean_snapshot["current_price"]))
    previous_price = Decimal(str(previous.current_price))
    current_stock  = clean_snapshot["stock_status"]
    previous_stock = previous.stock_status

    # ── Branch 1: Price Alert ─────────────────────────────────
    if previous_price > 0:
        change_pct = (
            (previous_price - current_price) / previous_price
        ) * Decimal("100")

        if abs(change_pct) >= Decimal(
            str(settings.PRICE_CHANGE_THRESHOLD_PCT)
        ):
            # Positive change_pct = price went DOWN (drop)
            # Negative change_pct = price went UP (increase)
            alert_type = (
                "price_drop" if change_pct > 0 else "price_increase"
            )

            alert = PriceAlert(
                product_id    = product_id,
                alert_type    = alert_type,
                previous_value= previous_price,
                current_value = current_price,
                change_pct    = round(change_pct, 2),
                threshold_used= Decimal(
                    str(settings.PRICE_CHANGE_THRESHOLD_PCT)
                ),
                is_seen       = False,
            )
            session.add(alert)
            alerts_created += 1

            logger.info(
                f"[Alert] {alert_type} | product_id={product_id} | "
                f"{previous_price} → {current_price} "
                f"({round(change_pct, 2)}%)"
            )

    # ── Branch 2: Stock Alert ─────────────────────────────────
    if previous_stock != current_stock:
        if current_stock == "out_of_stock":
            stock_alert_type = "out_of_stock"
        elif current_stock == "in_stock" and previous_stock == "out_of_stock":
            stock_alert_type = "back_in_stock"
        else:
            stock_alert_type = None

        if stock_alert_type:
            alert = PriceAlert(
                product_id    = product_id,
                alert_type    = stock_alert_type,
                previous_value= None,
                current_value = None,
                change_pct    = None,
                threshold_used= None,
                is_seen       = False,
            )
            session.add(alert)
            alerts_created += 1

            logger.info(
                f"[Alert] {stock_alert_type} | product_id={product_id} | "
                f"{previous_stock} → {current_stock}"
            )

    return alerts_created


# ─── Scrape Log ───────────────────────────────────────────────

def log_scrape_run(session: Session, log_data: dict) -> None:
    """
    Inserts one scrape log row per keyword per run.
    Called by main.py after each keyword finishes processing.

    Status logic:
        errors == 0 and products_saved > 0  → "success"
        errors > 0  and products_saved > 0  → "partial"
        products_saved == 0                 → "failed"
    """
    products_saved = (
        log_data.get("products_new", 0) +
        log_data.get("products_updated", 0)
    )
    errors = log_data.get("errors", 0)

    if products_saved == 0:
        status = "failed"
    elif errors > 0:
        status = "partial"
    else:
        status = "success"

    scrape_log = ScrapeLog(
        keyword          = log_data.get("keyword"),
        pages_scraped    = log_data.get("pages_scraped", 0),
        products_found   = log_data.get("products_found", 0),
        products_new     = log_data.get("products_new", 0),
        products_updated = log_data.get("products_updated", 0),
        alerts_triggered = log_data.get("alerts_triggered", 0),
        errors           = errors,
        error_details    = log_data.get("error_details"),
        duration_secs    = log_data.get("duration_secs"),
        status           = status,
    )

    session.add(scrape_log)
    logger.info(
        f"[ScrapeLog] keyword='{log_data.get('keyword')}' | "
        f"status={status} | "
        f"new={log_data.get('products_new', 0)} | "
        f"updated={log_data.get('products_updated', 0)} | "
        f"alerts={log_data.get('alerts_triggered', 0)} | "
        f"errors={errors}"
    )


# ─── Orchestrator ─────────────────────────────────────────────

def save_product(session: Session, clean: dict) -> dict:
    """
    Full pipeline for one product — seller → product → snapshot → alerts.
    This is the only function main.py calls per product.

    Takes the structured clean dict from cleaner.clean_product().
    Returns a stats dict that main.py aggregates into the scrape log.

    Return values:
        status   : "rejected" | "skipped" | "saved"
        is_new   : True if product was inserted for the first time
        snapshot : True if a new snapshot row was inserted
        alerts   : count of alerts created
    """
    # ── Step 1: Validity check ────────────────────────────────
    if not clean.get("valid"):
        logger.debug(
            f"Rejected: {clean.get('product', {}).get('noon_sku', 'unknown')}"
        )
        return {
            "status":   "rejected",
            "is_new":   False,
            "snapshot": False,
            "alerts":   0,
        }

    try:
        # ── Step 2: Upsert seller ─────────────────────────────
        seller_id = upsert_seller(session, clean["seller"])

        # ── Step 3: Upsert product ────────────────────────────
        product_id, is_new = upsert_product(
            session        = session,
            clean_product  = clean["product"],
            seller_id      = seller_id,
        )

        # ── Step 4: Get latest snapshot ───────────────────────
        previous = get_latest_snapshot(session, product_id)

        # ── Step 5: Change detection ──────────────────────────
        if not _has_changed(previous, clean["snapshot"]):
            logger.debug(
                f"Skipped snapshot — no change | "
                f"product_id={product_id} | "
                f"sku={clean['product']['noon_sku']}"
            )
            return {
                "status":   "skipped",
                "is_new":   is_new,
                "snapshot": False,
                "alerts":   0,
            }

        # ── Step 6: Insert snapshot ───────────────────────────
        insert_snapshot(session, clean["snapshot"], product_id)

        # ── Step 7: Alert detection ───────────────────────────
        alerts_created = check_and_create_alerts(
            session        = session,
            product_id     = product_id,
            clean_snapshot = clean["snapshot"],
            previous       = previous,
        )

        logger.debug(
            f"Saved | product_id={product_id} | "
            f"sku={clean['product']['noon_sku']} | "
            f"new={is_new} | alerts={alerts_created}"
        )

        return {
            "status":   "saved",
            "is_new":   is_new,
            "snapshot": True,
            "alerts":   alerts_created,
        }

    except Exception as e:
        logger.error(
            f"Unexpected error in save_product | "
            f"sku={clean.get('product', {}).get('noon_sku', 'unknown')} | "
            f"error={e}"
        )
        # Re-raise so the session in main.py can roll back
        raise