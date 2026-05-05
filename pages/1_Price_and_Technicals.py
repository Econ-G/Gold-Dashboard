"""Price & Technical indicators page."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import TICKERS, get_prices
from lib.indicators import sma, ema, rsi, macd, bollinger, atr, realized_vol_series, support_resistance_levels

st.set_page_config(page_title="Price & Technicals", layout="wide")
st.title("Price & Technicals")

# ---- Controls ----
col_a, col_b, col_c = st.columns([1, 1, 2])
with col_a:
    instrument = st.selectbox(
        "Instrument",
        options=["gold_futures", "gld", "iau", "silver_futures", "gdx", "gdxj"],
        format_func=lambda k: f"{k}  ({TICKERS[k]})",
    )
with col_b:
    period = st.selectbox("History", ["6mo", "1y", "2y", "5y", "10y"], index=2)
with col_c:
    show_bb = st.checkbox("Bollinger Bands (20, 2σ)", value=True)
    show_ma = st.checkbox("Moving averages (20/50/200)", value=True)
    show_sr = st.checkbox("Auto-detected support/resistance", value=True)

df = get_prices(TICKERS[instrument], period=period)
if df.empty:
    st.warning("No data.")
    st.stop()

close = df["Close"]

# ---- Indicators ----
df["SMA20"]  = sma(close, 20)
df["SMA50"]  = sma(close, 50)
df["SMA200"] = sma(close, 200)
df["EMA21"]  = ema(close, 21)
df["RSI14"]  = rsi(close, 14)
m = macd(close)
bb = bollinger(close, 20, 2.0)
df["ATR14"]  = atr(df, 14)
df["RV30"]   = realized_vol_series(close, 30) * 100

# ---- Header tiles ----
last = close.iloc[-1]
prev = close.iloc[-2]
chg_pct = (last / prev - 1) * 100

t1, t2, t3, t4, t5, t6 = st.columns(6)
t1.metric("Last", f"${last:,.2f}", f"{chg_pct:+.2f}%")
t2.metric("RSI(14)", f"{df['RSI14'].iloc[-1]:.1f}")
t3.metric("ATR(14)", f"${df['ATR14'].iloc[-1]:,.2f}")
t4.metric("Real vol 30d", f"{df['RV30'].iloc[-1]:.1f}%")
t5.metric("vs SMA50",  f"{(last/df['SMA50'].iloc[-1]-1)*100:+.2f}%"  if not pd.isna(df['SMA50'].iloc[-1])  else "—")
t6.metric("vs SMA200", f"{(last/df['SMA200'].iloc[-1]-1)*100:+.2f}%" if not pd.isna(df['SMA200'].iloc[-1]) else "—")

# ---- Multi-panel chart ----
fig = make_subplots(
    rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
    row_heights=[0.55, 0.15, 0.15, 0.15],
    subplot_titles=("Price", "Volume", "RSI(14)", "MACD"),
)

# Price + overlays
fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                              low=df["Low"], close=df["Close"], name="Price"), row=1, col=1)
if show_ma:
    for col, color in [("SMA20", "#1f77b4"), ("SMA50", "#ff7f0e"), ("SMA200", "#2ca02c")]:
        fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=col,
                                  line=dict(width=1.1, color=color)), row=1, col=1)
if show_bb:
    fig.add_trace(go.Scatter(x=df.index, y=bb["upper"], mode="lines",
                              line=dict(width=0.8, color="rgba(150,150,150,0.6)"),
                              name="BB upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=bb["lower"], mode="lines",
                              line=dict(width=0.8, color="rgba(150,150,150,0.6)"),
                              fill="tonexty", fillcolor="rgba(150,150,150,0.08)",
                              name="BB lower"), row=1, col=1)

if show_sr:
    sr = support_resistance_levels(close, window=10, n_levels=4, tolerance=0.015)
    for price, touches in sr["resistance"]:
        fig.add_hline(y=price, line_dash="dot", line_color="rgba(214,39,40,0.55)",
                      annotation_text=f"R ${price:.0f} ({touches}x)",
                      annotation_position="right", row=1, col=1)
    for price, touches in sr["support"]:
        fig.add_hline(y=price, line_dash="dot", line_color="rgba(44,160,44,0.55)",
                      annotation_text=f"S ${price:.0f} ({touches}x)",
                      annotation_position="right", row=1, col=1)

# Volume
if "Volume" in df.columns and df["Volume"].sum() > 0:
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume",
                          marker=dict(color="rgba(100,100,100,0.5)")), row=2, col=1)

# RSI
fig.add_trace(go.Scatter(x=df.index, y=df["RSI14"], name="RSI", line=dict(color="#9467bd")), row=3, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red",   row=3, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

# MACD
fig.add_trace(go.Bar(x=df.index, y=m["hist"], name="MACD hist",
                      marker=dict(color="rgba(100,100,100,0.5)")), row=4, col=1)
fig.add_trace(go.Scatter(x=df.index, y=m["macd"],   name="MACD",   line=dict(color="#1f77b4")), row=4, col=1)
fig.add_trace(go.Scatter(x=df.index, y=m["signal"], name="Signal", line=dict(color="#ff7f0e")), row=4, col=1)

fig.update_layout(height=820, margin=dict(l=10, r=10, t=40, b=10),
                  xaxis_rangeslider_visible=False, legend=dict(orientation="h"),
                  showlegend=True)
fig.update_xaxes(rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# ---- Quick read ----
with st.expander("How to read this", expanded=False):
    st.markdown("""
- **Price above 50-SMA above 200-SMA** = healthy uptrend. Inverse = downtrend.
- **RSI > 70** typically means overbought (pullback risk); **< 30** oversold (bounce candidate).
- **MACD histogram** flipping from negative to positive = momentum turning up.
- **Bollinger band touches** mark statistical extremes — not signals on their own; pair with RSI.
- **ATR** is a position-sizing input: stops set at 1–2× ATR avoid noise stop-outs.
""")
