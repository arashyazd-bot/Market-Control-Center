"""Stooq adapter — free, no-key daily EOD data (CSV). Works from cloud IPs where
yfinance is throttled, so it's the failover for indices, commodities, FX and ETFs.
Returns a failure marker (is_sample=True, data=None) so the router can move on."""
from __future__ import annotations

import io

import pandas as pd
import requests
import streamlit as st

import config
from data import DataResult

_BASE = "https://stooq.com/q/d/l/"


def _csv(symbol: str, start: str | None = None) -> pd.DataFrame:
    params = {"s": symbol, "i": "d"}
    if start:
        params["d1"] = start.replace("-", "")
        params["d2"] = pd.Timestamp.today().strftime("%Y%m%d")
    r = requests.get(_BASE, params=params, timeout=8)
    r.raise_for_status()
    head = r.text.lstrip()[:4].lower()
    if not head.startswith("date"):          # stooq returns "No data" as plain text
        raise ValueError("no data")
    df = pd.read_csv(io.StringIO(r.text))
    if df.empty or "Close" not in df:
        raise ValueError("empty")
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date").sort_index()


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def get_quote(symbol: str) -> DataResult:
    try:
        close = _csv(symbol)["Close"].dropna()
        price = float(close.iloc[-1])
        chg = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
        return DataResult({"price": price, "change_pct": chg}, is_sample=False, source="Stooq")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="Stooq", note=f"Stooq:{exc}"[:80])


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def get_history(symbol: str, start: str) -> DataResult:
    try:
        s = _csv(symbol, start)["Close"].dropna()
        if s.empty:
            raise ValueError("empty")
        s.name = "Close"
        return DataResult(s, is_sample=False, source="Stooq")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="Stooq", note=f"Stooq:{exc}"[:80])
