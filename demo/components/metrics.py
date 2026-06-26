# ─── components/metrics.py ───────────────────────────────────────────────────
# Reusable KPI card components for Noon Intelligence dashboard.
#
# Built entirely in HTML/CSS via st.markdown() — no st.metric() used.
# Reason: st.metric() always looks like Streamlit regardless of CSS overrides.
# Full HTML control gets us closer to Stripe/Linear/Vercel aesthetics.
#
# Primary function:
#   render_kpi_row(metrics: list[dict])
#
# Each metric dict accepts:
#   label       : str   — card label, sentence case (e.g. "Unseen Alerts")
#   value       : any   — the primary number or text shown large
#   subtitle    : str   — contextual answer to "why should I care?"
#   accent_color: str   — hex color for the top accent bar + value
#   icon        : str   — single character shown top-right (muted)
#
# Accent color guide:
#   Alerts / danger   → #EF4444
#   Healthy / success → #10B981
#   Neutral / info    → #2563EB
#   Warning           → #F59E0B
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st


# ─── CSS (injected once) ──────────────────────────────────────────────────────
# Injected at module level so it's available the first time any card renders.
# Streamlit deduplicates identical markdown blocks so calling this multiple
# times across pages has no performance cost.
# ─────────────────────────────────────────────────────────────────────────────
_CARD_CSS = """
<style>
.ni-card {
    background    : #FFFFFF;
    border        : 1px solid #E5E7EB;
    border-radius : 16px;
    padding       : 20px;
    transition    : border-color 0.15s ease;
    height        : 100%;
    box-sizing    : border-box;
}

.ni-card:hover {
    border-color  : #D1D5DB;
}

.ni-card-accent {
    height        : 3px;
    margin        : -20px -20px 16px -20px;
    border-radius : 16px 16px 0 0;
}

.ni-card-header {
    display         : flex;
    justify-content : space-between;
    align-items     : center;
    margin-bottom   : 12px;
}

.ni-card-label {
    font-size   : 12px;
    font-weight : 500;
    color       : #6B7280;
    line-height : 1.4;
}

.ni-card-icon {
    font-size : 16px;
    color     : #D1D5DB;
}

.ni-card-value {
    font-size            : 32px;
    font-weight          : 700;
    line-height          : 1.1;
    margin-bottom        : 6px;
    font-variant-numeric : tabular-nums;
}

.ni-card-subtitle {
    font-size  : 13px;
    color      : #9CA3AF;
    line-height: 1.4;
}
</style>
"""


def _card_html(
    label       : str,
    value       : str | int | float,
    subtitle    : str  = "",
    accent_color: str  = "#2563EB",
    icon        : str  = "",
) -> str:
    """
    Returns the raw HTML string for a single KPI card.
    Not called directly by pages — used internally by render functions.
    """
    subtitle_html = (
        f'<div class="ni-card-subtitle">{subtitle}</div>'
        if subtitle else ""
    )
    icon_html = (
        f'<div class="ni-card-icon">{icon}</div>'
        if icon else ""
    )

    return f"""
    <div class="ni-card">
        <div class="ni-card-accent"
             style="background:{accent_color};"></div>
        <div class="ni-card-header">
            <div class="ni-card-label">{label}</div>
            {icon_html}
        </div>
        <div class="ni-card-value"
             style="color:{accent_color};">{value}</div>
        {subtitle_html}
    </div>
    """


def render_kpi_row(metrics: list[dict]) -> None:
    """
    Renders a horizontal row of KPI cards.
    Automatically creates the correct number of columns.

    Args:
        metrics: list of dicts, each with keys:
            label        (str)  required
            value        (any)  required
            subtitle     (str)  optional
            accent_color (str)  optional, default #2563EB
            icon         (str)  optional

    Example:
        render_kpi_row([
            {
                "label"        : "Unseen Alerts",
                "value"        : 12,
                "subtitle"     : "3 price drops today",
                "accent_color" : "#EF4444",
                "icon"         : "🔔",
            },
            {
                "label"        : "Active Products",
                "value"        : 40,
                "subtitle"     : "Across 4 sellers",
                "accent_color" : "#2563EB",
                "icon"         : "◈",
            },
        ])
    """
    # Inject CSS once — Streamlit deduplicates identical blocks.
    st.markdown(_CARD_CSS, unsafe_allow_html=True)

    cols = st.columns(len(metrics))

    for col, metric in zip(cols, metrics):
        html = _card_html(
            label        = metric.get("label", ""),
            value        = metric.get("value", "—"),
            subtitle     = metric.get("subtitle", ""),
            accent_color = metric.get("accent_color", "#2563EB"),
            icon         = metric.get("icon", ""),
        )
        with col:
            st.markdown(html, unsafe_allow_html=True)

    # Breathing room below the card row.
    st.markdown("<div style='margin-bottom:24px;'></div>",
                unsafe_allow_html=True)


def render_single_kpi(
    label       : str,
    value       : str | int | float,
    subtitle    : str = "",
    accent_color: str = "#2563EB",
    icon        : str = "",
) -> None:
    """
    Renders exactly one KPI card without a column wrapper.
    Used when a single stat needs to stand alone on a page.
    """
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    html = _card_html(
        label        = label,
        value        = value,
        subtitle     = subtitle,
        accent_color = accent_color,
        icon         = icon,
    )
    st.markdown(html, unsafe_allow_html=True)