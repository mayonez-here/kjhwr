"""Decision-time forecast selection.

For a delivery day D, the buyer decides on D-1 at the day-ahead gate closure
(`cutoff`, UK local time). For every half-hour of D we therefore take the latest
forecast published at or before that cutoff, and compare it with what was actually
generated.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from .config import LOCAL_TZ
from .store import DataStore

UTC = timezone.utc
STEP = timedelta(minutes=30)


def parse_cutoff(value: str) -> time:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("cutoff must be HH:MM (24h, UK local time)") from exc


def cutoff_utc(delivery: date, cutoff: time) -> datetime:
    """Gate closure for `delivery`: `cutoff` local time on the previous day, in UTC."""
    local = datetime.combine(delivery - timedelta(days=1), cutoff, tzinfo=LOCAL_TZ)
    return local.astimezone(UTC)


def day_targets(delivery: date):
    """All half-hourly target times (UTC) covering the UK-local delivery day."""
    start = datetime.combine(delivery, time(0), tzinfo=LOCAL_TZ).astimezone(UTC)
    end = datetime.combine(delivery + timedelta(days=1), time(0), tzinfo=LOCAL_TZ).astimezone(UTC)
    t = start
    while t < end:
        yield t
        t += STEP


def build_day(store: DataStore, delivery: date, cutoff: time) -> list[dict]:
    """One row per half-hour of `delivery`: forecast known at cutoff vs actual."""
    key = (delivery, cutoff)
    cached = store.day_cache.get(key)
    if cached is not None:
        return cached

    cut = cutoff_utc(delivery, cutoff)
    rows = []
    for t in day_targets(delivery):
        actual = store.actuals.get(t)
        row = {
            "t": t,
            "forecast": None,
            "publish": None,
            "actual": actual,
            "error": None,  # forecast - actual (positive = over-forecast)
            "horizon_h": None,
        }
        hit = store.latest_forecast(t, cut)
        if hit:
            pub, gen = hit
            row.update(forecast=gen, publish=pub, horizon_h=(t - pub).total_seconds() / 3600)
            if actual is not None:
                row["error"] = gen - actual
        rows.append(row)

    store.day_cache[key] = rows
    return rows
