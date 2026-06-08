"""Sentiment data — primarily the CNN Fear & Greed Index via its public JSON
endpoint, with sample fallback."""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

import config
from data import DataResult
from data import sample


@st.cache_data(ttl=config.TTL_SENTIMENT, show_spinner=False)
def get_fear_greed() -> DataResult:
    """Return dict {score, rating, history(Series)} from CNN's Fear & Greed feed."""
    try:
        resp = requests.get(config.CNN_FEAR_GREED_URL, headers=config.BROWSER_HEADERS, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        fg = payload["fear_and_greed"]
        score = float(fg["score"])
        rating = fg.get("rating", sample.rating_for(score)).title()

        hist_raw = payload.get("fear_and_greed_historical", {}).get("data", [])
        if hist_raw:
            idx = pd.to_datetime([p["x"] for p in hist_raw], unit="ms")
            hist = pd.Series([p["y"] for p in hist_raw], index=idx, name="fear_greed")
        else:
            hist = sample.fear_greed()["history"]
        return DataResult({"score": score, "rating": rating, "history": hist}, is_sample=False)
    except Exception as exc:
        return DataResult(sample.fear_greed(), is_sample=True, note=str(exc)[:80])
