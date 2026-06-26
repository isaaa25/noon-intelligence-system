# ─── components/tables.py ────────────────────────────────────────────────────
# Styled dataframe rendering for Noon Intelligence dashboard.
#
# Pages never call st.dataframe() directly — they call a function here.
# This guarantees consistent column formatting, labels, and row highlighting
# across every page.
#
# Pattern:
#   render_alerts_table(df)         → Alerts page
#   render_ranking_table(df)        → Product Detail page
#   render_attention_table(df)      → Dashboard homepage
#   render_scrape_logs_table(df)    → System Health page
#
# FIX (critical): The original code called .drop(columns=[...]) on the
#   DataFrame BEFORE passing to .style.apply(). This caused a KeyError
#   crash because _highlight() referenced columns that no longer existed.
#
#   Correct pattern:
#     1. Keep ALL columns (including is_seen, is_client, alert_type) in the
#        DataFrame when creating the Styler.
#     2. Apply highlighting via .apply() — all columns available.
#     3. Hide internal columns from display using .hide(axis="columns").
#        Styler.hide() removes columns from the rendered output while keeping
#        them available inside .apply() functions.
#
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import streamlit as st


# ─── Private Helpers ─────────────────────────────────────────────────────────

def _fmt_price(val) -> str:
    """Formats a numeric price as 'AED 3,799'. Returns '—' for nulls."""
    try:
        return f"AED {float(val):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(val, direction: str = "auto") -> str:
    """
    Formats a percentage change with directional arrow.
    direction: "drop" forces ▼, "rise" forces ▲, "auto" reads the sign.
    Returns '—' for nulls.
    """
    try:
        v = float(val)
        if direction == "drop" or (direction == "auto" and v > 0):
            return f"▼ {v:.1f}%"
        elif direction == "rise" or (direction == "auto" and v < 0):
            return f"▲ {abs(v):.1f}%"
        return f"{v:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_datetime(val) -> str:
    """Formats a datetime as 'Jun 14, 2026 · 09:12 AM'."""
    try:
        if isinstance(val, str):
            val = pd.to_datetime(val)
        return val.strftime("%b %d, %Y · %I:%M %p")
    except Exception:
        return str(val)


def _fmt_stock(val: str) -> str:
    """Replaces raw stock_status values with readable dot + label strings."""
    mapping = {
        "in_stock"    : "● In Stock",
        "out_of_stock": "○ Out of Stock",
        "limited"     : "◑ Limited",
        "unknown"     : "— Unknown",
    }
    return mapping.get(str(val).lower(), str(val))


def _fmt_alert_type(val: str) -> str:
    """Human-readable alert type labels."""
    mapping = {
        "price_drop"    : "Price Drop",
        "price_increase": "Price Increase",
        "out_of_stock"  : "Out of Stock",
        "back_in_stock" : "Back in Stock",
        "new_competitor": "New Competitor",
    }
    return mapping.get(str(val).lower(), str(val).replace("_", " ").title())


# ─── 1. Alerts Table ─────────────────────────────────────────────────────────
def render_alerts_table(df: pd.DataFrame) -> None:
    """
    Renders the full alert feed on the Alerts page.

    Row highlighting:
        Unseen + price alert  → #FEF2F2  (light red  — critical)
        Unseen + stock alert  → #FFFBEB  (light amber — informational)
        Seen                  → #FFFFFF  (white       — acknowledged)

    FIX: is_seen and alert_type are kept in the DataFrame through .apply(),
         then hidden from display via .hide(axis="columns") — NOT .drop().
         Dropping before .apply() caused a KeyError crash.

    Expected df columns (from get_alerts()):
        alert_id, seller_name, product_name, alert_type,
        previous_value, current_value, change_pct,
        threshold_used, is_seen, triggered_at, is_client
    """
    if df.empty:
        st.info("No alerts match the current filter.")
        return

    display = df.copy()

    # ── Pre-format visible columns ───────────────────────────────────────────
    display["Alert Type"]     = display["alert_type"].apply(_fmt_alert_type)
    display["Previous Price"] = display["previous_value"].apply(_fmt_price)
    display["Current Price"]  = display["current_value"].apply(_fmt_price)
    display["Change"]         = display.apply(
        lambda r: _fmt_pct(r["change_pct"], direction="drop")
        if r["alert_type"] == "price_drop"
        else _fmt_pct(r["change_pct"], direction="rise")
        if r["alert_type"] == "price_increase"
        else "—",
        axis=1,
    )
    display["Triggered At"]   = display["triggered_at"].apply(_fmt_datetime)
    display["Seller"]         = display["seller_name"]
    display["Product"]        = display["product_name"]
    display["Status"]         = display["is_seen"].apply(
        lambda v: "Seen" if bool(v) else "Unseen"
    )

    # Columns shown in the table (visible to the user)
    cols_to_show = [
        "Seller", "Product", "Alert Type",
        "Previous Price", "Current Price", "Change",
        "Triggered At", "Status",
    ]
    # Internal columns needed by _highlight but hidden from display
    internal_cols = ["is_seen", "alert_type"]

    display = display[cols_to_show + internal_cols]

    # ── Row highlighting ─────────────────────────────────────────────────────
    # FIX: _highlight reads is_seen and alert_type which are still present
    #      in the DataFrame at this point. They get hidden after .apply().
    def _highlight(row):
        # bool() cast — PostgreSQL may return numpy.bool_
        if bool(row["is_seen"]):
            return ["background-color: #FFFFFF"] * len(row)
        if row["alert_type"] in ("price_drop", "price_increase"):
            return ["background-color: #FEF2F2"] * len(row)
        return ["background-color: #FFFBEB"] * len(row)

    styler = (
        display
        .style
        .apply(_highlight, axis=1)
        # FIX: .hide() removes columns from rendered output while keeping
        #      them available during .apply(). Never use .drop() before .apply().
        .hide(subset=internal_cols, axis="columns")
    )

    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
    )


# ─── 2. Ranking Table ────────────────────────────────────────────────────────
def render_ranking_table(df: pd.DataFrame) -> None:
    """
    Renders the price ranking table on the Product Detail page.
    Shows all sellers ranked cheapest to most expensive for one product.

    Row highlighting:
        Client row (is_client=True) → #EFF6FF  (light blue)
        All others                  → #FFFFFF

    FIX: is_client kept through .apply(), hidden with .hide() — not .drop().

    Expected df columns (from get_product_current_ranking()):
        rank, seller_name, current_price, original_price,
        discount_pct, stock_status, is_client
    """
    if df.empty:
        st.info("No ranking data available.")
        return

    display = df.copy()

    # ── Pre-format visible columns ───────────────────────────────────────────
    display["Rank"] = display["rank"].apply(
        lambda r: "🥇 1st" if r == 1
        else f"{r}{'nd' if r == 2 else 'rd' if r == 3 else 'th'}"
    )
    display["Seller"]         = display["seller_name"]
    display["Current Price"]  = display["current_price"].apply(_fmt_price)
    display["Original Price"] = display["original_price"].apply(_fmt_price)
    display["Discount"]       = display["discount_pct"].apply(
        lambda v: f"{float(v):.1f}% off"
        if pd.notna(v) and float(v) > 0 else "—"
    )
    display["Stock"]          = display["stock_status"].apply(_fmt_stock)

    cols_to_show = [
        "Rank", "Seller", "Current Price",
        "Original Price", "Discount", "Stock",
    ]
    internal_cols = ["is_client"]

    display = display[cols_to_show + internal_cols]

    # ── Row highlighting ─────────────────────────────────────────────────────
    def _highlight(row):
        # FIX: bool() cast for numpy.bool_ safety
        if bool(row["is_client"]):
            return ["background-color: #EFF6FF"] * len(row)
        return ["background-color: #FFFFFF"] * len(row)

    styler = (
        display
        .style
        .apply(_highlight, axis=1)
        # FIX: hide is_client from display without dropping it
        .hide(subset=internal_cols, axis="columns")
    )

    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
    )


# ─── 3. Products Requiring Attention Table ───────────────────────────────────
def render_attention_table(df: pd.DataFrame) -> None:
    """
    Renders the "Products Requiring Attention" table on the homepage.
    Action-oriented — every row implies a decision.

    No internal styling columns needed here — all rows get the same
    red tint, so no .hide() fix required for this table.

    Expected df columns (from get_products_requiring_attention()):
        product_name, client_price, cheapest_competitor_price,
        cheapest_competitor_name, gap_aed, gap_pct
    """
    if df.empty:
        st.success("✓ No products are currently being undercut.")
        return

    display = df.copy()

    display["Product"]             = display["product_name"]
    display["Your Price"]          = display["client_price"].apply(_fmt_price)
    display["Cheapest Competitor"] = display["cheapest_competitor_name"]
    display["Competitor Price"]    = display["cheapest_competitor_price"].apply(_fmt_price)
    display["Gap"]                 = display.apply(
        lambda r: f"Undercut by AED {abs(float(r['gap_aed'])):,.0f} ({float(r['gap_pct']):.1f}%)",
        axis=1,
    )

    cols_to_show = [
        "Product", "Your Price",
        "Cheapest Competitor", "Competitor Price", "Gap",
    ]
    display = display[cols_to_show]

    # All rows get red tint — every product here needs attention.
    # No internal columns needed so no .hide() required.
    def _highlight(row):
        return ["background-color: #FEF2F2"] * len(row)

    styler = display.style.apply(_highlight, axis=1)

    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
    )


# ─── 4. Scrape Logs Table ─────────────────────────────────────────────────────
def render_scrape_logs_table(df: pd.DataFrame) -> None:
    """
    Renders the scrape history table on the System Health page.
    Failed/partial runs get row highlighting.

    FIX: status kept through .apply(), hidden with .hide() — not .drop().

    Expected df columns (from get_scrape_logs()):
        id, keyword, pages_scraped, products_found, products_new,
        products_updated, alerts_triggered, errors,
        duration_secs, status, run_at
    """
    if df.empty:
        st.info("No scrape logs found.")
        return

    display = df.copy()

    display["Run At"]         = display["run_at"].apply(_fmt_datetime)
    display["Status"]         = display["status"].apply(
        lambda v: "✓ Success" if v == "success"
        else "⚠ Partial"  if v == "partial"
        else "✗ Failed"
    )
    display["Duration"]       = display["duration_secs"].apply(
        lambda v: f"{float(v):.1f}s" if pd.notna(v) else "—"
    )
    display["Pages"]          = display["pages_scraped"]
    display["Products Found"] = display["products_found"]
    display["New Products"]   = display["products_new"]
    display["Updated"]        = display["products_updated"]
    display["Alerts"]         = display["alerts_triggered"]
    display["Errors"]         = display["errors"]

    cols_to_show = [
        "Run At", "Status", "Duration", "Pages",
        "Products Found", "New Products", "Updated",
        "Alerts", "Errors",
    ]
    # Keep raw status for highlighting, hide from display
    internal_cols = ["status"]

    display = display[cols_to_show + internal_cols]

    # ── Row highlighting ─────────────────────────────────────────────────────
    # FIX: status still available here for _highlight, hidden after .apply()
    def _highlight(row):
        if row["status"] == "failed":
            return ["background-color: #FEF2F2"] * len(row)
        if row["status"] == "partial":
            return ["background-color: #FFFBEB"] * len(row)
        return ["background-color: #FFFFFF"] * len(row)

    styler = (
        display
        .style
        .apply(_highlight, axis=1)
        # FIX: hide raw status column, the formatted "Status" column stays
        .hide(subset=internal_cols, axis="columns")
    )

    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
    )