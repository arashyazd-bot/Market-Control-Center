"""Plotly gauge builders: the Fear & Greed dial and the composite regime light.

The dials are drawn title-less and share one geometry (_GAUGE_*) so they render
at identical size. Titles are rendered as aligned markdown above each dial in
panels.py — Plotly's own indicator-title auto-layout placed the two titles at
different heights and let the subtitle overlap the arc."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Shared geometry — keep the two dials the same size and vertically aligned.
_GAUGE_HEIGHT = 210
_GAUGE_MARGIN = dict(l=28, r=28, t=11, b=14)
_GAUGE_NUMBER_SIZE = 29
_GAUGE_FONT = "Figtree, system-ui, sans-serif"


def _dark() -> bool:
    try:
        return bool(st.session_state.get("dark_mode", False))
    except Exception:
        return False


def _template() -> str:
    return "plotly_dark" if _dark() else "plotly"


def _font_color() -> str:
    return "#E2E8F0" if _dark() else "#0F172A"


def _apply_layout(fig: go.Figure) -> None:
    fc = _font_color()
    fig.update_layout(
        height=_GAUGE_HEIGHT,
        margin=_GAUGE_MARGIN,
        template=_template(),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=fc, family=_GAUGE_FONT),
    )


def _add_extremes(fig: go.Figure, left_text: str, right_text: str, *,
                  color_left: str | None = None, color_right: str | None = None,
                  xl: float = 0.02, xr: float = 0.98, y: float = 0.30) -> None:
    """Label the two ends of a dial so the spectrum is self-explanatory — the
    left (low/red) extreme and the right (high/green) extreme. Colours default
    to a legible red/green for translucent bands; pass white for solid bands."""
    dark = _dark()
    cl = color_left or ("#F4564A" if dark else "#C8102E")
    cr = color_right or ("#3FB950" if dark else "#1A7F37")
    fig.add_annotation(x=xl, y=y, xref="paper", yref="paper",
                       text=left_text, showarrow=False,
                       xanchor="left", yanchor="middle",
                       font=dict(size=8, color=cl, family=_GAUGE_FONT))
    fig.add_annotation(x=xr, y=y, xref="paper", yref="paper",
                       text=right_text, showarrow=False,
                       xanchor="right", yanchor="middle",
                       font=dict(size=8, color=cr, family=_GAUGE_FONT))


def fear_greed_gauge(score: float) -> go.Figure:
    fc = _font_color()
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": _GAUGE_NUMBER_SIZE, "color": fc}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1,
                     "tickfont": {"size": 9, "color": fc}},
            "bar": {"color": "rgba(128,128,128,0.6)", "thickness": 0.25},
            "steps": [
                {"range": [0, 25],   "color": "#DC2626"},
                {"range": [25, 45],  "color": "#EA580C"},
                {"range": [45, 55],  "color": "#CA8A04"},
                {"range": [55, 75],  "color": "#0891B2"},
                {"range": [75, 100], "color": "#047857"},
            ],
        },
    ))
    # 0 = Extreme Fear (red zone), 100 = Extreme Greed (green zone). The bands
    # are solid, so use white text sitting on the coloured zones (no arrows —
    # white arrows would vanish where they fall on the background).
    _add_extremes(fig, "FEAR", "GREED", color_left="#FFFFFF",
                  color_right="#FFFFFF", xl=0.04, xr=0.96)
    _apply_layout(fig)
    return fig


def regime_gauge(score: float, color: str) -> go.Figure:
    fc = _font_color()
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"valueformat": ".2f", "font": {"size": _GAUGE_NUMBER_SIZE, "color": color}},
        gauge={
            "axis": {"range": [-1, 1], "tickvals": [-1, -0.33, 0.33, 1],
                     "tickfont": {"size": 9, "color": fc}},
            "bar": {"color": color, "thickness": 0.25},
            "steps": [
                {"range": [-1, -0.33],  "color": "rgba(220,38,38,0.3)"},
                {"range": [-0.33, 0.33],"color": "rgba(202,138,4,0.3)"},
                {"range": [0.33, 1],    "color": "rgba(4,120,87,0.3)"},
            ],
            "threshold": {"line": {"color": fc, "width": 3}, "value": score},
        },
    ))
    # −1 = maximum Risk-Off (red), +1 = maximum Risk-On (green), middle Neutral.
    _add_extremes(fig, "◀ RISK-OFF", "RISK-ON ▶")
    _apply_layout(fig)
    return fig
