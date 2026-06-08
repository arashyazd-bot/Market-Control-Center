"""FRED data access. Falls back to bundled sample data when the ``fredapi``
package or a ``FRED_API_KEY`` is unavailable, or when a request fails."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

import config
from data import DataResult
from data import sample


def _api_key() -> str | None:
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key
    try:  # st.secrets raises if no secrets file exists
        return st.secrets.get("FRED_API_KEY")
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def _client():
    """Build a cached Fred client, or None if unavailable."""
    key = _api_key()
    if not key:
        return None
    try:
        from fredapi import Fred

        return Fred(api_key=key)
    except Exception:
        return None


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_series(key: str, observation_start: str = "2018-01-01") -> DataResult:
    """Fetch a FRED series by its logical key (see config.FRED_SERIES)."""
    series_id = config.FRED_SERIES.get(key, key)
    client = _client()
    if client is None:
        return DataResult(sample.fred_series(key), is_sample=True, note="no FRED key")
    try:
        raw = client.get_series(series_id, observation_start=observation_start)
        s = pd.Series(raw).dropna()
        if s.empty:
            raise ValueError("empty series")
        s.name = key
        return DataResult(s, is_sample=False)
    except Exception as exc:  # network / bad id / rate limit
        return DataResult(sample.fred_series(key), is_sample=True, note=str(exc)[:80])


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_yield_curve() -> DataResult:
    """Latest yield for each constant maturity -> Series indexed by years."""
    client = _client()
    if client is None:
        return DataResult(sample.yield_curve(), is_sample=True, note="no FRED key")
    try:
        values = {}
        for years, series_id in config.YIELD_CURVE.items():
            s = pd.Series(client.get_series(series_id)).dropna()
            if not s.empty:
                values[years] = float(s.iloc[-1])
        if not values:
            raise ValueError("no curve data")
        return DataResult(pd.Series(values, name="yield_curve"), is_sample=False)
    except Exception as exc:
        return DataResult(sample.yield_curve(), is_sample=True, note=str(exc)[:80])


def latest(result: DataResult) -> float:
    """Last value of a series-bearing DataResult."""
    try:
        return float(result.data.iloc[-1])
    except Exception:
        return float("nan")


def yoy_change(result: DataResult) -> float:
    """Approximate year-over-year % change of a series (used for CPI levels etc.)."""
    s = result.data
    try:
        if len(s) < 13:
            return float("nan")
        # monthly data -> 12 periods; daily -> ~252; pick by frequency guess
        periods = 12 if len(s) < 400 else 252
        return float((s.iloc[-1] / s.iloc[-periods] - 1) * 100)
    except Exception:
        return float("nan")
