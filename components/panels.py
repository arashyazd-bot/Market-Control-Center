"""Panel renderers — one function per dashboard tab. Each pulls from the data
layer, surfaces a live/sample badge, and draws charts via components.charts."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from components import charts, gauges
from data import composite, fmp, fred, macro, markets, sentiment, valuation
from utils.formatting import fmt_delta, fmt_num, percentile_label


def _badge(*results) -> None:
    """Render a small caption noting whether any source fell back to sample data."""
    sample_notes = [r.note for r in results if getattr(r, "is_sample", False)]
    if sample_notes:
        st.caption(f"🟡 sample data in use ({len(sample_notes)} source(s)) — "
                   "add a FRED_API_KEY and internet for live values")
    else:
        st.caption("🟢 live data")


def _chart(fig, key: str) -> None:
    st.plotly_chart(fig, width="stretch", key=key)


# ---------------------------------------------------------------------------
# 1. Overview
# ---------------------------------------------------------------------------
def render_overview() -> None:
    st.subheader("Market Regime — Single Pane of Glass")
    regime = composite.compute_regime()
    sp = markets.quote("^GSPC")
    vix = markets.quote("^VIX")
    spread = fred.get_series("spread_10y2y")
    fg = sentiment.get_fear_greed()

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("S&P 500", fmt_num(sp.data["price"], 0),
              fmt_delta(sp.data["change_pct"]))
    k2.metric("VIX", fmt_num(vix.data["price"], 2),
              fmt_delta(vix.data["change_pct"]), delta_color="inverse")
    k3.metric("10Y–2Y Spread", fmt_num(fred.latest(spread), 2, suffix="%"))
    k4.metric("Fear & Greed", fmt_num(fg.data["score"], 0), fg.data["rating"],
              delta_color="off")
    k5.metric("Regime", regime.data["label"])

    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        _chart(gauges.regime_gauge(regime.data["score"], regime.data["label"],
                                   regime.data["color"]), key="overview_regime")
    with g2:
        _chart(gauges.fear_greed_gauge(fg.data["score"], fg.data["rating"]),
               key="overview_feargreed")

    with st.expander("How the regime score is built"):
        comp = regime.data["components"]
        comp_df = pd.DataFrame({
            "Component": list(comp.keys()),
            "Sub-score (-1..+1)": [round(v, 2) for v in comp.values()],
            "Weight": [config.COMPOSITE_WEIGHTS[k] for k in comp],
        })
        st.dataframe(comp_df, hide_index=True, width="stretch")
        st.caption("Positive = risk-on. Weighted blend → headline score. "
                   "Tune weights/series in config.py.")
    _badge(regime, sp, vix, spread, fg)


# ---------------------------------------------------------------------------
# 2. Valuation
# ---------------------------------------------------------------------------
def render_valuation() -> None:
    st.subheader("Valuation — Is the market expensive?")
    val = valuation.get_valuation()
    v = val.data

    c1, c2, c3 = st.columns(3)
    c1.metric("Shiller CAPE", fmt_num(v["cape"], 1),
              percentile_label(v.get("cape_pct", float("nan"))), delta_color="off")
    c2.metric("Buffett Indicator", fmt_num(v["buffett"], 0, suffix="%"),
              percentile_label(v.get("buffett_pct", float("nan"))), delta_color="off")
    c3.metric("Equity Risk Premium", fmt_num(v["erp"], 2, suffix="%"),
              "earnings yield − 10Y", delta_color="off")

    c4, c5, c6 = st.columns(3)
    c4.metric("Trailing P/E", fmt_num(v["pe_ttm"], 1))
    c5.metric("Forward P/E", fmt_num(v["forward_pe"], 1))
    c6.metric("Dividend Yield", fmt_num(v["dividend_yield"], 2, suffix="%"))

    st.info(
        "**Reading it:** CAPE > ~30 and Buffett Indicator > ~150% are historically "
        "rich, implying lower forward 10-year returns. A *negative* equity risk "
        "premium means stocks yield less than risk-free Treasuries — a late-cycle "
        "warning, not a timing trigger.")
    _badge(val)


# ---------------------------------------------------------------------------
# 3. Sentiment & Internals
# ---------------------------------------------------------------------------
def render_sentiment() -> None:
    st.subheader("Sentiment & Market Internals")
    fg = sentiment.get_fear_greed()
    vix_hist = markets.price_history("^VIX", period="1y")
    sectors = markets.sector_performance()
    concentration = markets.concentration_proxy()

    c1, c2 = st.columns([1, 2])
    with c1:
        _chart(gauges.fear_greed_gauge(fg.data["score"], fg.data["rating"]),
               key="sent_feargreed")
        st.metric("Breadth: Equal-wt − Cap-wt (YTD)",
                  fmt_num(concentration.data, 1, suffix="%"),
                  "negative = narrow / mega-cap led", delta_color="off")
    with c2:
        _chart(charts.line_chart(fg.data["history"], "Fear & Greed (1Y)",
                                 color="#e9c46a"), key="sent_fg_hist")

    _chart(charts.line_chart(vix_hist.data["Close"], "VIX (1Y)", color="#e63946"),
           key="sent_vix")
    _chart(charts.sector_heatmap(sectors.data), key="sent_sectors")
    _badge(fg, vix_hist, sectors, concentration)


# ---------------------------------------------------------------------------
# 4. Rates & Macro
# ---------------------------------------------------------------------------
def render_rates_macro() -> None:
    st.subheader("Rates & Macro Cycle")
    st.caption(f"Active macro source: **{macro.active_source()}** (FMP → FRED → sample)")
    curve = macro.yield_curve()
    s_10y2y = macro.spread_series("s10y2y")
    s_10y3m = macro.spread_series("s10y3m")
    hy = macro.series("hy_oas")
    ig = macro.series("ig_oas")
    gdp = macro.gdp_growth()
    sp = markets.price_history("^GSPC", period="2y")

    _chart(charts.yield_curve_chart(curve.data), key="rates_curve")

    c1, c2 = st.columns(2)
    with c1:
        _chart(charts.spread_chart(s_10y2y.data, "10Y–2Y Spread (recession signal)"),
               key="rates_10y2y")
    with c2:
        _chart(charts.spread_chart(s_10y3m.data, "10Y–3M Spread"), key="rates_10y3m")

    cc1, cc2 = st.columns(2)
    with cc1:
        _chart(charts.line_chart(hy.data, "High-Yield Credit Spread (OAS)",
                                 color="#e63946", y_suffix="%", recessions=True),
               key="rates_hy")
    with cc2:
        sp_yoy = (sp.data["Close"].pct_change(252) * 100).dropna()
        _chart(charts.dual_axis_chart(gdp.data, sp_yoy, "Real GDP growth %",
                                      "S&P 500 YoY %", "Growth: Economy vs Market"),
               key="rates_gdp")

    # Macro tiles.
    unemp = macro.series("unemployment")
    sahm = macro.series("sahm")
    cpi = macro.series("cpi")
    ff = macro.series("fed_funds")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Unemployment", fmt_num(macro.latest(unemp), 1, suffix="%"))
    m2.metric("Sahm Rule", fmt_num(macro.latest(sahm), 2),
              "≥0.50 = recession trigger", delta_color="off")
    m3.metric("CPI YoY", fmt_num(macro.yoy_change(cpi), 1, suffix="%"))
    m4.metric("Fed Funds", fmt_num(macro.latest(ff), 2, suffix="%"))

    _render_leading_indicators()
    _badge(curve, s_10y2y, s_10y3m, hy, ig, gdp, sp, unemp, sahm, cpi, ff)


def _render_leading_indicators() -> None:
    """Leading / housing / policy block — FMP-tier live macro plus the calendar."""
    st.divider()
    st.markdown("##### Leading, Housing & Policy")
    sent = macro.series("umich_sentiment")
    claims = macro.series("initial_claims")
    mortgage = macro.series("mortgage_30y")
    recprob = macro.series("recession_prob")

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Consumer Sentiment", fmt_num(macro.latest(sent), 1),
              "U. of Michigan", delta_color="off")
    t2.metric("Initial Claims", fmt_num(macro.latest(claims), 0),
              "weekly", delta_color="off")
    t3.metric("30Y Mortgage", fmt_num(macro.latest(mortgage), 2, suffix="%"),
              "real-estate cost", delta_color="off")
    t4.metric("Recession Prob.", fmt_num(macro.latest(recprob), 2, suffix="%"),
              "smoothed (FRED/FMP)", delta_color="off")

    lc1, lc2 = st.columns(2)
    with lc1:
        _chart(charts.line_chart(recprob.data, "Smoothed US Recession Probability",
                                 color="#e63946", y_suffix="%", recessions=True),
               key="lead_recprob")
    with lc2:
        _chart(charts.line_chart(sent.data, "Consumer Sentiment (UMich)",
                                 color="#e9c46a"), key="lead_sentiment")

    # Upcoming high-impact US releases.
    cal = fmp.get_economic_calendar()
    st.markdown("**Upcoming US economic releases**")
    st.dataframe(cal.data, hide_index=True, width="stretch")
    if cal.is_sample:
        st.caption("🟡 sample calendar — live calendar needs an FMP Starter+ plan")
    _badge(sent, claims, mortgage, recprob)


# ---------------------------------------------------------------------------
# 5. Cross-asset & Politics
# ---------------------------------------------------------------------------
def render_crossasset_politics() -> None:
    st.subheader("Cross-Asset & Policy")

    cols = st.columns(len(config.CROSS_ASSET))
    series_map = {}
    hist_results = []
    for col, (name, ticker) in zip(cols, config.CROSS_ASSET.items()):
        q = markets.quote(ticker)
        col.metric(name, fmt_num(q.data["price"], 2), fmt_delta(q.data["change_pct"]))
        h = markets.price_history(ticker, period="1y")
        hist_results.append(h)
        series_map[name] = h.data["Close"]

    _chart(charts.normalized_multi(series_map, "Cross-Asset (1Y, rebased to 100)"),
           key="cross_multi")

    # Copper/Gold ratio — a growth/inflation barometer.
    copper = markets.price_history("HG=F", period="1y")
    gold = markets.price_history("GC=F", period="1y")
    ratio = (copper.data["Close"] / gold.data["Close"]).dropna()
    epu = fred.get_series("policy_uncertainty")
    cg1, cg2 = st.columns(2)
    with cg1:
        _chart(charts.line_chart(ratio, "Copper / Gold ratio (growth barometer)",
                                 color="#f4a261"), key="cross_coppergold")
    with cg2:
        _chart(charts.line_chart(epu.data, "Economic Policy Uncertainty Index",
                                 color="#b5179e"), key="cross_epu")

    st.info(
        "**Policy & news (v1 placeholder):** live AAII survey, CME FedWatch rate-cut "
        "odds, and a news-sentiment feed are scoped for a later pass. The Economic "
        "Policy Uncertainty index above is the live proxy for political/policy risk.")
    _badge(epu, copper, gold, *hist_results)
