"""
main.py

The sole entry point for Price Intel.
Parse CLI args → initialise resources → run the requested mode.

ARCHITECTURE CHANGE FROM v1:
  v1: main.py owned the browser.
      It launched Patchright, created a fresh browser context per keyword,
      passed that context to scrapers, and tore everything down manually.

  v2: main.py is a pure orchestrator.
      It creates ProxyManager and SessionManager once at startup.
      The browser is completely invisible here — it opens and closes
      inside SessionManager.initialise() / bootstrap_session() automatically.
      Scrapers receive session_manager, not a browser context.

RESOURCE HIERARCHY:
  ProxyManager    → UAE residential sticky proxy pool (IPRoyal)
  SessionManager  → browser bootstrap, Akamai cookies, JWT lifecycle,
                    disk persistence, health checks, re-bootstrap on block
  SessionLocal    → SQLAlchemy database session (unchanged from v1)

  All three live for the entire run duration.
  Nothing is created or destroyed per keyword or per seller.

TRANSACTION BOUNDARY (unchanged from v1):
  session.commit() is called in main.py ONLY.
  loader functions never commit — they only write to the session.
  One commit covers all products for one keyword run or one store run.
  On any exception, session.rollback() reverts the entire keyword/store run.

MODES:
  discovery → search_scraper across all SEARCH_KEYWORDS in config
  store     → store_scraper across all is_tracked sellers in database
  full      → discovery then store (designed for the daily cron job)
"""

import asyncio
import argparse
import logging
import time

from sqlalchemy import select

from config import settings
from pipeline.models import SessionLocal, Seller, init_db
from pipeline.cleaner import clean_product
from pipeline.loader import save_product, log_scrape_run
from scraper.proxy_manager import ProxyManager
from scraper.session_manager import SessionManager
from scraper.utils import random_delay
from scraper.search_scraper import scrape_search
from scraper.store_scraper import scrape_store


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


# ─────────────────────────────────────────────────────────────────────────────
# COUNTER HELPERS  (unchanged from v1)
# ─────────────────────────────────────────────────────────────────────────────

def _empty_counters() -> dict:
    """
    Returns a fresh counters dict for one keyword or store run.
    Aggregated across all products in that run then passed to log_scrape_run.
    """
    return {
        "products_found":   0,
        "products_new":     0,
        "products_updated": 0,
        "alerts_triggered": 0,
        "errors":           0,
        "error_details":    None,
    }


def _update_counters(counters: dict, result: dict) -> None:
    """
    Updates counters in-place from save_product return value.
    Called once per product in the assembly line loop.
    """
    status = result.get("status")

    if status == "rejected":
        counters["errors"] += 1

    elif status == "saved":
        if result.get("is_new"):
            counters["products_new"] += 1
        else:
            counters["products_updated"] += 1
        counters["alerts_triggered"] += result.get("alerts", 0)


# ─────────────────────────────────────────────────────────────────────────────
# ASSEMBLY LINE  (unchanged from v1)
# ─────────────────────────────────────────────────────────────────────────────

def _process_products(
    session:      object,
    raw_products: list[dict],
    counters:     dict,
) -> None:
    """
    Runs each raw product through clean → save.
    Updates counters in-place. Does not commit — caller owns the transaction.

    Fatal database exceptions bubble up to the orchestrator for rollback.
    Individual product failures are absorbed by cleaner/loader and
    counted as errors without killing the entire keyword run.
    """
    for raw in raw_products:
        clean  = clean_product(raw)
        result = save_product(session, clean)
        _update_counters(counters, result)


# ─────────────────────────────────────────────────────────────────────────────
# DISCOVERY MODE
# ─────────────────────────────────────────────────────────────────────────────

async def run_discovery(
    session_manager: SessionManager,
    session:         object,
) -> None:
    """
    Runs search_scraper for every keyword in SEARCH_KEYWORDS.

    What this achieves:
      - Finds all products listed for each keyword on noon.
      - Captures the client's products AND all competitor products
        in a single search run per keyword.
      - Populates sellers table with partner IDs for store monitoring.
      - Generates price_alerts via loader for any first-seen or changed prices.

    Architecture change from v1:
      v1: created browser context per keyword, passed to scraper.
      v2: session_manager is shared across all keywords.
          scrape_search() calls session_manager.ensure_valid() internally
          before every API request. JWT refresh and re-bootstrap happen
          transparently without any intervention from main.py.

    Transaction boundary:
      One commit per keyword. All products for that keyword commit together.
      If any keyword fails, only that keyword rolls back.
    """
    keywords = settings.SEARCH_KEYWORDS

    if not keywords:
        logger.warning("No SEARCH_KEYWORDS in config. Nothing to scrape.")
        return

    logger.info(f"Discovery mode | {len(keywords)} keyword(s) to process.")

    for keyword in keywords:
        logger.info(f"─── Keyword: '{keyword}' " + "─" * 40)
        start_time = time.time()
        counters   = _empty_counters()
        counters["keyword"] = keyword

        try:
            raw_products = await scrape_search(
                session_manager = session_manager,
                keyword         = keyword,
                pages           = settings.PAGES_PER_KEYWORD,
                sort_by         = "recommended",
            )

            counters["products_found"] = len(raw_products)
            logger.info(f"[{keyword}] {len(raw_products)} products scraped.")

            # ── Clean → save ──────────────────────────────────────────────
            _process_products(session, raw_products, counters)

            # ── Commit this keyword run ───────────────────────────────────
            counters["pages_scraped"] = settings.PAGES_PER_KEYWORD
            counters["duration_secs"] = round(time.time() - start_time, 2)
            log_scrape_run(session, counters)
            session.commit()

            logger.info(
                f"[{keyword}] Done | "
                f"new={counters['products_new']} | "
                f"updated={counters['products_updated']} | "
                f"alerts={counters['alerts_triggered']} | "
                f"errors={counters['errors']} | "
                f"{counters['duration_secs']}s"
            )

        except Exception as exc:
            logger.error(f"[{keyword}] Run failed: {exc}", exc_info=True)
            session.rollback()

            counters["error_details"] = str(exc)
            counters["duration_secs"] = round(time.time() - start_time, 2)
            log_scrape_run(session, counters)
            session.commit()   # commit the failure log

        # ── Delay between keywords ────────────────────────────────────────
        if keyword != keywords[-1]:
            await random_delay()


# ─────────────────────────────────────────────────────────────────────────────
# STORE MONITORING MODE
# ─────────────────────────────────────────────────────────────────────────────

async def run_store_monitoring(
    session_manager: SessionManager,
    session:         object,
) -> None:
    """
    Runs store_scraper for every tracked seller in the database.

    What this achieves:
      - Deep-scrapes each competitor's full store catalogue.
      - Captures price changes on products not yet found via keyword search.
      - For the client's own store: captures the complete inventory
        (no keyword filter) for accurate self-vs-market comparison.
      - Generates price_alerts for any stock or price changes.

    Architecture change from v1:
      v1: created browser context per seller, had a bug where context
          was created twice (first one leaked silently every single run).
          max_pages was passed in from main.py before store size was known.

      v2: session_manager is shared. No context creation here at all.
          max_pages removed entirely — store_scraper decides it internally
          after reading nbHits from page 1 (small stores get full coverage,
          large stores are capped at STORE_PAGES_LARGE automatically).

    Client vs competitor logic:
      Client store  (is_client=True)  → keywords=None → capture everything
      Competitor stores               → keywords=SEARCH_KEYWORDS → filter

    Transaction boundary:
      One commit per seller. Consistent with discovery mode.
    """
    tracked_sellers = session.scalars(
        select(Seller)
        .where(Seller.is_tracked == True)
        .where(Seller.store_slug.is_not(None))
    ).all()

    if not tracked_sellers:
        logger.warning(
            "No tracked sellers with store_slug found. "
            "Run discovery mode first to populate sellers, "
            "then set is_tracked=True on the ones you want to monitor."
        )
        return

    keywords = settings.SEARCH_KEYWORDS
    logger.info(
        f"Store monitoring | {len(tracked_sellers)} tracked seller(s)."
    )

    for seller in tracked_sellers:
        logger.info(
            f"─── Store: '{seller.store_name}' ({seller.store_slug}) "
            + "─" * 30
        )
        start_time = time.time()
        counters   = _empty_counters()
        counters["keyword"] = f"store:{seller.store_name}"

        try:
            raw_products = await scrape_store(
                session_manager = session_manager,
                partner_id      = seller.store_slug,

                # Client's own store: no filter → full inventory snapshot.
                # Competitor stores: filter to tracked keywords only.
                # This prevents storing thousands of irrelevant products
                # from large multi-category competitor stores.
                keywords        = None if seller.is_client else keywords,

                sort_by         = "recommended",
                # "recommended" surfaces best-sellers first.
                # For large stores where we cap at STORE_PAGES_LARGE,
                # this ensures we capture the most commercially relevant
                # products within our page budget.
            )

            counters["products_found"] = len(raw_products)
            logger.info(
                f"[{seller.store_name}] {len(raw_products)} products scraped."
            )

            # ── Clean → save ──────────────────────────────────────────────
            _process_products(session, raw_products, counters)

            # ── Commit this seller run ────────────────────────────────────
            counters["duration_secs"] = round(time.time() - start_time, 2)
            log_scrape_run(session, counters)
            session.commit()

            logger.info(
                f"[{seller.store_name}] Done | "
                f"new={counters['products_new']} | "
                f"updated={counters['products_updated']} | "
                f"alerts={counters['alerts_triggered']} | "
                f"errors={counters['errors']} | "
                f"{counters['duration_secs']}s"
            )

        except Exception as exc:
            logger.error(
                f"[{seller.store_name}] Run failed: {exc}", exc_info=True
            )
            session.rollback()

            counters["error_details"] = str(exc)
            counters["duration_secs"] = round(time.time() - start_time, 2)
            log_scrape_run(session, counters)
            session.commit()

        if seller != tracked_sellers[-1]:
            await random_delay()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def main(mode: str) -> None:
    """
    Creates all global resources and delegates to the appropriate mode.

    Resource lifecycle (simplified from v1):
      v1: init database, fetch headers, launch browser, run mode,
          close browser, close playwright, close database session.
      v2: init database, create proxy+session managers, initialise session,
          run mode, close database session.
          Browser lifecycle is invisible — handled inside SessionManager.

    The session_manager.initialise() call does one of three things:
      A. Loads valid session from disk → refreshes JWT → ready in <1s
      B. Session stale on disk → browser opens, harvests cookies, closes
      C. No session on disk → browser opens, harvests cookies, closes
    In cases B and C, the browser window opens briefly then closes automatically.
    """
    logger.info(f"Price Intel starting | mode={mode}")

    # ── Database ──────────────────────────────────────────────────────────
    init_db()
    logger.info("Database tables verified.")

    # ── Stealth session layer ─────────────────────────────────────────────
    proxy_manager   = ProxyManager()
    session_manager = SessionManager(proxy_manager)

    logger.info("Initialising session (load from disk or browser bootstrap)...")
    await session_manager.initialise()

    status = session_manager.get_status()
    logger.info(
        f"Session ready | "
        f"age={status.get('bootstrap_age_h')}h | "
        f"jwt_ttl={status.get('jwt_expires_in_s')}s | "
        f"requests_so_far={status.get('request_count')}"
    )

    # ── Database session ──────────────────────────────────────────────────
    session = SessionLocal()

    try:
        if mode == "discovery":
            await run_discovery(session_manager, session)

        elif mode == "store":
            await run_store_monitoring(session_manager, session)

        elif mode == "full":
            await run_discovery(session_manager, session)
            logger.info("Discovery complete. Starting store monitoring.")
            await run_store_monitoring(session_manager, session)

        logger.info(f"Price Intel finished | mode={mode}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user. Rolling back and shutting down.")
        session.rollback()

    except Exception as exc:
        logger.error(f"Fatal error in main: {exc}", exc_info=True)
        session.rollback()
        raise

    finally:
        # Only the database session needs explicit cleanup here.
        # Browser was already closed inside bootstrap_session().
        # ProxyManager and SessionManager hold no OS resources.
        session.close()
        logger.info("Database session closed. Goodbye.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Price Intel — Noon Competitor Price Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --mode discovery   "
            "# search keywords → find products and sellers\n"
            "  python main.py --mode store       "
            "# scrape tracked seller store catalogues\n"
            "  python main.py --mode full        "
            "# discovery then store (use for daily cron)\n"
        ),
    )

    parser.add_argument(
        "--mode",
        choices=["discovery", "store", "full"],
        default="discovery",
        help="Run mode: discovery | store | full (default: discovery)",
    )

    args = parser.parse_args()
    asyncio.run(main(args.mode))