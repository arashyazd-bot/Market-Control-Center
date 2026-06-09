"""Business-cycle phase engine — deterministic rules over FRED macro signals
(yield-curve slope, high-yield credit spreads, recession probability, the Sahm
rule, and the unemployment trend) that place the economy on an Early → Mid →
Late → Recession arc. Transparent (every input is surfaced in `rationale`) and
zero-cost: no model calls, just thresholds. Core to the dashboard's value prop —
'where are we in the cycle.'"""
from __future__ import annotations

from data import DataResult, macro


def _safe(fn, default=float("nan")) -> float:
    try:
        v = float(fn())
        return v if v == v else default
    except Exception:
        return default


def compute_cycle() -> DataResult:
    curve = macro.yield_curve()
    hy = macro.series("hy_oas")
    unemp = macro.series("unemployment")

    slope = _safe(lambda: float(curve.data.get(10)) - float(curve.data.get(2)))
    hy_latest = _safe(lambda: macro.latest(hy))
    recprob = _safe(lambda: macro.latest(macro.series("recession_prob")))
    sahm = _safe(lambda: macro.latest(macro.series("sahm")))

    # Unemployment: how far above its recent (~18mo) cycle low?
    try:
        u = unemp.data
        u_latest = float(u.iloc[-1])
        u_min = float(u.iloc[-360:].min())
        u_rising = u_latest - u_min
    except Exception:
        u_latest, u_rising = float("nan"), 0.0

    is_sample = curve.is_sample or hy.is_sample or unemp.is_sample

    pos, why = 50.0, []
    if slope == slope:
        if slope < 0:
            pos += 25; why.append(f"Yield curve inverted ({slope:+.2f}%) — classic late-cycle/recession signal")
        elif slope > 1.0:
            pos -= 25; why.append(f"Yield curve steep ({slope:+.2f}%) — early-cycle")
        else:
            why.append(f"Yield curve modestly positive ({slope:+.2f}%)")
    if hy_latest == hy_latest:
        if hy_latest > 5.0:
            pos += 15; why.append(f"High-yield credit spreads wide ({hy_latest:.1f}%) — stress building")
        elif hy_latest < 3.5:
            pos -= 10; why.append(f"Credit spreads tight ({hy_latest:.1f}%) — healthy risk appetite")
    if recprob == recprob and recprob > 0:
        pos += min(recprob * 0.5, 25)
        if recprob >= 25:
            why.append(f"Elevated recession probability ({recprob:.0f}%)")
    if u_rising == u_rising:
        if u_rising > 0.5:
            pos += 15; why.append(f"Unemployment rising {u_rising:+.1f}pp off its cycle low")
        elif u_rising < 0.2 and u_latest == u_latest and u_latest < 4.5:
            pos -= 5; why.append("Unemployment near cycle lows")

    sahm_triggered = sahm == sahm and sahm >= 0.5
    if sahm_triggered:
        pos = max(pos, 85.0); why.append(f"Sahm rule triggered ({sahm:.2f}) — recession indicator")

    pos = max(0.0, min(100.0, pos))
    if sahm_triggered or pos >= 80:
        phase, color = "Recession", "#C8102E"
    elif pos >= 55:
        phase, color = "Late cycle", "#C2410C"
    elif pos >= 30:
        phase, color = "Mid cycle", "#1D4ED8"
    else:
        phase, color = "Early cycle", "#1A7F37"

    return DataResult(
        {"phase": phase, "position": pos, "color": color, "slope": slope,
         "hy": hy_latest, "recprob": recprob, "sahm": sahm, "rationale": why},
        is_sample=is_sample, source="derived" if not is_sample else "sample")
