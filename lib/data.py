"""Cached data fetchers for the gold dashboard.

All functions are decorated with `st.cache_data(ttl=...)` so that:
- intraday price calls refresh every 5 min
- macro/FRED series refresh every 6 h
- COT-style weekly data refreshes every 24 h

This keeps the dashboard responsive without hammering external APIs.
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# Ticker registry — single source of truth
# ---------------------------------------------------------------------------
TICKERS = {
    # Gold core
    "gold_futures":   "GC=F",
    "silver_futures": "SI=F",
    "gld":            "GLD",
    "iau":            "IAU",
    "gdx":            "GDX",
    "gdxj":           "GDXJ",
    # Cross-asset
    "wti":            "CL=F",
    "copper":         "HG=F",
    "btc":            "BTC-USD",
    "spx":            "^GSPC",
    "vix":            "^VIX",
    "gvz":            "^GVZ",
    "dxy":            "DX-Y.NYB",
    # Yields (CBOE-quoted, divide by 10 to get %)
    "us10y":          "^TNX",
    "us5y":           "^FVX",
    "us2y":           "^IRX",  # actually 13-week T-bill, used as front-end proxy
    # FX
    "eurusd":         "EURUSD=X",
    "usdjpy":         "JPY=X",
    "usdcny":         "CNY=X",
}

FRED_SERIES = {
    "real_10y":       "DFII10",   # 10Y TIPS yield (real)
    "real_5y":        "DFII5",
    "breakeven_10y":  "T10YIE",
    "nominal_10y":    "DGS10",
    "nominal_2y":     "DGS2",
    "fed_funds":      "DFF",
    "cpi":            "CPIAUCSL",
    "core_cpi":       "CPILFESL",
    "core_pce":       "PCEPILFE",
    "m2":             "M2SL",
    "unemployment":   "UNRATE",
    "nfp":            "PAYEMS",
}


# ---------------------------------------------------------------------------
# yfinance fetchers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_prices(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """Return OHLCV history for a single ticker. Empty DF on failure."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        if df.empty:
            return df
        df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_close_panel(tickers: dict[str, str], period: str = "2y") -> pd.DataFrame:
    """Return a wide DF of closing prices indexed by date, columns = friendly names."""
    cols = {}
    for name, sym in tickers.items():
        df = get_prices(sym, period=period)
        if not df.empty:
            cols[name] = df["Close"]
    if not cols:
        return pd.DataFrame()
    panel = pd.concat(cols, axis=1)
    return panel


@st.cache_data(ttl=300, show_spinner=False)
def get_last_price(ticker: str) -> tuple[float, float]:
    """Return (last_close, prev_close) for a quick header tile."""
    df = get_prices(ticker, period="10d")
    if df.empty or len(df) < 2:
        return (float("nan"), float("nan"))
    return (float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2]))


# ---------------------------------------------------------------------------
# FRED fetcher (uses public CSV endpoint, no API key required)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=21600, show_spinner=False)  # 6h
def get_fred_series(series_id: str, years: int = 5) -> pd.Series:
    """Pull a FRED series via the no-auth CSV endpoint."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().set_index("date")["value"]
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
        return df[df.index >= cutoff].rename(series_id)
    except Exception:
        return pd.Series(dtype=float, name=series_id)


@st.cache_data(ttl=21600, show_spinner=False)
def get_fred_panel(series_map: dict[str, str], years: int = 5) -> pd.DataFrame:
    """Wide panel of FRED series, columns = friendly names."""
    cols = {}
    for name, sid in series_map.items():
        s = get_fred_series(sid, years=years)
        if not s.empty:
            cols[name] = s
    if not cols:
        return pd.DataFrame()
    return pd.concat(cols, axis=1).sort_index().ffill()


# ---------------------------------------------------------------------------
# GLD-spot conversion (uses our existing module)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_conversion_model(years: int = 5) -> dict:
    """Fit the GLD/spot ratio model once per hour."""
    from gld_converter import fetch_data, fit_decay_model
    df = fetch_data(years=years)
    return fit_decay_model(df)


def gld_to_spot(gld: float, model: dict, when=None) -> float:
    from gld_converter import gld_to_spot as _g2s
    return _g2s(gld, model, when=when)


def spot_to_gld(spot: float, model: dict, when=None) -> float:
    from gld_converter import spot_to_gld as _s2g
    return _s2g(spot, model, when=when)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def pct_change(curr: float, prev: float) -> float:
    if prev == 0 or np.isnan(prev) or np.isnan(curr):
        return float("nan")
    return (curr / prev - 1) * 100


def fmt_money(x: float, dp: int = 2) -> str:
    if np.isnan(x):
        return "—"
    return f"${x:,.{dp}f}"


def fmt_pct(x: float, dp: int = 2) -> str:
    if np.isnan(x):
        return "—"
    return f"{x:+.{dp}f}%"


# ---------------------------------------------------------------------------
# CFTC Commitments of Traders (disaggregated, futures-only)
# Public Socrata endpoint, no key required.
# Gold contract code: 088691 (COMEX gold)
# ---------------------------------------------------------------------------
CFTC_GOLD_CODE = "088691"
CFTC_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"


@st.cache_data(ttl=86400, show_spinner=False)  # 24h: COT updates weekly
def get_cftc_cot(years: int = 5, contract_code: str = CFTC_GOLD_CODE) -> pd.DataFrame:
    """Pull weekly COT history from CFTC Socrata API.

    Returns a DataFrame indexed by report date with columns for managed
    money, producer/merchant (commercials), swap dealers, and other reportables.
    """
    params = {
        "cftc_contract_market_code": contract_code,
        "$limit": 600,  # ~12 years of weekly reports
        "$order": "report_date_as_yyyy_mm_dd DESC",
    }
    try:
        r = requests.get(CFTC_URL, params=params, timeout=20)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
    df = df.set_index("date").sort_index()

    num_cols = [c for c in df.columns if any(k in c for k in [
        "positions", "open_interest", "traders", "concentration"
    ])]
    df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")

    # Field-name resolver: Socrata occasionally emits double-underscore names.
    def _col(name: str) -> str:
        if name in df.columns:
            return name
        alt = name.replace("swap_", "swap__")
        return alt if alt in df.columns else name  # may KeyError downstream — caught below

    derived = {}
    try:
        derived["mm_net_long"]   = df[_col("m_money_positions_long_all")] - df[_col("m_money_positions_short_all")]
        derived["comm_net_long"] = df[_col("prod_merc_positions_long")]   - df[_col("prod_merc_positions_short")]
        derived["swap_net_long"] = df[_col("swap_positions_long_all")]    - df[_col("swap_positions_short_all")]
        derived["mm_long_pct"]   = df[_col("m_money_positions_long_all")]  / df["open_interest_all"] * 100
        derived["mm_short_pct"]  = df[_col("m_money_positions_short_all")] / df["open_interest_all"] * 100
    except KeyError:
        # Schema drift — return raw frame so the page can still show OI etc.
        pass
    df = pd.concat([df, pd.DataFrame(derived, index=df.index)], axis=1)

    cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
    return df[df.index >= cutoff]


# ---------------------------------------------------------------------------
# Gold futures curve (front month + deferreds)
# ---------------------------------------------------------------------------
# CME gold contract month codes: G=Feb J=Apr M=Jun Q=Aug V=Oct Z=Dec
# Active months are mostly Feb/Apr/Jun/Aug/Oct/Dec.
GOLD_CURVE_CONTRACTS = [
    ("GC=F",       "Front (cont.)"),
    ("GCM26.CMX",  "Jun 2026"),
    ("GCQ26.CMX",  "Aug 2026"),
    ("GCV26.CMX",  "Oct 2026"),
    ("GCZ26.CMX",  "Dec 2026"),
    ("GCG27.CMX",  "Feb 2027"),
    ("GCJ27.CMX",  "Apr 2027"),
    ("GCM27.CMX",  "Jun 2027"),
    ("GCZ27.CMX",  "Dec 2027"),
    ("GCZ28.CMX",  "Dec 2028"),
]


@st.cache_data(ttl=900, show_spinner=False)
def get_futures_curve() -> pd.DataFrame:
    """Return latest closes for the gold futures curve, with maturity tags."""
    rows = []
    for sym, label in GOLD_CURVE_CONTRACTS:
        df = get_prices(sym, period="5d")
        if df.empty:
            continue
        rows.append({
            "symbol": sym,
            "label": label,
            "close": float(df["Close"].iloc[-1]),
            "date":  df.index[-1],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# FOMC meeting dates (recent + scheduled). Manually maintained.
# Source: federalreserve.gov/monetarypolicy/fomccalendars.htm
# ---------------------------------------------------------------------------
FOMC_DATES = [
    "2018-01-31","2018-03-21","2018-05-02","2018-06-13","2018-08-01","2018-09-26","2018-11-08","2018-12-19",
    "2019-01-30","2019-03-20","2019-05-01","2019-06-19","2019-07-31","2019-09-18","2019-10-30","2019-12-11",
    "2020-01-29","2020-03-03","2020-03-15","2020-04-29","2020-06-10","2020-07-29","2020-09-16","2020-11-05","2020-12-16",
    "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
    "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
    "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
    "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
    "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
    "2026-01-28","2026-03-18","2026-04-29","2026-06-17","2026-07-29","2026-09-16","2026-10-28","2026-12-09",
]


@st.cache_data(ttl=86400, show_spinner=False)
def get_fomc_dates() -> pd.DatetimeIndex:
    return pd.to_datetime(FOMC_DATES)


# ---------------------------------------------------------------------------
# GLD snapshot info (current AUM, shares, fund metrics from yfinance)
# ---------------------------------------------------------------------------
_KNOWN_EXPENSE = {"GLD": 0.0040, "IAU": 0.0025, "GDX": 0.0051, "GDXJ": 0.0052}


@st.cache_data(ttl=3600, show_spinner=False)
def get_etf_snapshot(ticker: str = "GLD") -> dict:
    """Return current AUM, NAV, expense, YTD from yfinance.

    yfinance returns YTD as a percent in some builds and a fraction in others;
    we normalise to a fraction here. Expense ratio is occasionally None for
    commodity ETFs — fallback to known-good values.
    """
    try:
        info = yf.Ticker(ticker).get_info()
    except Exception:
        return {}
    ytd = info.get("ytdReturn")
    if ytd is not None and abs(ytd) > 1.5:  # clearly a percent, not a fraction
        ytd = ytd / 100.0
    expense = info.get("annualReportExpenseRatio")
    if expense is None:
        expense = _KNOWN_EXPENSE.get(ticker)
    return {
        "name":       info.get("longName") or info.get("shortName"),
        "aum_usd":    info.get("totalAssets"),
        "nav":        info.get("navPrice"),
        "expense":    expense,
        "ytd_return": ytd,
        "category":   info.get("category"),
    }
