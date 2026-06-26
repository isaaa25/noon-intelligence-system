# ─── views/alerts.py ─────────────────────────────────────────────────────────
# Alerts page — daily action feed for the client.
# The page a seller checks every morning to see what changed overnight.
#
# Features:
#   - Summary KPI cards (total unseen, price changes, stock events)
#   - Three-way filter: alert type, seller, seen/unseen status
#   - Full alert table via render_alerts_table()
#   - Mark individual alert as seen (only write operation on this page)
#
# Filters are stored in st.session_state so a rerun after marking an
# alert seen doesn't reset the dropdowns back to "All".
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd

from queries import (
    get_alerts,
    get_alerts_summary,
    get_all_sellers,
    mark_alert_seen,
)
from components.metrics import render_kpi_row
from components.tables  import render_alerts_table


# ── Alert type options for the filter dropdown ────────────────────────────────
ALERT_TYPE_OPTIONS = {
    "All Types"     : None,
    "Price Drop"    : "price_drop",
    "Price Increase": "price_increase",
    "Out of Stock"  : "out_of_stock",
    "Back in Stock" : "back_in_stock",
    "New Competitor": "new_competitor",
}

STATUS_OPTIONS = {
    "All"        : None,
    "Unseen Only": False,
    "Seen Only"  : True,
}


def render() -> None:

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
        <div style="font-size:26px; font-weight:700; color:#111827;
                    letter-spacing:-0.02em; margin-bottom:4px;">
            Alerts
        </div>
        <div style="font-size:14px; color:#6B7280; margin-bottom:24px;">
            Price changes, stock events, and competitor activity across all tracked products.
        </div>
    """, unsafe_allow_html=True)

    # ── Fetch summary ─────────────────────────────────────────────────────────
    summary        = get_alerts_summary()
    total_unseen   = int(summary.get("total_unseen",         0))
    unseen_prices  = int(summary.get("unseen_price_changes", 0))
    unseen_stock   = int(summary.get("unseen_stock_events",  0))

    # ── Section 1: KPI cards ──────────────────────────────────────────────────
    render_kpi_row([
        {
            "label"        : "Unseen Alerts",
            "value"        : total_unseen,
            "subtitle"     : "Awaiting your review",
            "accent_color" : "#EF4444" if total_unseen > 0 else "#10B981",
            "icon"         : "🔔",
        },
        {
            "label"        : "Unseen Price Changes",
            "value"        : unseen_prices,
            "subtitle"     : "Price drops and increases",
            "accent_color" : "#EF4444" if unseen_prices > 0 else "#10B981",
            "icon"         : "↕",
        },
        {
            "label"        : "Unseen Stock Events",
            "value"        : unseen_stock,
            "subtitle"     : "Out of stock and restocks",
            "accent_color" : "#F59E0B" if unseen_stock > 0 else "#10B981",
            "icon"         : "◈",
        },
    ])

    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:8px 0 24px 0;'>",
        unsafe_allow_html=True,
    )

    # ── Section 2: Filters ────────────────────────────────────────────────────
    # Initialise filter session state on first visit.
    # Persisted so filters survive the rerun triggered by mark-as-seen.
    if "alert_filter_type"   not in st.session_state:
        st.session_state["alert_filter_type"]   = "All Types"
    if "alert_filter_seller" not in st.session_state:
        st.session_state["alert_filter_seller"] = "All Sellers"
    if "alert_filter_status" not in st.session_state:
        st.session_state["alert_filter_status"] = "All"

    # Build seller options from database
    sellers     = get_all_sellers()
    seller_map  = {"All Sellers": None}
    for s in sellers:
        seller_map[s["store_name"]] = s["id"]

    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;'>"
        "Filter Alerts</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        selected_type_label = st.selectbox(
            "Alert Type",
            options=list(ALERT_TYPE_OPTIONS.keys()),
            index=list(ALERT_TYPE_OPTIONS.keys()).index(
                st.session_state["alert_filter_type"]
            ),
            key="alert_type_select",
        )

    with col2:
        selected_seller_label = st.selectbox(
            "Seller",
            options=list(seller_map.keys()),
            index=list(seller_map.keys()).index(
                st.session_state["alert_filter_seller"]
            ) if st.session_state["alert_filter_seller"] in seller_map else 0,
            key="alert_seller_select",
        )

    with col3:
        selected_status_label = st.selectbox(
            "Status",
            options=list(STATUS_OPTIONS.keys()),
            index=list(STATUS_OPTIONS.keys()).index(
                st.session_state["alert_filter_status"]
            ),
            key="alert_status_select",
        )

    # Persist selections to session state
    st.session_state["alert_filter_type"]   = selected_type_label
    st.session_state["alert_filter_seller"] = selected_seller_label
    st.session_state["alert_filter_status"] = selected_status_label

    # Resolve labels to actual filter values
    alert_type_val  = ALERT_TYPE_OPTIONS[selected_type_label]
    seller_id_val   = seller_map[selected_seller_label]
    is_seen_val     = STATUS_OPTIONS[selected_status_label]

    # ── Fetch filtered alerts ─────────────────────────────────────────────────
    alerts = get_alerts(
        alert_type = alert_type_val,
        seller_id  = seller_id_val,
        is_seen    = is_seen_val,
    )
    alerts_df = pd.DataFrame(alerts) if alerts else pd.DataFrame()

    # ── Section 3: Mark as seen ───────────────────────────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:24px 0 16px 0;'>",
        unsafe_allow_html=True,
    )

    unseen_alerts = [a for a in alerts if not bool(a.get("is_seen", True))]

    if unseen_alerts:
        st.markdown(
            "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;'>"
            "Mark as Seen</p>",
            unsafe_allow_html=True,
        )

        # Build selectbox options: human-readable label → alert_id
        seen_options = {
            f"Alert #{a['alert_id']} — {a['product_name']} — {a['alert_type'].replace('_', ' ').title()}": a["alert_id"]
            for a in unseen_alerts
        }

        mark_col1, mark_col2 = st.columns([3, 1])

        with mark_col1:
            selected_label = st.selectbox(
                "Select alert to mark as seen",
                options=list(seen_options.keys()),
                label_visibility="collapsed",
            )

        with mark_col2:
            if st.button("Mark as Seen", type="primary", use_container_width=True):
                alert_id_to_mark = seen_options[selected_label]
                mark_alert_seen(alert_id_to_mark)
                st.success(f"Alert #{alert_id_to_mark} marked as seen.")
                st.rerun()
    else:
        st.markdown(
            "<p style='font-size:13px; color:#10B981;'>✓ All alerts in current view have been seen.</p>",
            unsafe_allow_html=True,
        )

    # ── Section 4: Alerts table ───────────────────────────────────────────────
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; "
        "margin-top:20px; margin-bottom:12px;'>"
        f"Alerts ({len(alerts_df)} results)</p>",
        unsafe_allow_html=True,
    )

    render_alerts_table(alerts_df)

    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)