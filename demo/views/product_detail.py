# ─── views/product_detail.py ─────────────────────────────────────────────────
# Product Detail page — deep dive into one product across all sellers.
#
# Sections:
#   0. Product selector (pre-populated from session state if navigated here)
#   1. Two KPI cards — client current price + current rank
#   2. Price history line chart (hero visual — full width)
#   3. Current ranking table + price position bar chart (two columns)
#   4. Recent alerts for this product (last 10, read-only)
#
# Session state:
#   Reads  st.session_state["selected_product_name"] on load.
#   Writes st.session_state["selected_product_name"] when user changes selector.
#   This keeps Market Position → Product Detail navigation working.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd

from queries import (
    get_all_product_names,
    get_price_history,
    get_product_current_ranking,
    get_product_recent_alerts,
)
from components.metrics import render_kpi_row
from components.charts  import price_history_chart, price_position_bar
from components.tables  import render_ranking_table, render_alerts_table


def render() -> None:

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
        <div style="font-size:26px; font-weight:700; color:#111827;
                    letter-spacing:-0.02em; margin-bottom:4px;">
            Product Detail
        </div>
        <div style="font-size:14px; color:#6B7280; margin-bottom:20px;">
            Price history, competitive ranking, and recent alerts for one product.
        </div>
    """, unsafe_allow_html=True)

    # ── Section 0: Product selector ───────────────────────────────────────────
    product_names = get_all_product_names()

    if not product_names:
        st.warning("No products found in the database.")
        return

    # Determine the default selection:
    # If session state has a product (set by Market Position navigation), use it.
    # Otherwise default to the first product in the list.
    session_product = st.session_state.get("selected_product_name")
    if session_product and session_product in product_names:
        default_index = product_names.index(session_product)
    else:
        default_index = 0

    selected_product = st.selectbox(
        "Select Product",
        options = product_names,
        index   = default_index,
        label_visibility = "visible",
    )

    # Keep session state in sync with the selector.
    # This means if user manually changes the dropdown, session state updates.
    st.session_state["selected_product_name"] = selected_product

    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:20px 0;'>",
        unsafe_allow_html=True,
    )

    # ── Fetch all data for selected product ───────────────────────────────────
    history_data  = get_price_history(selected_product)
    ranking_data  = get_product_current_ranking(selected_product)
    recent_alerts = get_product_recent_alerts(selected_product, limit=10)

    history_df = pd.DataFrame(history_data) if history_data else pd.DataFrame()
    ranking_df = pd.DataFrame(ranking_data) if ranking_data else pd.DataFrame()
    alerts_df  = pd.DataFrame(recent_alerts) if recent_alerts else pd.DataFrame()

    # ── Section 1: KPI cards ──────────────────────────────────────────────────
    # Extract client row from ranking data for current price and rank.
    client_rows = [r for r in ranking_data if bool(r.get("is_client", False))]

    if client_rows:
        client_row   = client_rows[0]
        client_price = float(client_row.get("current_price", 0))
        client_rank  = int(client_row.get("rank", 0))
        total_sellers= len(ranking_data)

        rank_label   = (
            "1st — Cheapest" if client_rank == 1
            else f"{client_rank}{'nd' if client_rank == 2 else 'rd' if client_rank == 3 else 'th'} of {total_sellers}"
        )
        rank_color   = (
            "#10B981" if client_rank == 1
            else "#F59E0B" if client_rank == 2
            else "#EF4444"
        )
        rank_subtitle = (
            "You are the cheapest seller" if client_rank == 1
            else f"Undercut by {total_sellers - client_rank} cheaper seller{'s' if (total_sellers - client_rank) > 1 else ''}"
        )

        render_kpi_row([
            {
                "label"        : "Your Current Price",
                "value"        : f"AED {client_price:,.0f}",
                "subtitle"     : f"TechZone UAE · {selected_product}",
                "accent_color" : "#2563EB",
                "icon"         : "◈",
            },
            {
                "label"        : "Your Market Rank",
                "value"        : rank_label,
                "subtitle"     : rank_subtitle,
                "accent_color" : rank_color,
                "icon"         : "↑" if client_rank == 1 else "↓",
            },
        ])
    else:
        st.info("No pricing data found for your store on this product.")

    # ── Section 2: Price history chart (hero visual) ──────────────────────────
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;'>"
        "Price History — All Sellers</p>",
        unsafe_allow_html=True,
    )

    if history_df.empty:
        st.caption("No price history available for this product.")
    else:
        fig = price_history_chart(history_df)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Subtle caption below chart explaining the line styles
        st.markdown(
            "<p style='font-size:11px; color:#9CA3AF; margin-top:4px;'>"
            "Blue line = your store. Grey lines = competitors. "
            "Gaps in lines indicate out-of-stock periods.</p>",
            unsafe_allow_html=True,
        )

    # ── Section 3: Ranking table + price position bar ─────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:24px 0;'>",
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown(
            "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;'>"
            "Current Ranking</p>",
            unsafe_allow_html=True,
        )
        render_ranking_table(ranking_df)

    with col_right:
        st.markdown(
            "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;'>"
            "Price Comparison</p>",
            unsafe_allow_html=True,
        )
        if not ranking_df.empty:
            fig = price_position_bar(ranking_df)
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False},
            )

    # ── Section 4: Recent alerts for this product ─────────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:24px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:4px;'>"
        "Recent Alerts</p>"
        "<p style='font-size:12px; color:#9CA3AF; margin-bottom:12px;'>"
        "Last 10 alerts for this product across all sellers.</p>",
        unsafe_allow_html=True,
    )

    if alerts_df.empty:
        st.markdown(
            "<p style='font-size:13px; color:#10B981;'>"
            "✓ No recent alerts for this product.</p>",
            unsafe_allow_html=True,
        )
    else:
        render_alerts_table(alerts_df)

    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)