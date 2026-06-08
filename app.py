"""Market Control Center — a single-pane-of-glass view of US market, macro,
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

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Barlow:wght@300;400;500;600;700&family=Barlow+Condensed:wght@400;500;600;700&display=swap');

:root {
    --mono: 'IBM Plex Mono', ui-monospace, monospace;
    --sans: 'Barlow', system-ui, sans-serif;
    --cond: 'Barlow Condensed', system-ui, sans-serif;
    --c-border: rgba(99,118,167,0.18);
    --c-card:   rgba(14,20,40,0.55);
    --c-accent: #7C8FD8;
    --c-muted:  #64748B;
    --c-text:   #E2E8F0;
    --c-sub:    #94A3B8;
}

/* ── Global typography ── */
html, body, [class*="css"] {
    font-family: var(--sans) !important;
}
h1 {
    font-family: var(--cond) !important;
    font-weight: 700 !important;
    font-size: 2.1rem !important;
    letter-spacing: -0.02em !important;
}
h2, h3, h4, h5 {
    font-family: var(--cond) !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: var(--c-card);
    border: 1px solid var(--c-border);
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
}
[data-testid="stMetricLabel"] > div {
    font-family: var(--cond) !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: var(--c-sub) !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    font-weight: 500 !important;
}
[data-testid="stMetricDelta"] > div {
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: transparent !important;
    border-bottom: 1px solid var(--c-border) !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--cond) !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    padding: 8px 18px !important;
    margin-bottom: -1px !important;
    border-radius: 0 !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(99,118,200,0.08) !important;
    border-bottom: 2px solid var(--c-accent) !important;
    color: var(--c-accent) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] > div:first-child {
    background: #080c18 !important;
    border-right: 1px solid var(--c-border) !important;
}

/* ── Buttons ── */
.stButton > button {
    font-family: var(--cond) !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border-radius: 5px !important;
    border: 1px solid rgba(99,118,167,0.35) !important;
    background: rgba(20,30,60,0.4) !important;
    transition: border-color 0.15s, background 0.15s !important;
}
.stButton > button:hover {
    border-color: var(--c-accent) !important;
    background: rgba(99,118,200,0.12) !important;
}

/* ── Misc ── */
hr {
    border-color: var(--c-border) !important;
    margin: 0.8rem 0 !important;
}
.stCaption > p {
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    color: var(--c-muted) !important;
}
details {
    border: 1px solid var(--c-border) !important;
    border-radius: 6px !important;
    background: var(--c-card) !important;
}
header[data-testid="stHeader"] {
    background: rgba(5,8,18,0.92) !important;
    backdrop-filter: blur(12px) !important;
    border-bottom: 1px solid var(--c-border) !important;
}

/* ── Custom page header ── */
.mcc-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    padding: 0.25rem 0 1rem;
    border-bottom: 1px solid var(--c-border);
    margin-bottom: 1.2rem;
}
.mcc-eyebrow {
    font-family: var(--mono);
    font-size: 0.6rem;
    font-weight: 500;
    letter-spacing: 0.2em;
    color: var(--c-accent);
    text-transform: uppercase;
    margin-bottom: 0.2rem;
}
.mcc-title {
    font-family: var(--cond);
    font-size: 2.1rem;
    font-weight: 700;
    color: #F1F5F9;
    letter-spacing: -0.02em;
    margin: 0;
    line-height: 1.1;
}
.mcc-meta {
    text-align: right;
    font-family: var(--mono);
    font-size: 0.62rem;
    color: var(--c-muted);
    line-height: 1.9;
}
.mcc-live-dot {
    display: inline-block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #10B981;
    margin-right: 5px;
    vertical-align: middle;
    animation: mcc-pulse 2.5s ease-in-out infinite;
}
@keyframes mcc-pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.3; }
}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar() -> None:
    with st.sidebar:
        st.markdown("""
<div style="font-family:'Barlow Condensed',sans-serif;padding:0.5rem 0 0.25rem">
  <div style="font-size:0.58rem;letter-spacing:0.2em;color:#7C8FD8;
              text-transform:uppercase;font-weight:600;margin-bottom:4px">
    Market Control Center
  </div>
  <div style="font-size:1.05rem;font-weight:700;color:#E2E8F0;line-height:1.3">
    US Markets<br>at a Glance
  </div>
</div>""", unsafe_allow_html=True)
        st.divider()

        has_fmp = bool(os.environ.get("FMP_API_KEY"))
        has_fred = bool(os.environ.get("FRED_API_KEY"))
        if has_fmp:
            st.success("FMP key detected — live rates/macro via FMP (FRED fallback).")
        elif has_fred:
            st.success("FRED API key detected — live macro data enabled.")
        else:
            st.warning(
                "No FMP_API_KEY or FRED_API_KEY found. Running on **sample data** "
                "for macro/rates.\n\nAdd a free FRED key (fredaccount.stlouisfed.org) "
                "or an FMP key to `.env`.")

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


def main() -> None:
    _inject_css()
    sidebar()

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
