# ─── views/system_health.py ──────────────────────────────────────────────────
# System Health page — scraper reliability and run history.
# Pure display page: no filters, no write operations, no session state.
# Audience: you (developer) and technical recruiters viewing the portfolio.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd

from queries import get_scrape_logs, get_system_health_summary
from components.metrics import render_kpi_row
from components.charts  import scrape_activity_chart
from components.tables  import render_scrape_logs_table


def render() -> None:

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
        <div style="font-size:26px; font-weight:700; color:#111827;
                    letter-spacing:-0.02em; margin-bottom:4px;">
            System Health
        </div>
        <div style="font-size:14px; color:#6B7280; margin-bottom:24px;">
            Scraper run history, reliability metrics, and alert generation overview.
        </div>
    """, unsafe_allow_html=True)

    # ── Fetch data ────────────────────────────────────────────────────────────
    summary  = get_system_health_summary()
    logs     = get_scrape_logs()
    logs_df  = pd.DataFrame(logs) if logs else pd.DataFrame()

    # ── Section 1: KPI cards — row 1 ─────────────────────────────────────────
    total_runs      = int(summary.get("total_runs",      0))
    successful_runs = int(summary.get("successful_runs", 0))
    failed_runs     = int(summary.get("failed_runs",     0))
    success_rate    = (
        round((successful_runs / total_runs) * 100, 1)
        if total_runs > 0 else 0
    )

    render_kpi_row([
        {
            "label"        : "Total Scrape Runs",
            "value"        : total_runs,
            "subtitle"     : "Since monitoring began",
            "accent_color" : "#2563EB",
            "icon"         : "↺",
        },
        {
            "label"        : "Successful Runs",
            "value"        : successful_runs,
            "subtitle"     : f"{success_rate}% success rate",
            "accent_color" : "#10B981",
            "icon"         : "✓",
        },
        {
            "label"        : "Failed Runs",
            "value"        : failed_runs,
            "subtitle"     : "Require investigation" if failed_runs > 0 else "No failures recorded",
            "accent_color" : "#EF4444" if failed_runs > 0 else "#10B981",
            "icon"         : "✗",
        },
    ])

    # ── Section 1: KPI cards — row 2 ─────────────────────────────────────────
    avg_duration = float(summary.get("avg_duration_secs",     0) or 0)
    total_alerts = int(summary.get("total_alerts_triggered",  0) or 0)
    total_updated= int(summary.get("total_products_updated",  0) or 0)

    render_kpi_row([
        {
            "label"        : "Total Alerts Generated",
            "value"        : total_alerts,
            "subtitle"     : "Across all scrape runs",
            "accent_color" : "#F59E0B",
            "icon"         : "🔔",
        },
        {
            "label"        : "Total Products Updated",
            "value"        : total_updated,
            "subtitle"     : "Price snapshots recorded",
            "accent_color" : "#2563EB",
            "icon"         : "◈",
        },
        {
            "label"        : "Avg Run Duration",
            "value"        : f"{avg_duration:.1f}s",
            "subtitle"     : "Per scrape run",
            "accent_color" : "#6B7280",
            "icon"         : "⏱",
        },
    ])

    # ── Section 2: Scrape activity chart ─────────────────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:8px 0 24px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;'>"
        "Alerts per Scrape Run</p>",
        unsafe_allow_html=True,
    )

    if logs_df.empty:
        st.caption("No scrape logs available.")
    else:
        fig = scrape_activity_chart(logs_df)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Color legend — explains the bar colors
        st.markdown("""
            <div style="display:flex; gap:20px; margin-top:4px; margin-bottom:8px;">
                <span style="font-size:12px; color:#6B7280;">
                    <span style="color:#2563EB;">■</span> Success
                </span>
                <span style="font-size:12px; color:#6B7280;">
                    <span style="color:#F59E0B;">■</span> Partial
                </span>
                <span style="font-size:12px; color:#6B7280;">
                    <span style="color:#EF4444;">■</span> Failed
                </span>
            </div>
        """, unsafe_allow_html=True)

    # ── Section 3: Full scrape logs table ────────────────────────────────────
    st.markdown(
        "<hr style='border:none; border-top:1px solid #F3F4F6; margin:24px 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#111827; margin-bottom:12px;'>"
        "Run History</p>",
        unsafe_allow_html=True,
    )

    render_scrape_logs_table(logs_df)

    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)