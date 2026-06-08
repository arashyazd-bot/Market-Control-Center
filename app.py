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
from data import markets

load_dotenv()

st.set_page_config(
    page_title="Market Control Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Structural CSS (theme-agnostic): Fidelity-inspired clean sans, compact,
#    tabular numbers, dense professional spacing. ──────────────────────────────
_CSS_BASE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@300;400;500;600;700;800&display=swap');

:root {
    --sans: 'Figtree', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

/* Global 30% downscale: rem-based sizing shrinks with the root font-size. */
html { font-size: 11px; }
html, body, [class*="css"] {
    font-family: var(--sans) !important;
    line-height: 1.5;
}
.block-container { padding-top: 2.6rem !important; padding-bottom: 2rem !important; }

h1, h2, h3, h4, h5, h6 {
    font-family: var(--sans) !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
}
h1 { font-size: 1.7rem !important; }
h2 { font-size: 1.5rem !important; }
h3, h4, h5, h6 { font-size: 1.35rem !important; }

/* tabular figures everywhere numbers matter */
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"],
.mcc-tv, .mcc-ti, .mcc-meta, [data-testid="stDataFrame"] {
    font-variant-numeric: tabular-nums !important;
    font-feature-settings: "tnum" 1 !important;
}

/* ── Metric cards — compact, numbers always fit ── */
[data-testid="stMetric"] {
    border: 1px solid var(--c-border);
    border-radius: 6px;
    padding: 0.65rem 0.85rem;
    background: var(--c-card);
}
[data-testid="stMetricLabel"] > div {
    font-size: 1.0rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    color: var(--c-sub) !important;
    white-space: normal !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.015em !important;
    color: var(--c-text) !important;
    white-space: nowrap !important;
}
[data-testid="stMetricDelta"] { font-size: 1.0rem !important; }

/* ── Tabs — clean text tabs, underline on active (Fidelity style) ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    background: transparent !important;
    border-bottom: 1px solid var(--c-border) !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
    padding: 6px 11px !important;
    margin-bottom: -1px !important;
    border-radius: 0 !important;
    min-height: 30px !important;
    color: var(--c-sub) !important;
}
.stTabs [aria-selected="true"] {
    background: var(--c-tab-active-bg) !important;
    border-bottom: 2.5px solid var(--c-accent) !important;
    color: var(--c-accent) !important;
}

/* ── Buttons ── */
.stButton > button {
    font-size: 1.0rem !important;
    font-weight: 600 !important;
    border-radius: 5px !important;
    min-height: 30px !important;
    border: 1px solid var(--c-btn-border) !important;
    background: var(--c-btn-bg) !important;
    color: var(--c-text) !important;
    transition: border-color 0.15s, background 0.15s !important;
}
.stButton > button:hover {
    border-color: var(--c-accent) !important;
    background: var(--c-btn-hover) !important;
}

.stCaption > p,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    font-size: 1.05rem !important;          /* descriptions +~2px, >= 11px floor */
    color: var(--c-muted) !important;
}

details {
    border: 1px solid var(--c-border) !important;
    border-radius: 6px !important;
    background: var(--c-card) !important;
}

header[data-testid="stHeader"] {
    border-bottom: 1px solid var(--c-border) !important;
    backdrop-filter: blur(12px) !important;
    background: var(--c-topbar) !important;
}

/* ── Top ticker strip (Fidelity marquee) ── */
.mcc-ticker {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1.6rem;
    align-items: baseline;
    padding: 0.35rem 0 0.6rem;
    margin-bottom: 0.3rem;
    border-bottom: 1px solid var(--c-border);
    font-size: 1.0rem;
}
.mcc-ti { white-space: nowrap; }
.mcc-tn { color: var(--c-sub); font-weight: 700; letter-spacing: 0.02em;
          font-size: 1.0rem; text-transform: uppercase; margin-right: 0.4rem; }
.mcc-tv { color: var(--c-text); font-weight: 600; margin-right: 0.35rem; }
.mcc-up   { color: var(--c-up);   font-weight: 600; }
.mcc-down { color: var(--c-down); font-weight: 600; }

/* ── Custom page header ── */
.mcc-header {
    display: flex; align-items: flex-end; justify-content: space-between;
    padding: 0.15rem 0 0.7rem;
    border-bottom: 1px solid var(--c-border);
    margin-bottom: 0.9rem;
}
.mcc-eyebrow {
    font-size: 1.0rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--c-accent); margin-bottom: 0.25rem;
}
.mcc-title {
    font-size: 1.75rem; font-weight: 800; color: var(--c-text);
    letter-spacing: -0.02em; margin: 0; line-height: 1.05;
}
.mcc-meta {
    text-align: right; font-size: 1.0rem; color: var(--c-muted); line-height: 1.7;
}
.mcc-live-dot {
    display: inline-block; width: 4px; height: 4px; border-radius: 50%;
    background: var(--c-up); margin-right: 4px; vertical-align: middle;
    animation: mcc-pulse 2.5s ease-in-out infinite;
}
@keyframes mcc-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
</style>
"""

# ── Light mode (default daylight) — Fidelity palette: green accent, strong text ─
_CSS_LIGHT = """
<style>
:root {
    --c-border:       rgba(15,23,42,0.12);
    --c-card:         #FBFCFD;
    --c-accent:       #368727;   /* Fidelity green */
    --c-muted:        #6B7280;
    --c-text:         #1A1A1A;
    --c-sub:          #4B5563;
    --c-up:           #1A7F37;
    --c-down:         #C8102E;
    --c-tab-active-bg:rgba(54,135,39,0.06);
    --c-btn-border:   rgba(54,135,39,0.30);
    --c-btn-bg:       rgba(54,135,39,0.05);
    --c-btn-hover:    rgba(54,135,39,0.11);
    --c-topbar:       rgba(255,255,255,0.92);
}
[data-testid="stSidebar"] > div:first-child {
    background: #F4F6F8 !important;
    border-right: 1px solid rgba(15,23,42,0.1) !important;
}
</style>
"""

# ── Night mode override ───────────────────────────────────────────────────────
_CSS_DARK = """
<style>
:root {
    --c-border:       rgba(120,140,180,0.18);
    --c-card:         rgba(18,24,38,0.6);
    --c-accent:       #5DBB46;   /* brighter Fidelity green for dark */
    --c-muted:        #7A8699;
    --c-text:         #E6EAF0;
    --c-sub:          #9AA6B8;
    --c-up:           #3FB950;
    --c-down:         #F4564A;
    --c-tab-active-bg:rgba(93,187,70,0.10);
    --c-btn-border:   rgba(120,140,180,0.32);
    --c-btn-bg:       rgba(28,36,54,0.5);
    --c-btn-hover:    rgba(93,187,70,0.14);
    --c-topbar:       rgba(8,11,20,0.92);
}
.stApp, [data-testid="stAppViewContainer"] { background-color: #0C0F17 !important; }
.main .block-container { background: transparent !important; }
[data-testid="stSidebar"] > div:first-child {
    background: #080b14 !important;
    border-right: 1px solid rgba(120,140,180,0.18) !important;
}
p, .stMarkdown p { color: #E6EAF0 !important; }
h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5 { color: #E6EAF0 !important; }
label { color: #9AA6B8 !important; }
[data-testid="stMetricValue"] { color: #E6EAF0 !important; }
[data-testid="stMetricLabel"] > div { color: #9AA6B8 !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] div, [data-testid="stSidebar"] label { color: #E6EAF0 !important; }
[data-testid="stNotification"] { background: rgba(18,24,38,0.85) !important; }
[data-testid="stDataFrame"] th { background: #0C0F17 !important; color: #9AA6B8 !important; }
[data-testid="stDataFrame"] td { color: #E6EAF0 !important; }
</style>
"""


def _inject_css(dark: bool) -> None:
    st.markdown(_CSS_BASE + (_CSS_DARK if dark else _CSS_LIGHT), unsafe_allow_html=True)


# Marquee tickers, Fidelity-style (name, yfinance symbol, decimals).
_TICKERS = [
    ("S&P 500", "^GSPC", 0),
    ("Nasdaq", "^IXIC", 0),
    ("Dow", "^DJI", 0),
    ("VIX", "^VIX", 2),
    ("10Y", "^TNX", 2),
    ("Gold", "GC=F", 0),
    ("WTI", "CL=F", 2),
    ("Bitcoin", "BTC-USD", 0),
]


def ticker_strip() -> None:
    """Horizontal scrolling quote bar across the top — the Fidelity marquee."""
    cells = []
    for name, sym, dec in _TICKERS:
        try:
            q = markets.quote(sym)
            price = float(q.data["price"])
            chg = float(q.data["change_pct"])
        except Exception:
            continue
        cls = "mcc-up" if chg >= 0 else "mcc-down"
        arrow = "▲" if chg >= 0 else "▼"
        cells.append(
            f'<span class="mcc-ti"><span class="mcc-tn">{name}</span>'
            f'<span class="mcc-tv">{price:,.{dec}f}</span>'
            f'<span class="{cls}">{arrow} {chg:+.2f}%</span></span>')
    if cells:
        st.markdown('<div class="mcc-ticker">' + "".join(cells) + "</div>",
                    unsafe_allow_html=True)


def sidebar(dark: bool) -> None:
    with st.sidebar:
        accent = "#5DBB46" if dark else "#368727"
        text_color = "#E6EAF0" if dark else "#1A1A1A"
        st.markdown(f"""
<div style="font-family:'Figtree',sans-serif;padding:0.4rem 0 0.2rem">
  <div style="font-size:1.0rem;letter-spacing:0.14em;color:{accent};
              text-transform:uppercase;font-weight:700;margin-bottom:4px">
    Market Control Center
  </div>
  <div style="font-size:1.15rem;font-weight:800;color:{text_color};line-height:1.25">
    US Markets at a Glance
  </div>
</div>""", unsafe_allow_html=True)

        st.divider()

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


def main() -> None:
    dark = st.session_state.setdefault("dark_mode", False)

    _inject_css(dark)
    sidebar(dark)
    panels.warm_caches()   # parallel prefetch so panels hit warm caches
    ticker_strip()

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
        "Overview", "Valuation", "Sentiment",
        "Rates & Macro", "Cross-Asset", "Intelligence",
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
