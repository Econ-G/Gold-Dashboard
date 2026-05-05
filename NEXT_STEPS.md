# Next Steps — Publicization & Future Work

State as of last session: Phase 1 + Phase 2 complete, all files compile clean, dashboard verified live at `localhost:8501`. Repository is **publication-ready**: `README.md`, `LICENSE`, `.gitignore`, `CONVERSION.md`, `DASHBOARD.md` all in place. Nothing else needs to be built before going public.

GitHub: **github.com/Econ-G/Gold-Dashboard** (target URL — repo not yet created).

---

## 1. Push to GitHub

### 1a. Create the empty repo on GitHub (web, ~30 sec)

Go to <https://github.com/new>:

- **Owner:** Econ-G
- **Repository name:** `Gold-Dashboard`
- **Public**
- **Do NOT** check any of "Add README", "Add .gitignore", or "Add license" — those exist locally already
- Click "Create repository"

### 1b. Verify git config (one-time, if not set)

```bash
git config --global user.name "Louis Zhao"
git config --global user.email "louis.zhao@mail.utoronto.ca"
```

### 1c. Initialize, commit, push (from project root)

```bash
cd "C:/Users/rhino/OneDrive/桌面/Personal Project/Gold"
git init
git add .
git commit -m "Initial commit: gold trading dashboard with positioning, futures curve, and conversion model"
git branch -M main
git remote add origin https://github.com/Econ-G/Gold-Dashboard.git
git push -u origin main
```

If GitHub asks for auth, use a personal access token (Settings → Developer settings → Personal access tokens → Fine-grained → "Only select repositories" → Gold-Dashboard → repo:write).

The `.gitignore` already excludes `gld_spot_cache.csv`, `__pycache__/`, and IDE metadata — first commit is clean.

---

## 2. Deploy to Streamlit Community Cloud (free, ~5 min)

1. Go to <https://share.streamlit.io>
2. Sign in with the **Econ-G** GitHub account
3. Click **"New app"**
4. Repo: `Econ-G/Gold-Dashboard`, branch: `main`, main file: `app.py`
5. Click **Deploy**. Build takes ~2 minutes.
6. Public URL will be `https://gold-dashboard-econ-g.streamlit.app` (or similar — Streamlit auto-generates).
7. Edit `README.md` line 7 to replace the placeholder with the real demo URL, commit, push. The deployed app rebuilds automatically.

If a yfinance call fails on the cloud build, it's typically a transient Yahoo block — wait 5 min and reboot the app from the Streamlit dashboard.

---

## 3. Capture a screenshot (3 min)

- Open the dashboard, navigate to the **Overview** page.
- Use Windows + Shift + S (Snipping Tool) to capture the full visible page.
- Save as `docs/screenshot_overview.png` in the repo.
- Add to README under the live-demo line:

  ```markdown
  ![Overview](docs/screenshot_overview.png)
  ```

A 10-second GIF (use [ScreenToGif](https://www.screentogif.com/)) showing a click-through Overview → Macro → Seasonality → Positioning is materially better than a static screenshot.

---

## 4. LinkedIn post template

> Built a gold trading dashboard in Python — eight integrated views (technicals, macro drivers, cross-asset ratios, options vol, seasonality, CFTC positioning, futures curve) plus a custom **GLD-to-spot conversion model** that empirically recovers the ETF's 0.40%/yr expense-ratio drift from market data alone, with 0.31% MAPE on out-of-sample backtest.
>
> Stack: Streamlit · Plotly · pandas · yfinance · FRED · CFTC public APIs.
>
> Live demo: <link>
> Code: https://github.com/Econ-G/Gold-Dashboard
>
> Open to feedback, especially from anyone in commodities or macro.

Pick **one** technical hook to lead with. Strongest options:

- "Recovered GLD's 0.40%/yr expense ratio from price data alone — 3× more accurate than a fixed conversion ratio"
- "Live CFTC positioning, IV term structure, and FOMC drift in one place — no API keys required"
- "Conversion model error: 0.31% MAPE on a walk-forward backtest"

---

## 5. Resume line

Place under "Projects" or "Personal Projects":

> **Gold Dashboard** — Streamlit application integrating live yfinance, FRED, and CFTC data across 8 analytical sections (technicals, macro drivers, options vol, seasonality, positioning, futures curve). Custom log-linear decay model recovers GLD's 0.40%/yr expense ratio from market data with 0.31% MAPE on out-of-sample backtest. *[live demo](link) · [github](https://github.com/Econ-G/Gold-Dashboard)*

---

## 6. Future work (Phase 3 backlog)

Pick whichever of these maps to a job you're interviewing for:

| Item | Difficulty | Why it's worth doing |
|---|---|---|
| Live economic calendar (Investing.com scrape or paid API) | Hard | Closes the macro-event loop — most-asked feature in a recruiter demo |
| Shanghai Gold Exchange premium | Hard | Differentiator; signals genuine domain knowledge of physical gold market |
| News sentiment (NewsAPI + LLM classifier) | Hard | Lets you talk about LLM integration on top of the quant work — strong for hybrid roles |
| Geopolitical Risk Index (Caldara-Iacoviello CSV) | Medium | Free CSV; pretty time-series chart; quick win |
| WGC central-bank net-purchases panel | Medium | Quarterly only; structural-demand narrative |
| India physical-demand proxies (jewelry import data) | Hard | Differentiator; explains the seasonality directly |
| FRED economic-release dashboard (CPI / PCE / NFP / ISM cards) | Easy | Half-day of work; rounds out the macro page |
| Mining-sector AISC tracker | Hard | Requires aggregating individual miner reports; low ROI for time |
| Backtest engine on top of seasonality / FOMC drift | Medium | Lets you publish tradable strategy stats — would extend the project significantly |

Recommended next addition if you have ~1 hour: **FRED economic-release cards on the Macro Drivers page** (Easy, immediate visual impact).
Recommended if you have ~half a day: **Geopolitical Risk Index integration** (Medium, free, clean chart, fits naturally on the Macro page).
Recommended if you want to go big: **Backtest engine** (lets you take seasonality, FOMC drift, COT extremes, and produce concrete strategy P&Ls — this is the single addition most likely to convert a recruiter glance into a phone screen).

---

## 7. Maintenance reminders

- Re-run `python gld_converter.py --backtest` annually; if the recovered drift moves materially away from 0.40%/yr, GLD's expense ratio may have changed.
- The `FOMC_DATES` list in `lib/data.py` is hardcoded through end of 2026 — extend it once 2027 dates are published by the Fed.
- The `GOLD_CURVE_CONTRACTS` list also bakes in specific contract codes (GCM26, GCQ26, …); rotate as contracts expire and new ones become liquid.

---

## 8. Things this project does **not** do (be honest in conversations)

- Generates no trading signals or recommendations — it visualises and synthesises, doesn't predict
- No live order entry / broker integration
- Does not handle position sizing or P&L tracking
- Real-time tick data is not available on the free yfinance stack — refresh cadence is daily-close + intraday delayed

If a recruiter pushes on these, the honest answer is: "Adding any of those is straightforward; this is the analytical core, not the execution layer."
