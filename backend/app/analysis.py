"""Accuracy metrics and API payload builders. Pure Python, no pandas (keeps deploys small)."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from .config import BAND_MIN_POINTS, BAND_WINDOW_DAYS, LOCAL_TZ
from .selection import UTC, build_day, cutoff_utc, day_targets
from .store import DataStore

LEVEL_EDGES = [0, 2000, 5000, 10000, 15000, math.inf]  # MW buckets by actual wind output
HORIZON_BUCKET_H = 12
HORIZON_CAP_H = 96


def _r(x, nd=1):
    return None if x is None else round(x, nd)


def quantile(sorted_vals: list[float], q: float):
    """Linear-interpolated quantile of an already sorted list."""
    n = len(sorted_vals)
    if n == 0:
        return None
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def summarize(pairs: list[tuple[float, float]]) -> dict:
    """Error statistics for (forecast, actual) pairs. error = forecast - actual."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    errs = [f - a for f, a in pairs]
    abs_sorted = sorted(abs(e) for e in errs)
    err_sorted = sorted(errs)
    sum_actual = sum(a for _, a in pairs)
    sum_abs = sum(abs_sorted)
    return {
        "n": n,
        "mae": _r(sum_abs / n),
        "rmse": _r(math.sqrt(sum(e * e for e in errs) / n)),
        "bias": _r(sum(errs) / n),
        # weighted absolute % error: robust when output is near zero (plain MAPE is not)
        "wape_pct": _r(sum_abs / sum_actual * 100, 2) if sum_actual > 0 else None,
        "p50_abs": _r(quantile(abs_sorted, 0.5)),
        "p90_abs": _r(quantile(abs_sorted, 0.9)),
        "p95_abs": _r(quantile(abs_sorted, 0.95)),
        "max_abs": _r(abs_sorted[-1]),
        "mean_actual": _r(sum_actual / n),
        "mean_forecast": _r(sum(f for f, _ in pairs) / n),
        "err_p10": _r(quantile(err_sorted, 0.10)),
        "err_p90": _r(quantile(err_sorted, 0.90)),
    }


def _pairs(rows):
    return [(r["forecast"], r["actual"]) for r in rows if r["error"] is not None]


def error_band(store: DataStore, delivery: date, cutoff: time,
               window: int = BAND_WINDOW_DAYS, min_points: int = BAND_MIN_POINTS):
    """80 % error band from the previous `window` fully-observed delivery days.

    Only delivery days <= D-2 are used: their actuals were complete before the D-1
    gate closure, so this is exactly what the buyer could have known (no leakage).
    Returns None when there is not enough history (first days of the dataset).
    """
    errs: list[float] = []
    for k in range(2, 2 + window):
        for r in build_day(store, delivery - timedelta(days=k), cutoff):
            if r["error"] is not None:
                errs.append(r["error"])
    if len(errs) < min_points:
        return None
    errs.sort()
    return {
        "p10": _r(quantile(errs, 0.10)),
        "p90": _r(quantile(errs, 0.90)),
        "n": len(errs),
        "window_days": window,
        "level_pct": 80,
    }


def decision_payload(store: DataStore, delivery: date, cutoff: time) -> dict:
    rows = build_day(store, delivery, cutoff)
    band = error_band(store, delivery, cutoff)

    series = []
    for r in rows:
        f = r["forecast"]
        lo = hi = None
        if f is not None and band:
            # actual = forecast - error  =>  low actual <-> high (positive) error
            lo = max(0.0, f - band["p90"])
            hi = max(0.0, f - band["p10"])
        series.append({
            "t": r["t"].isoformat().replace("+00:00", "Z"),
            "forecast": _r(f),
            "lower": _r(lo),
            "upper": _r(hi),
            "actual": _r(r["actual"]),
            "publish": r["publish"].isoformat().replace("+00:00", "Z") if r["publish"] else None,
        })

    fvals = [r["forecast"] for r in rows if r["forecast"] is not None]
    lows = [s["lower"] for s in series if s["lower"] is not None]
    pubs = [r["publish"] for r in rows if r["publish"] is not None]
    avg = sum(fvals) / len(fvals) if fvals else None
    avg_low = sum(lows) / len(lows) if lows else None

    # Score this very decision if the day has already been delivered
    realised = summarize(_pairs(rows))

    return {
        "delivery_date": delivery.isoformat(),
        "cutoff_local": f"{cutoff.hour:02d}:{cutoff.minute:02d}",
        "cutoff_utc": cutoff_utc(delivery, cutoff).isoformat().replace("+00:00", "Z"),
        "forecast_runs": {
            "earliest_publish": min(pubs).isoformat().replace("+00:00", "Z") if pubs else None,
            "latest_publish": max(pubs).isoformat().replace("+00:00", "Z") if pubs else None,
            "distinct_runs": len(set(pubs)),
        },
        # "expected" = slots for which the dataset has ANY forecast. If Elexon publishes
        # hourly values, the off-the-hour half-hours are not counted as missing.
        "coverage": {"points": len(fvals),
                     "expected": sum(1 for r in rows if r["t"] in store.forecasts)},
        "summary": {
            "avg_mw": _r(avg),
            "min_mw": _r(min(fvals)) if fvals else None,
            "max_mw": _r(max(fvals)) if fvals else None,
            "energy_mwh": _r(avg * 24, 0) if avg is not None else None,
            "downside_avg_mw": _r(avg_low),
            "downside_gap_mw": _r(avg - avg_low) if avg is not None and avg_low is not None else None,
        },
        "band": band,
        "realised": realised if realised["n"] else None,
        "series": series,
    }


def _days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def accuracy_payload(store: DataStore, start: date, end: date, cutoff: time) -> dict:
    all_rows, by_day = [], []
    by_hour: dict[int, list] = defaultdict(list)
    by_level: dict[int, list] = defaultdict(list)
    timeseries = []

    for d in _days(start, end):
        rows = build_day(store, d, cutoff)
        pairs = _pairs(rows)
        if pairs:
            s = summarize(pairs)
            by_day.append({"date": d.isoformat(), **{k: s[k] for k in
                           ("n", "mae", "rmse", "bias", "mean_actual", "mean_forecast")}})
        for r in rows:
            all_rows.append(r)
            timeseries.append({
                "t": r["t"].isoformat().replace("+00:00", "Z"),
                "forecast": _r(r["forecast"]),
                "actual": _r(r["actual"]),
            })
            if r["error"] is not None:
                by_hour[r["t"].astimezone(LOCAL_TZ).hour].append((r["forecast"], r["actual"]))
                for i in range(len(LEVEL_EDGES) - 1):
                    if LEVEL_EDGES[i] <= r["actual"] < LEVEL_EDGES[i + 1]:
                        by_level[i].append((r["forecast"], r["actual"]))
                        break

    pairs_all = _pairs(all_rows)
    errs = sorted(f - a for f, a in pairs_all)

    # signed-error histogram (1 GW bins) to show the shape of the risk
    hist: dict[int, int] = defaultdict(int)
    for e in errs:
        hist[int(math.floor(e / 1000.0))] += 1
    histogram = [{"from_mw": b * 1000, "to_mw": (b + 1) * 1000, "count": c}
                 for b, c in sorted(hist.items())]

    def lvl_label(i):
        lo, hi = LEVEL_EDGES[i], LEVEL_EDGES[i + 1]
        return f"{lo/1000:g}+ GW" if math.isinf(hi) else f"{lo/1000:g}-{hi/1000:g} GW"

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "cutoff_local": f"{cutoff.hour:02d}:{cutoff.minute:02d}",
        "overall": summarize(pairs_all),
        "by_day": by_day,
        "by_hour": [{"hour": h, **summarize(by_hour[h])} for h in sorted(by_hour)],
        "by_level": [{"bucket": lvl_label(i), **summarize(by_level[i])}
                     for i in sorted(by_level)],
        "histogram": histogram,
        "timeseries": timeseries,
    }


def horizon_payload(store: DataStore, start: date, end: date) -> dict:
    """Error vs lead time using EVERY published forecast (not just the decision-time one).

    Shows how much forecasts improve as delivery approaches - useful context for
    choosing when to buy and how much to trust a forecast of a given age.
    """
    first = next(iter(day_targets(start)))
    last = list(day_targets(end))[-1] + timedelta(minutes=30)
    buckets: dict[int, list] = defaultdict(list)
    for target, (pubs, gens) in store.forecasts.items():
        if not (first <= target < last):
            continue
        actual = store.actuals.get(target)
        if actual is None:
            continue
        for pub, gen in zip(pubs, gens):
            h = (target - pub).total_seconds() / 3600
            if h < 0:
                continue
            b = int(min(h, HORIZON_CAP_H - 0.001) // HORIZON_BUCKET_H) * HORIZON_BUCKET_H
            buckets[b].append((gen, actual))
    out = []
    for b in sorted(buckets):
        label = (f"{b}h+" if b + HORIZON_BUCKET_H >= HORIZON_CAP_H
                 else f"{b}-{b + HORIZON_BUCKET_H}h")
        out.append({"bucket": label, "from_h": b, **summarize(buckets[b])})
    return {"start": start.isoformat(), "end": end.isoformat(), "by_horizon": out}
