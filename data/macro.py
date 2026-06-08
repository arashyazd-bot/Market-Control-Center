"""Macro/rates resolver. Presents one interface to panels and the composite
signal, choosing the best available source per series:

    FMP (if FMP_API_KEY set)  ->  FRED (if FRED_API_KEY set)  ->  sample

Keys FMP doesn't carry (credit spreads, Sahm rule, policy uncertainty) skip
straight to FRED. This keeps panels declarative — they never branch on source.
"""
from __future__ import annotations

import config
from data import DataResult, fmp, fred


def active_source() -> str:
    if fmp.available():
        return "FMP"
    if fred._api_key():
        return "FRED"
    return "sample"


def yield_curve() -> DataResult:
    if fmp.available():
        r = fmp.get_yield_curve()
        if not r.is_sample:
            return r
    return fred.get_yield_curve()


def series(key: str) -> DataResult:
    """Generic time series by logical key, FMP-first where supported."""
    if fmp.available() and key in config.FMP_INDICATORS:
        r = fmp.get_indicator(key)
        if not r.is_sample:
            return r
    return fred.get_series(key)


def gdp_growth() -> DataResult:
    if fmp.available():
        r = fmp.get_gdp_growth()
        if not r.is_sample:
            return r
    return fred.get_series("gdp_growth")


def spread_series(which: str) -> DataResult:
    """Time series for 's10y2y' or 's10y3m'. From FMP treasury history when
    available, else the matching FRED spread series."""
    if fmp.available():
        hist = fmp.get_spread_history()
        if not hist.is_sample and which in hist.data:
            return DataResult(hist.data[which], is_sample=False)
    fred_key = {"s10y2y": "spread_10y2y", "s10y3m": "spread_10y3m"}[which]
    return fred.get_series(fred_key)


def latest(result: DataResult) -> float:
    return fred.latest(result)


def yoy_change(result: DataResult) -> float:
    return fred.yoy_change(result)
