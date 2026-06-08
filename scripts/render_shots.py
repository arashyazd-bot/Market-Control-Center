"""Render the dashboard's panels to static PNGs (for phone preview when a live
browser/server isn't reachable). Uses kaleido for Plotly export and PIL to
stack each tab's charts under a KPI header strip. Runs on whatever data the
data layer returns (sample fallback when offline)."""
from __future__ import annotations

import io
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

import config
from components import charts, gauges
from data import composite, fred, markets, sentiment, valuation
from utils.formatting import fmt_num, fmt_delta

BG = (14, 17, 23)
CARD = (26, 31, 43)
FG = (230, 230, 230)
MUTED = (154, 160, 166)
ACCENT = (76, 201, 240)
WIDTH = 980
OUT = "/tmp/shots"
os.makedirs(OUT, exist_ok=True)


def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def fig_to_img(fig, w, h):
    png = fig.to_image(format="png", width=w, height=h, scale=1)
    return Image.open(io.BytesIO(png)).convert("RGB")


def header_strip(title, subtitle, kpis):
    """kpis: list of (label, value, sub) tuples rendered as cards."""
    h = 170 if kpis else 90
    img = Image.new("RGB", (WIDTH, h), BG)
    d = ImageDraw.Draw(img)
    d.text((24, 16), title, font=font(34, bold=True), fill=FG)
    d.text((24, 58), subtitle, font=font(18), fill=MUTED)
    if kpis:
        n = len(kpis)
        gap = 12
        cw = (WIDTH - 24 * 2 - gap * (n - 1)) // n
        x = 24
        for label, value, sub in kpis:
            d.rounded_rectangle([x, 92, x + cw, 158], radius=10, fill=CARD)
            d.text((x + 14, 100), label, font=font(15), fill=MUTED)
            d.text((x + 14, 118), value, font=font(26, bold=True), fill=FG)
            if sub:
                col = (42, 157, 143) if sub.startswith("+") else (
                    (230, 57, 70) if sub.startswith("-") else MUTED)
                d.text((x + 14, 150 - 4), sub, font=font(13), fill=col)
            x += cw + gap
    return img


def row(figs_with_w, h):
    """Render several square-ish figures centered side by side in equal slots."""
    canvas = Image.new("RGB", (WIDTH, h), BG)
    slot = WIDTH // len(figs_with_w)
    for i, (fig, size) in enumerate(figs_with_w):
        fig.update_layout(margin=dict(l=10, r=10, t=70, b=10),
                          paper_bgcolor="#0e1117")
        im = fig_to_img(fig, size, size)
        x = i * slot + (slot - size) // 2
        y = (h - size) // 2
        canvas.paste(im, (x, y))
    return canvas


def stack(title, subtitle, kpis, figs):
    imgs = [header_strip(title, subtitle, kpis)]
    for fig, hh in figs:
        # A tuple of (fig, w) pairs means render them as a side-by-side row.
        if isinstance(fig, list):
            imgs.append(row(fig, hh))
        else:
            imgs.append(fig_to_img(fig, WIDTH, hh))
    total_h = sum(i.height for i in imgs) + 16 * (len(imgs) + 1)
    canvas = Image.new("RGB", (WIDTH, total_h), BG)
    y = 16
    for i in imgs:
        canvas.paste(i, (0, y))
        y += i.height + 16
    return canvas


def main():
    paths = []

    # ---- Overview ----
    regime = composite.compute_regime()
    sp = markets.quote("^GSPC"); vix = markets.quote("^VIX")
    spread = fred.get_series("spread_10y2y"); fg = sentiment.get_fear_greed()
    kpis = [
        ("S&P 500", fmt_num(sp.data["price"], 0), fmt_delta(sp.data["change_pct"])),
        ("VIX", fmt_num(vix.data["price"], 1), fmt_delta(vix.data["change_pct"])),
        ("10Y-2Y", fmt_num(fred.latest(spread), 2, suffix="%"), ""),
        ("Fear/Greed", fmt_num(fg.data["score"], 0), fg.data["rating"]),
        ("Regime", regime.data["label"], ""),
    ]
    ov = stack("Market Regime", "Single pane of glass  -  sample data preview", kpis, [
        ([(gauges.regime_gauge(regime.data["score"], regime.data["label"],
                               regime.data["color"]), 470),
          (gauges.fear_greed_gauge(fg.data["score"], fg.data["rating"]), 470)], 480),
    ])
    p = f"{OUT}/1_overview.png"; ov.save(p); paths.append(p)

    # ---- Rates & Macro ----
    curve = fred.get_yield_curve()
    s2 = fred.get_series("spread_10y2y"); hy = fred.get_series("hy_oas")
    gdp = fred.get_series("gdp_growth"); sp2 = markets.price_history("^GSPC", "2y")
    sp_yoy = (sp2.data["Close"].pct_change(252) * 100).dropna()
    rm = stack("Rates & Macro Cycle", "Yield curve, spreads, credit, growth", [], [
        (charts.yield_curve_chart(curve.data), 320),
        (charts.spread_chart(s2.data, "10Y-2Y Spread (recession signal)"), 300),
        (charts.line_chart(hy.data, "High-Yield Credit Spread (OAS)", color="#e63946",
                           y_suffix="%"), 300),
        (charts.dual_axis_chart(gdp.data, sp_yoy, "Real GDP growth %", "S&P 500 YoY %",
                                "Growth: Economy vs Market"), 320),
    ])
    p = f"{OUT}/2_rates_macro.png"; rm.save(p); paths.append(p)

    # ---- Sentiment & Internals ----
    vixh = markets.price_history("^VIX", "1y"); sectors = markets.sector_performance()
    se = stack("Sentiment & Internals", "Fear/greed, volatility, sector rotation", [], [
        (charts.line_chart(fg.data["history"], "Fear & Greed (1Y)", color="#e9c46a"), 300),
        (charts.line_chart(vixh.data["Close"], "VIX (1Y)", color="#e63946"), 300),
        (charts.sector_heatmap(sectors.data), 430),
    ])
    p = f"{OUT}/3_sentiment.png"; se.save(p); paths.append(p)

    # ---- Cross-asset & Politics ----
    series_map = {n: markets.price_history(t, "1y").data["Close"]
                  for n, t in config.CROSS_ASSET.items()}
    copper = markets.price_history("HG=F", "1y"); gold = markets.price_history("GC=F", "1y")
    ratio = (copper.data["Close"] / gold.data["Close"]).dropna()
    epu = fred.get_series("policy_uncertainty")
    ca = stack("Cross-Asset & Policy", "Risk appetite & policy risk", [], [
        (charts.normalized_multi(series_map, "Cross-Asset (1Y, rebased to 100)"), 320),
        (charts.line_chart(ratio, "Copper / Gold ratio (growth barometer)",
                           color="#f4a261"), 300),
        (charts.line_chart(epu.data, "Economic Policy Uncertainty Index",
                           color="#b5179e"), 300),
    ])
    p = f"{OUT}/4_crossasset.png"; ca.save(p); paths.append(p)

    print("\n".join(paths))


if __name__ == "__main__":
    main()
