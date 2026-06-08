"""Valuation metrics: Shiller CAPE, the Buffett Indicator (total market cap / GDP),
trailing/forward P/E, and the equity risk premium. CAPE/P/E are scraped from
multpl.com when reachable; the Buffett Indicator is derived from FRED. Everything
falls back to bundled sample values."""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

import config
from data import DataResult
from data import fred
from data import sample


def _multpl(path: str) -> float:
    """Scrape the current value from a multpl.com table page."""
    url = f"https://www.multpl.com/{path}"
    resp = requests.get(url, headers=config.BROWSER_HEADERS, timeout=10)
    resp.raise_for_status()
    tables = pd.read_html(resp.text)
    # First data row of the main table holds the current value.
    val = tables[0].iloc[0, 1]
    return float(str(val).split()[0].replace(",", ""))


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_valuation() -> DataResult:
    sample_vals = sample.valuation()
    out = dict(sample_vals)
    is_sample = False
    notes = []

    # Buffett Indicator from FRED (Wilshire 5000 price index vs nominal GDP).
    wil = fred.get_series("wilshire")
    gdp = fred.get_series("gdp_nominal")
    if not (wil.is_sample or gdp.is_sample):
        try:
            # Wilshire full-cap price index ~ market cap in $B at the standard scaling.
            mcap = float(wil.data.iloc[-1])
            gdp_b = float(gdp.data.iloc[-1])  # GDP in $B (annualized)
            out["buffett"] = round(mcap / gdp_b * 100, 1)
        except Exception as exc:
            notes.append(f"buffett:{exc}")
            is_sample = True
    else:
        is_sample = True

    # CAPE + trailing P/E from multpl (best-effort).
    try:
        out["cape"] = _multpl("shiller-pe/")
        out["pe_ttm"] = _multpl("s-p-500-pe-ratio/")
        out["earnings_yield"] = round(100.0 / out["pe_ttm"], 2)
    except Exception as exc:
        notes.append(f"multpl:{exc}")
        is_sample = True

    # Equity risk premium = earnings yield - 10Y nominal yield.
    curve = fred.get_yield_curve()
    try:
        y10 = float(curve.data.get(10)) if hasattr(curve.data, "get") else float("nan")
        if y10 == y10:  # not NaN
            out["erp"] = round(out["earnings_yield"] - y10, 2)
    except Exception:
        pass

    return DataResult(out, is_sample=is_sample, note="; ".join(notes)[:120])
