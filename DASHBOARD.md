# Gold Trading Dashboard

A Streamlit-based gold-market dashboard. Real prices via yfinance, real macro via FRED's public CSV endpoint (no API key required). Live data with smart caching; manual and auto refresh.

## Quick start

```bash
cd "C:/Users/rhino/OneDrive/桌面/Personal Project/Gold"
streamlit run app.py
```

The app will open at `http://localhost:8501`.

## Architecture

```
Gold/
├── app.py                              # Overview / landing page
├── pages/
│   ├── 1_Price_and_Technicals.py       # Candles + MAs/RSI/MACD/BB/ATR + auto S/R
│   ├── 2_Macro_Drivers.py              # Real yields, DXY, rolling correlations
│   ├── 3_Cross_Asset_Ratios.py         # Gold vs silver/oil/copper/SPX/BTC/GDX
│   ├── 4_Volatility.py                 # Realized vs GVZ + IV smile + term structure + put/call
│   ├── 5_Seasonality.py                # Monthly heatmap + day-of-year + FOMC drift
│   ├── 6_GLD_Spot_Converter.py         # UI on top of gld_converter.py
│   ├── 7_Positioning_and_Flows.py      # CFTC COT (managed money / commercials / swap) + GLD snapshot
│   └── 8_Futures_Curve.py              # Multi-contract curve + contango/backwardation gauge
├── lib/
│   ├── data.py                         # Cached fetchers (yfinance + FRED + CFTC + ETF info)
│   └── indicators.py                   # SMA/EMA/RSI/MACD/BB/ATR/vol + S/R clustering + FOMC windows
├── gld_converter.py                    # Spot↔GLD model (see CONVERSION.md)
├── CONVERSION.md                       # Conversion math + backtest doc
├── DASHBOARD.md                        # This document
└── requirements.txt
```

### Caching strategy

| Layer | TTL | Reason |
|---|---|---|
| Intraday prices (yfinance) | 5 min | Fresh enough for tactical use without rate-limiting |
| FRED macro series | 6 h | Updated daily at most |
| Conversion model fit | 1 h | Stable; refits only when ratio drift might shift |
| Option chains | 15 min | Quotes can move fast in vol events |
| CFTC COT | 24 h | Reports release weekly (Friday); daily refresh is plenty |
| Futures curve | 15 min | Liquid contracts, fast refresh |
| ETF snapshot (AUM/NAV) | 1 h | Updated end-of-day by issuer |

Sidebar **"Force refresh data"** clears all caches and reruns. The auto-refresh slider injects a meta-refresh tag (no extra dependency).

## Pages

### 1. Overview (`app.py`)

The landing page. At-a-glance health:

- **Top tiles:** Gold spot, GLD, silver, DXY, BTC, VIX (with 1-day % change)
- **Conversion strip:** live spot/GLD ratio, fitted drift, key spot levels (4,550 / 5,300) translated to GLD
- **Gold candle chart** with 50/200-day SMAs (1-year window)
- **Macro tiles:** 10Y real, 10Y nominal, 10Y breakeven, fed funds (with 1-month change in basis points)

### 2. Price & Technicals

The chartist page. User selects instrument (gold futures / GLD / IAU / silver / GDX / GDXJ) and history (6mo–10y).

- Header tiles: last price + 1-day %, RSI, ATR, 30-day realized vol, distance from 50/200 SMA
- 4-panel chart: candlesticks with optional Bollinger and 20/50/200 SMAs · volume · RSI(14) · MACD(12,26,9)
- "How to read this" expander explains conventional interpretation

### 3. Macro Drivers

Why is gold moving?

- **Gold vs. 10Y real yield** with the real-yield axis inverted (visualizes the inverse correlation directly)
- **Gold vs. DXY** with DXY inverted
- **Rolling 60-day correlation** of gold returns vs. real yield, breakeven, DXY, nominal yield
- Header tiles show 1-month basis-point changes for each driver

### 4. Cross-Asset Ratios

Six-panel grid: gold/silver, gold/oil, gold/copper, gold/SPX, gold/BTC, gold/GDX. Each tile shows current value plus 1-year z-score; |z|>2 flags a stretched ratio. Dotted line on each chart marks the 1-year mean.

### 5. Volatility

- **Realized (30/60d) vs GVZ** time series — spot the regime where options are cheap or expensive
- Live header tile shows the implied-realized spread in percentage points
- **GLD option chain IV smile** for any selected expiry (call vs put curves around spot)
- 5%-OTM put-call IV skew metric for a quick fear gauge

### 6. Seasonality

Quantitative seasonality on real history (5–25 years, user-selectable):

- **Monthly heatmap** — every year × every month, color-coded by return
- **Aggregate stats table** — mean, median, win rate, stdev, best/worst by calendar month
- **Average-path-through-year** chart — typical cumulative return shape over a calendar year

### 7. Positioning & Flows

CFTC weekly Commitments of Traders (disaggregated, futures-only) for COMEX gold (contract code 088691):

- **Header tiles:** managed-money net long with historical percentile, MM long/short as % of OI, total open interest
- **Gold price overlaid with managed-money net positioning** — visualises whether speculators are confirming or fading the trend
- **Long-vs-short stack** — separates the two sides; net line drawn on top
- **Net positioning by category** — managed money vs. producers/commercials vs. swap dealers (the latter two are typically the smart-money cohort)
- **GLD ETF snapshot** — AUM, NAV, expense ratio, YTD return

Data: CFTC public Socrata API (`publicreporting.cftc.gov/resource/72hh-3qpy.json`), no key required, ~600 weekly reports available.

### 8. Futures Curve

- **Curve chart** — front month through Dec 2028, prices and contract labels
- **Curve state header** — contango or backwardation, median implied annualized carry
- **Carry vs. fed funds** — if implied carry deviates significantly from short-term rates, it's a physical-tightness or arb-impediment signal
- **Spread table** — every contract's $/% spread vs. the front and implied annualized carry

### 9. GLD ↔ Spot Converter

UI wrapper on the model in `gld_converter.py`:

- Live spot, GLD, ratio header
- Two-way converter with **forward-dated evaluation** (important for option-expiry math — drift accumulates ~0.4%/yr)
- Quick-reference table: spot levels (3,500 → 6,000) → equivalent GLD
- Ratio-drift chart: actual daily ratio vs. fitted model line

## Data sources

| Source | Used for | License | Cost |
|---|---|---|---|
| yfinance | All prices, FX, ETF chains, option chains, GVZ, ETF info | yfinance terms | Free |
| FRED CSV (`fred.stlouisfed.org/graph/fredgraph.csv?id=…`) | Real yields, breakevens, fed funds, CPI/PCE/M2 | Public domain | Free, no key |
| CFTC Socrata (`publicreporting.cftc.gov/resource/72hh-3qpy.json`) | Weekly COT positioning | Public domain | Free, no key |
| Federal Reserve calendar | FOMC meeting dates (hardcoded list) | Public domain | Free |

Adding paid feeds (LBMA fixings, ICE MOVE, CFTC parsed COT) is a single function in `lib/data.py` away — same caching pattern.

## Performance

A cold load of the Overview page runs ~6–10 yfinance pulls plus 4 FRED pulls. Total: typically 5–10 s. Subsequent loads within the cache TTL are sub-second.

## Roadmap

Already shipped (Phase 1 of the metric inventory):

- [x] Price + technicals (candles, MAs, RSI, MACD, BB, ATR, RV)
- [x] Macro drivers (real yields, breakevens, DXY, fed funds, rolling correlations)
- [x] Cross-asset ratios with z-scores
- [x] Volatility (realized vs GVZ, IV smile, skew)
- [x] Seasonality (heatmap + average path)
- [x] GLD↔Spot converter
- [x] Auto-refresh and manual cache-clear

Phase 2 (Medium difficulty) — shipped:

- [x] CFTC COT positioning (managed money / commercials / swap dealers)
- [x] GLD AUM / NAV / expense / YTD snapshot
- [x] Futures curve with contango/backwardation gauge and implied carry
- [x] FOMC calendar + pre-FOMC drift study (1d before, 1d after, total)
- [x] IV term structure and put/call OI ratio across all GLD expiries
- [x] Auto-detected support/resistance levels from pivot clustering

Phase 3 candidates (Hard):

- [ ] Live economic calendar (Investing.com scrape or paid API)
- [ ] Shanghai Gold Exchange premium
- [ ] News sentiment (NewsAPI + LLM classifier)
- [ ] Geopolitical Risk Index (Caldara-Iacoviello CSV)
- [ ] WGC central-bank net purchases (quarterly bars)
- [ ] India physical demand proxies

## Maintenance log

| Date | Change |
|---|---|
| 2026-05-01 | Initial build: Phase 1 complete (6 pages + Overview, lib/data + lib/indicators, requirements.txt). Smoke-tested data layer (yfinance, FRED CSV, GVZ). All files compile clean. |
| 2026-05-01 | Phase 2 shipped: added pages 7 (Positioning & Flows) and 8 (Futures Curve); extended page 4 with IV term structure and put/call OI ratio across expiries; extended page 5 with FOMC pre/post-meeting drift study; added auto-detected pivot S/R to page 1. Added CFTC Socrata fetcher, futures-curve fetcher, FOMC date table, ETF snapshot helper, and pivot-clustering indicator. CFTC field-name resolver handles Socrata's double-underscore swap fields. Smoke-tested live: 157 weeks of COT history, 10 contracts on the curve, 73 FOMC dates, GLD AUM $155B. |
