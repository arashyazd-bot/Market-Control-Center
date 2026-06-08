"""Plotly gauge builders: the Fear & Greed dial and the composite regime light.

Both dials share one geometry (_GAUGE_*) so they render at identical size and
align side-by-side in the Overview columns."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Shared geometry — keep the two dials the same size and vertically aligned.
_GAUGE_HEIGHT = 320
_GAUGE_MARGIN = dict(l=40, r=40, t=70, b=24)
_GAUGE_NUMBER_SIZE = 42
_GAUGE_TITLE_SIZE = 16
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


def fear_greed_gauge(score: float, rating: str) -> go.Figure:
    fc = _font_color()
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"Fear &amp; Greed<br>"
                       f"<span style='font-size:0.95em'>{rating}</span>",
               "font": {"size": _GAUGE_TITLE_SIZE, "color": fc}},
        number={"font": {"size": _GAUGE_NUMBER_SIZE, "color": fc}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1,
                     "tickfont": {"size": 13, "color": fc}},
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
    _apply_layout(fig)
    return fig


def regime_gauge(score: float, label: str, color: str) -> go.Figure:
    fc = _font_color()
    dark = _dark()
    red = "#F4564A" if dark else "#C8102E"
    green = "#3FB950" if dark else "#1A7F37"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"Market Regime<br>"
                       f"<span style='font-size:0.95em;color:{color}'><b>{label}</b></span>",
               "font": {"size": _GAUGE_TITLE_SIZE, "color": fc}},
        number={"valueformat": ".2f", "font": {"size": _GAUGE_NUMBER_SIZE, "color": color}},
        gauge={
            "axis": {"range": [-1, 1], "tickvals": [-1, -0.33, 0.33, 1],
                     "tickfont": {"size": 13, "color": fc}},
            "bar": {"color": color, "thickness": 0.25},
            "steps": [
                {"range": [-1, -0.33],  "color": "rgba(220,38,38,0.3)"},
                {"range": [-0.33, 0.33],"color": "rgba(202,138,4,0.3)"},
                {"range": [0.33, 1],    "color": "rgba(4,120,87,0.3)"},
            ],
            "threshold": {"line": {"color": fc, "width": 3}, "value": score},
        },
    ))
    # Spectrum extremes so the viewer knows what the score means: the −1 end is
    # maximum Risk-Off, the +1 end maximum Risk-On, the middle band Neutral.
    fig.add_annotation(x=0.02, y=0.30, xref="paper", yref="paper",
                       text="◀ RISK-OFF", showarrow=False,
                       xanchor="left", yanchor="middle",
                       font=dict(size=12, color=red, family=_GAUGE_FONT))
    fig.add_annotation(x=0.98, y=0.30, xref="paper", yref="paper",
                       text="RISK-ON ▶", showarrow=False,
                       xanchor="right", yanchor="middle",
                       font=dict(size=12, color=green, family=_GAUGE_FONT))
    _apply_layout(fig)
    return fig
