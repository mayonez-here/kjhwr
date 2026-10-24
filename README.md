# Wind Forecast Desk

Decision-support web app for a GB energy utility's **day-ahead** power buying team. It answers two questions using national wind data from Elexon (BMRS) only:

1. **What is the latest wind forecast I can act on?** For any delivery day, the app shows the forecast that was actually *published before day-ahead gate closure*, with an uncertainty band sized from recent errors.
2. **How wrong are those forecasts?** Quantified errors (MAE, RMSE, bias, WAPE, P90/P95, by day / hour of day / wind level / forecast lead time), so the buy decision can allow for them.

Scope: purchase decisions made in **January 2026** (decision days 1–31 Jan → delivery days 2 Jan–1 Feb).

**Live app:** `<ADD VERCEL / HEROKU URL HERE>`
**AI disclosure:** this project was built with AI assistance (Claude, via Claude Code). Design, code and tests were generated with it and reviewed by the author.

## How to start

### Docker (recommended)
```bash
docker compose up --build        # → http://localhost:8000
```

### Local dev
```bash
# backend
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
uvicorn backend.app.main:app --reload --port 8000

# frontend (second terminal) → http://localhost:5173 (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

### Load the real Elexon data (do this first)
The app reads `data/snapshot.json`. The repo may ship with a **synthetic** placeholder (the UI shows a yellow banner when it does). Replace it with real data:
```bash
pip install -r backend/requirements.txt
python scripts/fetch_data.py     # needs internet; ~1 min; writes data/snapshot.json
```
Commit the resulting file so the deployed app is self-contained and never depends on Elexon being up.

### Tests
```bash
pytest backend/tests -q
```

## Methodology (the important bit)

**Decision-time forecast.** Day-ahead auctions close mid-morning on D-1. For each target time in delivery day D we take the **latest forecast with `publishTime` ≤ gate closure** (default 09:00 UK time on D-1, adjustable in the UI). Forecasts published later are never used, so there is no look-ahead. Implemented with a per-target sorted publish-time list and `bisect` (`backend/app/store.py`, `selection.py`).

**Error** = forecast − actual (positive = over-forecast, i.e. you'd under-buy). Only timestamps present in *both* datasets are scored.

| Metric | Why |
|---|---|
| MAE / RMSE | typical miss / penalises large misses |
| Bias | systematic over/under-forecasting |
| WAPE = Σ\|e\| / Σ actual | % error that stays sane when output ≈ 0 (plain MAPE explodes) |
| P90 / P95 abs error | tail risk to plan reserve against |

**Uncertainty band.** 10th–90th percentile of (forecast − actual) over the previous 7 delivery days at the same cutoff, using only days ≤ D-2 (their actuals were complete by D-1 gate closure). Applied to today's forecast → an 80 % interval for the actual. Not shown for the first days of the dataset (insufficient history).

**Lead-time view** scores *every* published forecast run (not only the decision-time one) by hours-before-delivery, to show what waiting for a fresher run would buy.

**Assumptions / limits** — gate closure time is assumed (09:00 default, editable); national wind only; no price or demand data; the band is empirical, not a calibrated probabilistic model.

## Files

```
backend/app/
  config.py      constants: paths, timezone, Jan-2026 window, default cutoff
  store.py       DataStore: load snapshot, latest_forecast(target, cutoff)
  selection.py   cutoff → UTC, build per-half-hour forecast-vs-actual rows
  analysis.py    metrics + payload builders (decision / accuracy / horizon)
  main.py        FastAPI routes under /api; serves frontend/dist when present
  elexon.py      Elexon Insights client (used only by the fetch script)
backend/tests/   pytest: no-leakage selection, hand-computed metrics, API
scripts/
  fetch_data.py       real Elexon data → data/snapshot.json
  make_synthetic.py   fake data for dev/tests (flagged synthetic)
frontend/src/    React + Vite + Recharts (Decision / Accuracy / Horizon tabs)
data/snapshot.json   pre-fetched data used by the app
api/index.py     Vercel serverless entrypoint
Dockerfile, docker-compose.yml, heroku.yml, vercel.json   packaging / deploy
```

API: `GET /api/meta`, `/api/decision?delivery_date=&cutoff=`, `/api/accuracy?start=&end=&cutoff=`, `/api/horizon?start=&end=`, `/api/health`.

## Deploy

**Vercel:** import the repo; `vercel.json` builds the React app and exposes FastAPI as a serverless function (data bundled via `includeFiles`).
**Heroku (container):** `heroku stack:set container && git push heroku main` (uses `heroku.yml` + `Dockerfile`; honours `$PORT`).

## Design decisions

- **Snapshot instead of live calls**: reproducible numbers, instant responses, no API rate limits, app survives Elexon outages. Trade-off: data is as fresh as the last `fetch_data.py` run (fine for a fixed historical month).
- **No pandas**: data is small (tens of thousands of rows); plain Python keeps the serverless bundle tiny and the logic easy to review.
- **Computed once, cached**: each (delivery day, cutoff) is built once and memoised.
