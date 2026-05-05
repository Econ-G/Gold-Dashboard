# GLD ↔ Gold Spot Conversion

A precise, time-aware converter between SPDR Gold Trust ETF (`GLD`) and gold spot price ($/oz). Companion to `gld_converter.py`.

## 1. Why a fixed divisor is wrong

The common rule of thumb is **"GLD ≈ gold spot ÷ 10"**. This was true at GLD's 2004 inception (each share was backed by exactly 1/10 oz of gold), but it accumulates error every year because of how the trust is structured:

- GLD has a **0.40% annual expense ratio**, paid by the trust *selling gold* to cover fees.
- This means each share is backed by slightly less gold every day.
- After ~21 years, each share is backed by roughly **0.0916 oz** instead of the original 0.1 oz.
- Therefore the **Spot/GLD ratio drifts upward** at ~0.40%/yr.

A fixed divisor of 10 would understate spot by **≈8% today**. The converter eliminates this by fitting the empirical drift from history.

## 2. The model

Let `ratio_t = Spot_t / GLD_t`. We fit:

```
log(ratio_t) = a + b · t_days
```

This is exponential growth (matches a constant-rate decay in gold-per-share). Two parameters:

- `a` — average level (absorbs futures-basis offset between `GC=F` and true LBMA spot)
- `b` — daily drift; converted to **annual drift = (e^(365·b) − 1)**

### Empirical fit (5 years of daily closes, 2021-05-03 → 2026-05-01)

| Parameter | Value | Meaning |
|---|---|---|
| `a` | 2.367848 | implies a base ratio ≈ 10.67 at the start of history |
| `b` | 1.074 × 10⁻⁵ | daily log-drift |
| **Annual drift** | **+0.393%/yr** | **matches GLD's 0.40% expense ratio almost exactly ✓** |
| Residual stdev | 0.332% | typical day-to-day noise around the fit |

The fitted annual drift recovering 0.39%/yr from purely empirical price data is strong evidence the model is structurally correct.

## 3. Backtest results

Walk-forward validation: fit on 2021-05 → 2024-10 (879 days), test on 2024-10 → 2026-05 (377 days). The model never sees the test set during fitting.

| Model | MAE ($/oz) | RMSE ($/oz) | MAPE (%) | Max error ($/oz) |
|---|---:|---:|---:|---:|
| Fixed mean ratio (baseline) | 37.95 | 42.76 | 1.017% | 127.86 |
| **Time-decay (this script)** | **11.91** | **18.50** | **0.312%** | 123.81 |
| Rolling 60-day mean | 12.35 | 18.91 | 0.322% | 119.80 |

**Takeaways:**

- The time-decay model cuts error by **~3×** vs. a fixed ratio.
- Typical conversion error: **±0.31%** (≈ ±$15/oz at current prices).
- Worst-case error (~$124) corresponds to single-day futures-basis dislocations during volatile sessions. These mean-revert within days.
- The 60-day rolling mean is nearly as good and is more reactive — useful as a sanity check, but it lags during sustained moves.

## 4. Sources of remaining error

| Source | Magnitude | Mitigation |
|---|---|---|
| `GC=F` futures basis vs. true spot (cost-of-carry) | 0.1–0.5% | Absorbed into `a`; replace `GC=F` with `XAUUSD` for tighter fit if available |
| GLD bid/ask + premium/discount to NAV | ±0.05% | Negligible; use mid prices |
| Time-of-day mismatch (NYSE close vs. 24h gold) | ±0.2% on volatile days | Use closes from same window |
| FOMC / CPI day dislocations | up to 1% intraday | Wait for re-convergence; do not trade the gap |

## 5. Usage

```bash
# GLD price -> implied spot
python gld_converter.py --gld 424.38

# Spot -> implied GLD
python gld_converter.py --spot 4637

# Both directions plus backtest report
python gld_converter.py --gld 424.38 --spot 4637 --backtest

# Force a fresh data pull (default uses 1-day cache)
python gld_converter.py --no-cache --backtest

# Use a longer history window
python gld_converter.py --years 10 --backtest
```

### Live example (2026-05-01)

```
GLD  $424.38/share  ->  Spot  $4,619.62/oz
Spot $4,637.00/oz   ->  GLD   $425.98/share
```

Compare to the simple "÷10.89" approximation (today's spot ratio): the model is more conservative because it weights the entire history, not just the latest noisy ratio. Both are within 0.4% — pick the model output for stability, the spot ratio for the *very* latest reading.

## 6. Maintenance

- **Re-run yearly.** The fitted drift will stay near 0.40%/yr unless GLD changes its expense ratio or there's a sponsor change.
- **Cache.** `gld_spot_cache.csv` is auto-refreshed when older than one day.
- **Upgrading the spot proxy.** `GC=F` is free but futures-based. For higher accuracy, swap to LBMA fixings or a paid spot feed by editing `SPOT_TICKER` in `gld_converter.py` and re-running. The fit will adjust automatically.

## 7. Programmatic use

```python
from gld_converter import fetch_data, fit_decay_model, gld_to_spot, spot_to_gld

df = fetch_data(years=5)
model = fit_decay_model(df)

print(gld_to_spot(424.38, model))           # implied spot today
print(spot_to_gld(4637, model))             # implied GLD today
print(gld_to_spot(450, model, when="2026-08-21"))   # for option expiry date
```

The `when=` argument is useful when pricing option payoffs: an Aug-2026 expiry should be evaluated using the ratio *at that future date*, accounting for accumulated drift.

## 8. Files

| File | Purpose |
|---|---|
| `gld_converter.py` | Converter, model fit, backtest, CLI |
| `gld_spot_cache.csv` | Auto-generated daily-close cache (regenerated when stale) |
| `CONVERSION.md` | This document |
