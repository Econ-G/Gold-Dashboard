"""Seasonality analytics: monthly and day-of-week return distributions."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import TICKERS, get_prices
from lib.indicators import monthly_returns_matrix

st.set_page_config(page_title="Seasonality", layout="wide")
st.title("Seasonality")
st.caption("Gold has well-known seasonal patterns — Aug–Oct strength tied to Indian wedding season "
           "and Chinese New Year demand into Jan/Feb. This page quantifies them on real data.")

instrument = st.selectbox(
    "Instrument",
    ["gold_futures", "gld", "silver_futures"],
    format_func=lambda k: f"{k}  ({TICKERS[k]})",
)
years_history = st.slider("Years of history", 5, 25, 15)

df = get_prices(TICKERS[instrument], period=f"{years_history}y")
if df.empty:
    st.warning("No data.")
    st.stop()
close = df["Close"]

# ---- Monthly heatmap ----
mat = monthly_returns_matrix(close)
mat = mat.sort_index(ascending=False)  # newest year on top

st.subheader("Monthly return heatmap (%)")
fig = go.Figure(data=go.Heatmap(
    z=mat.values,
    x=[pd.Timestamp(2000, m, 1).strftime("%b") for m in mat.columns],
    y=mat.index.astype(str),
    colorscale="RdYlGn",
    zmid=0,
    text=np.round(mat.values, 1),
    texttemplate="%{text}",
    textfont=dict(size=10),
    colorbar=dict(title="%"),
))
fig.update_layout(height=max(360, 22 * len(mat) + 60), margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# ---- Aggregate stats ----
st.subheader("Average monthly return & win rate")
agg = pd.DataFrame({
    "Mean (%)":   mat.mean(),
    "Median (%)": mat.median(),
    "Win rate (%)": (mat > 0).mean() * 100,
    "Stdev (%)":  mat.std(),
    "Best (%)":   mat.max(),
    "Worst (%)":  mat.min(),
})
agg.index = [pd.Timestamp(2000, m, 1).strftime("%b") for m in agg.index]
st.dataframe(agg.style.format("{:+.2f}").background_gradient(subset=["Mean (%)", "Win rate (%)"], cmap="RdYlGn"),
             use_container_width=True)

# ---- Cumulative seasonality curve ----
st.subheader("Average path through the year")
daily = close.pct_change().dropna()
daily_df = daily.to_frame("ret")
daily_df["doy"] = daily_df.index.dayofyear
avg_by_doy = daily_df.groupby("doy")["ret"].mean()
cum_path = (1 + avg_by_doy).cumprod() - 1

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=cum_path.index, y=cum_path * 100, mode="lines",
                           line=dict(color="#d4af37", width=2), name="Avg cumulative"))
fig2.add_hline(y=0, line_dash="dash", line_color="grey")
fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                   xaxis_title="Day of year", yaxis_title="Average cumulative return (%)")
st.plotly_chart(fig2, use_container_width=True)

with st.expander("How to read this", expanded=False):
    st.markdown(f"""
- Read each row as one calendar year. Green = positive month, red = negative.
- **Aug–Oct** historically strong (Indian wedding/Diwali season into November).
- **Jan–Feb** often firm (Chinese New Year buying ahead of holiday).
- **Mar–Jun** mixed — typically the weakest stretch.
- The cumulative-path chart shows the *typical* shape of a year. A real year that diverges materially from this curve is information about regime.
- Sample size: {years_history} years. Increase years for more stable averages; decrease for recent-regime focus.
""")

# ---------------------------------------------------------------------------
# FOMC drift study
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("FOMC drift — gold around Fed meetings")
st.caption("How gold has moved in the trading days surrounding scheduled FOMC announcements. "
           "Persistent drift in either direction is exploitable; randomness means stand aside.")

from lib.data import get_fomc_dates
from lib.indicators import fomc_window_returns

fomc_dates = get_fomc_dates()
fomc_in_history = fomc_dates[(fomc_dates >= close.index[0]) & (fomc_dates <= close.index[-1])]
fomc_df = fomc_window_returns(close, fomc_in_history, pre_days=1, post_days=1)

if fomc_df.empty:
    st.info("Not enough overlap with FOMC calendar.")
else:
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Meetings analysed", f"{len(fomc_df)}")
    f2.metric("Avg pre-FOMC (1d)",  f"{fomc_df['pre_ret'].mean():+.2f}%",
              f"win {(fomc_df['pre_ret']>0).mean()*100:.0f}%")
    f3.metric("Avg post-FOMC (1d)", f"{fomc_df['post_ret'].mean():+.2f}%",
              f"win {(fomc_df['post_ret']>0).mean()*100:.0f}%")
    f4.metric("Avg total (-1 to +1)", f"{fomc_df['total_ret'].mean():+.2f}%",
              f"win {(fomc_df['total_ret']>0).mean()*100:.0f}%")

    fig_fomc = go.Figure()
    fig_fomc.add_trace(go.Bar(
        x=fomc_df.index, y=fomc_df["total_ret"],
        marker=dict(color=["#2ca02c" if v > 0 else "#d62728" for v in fomc_df["total_ret"]]),
        name="Total return (-1 to +1 days)",
    ))
    fig_fomc.add_hline(y=fomc_df["total_ret"].mean(), line_dash="dash",
                       line_color="black",
                       annotation_text=f"Mean {fomc_df['total_ret'].mean():+.2f}%")
    fig_fomc.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title="FOMC date",
                            yaxis_title="Total return (%)")
    st.plotly_chart(fig_fomc, use_container_width=True)

    with st.expander("How to read this", expanded=False):
        st.markdown("""
- **Pre-FOMC drift** has historically been positive across many assets (the "pre-FOMC drift" anomaly), but for gold it is regime-dependent — strongest when the market expects dovish surprises.
- A **win rate above 60%** with positive average is meaningful; a 50/50 split with small mean is noise.
- The post-FOMC reaction is dominated by surprise vs. expectations. The chart by itself can't distinguish "Fed dovish vs. hawkish" — pair with the dot-plot release schedule.
- Take-away: avoid initiating new directional gold positions in the 24h before an FOMC unless you have a specific view on the surprise direction.
""")

# ---------------------------------------------------------------------------
# Note about upcoming FOMC dates
# ---------------------------------------------------------------------------
upcoming = fomc_dates[fomc_dates > pd.Timestamp.now()][:3]
if len(upcoming) > 0:
    st.info("**Next FOMC meetings:** " + ", ".join(d.strftime("%Y-%m-%d") for d in upcoming))
