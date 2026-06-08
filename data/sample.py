"""Deterministic bundled sample data used as a graceful fallback whenever a live
source or API key is unavailable. Values are plausible but illustrative — they let
the full dashboard render (and be smoke-tested) with no network access.

Every series is seeded so repeated runs are stable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _daily_index(days: int) -> pd.DatetimeIndex:
    end = pd.Timestamp("2026-06-01")
    return pd.date_range(end=end, periods=days, freq="B")


def _seed(name: str) -> np.random.Generator:
    # Stable across processes (Python's str hash is randomized per run).
    import hashlib

    digest = hashlib.md5(name.encode()).hexdigest()
    return np.random.default_rng(int(digest[:8], 16))


def _random_walk(name: str, start: float, days: int, vol: float, drift: float = 0.0) -> pd.Series:
    rng = _seed(name)
    steps = rng.normal(drift, vol, days)
    values = start * np.exp(np.cumsum(steps))
    return pd.Series(values, index=_daily_index(days), name=name)


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------
def yield_curve() -> pd.Series:
    """A mildly inverted curve (short > long) typical of a late-cycle regime."""
    data = {
        0.25: 5.30, 0.5: 5.20, 1: 4.95, 2: 4.55, 5: 4.30,
        7: 4.32, 10: 4.40, 20: 4.70, 30: 4.62,
    }
    return pd.Series(data, name="yield_curve")


# Static "latest value + short history" presets for FRED-style series.
_FRED_PRESETS = {
    "spread_10y2y": (-0.15, 0.05),
    "spread_10y3m": (-0.90, 0.06),
    "fed_funds": (5.33, 0.0),
    "real_yield_10y": (2.05, 0.04),
    "breakeven_10y": (2.32, 0.03),
    "gdp_growth": (2.4, 0.6),
    "industrial_production": (102.5, 0.4),
    "cpi": (3.3, 0.15),
    "pce": (2.8, 0.12),
    "m2": (21000.0, 60.0),
    "unemployment": (4.0, 0.08),
    "initial_claims": (220000.0, 9000.0),
    "sahm": (0.20, 0.05),
    "hy_oas": (3.6, 0.20),
    "ig_oas": (1.05, 0.06),
    "umich_sentiment": (69.0, 2.0),
    "policy_uncertainty": (135.0, 25.0),
    "mortgage_30y": (6.7, 0.08),
    "recession_prob": (0.5, 0.15),
    "gdp_growth": (2.2, 0.4),
}


def fred_series(key: str, days: int = 1820) -> pd.Series:
    # ~7 years of business days so NBER recession shading (e.g. 2020) is in-window.
    level, vol = _FRED_PRESETS.get(key, (100.0, 1.0))
    rng = _seed("fred_" + key)
    noise = rng.normal(0, vol, days).cumsum() * 0.15
    base = np.linspace(level * 0.97, level, days)
    return pd.Series(base + noise, index=_daily_index(days), name=key)


def fred_latest(key: str) -> float:
    return float(fred_series(key).iloc[-1])


# ---------------------------------------------------------------------------
# Markets
# ---------------------------------------------------------------------------
_PRICE_PRESETS = {
    "^GSPC": (5200, 0.008, 0.0004),
    "^DJI": (39000, 0.007, 0.0003),
    "^IXIC": (16400, 0.011, 0.0005),
    "^VIX": (14.5, 0.05, -0.0002),
    "SPY": (520, 0.008, 0.0004),
    "RSP": (165, 0.007, 0.0002),
    "DX-Y.NYB": (104, 0.004, 0.0),
    "GC=F": (2350, 0.009, 0.0003),
    "CL=F": (78, 0.018, 0.0),
    "HG=F": (4.5, 0.013, 0.0001),
    "BTC-USD": (66000, 0.03, 0.0006),
}


def price_history(ticker: str, days: int = 400) -> pd.DataFrame:
    start, vol, drift = _PRICE_PRESETS.get(ticker, (100, 0.01, 0.0))
    close = _random_walk(ticker, start, days, vol, drift)
    return pd.DataFrame({"Close": close})


def quote(ticker: str) -> dict:
    hist = price_history(ticker, days=5)["Close"]
    price = float(hist.iloc[-1])
    change_pct = float((hist.iloc[-1] / hist.iloc[-2] - 1) * 100)
    return {"price": price, "change_pct": change_pct}


def sector_performance() -> pd.DataFrame:
    """Per-sector returns over standard lookbacks (%)."""
    from config import SECTORS

    rng = _seed("sectors")
    rows = []
    for etf, label in SECTORS.items():
        rows.append({
            "etf": etf,
            "sector": label,
            "1W": float(rng.normal(0.3, 1.5)),
            "1M": float(rng.normal(1.2, 3.5)),
            "3M": float(rng.normal(3.0, 6.0)),
            "YTD": float(rng.normal(8.0, 9.0)),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------
def fear_greed() -> dict:
    rng = _seed("feargreed")
    hist = pd.Series(
        np.clip(55 + rng.normal(0, 12, 180).cumsum() * 0.1, 5, 95),
        index=_daily_index(180),
        name="fear_greed",
    )
    score = float(hist.iloc[-1])
    return {"score": score, "rating": rating_for(score), "history": hist}


def rating_for(score: float) -> str:
    if score < 25:
        return "Extreme Fear"
    if score < 45:
        return "Fear"
    if score < 55:
        return "Neutral"
    if score < 75:
        return "Greed"
    return "Extreme Greed"


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------
def economic_calendar() -> pd.DataFrame:
    """Illustrative upcoming US releases (used when no live calendar is available)."""
    today = pd.Timestamp("2026-06-08")
    rows = [
        (today + pd.Timedelta(days=2), "CPI (MoM)", "High", "0.2%", "0.3%"),
        (today + pd.Timedelta(days=3), "Initial Jobless Claims", "Medium", "220K", "225K"),
        (today + pd.Timedelta(days=6), "Retail Sales (MoM)", "High", "0.3%", "0.1%"),
        (today + pd.Timedelta(days=7), "FOMC Rate Decision", "High", "3.50%", "3.50%"),
        (today + pd.Timedelta(days=9), "U. of Mich. Sentiment", "Medium", "50.5", "49.8"),
    ]
    return pd.DataFrame(rows, columns=["date", "event", "impact", "estimate", "previous"])


def valuation() -> dict:
    return {
        "cape": 34.5,
        "cape_pct": 92.0,         # historical percentile
        "buffett": 192.0,         # total market cap / GDP, %
        "buffett_pct": 95.0,
        "pe_ttm": 27.8,
        "forward_pe": 21.5,
        "dividend_yield": 1.30,
        "earnings_yield": 3.60,
        "erp": -0.80,             # earnings yield - 10Y, %
    }
