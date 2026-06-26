# ─── app.py ──────────────────────────────────────────────────────────────────
# Entry point for the Noon Intelligence dashboard.
# Run with: streamlit run app.py
#
# Responsibilities:
#   1. Configure the Streamlit page
#   2. Inject global CSS
#   3. Initialise session state
#   4. Verify database connection
#   5. Render sidebar (header + timestamp + navigation)
#   6. Route to the correct page
#
# This file never renders business content directly.
# All page content lives in pages/ and is called via render().
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st

# ─── 1. Page Configuration ───────────────────────────────────────────────────
# Must be the very first Streamlit call — before any other st.* usage.
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Noon Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Imports (after set_page_config) ─────────────────────────────────────────
from db import test_connection
from queries import get_last_scrape_info

from views import home, alerts, product_detail, market_position, system_health

# ─── 2. Global CSS ───────────────────────────────────────────────────────────
# Goals:
#   - Apply Inter font with a safe system-font fallback chain
#   - Set a warm off-white page background so white cards stand out
#   - Clean up the sidebar appearance
#   - Hide Streamlit's default chrome (hamburger menu, footer, top bar)
#   - Tighten st.metric() typography to match our hierarchy
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Font ─────────────────────────────────────────────── */
/* No Google Fonts import — relies on locally installed Inter
   then falls back through the OS system-UI sans-serif chain. */
html, body, [class*="css"] {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system,
                 BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* ── Page background ──────────────────────────────────── */
.stApp {
    background-color: #F8FAFC;
}

/* ── Sidebar ──────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}
[data-testid="stSidebar"] * {
    font-size: 14px;
}

/* ── Hide Streamlit chrome ────────────────────────────── */
/* Top colour bar */
# [data-testid="stHeader"] {
#     display: none;
}
/* Hamburger / kebab menu */
# [data-testid="stToolbar"] {
#     display: none;
# }
/* "Made with Streamlit" footer */
footer {
    display: none;
}

/* ── st.metric() typography ───────────────────────────── */
[data-testid="stMetricValue"] {
    font-size: 28px;
    font-weight: 700;
    color: #111827;
}
[data-testid="stMetricLabel"] {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7280;
}
[data-testid="stMetricDelta"] {
    font-size: 13px;
    font-weight: 500;
}

/* ── Headings ─────────────────────────────────────────── */
h1 { font-size: 32px; font-weight: 700; color: #111827; }
h2 { font-size: 20px; font-weight: 600; color: #111827; }
h3 { font-size: 16px; font-weight: 600; color: #111827; }

/* ── Dataframe / table text ───────────────────────────── */
[data-testid="stDataFrame"] {
    font-size: 13px;
}

/* ── Radio nav — hide the circle indicators ───────────── */
[data-testid="stSidebar"] .stRadio > div {
    gap: 4px;
}
[data-testid="stSidebar"] .stRadio label {
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 500;
    color: #374151;
    transition: background 0.15s;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background-color: #F3F4F6;
}
</style>
""", unsafe_allow_html=True)


# ─── 3. Session State Initialisation ─────────────────────────────────────────
# Rule: only values that must survive navigation between pages live here.
# Page-local filters are handled inside each page file.
#
# selected_product_name:
#   Stores a product name string (not an ID — IDs are seller-specific).
#   Set by Market Position page when user clicks "View Details".
#   Read by Product Detail page to pre-select the correct product.
#
# selected_page:
#   Tracks the active page. Allows other pages to programmatically
#   trigger navigation (e.g. Dashboard → Product Detail on click).
# ─────────────────────────────────────────────────────────────────────────────
if "selected_product_name" not in st.session_state:
    st.session_state["selected_product_name"] = None

if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "Dashboard"


# ─── 4. Database Connection Check ────────────────────────────────────────────
# Runs before any page content renders.
# On failure: shows a clear human-readable error and halts execution.
# On success: continues silently — users don't need infrastructure updates.
# ─────────────────────────────────────────────────────────────────────────────
ok, error_msg = test_connection()

if not ok:
    st.error("⚠️ Cannot connect to the database.")
    st.markdown(
        f"<p style='color:#6B7280; font-size:13px;'>{error_msg}</p>",
        unsafe_allow_html=True,
    )
    st.info("Check your `.env` file and ensure the database server is running.")
    st.stop()


# ─── 5. Sidebar ──────────────────────────────────────────────────────────────

with st.sidebar:

    # ── Product header ────────────────────────────────────────────────────────
    st.markdown("""
        <div style="padding: 8px 4px 16px 4px;">
            <div style="font-size:18px; font-weight:700; color:#111827;
                        letter-spacing:-0.02em;">
                Noon Intelligence
            </div>
            <div style="font-size:12px; color:#6B7280; margin-top:2px;">
                Price Monitoring · UAE
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Last updated timestamp ────────────────────────────────────────────────
    # Shown at the TOP of the sidebar — first question users ask is
    # "how fresh is this data?"
    scrape_info = get_last_scrape_info()

    if scrape_info:
        run_at     = scrape_info["run_at"]
        status     = scrape_info["status"]
        status_color = "#10B981" if status == "success" else "#EF4444"

        # Format: Jun 21, 2026 · 08:15 AM
        formatted_time = run_at.strftime("%b %d, %Y · %I:%M %p")

        st.markdown(f"""
            <div style="
                background: #F8FAFC;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px 12px;
                margin-bottom: 16px;
            ">
                <div style="font-size:10px; font-weight:600; color:#6B7280;
                            text-transform:uppercase; letter-spacing:0.06em;
                            margin-bottom:4px;">
                    Last Updated
                </div>
                <div style="font-size:13px; font-weight:500; color:#111827;">
                    {formatted_time}
                </div>
                <div style="font-size:11px; margin-top:4px;">
                    <span style="color:{status_color};">●</span>
                    <span style="color:#6B7280; margin-left:4px;">
                        Scrape {status}
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(
            "<p style='font-size:12px; color:#6B7280;'>No scrape data yet.</p>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Navigation ────────────────────────────────────────────────────────────
    # Clean text labels — no emojis. More SaaS-like for portfolio presentation.
    # Radio gives us selected_page directly with no session_state gymnastics.
    PAGES = [
        "Dashboard",
        "Market Position",
        "Product Detail",
        "Alerts",
        "System Health",
    ]
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "Dashboard"

    selected_page = st.radio(
        "",
        PAGES,
        key="selected_page",
        label_visibility="collapsed",
    )
    # selected_page = st.radio(
    #     label="Navigation",
    #     options=PAGES,
    #     index=PAGES.index(st.session_state["selected_page"])
    #           if st.session_state["selected_page"] in PAGES
    #           else 0,
    #     label_visibility="collapsed",  # hides the "Navigation" label
    # )

    # # Keep session_state in sync so other pages can trigger navigation.
    # st.session_state["selected_page"] = selected_page


# ─── 6. Page Routing ─────────────────────────────────────────────────────────
# Each page module exposes a single render() function.
# app.py calls it — pages never call each other directly.
# ─────────────────────────────────────────────────────────────────────────────
if selected_page == "Dashboard":
    home.render()

elif selected_page == "Market Position":
    market_position.render()

elif selected_page == "Product Detail":
    product_detail.render()

elif selected_page == "Alerts":
    alerts.render()

elif selected_page == "System Health":
    system_health.render()