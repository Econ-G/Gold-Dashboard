"""CFTC COT positioning + GLD ETF snapshot."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import (
    TICKERS, get_prices, get_cftc_cot, get_etf_snapshot,
)

st.set_page_config(page_title="Positioning & Flows", layout="wide")
st.title("Positioning & Flows")
st.caption("CFTC weekly Commitments of Traders for COMEX gold (futures-only, disaggregated). "
           "Tracks where speculators are positioned relative to historical extremes — "
           "stretched longs are vulnerable to liquidation, stretched shorts to squeezes.")

years = st.slider("History (years)", 2, 10, 5)
cot = get_cftc_cot(years=years)
gold = get_prices(TICKERS["gold_futures"], period=f"{years}y")["Close"]

if cot.empty:
    st.warning("CFTC data unavailable. The Socrata endpoint may be temporarily down.")
    st.stop()

# ---------------------------------------------------------------------------
# Header tiles — current positioning vs history
# ---------------------------------------------------------------------------
last = cot.iloc[-1]

def _pctile(series: pd.Series, value: float) -> float:
    return float((series < value).mean() * 100)

mm_long  = float(last["m_money_positions_long_all"])
mm_short = float(last["m_money_positions_short_all"])
mm_net   = float(last["mm_net_long"])
oi       = float(last["open_interest_all"])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Latest report", last.name.strftime("%Y-%m-%d"))
c2.metric("Managed money net long", f"{mm_net:,.0f}",
          f"pctile {_pctile(cot['mm_net_long'], mm_net):.0f}",
          help="Where current MM net long stands vs. history. Above 80 = stretched long.")
c3.metric("MM long (% of OI)",  f"{last['mm_long_pct']:.1f}%")
c4.metric("MM short (% of OI)", f"{last['mm_short_pct']:.1f}%")
c5.metric("Open interest",      f"{oi:,.0f}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Chart 1: Gold price vs. managed money net long
# ---------------------------------------------------------------------------
st.subheader("Gold price vs. managed money net positioning")
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(x=gold.index, y=gold, name="Gold ($/oz)",
                          line=dict(color="#d4af37", width=1.5)),
              secondary_y=False)
fig.add_trace(go.Scatter(x=cot.index, y=cot["mm_net_long"], name="MM net long (contracts)",
                          line=dict(color="#1f77b4", width=1.2)),
              secondary_y=True)
fig.update_yaxes(title_text="Gold ($/oz)",                secondary_y=False)
fig.update_yaxes(title_text="MM net long (contracts)",    secondary_y=True)
fig.update_layout(height=440, margin=dict(l=10, r=10, t=10, b=10),
                  legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Chart 2: Long vs short stack
# ---------------------------------------------------------------------------
st.subheader("Managed money: longs vs. shorts")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=cot.index, y=cot["m_money_positions_long_all"],
                           name="Longs", fill="tozeroy",
                           line=dict(color="#2ca02c", width=0)))
fig2.add_trace(go.Scatter(x=cot.index, y=-cot["m_money_positions_short_all"],
                           name="Shorts", fill="tozeroy",
                           line=dict(color="#d62728", width=0)))
fig2.add_trace(go.Scatter(x=cot.index, y=cot["mm_net_long"], name="Net long",
                           line=dict(color="black", width=1.5)))
fig2.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                   yaxis_title="Contracts", legend=dict(orientation="h"))
st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Chart 3: Net positioning by category (commercials / swap dealers / MM)
# ---------------------------------------------------------------------------
st.subheader("Net positioning by trader category")
fig3 = go.Figure()
for col, name, color in [
    ("mm_net_long",   "Managed money",        "#1f77b4"),
    ("comm_net_long", "Producers/Commercials", "#ff7f0e"),
    ("swap_net_long", "Swap dealers",          "#9467bd"),
]:
    if col in cot.columns:
        fig3.add_trace(go.Scatter(x=cot.index, y=cot[col], name=name,
                                   line=dict(color=color, width=1.2)))
fig3.add_hline(y=0, line_dash="dash", line_color="grey")
fig3.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                   yaxis_title="Net long (contracts)", legend=dict(orientation="h"))
st.plotly_chart(fig3, use_container_width=True)

# ---------------------------------------------------------------------------
# GLD snapshot
# ---------------------------------------------------------------------------
st.subheader("GLD ETF snapshot")
snap = get_etf_snapshot("GLD")
if snap:
    s1, s2, s3, s4 = st.columns(4)
    aum = snap.get("aum_usd")
    s1.metric("AUM", f"${aum/1e9:.2f}B" if aum else "—")
    s2.metric("NAV", f"${snap.get('nav'):.2f}" if snap.get("nav") else "—")
    s3.metric("Expense ratio", f"{snap.get('expense')*100:.2f}%"
              if snap.get("expense") else "—")
    s4.metric("YTD return", f"{snap.get('ytd_return')*100:+.1f}%"
              if snap.get("ytd_return") is not None else "—")
    st.caption(snap.get("name", ""))
else:
    st.info("Snapshot unavailable.")

with st.expander("How to read this", expanded=False):
    st.markdown("""
- **Managed money (MM)** are hedge funds and CTAs — the speculative crowd. Their net positioning leads price *and* lags it: they pile in on trends and unwind on reversals.
- **Net long > 80th percentile** = crowded long. Bullish exhaustion risk; gentle pullbacks can cascade.
- **Net long < 20th percentile** = washed out. Often a high-quality contrarian buy zone, especially with price stable.
- **Producers/commercials** are gold miners hedging output — they are *structurally short*. Their net short rising sharply often coincides with price tops.
- **Swap dealers** typically take the other side of MM flow.
- The chart of MM net long against price often shows correlation > 0.7 — useful sanity check that the speculative crowd is paying attention.
""")
