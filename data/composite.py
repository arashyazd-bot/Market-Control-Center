"""Composite regime signal. Blends a weighted basket of normalized sub-scores
(each in [-1, +1], positive = risk-on) into one headline number and a
Risk-Off / Neutral / Risk-On label."""
from __future__ import annotations

import streamlit as st

import config
from data import DataResult, fred, markets, sentiment, valuation
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
    spread = fred.get_series("spread_10y2y")
    is_sample |= spread.is_sample
    components["yield_curve"] = _lin(fred.latest(spread), low_score_at=-1.0, high_score_at=1.0)

    # Credit spreads (HY OAS): tight = risk-on.
    hy = fred.get_series("hy_oas")
    is_sample |= hy.is_sample
    components["credit"] = _lin(fred.latest(hy), low_score_at=config.HY_OAS_WIDE,
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
    sahm = fred.get_series("sahm")
    is_sample |= sahm.is_sample
    components["sahm"] = _lin(fred.latest(sahm), low_score_at=1.0, high_score_at=0.0)

    # Weighted blend.
    total_w = sum(config.COMPOSITE_WEIGHTS.values())
    score = sum(config.COMPOSITE_WEIGHTS[k] * components[k] for k in config.COMPOSITE_WEIGHTS) / total_w
    score = clamp(score)
    label, color = label_for(score)

    return DataResult(
        {"score": score, "label": label, "color": color, "components": components},
        is_sample=is_sample,
    )
