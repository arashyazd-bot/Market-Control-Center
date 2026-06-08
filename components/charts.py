"""Reusable Plotly chart builders shared across panels."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_LAYOUT = dict(
    template="plotly_dark",
    margin=dict(l=40, r=20, t=50, b=30),
    height=320,
    hovermode="x unified",
)


def line_chart(series: pd.Series, title: str, color: str = "#4cc9f0",
               y_suffix: str = "", fill: bool = False) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values, mode="lines", name=title,
        line=dict(color=color, width=2), fill="tozeroy" if fill else None,
    ))
    fig.update_layout(title=title, **_LAYOUT)
    fig.update_yaxes(ticksuffix=y_suffix)
    return fig


def spread_chart(series: pd.Series, title: str, y_suffix: str = "%") -> go.Figure:
    """Line with a zero reference line; shades inversion (below zero) in red."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values, mode="lines",
        line=dict(color="#4cc9f0", width=2), name=title,
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#e63946", opacity=0.7)
    fig.update_layout(title=title, **_LAYOUT)
    fig.update_yaxes(ticksuffix=y_suffix)
    return fig


def yield_curve_chart(curve: pd.Series) -> go.Figure:
    """Yield (%) vs maturity (years)."""
    s = curve.sort_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines+markers",
        line=dict(color="#4cc9f0", width=3), marker=dict(size=8),
    ))
    fig.update_layout(title="US Treasury Yield Curve", **_LAYOUT)
    fig.update_xaxes(title="Maturity (years)", type="log",
                     tickvals=list(s.index), ticktext=[str(x) for x in s.index])
    fig.update_yaxes(title="Yield", ticksuffix="%")
    return fig


def dual_axis_chart(left: pd.Series, right: pd.Series, left_name: str,
                    right_name: str, title: str) -> go.Figure:
    """Two series on independent y-axes (e.g. GDP growth vs index YoY)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=left.index, y=left.values, name=left_name,
                             line=dict(color="#f4a261", width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=right.index, y=right.values, name=right_name,
                             line=dict(color="#4cc9f0", width=2)), secondary_y=True)
    fig.update_layout(title=title, **_LAYOUT)
    fig.update_yaxes(title=left_name, secondary_y=False)
    fig.update_yaxes(title=right_name, secondary_y=True)
    return fig


def sector_heatmap(df: pd.DataFrame) -> go.Figure:
    """Sector x lookback-window return heatmap (red→green)."""
    periods = ["1W", "1M", "3M", "YTD"]
    sorted_df = df.sort_values("YTD", ascending=False)
    z = sorted_df[periods].values
    fig = go.Figure(go.Heatmap(
        z=z, x=periods, y=sorted_df["sector"].values,
        colorscale=[[0, "#e63946"], [0.5, "#1a1f2b"], [1, "#2a9d8f"]],
        zmid=0, text=[[f"{v:+.1f}%" for v in row] for row in z],
        texttemplate="%{text}", colorbar=dict(title="%"),
    ))
    fig.update_layout(title="Sector Relative Strength", template="plotly_dark",
                      height=430, margin=dict(l=40, r=20, t=50, b=30))
    return fig


def normalized_multi(series_map: dict, title: str) -> go.Figure:
    """Overlay several price series rebased to 100 for relative comparison."""
    fig = go.Figure()
    palette = ["#4cc9f0", "#f4a261", "#2a9d8f", "#e63946", "#b5179e", "#e9c46a"]
    for i, (name, s) in enumerate(series_map.items()):
        s = s.dropna()
        if s.empty:
            continue
        rebased = s / s.iloc[0] * 100
        fig.add_trace(go.Scatter(x=rebased.index, y=rebased.values, name=name,
                                 line=dict(color=palette[i % len(palette)], width=2)))
    fig.add_hline(y=100, line_dash="dot", line_color="grey", opacity=0.5)
    fig.update_layout(title=title, **_LAYOUT)
    fig.update_yaxes(title="Rebased to 100")
    return fig
