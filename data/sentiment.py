"""Sentiment — the CNN Fear & Greed Index via its public JSON feed. CNN's
endpoint refuses connections from many cloud IPs (e.g. Render), so when it's
unreachable we compute a transparent **proxy** from live market data
(VIX + S&P momentum + high-yield credit) instead of falling back to fabricated
sample data. Clearly labelled source='proxy'."""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

import config
from data import DataResult
from data import sample


def _lin(value: float, lo: float, hi: float):
    """Map value to 0-100 with lo->0, hi->100 (clamped). None if NaN."""
    if value != value:
        return None
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


def _proxy() -> DataResult | None:
    """Volatility/momentum/credit Fear & Greed proxy from live data (no CNN)."""
    from data import macro, markets
    try:
        vix_q = markets.quote("^VIX")
        spy = markets.price_history("SPY", period="1y")
        if vix_q.is_sample or spy.is_sample:
            return None
        parts = []
        v_now = _lin(float(vix_q.data["price"]), 35.0, 13.0)   # calm VIX = greed
        if v_now is not None:
            parts.append(v_now)
        close = spy.data["Close"]
        mom = float((close.iloc[-1] / close.rolling(125).mean().iloc[-1] - 1) * 100)
        m = _lin(mom, -10.0, 10.0)                              # positive momentum = greed
        if m is not None:
            parts.append(m)
        hy = macro.series("hy_oas")
        if not hy.is_sample:
            cr = _lin(float(macro.latest(hy)), 8.0, 3.0)        # tight credit = greed
            if cr is not None:
                parts.append(cr)
        if not parts:
            return None
        score = round(sum(parts) / len(parts), 1)

        # Proxy 1Y history from VIX (inverted, volatility-implied sentiment).
        vh = markets.price_history("^VIX", period="1y")
        if not vh.is_sample:
            v = vh.data["Close"].clip(13, 35)
            hist = ((35 - v) / (35 - 13) * 100).rename("fear_greed")
        else:
            hist = sample.fear_greed()["history"]

        return DataResult({"score": score, "rating": sample.rating_for(score),
                           "history": hist}, is_sample=False, source="proxy",
                          note="VIX+momentum+credit proxy (CNN unreachable)")
    except Exception:
        return None


@st.cache_data(ttl=config.TTL_SENTIMENT, show_spinner=False)
def get_fear_greed() -> DataResult:
    """CNN Fear & Greed → live proxy (cloud-resilient) → sample."""
    try:
        resp = requests.get(config.CNN_FEAR_GREED_URL, headers=config.BROWSER_HEADERS,
                            timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        fg = payload["fear_and_greed"]
        score = float(fg["score"])
        rating = fg.get("rating", sample.rating_for(score)).title()
        hist_raw = payload.get("fear_and_greed_historical", {}).get("data", [])
        if hist_raw:
            idx = pd.to_datetime([p["x"] for p in hist_raw], unit="ms")
            hist = pd.Series([p["y"] for p in hist_raw], index=idx, name="fear_greed")
        else:
            hist = sample.fear_greed()["history"]
        return DataResult({"score": score, "rating": rating, "history": hist},
                          is_sample=False, source="CNN")
    except Exception as exc:
        proxy = _proxy()
        if proxy is not None:
            return proxy
        return DataResult(sample.fear_greed(), is_sample=True, source="sample",
                          note=f"CNN:{exc}"[:80])
