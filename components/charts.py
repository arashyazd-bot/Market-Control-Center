"""Reusable Plotly chart builders shared across panels."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import config


def _dark() -> bool:
    try:
        return bool(st.session_state.get("dark_mode", False))
    except Exception:
        return False


def _template() -> str:
    return "plotly_dark" if _dark() else "plotly"


def _paper_bg() -> str:
    return "rgba(0,0,0,0)"


def _font_color() -> str:
    return "#E2E8F0" if _dark() else "#0F172A"


def _grid_color() -> str:
    return "rgba(255,255,255,0.08)" if _dark() else "rgba(0,0,0,0.07)"


# Semantic colors per theme — meets WCAG AA contrast on both backgrounds
_COLORS = {
    True: {   # dark
        "primary": "#4cc9f0",
        "warning": "#f4a261",
        "success": "#2a9d8f",
        "danger":  "#e63946",
        "purple":  "#b5179e",
        "yellow":  "#e9c46a",
    },
    False: {  # light
        "primary": "#1D4ED8",
        "warning": "#C2410C",
        "success": "#047857",
        "danger":  "#B91C1C",
        "purple":  "#6D28D9",
        "yellow":  "#92400E",
    },
}

_HEATMAP_SCALE = {
    True:  [[0, "#e63946"], [0.5, "#1a1f2b"], [1, "#2a9d8f"]],
    False: [[0, "#B91C1C"], [0.5, "#E2E8F0"], [1, "#047857"]],
}


def c(name: str) -> str:
    """Return a theme-correct semantic color."""
    return _COLORS[_dark()][name]


def _layout(**extra) -> dict:
    fc = _font_color()
    gc = _grid_color()
    base = dict(
        template=_template(),
        paper_bgcolor=_paper_bg(),
        plot_bgcolor=_paper_bg(),
        margin=dict(l=40, r=20, t=50, b=30),
        height=320,
        hovermode="x unified",
        dragmode="pan",          # click-drag pans; scroll/pinch zooms
        font=dict(size=13, color=fc, family="Figtree, system-ui, sans-serif"),
        xaxis=dict(gridcolor=gc, zerolinecolor=gc, tickfont=dict(size=13)),
        yaxis=dict(gridcolor=gc, zerolinecolor=gc, tickfont=dict(size=13)),
        legend=dict(font=dict(size=13)),
    )
    base.update(extra)
    return base


def add_recession_shading(fig: go.Figure, x_start, x_end, label: bool = True) -> go.Figure:
    try:
        x_start, x_end = pd.Timestamp(x_start), pd.Timestamp(x_end)
    except (ValueError, TypeError):
        return fig
    shc = "rgba(120,120,120,0.15)"
    labeled = False
    for rs, re in config.NBER_RECESSIONS:
        lo, hi = max(pd.Timestamp(rs), x_start), min(pd.Timestamp(re), x_end)
        if lo >= hi:
            continue
        fig.add_vrect(
            x0=lo, x1=hi, fillcolor=shc, line_width=0, layer="below",
            annotation_text="Recession" if (label and not labeled) else None,
            annotation_position="top left",
            annotation=dict(font=dict(size=12, color="#9aa0a6")),
        )
        labeled = True
    return fig


def _xrange(*series: pd.Series):
    idxs = [s.index for s in series if s is not None and len(s)]
    if not idxs:
        return None
    return min(i.min() for i in idxs), max(i.max() for i in idxs)


def line_chart(series: pd.Series, title: str, color: str | None = None,
               y_suffix: str = "", fill: bool = False,
               recessions: bool = False) -> go.Figure:
    col = color or c("primary")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values, mode="lines", name=title,
        line=dict(color=col, width=2.5), fill="tozeroy" if fill else None,
    ))
    fig.update_layout(title=title, **_layout())
    fig.update_yaxes(ticksuffix=y_suffix)
    if recessions:
        rng = _xrange(series)
        if rng:
            add_recession_shading(fig, *rng)
    return fig


def spread_chart(series: pd.Series, title: str, y_suffix: str = "%",
                 recessions: bool = True) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values, mode="lines",
        line=dict(color=c("primary"), width=2.5), name=title,
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=c("danger"), opacity=0.7)
    fig.update_layout(title=title, **_layout())
    fig.update_yaxes(ticksuffix=y_suffix)
    if recessions:
        rng = _xrange(series)
        if rng:
            add_recession_shading(fig, *rng)
    return fig


def yield_curve_chart(curve: pd.Series) -> go.Figure:
    s = curve.sort_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values, mode="lines+markers",
        line=dict(color=c("primary"), width=3),
        marker=dict(size=9),
    ))
    fig.update_layout(title="US Treasury Yield Curve", **_layout())
    fig.update_xaxes(title="Maturity (years)", type="log",
                     tickvals=list(s.index), ticktext=[str(x) for x in s.index])
    fig.update_yaxes(title="Yield", ticksuffix="%")
    return fig


def dual_axis_chart(left: pd.Series, right: pd.Series, left_name: str,
                    right_name: str, title: str, recessions: bool = True) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=left.index, y=left.values, name=left_name,
                             line=dict(color=c("warning"), width=2.5)),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=right.index, y=right.values, name=right_name,
                             line=dict(color=c("primary"), width=2.5)),
                  secondary_y=True)
    fig.update_layout(title=title, **_layout())
    fig.update_yaxes(title=left_name, secondary_y=False)
    fig.update_yaxes(title=right_name, secondary_y=True)
    if recessions:
        rng = _xrange(left, right)
        if rng:
            add_recession_shading(fig, *rng)
    return fig


def sector_heatmap(df: pd.DataFrame) -> go.Figure:
    periods = ["1W", "1M", "3M", "YTD"]
    sorted_df = df.sort_values("YTD", ascending=False)
    z = sorted_df[periods].values
    fig = go.Figure(go.Heatmap(
        z=z, x=periods, y=sorted_df["sector"].values,
        colorscale=_HEATMAP_SCALE[_dark()],
        zmid=0, text=[[f"{v:+.1f}%" for v in row] for row in z],
        texttemplate="%{text}", colorbar=dict(title="%"),
    ))
    fig.update_layout(title="Sector Relative Strength",
                      **_layout(height=430))
    return fig


def normalized_multi(series_map: dict, title: str) -> go.Figure:
    dark = _dark()
    palette = list(_COLORS[dark].values())
    fig = go.Figure()
    for i, (name, s) in enumerate(series_map.items()):
        s = s.dropna()
        if s.empty:
            continue
        rebased = s / s.iloc[0] * 100
        fig.add_trace(go.Scatter(x=rebased.index, y=rebased.values, name=name,
                                 line=dict(color=palette[i % len(palette)], width=2.5)))
    fig.add_hline(y=100, line_dash="dot",
                  line_color="#888888" if dark else "#94A3B8", opacity=0.6)
    fig.update_layout(title=title, **_layout())
    fig.update_yaxes(title="Rebased to 100")
    return fig
