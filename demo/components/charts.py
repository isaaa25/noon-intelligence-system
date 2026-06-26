# # ─── components/charts.py ────────────────────────────────────────────────────
# # Every Plotly figure in the Noon Intelligence dashboard is built here.
# # Pages never import Plotly directly — they call a function and get a figure.
# #
# # Pattern:
# #   fig = price_history_chart(df)
# #   st.plotly_chart(fig, use_container_width=True)
# #
# # Color logic is always driven by is_client flag — never by seller name.
# # This keeps the app resellable: swap the client, colors follow automatically.
# #
# # Shared styling is defined once in _base_layout() and applied to every chart.
# #
# # Chart inventory:
# #   1. price_history_chart()     — hero line chart, Product Detail page
# #   2. competitive_position_donut() — donut, Dashboard + Market Position
# #   3. market_position_bar()     — horizontal bar, Market Position page
# #   4. alerts_by_date_chart()    — bar by calendar day, Dashboard homepage
# #   5. scrape_activity_chart()   — bar by scrape run, System Health page
# #   6. price_position_bar()      — vertical bar, Product Detail page
# #
# # Note: charts 4 and 5 look similar but tell different stories.
# #   alerts_by_date_chart()  → market events per day (homepage)
# #   scrape_activity_chart() → scraper run history (system health)
# # ─────────────────────────────────────────────────────────────────────────────

# import pandas as pd
# import plotly.graph_objects as go


# # ─── Design Tokens ───────────────────────────────────────────────────────────
# CLIENT_COLOR     = "#2563EB"   # Blue  — always the client's line/bar
# COMPETITOR_COLOR = "#D1D5DB"   # Light grey — competitors are context
# DANGER_COLOR     = "#EF4444"   # Red   — alerts, drops, overpriced
# SUCCESS_COLOR    = "#10B981"   # Green — cheapest, healthy, in stock
# WARNING_COLOR    = "#F59E0B"   # Amber — competitive, warning
# NEUTRAL_COLOR    = "#6B7280"   # Grey  — secondary text, subtle elements
# FONT_FAMILY      = "Inter, ui-sans-serif, system-ui, sans-serif"


# # ─── Private: Base Layout ────────────────────────────────────────────────────
# def _base_layout(title: str = "", height: int = 380) -> dict:
#     """
#     Shared Plotly layout applied to every chart.
#     Individual chart functions call this and update with chart-specific keys.

#     Establishes:
#     - White background (cards sit on #F8FAFC page, chart inside is white)
#     - Inter font stack
#     - Clean axis styling — no spines, subtle gridlines
#     - Legend at bottom to maximise chart area
#     - Consistent hover styling
#     """
#     return dict(
#         title=dict(
#             text    = title,
#             font    = dict(family=FONT_FAMILY, size=14, color="#111827"),
#             x       = 0,
#             xanchor = "left",
#             pad     = dict(l=0, t=0),
#         ),
#         height        = height,
#         paper_bgcolor = "#FFFFFF",
#         plot_bgcolor  = "#FFFFFF",
#         font          = dict(family=FONT_FAMILY, size=12, color="#6B7280"),
#         margin        = dict(l=0, r=0, t=40, b=0),
#         legend        = dict(
#             orientation = "h",
#             yanchor     = "bottom",
#             y           = -0.25,
#             xanchor     = "left",
#             x           = 0,
#             font        = dict(size=12, color="#6B7280"),
#             bgcolor     = "rgba(0,0,0,0)",
#         ),
#         hoverlabel    = dict(
#             bgcolor     = "#1F2937",
#             font_size   = 13,
#             font_color  = "#F9FAFB",
#             bordercolor = "#1F2937",
#         ),
#         xaxis         = dict(
#             showgrid  = False,
#             showline  = False,
#             tickfont  = dict(size=11, color="#9CA3AF"),
#             tickcolor = "rgba(0,0,0,0)",
#         ),
#         yaxis         = dict(
#             showgrid  = True,
#             gridcolor = "#F3F4F6",
#             gridwidth = 1,
#             showline  = False,
#             zeroline  = False,
#             tickfont  = dict(size=11, color="#9CA3AF"),
#             tickcolor = "rgba(0,0,0,0)",
#         ),
#     )


# # ─── 1. Price History Line Chart ──────────────────────────────────────────────
# def price_history_chart(df: pd.DataFrame) -> go.Figure:
#     """
#     Hero chart — price over time for one product across all sellers.
#     Client line: blue, 3px width, fully opaque.
#     Competitor lines: light grey, 1.5px width.
#     This contrast makes the client the visual focus; competitors are context.

#     bool() cast on is_client prevents silent failures when PostgreSQL
#     returns numpy.bool_ instead of Python bool.

#     Expected df columns:
#         scraped_at    : datetime
#         seller_name   : str
#         current_price : float
#         is_client     : bool
#         stock_status  : str
#     """
#     fig = go.Figure()

#     for seller in df["seller_name"].unique():
#         seller_df = df[df["seller_name"] == seller].copy()
#         is_client = bool(seller_df["is_client"].iloc[0])

#         # Gap in line where stock_status = out_of_stock communicates
#         # unavailability more clearly than a zero or flat line.
#         seller_df.loc[
#             seller_df["stock_status"] == "out_of_stock", "current_price"
#         ] = None

#         fig.add_trace(go.Scatter(
#             x             = seller_df["scraped_at"],
#             y             = seller_df["current_price"],
#             name          = seller,
#             mode          = "lines",
#             line          = dict(
#                 color = CLIENT_COLOR if is_client else COMPETITOR_COLOR,
#                 width = 3 if is_client else 1.5,
#                 dash  = "solid",
#             ),
#             opacity       = 1.0 if is_client else 0.8,
#             connectgaps   = False,
#             hovertemplate = (
#                 f"<b>{seller}</b><br>"
#                 "%{x|%b %d, %Y}<br>"
#                 "AED %{y:,.2f}"
#                 "<extra></extra>"
#             ),
#         ))

#     layout = _base_layout(height=400)
#     layout["yaxis"].update(tickprefix="AED ", tickformat=",.0f")
#     layout["xaxis"].update(tickformat="%b %d")
#     fig.update_layout(**layout)
#     return fig


# # ─── 2. Competitive Position Donut ───────────────────────────────────────────
# def competitive_position_donut(summary: dict) -> go.Figure:
#     """
#     Donut chart: how many client products are Cheapest / Competitive / Overpriced.
#     Center annotation shows total count + "Products" label on two lines.

#     Expected summary keys: cheapest, competitive, overpriced
#     """
#     values = [
#         summary.get("cheapest",    0),
#         summary.get("competitive", 0),
#         summary.get("overpriced",  0),
#     ]
#     total = sum(values)

#     fig = go.Figure(go.Pie(
#         labels        = ["Cheapest", "Competitive", "Overpriced"],
#         values        = values,
#         hole          = 0.65,
#         marker        = dict(
#             colors = [SUCCESS_COLOR, CLIENT_COLOR, DANGER_COLOR],
#             line   = dict(color="#FFFFFF", width=2),
#         ),
#         textinfo      = "none",
#         hovertemplate = (
#             "<b>%{label}</b><br>"
#             "%{value} products<br>"
#             "%{percent}"
#             "<extra></extra>"
#         ),
#     ))

#     fig.add_annotation(
#         text      = f"<b>{total}</b><br><span style='font-size:11px'>Products</span>",
#         x=0.5, y=0.5, xref="paper", yref="paper",
#         showarrow = False,
#         font      = dict(size=22, color="#111827", family=FONT_FAMILY),
#         align     = "center",
#     )

#     layout = _base_layout(height=300)
#     layout.pop("xaxis", None)
#     layout.pop("yaxis", None)
#     layout["margin"] = dict(l=0, r=0, t=40, b=0)
#     fig.update_layout(**layout)
#     return fig


# # ─── 3. Market Position Bar Chart ────────────────────────────────────────────
# def market_position_bar(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
#     """
#     Horizontal grouped bar chart — price comparison across sellers.
#     Sorted by client gap descending: most urgent products at top.

#     top_n: pass None for full list (Market Position page).
#            Default 10 limits visual noise on the homepage.

#     dropna() before head(top_n) prevents NaN gap rows consuming slots
#     when a product has no competitors in the latest snapshot window.

#     Expected df columns:
#         product_name  : str
#         seller_name   : str
#         current_price : float
#         is_client     : bool
#     """
#     if df.empty:
#         return go.Figure()

#     if top_n:
#         client_prices = (
#             df[df["is_client"] == True][["product_name", "current_price"]]
#             .rename(columns={"current_price": "client_price"})
#         )
#         comp_min = (
#             df[df["is_client"] == False]
#             .groupby("product_name")["current_price"]
#             .min()
#             .reset_index()
#             .rename(columns={"current_price": "min_comp_price"})
#         )
#         ranked = client_prices.merge(comp_min, on="product_name", how="left")
#         ranked["gap"] = ranked["client_price"] - ranked["min_comp_price"]
#         top_products = (
#             ranked
#             .dropna(subset=["gap"])
#             .sort_values("gap", ascending=False)
#             .head(top_n)["product_name"]
#             .tolist()
#         )
#         df = df[df["product_name"].isin(top_products)]

#     fig = go.Figure()

#     for seller in df["seller_name"].unique():
#         seller_df = df[df["seller_name"] == seller]
#         is_client = bool(seller_df["is_client"].iloc[0])

#         fig.add_trace(go.Bar(
#             name          = seller,
#             x             = seller_df["current_price"],
#             y             = seller_df["product_name"],
#             orientation   = "h",
#             marker_color  = CLIENT_COLOR if is_client else COMPETITOR_COLOR,
#             hovertemplate = (
#                 f"<b>{seller}</b><br>%{{y}}<br>AED %{{x:,.0f}}"
#                 "<extra></extra>"
#             ),
#         ))

#     layout = _base_layout(
#         height=max(300, len(df["product_name"].unique()) * 50)
#     )
#     layout["barmode"] = "group"
#     layout["xaxis"].update(
#         tickprefix="AED ", tickformat=",.0f",
#         showgrid=True, gridcolor="#F3F4F6",
#     )
#     layout["yaxis"].update(showgrid=False, automargin=True)
#     layout["margin"] = dict(l=0, r=0, t=40, b=0)
#     fig.update_layout(**layout)
#     return fig


# # ─── 4. Alerts by Date Chart (Homepage) ──────────────────────────────────────
# def alerts_by_date_chart(df: pd.DataFrame) -> go.Figure:
#     """
#     Bar chart of market alerts per CALENDAR DAY.
#     Lives on the Dashboard homepage — tells the market activity story.

#     One bar per day that had at least one alert.
#     Story: "How active has the market been recently?"

#     This is semantically different from scrape_activity_chart():
#       - This groups by alert trigger date (market events)
#       - scrape_activity_chart groups by scrape run (system events)

#     Expected df columns (from get_alerts_per_day()):
#         alert_date  : date
#         alert_count : int
#     """
#     if df.empty:
#         return go.Figure()

#     fig = go.Figure(go.Bar(
#         x             = df["alert_date"],
#         y             = df["alert_count"],
#         marker_color  = CLIENT_COLOR,
#         marker_line_width = 0,
#         hovertemplate = (
#             "%{x|%b %d, %Y}<br>"
#             "<b>%{y} market alerts</b>"
#             "<extra></extra>"
#         ),
#     ))

#     layout = _base_layout(height=260)
#     layout["xaxis"].update(tickformat="%b %d")
#     layout["yaxis"].update(title=None)
#     layout["showlegend"] = False
#     layout["margin"]     = dict(l=0, r=0, t=20, b=0)
#     fig.update_layout(**layout)
#     return fig


# # ─── 5. Scrape Activity Chart (System Health) ─────────────────────────────────
# def scrape_activity_chart(df: pd.DataFrame) -> go.Figure:
#     """
#     Bar chart of alerts triggered per SCRAPE RUN.
#     Lives on the System Health page — tells the system reliability story.

#     One bar per scrape run (from scrape_logs table).
#     Story: "Is the scraper running reliably and generating alerts?"

#     This is semantically different from alerts_by_date_chart():
#       - This groups by scrape run timestamp (system events)
#       - alerts_by_date_chart groups by alert trigger date (market events)

#     Expected df columns (from get_scrape_logs()):
#         run_at            : datetime
#         alerts_triggered  : int
#         status            : str
#     """
#     if df.empty:
#         return go.Figure()

#     # Color each bar by scrape status: success=blue, partial=amber, failed=red
#     colors = df["status"].map({
#         "success": CLIENT_COLOR,
#         "partial": WARNING_COLOR,
#         "failed" : DANGER_COLOR,
#     }).fillna(NEUTRAL_COLOR).tolist()

#     fig = go.Figure(go.Bar(
#         x                 = df["run_at"],
#         y                 = df["alerts_triggered"],
#         marker_color      = colors,
#         marker_line_width = 0,
#         hovertemplate     = (
#             "%{x|%b %d, %Y}<br>"
#             "<b>%{y} alerts triggered</b>"
#             "<extra></extra>"
#         ),
#     ))

#     layout = _base_layout(title="Alerts per Scrape Run", height=280)
#     layout["xaxis"].update(tickformat="%b %d")
#     layout["yaxis"].update(title=None)
#     layout["showlegend"] = False
#     layout["margin"]     = dict(l=0, r=0, t=40, b=0)
#     fig.update_layout(**layout)
#     return fig


# # ─── 6. Price Position Bar (Product Detail) ──────────────────────────────────
# def price_position_bar(df: pd.DataFrame) -> go.Figure:
#     """
#     Vertical bar chart — current price comparison across all sellers
#     for a single selected product. Sorted cheapest to most expensive.

#     Client bar: blue. Competitor bars: light grey.
#     Dashed red reference line at cheapest competitor price makes the
#     gap immediately visible without reading numbers.

#     Expected df columns:
#         seller_name   : str
#         current_price : float
#         is_client     : bool
#         stock_status  : str
#     """
#     if df.empty:
#         return go.Figure()

#     df = df.sort_values("current_price", ascending=True)

#     colors = [
#         CLIENT_COLOR if bool(is_c) else COMPETITOR_COLOR
#         for is_c in df["is_client"]
#     ]

#     fig = go.Figure(go.Bar(
#         x                 = df["seller_name"],
#         y                 = df["current_price"],
#         marker_color      = colors,
#         marker_line_width = 0,
#         hovertemplate     = (
#             "<b>%{x}</b><br>AED %{y:,.0f}<extra></extra>"
#         ),
#     ))

#     competitors = df[df["is_client"] == False]
#     if not competitors.empty:
#         min_price = competitors["current_price"].min()
#         fig.add_hline(
#             y                   = min_price,
#             line_dash           = "dash",
#             line_color          = DANGER_COLOR,
#             line_width          = 1.5,
#             annotation_text     = f"Cheapest competitor: AED {min_price:,.0f}",
#             annotation_position = "top right",
#             annotation_font     = dict(size=11, color=DANGER_COLOR),
#         )

#     layout = _base_layout(height=300)
#     layout["yaxis"].update(tickprefix="AED ", tickformat=",.0f")
#     layout["showlegend"] = False
#     layout["margin"]     = dict(l=0, r=0, t=40, b=0)
#     fig.update_layout(**layout)
#     return fig
# ─── components/charts.py ────────────────────────────────────────────────────
# Every Plotly figure in the Noon Intelligence dashboard is built here.
# Pages never import Plotly directly — they call a function and get a figure.
#
# Pattern:
#   fig = price_history_chart(df)
#   st.plotly_chart(fig, use_container_width=True)
#
# Color logic is always driven by is_client flag — never by seller name.
# This keeps the app resellable: swap the client, colors follow automatically.
#
# Shared styling is defined once in _base_layout() and applied to every chart.
#
# FIX 1: bool() casting on is_client reads from iloc[0] — prevents silent
#         failures when PostgreSQL returns numpy.bool_ instead of Python bool.
# FIX 2: dropna() added in market_position_bar() before head(top_n) to handle
#         products with no competitors gracefully (NaN gap → sorted to bottom).
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import plotly.graph_objects as go


# ─── Design Tokens ───────────────────────────────────────────────────────────
CLIENT_COLOR     = "#2563EB"   # Blue  — always the client's line/bar
COMPETITOR_COLOR = "#D1D5DB"   # Light grey — competitors are context
DANGER_COLOR     = "#EF4444"   # Red   — alerts, drops, overpriced
SUCCESS_COLOR    = "#10B981"   # Green — cheapest, healthy, in stock
WARNING_COLOR    = "#F59E0B"   # Amber — competitive, warning
NEUTRAL_COLOR    = "#6B7280"   # Grey  — secondary text, subtle elements
FONT_FAMILY      = "Inter, ui-sans-serif, system-ui, sans-serif"


# ─── Private: Base Layout ────────────────────────────────────────────────────
def _base_layout(title: str = "", height: int = 380) -> dict:
    """
    Shared Plotly layout applied to every chart.
    Individual chart functions call this and update with chart-specific keys.

    Establishes:
    - White background (cards sit on #F8FAFC page, chart inside is white)
    - Inter font stack
    - Clean axis styling — no spines, subtle gridlines
    - Legend at bottom to maximise chart area
    - Consistent hover styling
    """
    return dict(
        title=dict(
            text      = title,
            font      = dict(
                family = FONT_FAMILY,
                size   = 14,
                color  = "#111827",
            ),
            x         = 0,
            xanchor   = "left",
            pad       = dict(l=0, t=0),
        ),
        height          = height,
        paper_bgcolor   = "#FFFFFF",
        plot_bgcolor    = "#FFFFFF",
        font            = dict(
            family = FONT_FAMILY,
            size   = 12,
            color  = "#6B7280",
        ),
        margin          = dict(l=0, r=0, t=40, b=0),
        legend          = dict(
            orientation = "h",
            yanchor     = "bottom",
            y           = -0.25,
            xanchor     = "left",
            x           = 0,
            font        = dict(size=12, color="#6B7280"),
            bgcolor     = "rgba(0,0,0,0)",
        ),
        hoverlabel      = dict(
            bgcolor    = "#1F2937",
            font_size  = 13,
            font_color = "#F9FAFB",
            bordercolor= "#1F2937",
        ),
        xaxis           = dict(
            showgrid    = False,
            showline    = False,
            tickfont    = dict(size=11, color="#9CA3AF"),
            tickcolor   = "rgba(0,0,0,0)",
        ),
        yaxis           = dict(
            showgrid    = True,
            gridcolor   = "#F3F4F6",
            gridwidth   = 1,
            showline    = False,
            zeroline    = False,
            tickfont    = dict(size=11, color="#9CA3AF"),
            tickcolor   = "rgba(0,0,0,0)",
        ),
    )


# ─── 1. Price History Line Chart ──────────────────────────────────────────────
def price_history_chart(df: pd.DataFrame) -> go.Figure:
    """
    Hero chart — price over time for one product across all sellers.
    Client line: blue, 3px width, fully opaque.
    Competitor lines: light grey, 1.5px width.
    This contrast makes the client the visual focus; competitors are context.

    FIX: bool() cast on is_client prevents silent failures when PostgreSQL
         returns numpy.bool_ instead of Python bool.

    Expected df columns:
        scraped_at    : datetime
        seller_name   : str
        current_price : float
        is_client     : bool
        stock_status  : str
    """
    fig = go.Figure()

    sellers = df["seller_name"].unique()

    for seller in sellers:
        seller_df = df[df["seller_name"] == seller].copy()

        # FIX: explicit bool() cast — numpy.bool_ can fail identity checks
        is_client = bool(seller_df["is_client"].iloc[0])

        # Replace out-of-stock prices with None so line breaks visually —
        # gaps in the line communicate unavailability clearly.
        seller_df.loc[
            seller_df["stock_status"] == "out_of_stock", "current_price"
        ] = None

        color      = CLIENT_COLOR if is_client else COMPETITOR_COLOR
        line_width = 3 if is_client else 1.5
        opacity    = 1.0 if is_client else 0.8

        fig.add_trace(go.Scatter(
            x             = seller_df["scraped_at"],
            y             = seller_df["current_price"],
            name          = seller,
            mode          = "lines",
            line          = dict(color=color, width=line_width, dash="solid"),
            opacity       = opacity,
            connectgaps   = False,
            hovertemplate = (
                f"<b>{seller}</b><br>"
                "%{x|%b %d, %Y}<br>"
                "AED %{y:,.2f}"
                "<extra></extra>"
            ),
        ))

    layout = _base_layout(height=400)
    layout["yaxis"].update(
        tickprefix = "AED ",
        tickformat = ",.0f",
    )
    layout["xaxis"].update(
        tickformat = "%b %d",
    )

    fig.update_layout(**layout)
    return fig


# ─── 2. Competitive Position Donut ───────────────────────────────────────────
def competitive_position_donut(summary: dict) -> go.Figure:
    """
    Donut chart showing how many client products are
    Cheapest / Competitive / Overpriced.

    Center annotation shows total product count + "Products" label.
    Colors are semantic: green = good, blue = acceptable, red = needs action.

    Expected summary keys: cheapest, competitive, overpriced
    """
    labels = ["Cheapest", "Competitive", "Overpriced"]
    values = [
        summary.get("cheapest",    0),
        summary.get("competitive", 0),
        summary.get("overpriced",  0),
    ]
    colors = [SUCCESS_COLOR, CLIENT_COLOR, DANGER_COLOR]
    total  = sum(values)

    fig = go.Figure(go.Pie(
        labels        = labels,
        values        = values,
        hole          = 0.65,
        marker        = dict(
            colors = colors,
            line   = dict(color="#FFFFFF", width=2),
        ),
        textinfo      = "none",
        hovertemplate = (
            "<b>%{label}</b><br>"
            "%{value} products<br>"
            "%{percent}"
            "<extra></extra>"
        ),
    ))

    # Center annotation — two lines: value (large) + "Products" label (small)
    fig.add_annotation(
        text      = f"<b>{total}</b><br><span style='font-size:11px'>Products</span>",
        x         = 0.5,
        y         = 0.5,
        xref      = "paper",
        yref      = "paper",
        showarrow = False,
        font      = dict(size=22, color="#111827", family=FONT_FAMILY),
        align     = "center",
    )

    layout = _base_layout(height=300)
    layout.pop("xaxis", None)
    layout.pop("yaxis", None)
    layout["margin"] = dict(l=0, r=0, t=40, b=0)

    fig.update_layout(**layout)
    return fig


# ─── 3. Market Position Bar Chart ────────────────────────────────────────────
def market_position_bar(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """
    Horizontal grouped bar chart comparing current prices across sellers
    for the top N products (by client gap, largest gap = most urgent).

    FIX: dropna() added before head(top_n) — products with no competitors
         produce NaN in the gap column. Without dropna(), NaN rows sort to
         the bottom silently but still consume one of the top_n slots,
         potentially displacing real results.

    FIX: bool() cast on is_client — same numpy.bool_ safety as above.

    Expected df columns:
        product_name  : str
        seller_name   : str
        current_price : float
        is_client     : bool
    """
    if df.empty:
        return go.Figure()

    if top_n:
        client_df = (
            df[df["is_client"] == True][["product_name", "current_price"]]
            .rename(columns={"current_price": "client_price"})
        )
        comp_min = (
            df[df["is_client"] == False]
            .groupby("product_name")["current_price"]
            .min()
            .reset_index()
            .rename(columns={"current_price": "min_comp_price"})
        )
        ranked = client_df.merge(comp_min, on="product_name", how="left")
        ranked["gap"] = ranked["client_price"] - ranked["min_comp_price"]

        # FIX: drop rows where gap is NaN (no competitors found) before
        # sorting — otherwise they silently consume top_n slots.
        top_products = (
            ranked
            .dropna(subset=["gap"])
            .sort_values("gap", ascending=False)
            .head(top_n)["product_name"]
            .tolist()
        )
        df = df[df["product_name"].isin(top_products)]

    fig = go.Figure()

    sellers = df["seller_name"].unique()
    for seller in sellers:
        seller_df = df[df["seller_name"] == seller]

        # FIX: explicit bool() cast
        is_client = bool(seller_df["is_client"].iloc[0])
        color     = CLIENT_COLOR if is_client else COMPETITOR_COLOR

        fig.add_trace(go.Bar(
            name          = seller,
            x             = seller_df["current_price"],
            y             = seller_df["product_name"],
            orientation   = "h",
            marker_color  = color,
            hovertemplate = (
                f"<b>{seller}</b><br>"
                "%{y}<br>"
                "AED %{x:,.0f}"
                "<extra></extra>"
            ),
        ))

    layout = _base_layout(height=max(300, len(df["product_name"].unique()) * 50))
    layout["barmode"] = "group"
    layout["xaxis"].update(
        tickprefix = "AED ",
        tickformat = ",.0f",
        showgrid   = True,
        gridcolor  = "#F3F4F6",
    )
    layout["yaxis"].update(
        showgrid   = False,
        automargin = True,
    )
    layout["margin"] = dict(l=0, r=0, t=40, b=0)

    fig.update_layout(**layout)
    return fig


# ─── 4. Alerts Timeline Chart ────────────────────────────────────────────────
def alerts_timeline_chart(df: pd.DataFrame) -> go.Figure:
    """
    Bar chart of alerts triggered per scrape run over time.
    Lives on System Health page.
    Simple and clean — shows the scraper has been running reliably.

    Expected df columns:
        run_at            : datetime
        alerts_triggered  : int
        status            : str
    """
    if df.empty:
        return go.Figure()

    fig = go.Figure(go.Bar(
        x                = df["run_at"],
        y                = df["alerts_triggered"],
        marker_color     = CLIENT_COLOR,
        marker_line_width= 0,
        hovertemplate    = (
            "%{x|%b %d, %Y}<br>"
            "<b>%{y} alerts triggered</b>"
            "<extra></extra>"
        ),
    ))

    layout = _base_layout(title="Alerts Triggered Per Run", height=280)
    layout["xaxis"].update(tickformat="%b %d")
    layout["yaxis"].update(title=None)
    layout["margin"] = dict(l=0, r=0, t=40, b=0)

    fig.update_layout(**layout)
    return fig


# ─── 5. Price Position Bar (single product) ──────────────────────────────────
def price_position_bar(df: pd.DataFrame) -> go.Figure:
    """
    Vertical bar chart comparing current prices across all sellers
    for a single selected product.
    Lives on Product Detail page alongside the ranking table.

    Client bar: blue. Competitor bars: light grey.
    A horizontal dashed red line marks the cheapest competitor price.

    FIX: bool() cast on is_client for each row — same numpy.bool_ safety.

    Expected df columns:
        seller_name   : str
        current_price : float
        is_client     : bool
        stock_status  : str
    """
    if df.empty:
        return go.Figure()

    df = df.sort_values("current_price", ascending=True)

    # FIX: explicit bool() cast on every row
    colors = [
        CLIENT_COLOR if bool(is_c) else COMPETITOR_COLOR
        for is_c in df["is_client"]
    ]

    fig = go.Figure(go.Bar(
        x                = df["seller_name"],
        y                = df["current_price"],
        marker_color     = colors,
        marker_line_width= 0,
        hovertemplate    = (
            "<b>%{x}</b><br>"
            "AED %{y:,.0f}"
            "<extra></extra>"
        ),
    ))

    competitors = df[df["is_client"] == False]
    if not competitors.empty:
        min_comp_price = competitors["current_price"].min()
        fig.add_hline(
            y                   = min_comp_price,
            line_dash           = "dash",
            line_color          = DANGER_COLOR,
            line_width          = 1.5,
            annotation_text     = f"Cheapest competitor: AED {min_comp_price:,.0f}",
            annotation_position = "top right",
            annotation_font     = dict(size=11, color=DANGER_COLOR),
        )

    layout = _base_layout(height=300)
    layout["yaxis"].update(
        tickprefix = "AED ",
        tickformat = ",.0f",
    )
    layout["showlegend"] = False
    layout["margin"]     = dict(l=0, r=0, t=40, b=0)

    fig.update_layout(**layout)
    return fig


def scrape_activity_chart(df: pd.DataFrame) -> go.Figure:
    """
    Bar chart of alerts triggered per SCRAPE RUN.
    Lives on the System Health page — tells the system reliability story.

    One bar per scrape run (from scrape_logs table).
    Story: "Is the scraper running reliably and generating alerts?"

    This is semantically different from alerts_by_date_chart():
      - This groups by scrape run timestamp (system events)
      - alerts_by_date_chart groups by alert trigger date (market events)

    Expected df columns (from get_scrape_logs()):
        run_at            : datetime
        alerts_triggered  : int
        status            : str
    """
    if df.empty:
        return go.Figure()

    # Color each bar by scrape status: success=blue, partial=amber, failed=red
    colors = df["status"].map({
        "success": CLIENT_COLOR,
        "partial": WARNING_COLOR,
        "failed" : DANGER_COLOR,
    }).fillna(NEUTRAL_COLOR).tolist()

    fig = go.Figure(go.Bar(
        x                 = df["run_at"],
        y                 = df["alerts_triggered"],
        marker_color      = colors,
        marker_line_width = 0,
        hovertemplate     = (
            "%{x|%b %d, %Y}<br>"
            "<b>%{y} alerts triggered</b>"
            "<extra></extra>"
        ),
    ))

    layout = _base_layout(title="Alerts per Scrape Run", height=280)
    layout["xaxis"].update(tickformat="%b %d")
    layout["yaxis"].update(title=None)
    layout["showlegend"] = False
    layout["margin"]     = dict(l=0, r=0, t=40, b=0)
    fig.update_layout(**layout)
    return fig
