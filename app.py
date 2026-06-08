"""Market Control Center — single-pane-of-glass view of US market, macro,
sentiment, and policy conditions for asset-allocation timing.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from components import panels

load_dotenv()

st.set_page_config(
    page_title="Market Control Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Shared structural CSS (fonts, sizing, layout — theme-agnostic) ──────────
_CSS_BASE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Barlow:wght@300;400;500;600;700&family=Barlow+Condensed:wght@400;500;600;700&display=swap');

:root {
    --mono: 'IBM Plex Mono', ui-monospace, monospace;
    --sans: 'Barlow', system-ui, sans-serif;
    --cond: 'Barlow Condensed', system-ui, sans-serif;
}

/* ── Elder-friendly base sizing ──────────────────── */
html { font-size: 17px; }
html, body, [class*="css"] { font-family: var(--sans) !important; line-height: 1.6; }

h1 { font-family: var(--cond) !important; font-weight: 700 !important;
     font-size: 2.2rem !important; letter-spacing: -0.02em !important; }
h2, h3, h4, h5 { font-family: var(--cond) !important; font-weight: 600 !important;
                  letter-spacing: 0.01em !important; }

/* ── Metric cards ── */
[data-testid="stMetric"] {
    border: 1px solid var(--c-border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    background: var(--c-card);
}
[data-testid="stMetricLabel"] > div {
    font-family: var(--cond) !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: var(--c-sub) !important;
}
[data-testid="stMetricValue"] { font-family: var(--mono) !important; font-weight: 500 !important; }
[data-testid="stMetricDelta"] > div { font-family: var(--mono) !important; font-size: 0.82rem !important; }

/* ── Tabs — larger touch targets (elder 44px min) ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0; background: transparent !important;
    border-bottom: 1px solid var(--c-border) !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--cond) !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 10px 22px !important;
    margin-bottom: -1px !important;
    border-radius: 0 !important;
    min-height: 44px !important;
}
.stTabs [aria-selected="true"] {
    background: var(--c-tab-active-bg) !important;
    border-bottom: 3px solid var(--c-accent) !important;
    color: var(--c-accent) !important;
}

/* ── Buttons — 44px min height ── */
.stButton > button {
    font-family: var(--cond) !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border-radius: 5px !important;
    min-height: 44px !important;
    border: 1px solid var(--c-btn-border) !important;
    background: var(--c-btn-bg) !important;
    transition: border-color 0.15s, background 0.15s !important;
}
.stButton > button:hover {
    border-color: var(--c-accent) !important;
    background: var(--c-btn-hover) !important;
}

/* ── Caption / badge ── */
.stCaption > p {
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
    color: var(--c-muted) !important;
}

/* ── Expander ── */
details {
    border: 1px solid var(--c-border) !important;
    border-radius: 6px !important;
    background: var(--c-card) !important;
}

/* ── Chrome header ── */
header[data-testid="stHeader"] {
    border-bottom: 1px solid var(--c-border) !important;
    backdrop-filter: blur(12px) !important;
    background: var(--c-topbar) !important;
}

/* ── Custom page header ── */
.mcc-header {
    display: flex; align-items: flex-end;
    justify-content: space-between;
    padding: 0.1rem 0 0.9rem;
    border-bottom: 1px solid var(--c-border);
    margin-bottom: 1rem;
}
.mcc-eyebrow {
    font-family: var(--mono);
    font-size: 0.62rem; font-weight: 500;
    letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--c-accent); margin-bottom: 0.2rem;
}
.mcc-title {
    font-family: var(--cond); font-size: 2.1rem; font-weight: 700;
    color: var(--c-text); letter-spacing: -0.02em;
    margin: 0; line-height: 1.1;
}
.mcc-meta {
    text-align: right; font-family: var(--mono);
    font-size: 0.65rem; color: var(--c-muted); line-height: 1.9;
}
.mcc-live-dot {
    display: inline-block; width: 6px; height: 6px;
    border-radius: 50%; background: #16A34A;
    margin-right: 5px; vertical-align: middle;
    animation: mcc-pulse 2.5s ease-in-out infinite;
}
@keyframes mcc-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
</style>
"""

# ── Light mode (default) ─────────────────────────────────────────────────────
_CSS_LIGHT = """
<style>
:root {
    --c-border:       rgba(15,23,42,0.11);
    --c-card:         #F8FAFC;
    --c-accent:       #2563EB;
    --c-muted:        #64748B;
    --c-text:         #0F172A;
    --c-sub:          #475569;
    --c-tab-active-bg:rgba(37,99,235,0.06);
    --c-btn-border:   rgba(37,99,235,0.28);
    --c-btn-bg:       rgba(37,99,235,0.04);
    --c-btn-hover:    rgba(37,99,235,0.10);
    --c-topbar:       rgba(255,255,255,0.92);
}
[data-testid="stSidebar"] > div:first-child {
    background: #F1F5F9 !important;
    border-right: 1px solid rgba(15,23,42,0.1) !important;
}
</style>
"""

# ── Dark mode override (injected on top of light Streamlit theme) ─────────────
_CSS_DARK = """
<style>
:root {
    --c-border:       rgba(99,118,167,0.18);
    --c-card:         rgba(14,20,40,0.55);
    --c-accent:       #7C8FD8;
    --c-muted:        #64748B;
    --c-text:         #E2E8F0;
    --c-sub:          #94A3B8;
    --c-tab-active-bg:rgba(99,118,200,0.08);
    --c-btn-border:   rgba(99,118,167,0.35);
    --c-btn-bg:       rgba(20,30,60,0.4);
    --c-btn-hover:    rgba(99,118,200,0.12);
    --c-topbar:       rgba(5,8,18,0.92);
}

/* ── Page backgrounds ── */
.stApp, [data-testid="stAppViewContainer"] { background-color: #0E1117 !important; }
.main .block-container { background: transparent !important; }
[data-testid="stSidebar"] > div:first-child {
    background: #080c18 !important;
    border-right: 1px solid rgba(99,118,167,0.18) !important;
}

/* ── Text ── */
p, .stMarkdown p, span.stText { color: #E2E8F0 !important; }
h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5 { color: #E2E8F0 !important; }
label { color: #94A3B8 !important; }
[data-testid="stMetricValue"] { color: #E2E8F0 !important; }
[data-testid="stMetricLabel"] > div { color: #94A3B8 !important; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label { color: #E2E8F0 !important; }

/* ── Info / alert boxes ── */
[data-testid="stNotification"] { background: rgba(14,20,40,0.8) !important; }

/* ── Dataframes ── */
[data-testid="stDataFrame"] th { background: #0e1117 !important; color: #94A3B8 !important; }
[data-testid="stDataFrame"] td { color: #E2E8F0 !important; }
</style>
"""


def _inject_css(dark: bool) -> None:
    st.markdown(_CSS_BASE + (_CSS_DARK if dark else _CSS_LIGHT), unsafe_allow_html=True)


def sidebar(dark: bool) -> bool:
    with st.sidebar:
        color = "#7C8FD8" if dark else "#2563EB"
        text_color = "#E2E8F0" if dark else "#0F172A"
        st.markdown(f"""
<div style="font-family:'Barlow Condensed',sans-serif;padding:0.5rem 0 0.25rem">
  <div style="font-size:0.6rem;letter-spacing:0.2em;color:{color};
              text-transform:uppercase;font-weight:600;margin-bottom:4px">
    Market Control Center
  </div>
  <div style="font-size:1.1rem;font-weight:700;color:{text_color};line-height:1.3">
    US Markets<br>at a Glance
  </div>
</div>""", unsafe_allow_html=True)

        st.divider()

        # ── Night mode toggle ──
        new_dark = st.toggle("Night mode", value=dark, key="dark_mode_toggle",
                             help="Switch between daylight and night display")
        if new_dark != dark:
            st.session_state.dark_mode = new_dark
            st.rerun()

        st.divider()

        has_fmp = bool(os.environ.get("FMP_API_KEY"))
        has_fred = bool(os.environ.get("FRED_API_KEY"))
        if has_fmp:
            st.success("FMP key detected — live rates/macro via FMP (FRED fallback).")
        elif has_fred:
            st.success("FRED API key detected — live macro data enabled.")
        else:
            st.warning(
                "No FMP_API_KEY or FRED_API_KEY found. Running on **sample data**.\n\n"
                "Add a free FRED key (fredaccount.stlouisfed.org) or FMP key to `.env`.")

        st.divider()
        if st.button("↺  Refresh Data", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.caption(f"Updated {datetime.now():%Y-%m-%d %H:%M}")

        st.divider()
        st.markdown(
            "**Sources**\n\n"
            "🟢 live &nbsp;·&nbsp; 🟡 sample\n\n"
            "FMP · FRED · Yahoo Finance · CNN Fear & Greed")

    return new_dark


def main() -> None:
    dark = st.session_state.setdefault("dark_mode", False)

    _inject_css(dark)
    sidebar(dark)

    st.markdown(f"""
<div class="mcc-header">
  <div>
    <div class="mcc-eyebrow">US Markets · Macro · Sentiment · Policy</div>
    <div class="mcc-title">Market Control Center</div>
  </div>
  <div class="mcc-meta">
    <span class="mcc-live-dot"></span>LIVE DATA<br>
    {datetime.now():%a %d %b %Y &nbsp;&middot;&nbsp; %H:%M} ET
  </div>
</div>
""", unsafe_allow_html=True)

    (tab_overview, tab_val, tab_sent, tab_rates, tab_cross,
     tab_intel) = st.tabs([
        "🧭 Overview", "💰 Valuation", "😱 Sentiment",
        "📈 Rates & Macro", "🌍 Cross-Asset", "💹 Intelligence",
    ])

    with tab_overview:
        panels.render_overview()
    with tab_val:
        panels.render_valuation()
    with tab_sent:
        panels.render_sentiment()
    with tab_rates:
        panels.render_rates_macro()
    with tab_cross:
        panels.render_crossasset_politics()
    with tab_intel:
        panels.render_intelligence()


if __name__ == "__main__":
    main()
