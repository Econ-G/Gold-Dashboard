"""Gold Trading Dashboard — Overview page.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from lib.data import (
    TICKERS, FRED_SERIES,
    get_prices, get_last_price, get_close_panel,
    get_fred_series, get_conversion_model, gld_to_spot, spot_to_gld,
    pct_change, fmt_money, fmt_pct,
)

st.set_page_config(
    page_title="Gold Trading Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar — global controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Controls")
    refresh_min = st.slider("Auto-refresh (minutes)", 0, 30, 5,
                            help="0 = no auto-refresh. Cache TTL is 5 minutes regardless.")
    if st.button("Force refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Last load: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown("---")
    st.markdown(
        "**Pages**\n\n"
        "- Overview (this page)\n"
        "- Price & Technicals\n"
        "- Macro Drivers\n"
        "- Cross-Asset Ratios\n"
        "- Volatility\n"
        "- Seasonality\n"
        "- GLD ↔ Spot Converter"
    )

# Lightweight auto-refresh via meta tag (no extra deps)
if refresh_min > 0:
    st.markdown(
        f'<meta http-equiv="refresh" content="{refresh_min*60}">',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Gold Trading Dashboard")
st.caption("Real-time gold market monitor. Data: yfinance (prices) + FRED (macro). "
           "Cached 5 min for prices, 6 h for macro.")

# ---------------------------------------------------------------------------
# Top row — key prices
# ---------------------------------------------------------------------------
gold_now, gold_prev = get_last_price(TICKERS["gold_futures"])
gld_now,  gld_prev  = get_last_price(TICKERS["gld"])
dxy_now,  dxy_prev  = get_last_price(TICKERS["dxy"])
silver_now, silver_prev = get_last_price(TICKERS["silver_futures"])
btc_now, btc_prev   = get_last_price(TICKERS["btc"])
vix_now, vix_prev   = get_last_price(TICKERS["vix"])

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Gold spot ($/oz)", fmt_money(gold_now), fmt_pct(pct_change(gold_now, gold_prev)))
c2.metric("GLD ($)",          fmt_money(gld_now),  fmt_pct(pct_change(gld_now, gld_prev)))
c3.metric("Silver ($/oz)",    fmt_money(silver_now), fmt_pct(pct_change(silver_now, silver_prev)))
c4.metric("DXY",              fmt_money(dxy_now, 2), fmt_pct(pct_change(dxy_now, dxy_prev)))
c5.metric("BTC",              fmt_money(btc_now, 0), fmt_pct(pct_change(btc_now, btc_prev)))
c6.metric("VIX",              fmt_money(vix_now, 2), fmt_pct(pct_change(vix_now, vix_prev)))

st.markdown("---")

# ---------------------------------------------------------------------------
# Conversion strip
# ---------------------------------------------------------------------------
st.subheader("Spot ↔ GLD conversion")
try:
    model = get_conversion_model()
    ratio_today = gold_now / gld_now if gld_now else float("nan")

    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("Live ratio (spot/GLD)", f"{ratio_today:.4f}")
    cc2.metric("Fitted drift", f"{model['annual_drift_pct']:+.3f}%/yr",
               help="Recovers GLD's 0.40%/yr expense ratio from price data.")
    cc3.metric("Spot 4,550 → GLD", fmt_money(spot_to_gld(4550, model)))
    cc4.metric("Spot 5,300 → GLD", fmt_money(spot_to_gld(5300, model)))
except Exception as e:
    st.warning(f"Conversion model unavailable: {e}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Mini-snapshot: gold price chart with 50/200 SMA
# ---------------------------------------------------------------------------
st.subheader("Gold (1-year, futures continuous)")
g = get_prices(TICKERS["gold_futures"], period="1y")
if not g.empty:
    g["SMA50"]  = g["Close"].rolling(50).mean()
    g["SMA200"] = g["Close"].rolling(200).mean()
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=g.index, open=g["Open"], high=g["High"],
                                  low=g["Low"], close=g["Close"], name="Gold"))
    fig.add_trace(go.Scatter(x=g.index, y=g["SMA50"],  mode="lines",
                              name="50-day SMA", line=dict(width=1.2)))
    fig.add_trace(go.Scatter(x=g.index, y=g["SMA200"], mode="lines",
                              name="200-day SMA", line=dict(width=1.2)))
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_rangeslider_visible=False, legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Gold price data unavailable.")

# ---------------------------------------------------------------------------
# Quick macro tiles
# ---------------------------------------------------------------------------
st.subheader("Key macro drivers")
real10 = get_fred_series("DFII10", years=2)
nom10  = get_fred_series("DGS10",  years=2)
brk10  = get_fred_series("T10YIE", years=2)
ff     = get_fred_series("DFF",    years=2)

m1, m2, m3, m4 = st.columns(4)
def _last(s):
    return float(s.iloc[-1]) if len(s) else float("nan")
def _prev(s):
    return float(s.iloc[-2]) if len(s) >= 2 else float("nan")
def _bp(curr, prev):
    if pd.isna(curr) or pd.isna(prev): return "—"
    return f"{(curr-prev)*100:+.1f} bp"

m1.metric("10Y real yield (%)", f"{_last(real10):.2f}", _bp(_last(real10), _prev(real10)),
          help="Inverse-correlated with gold; #1 macro driver.")
m2.metric("10Y nominal (%)",    f"{_last(nom10):.2f}",  _bp(_last(nom10), _prev(nom10)))
m3.metric("Breakeven 10Y (%)",  f"{_last(brk10):.2f}",  _bp(_last(brk10), _prev(brk10)),
          help="Market-implied inflation expectation.")
m4.metric("Fed funds (%)",      f"{_last(ff):.2f}",     _bp(_last(ff), _prev(ff)))

st.caption("Open the **Macro Drivers** page for full charts and rolling correlations.")
