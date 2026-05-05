"""Cross-asset ratios: gold/silver, gold/oil, gold/copper, gold/SPX, gold/BTC, gold/GDX."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import TICKERS, get_close_panel

st.set_page_config(page_title="Cross-Asset Ratios", layout="wide")
st.title("Cross-Asset Ratios")
st.caption("Ratios reveal regime: gold/silver flags risk-off, gold/SPX shows long-cycle valuation, "
           "gold/GDX measures miner stretch.")

period = st.selectbox("History", ["1y", "2y", "5y", "10y"], index=2)

panel = get_close_panel({
    "gold":   TICKERS["gold_futures"],
    "silver": TICKERS["silver_futures"],
    "wti":    TICKERS["wti"],
    "copper": TICKERS["copper"],
    "spx":    TICKERS["spx"],
    "btc":    TICKERS["btc"],
    "gdx":    TICKERS["gdx"],
}, period=period).dropna(how="all")

if panel.empty:
    st.warning("No data.")
    st.stop()

ratios = pd.DataFrame({
    "Gold/Silver":  panel["gold"] / panel["silver"],
    "Gold/Oil":     panel["gold"] / panel["wti"],
    "Gold/Copper":  panel["gold"] / panel["copper"],
    "Gold/SPX":     panel["gold"] / panel["spx"],
    "Gold/BTC":     panel["gold"] / panel["btc"],
    "Gold/GDX":     panel["gold"] / panel["gdx"],
}).dropna(how="all")

# ---- Header tiles ----
def _last(s): return float(s.dropna().iloc[-1]) if s.dropna().size else float("nan")
def _z(s, n=252):
    s2 = s.dropna().tail(n)
    if s2.size < 30: return float("nan")
    return (s2.iloc[-1] - s2.mean()) / s2.std()

cols = st.columns(len(ratios.columns))
for i, name in enumerate(ratios.columns):
    cols[i].metric(name, f"{_last(ratios[name]):,.2f}", f"z={_z(ratios[name]):+.1f} (1y)",
                   help=f"Z-score over trailing 1y. |z|>2 = stretched.")

# ---- Charts ----
fig = make_subplots(rows=3, cols=2, subplot_titles=list(ratios.columns), vertical_spacing=0.10)
positions = [(1,1),(1,2),(2,1),(2,2),(3,1),(3,2)]
for (r, c), name in zip(positions, ratios.columns):
    s = ratios[name].dropna()
    fig.add_trace(go.Scatter(x=s.index, y=s, mode="lines", name=name, showlegend=False), row=r, col=c)
    # 1y mean line
    if s.size > 252:
        mean_1y = s.tail(252).mean()
        fig.add_hline(y=mean_1y, line_dash="dot", line_color="grey", row=r, col=c)

fig.update_layout(height=720, margin=dict(l=10, r=10, t=40, b=10))
st.plotly_chart(fig, use_container_width=True)

with st.expander("How to read this", expanded=False):
    st.markdown("""
- **Gold/Silver > 85** → safe-haven regime; silver lagging means industrial demand soft. Mean revert if gold stalls.
- **Gold/Oil**: high readings often during demand shocks. Long-run mean ~17–22.
- **Gold/Copper**: rising → growth fears (gold up, copper down). Falling → reflation.
- **Gold/SPX**: very long cycles. Below 1 = equities richly valued vs. gold; above 2 = gold stretched.
- **Gold/BTC**: digital vs. physical store-of-value. BTC outperforms in liquidity-flush regimes.
- **Gold/GDX**: high → miners cheap relative to gold (often a setup for miners to catch up).
""")
