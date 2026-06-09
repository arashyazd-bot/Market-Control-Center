"""CoinGecko adapter — free, no-key crypto prices/history. Failover for Bitcoin
(and any future crypto) when FMP is unavailable."""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

import config
from data import DataResult

_BASE = "https://api.coingecko.com/api/v3"


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def get_quote(coin_id: str = "bitcoin", vs: str = "usd") -> DataResult:
    try:
        r = requests.get(f"{_BASE}/simple/price",
                         params={"ids": coin_id, "vs_currencies": vs,
                                 "include_24hr_change": "true"}, timeout=8)
        r.raise_for_status()
        d = r.json()[coin_id]
        return DataResult({"price": float(d[vs]),
                           "change_pct": float(d.get(f"{vs}_24h_change", 0.0))},
                          is_sample=False, source="CoinGecko")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="CoinGecko", note=f"CoinGecko:{exc}"[:80])


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def get_history(coin_id: str = "bitcoin", days: int = 400, vs: str = "usd") -> DataResult:
    try:
        r = requests.get(f"{_BASE}/coins/{coin_id}/market_chart",
                         params={"vs_currency": vs, "days": days, "interval": "daily"},
                         timeout=10)
        r.raise_for_status()
        prices = r.json()["prices"]
        idx = pd.to_datetime([p[0] for p in prices], unit="ms")
        s = pd.Series([p[1] for p in prices], index=idx, name="Close")
        s = s[~s.index.duplicated(keep="last")]
        if s.empty:
            raise ValueError("empty")
        return DataResult(s, is_sample=False, source="CoinGecko")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="CoinGecko", note=f"CoinGecko:{exc}"[:80])
