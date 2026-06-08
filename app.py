"""Market-Timing Dashboard — a single-pane-of-glass view of US market, macro,
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
    page_title="Market-Timing Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def sidebar() -> None:
    with st.sidebar:
        st.title("📊 Market Timing")
        st.caption("State of the US economy, markets & policy — at a glance.")
        st.divider()

        has_key = bool(os.environ.get("FRED_API_KEY"))
        if has_key:
            st.success("FRED API key detected — live macro data enabled.")
        else:
            st.warning(
                "No FRED_API_KEY found. Running on **sample data** for macro/rates.\n\n"
                "Get a free key at fredaccount.stlouisfed.org and add it to `.env`.")

        st.divider()
        if st.button("🔄 Refresh data", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.caption(f"Last loaded: {datetime.now():%Y-%m-%d %H:%M}")

        st.divider()
        st.markdown(
            "**Legend**\n\n"
            "🟢 live source &nbsp;·&nbsp; 🟡 sample fallback\n\n"
            "Data: FRED · Yahoo Finance · CNN Fear & Greed")


def main() -> None:
    sidebar()
    st.title("Market-Timing Dashboard")
    st.caption(
        "Built for top-down allocation: gauge the regime, valuation, sentiment, "
        "rates, the business cycle, and cross-asset/policy risk on one screen.")

    tab_overview, tab_val, tab_sent, tab_rates, tab_cross = st.tabs([
        "🧭 Overview", "💰 Valuation", "😱 Sentiment & Internals",
        "📈 Rates & Macro", "🌍 Cross-Asset & Politics",
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


if __name__ == "__main__":
    main()
