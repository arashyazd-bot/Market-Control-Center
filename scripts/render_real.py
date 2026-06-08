"""Render a LIVE-data preview of the dashboard using real figures pulled from
the financial-data MCP server (FMP) on 2026-06-08. Equity-index/VIX/commodity
quotes require a higher FMP plan tier, so those panels are omitted here; this
preview focuses on what's available live: the Treasury curve, the 10Y-2Y spread
history, macro indicators, today's sector performance, and Bitcoin."""
from __future__ import annotations

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
from PIL import Image

from components import charts
from scripts.render_shots import header_strip, fig_to_img, BG, WIDTH

OUT = "/tmp/shots"
os.makedirs(OUT, exist_ok=True)

# --- Real data captured from MCP (FMP), 2026-06-08 ---------------------------
YIELD_CURVE = {0.25: 3.78, 0.5: 3.81, 1: 3.88, 2: 4.17, 5: 4.29,
               7: 4.41, 10: 4.55, 20: 5.03, 30: 5.01}  # 2026-06-05
SECTORS_1D = {  # 2026-06-05 average daily % change
    "Healthcare": 0.19, "Real Estate": -0.05, "Financial Services": -0.18,
    "Consumer Defensive": -0.21, "Utilities": -1.06, "Basic Materials": -1.12,
    "Communication Services": -1.41, "Industrials": -2.03,
    "Consumer Cyclical": -4.13, "Technology": -4.51, "Energy": -5.64,
}
BTC = {"price": 63782, "chg": 3.07, "ma50": 75807, "ma200": 78476,
       "yr_high": 126296, "yr_low": 59073}
MACRO = {"gdp_saar": 1.62, "cpi_yoy": 3.78, "unemp": 4.3, "fedfunds": 3.63}
SPREAD_NOW = {"s10y2y": 0.38, "s10y3m": 0.77, "y10": 4.55, "y2": 4.17, "y3m": 3.78}
LEADING = {"sentiment": 49.8, "claims": 225000, "mortgage": 6.48, "recprob": 0.44}
CONSUMER_SENTIMENT = {  # UMich, monthly (real)
    "2024-06": 68.2, "2024-07": 66.4, "2024-08": 67.9, "2024-09": 70.1,
    "2024-10": 70.5, "2024-11": 71.8, "2024-12": 74.0, "2025-01": 71.7,
    "2025-02": 64.7, "2025-03": 57.0, "2025-04": 52.2, "2025-05": 52.2,
    "2025-06": 60.7, "2025-07": 61.7, "2025-08": 58.2, "2025-09": 55.1,
    "2025-10": 53.6, "2025-11": 51.0, "2025-12": 52.9, "2026-01": 56.4,
    "2026-02": 56.6, "2026-03": 53.3, "2026-04": 49.8,
}
RECESSION_PROB = {  # smoothed US recession probability, % (real)
    "2024-01": 2.64, "2024-04": 0.50, "2024-07": 0.86, "2024-10": 0.50,
    "2025-01": 0.54, "2025-04": 0.52, "2025-07": 0.52, "2025-08": 1.02,
    "2025-09": 1.26, "2025-10": 1.36, "2025-11": 0.76, "2025-12": 0.40,
    "2026-01": 0.34, "2026-02": 0.30, "2026-03": 0.46, "2026-04": 0.44,
}


def stack(imgs):
    total = sum(i.height for i in imgs) + 16 * (len(imgs) + 1)
    canvas = Image.new("RGB", (WIDTH, total), BG)
    y = 16
    for im in imgs:
        canvas.paste(im, (0, y)); y += im.height + 16
    return canvas


def sector_bar(sectors: dict) -> go.Figure:
    s = pd.Series(sectors).sort_values()
    colors = ["#2a9d8f" if v >= 0 else "#e63946" for v in s.values]
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index, orientation="h", marker_color=colors,
        text=[f"{v:+.1f}%" for v in s.values], textposition="outside",
    ))
    fig.update_layout(title="Sector Performance — 2026-06-05 (real, 1-day avg)",
                      template="plotly_dark", height=430,
                      margin=dict(l=40, r=40, t=50, b=30),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
    fig.update_xaxes(ticksuffix="%")
    return fig


def main():
    # ---- Panel A: Rates & Macro (LIVE) ----
    kpis = [
        ("10Y-2Y", f"+{SPREAD_NOW['s10y2y']:.2f}%", "un-inverted"),
        ("10Y Yield", f"{SPREAD_NOW['y10']:.2f}%", ""),
        ("Fed Funds", f"{MACRO['fedfunds']:.2f}%", "-0.70 yoy"),
        ("CPI YoY", f"{MACRO['cpi_yoy']:.1f}%", ""),
        ("Unemployment", f"{MACRO['unemp']:.1f}%", ""),
        ("GDP SAAR", f"+{MACRO['gdp_saar']:.1f}%", ""),
    ]
    hdr = header_strip("Rates & Macro — LIVE", "Real data via FMP MCP  -  2026-06-08",
                       kpis)

    curve = pd.Series(YIELD_CURVE, name="yield_curve")
    figs = [(charts.yield_curve_chart(curve), 340)]
    # Spread history comes from the captured MCP treasury file (preview snapshot).
    spread_file = "/tmp/real_spreads.json"
    if os.path.exists(spread_file):
        spreads = pd.DataFrame(json.load(open(spread_file)))
        spreads["date"] = pd.to_datetime(spreads["date"])
        spreads = spreads.set_index("date")
        figs += [
            (charts.spread_chart(spreads["s10y2y"], "10Y-2Y Spread (real, 2019-2026)"), 320),
            (charts.spread_chart(spreads["s10y3m"], "10Y-3M Spread (real, 2019-2026)"), 320),
        ]
    imgs = [hdr] + [fig_to_img(f, WIDTH, h) for f, h in figs]
    stack(imgs).save(f"{OUT}/real_1_rates_macro.png")

    # ---- Panel B: Sectors & Crypto (LIVE) ----
    btc_sub = f"vs 200DMA {BTC['ma200']:,}  ({(BTC['price']/BTC['ma200']-1)*100:+.0f}%)"
    kpis2 = [
        ("Bitcoin", f"${BTC['price']:,}", f"+{BTC['chg']:.1f}%"),
        ("BTC 50DMA", f"${BTC['ma50']:,}", ""),
        ("BTC 200DMA", f"${BTC['ma200']:,}", "price below = bearish"),
        ("BTC 1Y range", f"${BTC['yr_low']/1000:.0f}k-{BTC['yr_high']/1000:.0f}k", ""),
    ]
    hdr2 = header_strip("Sectors & Crypto — LIVE", "Real data via FMP MCP  -  2026-06-08",
                        kpis2)
    imgs2 = [hdr2, fig_to_img(sector_bar(SECTORS_1D), WIDTH, 430)]
    stack(imgs2).save(f"{OUT}/real_2_sectors_crypto.png")

    # ---- Panel C: Leading, Housing & Policy (LIVE) ----
    kpis3 = [
        ("Consumer Sent.", f"{LEADING['sentiment']:.1f}", "UMich — depressed"),
        ("Initial Claims", f"{LEADING['claims']:,}", "weekly — healthy"),
        ("30Y Mortgage", f"{LEADING['mortgage']:.2f}%", "-0.37 yoy"),
        ("Recession Prob", f"{LEADING['recprob']:.2f}%", "smoothed — low"),
    ]
    hdr3 = header_strip("Leading, Housing & Policy — LIVE",
                        "Real data via FMP MCP  -  2026-06-08", kpis3)

    def _series(d):
        s = pd.Series({pd.Timestamp(k + "-01"): v for k, v in d.items()}).sort_index()
        return s

    recprob = _series(RECESSION_PROB)
    sent = _series(CONSUMER_SENTIMENT)
    figs3 = [
        (charts.line_chart(recprob, "Smoothed US Recession Probability (real)",
                           color="#e63946", y_suffix="%"), 300),
        (charts.line_chart(sent, "Consumer Sentiment — UMich (real)",
                           color="#e9c46a"), 300),
    ]
    imgs3 = [hdr3] + [fig_to_img(f, WIDTH, h) for f, h in figs3]
    stack(imgs3).save(f"{OUT}/real_3_leading.png")

    for p in ("real_1_rates_macro", "real_2_sectors_crypto", "real_3_leading"):
        print(f"{OUT}/{p}.png")


if __name__ == "__main__":
    main()
