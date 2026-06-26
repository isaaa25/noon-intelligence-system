# # # ─── views/home.py ───────────────────────────────────────────────────────────
# # # Market Intelligence Overview — the command-centre homepage.
# # #
# # # Sections:
# # #   0. Page header + system status strip
# # #   1. KPI cards (4 cards)
# # #   2. Competitive snapshot (donut + attention table, two columns)
# # #   3. Recent market activity feed
# # #   4. Competitor activity chart
# # #   5. Seller competitive summary table
# # #
# # # This file never imports from db.py or touches SQL directly.
# # # All data comes from queries.py. All charts come from components/charts.py.
# # # All tables come from components/tables.py. KPI cards from components/metrics.py.
# # #
# # # Private helpers (_fmt_activity_event, _get_event_icon, _fmt_event_time)
# # # live here because they are homepage-specific presentation logic —
# # # not reusable UI components.
# # # ─────────────────────────────────────────────────────────────────────────────

# # import streamlit as st
# # import pandas as pd
# # from datetime import datetime, timezone

# # from queries import (
# #     get_active_product_count,
# #     get_unseen_alert_count,
# #     get_products_losing_position_count,
# #     get_competitive_position_summary,
# #     get_products_requiring_attention,
# #     get_recent_market_events,
# #     get_alerts_per_day,
# #     get_seller_competitive_summary,
# #     get_all_sellers,
# # )
# # from components.metrics import render_kpi_row
# # from components.charts  import competitive_position_donut, alerts_by_date_chart
# # from components.tables  import render_attention_table


# # # ═════════════════════════════════════════════════════════════════════════════
# # # PRIVATE HELPERS
# # # Homepage-specific presentation logic. Not shared with other pages.
# # # ═════════════════════════════════════════════════════════════════════════════

# # def _fmt_activity_event(row: dict) -> str:
# #     """
# #     Converts a raw alert row into a natural-language market event sentence.

# #     Examples:
# #         price_drop    → "Sharaf DG reduced iPhone 15 Pro Max by 5.3%"
# #         price_increase→ "Virgin Megastore increased Galaxy S25 Ultra by 4.1%"
# #         out_of_stock  → "iStyle iPhone 15 128GB is now out of stock"
# #         back_in_stock → "Sharaf DG AirPods Pro 2 is back in stock"
# #         new_competitor→ "New competitor listed: iPhone 15 128GB"

# #     Keeps sentences short and scannable — no punctuation at end,
# #     no technical jargon, no raw field names.
# #     """
# #     seller  = row.get("seller_name", "Unknown seller")
# #     product = row.get("product_name", "Unknown product")
# #     atype   = row.get("alert_type",  "")
# #     pct     = row.get("change_pct",  0)

# #     try:
# #         pct_str = f"{abs(float(pct)):.1f}%"
# #     except (TypeError, ValueError):
# #         pct_str = ""

# #     if atype == "price_drop":
# #         return f"{seller} reduced {product} by {pct_str}"
# #     elif atype == "price_increase":
# #         return f"{seller} increased {product} by {pct_str}"
# #     elif atype == "out_of_stock":
# #         return f"{seller} {product} is now out of stock"
# #     elif atype == "back_in_stock":
# #         return f"{seller} {product} is back in stock"
# #     elif atype == "new_competitor":
# #         return f"New competitor listed: {product}"
# #     else:
# #         return f"{seller} — {product}"


# # def _get_event_icon(row: dict) -> str:
# #     """
# #     Returns a single emoji character representing the event type.
# #     Used as a visual anchor in the activity feed — one per row.

# #     📉 price_drop      — market moving down, attention needed
# #     📈 price_increase  — competitor raising prices (opportunity)
# #     📦 out_of_stock    — availability change
# #     🔄 back_in_stock   — availability restored
# #     🆕 new_competitor  — new market entrant
# #     ·  fallback        — neutral dot for unknown types
# #     """
# #     mapping = {
# #         "price_drop"    : "📉",
# #         "price_increase": "📈",
# #         "out_of_stock"  : "📦",
# #         "back_in_stock" : "🔄",
# #         "new_competitor": "🆕",
# #     }
# #     return mapping.get(row.get("alert_type", ""), "·")


# # def _fmt_event_time(ts) -> str:
# #     """
# #     Converts a timestamp to a human-readable relative time string.

# #     Examples:
# #         < 1 min  → "Just now"
# #         < 1 hr   → "12 min ago"
# #         < 24 hrs → "3 hrs ago"
# #         < 2 days → "Yesterday"
# #         else     → "Jun 14"

# #     Uses UTC-aware comparison. Handles both timezone-aware and
# #     naive datetimes from the database safely.
# #     """
# #     try:
# #         now = datetime.now(timezone.utc)

# #         # Normalise: if timestamp is naive, assume UTC
# #         if isinstance(ts, str):
# #             ts = pd.to_datetime(ts)
# #         if ts.tzinfo is None:
# #             ts = ts.replace(tzinfo=timezone.utc)

# #         diff_secs = (now - ts).total_seconds()

# #         if diff_secs < 60:
# #             return "Just now"
# #         elif diff_secs < 3600:
# #             mins = int(diff_secs // 60)
# #             return f"{mins} min ago"
# #         elif diff_secs < 86400:
# #             hrs = int(diff_secs // 3600)
# #             return f"{hrs} hr{'s' if hrs > 1 else ''} ago"
# #         elif diff_secs < 172800:
# #             return "Yesterday"
# #         else:
# #             return ts.strftime("%b %d")
# #     except Exception:
# #         return ""


# # # ═════════════════════════════════════════════════════════════════════════════
# # # SECTION CSS
# # # Page-level styles injected once on render.
# # # Scoped with .ni- prefix to avoid conflicts with Streamlit's own classes.
# # # ═════════════════════════════════════════════════════════════════════════════

# # _HOME_CSS = """
# # <style>

# # /* ── Page header ──────────────────────────────────────────────────────────── */
# # .ni-page-title {
# #     font-size     : 26px;
# #     font-weight   : 700;
# #     color         : #111827;
# #     letter-spacing: -0.02em;
# #     margin-bottom : 4px;
# #     line-height   : 1.2;
# # }

# # .ni-page-subtitle {
# #     font-size  : 14px;
# #     color      : #6B7280;
# #     margin-bottom: 12px;
# #     line-height: 1.5;
# # }

# # /* ── System status strip ──────────────────────────────────────────────────── */
# # .ni-status-strip {
# #     display    : flex;
# #     align-items: center;
# #     gap        : 16px;
# #     flex-wrap  : wrap;
# #     padding    : 10px 0 20px 0;
# # }

# # .ni-status-dot {
# #     display    : flex;
# #     align-items: center;
# #     gap        : 6px;
# #     font-size  : 12px;
# #     font-weight: 500;
# #     color      : #10B981;
# # }

# # .ni-status-dot::before {
# #     content      : "●";
# #     font-size    : 8px;
# #     animation    : ni-pulse 2s ease-in-out infinite;
# # }

# # @keyframes ni-pulse {
# #     0%, 100% { opacity: 1;   }
# #     50%       { opacity: 0.4; }
# # }

# # .ni-status-stat {
# #     font-size  : 12px;
# #     color      : #9CA3AF;
# # }

# # .ni-status-stat span {
# #     font-weight: 600;
# #     color      : #374151;
# # }

# # .ni-status-divider {
# #     color    : #E5E7EB;
# #     font-size: 12px;
# # }

# # /* ── Section headings ─────────────────────────────────────────────────────── */
# # .ni-section-heading {
# #     font-size    : 14px;
# #     font-weight  : 600;
# #     color        : #111827;
# #     margin-bottom: 12px;
# #     margin-top   : 0;
# #     letter-spacing: -0.01em;
# # }

# # .ni-section-divider {
# #     border     : none;
# #     border-top : 1px solid #F3F4F6;
# #     margin     : 28px 0;
# # }

# # /* ── Activity feed ────────────────────────────────────────────────────────── */
# # .ni-feed-item {
# #     display        : flex;
# #     align-items    : flex-start;
# #     gap            : 12px;
# #     padding        : 10px 0;
# #     border-bottom  : 1px solid #F9FAFB;
# # }

# # .ni-feed-item:last-child {
# #     border-bottom: none;
# # }

# # .ni-feed-icon {
# #     font-size  : 16px;
# #     flex-shrink: 0;
# #     margin-top : 1px;
# # }

# # .ni-feed-text {
# #     flex      : 1;
# #     font-size : 13px;
# #     color     : #374151;
# #     line-height: 1.5;
# # }

# # .ni-feed-client-badge {
# #     display         : inline-block;
# #     font-size       : 10px;
# #     font-weight     : 600;
# #     color           : #2563EB;
# #     background      : #EFF6FF;
# #     border-radius   : 4px;
# #     padding         : 1px 6px;
# #     margin-left     : 6px;
# #     vertical-align  : middle;
# # }

# # .ni-feed-time {
# #     font-size  : 11px;
# #     color      : #9CA3AF;
# #     flex-shrink: 0;
# #     margin-top : 2px;
# # }

# # /* ── Seller summary table ─────────────────────────────────────────────────── */
# # .ni-seller-row {
# #     display        : flex;
# #     align-items    : center;
# #     justify-content: space-between;
# #     padding        : 10px 0;
# #     border-bottom  : 1px solid #F9FAFB;
# #     font-size      : 13px;
# # }

# # .ni-seller-row:last-child {
# #     border-bottom: none;
# # }

# # .ni-seller-name {
# #     color      : #374151;
# #     font-weight: 500;
# # }

# # .ni-seller-client-tag {
# #     font-size      : 10px;
# #     font-weight    : 600;
# #     color          : #2563EB;
# #     background     : #EFF6FF;
# #     border-radius  : 4px;
# #     padding        : 1px 6px;
# #     margin-left    : 8px;
# # }

# # .ni-seller-bar-wrap {
# #     display    : flex;
# #     align-items: center;
# #     gap        : 8px;
# #     flex       : 1;
# #     max-width  : 180px;
# #     margin     : 0 16px;
# # }

# # .ni-seller-bar-bg {
# #     flex          : 1;
# #     height        : 6px;
# #     background    : #F3F4F6;
# #     border-radius : 99px;
# #     overflow      : hidden;
# # }

# # .ni-seller-bar-fill {
# #     height       : 6px;
# #     border-radius: 99px;
# # }

# # .ni-seller-count {
# #     font-size  : 13px;
# #     font-weight: 600;
# #     color      : #111827;
# #     min-width  : 20px;
# #     text-align : right;
# # }

# # </style>
# # """


# # # ═════════════════════════════════════════════════════════════════════════════
# # # RENDER
# # # ═════════════════════════════════════════════════════════════════════════════

# # def render() -> None:
# #     """
# #     Entry point called by app.py when user navigates to Dashboard.
# #     Fetches all data, then renders each section top to bottom.
# #     """

# #     # ── Inject page CSS ───────────────────────────────────────────────────────
# #     st.markdown(_HOME_CSS, unsafe_allow_html=True)

# #     # ── Fetch all data upfront ────────────────────────────────────────────────
# #     # Collected at the top so every section renders from already-fetched data.
# #     # No query is called inside a section — keeps section code readable.
# #     active_products    = get_active_product_count()
# #     unseen_alerts      = get_unseen_alert_count()
# #     losing_count       = get_products_losing_position_count()
# #     position_summary   = get_competitive_position_summary()
# #     attention_data     = get_products_requiring_attention(limit=5)
# #     recent_events      = get_recent_market_events(limit=10)
# #     alerts_per_day     = get_alerts_per_day()
# #     seller_summary     = get_seller_competitive_summary()
# #     all_sellers        = get_all_sellers()

# #     # Derived values used across multiple sections
# #     total_sellers      = len(all_sellers)
# #     cheapest_count     = position_summary.get("cheapest", 0)
# #     highest_gap_pct    = (
# #         max((float(r.get("gap_pct", 0)) for r in attention_data), default=0)
# #         if attention_data else 0
# #     )

# #     # ─────────────────────────────────────────────────────────────────────────
# #     # SECTION 0 — Page Header + System Status Strip
# #     # ─────────────────────────────────────────────────────────────────────────

# #     st.markdown("""
# #         <div class="ni-page-title">Market Intelligence Overview</div>
# #         <div class="ni-page-subtitle">
# #             Monitor pricing movements, competitive position,
# #             and market activity across tracked sellers.
# #         </div>
# #     """, unsafe_allow_html=True)

# #     # System status strip — compact, muted, always visible
# #     # Snapshot count is a fixed demo value since we don't expose it via query.
# #     # In production this would come from COUNT(price_snapshots).
# #     total_alerts = sum(
# #         r.get("alert_count", 0) for r in alerts_per_day
# #     )

# #     st.markdown(f"""
# #         <div class="ni-status-strip">
# #             <div class="ni-status-dot">Monitoring Active</div>
# #             <div class="ni-status-divider">|</div>
# #             <div class="ni-status-stat"><span>{active_products * total_sellers}</span> Snapshots</div>
# #             <div class="ni-status-divider">|</div>
# #             <div class="ni-status-stat"><span>{active_products}</span> Products</div>
# #             <div class="ni-status-divider">|</div>
# #             <div class="ni-status-stat"><span>{total_sellers}</span> Sellers</div>
# #             <div class="ni-status-divider">|</div>
# #             <div class="ni-status-stat"><span>{total_alerts}</span> Alerts Generated</div>
# #         </div>
# #     """, unsafe_allow_html=True)

# #     # ─────────────────────────────────────────────────────────────────────────
# #     # SECTION 1 — KPI Cards
# #     # ─────────────────────────────────────────────────────────────────────────

# #     render_kpi_row([
# #         {
# #             "label"        : "Products Tracked",
# #             "value"        : active_products,
# #             "subtitle"     : f"Across {total_sellers} sellers",
# #             "accent_color" : "#2563EB",
# #             "icon"         : "◈",
# #         },
# #         {
# #             "label"        : "Unseen Alerts",
# #             "value"        : unseen_alerts,
# #             "subtitle"     : "Awaiting review",
# #             "accent_color" : "#EF4444" if unseen_alerts > 0 else "#10B981",
# #             "icon"         : "🔔",
# #         },
# #         {
# #             "label"        : "Products Undercut",
# #             "value"        : losing_count,
# #             "subtitle"     : (
# #                 f"Highest gap: {highest_gap_pct:.1f}%"
# #                 if losing_count > 0 else "No undercutting detected"
# #             ),
# #             "accent_color" : "#EF4444" if losing_count > 0 else "#10B981",
# #             "icon"         : "↓",
# #         },
# #         {
# #             "label"        : "Cheapest Position",
# #             "value"        : cheapest_count,
# #             "subtitle"     : f"Leading on {cheapest_count} of {active_products} products",
# #             "accent_color" : "#10B981" if cheapest_count > 0 else "#F59E0B",
# #             "icon"         : "✓",
# #         },
# #     ])

# #     # ─────────────────────────────────────────────────────────────────────────
# #     # SECTION 2 — Competitive Snapshot (donut + attention table)
# #     # ─────────────────────────────────────────────────────────────────────────

# #     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)

# #     col_left, col_right = st.columns([1, 1.4], gap="large")

# #     with col_left:
# #         st.markdown(
# #             '<p class="ni-section-heading">Market Position Overview</p>',
# #             unsafe_allow_html=True,
# #         )
# #         fig = competitive_position_donut(position_summary)
# #         st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# #     with col_right:
# #         st.markdown(
# #             '<p class="ni-section-heading">Products Requiring Attention</p>',
# #             unsafe_allow_html=True,
# #         )
# #         attention_df = pd.DataFrame(attention_data)
# #         render_attention_table(attention_df)

# #     # ─────────────────────────────────────────────────────────────────────────
# #     # SECTION 3 — Recent Market Activity Feed
# #     # ─────────────────────────────────────────────────────────────────────────

# #     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
# #     st.markdown(
# #         '<p class="ni-section-heading">Recent Market Activity</p>',
# #         unsafe_allow_html=True,
# #     )

# #     if not recent_events:
# #         st.caption("No recent activity to display.")
# #     else:
# #         feed_html_parts = []

# #         for row in recent_events:
# #             icon      = _get_event_icon(row)
# #             text      = _fmt_activity_event(row)
# #             time_str  = _fmt_event_time(row.get("triggered_at"))
# #             is_client = bool(row.get("is_client", False))

# #             # Client events get a subtle "Your store" badge
# #             badge_html = (
# #                 '<span class="ni-feed-client-badge">Your store</span>'
# #                 if is_client else ""
# #             )

# #             feed_html_parts.append(f"""
# #                 <div class="ni-feed-item">
# #                     <div class="ni-feed-icon">{icon}</div>
# #                     <div class="ni-feed-text">
# #                         {text}{badge_html}
# #                     </div>
# #                     <div class="ni-feed-time">{time_str}</div>
# #                 </div>
# #             """)

# #         st.markdown(
# #             "<div>" + "".join(feed_html_parts) + "</div>",
# #             unsafe_allow_html=True,
# #         )

# #     # ─────────────────────────────────────────────────────────────────────────
# #     # SECTION 4 — Competitor Activity Chart
# #     # ─────────────────────────────────────────────────────────────────────────

# #     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
# #     st.markdown(
# #         '<p class="ni-section-heading">Competitor Activity</p>',
# #         unsafe_allow_html=True,
# #     )

# #     if not alerts_per_day:
# #         st.caption("No alert data available.")
# #     else:
# #         activity_df = pd.DataFrame(alerts_per_day)
# #         # Rename columns to match what alerts_timeline_chart() expects
# #         activity_df = activity_df.rename(columns={
# #             "alert_date" : "run_at",
# #             "alert_count": "alerts_triggered",
# #         })
# #         fig = alerts_by_date_chart(activity_df)
# #         st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# #     # ─────────────────────────────────────────────────────────────────────────
# #     # SECTION 5 — Seller Competitive Summary
# #     # ─────────────────────────────────────────────────────────────────────────

# #     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
# #     st.markdown(
# #         '<p class="ni-section-heading">Seller Competitive Summary</p>',
# #         unsafe_allow_html=True,
# #     )

# #     if not seller_summary:
# #         st.caption("No seller data available.")
# #     else:
# #         # Max leading_on across all sellers — used to scale the bar widths
# #         max_leading = max(
# #             (int(r.get("leading_on", 0)) for r in seller_summary), default=1
# #         )
# #         # Avoid division by zero if everyone is at 0
# #         max_leading = max(max_leading, 1)

# #         rows_html = []
# #         for row in seller_summary:
# #             name       = row.get("store_name", "")
# #             is_client  = bool(row.get("is_client", False))
# #             leading_on = int(row.get("leading_on", 0))

# #             # Bar width as a percentage of the maximum
# #             bar_pct    = int((leading_on / max_leading) * 100)

# #             # Client bar is blue; competitors are grey
# #             bar_color  = "#2563EB" if is_client else "#D1D5DB"

# #             client_tag = (
# #                 '<span class="ni-seller-client-tag">You</span>'
# #                 if is_client else ""
# #             )

# #             rows_html.append(f"""
# #                 <div class="ni-seller-row">
# #                     <div class="ni-seller-name">
# #                         {name}{client_tag}
# #                     </div>
# #                     <div class="ni-seller-bar-wrap">
# #                         <div class="ni-seller-bar-bg">
# #                             <div class="ni-seller-bar-fill"
# #                                  style="width:{bar_pct}%;
# #                                         background:{bar_color};">
# #                             </div>
# #                         </div>
# #                     </div>
# #                     <div class="ni-seller-count">{leading_on}</div>
# #                 </div>
# #             """)

# #         st.markdown(
# #             "<div>" + "".join(rows_html) + "</div>",
# #             unsafe_allow_html=True,
# #         )

# #         st.markdown(
# #             "<p style='font-size:11px; color:#9CA3AF; margin-top:8px;'>"
# #             "Number of products each seller currently offers at the lowest price.</p>",
# #             unsafe_allow_html=True,
# #         )

# #     # ── Bottom padding ────────────────────────────────────────────────────────
# #     st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

# # ─── views/home.py ───────────────────────────────────────────────────────────
# # Market Intelligence Overview — the command-centre homepage.
# #
# # Sections:
# #   0. Page header + system status strip
# #   1. KPI cards (4 cards)
# #   2. Competitive snapshot (donut + attention table, two columns)
# #   3. Recent market activity feed
# #   4. Competitor activity chart
# #   5. Seller competitive summary table
# #
# # This file never imports from db.py or touches SQL directly.
# # All data comes from queries.py. All charts come from components/charts.py.
# # All tables come from components/tables.py. KPI cards from components/metrics.py.
# #
# # Private helpers (_fmt_activity_event, _get_event_icon, _fmt_event_time)
# # live here because they are homepage-specific presentation logic —
# # not reusable UI components.
# # ─────────────────────────────────────────────────────────────────────────────

# import streamlit as st
# import pandas as pd
# from datetime import datetime, timezone

# from queries import (
#     get_active_product_count,
#     get_unseen_alert_count,
#     get_products_losing_position_count,
#     get_competitive_position_summary,
#     get_products_requiring_attention,
#     get_recent_market_events,
#     get_alerts_per_day,
#     get_seller_competitive_summary,
#     get_all_sellers,
# )
# from components.metrics import render_kpi_row
# from components.charts  import competitive_position_donut, alerts_timeline_chart
# from components.tables  import render_attention_table


# # ═════════════════════════════════════════════════════════════════════════════
# # PRIVATE HELPERS
# # Homepage-specific presentation logic. Not shared with other pages.
# # ═════════════════════════════════════════════════════════════════════════════

# def _fmt_activity_event(row: dict) -> str:
#     """
#     Converts a raw alert row into a natural-language market event sentence.

#     Examples:
#         price_drop    → "Sharaf DG reduced iPhone 15 Pro Max by 5.3%"
#         price_increase→ "Virgin Megastore increased Galaxy S25 Ultra by 4.1%"
#         out_of_stock  → "iStyle iPhone 15 128GB is now out of stock"
#         back_in_stock → "Sharaf DG AirPods Pro 2 is back in stock"
#         new_competitor→ "New competitor listed: iPhone 15 128GB"

#     Keeps sentences short and scannable — no punctuation at end,
#     no technical jargon, no raw field names.
#     """
#     seller  = row.get("seller_name", "Unknown seller")
#     product = row.get("product_name", "Unknown product")
#     atype   = row.get("alert_type",  "")
#     pct     = row.get("change_pct",  0)

#     try:
#         pct_str = f"{abs(float(pct)):.1f}%"
#     except (TypeError, ValueError):
#         pct_str = ""

#     if atype == "price_drop":
#         return f"{seller} reduced {product} by {pct_str}"
#     elif atype == "price_increase":
#         return f"{seller} increased {product} by {pct_str}"
#     elif atype == "out_of_stock":
#         return f"{seller} {product} is now out of stock"
#     elif atype == "back_in_stock":
#         return f"{seller} {product} is back in stock"
#     elif atype == "new_competitor":
#         return f"New competitor listed: {product}"
#     else:
#         return f"{seller} — {product}"


# def _get_event_icon(row: dict) -> str:
#     """
#     Returns a single emoji character representing the event type.
#     Used as a visual anchor in the activity feed — one per row.

#     📉 price_drop      — market moving down, attention needed
#     📈 price_increase  — competitor raising prices (opportunity)
#     📦 out_of_stock    — availability change
#     🔄 back_in_stock   — availability restored
#     🆕 new_competitor  — new market entrant
#     ·  fallback        — neutral dot for unknown types
#     """
#     mapping = {
#         "price_drop"    : "📉",
#         "price_increase": "📈",
#         "out_of_stock"  : "📦",
#         "back_in_stock" : "🔄",
#         "new_competitor": "🆕",
#     }
#     return mapping.get(row.get("alert_type", ""), "·")


# def _fmt_event_time(ts) -> str:
#     """
#     Converts a timestamp to a human-readable relative time string.

#     Examples:
#         < 1 min  → "Just now"
#         < 1 hr   → "12 min ago"
#         < 24 hrs → "3 hrs ago"
#         < 2 days → "Yesterday"
#         else     → "Jun 14"

#     Uses UTC-aware comparison. Handles both timezone-aware and
#     naive datetimes from the database safely.
#     """
#     try:
#         now = datetime.now(timezone.utc)

#         # Normalise: if timestamp is naive, assume UTC
#         if isinstance(ts, str):
#             ts = pd.to_datetime(ts)
#         if ts.tzinfo is None:
#             ts = ts.replace(tzinfo=timezone.utc)

#         diff_secs = (now - ts).total_seconds()

#         if diff_secs < 60:
#             return "Just now"
#         elif diff_secs < 3600:
#             mins = int(diff_secs // 60)
#             return f"{mins} min ago"
#         elif diff_secs < 86400:
#             hrs = int(diff_secs // 3600)
#             return f"{hrs} hr{'s' if hrs > 1 else ''} ago"
#         elif diff_secs < 172800:
#             return "Yesterday"
#         else:
#             return ts.strftime("%b %d")
#     except Exception:
#         return ""


# # ═════════════════════════════════════════════════════════════════════════════
# # SECTION CSS
# # Page-level styles injected once on render.
# # Scoped with .ni- prefix to avoid conflicts with Streamlit's own classes.
# # ═════════════════════════════════════════════════════════════════════════════

# _HOME_CSS = """
# <style>

# /* ── Page header ──────────────────────────────────────────────────────────── */
# .ni-page-title {
#     font-size     : 26px;
#     font-weight   : 700;
#     color         : #111827;
#     letter-spacing: -0.02em;
#     margin-bottom : 4px;
#     line-height   : 1.2;
# }

# .ni-page-subtitle {
#     font-size  : 14px;
#     color      : #6B7280;
#     margin-bottom: 12px;
#     line-height: 1.5;
# }

# /* ── System status strip ──────────────────────────────────────────────────── */
# .ni-status-strip {
#     display    : flex;
#     align-items: center;
#     gap        : 16px;
#     flex-wrap  : wrap;
#     padding    : 10px 0 20px 0;
# }

# .ni-status-dot {
#     display    : flex;
#     align-items: center;
#     gap        : 6px;
#     font-size  : 12px;
#     font-weight: 500;
#     color      : #10B981;
# }

# .ni-status-dot::before {
#     content      : "●";
#     font-size    : 8px;
#     animation    : ni-pulse 2s ease-in-out infinite;
# }

# @keyframes ni-pulse {
#     0%, 100% { opacity: 1;   }
#     50%       { opacity: 0.4; }
# }

# .ni-status-stat {
#     font-size  : 12px;
#     color      : #9CA3AF;
# }

# .ni-status-stat span {
#     font-weight: 600;
#     color      : #374151;
# }

# .ni-status-divider {
#     color    : #E5E7EB;
#     font-size: 12px;
# }

# /* ── Section headings ─────────────────────────────────────────────────────── */
# .ni-section-heading {
#     font-size    : 14px;
#     font-weight  : 600;
#     color        : #111827;
#     margin-bottom: 12px;
#     margin-top   : 0;
#     letter-spacing: -0.01em;
# }

# .ni-section-divider {
#     border     : none;
#     border-top : 1px solid #F3F4F6;
#     margin     : 28px 0;
# }

# /* ── Activity feed ────────────────────────────────────────────────────────── */
# .ni-feed-item {
#     display        : flex;
#     align-items    : flex-start;
#     gap            : 12px;
#     padding        : 10px 0;
#     border-bottom  : 1px solid #F9FAFB;
# }

# .ni-feed-item:last-child {
#     border-bottom: none;
# }

# .ni-feed-icon {
#     font-size  : 16px;
#     flex-shrink: 0;
#     margin-top : 1px;
# }

# .ni-feed-text {
#     flex      : 1;
#     font-size : 13px;
#     color     : #374151;
#     line-height: 1.5;
# }

# .ni-feed-client-badge {
#     display         : inline-block;
#     font-size       : 10px;
#     font-weight     : 600;
#     color           : #2563EB;
#     background      : #EFF6FF;
#     border-radius   : 4px;
#     padding         : 1px 6px;
#     margin-left     : 6px;
#     vertical-align  : middle;
# }

# .ni-feed-time {
#     font-size  : 11px;
#     color      : #9CA3AF;
#     flex-shrink: 0;
#     margin-top : 2px;
# }

# /* ── Seller summary table ─────────────────────────────────────────────────── */
# .ni-seller-row {
#     display        : flex;
#     align-items    : center;
#     justify-content: space-between;
#     padding        : 10px 0;
#     border-bottom  : 1px solid #F9FAFB;
#     font-size      : 13px;
# }

# .ni-seller-row:last-child {
#     border-bottom: none;
# }

# .ni-seller-name {
#     color      : #374151;
#     font-weight: 500;
# }

# .ni-seller-client-tag {
#     font-size      : 10px;
#     font-weight    : 600;
#     color          : #2563EB;
#     background     : #EFF6FF;
#     border-radius  : 4px;
#     padding        : 1px 6px;
#     margin-left    : 8px;
# }

# .ni-seller-bar-wrap {
#     display    : flex;
#     align-items: center;
#     gap        : 8px;
#     flex       : 1;
#     max-width  : 180px;
#     margin     : 0 16px;
# }

# .ni-seller-bar-bg {
#     flex          : 1;
#     height        : 6px;
#     background    : #F3F4F6;
#     border-radius : 99px;
#     overflow      : hidden;
# }

# .ni-seller-bar-fill {
#     height       : 6px;
#     border-radius: 99px;
# }

# .ni-seller-count {
#     font-size  : 13px;
#     font-weight: 600;
#     color      : #111827;
#     min-width  : 20px;
#     text-align : right;
# }

# </style>
# """


# # ═════════════════════════════════════════════════════════════════════════════
# # RENDER
# # ═════════════════════════════════════════════════════════════════════════════

# def render() -> None:
#     """
#     Entry point called by app.py when user navigates to Dashboard.
#     Fetches all data, then renders each section top to bottom.
#     """

#     # ── Inject page CSS ───────────────────────────────────────────────────────
#     st.markdown(_HOME_CSS, unsafe_allow_html=True)

#     # ── Fetch all data upfront ────────────────────────────────────────────────
#     # Collected at the top so every section renders from already-fetched data.
#     # No query is called inside a section — keeps section code readable.
#     active_products    = get_active_product_count()
#     unseen_alerts      = get_unseen_alert_count()
#     losing_count       = get_products_losing_position_count()
#     position_summary   = get_competitive_position_summary()
#     attention_data     = get_products_requiring_attention(limit=5)
#     recent_events      = get_recent_market_events(limit=10)
#     alerts_per_day     = get_alerts_per_day()
#     seller_summary     = get_seller_competitive_summary()
#     all_sellers        = get_all_sellers()

#     # Derived values used across multiple sections
#     total_sellers      = len(all_sellers)
#     cheapest_count     = position_summary.get("cheapest", 0)
#     highest_gap_pct    = (
#         max((float(r.get("gap_pct", 0)) for r in attention_data), default=0)
#         if attention_data else 0
#     )

#     # ─────────────────────────────────────────────────────────────────────────
#     # SECTION 0 — Page Header + System Status Strip
#     # ─────────────────────────────────────────────────────────────────────────

#     st.markdown("""
#         <div class="ni-page-title">Market Intelligence Overview</div>
#         <div class="ni-page-subtitle">
#             Monitor pricing movements, competitive position,
#             and market activity across tracked sellers.
#         </div>
#     """, unsafe_allow_html=True)

#     # System status strip — compact, muted, always visible
#     # Snapshot count is a fixed demo value since we don't expose it via query.
#     # In production this would come from COUNT(price_snapshots).
#     total_alerts = sum(
#         r.get("alert_count", 0) for r in alerts_per_day
#     )

#     # Snapshot count: use real total from alerts_per_day as a proxy,
#     # or hardcode 1200 for the demo since active_products * total_sellers = 40
#     # which is wrong. In production replace with get_snapshot_count() query.
#     snapshot_count = 1200

#     st.markdown(f"""
#         <div class="ni-status-strip">
#             <div class="ni-status-dot">Monitoring Active</div>
#             <div class="ni-status-divider">|</div>
#             <div class="ni-status-stat"><span>{snapshot_count:,}</span> Snapshots</div>
#             <div class="ni-status-divider">|</div>
#             <div class="ni-status-stat"><span>{active_products}</span> Products</div>
#             <div class="ni-status-divider">|</div>
#             <div class="ni-status-stat"><span>{total_sellers}</span> Sellers</div>
#             <div class="ni-status-divider">|</div>
#             <div class="ni-status-stat"><span>{total_alerts}</span> Alerts Generated</div>
#         </div>
#     """, unsafe_allow_html=True)

#     # ─────────────────────────────────────────────────────────────────────────
#     # SECTION 1 — KPI Cards
#     # ─────────────────────────────────────────────────────────────────────────

#     render_kpi_row([
#         {
#             "label"        : "Products Tracked",
#             "value"        : active_products,
#             "subtitle"     : f"Across {total_sellers} sellers",
#             "accent_color" : "#2563EB",
#             "icon"         : "◈",
#         },
#         {
#             "label"        : "Unseen Alerts",
#             "value"        : unseen_alerts,
#             "subtitle"     : "Awaiting review",
#             "accent_color" : "#EF4444" if unseen_alerts > 0 else "#10B981",
#             "icon"         : "🔔",
#         },
#         {
#             "label"        : "Products Undercut",
#             "value"        : losing_count,
#             "subtitle"     : (
#                 f"Highest gap: {highest_gap_pct:.1f}%"
#                 if losing_count > 0 else "No undercutting detected"
#             ),
#             "accent_color" : "#EF4444" if losing_count > 0 else "#10B981",
#             "icon"         : "↓",
#         },
#         {
#             "label"        : "Cheapest Position",
#             "value"        : cheapest_count,
#             "subtitle"     : f"Leading on {cheapest_count} of {active_products} products",
#             "accent_color" : "#10B981" if cheapest_count > 0 else "#F59E0B",
#             "icon"         : "✓",
#         },
#     ])

#     # ─────────────────────────────────────────────────────────────────────────
#     # SECTION 2 — Competitive Snapshot (donut + attention table)
#     # ─────────────────────────────────────────────────────────────────────────

#     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)

#     col_left, col_right = st.columns([1, 1.4], gap="large")

#     with col_left:
#         st.markdown(
#             '<p class="ni-section-heading">Market Position Overview</p>',
#             unsafe_allow_html=True,
#         )
#         fig = competitive_position_donut(position_summary)
#         st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

#     with col_right:
#         st.markdown(
#             '<p class="ni-section-heading">Products Requiring Attention</p>',
#             unsafe_allow_html=True,
#         )
#         attention_df = pd.DataFrame(attention_data)
#         render_attention_table(attention_df)

#     # ─────────────────────────────────────────────────────────────────────────
#     # SECTION 3 — Recent Market Activity Feed
#     # ─────────────────────────────────────────────────────────────────────────

#     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
#     st.markdown(
#         '<p class="ni-section-heading">Recent Market Activity</p>',
#         unsafe_allow_html=True,
#     )

#     if not recent_events:
#         st.caption("No recent activity to display.")
#     else:
#         # FIX: render each feed item as a separate st.markdown() call.
#         # Joining all items into one big HTML string causes Streamlit's
#         # markdown renderer to stop processing unsafe HTML mid-block
#         # when emojis (📉, 📈 etc.) appear inside the f-string.
#         # One call per item avoids this entirely.
#         st.markdown('<div class="ni-feed-container">', unsafe_allow_html=True)

#         for row in recent_events:
#             icon      = _get_event_icon(row)
#             text      = _fmt_activity_event(row)
#             time_str  = _fmt_event_time(row.get("triggered_at"))
#             is_client = bool(row.get("is_client", False))

#             badge_html = (
#                 '<span class="ni-feed-client-badge">Your store</span>'
#                 if is_client else ""
#             )

#             # Icon rendered as plain text in its own column to avoid
#             # emoji-in-f-string HTML parser issues
#             col_icon, col_text, col_time = st.columns([0.04, 0.86, 0.10])

#             with col_icon:
#                 st.markdown(
#                     f"<div class='ni-feed-icon'>{icon}</div>",
#                     unsafe_allow_html=True,
#                 )
#             with col_text:
#                 st.markdown(
#                     f"<div class='ni-feed-text'>{text}{badge_html}</div>",
#                     unsafe_allow_html=True,
#                 )
#             with col_time:
#                 st.markdown(
#                     f"<div class='ni-feed-time'>{time_str}</div>",
#                     unsafe_allow_html=True,
#                 )

#         st.markdown('</div>', unsafe_allow_html=True)

#     # ─────────────────────────────────────────────────────────────────────────
#     # SECTION 4 — Competitor Activity Chart
#     # ─────────────────────────────────────────────────────────────────────────

#     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
#     st.markdown(
#         '<p class="ni-section-heading">Competitor Activity</p>',
#         unsafe_allow_html=True,
#     )

#     if not alerts_per_day:
#         st.caption("No alert data available.")
#     else:
#         activity_df = pd.DataFrame(alerts_per_day)
#         # Rename columns to match what alerts_timeline_chart() expects
#         activity_df = activity_df.rename(columns={
#             "alert_date" : "run_at",
#             "alert_count": "alerts_triggered",
#         })
#         fig = alerts_timeline_chart(activity_df)
#         st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

#     # ─────────────────────────────────────────────────────────────────────────
#     # SECTION 5 — Seller Competitive Summary
#     # ─────────────────────────────────────────────────────────────────────────

#     st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
#     st.markdown(
#         '<p class="ni-section-heading">Seller Competitive Summary</p>',
#         unsafe_allow_html=True,
#     )

#     if not seller_summary:
#         st.caption("No seller data available.")
#     else:
#         max_leading = max(
#             (int(r.get("leading_on", 0)) for r in seller_summary), default=1
#         )
#         max_leading = max(max_leading, 1)

#         # FIX: render each seller row as a separate st.markdown() call.
#         # Same root cause as the feed — large joined HTML strings with
#         # special characters cause Streamlit's parser to escape mid-block.
#         for row in seller_summary:
#             name       = row.get("store_name", "")
#             is_client  = bool(row.get("is_client", False))
#             leading_on = int(row.get("leading_on", 0))
#             bar_pct    = int((leading_on / max_leading) * 100)
#             bar_color  = "#2563EB" if is_client else "#D1D5DB"
#             client_tag = (
#                 '<span class="ni-seller-client-tag">You</span>'
#                 if is_client else ""
#             )

#             st.markdown(f"""
#                 <div class="ni-seller-row">
#                     <div class="ni-seller-name">
#                         {name}{client_tag}
#                     </div>
#                     <div class="ni-seller-bar-wrap">
#                         <div class="ni-seller-bar-bg">
#                             <div class="ni-seller-bar-fill"
#                                  style="width:{bar_pct}%;
#                                         background:{bar_color};">
#                             </div>
#                         </div>
#                     </div>
#                     <div class="ni-seller-count">{leading_on}</div>
#                 </div>
#             """, unsafe_allow_html=True)

#         st.markdown(
#             "<p style='font-size:11px; color:#9CA3AF; margin-top:8px;'>"
#             "Number of products each seller currently offers at the lowest price.</p>",
#             unsafe_allow_html=True,
#         )

#     # ── Bottom padding ────────────────────────────────────────────────────────
#     st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

# ─── views/home.py ───────────────────────────────────────────────────────────
# Market Intelligence Overview — the command-centre homepage.
#
# Sections:
#   0. Page header + system status strip
#   1. KPI cards (4 cards)
#   2. Competitive snapshot (donut + attention table, two columns)
#   3. Recent market activity feed
#   4. Competitor activity chart
#   5. Seller competitive summary table
#
# This file never imports from db.py or touches SQL directly.
# All data comes from queries.py. All charts come from components/charts.py.
# All tables come from components/tables.py. KPI cards from components/metrics.py.
#
# Private helpers (_fmt_activity_event, _get_event_icon, _fmt_event_time)
# live here because they are homepage-specific presentation logic —
# not reusable UI components.
# ─────────────────────────────────────────────────────────────────────────────
print("Home import started")
# import sys, os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from queries import (
    get_active_product_count,
    get_unseen_alert_count,
    get_products_losing_position_count,
    get_competitive_position_summary,
    get_products_requiring_attention,
    get_recent_market_events,
    get_alerts_per_day,
    get_seller_competitive_summary,
    get_all_sellers,
)
from components.metrics import render_kpi_row
from components.charts  import competitive_position_donut, alerts_timeline_chart
from components.tables  import render_attention_table


# ═════════════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# Homepage-specific presentation logic. Not shared with other pages.
# ═════════════════════════════════════════════════════════════════════════════

def _fmt_activity_event(row: dict) -> str:
    """
    Converts a raw alert row into a natural-language market event sentence.

    Examples:
        price_drop    → "Sharaf DG reduced iPhone 15 Pro Max by 5.3%"
        price_increase→ "Virgin Megastore increased Galaxy S25 Ultra by 4.1%"
        out_of_stock  → "iStyle iPhone 15 128GB is now out of stock"
        back_in_stock → "Sharaf DG AirPods Pro 2 is back in stock"
        new_competitor→ "New competitor listed: iPhone 15 128GB"

    Keeps sentences short and scannable — no punctuation at end,
    no technical jargon, no raw field names.
    """
    seller  = row.get("seller_name", "Unknown seller")
    product = row.get("product_name", "Unknown product")
    atype   = row.get("alert_type",  "")
    pct     = row.get("change_pct",  0)

    try:
        pct_str = f"{abs(float(pct)):.1f}%"
    except (TypeError, ValueError):
        pct_str = ""

    if atype == "price_drop":
        return f"{seller} reduced {product} by {pct_str}"
    elif atype == "price_increase":
        return f"{seller} increased {product} by {pct_str}"
    elif atype == "out_of_stock":
        return f"{seller} {product} is now out of stock"
    elif atype == "back_in_stock":
        return f"{seller} {product} is back in stock"
    elif atype == "new_competitor":
        return f"New competitor listed: {product}"
    else:
        return f"{seller} — {product}"


def _get_event_icon(row: dict) -> str:
    """
    Returns a single emoji character representing the event type.
    Used as a visual anchor in the activity feed — one per row.

    📉 price_drop      — market moving down, attention needed
    📈 price_increase  — competitor raising prices (opportunity)
    📦 out_of_stock    — availability change
    🔄 back_in_stock   — availability restored
    🆕 new_competitor  — new market entrant
    ·  fallback        — neutral dot for unknown types
    """
    mapping = {
        "price_drop"    : "📉",
        "price_increase": "📈",
        "out_of_stock"  : "📦",
        "back_in_stock" : "🔄",
        "new_competitor": "🆕",
    }
    return mapping.get(row.get("alert_type", ""), "·")


def _fmt_event_time(ts) -> str:
    """
    Converts a timestamp to a human-readable relative time string.

    Examples:
        < 1 min  → "Just now"
        < 1 hr   → "12 min ago"
        < 24 hrs → "3 hrs ago"
        < 2 days → "Yesterday"
        else     → "Jun 14"

    Uses UTC-aware comparison. Handles both timezone-aware and
    naive datetimes from the database safely.
    """
    try:
        now = datetime.now(timezone.utc)

        # Normalise: if timestamp is naive, assume UTC
        if isinstance(ts, str):
            ts = pd.to_datetime(ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        diff_secs = (now - ts).total_seconds()

        if diff_secs < 60:
            return "Just now"
        elif diff_secs < 3600:
            mins = int(diff_secs // 60)
            return f"{mins} min ago"
        elif diff_secs < 86400:
            hrs = int(diff_secs // 3600)
            return f"{hrs} hr{'s' if hrs > 1 else ''} ago"
        elif diff_secs < 172800:
            return "Yesterday"
        else:
            return ts.strftime("%b %d")
    except Exception:
        return ""


# # ═════════════════════════════════════════════════════════════════════════════
# # SECTION CSS
# # Page-level styles injected once on render.
# # Scoped with .ni- prefix to avoid conflicts with Streamlit's own classes.
# # ═════════════════════════════════════════════════════════════════════════════

_HOME_CSS = """
<style>

/* ── Page header ──────────────────────────────────────────────────────────── */
.ni-page-title {
    font-size     : 26px;
    font-weight   : 700;
    color         : #111827;
    letter-spacing: -0.02em;
    margin-bottom : 4px;
    line-height   : 1.2;
}

.ni-page-subtitle {
    font-size  : 14px;
    color      : #6B7280;
    margin-bottom: 12px;
    line-height: 1.5;
}

/* ── System status strip ──────────────────────────────────────────────────── */
.ni-status-strip {
    display    : flex;
    align-items: center;
    gap        : 16px;
    flex-wrap  : wrap;
    padding    : 10px 0 20px 0;
}

.ni-status-dot {
    display    : flex;
    align-items: center;
    gap        : 6px;
    font-size  : 12px;
    font-weight: 500;
    color      : #10B981;
}

.ni-status-dot::before {
    content      : "●";
    font-size    : 8px;
    animation    : ni-pulse 2s ease-in-out infinite;
}

@keyframes ni-pulse {
    0%, 100% { opacity: 1;   }
    50%       { opacity: 0.4; }
}

.ni-status-stat {
    font-size  : 12px;
    color      : #9CA3AF;
}

.ni-status-stat span {
    font-weight: 600;
    color      : #374151;
}

.ni-status-divider {
    color    : #E5E7EB;
    font-size: 12px;
}

/* ── Section headings ─────────────────────────────────────────────────────── */
.ni-section-heading {
    font-size    : 14px;
    font-weight  : 600;
    color        : #111827;
    margin-bottom: 12px;
    margin-top   : 0;
    letter-spacing: -0.01em;
}

.ni-section-divider {
    border     : none;
    border-top : 1px solid #F3F4F6;
    margin     : 28px 0;
}

/* ── Activity feed ────────────────────────────────────────────────────────── */
.ni-feed-item {
    display        : flex;
    align-items    : flex-start;
    gap            : 12px;
    padding        : 10px 0;
    border-bottom  : 1px solid #F9FAFB;
}

.ni-feed-item:last-child {
    border-bottom: none;
}

.ni-feed-icon {
    font-size  : 16px;
    flex-shrink: 0;
    margin-top : 1px;
}

.ni-feed-text {
    flex      : 1;
    font-size : 13px;
    color     : #374151;
    line-height: 1.5;
}

.ni-feed-client-badge {
    display         : inline-block;
    font-size       : 10px;
    font-weight     : 600;
    color           : #2563EB;
    background      : #EFF6FF;
    border-radius   : 4px;
    padding         : 1px 6px;
    margin-left     : 6px;
    vertical-align  : middle;
}

.ni-feed-time {
    font-size  : 11px;
    color      : #9CA3AF;
    flex-shrink: 0;
    margin-top : 2px;
}

/* ── Seller summary table ─────────────────────────────────────────────────── */
.ni-seller-row {
    display        : flex;
    align-items    : center;
    justify-content: space-between;
    padding        : 10px 0;
    border-bottom  : 1px solid #F9FAFB;
    font-size      : 13px;
}

.ni-seller-row:last-child {
    border-bottom: none;
}

.ni-seller-name {
    color      : #374151;
    font-weight: 500;
}

.ni-seller-client-tag {
    font-size      : 10px;
    font-weight    : 600;
    color          : #2563EB;
    background     : #EFF6FF;
    border-radius  : 4px;
    padding        : 1px 6px;
    margin-left    : 8px;
}

.ni-seller-bar-wrap {
    display    : flex;
    align-items: center;
    gap        : 8px;
    flex       : 1;
    max-width  : 180px;
    margin     : 0 16px;
}

.ni-seller-bar-bg {
    flex          : 1;
    height        : 6px;
    background    : #F3F4F6;
    border-radius : 99px;
    overflow      : hidden;
}

.ni-seller-bar-fill {
    height       : 6px;
    border-radius: 99px;
}

.ni-seller-count {
    font-size  : 13px;
    font-weight: 600;
    color      : #111827;
    min-width  : 20px;
    text-align : right;
}

</style>
"""


# ═════════════════════════════════════════════════════════════════════════════
# RENDER
# ═════════════════════════════════════════════════════════════════════════════

def render() -> None:
    """
    Entry point called by app.py when user navigates to Dashboard.
    Fetches all data, then renders each section top to bottom.
    """

    # ── Inject page CSS ───────────────────────────────────────────────────────
    st.markdown(_HOME_CSS, unsafe_allow_html=True)

    # ── Fetch all data upfront ────────────────────────────────────────────────
    # Collected at the top so every section renders from already-fetched data.
    # No query is called inside a section — keeps section code readable.
    active_products    = get_active_product_count()
    unseen_alerts      = get_unseen_alert_count()
    losing_count       = get_products_losing_position_count()
    position_summary   = get_competitive_position_summary()
    attention_data     = get_products_requiring_attention(limit=5)
    recent_events      = get_recent_market_events(limit=10)
    alerts_per_day     = get_alerts_per_day()
    seller_summary     = get_seller_competitive_summary()
    all_sellers        = get_all_sellers()

    # Derived values used across multiple sections
    total_sellers      = len(all_sellers)
    cheapest_count     = position_summary.get("cheapest", 0)
    highest_gap_pct    = (
        max((float(r.get("gap_pct", 0)) for r in attention_data), default=0)
        if attention_data else 0
    )

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 0 — Page Header + System Status Strip
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown("""
        <div class="ni-page-title">Market Intelligence Overview</div>
        <div class="ni-page-subtitle">
            Monitor pricing movements, competitive position,
            and market activity across tracked sellers.
        </div>
    """, unsafe_allow_html=True)

    # System status strip — compact, muted, always visible
    # Snapshot count is a fixed demo value since we don't expose it via query.
    # In production this would come from COUNT(price_snapshots).
    total_alerts = sum(
        r.get("alert_count", 0) for r in alerts_per_day
    )

    # Snapshot count: use real total from alerts_per_day as a proxy,
    # or hardcode 1200 for the demo since active_products * total_sellers = 40
    # which is wrong. In production replace with get_snapshot_count() query.
    snapshot_count = 1200

    st.markdown(f"""
        <div class="ni-status-strip">
            <div class="ni-status-dot">Monitoring Active</div>
            <div class="ni-status-divider">|</div>
            <div class="ni-status-stat"><span>{snapshot_count:,}</span> Snapshots</div>
            <div class="ni-status-divider">|</div>
            <div class="ni-status-stat"><span>{active_products}</span> Products</div>
            <div class="ni-status-divider">|</div>
            <div class="ni-status-stat"><span>{total_sellers}</span> Sellers</div>
            <div class="ni-status-divider">|</div>
            <div class="ni-status-stat"><span>{total_alerts}</span> Alerts Generated</div>
        </div>
    """, unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 1 — KPI Cards
    # ─────────────────────────────────────────────────────────────────────────

    render_kpi_row([
        {
            "label"        : "Products Tracked",
            "value"        : active_products,
            "subtitle"     : f"Across {total_sellers} sellers",
            "accent_color" : "#2563EB",
            "icon"         : "◈",
        },
        {
            "label"        : "Unseen Alerts",
            "value"        : unseen_alerts,
            "subtitle"     : "Awaiting review",
            "accent_color" : "#EF4444" if unseen_alerts > 0 else "#10B981",
            "icon"         : "🔔",
        },
        {
            "label"        : "Products Undercut",
            "value"        : losing_count,
            "subtitle"     : (
                f"Highest gap: {highest_gap_pct:.1f}%"
                if losing_count > 0 else "No undercutting detected"
            ),
            "accent_color" : "#EF4444" if losing_count > 0 else "#10B981",
            "icon"         : "↓",
        },
        {
            "label"        : "Cheapest Position",
            "value"        : cheapest_count,
            "subtitle"     : f"Leading on {cheapest_count} of {active_products} products",
            "accent_color" : "#10B981" if cheapest_count > 0 else "#F59E0B",
            "icon"         : "✓",
        },
    ])

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 2 — Competitive Snapshot (donut + attention table)
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1.4], gap="large")

    with col_left:
        st.markdown(
            '<p class="ni-section-heading">Market Position Overview</p>',
            unsafe_allow_html=True,
        )
        fig = competitive_position_donut(position_summary)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_right:
        st.markdown(
            '<p class="ni-section-heading">Products Requiring Attention</p>',
            unsafe_allow_html=True,
        )
        attention_df = pd.DataFrame(attention_data)
        render_attention_table(attention_df)

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 3 — Recent Market Activity Feed
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
    st.markdown(
        '<p class="ni-section-heading">Recent Market Activity</p>',
        unsafe_allow_html=True,
    )

    if not recent_events:
        st.caption("No recent activity to display.")
    else:
        # FIX: render each feed item as a separate st.markdown() call.
        # Joining all items into one big HTML string causes Streamlit's
        # markdown renderer to stop processing unsafe HTML mid-block
        # when emojis (📉, 📈 etc.) appear inside the f-string.
        # One call per item avoids this entirely.
        st.markdown('<div class="ni-feed-container">', unsafe_allow_html=True)

        for row in recent_events:
            icon      = _get_event_icon(row)
            text      = _fmt_activity_event(row)
            time_str  = _fmt_event_time(row.get("triggered_at"))
            is_client = bool(row.get("is_client", False))

            badge_html = (
                '<span class="ni-feed-client-badge">Your store</span>'
                if is_client else ""
            )

            # Icon rendered as plain text in its own column to avoid
            # emoji-in-f-string HTML parser issues
            col_icon, col_text, col_time = st.columns([0.04, 0.86, 0.10])

            with col_icon:
                st.markdown(
                    f"<div class='ni-feed-icon'>{icon}</div>",
                    unsafe_allow_html=True,
                )
            with col_text:
                st.markdown(
                    f"<div class='ni-feed-text'>{text}{badge_html}</div>",
                    unsafe_allow_html=True,
                )
            with col_time:
                st.markdown(
                    f"<div class='ni-feed-time'>{time_str}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown('</div>', unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 4 — Competitor Activity Chart
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
    st.markdown(
        '<p class="ni-section-heading">Competitor Activity</p>',
        unsafe_allow_html=True,
    )

    if not alerts_per_day:
        st.caption("No alert data available.")
    else:
        activity_df = pd.DataFrame(alerts_per_day)
        # Rename columns to match what alerts_timeline_chart() expects
        activity_df = activity_df.rename(columns={
            "alert_date" : "run_at",
            "alert_count": "alerts_triggered",
        })
        fig = alerts_timeline_chart(activity_df)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION 5 — Seller Competitive Summary
    # ─────────────────────────────────────────────────────────────────────────

    st.markdown('<hr class="ni-section-divider">', unsafe_allow_html=True)
    st.markdown(
        '<p class="ni-section-heading">Seller Competitive Summary</p>',
        unsafe_allow_html=True,
    )

    if not seller_summary:
        st.caption("No seller data available.")
    else:
        max_leading = max(
            (int(r.get("leading_on", 0)) for r in seller_summary), default=1
        )
        max_leading = max(max_leading, 1)

        # FIX: render each seller row as a separate st.markdown() call.
        # Same root cause as the feed — large joined HTML strings with
        # special characters cause Streamlit's parser to escape mid-block.
        for row in seller_summary:
            name       = row.get("store_name", "")
            is_client  = bool(row.get("is_client", False))
            leading_on = int(row.get("leading_on", 0))
            bar_pct    = int((leading_on / max_leading) * 100)
            bar_color  = "#2563EB" if is_client else "#D1D5DB"
            client_tag = (
                '<span class="ni-seller-client-tag">You</span>'
                if is_client else ""
            )

            st.markdown(f"""
                <div class="ni-seller-row">
                    <div class="ni-seller-name">
                        {name}{client_tag}
                    </div>
                    <div class="ni-seller-bar-wrap">
                        <div class="ni-seller-bar-bg">
                            <div class="ni-seller-bar-fill"
                                 style="width:{bar_pct}%;
                                        background:{bar_color};">
                            </div>
                        </div>
                    </div>
                    <div class="ni-seller-count">{leading_on}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown(
            "<p style='font-size:11px; color:#9CA3AF; margin-top:8px;'>"
            "Number of products each seller currently offers at the lowest price.</p>",
            unsafe_allow_html=True,
        )

    # ── Bottom padding ────────────────────────────────────────────────────────
    st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)


print("Home import completed")