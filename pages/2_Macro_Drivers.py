"""Macro drivers: real yields, breakeven, DXY, fed funds. The 'why is gold moving' page."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import TICKERS, get_prices, get_fred_panel, FRED_SERIES
from lib.indicators import rolling_corr

st.set_page_config(page_title="Macro Drivers", layout="wide")
st.title("Macro Drivers")
st.caption("Gold's main drivers are real yields (inverse), DXY (inverse), and inflation expectations. "
           "Watch the rolling correlation panel to confirm regime.")

years = st.slider("History (years)", 1, 10, 3)

# ---- Data pulls ----
fred = get_fred_panel({k: v for k, v in FRED_SERIES.items() if k in
                       ["real_10y", "real_5y", "breakeven_10y", "nominal_10y", "nominal_2y", "fed_funds"]},
                      years=years)
gold = get_prices(TICKERS["gold_futures"], period=f"{years}y")["Close"]
dxy  = get_prices(TICKERS["dxy"],          period=f"{years}y")["Close"]

if fred.empty or gold.empty:
    st.warning("Macro data unavailable; check connection.")
    st.stop()

# Align
gold = gold.reindex(fred.index, method="ffill")
dxy  = dxy.reindex(fred.index, method="ffill")

# ---- Header tiles ----
def _last(s): return float(s.dropna().iloc[-1]) if s.dropna().size else float("nan")
def _delta_bp(s, lookback=21):
    if s.dropna().size < lookback + 1: return float("nan")
    return (s.dropna().iloc[-1] - s.dropna().iloc[-lookback - 1]) * 100

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("10Y real (%)", f"{_last(fred['real_10y']):.2f}", f"{_delta_bp(fred['real_10y']):+.0f}bp 1m")
c2.metric("5Y real (%)",  f"{_last(fred['real_5y']):.2f}",  f"{_delta_bp(fred['real_5y']):+.0f}bp 1m")
c3.metric("10Y breakeven (%)", f"{_last(fred['breakeven_10y']):.2f}", f"{_delta_bp(fred['breakeven_10y']):+.0f}bp 1m")
c4.metric("DXY", f"{_last(dxy):.2f}",
          f"{(dxy.dropna().iloc[-1]/dxy.dropna().iloc[-22]-1)*100:+.2f}% 1m" if dxy.dropna().size > 22 else "—")
c5.metric("Fed funds (%)", f"{_last(fred['fed_funds']):.2f}")

st.markdown("---")

# ---- Gold vs 10Y real yield (the chart that matters most) ----
st.subheader("Gold vs. 10-year real yield (inverse axis)")
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(x=gold.index, y=gold, name="Gold ($/oz)", line=dict(color="#d4af37", width=1.6)),
              secondary_y=False)
fig.add_trace(go.Scatter(x=fred.index, y=fred["real_10y"], name="10Y real yield (%)",
                         line=dict(color="#1f77b4", width=1.2)),
              secondary_y=True)
fig.update_yaxes(title_text="Gold ($/oz)", secondary_y=False)
fig.update_yaxes(title_text="10Y real yield (%)", secondary_y=True, autorange="reversed")
fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)

# ---- Gold vs DXY ----
st.subheader("Gold vs. DXY (inverse axis)")
fig2 = make_subplots(specs=[[{"secondary_y": True}]])
fig2.add_trace(go.Scatter(x=gold.index, y=gold, name="Gold ($/oz)", line=dict(color="#d4af37", width=1.6)))
fig2.add_trace(go.Scatter(x=dxy.index, y=dxy, name="DXY", line=dict(color="#2ca02c", width=1.2)),
               secondary_y=True)
fig2.update_yaxes(title_text="Gold ($/oz)", secondary_y=False)
fig2.update_yaxes(title_text="DXY", secondary_y=True, autorange="reversed")
fig2.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig2, use_container_width=True)

# ---- Rolling correlations ----
st.subheader("Rolling 60-day correlation: gold daily returns vs. drivers")
corr_df = pd.DataFrame({
    "vs 10Y real":       rolling_corr(gold, fred["real_10y"], 60),
    "vs 10Y breakeven":  rolling_corr(gold, fred["breakeven_10y"], 60),
    "vs DXY":            rolling_corr(gold, dxy, 60),
    "vs 10Y nominal":    rolling_corr(gold, fred["nominal_10y"], 60),
}).dropna(how="all")

fig3 = go.Figure()
for col in corr_df.columns:
    fig3.add_trace(go.Scatter(x=corr_df.index, y=corr_df[col], name=col, mode="lines"))
fig3.add_hline(y=0, line_dash="dash", line_color="grey")
fig3.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                   yaxis_title="Correlation", legend=dict(orientation="h"))
st.plotly_chart(fig3, use_container_width=True)

with st.expander("How to read this", expanded=False):
    st.markdown("""
- **Strong negative correlation with 10Y real (-0.5 or lower)** = classic regime. Gold reacts mechanically to TIPS yields.
- **Correlation flipping toward zero or positive** = thesis decoupling. Often happens during crisis (gold rallies *with* yields on safe-haven flows) or Fed pivots.
- **Negative correlation with DXY** is the second pillar; usually around -0.4 to -0.7.
- **Positive correlation with breakevens** = inflation hedge story working.
""")
