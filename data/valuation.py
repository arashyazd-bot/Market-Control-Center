"""Valuation metrics: Shiller CAPE, the Buffett Indicator (total market cap / GDP),
trailing P/E, dividend yield, and the equity risk premium. CAPE/P/E/dividend are
scraped from multpl.com when reachable; the Buffett Indicator is derived from FRED.
Unsourced fields (e.g. forward P/E — no free source) are left NaN and render as
"—" rather than fabricated. Percentile *context* is illustrative."""
from __future__ import annotations

import re

import requests
import streamlit as st

import config
from data import DataResult
from data import fred
from data import sample


def _multpl(path: str) -> float:
    """Current value from a multpl.com page. The page's main table is the
    Mean/Median/Min stats (NOT the current value) — the live figure is in the
    'Current ... is XX.XX' sentence, so parse that."""
    url = f"https://www.multpl.com/{path}"
    resp = requests.get(url, headers=config.BROWSER_HEADERS, timeout=10)
    resp.raise_for_status()
    text = resp.text
    # multpl states e.g. "Current Shiller PE Ratio is 41.67, a change of +0.10".
    m = re.search(r"\bis\s+\$?([0-9]+(?:\.[0-9]+)?)\s*%?,?\s*a change", text)
    if not m:  # fallback: "Current ... is XX.XX" (avoid CSS braces/semicolons)
        m = re.search(r"[Cc]urrent\b[^.<>{};]{0,80}?\bis\b\s*\$?([0-9]+(?:\.[0-9]+)?)", text)
    if not m:
        raise ValueError("multpl: current value not found")
    return float(m.group(1))


@st.cache_data(ttl=config.TTL_MACRO, show_spinner=False)
def get_valuation() -> DataResult:
    nan = float("nan")
    out = {"cape": nan, "cape_pct": nan, "buffett": nan, "buffett_pct": nan,
           "pe_ttm": nan, "forward_pe": nan, "dividend_yield": nan,
           "earnings_yield": nan, "erp": nan}
    notes, sources = [], set()

    # Buffett Indicator from FRED (Wilshire 5000 price index vs nominal GDP).
    wil = fred.get_series("wilshire")
    gdp = fred.get_series("gdp_nominal")
    if not (wil.is_sample or gdp.is_sample):
        try:
            out["buffett"] = round(float(wil.data.iloc[-1]) / float(gdp.data.iloc[-1]) * 100, 1)
            sources.add("FRED")
        except Exception as exc:
            notes.append(f"buffett:{exc}")

    # CAPE + trailing P/E from multpl (best-effort scrape).
    try:
        out["cape"] = _multpl("shiller-pe/")
        out["pe_ttm"] = _multpl("s-p-500-pe-ratio/")
        out["earnings_yield"] = round(100.0 / out["pe_ttm"], 2)
        sources.add("multpl")
    except Exception as exc:
        notes.append(f"multpl:{exc}")
    try:
        out["dividend_yield"] = _multpl("s-p-500-dividend-yield/")
        sources.add("multpl")
    except Exception as exc:
        notes.append(f"div:{exc}")

    # Equity risk premium = earnings yield - 10Y nominal yield.
    curve = fred.get_yield_curve()
    try:
        y10 = float(curve.data.get(10)) if hasattr(curve.data, "get") else nan
        if y10 == y10 and out["earnings_yield"] == out["earnings_yield"]:
            out["erp"] = round(out["earnings_yield"] - y10, 2)
            sources.add("FRED")
    except Exception:
        pass

    # Illustrative historical percentile context (no free live source).
    sv = sample.valuation()
    out["cape_pct"], out["buffett_pct"] = sv["cape_pct"], sv["buffett_pct"]

    is_sample = not sources                 # sample only if NOTHING came back live
    src = "+".join(sorted(sources)) if sources else "sample"
    return DataResult(out, is_sample=is_sample, source=src, note="; ".join(notes)[:120])
