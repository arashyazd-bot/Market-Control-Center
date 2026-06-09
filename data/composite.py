"""Composite regime signal. Blends a weighted basket of normalized sub-scores
(each in [-1, +1], positive = risk-on) into one headline number and a
Risk-Off / Neutral / Risk-On label."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from data import DataResult, macro, markets, sentiment, valuation
from utils.formatting import clamp


def _lin(value: float, low_score_at: float, high_score_at: float) -> float:
    """Map ``value`` linearly to [-1, 1] given the inputs that should score
    -1 (``low_score_at``) and +1 (``high_score_at``)."""
    if value != value:  # NaN
        return 0.0
    if high_score_at == low_score_at:
        return 0.0
    t = (value - low_score_at) / (high_score_at - low_score_at)
    return clamp(2 * t - 1)


def label_for(score: float):
    for lo, hi, label, color in config.REGIME_BANDS:
        if lo <= score < hi:
            return label, color
    return "Neutral", "#f4a261"


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def compute_regime() -> DataResult:
    components = {}
    is_sample = False

    # Yield-curve slope (10Y-2Y): inverted = risk-off.
    curve = macro.yield_curve()
    is_sample |= curve.is_sample
    try:
        slope = float(curve.data.get(10)) - float(curve.data.get(2))
    except Exception:
        slope = 0.0
    components["yield_curve"] = _lin(slope, low_score_at=-1.0, high_score_at=1.0)

    # Credit spreads (HY OAS): tight = risk-on.
    hy = macro.series("hy_oas")
    is_sample |= hy.is_sample
    components["credit"] = _lin(macro.latest(hy), low_score_at=config.HY_OAS_WIDE,
                                high_score_at=config.HY_OAS_TIGHT)

    # VIX: calm = risk-on.
    vix = markets.quote("^VIX")
    is_sample |= vix.is_sample
    components["vix"] = _lin(vix.data["price"], low_score_at=config.VIX_PANIC,
                             high_score_at=config.VIX_CALM)

    # Fear & Greed: greed = risk-on.
    fg = sentiment.get_fear_greed()
    is_sample |= fg.is_sample
    components["fear_greed"] = _lin(fg.data["score"], low_score_at=0, high_score_at=100)

    # Trend: SP500 vs 200DMA.
    trend = markets.above_200dma(config.SPY)
    is_sample |= trend.is_sample
    components["trend"] = _lin(trend.data, low_score_at=-10, high_score_at=10)

    # Valuation: cheap = risk-on (long-horizon tilt).
    val = valuation.get_valuation()
    is_sample |= val.is_sample
    components["valuation"] = _lin(val.data["cape"], low_score_at=config.CAPE_EXPENSIVE,
                                   high_score_at=config.CAPE_CHEAP)

    # Sahm rule: < 0.5 = no recession trigger = risk-on.
    sahm = macro.series("sahm")
    is_sample |= sahm.is_sample
    components["sahm"] = _lin(macro.latest(sahm), low_score_at=1.0, high_score_at=0.0)

    # Weighted blend.
    total_w = sum(config.COMPOSITE_WEIGHTS.values())
    score = sum(config.COMPOSITE_WEIGHTS[k] * components[k] for k in config.COMPOSITE_WEIGHTS) / total_w
    score = clamp(score)
    label, color = label_for(score)

    return DataResult(
        {"score": score, "label": label, "color": color, "components": components},
        is_sample=is_sample,
        source="derived" if not is_sample else "sample",
    )


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def regime_history(years: int = 8) -> DataResult:
    """Historical composite regime, monthly, from the components that HAVE
    history (curve slope, HY credit, VIX, S&P-vs-200DMA, Sahm) — re-weighted and
    scored with the same mappings. Plotted vs NBER recessions for credibility."""
    keys = ["yield_curve", "credit", "vix", "trend", "sahm"]
    w = {k: config.COMPOSITE_WEIGHTS[k] for k in keys}
    tot = sum(w.values())

    sl = macro.spread_series("s10y2y")
    hy = macro.series("hy_oas")
    vixh = markets.price_history("^VIX", period="10y")
    spyh = markets.price_history("SPY", period="10y")
    sahm = macro.series("sahm")
    is_sample = any(r.is_sample for r in (sl, hy, vixh, spyh, sahm))

    def _m(s):
        try:
            return s.resample("ME").last()
        except Exception:
            return s

    try:
        spy = spyh.data["Close"]
        df = pd.DataFrame({
            "yield_curve": _m(sl.data),
            "credit": _m(hy.data),
            "vix": _m(vixh.data["Close"]),
            "trend": _m((spy / spy.rolling(200).mean() - 1) * 100),
            "sahm": _m(sahm.data),
        }).dropna(how="all").iloc[-years * 12:]

        sc = pd.DataFrame(index=df.index)
        sc["yield_curve"] = df["yield_curve"].map(lambda v: _lin(v, -1.0, 1.0))
        sc["credit"] = df["credit"].map(lambda v: _lin(v, config.HY_OAS_WIDE, config.HY_OAS_TIGHT))
        sc["vix"] = df["vix"].map(lambda v: _lin(v, config.VIX_PANIC, config.VIX_CALM))
        sc["trend"] = df["trend"].map(lambda v: _lin(v, -10, 10))
        sc["sahm"] = df["sahm"].map(lambda v: _lin(v, 1.0, 0.0))

        score = sum(w[k] * sc[k].fillna(0.0) for k in keys) / tot
        score = score.clip(-1, 1).dropna()
        score.name = "regime"
        if score.empty:
            raise ValueError("empty regime history")
        return DataResult(score, is_sample=is_sample,
                          source="derived" if not is_sample else "sample")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="sample", note=str(exc)[:80])
