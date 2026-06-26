# ─── views/market_position.py ────────────────────────────────────────────────
# Market Position page — full competitive grid across all products.
#
# Sections:
#   1. KPI cards — Cheapest On / Competitive On / Overpriced On
#   2. Full attention table — all undercut products, sorted by gap
#   3. Price comparison pivot table — 10×4 grid, product × seller
#   4. Product drill-down navigator — sets session state → Product Detail
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd

from queries import (
    get_market_position_summary,
    get_market_position_data,
    get_products_requiring_attention,
    get_all_product_names,
)
from components.metrics import render_kpi_row
from components.tables  import render_attention_table


def render() -> None:

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
        <div style="font-size:26px; font-weight:700; color:#111827;
                    letter-spacing:-0.02em; margin-bottom:4px;">
            Market Position
        </div>
        <div style="font-size:14px; color:#6B7280; margin-bottom:24px;">
            Full competitive pricing grid across all tracked products and sellers.
        </div>
    """, unsafe_allow_html=True)

    # ── Fetch all data upfront ────────────────────────────────────────────────
    summary        = get_market_position_summary()
    position_data  = get_market_position_data()
    attention_data = get_products_requiring_attention(limit=50)
    product_names  = get_all_product_names()

    # ── Section 1: KPI cards ──────────────────────────────────────────────────
    cheapest    = int(summary.get("cheapest",    0))
    competitive = int(summary.get("competitive", 0))
    overpriced  = int(summary.get("overpriced",  0))
    total       = cheapest + competitive + overpriced

    render_kpi_row([
        {
            "label"        : "Cheapest Position",
            "value"        : cheapest,
            "subtitle"     : f"Leading on {cheapest} of {total} products",
            "accent_color" : "#10B981",
            "icon"         : "✓",
        },
        {
            "label"        : "Competitive Position",
            "value"        : competitive,
            "subtitle"     : f"Within {5}% of cheapest competitor",
            "accent_color" : "#2563EB",
            "icon"         : "~",
        },
        {
            "label"        : "Overpriced",
            "value"        : overpriced,
            "subtitle"     : "More than 5% above cheapest",
            "accent_color" : "#EF4444" if overpriced > 0 else "#10B981",
            "icon"         : "↑",
        },
    ])

    # ── Section 2: Products requiring attention ───────────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:8px 0 24px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:4px;'>"
        "Products Requiring Attention</p>"
        "<p style='font-size:12px; color:#9CA3AF; margin-bottom:12px;'>"
        "Products where at least one competitor is currently cheaper than you.</p>",
        unsafe_allow_html=True,
    )

    attention_df = pd.DataFrame(attention_data) if attention_data else pd.DataFrame()
    render_attention_table(attention_df)

    # ── Section 3: Full price comparison grid ─────────────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:24px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:4px;'>"
        "Price Comparison Grid</p>"
        "<p style='font-size:12px; color:#9CA3AF; margin-bottom:12px;'>"
        "Current prices for every product across all tracked sellers. "
        "Out of stock shown as — </p>",
        unsafe_allow_html=True,
    )

    if not position_data:
        st.caption("No position data available.")
    else:
        pos_df = pd.DataFrame(position_data)

        # ── Build combined price + stock status cell value ────────────────────
        # "AED 3,799" if in stock, "Out of Stock" if not.
        # Compact and readable for a 10×4 grid.
        def _fmt_cell(row):
            if row["stock_status"] == "out_of_stock":
                return "Out of Stock"
            try:
                return f"AED {float(row['current_price']):,.0f}"
            except (TypeError, ValueError):
                return "—"

        pos_df["cell_value"] = pos_df.apply(_fmt_cell, axis=1)

        # ── Pivot: product_name × seller_name ────────────────────────────────
        pivot = pos_df.pivot(
            index   = "product_name",
            columns = "seller_name",
            values  = "cell_value",
        )
        pivot.index.name   = "Product"
        pivot.columns.name = None

        # ── Identify client column for highlighting ───────────────────────────
        client_sellers = pos_df[pos_df["is_client"] == True]["seller_name"].unique()

        # ── Apply column-level highlighting via Styler ────────────────────────
        # Highlight the client's column in light blue.
        # Row-level highlighting not needed here — column identity is enough.
        def _highlight_client_col(col):
            if col.name in client_sellers:
                return ["background-color: #EFF6FF; font-weight: 600"] * len(col)
            return [""] * len(col)

        styler = pivot.style.apply(_highlight_client_col, axis=0)

        st.dataframe(
            styler,
            use_container_width=True,
            height=420,
        )

        # Legend below the grid
        client_name = client_sellers[0] if len(client_sellers) > 0 else "Your store"
        st.markdown(
            f"<p style='font-size:11px; color:#9CA3AF; margin-top:6px;'>"
            f"<span style='background:#EFF6FF; padding:1px 6px; border-radius:4px; "
            f"color:#2563EB; font-weight:600;'>{client_name}</span> "
            f"column highlighted in blue — your store's pricing.</p>",
            unsafe_allow_html=True,
        )

    # ── Section 4: Product drill-down navigator ───────────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:24px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:4px;'>"
        "View Product Detail</p>"
        "<p style='font-size:12px; color:#9CA3AF; margin-bottom:12px;'>"
        "Select a product to open its full price history and competitive analysis.</p>",
        unsafe_allow_html=True,
    )

    nav_col1, nav_col2 = st.columns([3, 1])

    with nav_col1:
        selected_product = st.selectbox(
            "Select product",
            options   = product_names,
            index     = 0,
            label_visibility = "collapsed",
        )

    with nav_col2:
        if st.button("Open Detail →", type="primary", use_container_width=True):
            # Set session state — Product Detail page reads these on load
            st.session_state["selected_product_name"] = selected_product
            st.session_state["selected_page"]         = "Product Detail"
            st.rerun()

    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)