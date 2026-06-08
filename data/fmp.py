"""Financial Modeling Prep (FMP) REST client — an optional live data source.

Enabled when ``FMP_API_KEY`` is set. Mirrors the data this project's FMP MCP
tools return (treasury rates, economic indicators, sector performance, economic
calendar). Every fetch returns a ``DataResult`` and falls back to bundled sample
data on any failure or when the key is missing.
"""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

import config
from data import DataResult
from data import sample

# FMP treasury maturity field -> maturity in years (matches config.YIELD_CURVE keys)
_TREASURY_FIELDS = {
    "month3": 0.25, "month6": 0.5, "year1": 1, "year2": 2, "year5": 5,
    "year7": 7, "year10": 10, "year20": 20, "year30": 30,
}


def _key() -> str | None:
    key = os.environ.get("FMP_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("FMP_API_KEY")
    except Exception:
        return None


def available() -> bool:
    return bool(_key())


def _get(path: str, **params) -> list:
    params["apikey"] = _key()
    resp = requests.get(f"{config.FMP_BASE_URL}/{path}", params=params, timeout=8)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("Error Message"):
        raise ValueError(data["Error Message"])
    if not isinstance(data, list) or not data:
        raise ValueError("empty FMP response")
    return data


def _indicator_series(name: str, start: str = "2018-01-01") -> pd.Series:
    rows = _get("economic-indicators", name=name,
                **{"from": start, "to": pd.Timestamp.today().strftime("%Y-%m-%d")})
    s = pd.Series({pd.Timestamp(r["date"]): r["value"] for r in rows}).sort_index()
    s.name = name
    return s


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_indicator(key: str) -> DataResult:
    """Generic economic indicator by logical key (see config.FMP_INDICATORS)."""
    if not available():
        return DataResult(sample.fred_series(key), is_sample=True, note="no FMP key")
    try:
        return DataResult(_indicator_series(config.FMP_INDICATORS[key]), is_sample=False)
    except Exception as exc:
        return DataResult(sample.fred_series(key), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_yield_curve() -> DataResult:
    if not available():
        return DataResult(sample.yield_curve(), is_sample=True, note="no FMP key")
    try:
        rows = _get("treasury-rates")
        latest = rows[0]
        curve = {yrs: latest[fld] for fld, yrs in _TREASURY_FIELDS.items()
                 if latest.get(fld) is not None}
        return DataResult(pd.Series(curve, name="yield_curve").sort_index(), is_sample=False)
    except Exception as exc:
        return DataResult(sample.yield_curve(), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_spread_history(start: str = "2019-06-01") -> DataResult:
    """DataFrame of 10Y-2Y and 10Y-3M spreads derived from treasury history."""
    if not available():
        raise_sample = pd.DataFrame()
        return DataResult(raise_sample, is_sample=True, note="no FMP key")
    try:
        rows = _get("treasury-rates",
                    **{"from": start, "to": pd.Timestamp.today().strftime("%Y-%m-%d")})
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        out = pd.DataFrame({
            "s10y2y": df["year10"] - df["year2"],
            "s10y3m": df["year10"] - df["month3"],
        }).dropna()
        return DataResult(out, is_sample=False)
    except Exception as exc:
        return DataResult(pd.DataFrame(), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_gdp_growth() -> DataResult:
    """Real GDP growth, annualized quarter-over-quarter % (SAAR), as a series."""
    if not available():
        return DataResult(sample.fred_series("gdp_growth"), is_sample=True, note="no FMP key")
    try:
        level = _indicator_series(config.FMP_REAL_GDP)
        growth = ((level / level.shift(1)) ** 4 - 1) * 100
        growth = growth.dropna()
        growth.name = "gdp_growth"
        return DataResult(growth, is_sample=False)
    except Exception as exc:
        return DataResult(sample.fred_series("gdp_growth"), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def get_sector_performance() -> DataResult:
    """Latest single-day average % change by sector (FMP snapshot)."""
    if not available():
        return DataResult(sample.sector_performance(), is_sample=True, note="no FMP key")
    try:
        # Walk back a few days to skip weekends/holidays with no snapshot.
        for back in range(0, 6):
            day = (pd.Timestamp.today() - pd.Timedelta(days=back)).strftime("%Y-%m-%d")
            try:
                rows = _get("sector-performance-snapshot", date=day)
            except Exception:
                continue
            df = pd.DataFrame(rows).rename(columns={"averageChange": "1D"})
            return DataResult(df[["sector", "1D"]], is_sample=False, meta={"date": day})
        raise ValueError("no recent snapshot")
    except Exception as exc:
        return DataResult(sample.sector_performance(), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def get_sector_pe() -> DataResult:
    """Latest trailing P/E by sector (FMP snapshot)."""
    if not available():
        return DataResult(sample.sector_pe(), is_sample=True, note="no FMP key")
    try:
        for back in range(0, 6):
            day = (pd.Timestamp.today() - pd.Timedelta(days=back)).strftime("%Y-%m-%d")
            try:
                rows = _get("sector-pe-snapshot", date=day)
            except Exception:
                continue
            df = pd.DataFrame(rows)[["sector", "pe"]]
            return DataResult(df, is_sample=False, meta={"date": day})
        raise ValueError("no recent snapshot")
    except Exception as exc:
        return DataResult(sample.sector_pe(), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MARKETS, show_spinner=False)
def get_movers(direction: str = "gainers", top: int = 10) -> DataResult:
    """Biggest gainers/losers, with leveraged/inverse ETFs filtered out."""
    if not available():
        return DataResult(sample.market_movers(direction), is_sample=True, note="no FMP key")
    try:
        rows = _get(f"biggest-{direction}")
        df = pd.DataFrame(rows)
        mask = ~df["name"].str.contains("|".join(config.MOVER_EXCLUDE), case=False, na=False)
        df = df[mask & (df["price"] >= 1.0)]
        df = df[["symbol", "name", "price", "changesPercentage"]].head(top)
        return DataResult(df.reset_index(drop=True), is_sample=False)
    except Exception as exc:
        return DataResult(sample.market_movers(direction), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_analyst_consensus(symbol: str) -> DataResult:
    """Combined price-target consensus + analyst grade distribution for a symbol."""
    if not available():
        return DataResult(sample.analyst_consensus(symbol), is_sample=True, note="no FMP key")
    try:
        pt = _get("price-target-consensus", symbol=symbol)[0]
        gr = _get("grades-consensus", symbol=symbol)[0]
        out = {
            "symbol": symbol,
            "consensus": gr.get("consensus", "—"),
            "buy": gr.get("strongBuy", 0) + gr.get("buy", 0),
            "hold": gr.get("hold", 0),
            "sell": gr.get("sell", 0) + gr.get("strongSell", 0),
            "target_low": pt.get("targetLow"),
            "target_consensus": pt.get("targetConsensus"),
            "target_high": pt.get("targetHigh"),
        }
        return DataResult(out, is_sample=False)
    except Exception as exc:
        return DataResult(sample.analyst_consensus(symbol), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_SENTIMENT, show_spinner=False)
def get_congressional_trades(top: int = 15) -> DataResult:
    """Latest US Senate trading disclosures (requires an FMP Starter+ tier)."""
    if not available():
        return DataResult(sample.congressional_trades(), is_sample=True, note="no FMP key")
    try:
        rows = _get("senate-latest")
        df = pd.DataFrame(rows)
        rename = {"dateRecieved": "date", "transactionDate": "date", "office": "senator",
                  "firstName": "first", "lastName": "last"}
        df = df.rename(columns={k: v for k, v in rename.items() if k in df})
        cols = [c for c in ["date", "symbol", "senator", "type", "amount"] if c in df]
        return DataResult(df[cols].head(top) if cols else df.head(top), is_sample=False)
    except Exception as exc:
        return DataResult(sample.congressional_trades(), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_SENTIMENT, show_spinner=False)
def get_economic_calendar(days: int = 10) -> DataResult:
    """Upcoming high-impact US economic releases (next ``days`` days)."""
    if not available():
        return DataResult(sample.economic_calendar(), is_sample=True, note="no FMP key")
    try:
        today = pd.Timestamp.today()
        rows = _get("economic-calendar",
                    **{"from": today.strftime("%Y-%m-%d"),
                       "to": (today + pd.Timedelta(days=days)).strftime("%Y-%m-%d")})
        df = pd.DataFrame(rows)
        if "country" in df:
            df = df[df["country"] == "US"]
        if "impact" in df:
            df = df[df["impact"].isin(["High", "Medium"])]
        cols = [c for c in ["date", "event", "impact", "estimate", "previous"] if c in df]
        return DataResult(df[cols].head(15).reset_index(drop=True), is_sample=False)
    except Exception as exc:
        return DataResult(sample.economic_calendar(), is_sample=True, note=str(exc)[:80])
