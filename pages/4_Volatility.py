"""Volatility page: realized vs implied, GVZ, GLD options IV/skew."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.data import TICKERS, get_prices
from lib.indicators import realized_vol_series

st.set_page_config(page_title="Volatility", layout="wide")
st.title("Volatility")
st.caption("Compare realized to implied vol; identify regimes where options are cheap vs. expensive.")

period = st.selectbox("History", ["6mo", "1y", "2y", "5y"], index=2)

# ---- Realized vs implied ----
gld = get_prices(TICKERS["gld"], period=period)["Close"]
gvz = get_prices(TICKERS["gvz"], period=period)["Close"]
rv30 = realized_vol_series(gld, 30) * 100
rv60 = realized_vol_series(gld, 60) * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("Realized vol 30d (%)", f"{rv30.dropna().iloc[-1]:.1f}" if rv30.dropna().size else "—")
c2.metric("Realized vol 60d (%)", f"{rv60.dropna().iloc[-1]:.1f}" if rv60.dropna().size else "—")
c3.metric("GVZ (%)",              f"{gvz.dropna().iloc[-1]:.1f}"  if gvz.dropna().size else "—")
spread = (gvz.dropna().iloc[-1] - rv30.dropna().iloc[-1]) if (gvz.dropna().size and rv30.dropna().size) else np.nan
c4.metric("Implied − Realized (pp)", f"{spread:+.1f}" if not np.isnan(spread) else "—",
          help="Positive = options pricing in more vol than realized = expensive. Negative = cheap.")

fig = go.Figure()
fig.add_trace(go.Scatter(x=rv30.index, y=rv30, name="Realized 30d", line=dict(color="#1f77b4")))
fig.add_trace(go.Scatter(x=rv60.index, y=rv60, name="Realized 60d", line=dict(color="#9467bd", dash="dot")))
fig.add_trace(go.Scatter(x=gvz.index, y=gvz, name="GVZ (implied)", line=dict(color="#d62728")))
fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10),
                  yaxis_title="Annualized vol (%)", legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ---- GLD option chain snapshot ----
st.subheader("GLD options — IV by strike")

@st.cache_data(ttl=900, show_spinner=False)
def get_gld_chain(expiry: str) -> pd.DataFrame:
    try:
        oc = yf.Ticker("GLD").option_chain(expiry)
        calls = oc.calls.assign(side="call")
        puts  = oc.puts.assign(side="put")
        return pd.concat([calls, puts], ignore_index=True)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=900, show_spinner=False)
def get_gld_expiries() -> list[str]:
    try:
        return list(yf.Ticker("GLD").options)
    except Exception:
        return []

expiries = get_gld_expiries()
if expiries:
    expiry = st.selectbox("Expiry", expiries, index=min(5, len(expiries)-1))
    chain = get_gld_chain(expiry)
    if not chain.empty:
        spot = float(get_prices(TICKERS["gld"], period="5d")["Close"].iloc[-1])
        # Filter ±15% around spot
        lo, hi = spot * 0.85, spot * 1.15
        chain = chain[(chain["strike"] >= lo) & (chain["strike"] <= hi)]
        chain["iv_pct"] = chain["impliedVolatility"] * 100

        fig2 = go.Figure()
        for side, color in [("call", "#1f77b4"), ("put", "#d62728")]:
            sub = chain[chain["side"] == side].sort_values("strike")
            fig2.add_trace(go.Scatter(x=sub["strike"], y=sub["iv_pct"], mode="lines+markers",
                                       name=side, line=dict(color=color)))
        fig2.add_vline(x=spot, line_dash="dash", line_color="grey",
                       annotation_text=f"Spot {spot:.2f}")
        fig2.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10),
                           xaxis_title="Strike", yaxis_title="Implied vol (%)",
                           legend=dict(orientation="h"))
        st.plotly_chart(fig2, use_container_width=True)

        # Skew metric
        atm = chain.iloc[(chain["strike"] - spot).abs().argsort()].head(2)
        otm_put  = chain[(chain["side"] == "put")  & (chain["strike"] <= spot * 0.95)].sort_values("strike", ascending=False).head(1)
        otm_call = chain[(chain["side"] == "call") & (chain["strike"] >= spot * 1.05)].sort_values("strike", ascending=True).head(1)
        if len(otm_put) and len(otm_call):
            skew = otm_put["iv_pct"].iloc[0] - otm_call["iv_pct"].iloc[0]
            st.info(f"**5%-OTM put-call IV skew:** {skew:+.2f} pp  "
                    f"(positive = put protection more expensive = downside fear)")
    else:
        st.warning("Could not load chain.")
else:
    st.warning("No expiries returned.")

with st.expander("How to read this", expanded=False):
    st.markdown("""
- **GVZ above realized 30d** = options expensive vs. recent reality. Selling premium is favored, buying is harder.
- **GVZ below realized** = options cheap; buying calls/puts has tailwinds.
- **Positive put-call skew** = market paying up for downside protection (fear). Sometimes a contrarian-bullish signal.
- **Skew flattening** = complacency.
- IV smile typically lifts at far-OTM strikes — those wings are the lottery-ticket pricing.
""")

# ---------------------------------------------------------------------------
# IV term structure + put/call open-interest ratio across all expiries
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("IV term structure & put/call ratio across expiries")
st.caption("ATM implied vol by expiry shows how the market prices vol over time. "
           "Put/call ratio summarises hedging demand for each tenor.")

if expiries:
    rows = []
    spot = float(get_prices(TICKERS["gld"], period="5d")["Close"].iloc[-1])
    today = pd.Timestamp.now().normalize()
    for exp in expiries[:20]:  # limit to first 20 expiries to bound API load
        ch = get_gld_chain(exp)
        if ch.empty:
            continue
        calls = ch[ch["side"] == "call"]
        puts  = ch[ch["side"] == "put"]
        # ATM = closest-strike option
        atm_call = calls.iloc[(calls["strike"] - spot).abs().argsort()].head(1)
        atm_put  = puts.iloc[(puts["strike"] - spot).abs().argsort()].head(1)
        if atm_call.empty or atm_put.empty:
            continue
        atm_iv = (atm_call["impliedVolatility"].iloc[0] + atm_put["impliedVolatility"].iloc[0]) / 2
        oi_call = calls["openInterest"].fillna(0).sum()
        oi_put  = puts["openInterest"].fillna(0).sum()
        pcr = oi_put / oi_call if oi_call > 0 else np.nan
        dte = (pd.Timestamp(exp) - today).days
        rows.append({"expiry": exp, "dte": dte, "atm_iv_pct": atm_iv * 100, "pcr": pcr})

    if rows:
        ts = pd.DataFrame(rows).sort_values("dte")
        col_a, col_b = st.columns(2)
        with col_a:
            fig_ts = go.Figure()
            fig_ts.add_trace(go.Scatter(x=ts["dte"], y=ts["atm_iv_pct"],
                                         mode="lines+markers", name="ATM IV",
                                         line=dict(color="#1f77b4", width=2)))
            fig_ts.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                                  xaxis_title="Days to expiry",
                                  yaxis_title="ATM implied vol (%)")
            st.plotly_chart(fig_ts, use_container_width=True)
        with col_b:
            fig_pcr = go.Figure()
            fig_pcr.add_trace(go.Bar(x=ts["dte"], y=ts["pcr"],
                                      marker=dict(color=["#d62728" if v > 1 else "#2ca02c" for v in ts["pcr"]]),
                                      name="Put/Call OI ratio"))
            fig_pcr.add_hline(y=1, line_dash="dash", line_color="grey",
                              annotation_text="Balanced (1.0)")
            fig_pcr.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                                   xaxis_title="Days to expiry",
                                   yaxis_title="Open-interest put/call ratio")
            st.plotly_chart(fig_pcr, use_container_width=True)

        with st.expander("How to read these", expanded=False):
            st.markdown("""
- **Upward-sloping IV term structure** (longer expiries higher IV) = normal. Indicates expectation of more uncertainty further out.
- **Inverted term structure** (short-dated > long-dated) = an event is being priced into the front (data print, FOMC, geopolitical).
- **Put/call OI ratio > 1** = more puts outstanding than calls = hedging dominant. Common around earnings/macro events.
- **PCR < 0.6** = call-heavy = bullish positioning. Gold rarely trades this low; when it does, it's usually a momentum top sign.
- **PCR diverging across tenors** (e.g. front low, back high) suggests traders see near-term strength but back-end risk.
""")
    else:
        st.info("Could not extract IV term structure (not enough valid chains).")
