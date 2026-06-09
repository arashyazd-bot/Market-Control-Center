"""Panel renderers — one function per dashboard tab. Each pulls from the data
layer, surfaces a live/sample badge, and draws charts via components.charts."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, wait

import pandas as pd
import streamlit as st

import config
import plotly.graph_objects as go

from components import charts, gauges
from components.charts import c as chart_color
from data import (composite, cycle, fmp, fred, macro, markets, router, sentiment,
                  valuation)
from utils.formatting import (fmt_delta, fmt_num, good_bad_color,
                              percentile_label, valuation_verdict_good)
from utils.summary import executive_summary

try:  # attach the script context to worker threads so st.cache_data stays quiet
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except Exception:  # pragma: no cover - shifts with Streamlit version
    add_script_run_ctx = get_script_run_ctx = None


def warm_caches(budget_s: float = 4.0) -> None:
    """Fetch independent data series concurrently to warm the st.cache_data
    caches before panels render.

    BOUNDED: the render waits at most ``budget_s`` seconds; any slow fetch keeps
    running in a background thread and populates the cache for later interactions,
    so this can never stall the page (the bug that hung the live site when a
    blocking prefetch hit Render-throttled yfinance). Every underlying fetch also
    has its own network timeout. A fast no-op once the caches are warm.
    """
    ctx = get_script_run_ctx() if get_script_run_ctx else None

    quote_tickers = set(config.CROSS_ASSET.values()) | {
        "^GSPC", "^IXIC", "^DJI", "^VIX", "^TNX", "GC=F", "CL=F", "BTC-USD"}
    hist_1y = set(config.CROSS_ASSET.values()) | {"^VIX", "SPY", "RSP", "HG=F", "GC=F"}
    macro_keys = ["hy_oas", "ig_oas", "unemployment", "sahm", "cpi", "fed_funds",
                  "umich_sentiment", "initial_claims", "mortgage_30y", "recession_prob"]

    thunks: list = []
    thunks += [lambda t=t: markets.quote(t) for t in quote_tickers]
    thunks += [lambda t=t: markets.price_history(t, "1y") for t in hist_1y]
    thunks += [lambda k=k: macro.series(k) for k in macro_keys]
    thunks += [lambda s=s: fmp.get_analyst_consensus(s) for s in config.ANALYST_WATCHLIST]
    thunks += [
        lambda: markets.price_history("^GSPC", "10y"),
        markets.sector_performance,
        composite.compute_regime,
        sentiment.get_fear_greed,
        valuation.get_valuation,
        macro.yield_curve,
        macro.gdp_growth,
        lambda: macro.spread_series("s10y2y"),
        lambda: macro.spread_series("s10y3m"),
        lambda: fred.get_series("spread_10y2y"),
        lambda: fred.get_series("policy_uncertainty"),
        fmp.get_sector_pe,
        lambda: fmp.get_movers("gainers"),
        lambda: fmp.get_movers("losers"),
        fmp.get_congressional_trades,
        fmp.get_economic_calendar,
    ]

    def run(fn) -> None:
        if ctx and add_script_run_ctx:
            add_script_run_ctx(threading.current_thread(), ctx)
        try:
            fn()
        except Exception:
            pass  # panels re-fetch and surface their own sample/live badge

    ex = ThreadPoolExecutor(max_workers=8)
    futures = [ex.submit(run, fn) for fn in thunks]
    wait(futures, timeout=budget_s)   # proceed after budget; stragglers finish in bg
    ex.shutdown(wait=False)


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


def _reason(results) -> tuple | None:
    """(count, human reason) for why sources fell back, from their .note text —
    or None if everything is live. Replaces the old canned 'add a FRED_API_KEY'."""
    notes = [(getattr(r, "note", "") or "") for r in results
             if getattr(r, "is_sample", False)]
    if not notes:
        return None
    blob = " ".join(notes).lower()
    if any(k in blob for k in ("429", "limit reach", "too many")):
        why = "FMP daily request limit reached — resets in ~24h"
    elif "402" in blob or "premium" in blob or "starter" in blob:
        why = "needs a paid FMP tier"
    elif any(k in blob for k in ("invalid api key", "no fmp key", "no fred key", "missing")):
        why = "missing/invalid API key"
    elif any(k in blob for k in ("ssl", "timeout", "timed out", "connection", "urlopen", "max retries")):
        why = "network/connection issue"
    else:
        why = "live source unavailable"
    return len(notes), why


def _badge(*results) -> None:
    """Honest live/sample badge: states how many feeds are on sample and WHY."""
    info = _reason(results)
    if info:
        n, why = info
        st.caption(f"🟡 {n} feed(s) showing sample data — {why}")
    else:
        st.caption("🟢 live data")


def _unavailable(result, what: str = "Live data") -> None:
    """Explicit honest empty-state for a table/section whose source is sample —
    no fabricated rows. States what's missing and why."""
    info = _reason([result])
    why = info[1] if info else "live source unavailable"
    st.info(f"**{what} unavailable** — {why}. Shows live when the source is reachable.")


def _mv(result, text: str) -> str:
    """Honest metric value — '—' when the source is sample, so no fabricated
    number is ever shown as if it were live."""
    return "—" if getattr(result, "is_sample", False) else text


def _md(result, text):
    """Metric delta — hidden when the source is sample."""
    return None if getattr(result, "is_sample", False) else text


def _q(result, key, default=float("nan")):
    """Safe field access — never crashes even if a feed returned data=None."""
    try:
        return result.data[key]
    except Exception:
        return default


def _chart(fig, key: str, kind: str = "timeline", sample: bool = False) -> None:
    """Render a Plotly figure.

    kind="timeline" → pan/zoom enabled (no scroll-zoom); for time series + heatmap.
    kind="static"   → axes locked (no zoom/pan/scroll), hover kept; for bar charts.
    kind="gauge"    → fully static indicator.
    sample=True      → overlay a 'SAMPLE DATA' watermark so a fabricated chart can
                       never be mistaken for a live one.
    """
    if sample:
        fig.add_annotation(text="SAMPLE DATA · not live", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, textangle=-18,
                           font=dict(size=22, color="rgba(150,150,150,0.40)"))
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
        f"<div style='font-size:1.23rem;font-weight:700;color:var(--c-text)'>{main}</div>"
        f"<div style='font-size:1.13rem;font-weight:600;color:{sc}'>{sub}</div>"
        f"</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 1. Overview
# ---------------------------------------------------------------------------
def _top_mover():
    """Biggest |1-day move| across headline assets (cache hits from the ticker)."""
    best = None
    for name, tk in [("S&P 500", "^GSPC"), ("Nasdaq", "^IXIC"), ("Dow", "^DJI"),
                     ("Gold", "GC=F"), ("Bitcoin", "BTC-USD"), ("Oil", "CL=F")]:
        q = markets.quote(tk)
        if q.is_sample:
            continue
        chg = q.data.get("change_pct")
        if chg is None or chg != chg:
            continue
        if best is None or abs(chg) > abs(best[1]):
            best = (name, chg)
    return best


def _render_methodology(regime, cyc) -> None:
    with st.expander("Methodology & live data sources"):
        st.markdown("**Market regime** — weighted, normalized blend of the signals below "
                    "(each scored −1 risk-off … +1 risk-on):")
        comp = regime.data["components"]
        st.dataframe(pd.DataFrame({
            "Signal": list(comp.keys()),
            "Sub-score": [round(v, 2) for v in comp.values()],
            "Weight": [config.COMPOSITE_WEIGHTS[k] for k in comp],
        }), hide_index=True, width="stretch")
        st.markdown("**Business cycle** — deterministic rules over the yield-curve slope, "
                    "high-yield credit spreads, recession probability, the Sahm rule and the "
                    "unemployment trend. No models, no token cost.")
        st.markdown("**Live data sources** — each value is served by the first reachable "
                    "provider and tracked end-to-end:")
        rs = router.status()
        if rs:
            rows = []
            for s, v in sorted(rs.items()):
                if v["cooldown"] > 0:
                    state = f"🟡 cooldown {v['cooldown']}s"
                elif v["note"] == "ok":
                    state = "🟢 ok"
                else:
                    state = f"🟡 {v['note'][:46]}"
                rows.append({"Source": s, "Status": state})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Priority — macro: FRED → US Treasury → FMP · markets: FMP → Yahoo → Stooq "
                   "→ CoinGecko · sentiment: CNN · then bundled sample (clearly marked).")


def render_overview() -> None:
    regime = composite.compute_regime()
    cyc = cycle.compute_cycle()
    sp = markets.quote("^GSPC")
    vix = markets.quote("^VIX")
    spread = fred.get_series("spread_10y2y")
    fg = sentiment.get_fear_greed()
    val = valuation.get_valuation()

    # --- Executive summary (rule-based; zero token cost) ---
    slope, sahm, hy = cyc.data["slope"], cyc.data["sahm"], cyc.data["hy"]
    facts = {
        "regime_label": None if regime.is_sample else regime.data["label"],
        "regime_score": regime.data["score"],
        "cycle_phase": None if cyc.is_sample else cyc.data["phase"],
        "cycle_note": cyc.data["rationale"][0] if cyc.data["rationale"] else "",
        "curve_inverted": slope == slope and slope < 0,
        "sahm_triggered": sahm == sahm and sahm >= 0.5,
        "credit_widening": hy == hy and hy > 5.0,
        "cape": float("nan") if val.is_sample else val.data.get("cape", float("nan")),
        "vix": float("nan") if vix.is_sample else vix.data["price"],
        "top_mover": _top_mover(),
    }
    items = "".join(f"<li>{b}</li>" for b in executive_summary(facts))
    st.markdown(f"<div class='mcc-exec'><div class='mcc-exec-h'>Executive Summary</div>"
                f"<ul>{items}</ul></div>", unsafe_allow_html=True)

    # --- KPI row ---
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("S&P 500", _mv(sp, fmt_num(_q(sp, "price"), 0)),
              _md(sp, fmt_delta(_q(sp, "change_pct"))))
    k2.metric("VIX", _mv(vix, fmt_num(_q(vix, "price"), 2)),
              _md(vix, fmt_delta(_q(vix, "change_pct"))), delta_color="inverse")
    k3.metric("10Y–2Y Spread", _mv(spread, fmt_num(fred.latest(spread), 2, suffix="%")))
    k4.metric("Fear & Greed", _mv(fg, fmt_num(_q(fg, "score"), 0)),
              _md(fg, _q(fg, "rating", "")), delta_color="off")
    k5.metric("Regime", _mv(regime, regime.data["label"]))

    st.divider()
    # --- Three dials: Regime | Business Cycle | Fear & Greed ---
    g1, g2, g3 = st.columns(3)
    with g1:
        _gauge_header("Market Regime",
                      "—" if regime.is_sample else regime.data["label"], regime.data["color"])
        _chart(gauges.regime_gauge(regime.data["score"], regime.data["color"]),
               key="ov_regime", kind="gauge", sample=regime.is_sample)
    with g2:
        _gauge_header("Business Cycle",
                      "—" if cyc.is_sample else cyc.data["phase"], cyc.data["color"])
        _chart(gauges.cycle_gauge(cyc.data["position"], cyc.data["color"]),
               key="ov_cycle", kind="gauge", sample=cyc.is_sample)
    with g3:
        _gauge_header("Fear &amp; Greed", "—" if fg.is_sample else
                      (fg.data["rating"] + (" · proxy" if fg.source == "proxy" else "")))
        _chart(gauges.fear_greed_gauge(fg.data["score"]),
               key="ov_fg", kind="gauge", sample=fg.is_sample)

    if not cyc.is_sample and cyc.data["rationale"]:
        with st.expander("Why this cycle phase"):
            for r in cyc.data["rationale"]:
                st.markdown(f"- {r}")

    st.divider()
    # --- Composite regime history (backtest credibility) ---
    st.markdown("##### Composite Regime — History vs Recessions")
    hist = composite.regime_history()
    if hist.data is not None and len(hist.data):
        _chart(charts.spread_chart(hist.data,
               "Composite Regime (monthly · −1 risk-off … +1 risk-on)",
               y_suffix="", recessions=True), key="ov_regime_hist", sample=hist.is_sample)
        st.caption("Reconstructed from the components with history (curve, credit, VIX, trend, "
                   "Sahm). Shaded bands = NBER recessions.")
    else:
        _unavailable(hist, "Regime history")

    _render_methodology(regime, cyc)
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
    c1.metric("Shiller CAPE", _mv(val, fmt_num(v["cape"], 1)), _md(val, cape_lbl),
              delta_color=good_bad_color(valuation_verdict_good(cape_lbl)))
    buf_lbl = percentile_label(v.get("buffett_pct", float("nan")))
    c2.metric("Buffett Indicator", _mv(val, fmt_num(v["buffett"], 0, suffix="%")),
              _md(val, buf_lbl), delta_color=good_bad_color(valuation_verdict_good(buf_lbl)))
    # ERP: a positive equity risk premium (stocks yield more than 10Y) is good;
    # negative is a late-cycle warning (bad). NaN -> neutral.
    erp = v.get("erp", float("nan"))
    erp_good = None if erp != erp else (erp >= 0)   # NaN != NaN
    c3.metric("Equity Risk Premium", _mv(val, fmt_num(erp, 2, suffix="%")),
              _md(val, "earnings yield − 10Y"), delta_color=good_bad_color(erp_good))

    c4, c5, c6 = st.columns(3)
    c4.metric("Trailing P/E", _mv(val, fmt_num(v["pe_ttm"], 1)))
    c5.metric("Forward P/E", _mv(val, fmt_num(v["forward_pe"], 1)))
    c6.metric("Dividend Yield", _mv(val, fmt_num(v["dividend_yield"], 2, suffix="%")))

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
        _gauge_header("Fear &amp; Greed", "—" if fg.is_sample else
                      (fg.data["rating"] + (" · proxy" if fg.source == "proxy" else "")))
        _chart(gauges.fear_greed_gauge(fg.data["score"]),
               key="sent_feargreed", kind="gauge", sample=fg.is_sample)
        st.metric("Breadth: Equal-wt − Cap-wt (YTD)",
                  _mv(concentration, fmt_num(concentration.data, 1, suffix="%")),
                  "negative = narrow / mega-cap led", delta_color="off")
    with c2:
        _chart(charts.line_chart(fg.data["history"], "Fear & Greed (1Y)",
                                 color=chart_color("yellow")), key="sent_fg_hist",
               sample=fg.is_sample)

    _chart(charts.line_chart(vix_hist.data["Close"], "VIX (1Y)",
                             color=chart_color("danger")), key="sent_vix",
           sample=vix_hist.is_sample)
    _chart(charts.sector_heatmap(sectors.data), key="sent_sectors",
           sample=sectors.is_sample)
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

    _chart(charts.yield_curve_chart(curve.data), key="rates_curve", kind="static",
           sample=curve.is_sample)

    c1, c2 = st.columns(2)
    with c1:
        _chart(charts.spread_chart(s_10y2y.data, "10Y–2Y Spread (recession signal)"),
               key="rates_10y2y", sample=s_10y2y.is_sample)
    with c2:
        _chart(charts.spread_chart(s_10y3m.data, "10Y–3M Spread"), key="rates_10y3m",
               sample=s_10y3m.is_sample)

    cc1, cc2 = st.columns(2)
    with cc1:
        _chart(charts.line_chart(hy.data, "High-Yield Credit Spread (OAS)",
                                 color=chart_color("danger"), y_suffix="%",
                                 recessions=True), key="rates_hy", sample=hy.is_sample)
    with cc2:
        sp_yoy = (sp.data["Close"].pct_change(252) * 100).dropna()
        _chart(charts.dual_axis_chart(gdp.data, sp_yoy, "Real GDP growth %",
                                      "S&P 500 YoY %", "Growth: Economy vs Market"),
               key="rates_gdp", sample=(gdp.is_sample or sp.is_sample))

    # Macro tiles.
    unemp = macro.series("unemployment")
    sahm = macro.series("sahm")
    cpi = macro.series("cpi")
    ff = macro.series("fed_funds")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Unemployment", _mv(unemp, fmt_num(macro.latest(unemp), 1, suffix="%")))
    m2.metric("Sahm Rule", _mv(sahm, fmt_num(macro.latest(sahm), 2)),
              "≥0.50 = recession trigger", delta_color="off")
    m3.metric("CPI YoY", _mv(cpi, fmt_num(macro.yoy_change(cpi), 1, suffix="%")))
    m4.metric("Fed Funds", _mv(ff, fmt_num(macro.latest(ff), 2, suffix="%")))

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
    t1.metric("Consumer Sentiment", _mv(sent, fmt_num(macro.latest(sent), 1)),
              "U. of Michigan", delta_color="off")
    t2.metric("Initial Claims", _mv(claims, fmt_num(macro.latest(claims), 0)),
              "weekly", delta_color="off")
    t3.metric("30Y Mortgage", _mv(mortgage, fmt_num(macro.latest(mortgage), 2, suffix="%")),
              "real-estate cost", delta_color="off")
    t4.metric("Recession Prob.", _mv(recprob, fmt_num(macro.latest(recprob), 2, suffix="%")),
              "smoothed (FRED/FMP)", delta_color="off")

    lc1, lc2 = st.columns(2)
    with lc1:
        _chart(charts.line_chart(recprob.data, "Smoothed US Recession Probability",
                                 color=chart_color("danger"), y_suffix="%",
                                 recessions=True), key="lead_recprob", sample=recprob.is_sample)
    with lc2:
        _chart(charts.line_chart(sent.data, "Consumer Sentiment (UMich)",
                                 color=chart_color("yellow")), key="lead_sentiment",
               sample=sent.is_sample)

    # Upcoming high-impact US releases.
    cal = router.chain([("FMP", fmp.get_economic_calendar)])
    st.markdown("**Upcoming US economic releases**")
    if cal.is_sample or cal.data is None:
        _unavailable(cal, "Economic calendar")
    else:
        st.dataframe(cal.data, hide_index=True, width="stretch")
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
        col.metric(name, _mv(q, fmt_num(_q(q, "price"), 2)),
                   _md(q, fmt_delta(_q(q, "change_pct"))))
        h = markets.price_history(ticker, period="1y")
        hist_results.append(h)
        series_map[name] = h.data["Close"]

    _chart(charts.normalized_multi(series_map, "Cross-Asset (1Y, rebased to 100)"),
           key="cross_multi", sample=any(h.is_sample for h in hist_results))

    # Copper/Gold ratio — a growth/inflation barometer.
    copper = markets.price_history("HG=F", period="1y")
    gold = markets.price_history("GC=F", period="1y")
    ratio = (copper.data["Close"] / gold.data["Close"]).dropna()
    epu = fred.get_series("policy_uncertainty")
    cg1, cg2 = st.columns(2)
    with cg1:
        _chart(charts.line_chart(ratio, "Copper / Gold ratio (growth barometer)",
                                 color=chart_color("warning")), key="cross_coppergold",
               sample=(copper.is_sample or gold.is_sample))
    with cg2:
        _chart(charts.line_chart(epu.data, "Economic Policy Uncertainty Index",
                                 color=chart_color("purple")), key="cross_epu",
               sample=epu.is_sample)

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
    st.caption("Stock & sector intelligence is FMP-only (no free fallback). Each feed shows "
               "live data, or an explicit note when FMP's free-tier limit/tier blocks it.")

    def _fmp(fn):   # route through the router for provenance + quota-skip; no sample
        return router.chain([("FMP", fn)])

    # --- Sector valuation (P/E) ---
    st.markdown("##### Sector Valuation (trailing P/E)")
    pe = _fmp(fmp.get_sector_pe)
    if pe.is_sample or pe.data is None:
        _unavailable(pe, "Sector P/E")
    else:
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
    consensus = [_fmp(lambda s=s: fmp.get_analyst_consensus(s)) for s in config.ANALYST_WATCHLIST]
    live_consensus = [c for c in consensus if not c.is_sample and c.data]
    if not live_consensus:
        _unavailable(consensus[0], "Analyst consensus")
    else:
        table = pd.DataFrame([{
            "Symbol": r.data["symbol"], "Rating": r.data["consensus"],
            "Buy": r.data["buy"], "Hold": r.data["hold"], "Sell": r.data["sell"],
            "Target Low": r.data["target_low"], "Target Cons.": r.data["target_consensus"],
            "Target High": r.data["target_high"],
        } for r in live_consensus])
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
    gainers = _fmp(lambda: fmp.get_movers("gainers"))
    losers = _fmp(lambda: fmp.get_movers("losers"))
    g, l = st.columns(2)
    with g:
        st.markdown("**🟢 Top gainers**")
        if gainers.is_sample or gainers.data is None:
            _unavailable(gainers, "Top gainers")
        else:
            st.dataframe(gainers.data, hide_index=True, width="stretch")
    with l:
        st.markdown("**🔴 Top losers**")
        if losers.is_sample or losers.data is None:
            _unavailable(losers, "Top losers")
        else:
            st.dataframe(losers.data, hide_index=True, width="stretch")

    # --- Congressional trades ---
    st.divider()
    st.markdown("##### Congressional Trading (Senate disclosures)")
    congress = _fmp(fmp.get_congressional_trades)
    if congress.is_sample or congress.data is None:
        _unavailable(congress, "Congressional trades")
    else:
        st.dataframe(congress.data, hide_index=True, width="stretch")

    _badge(pe, gainers, losers, congress, *consensus)
