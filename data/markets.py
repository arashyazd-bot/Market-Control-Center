"""Market data via yfinance, with sample fallback. Covers indices, the VIX,
sector ETFs, the equal-weight breadth proxy, and cross-asset instruments."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from data import DataResult
from data import fmp
from data import sample

# yfinance ticker -> FMP symbol, only for symbols FMP's tier actually serves.
# FMP works from cloud IPs (Render) where yfinance is throttled, so we prefer it
# for these and fall back to yfinance (live locally) then sample for the rest
# (sector ETFs, RSP, oil, copper, DXY, ^TNX are 402/premium on FMP).
_FMP_MAP = {
    "^GSPC": "^GSPC", "^DJI": "^DJI", "^IXIC": "^IXIC", "^VIX": "^VIX",
    "SPY": "SPY", "GC=F": "GCUSD", "BTC-USD": "BTCUSD",
}
_PERIOD_DAYS = {"1mo": 35, "1y": 400, "2y": 760, "5y": 1850, "10y": 3800}


def _yf():
    try:
        import yfinance as yf

        return yf
    except Exception:
        return None


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def price_history(ticker: str, period: str = "1y") -> DataResult:
    # Prefer FMP for supported symbols (works on Render); fall back to yfinance.
    if ticker in _FMP_MAP:
        days = _PERIOD_DAYS.get(period, 400)
        start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
        r = fmp.get_history(_FMP_MAP[ticker], start)
        if not r.is_sample and r.data is not None and len(r.data):
            return DataResult(pd.DataFrame({"Close": r.data}), is_sample=False)

    yf = _yf()
    if yf is None:
        return DataResult(sample.price_history(ticker), is_sample=True, note="yfinance missing")
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True, timeout=6)
        if df is None or df.empty or "Close" not in df:
            raise ValueError("no data")
        df = df[["Close"]].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return DataResult(df, is_sample=False)
    except Exception as exc:
        return DataResult(sample.price_history(ticker), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def quote(ticker: str) -> DataResult:
    """Latest price + 1-day % change."""
    # Prefer FMP's quote for supported symbols (live on Render).
    if ticker in _FMP_MAP:
        r = fmp.get_quote(_FMP_MAP[ticker])
        if not r.is_sample and r.data:
            return r

    res = price_history(ticker, period="1mo")
    df = res.data
    try:
        close = df["Close"]
        price = float(close.iloc[-1])
        change_pct = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
        return DataResult({"price": price, "change_pct": change_pct}, is_sample=res.is_sample,
                          note=res.note)
    except Exception:
        q = sample.quote(ticker)
        return DataResult(q, is_sample=True, note="quote fallback")


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def sector_performance() -> DataResult:
    """Trailing returns per sector ETF over 1W/1M/3M/YTD windows (%)."""
    yf = _yf()
    if yf is None:
        return DataResult(sample.sector_performance(), is_sample=True, note="yfinance missing")
    try:
        tickers = list(config.SECTORS.keys())
        data = yf.download(tickers, period="1y", auto_adjust=True, progress=False,
                           timeout=6)["Close"]
        if data is None or data.empty:
            raise ValueError("no data")
        data.index = pd.to_datetime(data.index).tz_localize(None)
        ytd_start = data[data.index >= pd.Timestamp(data.index[-1].year, 1, 1)]
        rows = []
        for etf in tickers:
            s = data[etf].dropna()
            if s.empty:
                continue
            def ret(lookback):
                if len(s) <= lookback:
                    return float("nan")
                return float((s.iloc[-1] / s.iloc[-lookback] - 1) * 100)
            ytd = float((s.iloc[-1] / ytd_start[etf].dropna().iloc[0] - 1) * 100)
            rows.append({
                "etf": etf, "sector": config.SECTORS[etf],
                "1W": ret(5), "1M": ret(21), "3M": ret(63), "YTD": ytd,
            })
        return DataResult(pd.DataFrame(rows), is_sample=False)
    except Exception as exc:
        return DataResult(sample.sector_performance(), is_sample=True, note=str(exc)[:80])


def above_200dma(ticker: str = config.SPY) -> DataResult:
    """Trend signal: latest close vs its 200-day moving average (% above)."""
    res = price_history(ticker, period="2y")
    try:
        close = res.data["Close"]
        ma = close.rolling(200).mean()
        pct = float((close.iloc[-1] / ma.iloc[-1] - 1) * 100)
        return DataResult(pct, is_sample=res.is_sample, note=res.note)
    except Exception:
        return DataResult(float("nan"), is_sample=True, note="trend fallback")


def concentration_proxy() -> DataResult:
    """Equal-weight (RSP) vs cap-weight (SPY) YTD spread. Negative = mega-cap
    driven / narrow market (concentration risk)."""
    rsp = sector_ytd(config.EQUAL_WEIGHT_SPY)
    spy = sector_ytd(config.SPY)
    try:
        return DataResult(rsp.data - spy.data, is_sample=rsp.is_sample or spy.is_sample)
    except Exception:
        return DataResult(float("nan"), is_sample=True)


def sector_ytd(ticker: str) -> DataResult:
    res = price_history(ticker, period="1y")
    try:
        s = res.data["Close"].dropna()
        ytd_start = s[s.index >= pd.Timestamp(s.index[-1].year, 1, 1)].iloc[0]
        return DataResult(float((s.iloc[-1] / ytd_start - 1) * 100), is_sample=res.is_sample)
    except Exception:
        return DataResult(float("nan"), is_sample=True)
