"""Macro/rates resolver. Every series routes through the health-aware source
router with **FRED-first** priority — FRED is effectively unlimited, so it carries
the macro load and the scarce FMP free-tier quota is reserved for market/stock
data FRED can't serve. Order per item: FRED → (Treasury / FMP) → sample.

Panels stay declarative; provenance is on each DataResult's .source.
"""
from __future__ import annotations

import config
from data import DataResult, fmp, fred, router, sample, treasury


def active_source() -> str:
    """Coarse label for the caption; real provenance is per-DataResult.source."""
    if fred._api_key():
        return "FRED-first" + (" (FMP backup)" if fmp.available() else "")
    if fmp.available():
        return "FMP"
    return "sample"


def yield_curve() -> DataResult:
    return router.chain(
        [("FRED", fred.get_yield_curve),
         ("Treasury", treasury.get_yield_curve),
         ("FMP", fmp.get_yield_curve)],
        sample_fn=sample.yield_curve)


def series(key: str) -> DataResult:
    cands = [("FRED", lambda k=key: fred.get_series(k))]
    if key in config.FMP_INDICATORS:
        cands.append(("FMP", lambda k=key: fmp.get_indicator(k)))
    return router.chain(cands, sample_fn=lambda k=key: sample.fred_series(k))


def spread_series(which: str) -> DataResult:
    fred_key = {"s10y2y": "spread_10y2y", "s10y3m": "spread_10y3m"}[which]

    def _fmp() -> DataResult:
        hist = fmp.get_spread_history()
        if not hist.is_sample and hasattr(hist.data, "__contains__") and which in hist.data:
            return DataResult(hist.data[which], is_sample=False, source="FMP")
        return DataResult(None, is_sample=True, source="FMP", note=hist.note or "no spread")

    return router.chain(
        [("FRED", lambda: fred.get_series(fred_key)), ("FMP", _fmp)],
        sample_fn=lambda: sample.fred_series(fred_key))


def gdp_growth() -> DataResult:
    return router.chain(
        [("FRED", lambda: fred.get_series("gdp_growth")), ("FMP", fmp.get_gdp_growth)],
        sample_fn=lambda: sample.fred_series("gdp_growth"))


def latest(result: DataResult) -> float:
    return fred.latest(result)


def yoy_change(result: DataResult) -> float:
    return fred.yoy_change(result)
