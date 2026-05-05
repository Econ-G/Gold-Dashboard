"""Technical indicators implemented in pure pandas/numpy (no TA-Lib dep)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    diff = s.diff()
    up = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(s, fast) - ema(s, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = s.rolling(n).mean()
    sd = s.rolling(n).std()
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range. df must have High, Low, Close."""
    h, l, c = df["High"], df["Low"], df["Close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def realized_vol(s: pd.Series, n: int = 30, annualize: int = 252) -> float:
    return float(s.pct_change().tail(n).std() * np.sqrt(annualize))


def realized_vol_series(s: pd.Series, n: int = 30, annualize: int = 252) -> pd.Series:
    return s.pct_change().rolling(n).std() * np.sqrt(annualize)


def rolling_corr(a: pd.Series, b: pd.Series, n: int = 60) -> pd.Series:
    return a.pct_change().rolling(n).corr(b.pct_change())


def monthly_returns_matrix(close: pd.Series) -> pd.DataFrame:
    """Pivot of monthly returns: rows = year, cols = month."""
    m = close.resample("ME").last().pct_change().dropna() * 100
    df = pd.DataFrame({"year": m.index.year, "month": m.index.month, "ret": m.values})
    return df.pivot(index="year", columns="month", values="ret")


def find_pivots(s: pd.Series, window: int = 10) -> tuple[pd.Series, pd.Series]:
    """Find pivot highs/lows: a point is a pivot high if it is the strict max
    over [i-window, i+window]. Returns (highs, lows) as Series of pivot prices
    aligned to the input index, NaN elsewhere.
    """
    n = len(s)
    highs = pd.Series(np.nan, index=s.index)
    lows  = pd.Series(np.nan, index=s.index)
    arr = s.values
    for i in range(window, n - window):
        seg = arr[i - window:i + window + 1]
        if arr[i] == seg.max() and (seg == arr[i]).sum() == 1:
            highs.iloc[i] = arr[i]
        if arr[i] == seg.min() and (seg == arr[i]).sum() == 1:
            lows.iloc[i] = arr[i]
    return highs, lows


def support_resistance_levels(s: pd.Series, window: int = 10, n_levels: int = 5,
                               tolerance: float = 0.015) -> dict:
    """Cluster recent pivots into support/resistance levels.

    `tolerance` = fraction of price within which two pivots are considered
    the same level (1.5% default). Returns dict with 'support' and 'resistance'
    lists, each containing (price, n_touches) tuples sorted by recency value.
    """
    highs, lows = find_pivots(s, window)
    last_price = float(s.iloc[-1])

    def _cluster(pivots: pd.Series, side: str) -> list[tuple[float, int]]:
        pts = pivots.dropna().values
        if len(pts) == 0:
            return []
        clusters = []
        for p in sorted(pts):
            placed = False
            for cl in clusters:
                if abs(p - cl["mean"]) / cl["mean"] <= tolerance:
                    cl["values"].append(p)
                    cl["mean"] = sum(cl["values"]) / len(cl["values"])
                    placed = True
                    break
            if not placed:
                clusters.append({"values": [p], "mean": p})
        # Filter to relevant side and sort by closeness to current price
        result = []
        for cl in clusters:
            price = cl["mean"]
            touches = len(cl["values"])
            if side == "support" and price < last_price:
                result.append((price, touches))
            elif side == "resistance" and price > last_price:
                result.append((price, touches))
        # Sort: closest to current price first, ties broken by touch count
        result.sort(key=lambda x: abs(x[0] - last_price))
        return result[:n_levels]

    return {
        "support":    _cluster(lows,  "support"),
        "resistance": _cluster(highs, "resistance"),
    }


def fomc_window_returns(close: pd.Series, fomc_dates: pd.DatetimeIndex,
                        pre_days: int = 1, post_days: int = 1) -> pd.DataFrame:
    """For each FOMC date, compute return over the [-pre_days, +post_days] window."""
    rows = []
    for d in fomc_dates:
        d = pd.Timestamp(d).normalize()
        # Find the closest trading day
        idx = close.index
        if d not in idx:
            # Snap to next available date
            future = idx[idx >= d]
            if len(future) == 0:
                continue
            d = future[0]
        try:
            i = idx.get_loc(d)
        except KeyError:
            continue
        if i - pre_days < 0 or i + post_days >= len(idx):
            continue
        p_before = close.iloc[i - pre_days]
        p_at     = close.iloc[i]
        p_after  = close.iloc[i + post_days]
        rows.append({
            "date":      d,
            "pre_ret":   (p_at / p_before - 1) * 100,
            "post_ret":  (p_after / p_at - 1) * 100,
            "total_ret": (p_after / p_before - 1) * 100,
        })
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()
