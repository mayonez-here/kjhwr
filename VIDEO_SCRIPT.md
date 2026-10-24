# Video script (≤10 min total) — record AFTER loading real data

## Part 1 — Customer pitch (≈4:30)
**0:00 Problem (30s).** "Every morning you commit to buying day-ahead power for tomorrow. Wind is the swing factor, and you have to lean on a forecast. Two questions: what's the latest forecast I can act on, and how far can I trust it?"

**0:30 Decision view (90s).** Open *Decision view*, pick a mid-January day. Point at: headline sentence (avg wind, MWh, downside), KPI row, the chart — blue = forecast you'd have had at 09:00 the day before, shaded = 80 % range from the last week's misses, orange = what really happened. "Nothing published after gate closure is ever used."
Change gate closure to 08:00 → chart updates. "Your team sets the cut-off."

**2:00 Accuracy (120s).** *Forecast accuracy* tab, whole month. Read the headline: typical miss, 9-in-10 bound, worst miss, bias. Show daily error bars (which days hurt), error-by-hour, error-by-wind-level ("where it's least reliable"). Use real numbers from your data.

**4:00 Close (30s).** "Pilot gives you a repeatable way to size the cover you buy on top of wind. Next: add demand and price, intraday updates, other regions."

## Part 2 — Tech lead review (≈5:00)
**0:00 Architecture (60s).** React/Vite/Recharts ↔ FastAPI ↔ in-memory store loaded from `data/snapshot.json`; `fetch_data.py` is the only code that talks to Elexon. One Docker image serves both; Vercel variant uses `api/index.py`.

**1:00 Core logic (120s).** `store.latest_forecast` (bisect, ≤ cutoff) → `selection.build_day` (UK-local day, DST-safe cutoff) → `analysis` (metrics, band uses ≤ D-2). Show test `test_selection_never_uses_forecast_published_after_cutoff` and the band-leakage test.

**3:00 Metrics choices (45s).** WAPE vs MAPE, bias sign convention, why P90/P95.

**3:45 Practices (45s).** Tests with hand-computed expectations, validation (422s), synthetic-data banner, README with AI disclosure, snapshot trade-offs.

**4:30 Limits & next steps (30s).** Assumed gate closure; empirical band; no price/demand; could add quantile models and live refresh.

## Before you submit
- [ ] `python scripts/fetch_data.py`, commit `data/snapshot.json`, confirm no yellow banner
- [ ] Deploy, paste URL in README, open in incognito
- [ ] Public repo with random name, unlisted YouTube video, open all links in incognito
