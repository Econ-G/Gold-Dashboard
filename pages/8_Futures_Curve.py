"""Gold futures curve: contango/backwardation and implied carry."""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import get_futures_curve, get_fred_series

st.set_page_config(page_title="Futures Curve", layout="wide")
st.title("Gold Futures Curve")
st.caption("COMEX gold prices across maturities. Gold is normally in **contango** "
           "(longer-dated > spot) because storage + interest exceed convenience yield. "
           "**Backwardation** is rare and signals physical-market tightness.")

curve = get_futures_curve()
if curve.empty or len(curve) < 2:
    st.warning("Curve data unavailable.")
    st.stop()

# Approximate days-to-expiry from contract month code
def _months_out(label: str) -> float:
    if "Front" in label:
        return 0.5  # ~ 2 weeks for the rolling front month
    try:
        # parse "Jun 2026" etc.
        parts = label.split()
        month = datetime.strptime(parts[0], "%b").month
        year = int(parts[1])
        target = datetime(year, month, 1)
        delta = target - datetime.now()
        return max(delta.days / 30.44, 0.1)
    except Exception:
        return np.nan


curve["months_out"] = curve["label"].map(_months_out)
front = curve.iloc[0]["close"]
curve["spread_$"]  = curve["close"] - front
curve["spread_%"]  = (curve["close"] / front - 1) * 100
# Implied annualized carry between front and each contract
curve["carry_pct_yr"] = curve.apply(
    lambda r: ((r["close"] / front) ** (12 / max(r["months_out"], 0.5)) - 1) * 100
              if r["months_out"] > 0.5 else np.nan,
    axis=1,
)

# ---- Header tiles ----
last_contract = curve.iloc[-1]
front_to_last_pct = (last_contract["close"] / front - 1) * 100
median_carry = float(curve["carry_pct_yr"].dropna().median())
fed_funds = get_fred_series("DFF", years=1)
ff_now = float(fed_funds.dropna().iloc[-1]) if fed_funds.dropna().size else np.nan
basis_vs_ff = median_carry - ff_now if not np.isnan(ff_now) else np.nan

state = "Contango" if median_carry > 0 else "Backwardation"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Front month", f"${front:,.2f}")
c2.metric(f"{last_contract['label']}", f"${last_contract['close']:,.2f}",
          f"{front_to_last_pct:+.2f}% vs front")
c3.metric("Curve state", state)
c4.metric("Median implied carry", f"{median_carry:+.2f}%/yr")
c5.metric("Carry − fed funds", f"{basis_vs_ff:+.2f}pp" if not np.isnan(basis_vs_ff) else "—",
          help="If carry < fed funds, the curve is below pure cost-of-carry — physical tightness or arb impediments.")

st.markdown("---")

# ---- The curve itself ----
st.subheader("Curve shape")
fig = go.Figure()
fig.add_trace(go.Scatter(x=curve["months_out"], y=curve["close"],
                         mode="lines+markers+text",
                         text=[f"${p:,.0f}" for p in curve["close"]],
                         textposition="top center",
                         line=dict(color="#d4af37", width=2.5),
                         marker=dict(size=10),
                         name="Gold curve"))
# Annotate contract labels under each point
for _, r in curve.iterrows():
    fig.add_annotation(x=r["months_out"], y=r["close"], text=r["label"],
                       showarrow=False, yshift=-30, font=dict(size=10, color="grey"))
fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=40),
                  xaxis_title="Months to expiry (approx)", yaxis_title="Price ($/oz)")
st.plotly_chart(fig, use_container_width=True)

# ---- Spread table ----
st.subheader("Spreads vs. front month")
display = curve[["label", "close", "spread_$", "spread_%", "carry_pct_yr"]].copy()
display.columns = ["Contract", "Price", "Spread $", "Spread %", "Implied carry %/yr"]
st.dataframe(
    display.style.format({
        "Price": "${:,.2f}",
        "Spread $": "{:+,.2f}",
        "Spread %": "{:+.2f}%",
        "Implied carry %/yr": "{:+.2f}%",
    }).background_gradient(subset=["Spread %"], cmap="RdYlGn"),
    use_container_width=True, hide_index=True,
)

with st.expander("How to read this", expanded=False):
    st.markdown("""
- **Contango** (the normal state): each later contract trades higher than the front. The slope ≈ short-term interest rate + storage − convenience yield. For gold this is usually 4–6%/yr in line with USD rates.
- **Backwardation**: front higher than deferreds. Rare in gold; signals **physical tightness** — refiners, central banks, or large delivery demand are bidding up immediate supply. Often coincides with price strength.
- **Carry minus fed funds**: pure financial arbitrage would push carry to ≈ fed funds. If carry is materially *below* fed funds, dealers are willing to lend gold cheaply — a hint of robust physical demand or balance-sheet constraints. If *above*, abundant supply.
- **Curve flattening over time** (compared with the previous read) often precedes a transition between regimes.
""")
