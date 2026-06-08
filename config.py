"""Central configuration: symbols, FRED series IDs, thresholds, cache TTLs, and
composite-signal weights. Keep all "magic strings" here so panels stay declarative."""

# ---------------------------------------------------------------------------
# Cache TTLs (seconds)
# ---------------------------------------------------------------------------
TTL_MARKETS = 15 * 60      # intraday-ish market data
TTL_MACRO = 6 * 60 * 60    # slow-moving macro series
TTL_SENTIMENT = 30 * 60    # sentiment feeds

# ---------------------------------------------------------------------------
# FRED series IDs
# ---------------------------------------------------------------------------
# Treasury yields by maturity (in years) -> FRED constant-maturity series
YIELD_CURVE = {
    0.25: "DGS3MO",
    0.5: "DGS6MO",
    1: "DGS1",
    2: "DGS2",
    5: "DGS5",
    7: "DGS7",
    10: "DGS10",
    20: "DGS20",
    30: "DGS30",
}

FRED_SERIES = {
    # rates / spreads
    "spread_10y2y": "T10Y2Y",
    "spread_10y3m": "T10Y3M",
    "fed_funds": "DFF",
    "real_yield_10y": "DFII10",
    "breakeven_10y": "T10YIE",
    # growth / cycle
    "gdp_growth": "A191RL1Q225SBEA",   # real GDP, % change SAAR
    "gdp_level": "GDPC1",
    "industrial_production": "INDPRO",
    # inflation / money
    "cpi": "CPIAUCSL",
    "pce": "PCEPI",
    "m2": "M2SL",
    # labor
    "unemployment": "UNRATE",
    "initial_claims": "ICSA",
    "sahm": "SAHMREALTIME",
    # credit
    "hy_oas": "BAMLH0A0HYM2",
    "ig_oas": "BAMLC0A0CM",
    # sentiment / policy
    "umich_sentiment": "UMCSENT",
    "policy_uncertainty": "USEPUINDXD",
    # leading / housing / probability
    "mortgage_30y": "MORTGAGE30US",
    "recession_prob": "RECPROUSM156N",
    # valuation inputs
    "wilshire": "WILL5000PR",
    "gdp_nominal": "GDP",
}

# ---------------------------------------------------------------------------
# Financial Modeling Prep (FMP) — optional live source (REST API).
# Set FMP_API_KEY to enable. FMP takes priority over FRED for the keys below;
# anything FMP lacks (credit spreads, Sahm, policy uncertainty) falls back to
# FRED, then to bundled sample data.
# ---------------------------------------------------------------------------
FMP_BASE_URL = "https://financialmodelingprep.com/stable"

# logical series key -> FMP economic-indicator name
FMP_INDICATORS = {
    "cpi": "CPI",
    "unemployment": "unemploymentRate",
    "fed_funds": "federalFunds",
    "umich_sentiment": "consumerSentiment",
    "initial_claims": "initialClaims",
    "mortgage_30y": "30YearFixedRateMortgageAverage",
    "recession_prob": "smoothedUSRecessionProbabilities",
}
FMP_REAL_GDP = "realGDP"  # level -> we derive SAAR growth from it

# Mega-cap watchlist for the analyst spotlight (Market Intelligence tab).
ANALYST_WATCHLIST = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]

# Substrings that mark leveraged/inverse ETFs we filter out of "market movers".
MOVER_EXCLUDE = ["ETF", "Daily", "2X", "3X", "Bull", "Bear", "Leverage",
                 "UltraShort", "Ultra", " Long ", " Short "]

# ---------------------------------------------------------------------------
# yfinance tickers
# ---------------------------------------------------------------------------
INDICES = {
    "S&P 500": "^GSPC",
    "Dow Jones": "^DJI",
    "Nasdaq": "^IXIC",
    "VIX": "^VIX",
}

# Sector SPDR ETFs -> human label
SECTORS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLY": "Cons. Discretionary",
    "XLP": "Cons. Staples",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication",
}

CROSS_ASSET = {
    "US Dollar (DXY)": "DX-Y.NYB",
    "Gold": "GC=F",
    "Oil (WTI)": "CL=F",
    "Copper": "HG=F",
    "Bitcoin": "BTC-USD",
}

EQUAL_WEIGHT_SPY = "RSP"   # vs SPY for concentration/breadth proxy
SPY = "SPY"

# ---------------------------------------------------------------------------
# Sentiment endpoint
# ---------------------------------------------------------------------------
CNN_FEAR_GREED_URL = "https://production.cnn.com/markets/fear-and-greed/graphdata"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ---------------------------------------------------------------------------
# Composite regime signal
# ---------------------------------------------------------------------------
# Each component contributes a sub-score in [-1, +1] (positive = risk-on /
# bullish). Weights are normalized at runtime, so they need not sum to 1.
COMPOSITE_WEIGHTS = {
    "yield_curve": 0.20,   # steeper / un-inverted = risk-on
    "credit": 0.20,        # tight HY spreads = risk-on
    "vix": 0.15,           # low VIX = risk-on
    "fear_greed": 0.15,    # greed = risk-on (contrarian-aware but trend-following here)
    "trend": 0.15,         # SP500 above 200DMA = risk-on
    "valuation": 0.10,     # cheap valuation = risk-on
    "sahm": 0.05,          # Sahm rule not triggered = risk-on
}

# Mapping of composite score -> regime label / color
REGIME_BANDS = [
    (-1.01, -0.33, "Risk-Off", "#e63946"),
    (-0.33, 0.33, "Neutral", "#f4a261"),
    (0.33, 1.01, "Risk-On", "#2a9d8f"),
]

# NBER-dated US recessions (peak -> trough). Used to shade macro time-series
# charts. Source: NBER Business Cycle Dating Committee.
NBER_RECESSIONS = [
    ("1990-07-01", "1991-03-31"),
    ("2001-03-01", "2001-11-30"),
    ("2007-12-01", "2009-06-30"),
    ("2020-02-01", "2020-04-30"),
]

# Reference levels used for point-in-time normalization
VIX_CALM = 13.0
VIX_PANIC = 35.0
HY_OAS_TIGHT = 3.0       # %
HY_OAS_WIDE = 8.0        # %
CAPE_CHEAP = 15.0
CAPE_EXPENSIVE = 33.0
