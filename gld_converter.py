"""
GLD <-> Gold Spot price converter, with model fitting and backtest.

Why this exists
---------------
GLD does not equal "gold spot / 10". Each share is backed by a slowly
shrinking number of ounces (the 0.40%/yr expense ratio is paid by selling
gold), so the Spot/GLD ratio drifts upward by ~0.4% per year. A naive fixed
divisor accumulates error. This script fits the empirical ratio over real
history and produces a precise, time-aware conversion.

Data sources (free):
  - GLD     : SPDR Gold Trust ETF (NYSE close)
  - GC=F    : COMEX gold futures front month (closest free spot proxy)

Note: GC=F trades at a small cost-of-carry premium to true LBMA spot
(typically 0.1-0.5%). The fitted ratio absorbs this; if you swap in true
spot data, refit and the constant term will shift slightly.

Usage:
  python gld_converter.py --gld 424.38                # GLD -> spot
  python gld_converter.py --spot 4637                 # spot -> GLD
  python gld_converter.py --backtest                  # show model accuracy
  python gld_converter.py --gld 424 --backtest        # both
"""
import sys
import io
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

GLD_TICKER = "GLD"
SPOT_TICKER = "GC=F"
CACHE_FILE = Path(__file__).parent / "gld_spot_cache.csv"


def fetch_data(years: int = 5, use_cache: bool = True) -> pd.DataFrame:
    """Return a DataFrame indexed by date with columns GLD, SPOT, ratio."""
    if use_cache and CACHE_FILE.exists():
        df = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
        last = df.index[-1].date()
        if (datetime.now().date() - last).days < 1:
            return df
    gld = yf.Ticker(GLD_TICKER).history(period=f"{years}y")["Close"].rename("GLD")
    spot = yf.Ticker(SPOT_TICKER).history(period=f"{years}y")["Close"].rename("SPOT")
    df = pd.concat([gld, spot], axis=1).dropna()
    df.index = df.index.tz_localize(None)
    df["ratio"] = df["SPOT"] / df["GLD"]
    df.to_csv(CACHE_FILE)
    return df


def fit_decay_model(df: pd.DataFrame) -> dict:
    """Fit log(ratio_t) = a + b * t_days.

    The ratio drifts up exponentially because GLD's per-share gold backing
    decays at ~0.40%/yr. Linear regression on log(ratio) recovers that drift
    plus the average level (which absorbs futures basis).
    """
    t = (df.index - df.index[0]).days.values.astype(float)
    y = np.log(df["ratio"].values)
    b, a = np.polyfit(t, y, 1)
    annual_drift_pct = (np.exp(b * 365) - 1) * 100
    residuals = y - (a + b * t)
    return {
        "a": float(a),
        "b": float(b),
        "t0": df.index[0],
        "annual_drift_pct": float(annual_drift_pct),
        "residual_std": float(residuals.std()),
    }


def predict_ratio(model: dict, when=None) -> float:
    when = pd.Timestamp(when or datetime.now()).tz_localize(None) if not isinstance(when, pd.Timestamp) else when
    if when.tz is not None:
        when = when.tz_localize(None)
    t_days = (when - model["t0"]).days
    return float(np.exp(model["a"] + model["b"] * t_days))


def gld_to_spot(gld_price: float, model: dict, when=None) -> float:
    return gld_price * predict_ratio(model, when)


def spot_to_gld(spot_price: float, model: dict, when=None) -> float:
    return spot_price / predict_ratio(model, when)


def _metrics(pred: pd.Series, actual: pd.Series) -> dict:
    err = (pred - actual).dropna()
    actual = actual.loc[err.index]
    return {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err ** 2))),
        "MAPE_%": float(np.mean(np.abs(err / actual)) * 100),
        "max_abs_err": float(np.max(np.abs(err))),
        "n": int(len(err)),
    }


def backtest(df: pd.DataFrame, train_frac: float = 0.7) -> dict:
    """Compare three converters: constant ratio, fitted decay, rolling mean."""
    cut = int(len(df) * train_frac)
    train, test = df.iloc[:cut], df.iloc[cut:]

    const_ratio = float(train["ratio"].mean())
    pred_const = test["GLD"] * const_ratio

    model = fit_decay_model(train)
    test_t = (test.index - model["t0"]).days.values.astype(float)
    pred_decay = test["GLD"].values * np.exp(model["a"] + model["b"] * test_t)
    pred_decay = pd.Series(pred_decay, index=test.index)

    rolling_ratio = df["ratio"].rolling(60).mean().shift(1)
    pred_roll = test["GLD"] * rolling_ratio.loc[test.index]

    actual = test["SPOT"]
    return {
        "train_period": f"{train.index[0].date()} -> {train.index[-1].date()} ({len(train)} rows)",
        "test_period":  f"{test.index[0].date()} -> {test.index[-1].date()} ({len(test)} rows)",
        "constant_ratio_value": const_ratio,
        "fitted_annual_drift_pct": model["annual_drift_pct"],
        "models": {
            "constant_ratio": _metrics(pred_const, actual),
            "time_decay":     _metrics(pred_decay, actual),
            "rolling_60d":    _metrics(pred_roll, actual),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="GLD <-> Gold spot converter")
    ap.add_argument("--gld", type=float, help="GLD price ($/share) -> implied spot")
    ap.add_argument("--spot", type=float, help="Spot price ($/oz) -> implied GLD")
    ap.add_argument("--backtest", action="store_true", help="Print backtest metrics")
    ap.add_argument("--years", type=int, default=5, help="Years of history to fit on")
    ap.add_argument("--no-cache", action="store_true", help="Force refresh from network")
    args = ap.parse_args()

    df = fetch_data(years=args.years, use_cache=not args.no_cache)
    model = fit_decay_model(df)
    fitted_today = predict_ratio(model)
    spot_today = float(df["ratio"].iloc[-1])

    print(f"History:        {df.index[0].date()} -> {df.index[-1].date()}  ({len(df)} trading days)")
    print(f"Fitted model:   ratio(t) = exp({model['a']:.6f} + {model['b']:.3e} * t_days)")
    print(f"Annual drift:   {model['annual_drift_pct']:+.3f}%/yr  (theoretical from expense ratio: ~+0.40%)")
    print(f"Residual stdev: {model['residual_std']*100:.3f}% (typical mispricing of model vs spot)")
    print(f"Ratio today (model): {fitted_today:.4f}")
    print(f"Ratio today (spot):  {spot_today:.4f}")
    print()

    if args.gld is not None:
        s = gld_to_spot(args.gld, model)
        print(f"GLD  ${args.gld:7.2f}/share  ->  Spot  ${s:8.2f}/oz")
    if args.spot is not None:
        g = spot_to_gld(args.spot, model)
        print(f"Spot ${args.spot:7.2f}/oz    ->  GLD   ${g:8.2f}/share")

    if args.backtest:
        print("\n=== Walk-forward backtest (70/30 split) ===")
        res = backtest(df)
        print(f"Train: {res['train_period']}")
        print(f"Test:  {res['test_period']}")
        print(f"Train constant ratio: {res['constant_ratio_value']:.4f}")
        print(f"Train fitted drift:   {res['fitted_annual_drift_pct']:+.3f}%/yr")
        print()
        print(f"{'Model':<18} {'MAE ($)':>10} {'RMSE ($)':>10} {'MAPE (%)':>10} {'MaxErr':>10}")
        for name, m in res["models"].items():
            print(f"{name:<18} {m['MAE']:>10.2f} {m['RMSE']:>10.2f} {m['MAPE_%']:>10.3f} {m['max_abs_err']:>10.2f}")


if __name__ == "__main__":
    main()
