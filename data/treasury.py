"""U.S. Treasury (home.treasury.gov) daily par yield curve — free, no key.
Official failover for the yield curve when FRED is unavailable."""
from __future__ import annotations

import io

import pandas as pd
import requests
import streamlit as st

import config
from data import DataResult

_URL = ("https://home.treasury.gov/resource-center/data-chart-center/"
        "interest-rates/daily-treasury-rates.csv/{yr}/all")

# config.YIELD_CURVE maturities (years) -> Treasury CSV column header
_WANT = {0.25: "3 Mo", 0.5: "6 Mo", 1: "1 Yr", 2: "2 Yr", 5: "5 Yr",
         7: "7 Yr", 10: "10 Yr", 20: "20 Yr", 30: "30 Yr"}


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_yield_curve() -> DataResult:
    try:
        yr = pd.Timestamp.today().year
        r = requests.get(_URL.format(yr=yr),
                         params={"type": "daily_treasury_yield_curve",
                                 "field_tdr_date_value": yr}, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        if df.empty or "Date" not in df:
            raise ValueError("no data")
        latest = df.iloc[0]   # newest row first
        curve = {yrs: float(latest[col]) for yrs, col in _WANT.items()
                 if col in latest and pd.notna(latest[col])}
        if not curve:
            raise ValueError("empty")
        return DataResult(pd.Series(curve, name="yield_curve").sort_index(),
                          is_sample=False, source="Treasury")
    except Exception as exc:
        return DataResult(None, is_sample=True, source="Treasury", note=f"Treasury:{exc}"[:80])
