"""GLD <-> Spot converter — UI wrapper around gld_converter.py."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import TICKERS, get_prices, get_conversion_model, gld_to_spot, spot_to_gld

st.set_page_config(page_title="GLD ↔ Spot Converter", layout="wide")
st.title("GLD ↔ Gold Spot Converter")
st.caption("Built on the time-decay model fitted in `gld_converter.py`. "
           "See CONVERSION.md for the math and backtest.")

model = get_conversion_model()

# ---- Live ratio ----
gold_now = get_prices(TICKERS["gold_futures"], period="5d")["Close"].iloc[-1]
gld_now  = get_prices(TICKERS["gld"],          period="5d")["Close"].iloc[-1]
ratio_now = gold_now / gld_now

c1, c2, c3 = st.columns(3)
c1.metric("Live spot", f"${gold_now:,.2f}")
c2.metric("Live GLD",  f"${gld_now:,.2f}")
c3.metric("Live ratio", f"{ratio_now:.4f}", f"fitted {np.exp(model['a']):.4f} base")

st.markdown("---")

# ---- Two-way converter ----
left, right = st.columns(2)
with left:
    st.subheader("Spot → GLD")
    spot_in = st.number_input("Gold spot ($/oz)", value=float(gold_now), step=10.0, format="%.2f")
    when_l = st.date_input("Evaluation date", value=pd.Timestamp.now().date(), key="d_l")
    gld_out = spot_to_gld(spot_in, model, when=pd.Timestamp(when_l))
    st.metric("Implied GLD ($/share)", f"${gld_out:,.2f}")

with right:
    st.subheader("GLD → Spot")
    gld_in = st.number_input("GLD price ($/share)", value=float(gld_now), step=1.0, format="%.2f")
    when_r = st.date_input("Evaluation date", value=pd.Timestamp.now().date(), key="d_r")
    spot_out = gld_to_spot(gld_in, model, when=pd.Timestamp(when_r))
    st.metric("Implied spot ($/oz)", f"${spot_out:,.2f}")

st.markdown("---")

# ---- Quick reference table ----
st.subheader("Quick reference (today's drift-adjusted ratio)")
levels = [3500, 4000, 4250, 4500, 4637, 4750, 5000, 5250, 5300, 5500, 6000]
table = pd.DataFrame({
    "Spot ($/oz)": levels,
    "GLD ($/share)": [round(spot_to_gld(s, model), 2) for s in levels],
})
st.dataframe(table, use_container_width=True, hide_index=True)

st.markdown("---")

# ---- Ratio history with fitted line ----
st.subheader("Ratio drift: history vs. fitted")
from gld_converter import fetch_data
df_hist = fetch_data(years=5)
t_days = (df_hist.index - model["t0"]).days.values.astype(float)
fitted = np.exp(model["a"] + model["b"] * t_days)

fig = go.Figure()
fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist["ratio"], name="Spot / GLD (daily)",
                         line=dict(color="#888", width=1)))
fig.add_trace(go.Scatter(x=df_hist.index, y=fitted, name="Fitted decay model",
                         line=dict(color="#d4af37", width=2)))
fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                  yaxis_title="Spot / GLD", legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Annual drift recovered: **{model['annual_drift_pct']:+.3f}%/yr** "
    f"(theoretical from GLD's 0.40% expense ratio). "
    f"Residual stdev: {model['residual_std']*100:.2f}%."
)
