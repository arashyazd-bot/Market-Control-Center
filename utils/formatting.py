"""Small presentation helpers: number/percent formatting and color selection."""
from __future__ import annotations

import math


def fmt_num(value, decimals: int = 2, prefix: str = "", suffix: str = "") -> str:
    """Format a number with thousands separators; returns '—' for missing values."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{prefix}{value:,.{decimals}f}{suffix}"


def fmt_pct(value, decimals: int = 2) -> str:
    """Format a value already expressed in percent (e.g. 3.4 -> '3.40%')."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:+.{decimals}f}%"


def fmt_delta(value, decimals: int = 2, suffix: str = "%") -> str:
    """Signed delta for st.metric (e.g. +1.25%)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return f"{value:+.{decimals}f}{suffix}"


def color_for_change(value: float) -> str:
    """Green for positive, red for negative, grey for flat/unknown."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "#9aa0a6"
    if value > 0:
        return "#2a9d8f"
    if value < 0:
        return "#e63946"
    return "#9aa0a6"


def percentile_label(pct: float) -> str:
    """Human label for a 0-100 percentile (used for valuation context)."""
    if pct is None or math.isnan(pct):
        return "—"
    if pct >= 80:
        return "Very Expensive"
    if pct >= 60:
        return "Expensive"
    if pct >= 40:
        return "Fair"
    if pct >= 20:
        return "Cheap"
    return "Very Cheap"


def clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
