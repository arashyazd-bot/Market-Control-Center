"""Panel renderers — one function per dashboard tab. Each pulls from the data
layer, surfaces a live/sample badge, and draws charts via components.charts."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
import plotly.graph_objects as go

from components import charts, gauges
from components.charts import c as chart_color
from data import composite, fmp, fred, macro, markets, sentiment, valuation
from utils.formatting import (fmt_delta, fmt_num, good_bad_color,
                              percentile_label, valuation_verdict_good)


# Timelines + the sector-strength heatmap: zoom/pan via drag + modebar, but
# scrollZoom is OFF so a two-finger page scroll over a chart never zooms it.
_CONFIG_TIMELINE = {
    "scrollZoom": False,
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "displaylogo": False,
    "doubleClick": "reset",      # double-click resets the view
}

# Bar charts: no zoom/pan/scroll/modebar — hover tooltips only.
_CONFIG_STATIC = {
    "scrollZoom": False,
    "displayModeBar": False,
    "doubleClick": False,
    "displaylogo": False,
}

# Gauges: fully static, no interaction at all.
_CONFIG_GAUGE = {
    "displayModeBar": False,
    "staticPlot": True,
}


def _badge(*results) -> None:
    sample_notes = [r.note for r in results if getattr(r, "is_sample", False)]
    if sample_notes:
        st.caption(f"🟡 sample data in use ({len(sample_notes)} source(s)) — "
                   "add a FRED_API_KEY and internet for live values")
    else:
        st.caption("🟢 live data")


def _chart(fig, key: str, kind: str = "timeline") -> None:
    """Render a Plotly figure.

    kind="timeline" → pan/zoom enabled (no scroll-zoom); for time series + heatmap.
    kind="static"   → axes locked (no zoom/pan/scroll), hover kept; for bar charts.
    kind="gauge"    → fully static indicator.
    """
    if kind == "static":
        fig.update_layout(dragmode=False)
        try:
            fig.update_xaxes(fixedrange=True)
            fig.update_yaxes(fixedrange=True)
        except Exception:
            pass
        cfg = _CONFIG_STATIC
    elif kind == "gauge":
        cfg = _CONFIG_GAUGE
    else:
        cfg = _CONFIG_TIMELINE
    st.plotly_chart(fig, use_container_width=True, key=key, config=cfg)


def _gauge_header(main: str, sub: str, sub_color: str | None = None) -> None:
    """Centered title above a dial. Rendered in markdown (not inside the Plotly
    indicator) so both dials' titles align and never overlap the arc."""
    sc = sub_color or "var(--c-sub)"
    st.markdown(
        f"<div style='text-align:center;font-family:Figtree,system-ui,sans-serif;"
        f"line-height:1.25;margin:0 0 -6px'>"
        f"<div style='font-size:1.05rem;font-weight:700;color:var(--c-text)'>{main}</div>"
        f"<div style='font-size:0.95rem;font-weight:600;color:{sc}'>{sub}</div>"
        f"</div>", unsafe_allow_html=True)


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
        _gauge_header("Market Regime", regime.data["label"], regime.data["color"])
        _chart(gauges.regime_gauge(regime.data["score"], regime.data["color"]),
               key="overview_regime", kind="gauge")
    with g2:
        _gauge_header("Fear &amp; Greed", fg.data["rating"])
        _chart(gauges.fear_greed_gauge(fg.data["score"]),
               key="overview_feargreed", kind="gauge")

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
    cape_lbl = percentile_label(v.get("cape_pct", float("nan")))
    c1.metric("Shiller CAPE", fmt_num(v["cape"], 1), cape_lbl,
              delta_color=good_bad_color(valuation_verdict_good(cape_lbl)))
    buf_lbl = percentile_label(v.get("buffett_pct", float("nan")))
    c2.metric("Buffett Indicator", fmt_num(v["buffett"], 0, suffix="%"), buf_lbl,
              delta_color=good_bad_color(valuation_verdict_good(buf_lbl)))
    # ERP: a positive equity risk premium (stocks yield more than 10Y) is good;
    # negative is a late-cycle warning (bad). NaN -> neutral.
    erp = v.get("erp", float("nan"))
    erp_good = None if erp != erp else (erp >= 0)   # NaN != NaN
    c3.metric("Equity Risk Premium", fmt_num(erp, 2, suffix="%"),
              "earnings yield − 10Y", delta_color=good_bad_color(erp_good))

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
        _gauge_header("Fear &amp; Greed", fg.data["rating"])
        _chart(gauges.fear_greed_gauge(fg.data["score"]),
               key="sent_feargreed", kind="gauge")
        st.metric("Breadth: Equal-wt − Cap-wt (YTD)",
                  fmt_num(concentration.data, 1, suffix="%"),
                  "negative = narrow / mega-cap led", delta_color="off")
    with c2:
        _chart(charts.line_chart(fg.data["history"], "Fear & Greed (1Y)",
                                 color=chart_color("yellow")), key="sent_fg_hist")

    _chart(charts.line_chart(vix_hist.data["Close"], "VIX (1Y)",
                             color=chart_color("danger")), key="sent_vix")
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
    # 10y of prices so the YoY series spans multiple years and reads as a real
    # comparison against GDP (dual_axis_chart aligns them to their shared window).
    sp = markets.price_history("^GSPC", period="10y")

    _chart(charts.yield_curve_chart(curve.data), key="rates_curve", kind="static")

    c1, c2 = st.columns(2)
    with c1:
        _chart(charts.spread_chart(s_10y2y.data, "10Y–2Y Spread (recession signal)"),
               key="rates_10y2y")
    with c2:
        _chart(charts.spread_chart(s_10y3m.data, "10Y–3M Spread"), key="rates_10y3m")

    cc1, cc2 = st.columns(2)
    with cc1:
        _chart(charts.line_chart(hy.data, "High-Yield Credit Spread (OAS)",
                                 color=chart_color("danger"), y_suffix="%",
                                 recessions=True), key="rates_hy")
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
                                 color=chart_color("danger"), y_suffix="%",
                                 recessions=True), key="lead_recprob")
    with lc2:
        _chart(charts.line_chart(sent.data, "Consumer Sentiment (UMich)",
                                 color=chart_color("yellow")), key="lead_sentiment")

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
                                 color=chart_color("warning")), key="cross_coppergold")
    with cg2:
        _chart(charts.line_chart(epu.data, "Economic Policy Uncertainty Index",
                                 color=chart_color("purple")), key="cross_epu")

    st.info(
        "**Policy & news (v1 placeholder):** live AAII survey, CME FedWatch rate-cut "
        "odds, and a news-sentiment feed are scoped for a later pass. The Economic "
        "Policy Uncertainty index above is the live proxy for political/policy risk.")
    _badge(epu, copper, gold, *hist_results)


# ---------------------------------------------------------------------------
# 6. Market Intelligence (stock/sector level)
# ---------------------------------------------------------------------------
def render_intelligence() -> None:
    st.subheader("Market Intelligence — Stock & Sector")
    st.caption(f"Active source: **{macro.active_source()}** · stock-level data needs an FMP key")

    # --- Sector valuation (P/E) ---
    st.markdown("##### Sector Valuation (trailing P/E)")
    pe = fmp.get_sector_pe()
    df_pe = pe.data.sort_values("pe")
    colors = [chart_color("success") if v < 25 else
              chart_color("yellow") if v < 40 else chart_color("danger")
              for v in df_pe["pe"]]
    fig = go.Figure(go.Bar(
        x=df_pe["pe"], y=df_pe["sector"], orientation="h", marker_color=colors,
        text=[f"{v:.0f}×" for v in df_pe["pe"]], textposition="outside"))
    from components.charts import _layout as _cl
    fig.update_layout(**_cl(height=280, margin=dict(l=28, r=28, t=14, b=21)))
    fig.update_xaxes(title="Price / Earnings")
    _chart(fig, key="intel_sector_pe", kind="static")
    st.caption("Green <25× · amber 25–40× · red >40× (richly valued)")

    # --- Analyst spotlight (watchlist) ---
    st.divider()
    st.markdown("##### Analyst Spotlight — Mega-Cap Watchlist")
    consensus = [fmp.get_analyst_consensus(s) for s in config.ANALYST_WATCHLIST]
    rows = [c.data for c in consensus]
    table = pd.DataFrame([{
        "Symbol": r["symbol"], "Rating": r["consensus"],
        "Buy": r["buy"], "Hold": r["hold"], "Sell": r["sell"],
        "Target Low": r["target_low"], "Target Cons.": r["target_consensus"],
        "Target High": r["target_high"],
    } for r in rows])

    a1, a2 = st.columns([3, 2])
    with a1:
        fig2 = go.Figure()
        syms = table["Symbol"]
        fig2.add_bar(y=syms, x=table["Buy"], name="Buy", orientation="h",
                     marker_color=chart_color("success"))
        fig2.add_bar(y=syms, x=table["Hold"], name="Hold", orientation="h",
                     marker_color=chart_color("yellow"))
        fig2.add_bar(y=syms, x=table["Sell"], name="Sell", orientation="h",
                     marker_color=chart_color("danger"))
        from components.charts import _layout as _cl
        fig2.update_layout(barmode="stack", title="Analyst ratings distribution",
                           **_cl(height=224))
        _chart(fig2, key="intel_ratings", kind="static")
    with a2:
        st.dataframe(table[["Symbol", "Rating", "Target Cons."]],
                     hide_index=True, width="stretch", height=320)
    with st.expander("Full analyst price targets"):
        st.dataframe(table, hide_index=True, width="stretch")

    # --- Market movers ---
    st.divider()
    st.markdown("##### Today's Market Movers")
    gainers = fmp.get_movers("gainers")
    losers = fmp.get_movers("losers")
    g, l = st.columns(2)
    with g:
        st.markdown("**🟢 Top gainers**")
        st.dataframe(gainers.data, hide_index=True, width="stretch")
    with l:
        st.markdown("**🔴 Top losers**")
        st.dataframe(losers.data, hide_index=True, width="stretch")

    # --- Congressional trades ---
    st.divider()
    st.markdown("##### Congressional Trading (Senate disclosures)")
    congress = fmp.get_congressional_trades()
    st.dataframe(congress.data, hide_index=True, width="stretch")
    if congress.is_sample:
        st.caption("🟡 sample — live Senate/House disclosures need an FMP Starter+ plan")

    _badge(pe, gainers, losers, congress, *consensus)
