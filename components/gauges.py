"""Plotly gauge builders: the Fear & Greed dial and the composite regime light."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def _dark() -> bool:
    try:
        return bool(st.session_state.get("dark_mode", False))
    except Exception:
        return False


def _template() -> str:
    return "plotly_dark" if _dark() else "plotly"


def _font_color() -> str:
    return "#E2E8F0" if _dark() else "#0F172A"


def fear_greed_gauge(score: float, rating: str) -> go.Figure:
    fc = _font_color()
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"Fear & Greed<br><span style='font-size:0.85em'>{rating}</span>",
               "font": {"size": 16, "color": fc}},
        number={"font": {"size": 44, "color": fc}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1,
                     "tickfont": {"size": 13, "color": fc}},
            "bar": {"color": "rgba(128,128,128,0.6)", "thickness": 0.15},
            "steps": [
                {"range": [0, 25],   "color": "#DC2626"},
                {"range": [25, 45],  "color": "#EA580C"},
                {"range": [45, 55],  "color": "#CA8A04"},
                {"range": [55, 75],  "color": "#0891B2"},
                {"range": [75, 100], "color": "#047857"},
            ],
        },
    ))
    fig.update_layout(
        height=270,
        margin=dict(l=20, r=20, t=65, b=10),
        template=_template(),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=fc),
    )
    return fig


def regime_gauge(score: float, label: str, color: str) -> go.Figure:
    fc = _font_color()
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"Market Regime<br>"
                       f"<span style='font-size:1.1em;color:{color}'><b>{label}</b></span>",
               "font": {"size": 16, "color": fc}},
        number={"valueformat": ".2f", "font": {"size": 42, "color": color}},
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
    fig.update_layout(
        height=310,
        margin=dict(l=20, r=20, t=75, b=10),
        template=_template(),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=fc),
    )
    return fig
