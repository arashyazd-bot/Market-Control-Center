"""Plotly gauge builders: the Fear & Greed dial and the composite regime light."""
from __future__ import annotations

import plotly.graph_objects as go


def fear_greed_gauge(score: float, rating: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"Fear & Greed<br><span style='font-size:0.8em'>{rating}</span>"},
        number={"font": {"size": 40}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "rgba(255,255,255,0.85)", "thickness": 0.15},
            "steps": [
                {"range": [0, 25], "color": "#e63946"},
                {"range": [25, 45], "color": "#f4a261"},
                {"range": [45, 55], "color": "#e9c46a"},
                {"range": [55, 75], "color": "#a8dadc"},
                {"range": [75, 100], "color": "#2a9d8f"},
            ],
        },
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=60, b=10))
    return fig


def regime_gauge(score: float, label: str, color: str) -> go.Figure:
    """Headline -1..+1 regime gauge (Risk-Off / Neutral / Risk-On)."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"Market Regime<br><span style='font-size:1.1em;color:{color}'>"
                       f"<b>{label}</b></span>"},
        number={"valueformat": "+.2f", "font": {"size": 38, "color": color}},
        gauge={
            "axis": {"range": [-1, 1], "tickvals": [-1, -0.33, 0.33, 1]},
            "bar": {"color": color, "thickness": 0.25},
            "steps": [
                {"range": [-1, -0.33], "color": "rgba(230,57,70,0.35)"},
                {"range": [-0.33, 0.33], "color": "rgba(244,162,97,0.35)"},
                {"range": [0.33, 1], "color": "rgba(42,157,143,0.35)"},
            ],
            "threshold": {"line": {"color": "white", "width": 3}, "value": score},
        },
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=70, b=10))
    return fig
