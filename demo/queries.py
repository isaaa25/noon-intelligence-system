# ─── queries.py ──────────────────────────────────────────────────────────────
# Data layer for Noon Intelligence Dashboard.
# All SQL lives here. Pages never touch the database directly.
#
# Return convention:
#   - Every read function returns list[dict]
#   - Pages convert to pd.DataFrame() as needed
#   - Write functions (mark_alert_seen) return None
#
# DEMO ASSUMPTION:
#   Products are matched across sellers by normalised name (LOWER + TRIM).
#   In production this should use a canonical master_product_id.
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy import text
from db import get_db

# Threshold used to classify client's competitive position.
# "Competitive"  = client price within this % above cheapest competitor.
# "Overpriced"   = client price more than this % above cheapest competitor.
COMPETITIVE_THRESHOLD_PCT = 3.0


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — UTILITY
# Shared helpers used across multiple pages.
# ═════════════════════════════════════════════════════════════════════════════

def get_all_sellers() -> list[dict]:
    """
    All sellers in the system.
    Used to populate filter dropdowns across pages.
    Returns: id, store_name, is_client, is_tracked
    """
    sql = text("""
        SELECT
            id,
            store_name,
            is_client,
            is_tracked
        FROM sellers
        ORDER BY is_client DESC, store_name ASC
    """)
    with get_db() as db:
        rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_all_product_names() -> list[str]:
    """
    Distinct product names tracked in the system.
    Used to populate the product selector dropdown on
    Product Detail and Market Position pages.

    DEMO ASSUMPTION: same name = same product across sellers.
    """
    sql = text("""
        SELECT DISTINCT TRIM(name) AS name
        FROM products
        WHERE is_active = true
        ORDER BY name ASC
    """)
    with get_db() as db:
        rows = db.execute(sql).mappings().all()
    return [r["name"] for r in rows]


def get_last_scrape_info() -> dict | None:
    """
    Most recent scrape log entry.
    Powers the "Data as of..." timestamp shown on every page.
    Returns: run_at, status, alerts_triggered, duration_secs
    Returns None if no scrape logs exist.
    """
    sql = text("""
        SELECT
            run_at,
            status,
            alerts_triggered,
            duration_secs
        FROM scrape_logs
        ORDER BY run_at DESC
        LIMIT 1
    """)
    with get_db() as db:
        row = db.execute(sql).mappings().first()
    return dict(row) if row else None


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — DASHBOARD PAGE
# Powers the command-centre homepage.
# ═════════════════════════════════════════════════════════════════════════════

def get_active_product_count() -> int:
    """
    Number of active products belonging to the client seller.
    """
    sql = text("""
        SELECT COUNT(p.id) AS cnt
        FROM products p
        JOIN sellers s ON s.id = p.seller_id
        WHERE s.is_client = true
          AND p.is_active  = true
    """)
    with get_db() as db:
        row = db.execute(sql).mappings().first()
    return row["cnt"] if row else 0


def get_unseen_alert_count() -> int:
    """
    Total number of alerts not yet marked as seen.
    """
    sql = text("""
        SELECT COUNT(id) AS cnt
        FROM price_alerts
        WHERE is_seen = false
    """)
    with get_db() as db:
        row = db.execute(sql).mappings().first()
    return row["cnt"] if row else 0


def get_products_losing_position_count() -> int:
    """
    Number of client products where at least one competitor
    currently has a strictly lower price.

    Uses a CTE to first isolate the single latest snapshot per
    product (avoiding duplicates when MAX scraped_at returns
    multiple rows at the same timestamp), then compares.

    DEMO ASSUMPTION: products matched by normalised name.
    """
    sql = text("""
        WITH latest_snapshots AS (
            -- One row per product: the most recent snapshot only.
            SELECT DISTINCT ON (product_id)
                product_id,
                current_price,
                stock_status,
                scraped_at
            FROM price_snapshots
            ORDER BY product_id, scraped_at DESC
        ),
        client_latest AS (
            -- Latest price for each CLIENT product.
            SELECT
                p.id            AS product_id,
                LOWER(TRIM(p.name)) AS norm_name,
                ls.current_price,
                ls.stock_status
            FROM latest_snapshots ls
            JOIN products p  ON p.id  = ls.product_id
            JOIN sellers  s  ON s.id  = p.seller_id
            WHERE s.is_client = true
              AND p.is_active  = true
        ),
        competitor_min AS (
            -- Lowest price any competitor offers per normalised product name.
            SELECT
                LOWER(TRIM(p.name)) AS norm_name,
                MIN(ls.current_price) AS min_price
            FROM latest_snapshots ls
            JOIN products p ON p.id  = ls.product_id
            JOIN sellers  s ON s.id  = p.seller_id
            WHERE s.is_client   = false
              AND ls.stock_status != 'out_of_stock'
            GROUP BY LOWER(TRIM(p.name))
        )
        SELECT COUNT(*) AS cnt
        FROM client_latest cl
        JOIN competitor_min cm ON cm.norm_name = cl.norm_name
        WHERE cm.min_price < cl.current_price
    """)
    with get_db() as db:
        row = db.execute(sql).mappings().first()
    return row["cnt"] if row else 0


def get_competitor_changes_count() -> int:
    """
    Total price-change alerts triggered by competitors
    (excludes client's own products).
    Shown as "Competitor Changes" on the dashboard.

    Note: demo data has all alerts at the same timestamp,
    so we count all competitor alerts rather than filtering
    to a single day — avoids showing 0 in the demo.
    """
    sql = text("""
        SELECT COUNT(pa.id) AS cnt
        FROM price_alerts pa
        JOIN products p ON p.id  = pa.product_id
        JOIN sellers  s ON s.id  = p.seller_id
        WHERE s.is_client = false
          AND pa.alert_type IN ('price_drop', 'price_increase')
    """)
    with get_db() as db:
        row = db.execute(sql).mappings().first()
    return row["cnt"] if row else 0


def get_recent_market_events(limit: int = 10) -> list[dict]:
    """
    Latest price alerts across all sellers, most recent first.
    Powers the "Recent Activity" feed on the homepage.

    Returns:
        seller_name, product_name, alert_type,
        previous_value, current_value, change_pct, triggered_at, is_client
    """
    sql = text("""
        SELECT
            s.store_name        AS seller_name,
            p.name              AS product_name,
            pa.alert_type,
            pa.previous_value,
            pa.current_value,
            pa.change_pct,
            pa.triggered_at,
            s.is_client
        FROM price_alerts pa
        JOIN products p ON p.id = pa.product_id
        JOIN sellers  s ON s.id = p.seller_id
        ORDER BY pa.triggered_at DESC, pa.id DESC
        LIMIT :limit
    """)
    with get_db() as db:
        rows = db.execute(sql, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]


def get_competitive_position_summary() -> dict:
    """
    Classifies each client product as Cheapest / Competitive / Overpriced
    by comparing its latest price against the lowest competitor price
    for the same product name.

    Thresholds (defined at top of file):
        Cheapest     → client price <= competitor min
        Competitive  → client price within COMPETITIVE_THRESHOLD_PCT % above min
        Overpriced   → client price more than COMPETITIVE_THRESHOLD_PCT % above min

    Returns: {"cheapest": int, "competitive": int, "overpriced": int}
    """
    sql = text("""
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (product_id)
                product_id,
                current_price,
                stock_status
            FROM price_snapshots
            ORDER BY product_id, scraped_at DESC
        ),
        client_latest AS (
            SELECT
                LOWER(TRIM(p.name)) AS norm_name,
                ls.current_price    AS client_price
            FROM latest_snapshots ls
            JOIN products p ON p.id  = ls.product_id
            JOIN sellers  s ON s.id  = p.seller_id
            WHERE s.is_client = true
              AND p.is_active  = true
        ),
        competitor_min AS (
            SELECT
                LOWER(TRIM(p.name)) AS norm_name,
                MIN(ls.current_price) AS min_price
            FROM latest_snapshots ls
            JOIN products p ON p.id  = ls.product_id
            JOIN sellers  s ON s.id  = p.seller_id
            WHERE s.is_client   = false
              AND ls.stock_status != 'out_of_stock'
            GROUP BY LOWER(TRIM(p.name))
        ),
        classified AS (
            SELECT
                CASE
                    WHEN cl.client_price <= cm.min_price
                        THEN 'cheapest'
                    WHEN cl.client_price <= cm.min_price * (1 + :threshold / 100.0)
                        THEN 'competitive'
                    ELSE 'overpriced'
                END AS position
            FROM client_latest cl
            JOIN competitor_min cm ON cm.norm_name = cl.norm_name
        )
        SELECT
            COUNT(*) FILTER (WHERE position = 'cheapest')    AS cheapest,
            COUNT(*) FILTER (WHERE position = 'competitive') AS competitive,
            COUNT(*) FILTER (WHERE position = 'overpriced')  AS overpriced
        FROM classified
    """)
    with get_db() as db:
        row = db.execute(
            sql, {"threshold": COMPETITIVE_THRESHOLD_PCT}
        ).mappings().first()
    if not row:
        return {"cheapest": 0, "competitive": 0, "overpriced": 0}
    return dict(row)


def get_products_requiring_attention(limit: int = 5) -> list[dict]:
    """
    Client products currently being undercut by at least one competitor.
    Sorted by absolute price gap descending (worst situation first).

    Returns:
        product_name, client_price, cheapest_competitor_price,
        cheapest_competitor_name, gap_aed, gap_pct
    """
    sql = text("""
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (product_id)
                product_id,
                current_price,
                stock_status
            FROM price_snapshots
            ORDER BY product_id, scraped_at DESC
        ),
        client_latest AS (
            SELECT
                p.name              AS product_name,
                LOWER(TRIM(p.name)) AS norm_name,
                ls.current_price    AS client_price
            FROM latest_snapshots ls
            JOIN products p ON p.id  = ls.product_id
            JOIN sellers  s ON s.id  = p.seller_id
            WHERE s.is_client = true
              AND p.is_active  = true
        ),
        competitor_prices AS (
            SELECT
                LOWER(TRIM(p.name)) AS norm_name,
                s.store_name        AS seller_name,
                ls.current_price    AS comp_price
            FROM latest_snapshots ls
            JOIN products p ON p.id  = ls.product_id
            JOIN sellers  s ON s.id  = p.seller_id
            WHERE s.is_client   = false
              AND ls.stock_status != 'out_of_stock'
        ),
        cheapest_competitor AS (
            -- For each product, find the single cheapest competitor.
            -- DISTINCT ON ensures one row per product even if two
            -- competitors tie on price.
            SELECT DISTINCT ON (norm_name)
                norm_name,
                seller_name AS cheapest_seller,
                comp_price  AS cheapest_price
            FROM competitor_prices
            ORDER BY norm_name, comp_price ASC
        )
        SELECT
            cl.product_name,
            cl.client_price,
            cc.cheapest_price           AS cheapest_competitor_price,
            cc.cheapest_seller          AS cheapest_competitor_name,
            ROUND(cl.client_price - cc.cheapest_price, 2)
                                        AS gap_aed,
            ROUND(
                (cl.client_price - cc.cheapest_price)
                / cc.cheapest_price * 100
            , 2)                        AS gap_pct
        FROM client_latest cl
        JOIN cheapest_competitor cc ON cc.norm_name = cl.norm_name
        WHERE cc.cheapest_price < cl.client_price
        ORDER BY gap_aed DESC
        LIMIT :limit
    """)
    with get_db() as db:
        rows = db.execute(sql, {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]

# ─── ADD THIS FUNCTION TO queries.py ─────────────────────────────────────────
# Place it in SECTION 2 (Dashboard Page), after get_competitor_changes_count()
# ─────────────────────────────────────────────────────────────────────────────

def get_alerts_per_day() -> list[dict]:
    """
    Total alerts triggered per calendar day, across all sellers.
    Powers the "Competitor Activity" bar chart on the homepage.

    Deliberately uses alert trigger date (not scrape date) so the chart
    reflects actual market events, not scraper run frequency.
    These are two different stories — homepage tells the market story.

    Returns:
        alert_date : date   — one row per day that had at least one alert
        alert_count: int    — total alerts triggered on that day
    """
    sql = text("""
        SELECT
            DATE(triggered_at AT TIME ZONE 'UTC') AS alert_date,
            COUNT(*)                               AS alert_count
        FROM price_alerts
        GROUP BY DATE(triggered_at AT TIME ZONE 'UTC')
        ORDER BY alert_date ASC
    """)
    with get_db() as db:
        rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_seller_competitive_summary() -> list[dict]:
    """
    For each seller, count how many products they are currently cheapest on.
    Powers the "Seller Competitive Summary" table on the homepage.

    Uses the same latest-snapshot-per-product logic as other queries.
    A seller "wins" a product if their current price equals the minimum
    price across all sellers for that normalised product name.

    Returns:
        store_name   : str
        is_client    : bool
        leading_on   : int  — number of products where this seller is cheapest
    """
    sql = text("""
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (product_id)
                product_id,
                current_price,
                stock_status
            FROM price_snapshots
            ORDER BY product_id, scraped_at DESC
        ),
        product_min AS (
            -- Cheapest price per normalised product name across all sellers
            SELECT
                LOWER(TRIM(p.name)) AS norm_name,
                MIN(ls.current_price) AS min_price
            FROM latest_snapshots ls
            JOIN products p ON p.id = ls.product_id
            WHERE ls.stock_status != 'out_of_stock'
            GROUP BY LOWER(TRIM(p.name))
        ),
        seller_wins AS (
            -- Count products where this seller matches the minimum price
            SELECT
                s.store_name,
                s.is_client,
                COUNT(*) AS leading_on
            FROM latest_snapshots ls
            JOIN products p  ON p.id  = ls.product_id
            JOIN sellers  s  ON s.id  = p.seller_id
            JOIN product_min pm ON pm.norm_name = LOWER(TRIM(p.name))
            WHERE ls.current_price = pm.min_price
              AND ls.stock_status  != 'out_of_stock'
            GROUP BY s.store_name, s.is_client
        )
        SELECT
            s.store_name,
            s.is_client,
            COALESCE(sw.leading_on, 0) AS leading_on
        FROM sellers s
        LEFT JOIN seller_wins sw ON sw.store_name = s.store_name
        WHERE s.is_tracked = true
        ORDER BY sw.leading_on DESC NULLS LAST, s.store_name ASC
    """)
    with get_db() as db:
        rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ALERTS PAGE
# ═════════════════════════════════════════════════════════════════════════════

def get_alerts(
    alert_type: str | None = None,
    seller_id:  int | None = None,
    is_seen:    bool | None = None,
) -> list[dict]:
    """
    Full alert feed with optional filters.
    All three filters are optional and combinable.

    Args:
        alert_type : one of 'price_drop', 'price_increase',
                     'out_of_stock', 'back_in_stock', 'new_competitor'
                     or None for all types.
        seller_id  : filter to one seller, or None for all.
        is_seen    : True = seen only, False = unseen only, None = all.

    Returns:
        alert_id, seller_name, product_name, alert_type,
        previous_value, current_value, change_pct,
        threshold_used, is_seen, triggered_at, is_client
    """
    # Build WHERE clauses dynamically to avoid messy string concat.
    filters = []
    params: dict = {}

    if alert_type is not None:
        filters.append("pa.alert_type = :alert_type")
        params["alert_type"] = alert_type

    if seller_id is not None:
        filters.append("s.id = :seller_id")
        params["seller_id"] = seller_id

    if is_seen is not None:
        filters.append("pa.is_seen = :is_seen")
        params["is_seen"] = is_seen

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    sql = text(f"""
        SELECT
            pa.id               AS alert_id,
            s.store_name        AS seller_name,
            p.name              AS product_name,
            pa.alert_type,
            pa.previous_value,
            pa.current_value,
            pa.change_pct,
            pa.threshold_used,
            pa.is_seen,
            pa.triggered_at,
            s.is_client
        FROM price_alerts pa
        JOIN products p ON p.id = pa.product_id
        JOIN sellers  s ON s.id = p.seller_id
        {where_clause}
        ORDER BY pa.triggered_at DESC, pa.id DESC
    """)
    with get_db() as db:
        rows = db.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


def get_alerts_summary() -> dict:
    """
    Aggregate counts for the summary cards at the top of the Alerts page.
    Single query using conditional COUNT to avoid multiple round trips.

    Returns:
        total_unseen, unseen_price_drops, unseen_stock_events
    """
    sql = text("""
        SELECT
            COUNT(*)
                FILTER (WHERE is_seen = false)
                AS total_unseen,
            COUNT(*)
                FILTER (WHERE is_seen = false
                          AND alert_type IN ('price_drop', 'price_increase'))
                AS unseen_price_changes,
            COUNT(*)
                FILTER (WHERE is_seen = false
                          AND alert_type IN ('out_of_stock', 'back_in_stock'))
                AS unseen_stock_events
        FROM price_alerts
    """)
    with get_db() as db:
        row = db.execute(sql).mappings().first()
    if not row:
        return {
            "total_unseen": 0,
            "unseen_price_changes": 0,
            "unseen_stock_events": 0,
        }
    return dict(row)


def mark_alert_seen(alert_id: int) -> None:
    """
    Mark a single alert as seen.
    Called when user clicks 'Mark as seen' on an individual alert row.
    """
    sql = text("""
        UPDATE price_alerts
        SET is_seen = true
        WHERE id = :alert_id
    """)
    with get_db() as db:
        db.execute(sql, {"alert_id": alert_id})
        db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — PRODUCT DETAIL PAGE
# ═════════════════════════════════════════════════════════════════════════════

def get_price_history(product_name: str) -> list[dict]:
    """
    Full price history for one product across ALL sellers.
    Powers the hero line chart on the Product Detail page.

    Matches products by normalised name (LOWER + TRIM).
    Returns one row per (seller, date) combination.

    Returns:
        scraped_at, seller_name, current_price,
        stock_status, is_client
    """
    sql = text("""
        SELECT
            ps.scraped_at,
            s.store_name    AS seller_name,
            ps.current_price,
            ps.stock_status,
            s.is_client
        FROM price_snapshots ps
        JOIN products p ON p.id = ps.product_id
        JOIN sellers  s ON s.id = p.seller_id
        WHERE LOWER(TRIM(p.name)) = LOWER(TRIM(:product_name))
        ORDER BY ps.scraped_at ASC, s.store_name ASC
    """)
    with get_db() as db:
        rows = db.execute(sql, {"product_name": product_name}).mappings().all()
    return [dict(r) for r in rows]


def get_product_current_ranking(product_name: str) -> list[dict]:
    """
    Current price ranking for one product across all sellers.
    "Current" = the single most recent snapshot per seller.

    Uses DISTINCT ON to guarantee exactly one row per seller
    even when multiple snapshots share the same scraped_at.

    Returns rows ordered by current_price ASC (rank 1 = cheapest).

    Returns:
        rank, seller_name, current_price, original_price,
        discount_pct, stock_status, is_client
    """
    sql = text("""
        WITH latest_per_seller AS (
            SELECT DISTINCT ON (p.seller_id)
                s.store_name        AS seller_name,
                ps.current_price,
                ps.original_price,
                ps.discount_pct,
                ps.stock_status,
                s.is_client
            FROM price_snapshots ps
            JOIN products p ON p.id = ps.product_id
            JOIN sellers  s ON s.id = p.seller_id
            WHERE LOWER(TRIM(p.name)) = LOWER(TRIM(:product_name))
            ORDER BY p.seller_id, ps.scraped_at DESC
        )
        SELECT
            RANK() OVER (ORDER BY current_price ASC) AS rank,
            seller_name,
            current_price,
            original_price,
            discount_pct,
            stock_status,
            is_client
        FROM latest_per_seller
        ORDER BY current_price ASC
    """)
    with get_db() as db:
        rows = db.execute(
            sql, {"product_name": product_name}
        ).mappings().all()
    return [dict(r) for r in rows]


def get_product_recent_alerts(
    product_name: str,
    limit: int = 10
) -> list[dict]:
    """
    Recent alerts for one specific product across all sellers.
    Shown in the bottom section of the Product Detail page.

    Returns:
        seller_name, alert_type, previous_value,
        current_value, change_pct, triggered_at, is_seen
    """
    sql = text("""
        SELECT
            s.store_name    AS seller_name,
            pa.alert_type,
            pa.previous_value,
            pa.current_value,
            pa.change_pct,
            pa.triggered_at,
            pa.is_seen
        FROM price_alerts pa
        JOIN products p ON p.id = pa.product_id
        JOIN sellers  s ON s.id = p.seller_id
        WHERE LOWER(TRIM(p.name)) = LOWER(TRIM(:product_name))
        ORDER BY pa.triggered_at DESC, pa.id DESC
        LIMIT :limit
    """)
    with get_db() as db:
        rows = db.execute(
            sql, {"product_name": product_name, "limit": limit}
        ).mappings().all()
    return [dict(r) for r in rows]


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — MARKET POSITION PAGE
# ═════════════════════════════════════════════════════════════════════════════

def get_market_position_data() -> list[dict]:
    """
    Latest price for every (product, seller) combination.
    Pages pivot this with pd.DataFrame.pivot() — keeping SQL simple.

    Returns:
        product_name, seller_name, current_price,
        stock_status, is_client
    """
    sql = text("""
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (product_id)
                product_id,
                current_price,
                stock_status
            FROM price_snapshots
            ORDER BY product_id, scraped_at DESC
        )
        SELECT
            p.name          AS product_name,
            s.store_name    AS seller_name,
            ls.current_price,
            ls.stock_status,
            s.is_client
        FROM latest_snapshots ls
        JOIN products p ON p.id = ls.product_id
        JOIN sellers  s ON s.id = p.seller_id
        ORDER BY p.name ASC, ls.current_price ASC
    """)
    with get_db() as db:
        rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_market_position_summary() -> dict:
    """
    Aggregate competitive position counts across ALL client products.
    Same classification logic as get_competitive_position_summary()
    on the dashboard — reused here for the Market Position page cards.

    Returns: {"cheapest": int, "competitive": int, "overpriced": int}
    """
    # Reuse the same logic — single source of truth.
    return get_competitive_position_summary()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SYSTEM HEALTH PAGE
# ═════════════════════════════════════════════════════════════════════════════

def get_scrape_logs() -> list[dict]:
    """
    All scrape log entries, most recent first.
    Displayed as a table on the System Health page.

    Returns:
        id, keyword, pages_scraped, products_found, products_new,
        products_updated, alerts_triggered, errors,
        duration_secs, status, run_at
    """
    sql = text("""
        SELECT
            id,
            keyword,
            pages_scraped,
            products_found,
            products_new,
            products_updated,
            alerts_triggered,
            errors,
            duration_secs,
            status,
            run_at
        FROM scrape_logs
        ORDER BY run_at DESC
    """)
    with get_db() as db:
        rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_system_health_summary() -> dict:
    """
    Aggregate statistics across all scrape runs.
    Powers the KPI cards at the top of the System Health page.

    Returns:
        total_runs, successful_runs, failed_runs,
        total_alerts_triggered, total_products_updated,
        avg_duration_secs
    """
    sql = text("""
        SELECT
            COUNT(*)                                        AS total_runs,
            COUNT(*) FILTER (WHERE status = 'success')     AS successful_runs,
            COUNT(*) FILTER (WHERE status = 'failed')      AS failed_runs,
            SUM(alerts_triggered)                          AS total_alerts_triggered,
            SUM(products_updated)                          AS total_products_updated,
            ROUND(AVG(duration_secs), 2)                   AS avg_duration_secs
        FROM scrape_logs
    """)
    with get_db() as db:
        row = db.execute(sql).mappings().first()
    if not row:
        return {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_alerts_triggered": 0,
            "total_products_updated": 0,
            "avg_duration_secs": 0,
        }
    return dict(row)