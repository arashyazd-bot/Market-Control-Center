# Market-Timing Dashboard

A single-pane-of-glass [Streamlit](https://streamlit.io) dashboard for reading the
state of the US economy, markets, sentiment, and policy — built to support top-down
asset-allocation timing (stocks, sectors, real estate).

## What's on it

| Tab | What it answers | Key indicators |
|-----|-----------------|----------------|
| **🧭 Overview** | What's the regime *right now*? | Composite Risk-On/Neutral/Risk-Off gauge, Fear & Greed, KPI strip |
| **💰 Valuation** | Is the market expensive? | Shiller CAPE, Buffett Indicator, Equity Risk Premium, P/E |
| **😱 Sentiment & Internals** | Fear vs greed; is the rally healthy? | Fear & Greed, VIX, sector heatmap, breadth/concentration |
| **📈 Rates & Macro** | Where are we in the cycle? | Yield curve, 10Y–2Y / 10Y–3M spreads, credit spreads, GDP vs S&P, Sahm, CPI |
| **🌍 Cross-Asset & Politics** | Risk appetite & policy risk | DXY, gold, oil, copper/gold, BTC, Policy Uncertainty index |
| **💹 Market Intelligence** | Stock/sector picking edge | Sector P/E valuation, analyst ratings & price targets (watchlist), market movers, congressional trades |

The **Composite Regime** score blends a weighted basket of normalized signals
(yield-curve slope, credit spreads, VIX, Fear & Greed, trend vs 200DMA, valuation,
Sahm rule) into one headline number. Weights live in `config.py` and are fully tunable.

## Quick start

```bash
pip install -r requirements.txt

# Optional but recommended — enables live macro/rates data:
cp .env.example .env
# then edit .env and paste a free key from https://fredaccount.stlouisfed.org/apikeys

streamlit run app.py        # opens http://localhost:8501
```

The dashboard **runs with no setup** — without a FRED key or internet it renders on
bundled sample data, flagged with a 🟡 badge per panel so live vs. sample state is
never ambiguous.

## Deploy on Render

The repo ships a `render.yaml` blueprint. In Render: **New ▸ Blueprint**, point at
this repo, and add your `FRED_API_KEY` / `FMP_API_KEY` values (they're declared with
`sync: false`, so they stay out of git). The blueprint sets the build and start
commands — Streamlit binds Render's `$PORT` on `0.0.0.0` automatically.

To wire it up manually instead, use:

- **Build:** `pip install -r requirements.txt`
- **Start:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

## Data sources

Rates/macro resolve in priority order **FMP → FRED → sample**, so the app works
with either key, both, or neither:

- **FMP** (Financial Modeling Prep, optional `FMP_API_KEY`) — treasury curve, GDP,
  CPI, unemployment, fed funds, consumer sentiment, initial claims, 30Y mortgage,
  recession probability, sector performance, economic calendar
- **FRED** (St. Louis Fed, `FRED_API_KEY`) — yields, GDP, inflation, labor, credit
  spreads, Sahm rule, policy uncertainty (and fallback for everything FMP lacks)
- **Yahoo Finance** (`yfinance`) — indices, VIX, sector ETFs, cross-asset prices
- **CNN Fear & Greed Index** — sentiment

Some FMP endpoints (calendar, index/commodity/forex quotes) require a paid FMP
tier; the app degrades gracefully to FRED/sample for those.

## Architecture

```
app.py              Streamlit entry: layout, sidebar, tabs
config.py           All symbols, FRED series IDs, thresholds, weights, TTLs
data/               Fetchers (fred, markets, sentiment, valuation, composite) + sample fallback
components/         Plotly gauges, charts, and per-tab panel renderers
utils/              Formatting helpers
```

Every fetch is cached (`st.cache_data`) and wrapped to fall back to `data/sample.py`
on any failure, returning a `DataResult` that carries a live/sample flag.

## Roadmap (v1 out of scope)

Live AAII survey, CME FedWatch rate-cut odds, news-sentiment feed, composite-signal
backtesting, alerting, and cloud deployment.
