"""FastAPI application: JSON API under /api plus the built React app (in Docker)."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import analysis, config
from .selection import parse_cutoff
from .store import DataStore

app = FastAPI(title="Wind Forecast Decision Support", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

_store: DataStore | None = None


def get_store() -> DataStore:
    global _store
    if _store is None:
        if not config.SNAPSHOT_PATH.exists():
            raise HTTPException(
                503,
                f"No data snapshot at {config.SNAPSHOT_PATH}. "
                "Run `python scripts/fetch_data.py` (real Elexon data) first.",
            )
        _store = DataStore.load(config.SNAPSHOT_PATH)
    return _store


def _cutoff(value: str):
    try:
        return parse_cutoff(value)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _check_day(d: date, label: str = "date"):
    if not (config.DELIVERY_FIRST <= d <= config.DELIVERY_LAST):
        raise HTTPException(
            422,
            f"{label} {d} outside supported range "
            f"{config.DELIVERY_FIRST}..{config.DELIVERY_LAST} "
            "(delivery days for purchase decisions made in January 2026)",
        )


def _check_range(start: date, end: date):
    _check_day(start, "start")
    _check_day(end, "end")
    if end < start:
        raise HTTPException(422, "end must be on or after start")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta(store: DataStore = Depends(get_store)):
    m = store.meta or {}
    days, d = [], config.DELIVERY_FIRST
    while d <= config.DELIVERY_LAST:
        days.append(d.isoformat())
        d += timedelta(days=1)
    return {
        "source": m.get("source", "unknown"),
        "synthetic": m.get("source") == "synthetic",
        "fetched_at": m.get("fetched_at"),
        "delivery_days": days,
        "default_cutoff": config.DEFAULT_CUTOFF,
        "decision_window": {"from": config.DECISION_FIRST.isoformat(),
                            "to": config.DECISION_LAST.isoformat()},
        "counts": {
            "actual_points": len(store.actuals),
            "forecast_targets": len(store.forecasts),
            "forecast_rows": sum(len(v[0]) for v in store.forecasts.values()),
        },
    }


@app.get("/api/decision")
def decision(
    delivery_date: date,
    cutoff: str = Query(config.DEFAULT_CUTOFF, description="HH:MM UK time on day before delivery"),
    store: DataStore = Depends(get_store),
):
    _check_day(delivery_date, "delivery_date")
    return analysis.decision_payload(store, delivery_date, _cutoff(cutoff))


@app.get("/api/accuracy")
def accuracy(
    start: date,
    end: date,
    cutoff: str = Query(config.DEFAULT_CUTOFF),
    store: DataStore = Depends(get_store),
):
    _check_range(start, end)
    return analysis.accuracy_payload(store, start, end, _cutoff(cutoff))


@app.get("/api/horizon")
def horizon(start: date, end: date, store: DataStore = Depends(get_store)):
    _check_range(start, end)
    return analysis.horizon_payload(store, start, end)


# Serve the React build when present (Docker / Heroku). In dev, Vite serves the UI.
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
