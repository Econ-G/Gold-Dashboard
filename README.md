# Gold Dashboard

A real-time gold-market analytics dashboard built with Streamlit. Integrates live price, macro, positioning, and options data across eight purpose-built sections, plus a custom **GLD-to-spot conversion model** that empirically recovers the ETF's expense-ratio drift from market data with **0.31% MAPE** on out-of-sample backtest.

> **Live demo:** _(deploy to Streamlit Community Cloud and paste the link here)_
>
> **Author:** Louis Zhao &middot; [LinkedIn](https://linkedin.com/in/louiswzhao) &middot; [Portfolio](https://econ-g.github.io/louis-portfolio)

---

## What it does

Eight integrated views of the gold market, all driven by live data with smart caching:

| Section | What's in it |
|---|---|
| **Overview** | KPI strip (gold, GLD, silver, DXY, BTC, VIX) · spot↔GLD conversion · 1-year candle chart · key macro tiles |
| **Price & Technicals** | Multi-instrument candles (gold/GLD/IAU/silver/GDX) · 20/50/200 SMAs · Bollinger · RSI · MACD · ATR · realized vol · auto-detected support/resistance via pivot clustering |
| **Macro Drivers** | Gold vs. 10Y real yield (inverted axis) · gold vs. DXY · 60-day rolling correlations vs. real yields, breakevens, DXY, nominals |
| **Cross-Asset Ratios** | Gold/silver · gold/oil · gold/copper · gold/SPX · gold/BTC · gold/GDX with 1-year z-scores |
| **Volatility** | Realized 30/60d vs. GVZ · GLD options IV smile · 5%-OTM put-call skew · IV term structure across all expiries · put/call open-interest ratio |
| **Seasonality** | Monthly return heatmap (15 years) · win-rate table · average path through the year · FOMC pre/post drift study (73 meetings) |
| **Positioning & Flows** | CFTC weekly Commitments of Traders (managed money / commercials / swap dealers) · GLD AUM/NAV/expense snapshot |
| **Futures Curve** | COMEX gold curve front month → Dec 2028 · contango/backwardation gauge · implied carry vs. fed funds |
| **GLD ↔ Spot Converter** | Two-way converter with forward-dated evaluation · ratio-drift chart · quick-reference table |

---

## Technical highlights

- **Empirical decay model.** Fitting `log(Spot/GLD) = a + b·t` to five years of daily closes recovers GLD's 0.40%/yr expense ratio as **+0.393%/yr** — a clean validation of the model from market data alone. Walk-forward backtest (70/30 split) gives **MAPE 0.31%**, ~3× better than a fixed-ratio baseline.
- **Free data only.** yfinance for prices, FRED's public CSV endpoint for macro (no API key), CFTC's Socrata endpoint for COT (no key). No paid feeds required.
- **Production-grade caching.** Tiered TTLs per data type (5 min for prices, 15 min for option chains and futures curve, 6 h for macro, 24 h for weekly COT). Manual cache-clear button in the sidebar.
- **Schema-resilient COT fetcher.** Handles a Socrata-side typo (`swap__positions_short_all` with double underscore) via a field-name resolver, so the fetcher does not silently drop categories.
- **Bug-fix-by-design.** Auto-refresh is implemented with a single meta-refresh tag — no extra dependency. ETF YTD returns are normalised across the two formats yfinance returns (some builds emit fractions, others percentages).
- **Modular layout.** `lib/data.py` for cached fetchers, `lib/indicators.py` for pure-pandas TA + S/R clustering + FOMC windows, one Streamlit page per analytical concern.

---

## Quick start

```bash
git clone https://github.com/Econ-G/Gold-Dashboard.git
cd Gold-Dashboard
pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501>.

No API keys required. First load takes 5–10 s; subsequent loads are sub-second within the cache window.

---

## Architecture

```
Gold-Dashboard/
├── app.py                              Overview / landing page
├── pages/
│   ├── 1_Price_and_Technicals.py
│   ├── 2_Macro_Drivers.py
│   ├── 3_Cross_Asset_Ratios.py
│   ├── 4_Volatility.py
│   ├── 5_Seasonality.py
│   ├── 6_GLD_Spot_Converter.py
│   ├── 7_Positioning_and_Flows.py
│   └── 8_Futures_Curve.py
├── lib/
│   ├── data.py                         cached fetchers (yfinance + FRED + CFTC)
│   └── indicators.py                   SMA/EMA/RSI/MACD/BB/ATR/vol + S/R + FOMC windows
├── gld_converter.py                    spot↔GLD model + CLI + backtest
├── CONVERSION.md                       conversion math, backtest, error sources
├── DASHBOARD.md                        architecture, page-by-page reference, roadmap
├── requirements.txt
└── LICENSE
```

---

## Data sources

| Source | Used for | Cost |
|---|---|---|
| [yfinance](https://github.com/ranaroussi/yfinance) | Prices, FX, ETFs, option chains, GVZ, ETF info | Free |
| [FRED](https://fred.stlouisfed.org/) (public CSV endpoint) | Real yields, breakevens, fed funds, CPI, PCE, M2 | Free, no key |
| [CFTC Socrata](https://publicreporting.cftc.gov/resource/72hh-3qpy.json) | Weekly Commitments of Traders | Free, no key |
| Federal Reserve calendar | FOMC meeting dates (hardcoded list) | Free |

---

## Documentation

- [`CONVERSION.md`](./CONVERSION.md) — full mathematical derivation of the GLD↔spot model, fit parameters, backtest tables, error-source breakdown, and the programmatic API.
- [`DASHBOARD.md`](./DASHBOARD.md) — architecture, page-by-page feature list, caching strategy, full data-source table, and Phase 3 roadmap.

---

## Roadmap

Shipped:

- Phase 1 — price/technicals, macro drivers, cross-asset ratios, volatility, seasonality, converter
- Phase 2 — CFTC positioning, futures curve, FOMC drift, IV term structure, put/call OI ratio, auto-detected S/R, ETF snapshot

In backlog (Phase 3):

- Live economic-calendar feed
- Shanghai Gold Exchange premium
- News sentiment via NewsAPI + LLM classifier
- Geopolitical Risk Index (Caldara-Iacoviello)
- WGC central-bank net-purchases panel
- India physical-demand proxies

---

## Disclaimer

This project is for **educational and analytical purposes only**. Nothing here is investment advice. Markets carry risk; verify all data independently before making any financial decision.

---

## License

MIT — see [`LICENSE`](./LICENSE).
