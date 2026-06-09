"""Market data resolver. Routes quotes/histories through the health-aware router:
FMP (works on cloud) → yfinance (throttled on cloud) → Stooq (no-key, cloud-ok)
→ sample; Bitcoin also tries CoinGecko. Provenance is on each DataResult.source."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from data import DataResult, coingecko, fmp, router, sample, stooq

# our ticker -> FMP symbol (only what FMP's tier serves live)
_FMP_MAP = {
    "^GSPC": "^GSPC", "^DJI": "^DJI", "^IXIC": "^IXIC", "^VIX": "^VIX",
    "SPY": "SPY", "GC=F": "GCUSD", "BTC-USD": "BTCUSD",
}
# our ticker -> Stooq symbol (free, no-key, works from cloud IPs)
_STOOQ_MAP = {
    "^GSPC": "^spx", "^DJI": "^dji", "^IXIC": "^ndq", "^VIX": "^vix",
    "SPY": "spy.us", "RSP": "rsp.us", "GC=F": "gc.f", "CL=F": "cl.f",
    "HG=F": "hg.f", "DX-Y.NYB": "dx.f", "BTC-USD": "btcusd",
}
_PERIOD_DAYS = {"1mo": 35, "1y": 400, "2y": 760, "5y": 1850, "10y": 3800}


def _yf():
    try:
        import yfinance as yf
        return yf
    except Exception:
        return None


def _yf_history(ticker: str, period: str) -> DataResult:
    yf = _yf()
    if yf is None:
        return DataResult(None, is_sample=True, source="yfinance", note="yfinance missing")
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True, timeout=6)
        if df is None or df.empty or "Close" not in df:
            raise ValueError("no data")
        s = df["Close"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None)
        s.name = "Close"
        return DataResult(s, is_sample=False, source="yfinance")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="yfinance", note=f"yfinance:{exc}"[:80])


def _yf_quote(ticker: str) -> DataResult:
    r = _yf_history(ticker, "1mo")
    if r.is_sample or r.data is None or len(r.data) < 2:
        return DataResult(None, is_sample=True, source="yfinance", note=r.note or "no quote")
    s = r.data
    return DataResult({"price": float(s.iloc[-1]),
                       "change_pct": float((s.iloc[-1] / s.iloc[-2] - 1) * 100)},
                      is_sample=False, source="yfinance")


def _as_close_df(r: DataResult) -> DataResult:
    """Series-bearing result -> DataFrame{'Close'} (the panel API), or failure marker."""
    if r.is_sample or r.data is None or len(r.data) == 0:
        return DataResult(None, is_sample=True, source=r.source, note=r.note)
    return DataResult(pd.DataFrame({"Close": r.data}), is_sample=False, source=r.source)


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def price_history(ticker: str, period: str = "1y") -> DataResult:
    days = _PERIOD_DAYS.get(period, 400)
    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    cands = []
    if ticker in _FMP_MAP:
        cands.append(("FMP", lambda: _as_close_df(fmp.get_history(_FMP_MAP[ticker], start))))
    cands.append(("yfinance", lambda: _as_close_df(_yf_history(ticker, period))))
    if ticker in _STOOQ_MAP:
        cands.append(("Stooq", lambda: _as_close_df(stooq.get_history(_STOOQ_MAP[ticker], start))))
    if ticker == "BTC-USD":
        cands.append(("CoinGecko", lambda: _as_close_df(coingecko.get_history("bitcoin", days))))
    return router.chain(cands, sample_fn=lambda: sample.price_history(ticker, days))


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def quote(ticker: str) -> DataResult:
    cands = []
    if ticker in _FMP_MAP:
        cands.append(("FMP", lambda: fmp.get_quote(_FMP_MAP[ticker])))
    cands.append(("yfinance", lambda: _yf_quote(ticker)))
    if ticker in _STOOQ_MAP:
        cands.append(("Stooq", lambda: stooq.get_quote(_STOOQ_MAP[ticker])))
    if ticker == "BTC-USD":
        cands.append(("CoinGecko", lambda: coingecko.get_quote("bitcoin")))
    return router.chain(cands, sample_fn=lambda: sample.quote(ticker))


def _yf_sector_performance() -> DataResult:
    yf = _yf()
    if yf is None:
        return DataResult(None, is_sample=True, source="yfinance", note="yfinance missing")
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

            def ret(lookback, s=s):
                if len(s) <= lookback:
                    return float("nan")
                return float((s.iloc[-1] / s.iloc[-lookback] - 1) * 100)

            ytd = float((s.iloc[-1] / ytd_start[etf].dropna().iloc[0] - 1) * 100)
            rows.append({"etf": etf, "sector": config.SECTORS[etf],
                         "1W": ret(5), "1M": ret(21), "3M": ret(63), "YTD": ytd})
        if not rows:
            raise ValueError("no rows")
        return DataResult(pd.DataFrame(rows), is_sample=False, source="yfinance")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="yfinance", note=f"yfinance:{exc}"[:80])


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def sector_performance() -> DataResult:
    # NOTE: FMP is intentionally NOT chained here. The sector heatmap needs
    # 1W/1M/3M/YTD windows, but FMP's sector-performance-snapshot only returns a
    # single 1D average-change column — chaining it would feed the heatmap the
    # wrong shape. yfinance computes the multi-window returns; sample is fallback.
    return router.chain([("yfinance", _yf_sector_performance)],
                        sample_fn=sample.sector_performance)


def above_200dma(ticker: str = config.SPY) -> DataResult:
    """Trend signal: latest close vs its 200-day moving average (% above)."""
    res = price_history(ticker, period="2y")
    try:
        close = res.data["Close"]
        ma = close.rolling(200).mean()
        pct = float((close.iloc[-1] / ma.iloc[-1] - 1) * 100)
        return DataResult(pct, is_sample=res.is_sample, source=res.source, note=res.note)
    except Exception:
        return DataResult(float("nan"), is_sample=True, source="sample", note="trend fallback")


def sector_ytd(ticker: str) -> DataResult:
    res = price_history(ticker, period="1y")
    try:
        s = res.data["Close"].dropna()
        ytd_start = s[s.index >= pd.Timestamp(s.index[-1].year, 1, 1)].iloc[0]
        return DataResult(float((s.iloc[-1] / ytd_start - 1) * 100),
                          is_sample=res.is_sample, source=res.source)
    except Exception:
        return DataResult(float("nan"), is_sample=True, source="sample")


def concentration_proxy() -> DataResult:
    """Equal-weight (RSP) vs cap-weight (SPY) YTD spread. Negative = narrow."""
    rsp = sector_ytd(config.EQUAL_WEIGHT_SPY)
    spy = sector_ytd(config.SPY)
    try:
        return DataResult(rsp.data - spy.data, is_sample=rsp.is_sample or spy.is_sample,
                          source=rsp.source if not rsp.is_sample else spy.source)
    except Exception:
        return DataResult(float("nan"), is_sample=True, source="sample")
