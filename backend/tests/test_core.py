import math
from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import analysis
from backend.app.main import app, get_store
from backend.app.selection import build_day, cutoff_utc
from backend.app.store import DataStore

UTC = timezone.utc
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731


def test_selection_never_uses_forecast_published_after_cutoff():
    target = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    store = DataStore.from_records(
        {},
        [(iso(target), 5000)],
        [
            (iso(target), "2026-01-09T06:00:00Z", 1000),
            (iso(target), "2026-01-09T08:59:00Z", 2000),  # latest at/before 09:00 -> chosen
            (iso(target), "2026-01-09T09:00:00Z", 3000),  # exactly at cutoff -> allowed, newer
            (iso(target), "2026-01-09T09:30:00Z", 9999),  # after cutoff -> must be ignored
        ],
    )
    rows = build_day(store, date(2026, 1, 10), time(9, 0))
    row = next(r for r in rows if r["t"] == target)
    assert row["forecast"] == 3000
    assert row["publish"] == datetime(2026, 1, 9, 9, 0, tzinfo=UTC)
    assert row["error"] == -2000  # 3000 - 5000
    assert row["horizon_h"] == 27

    early = build_day(store, date(2026, 1, 10), time(8, 0))  # fresh cache key
    row = next(r for r in early if r["t"] == target)
    assert row["forecast"] == 1000  # only the 06:00 run existed at 08:00


def test_cutoff_is_day_before_delivery_in_uk_time():
    assert cutoff_utc(date(2026, 1, 10), time(9, 0)) == datetime(2026, 1, 9, 9, 0, tzinfo=UTC)
    # BST month: 09:00 local is 08:00 UTC
    assert cutoff_utc(date(2026, 7, 10), time(9, 0)) == datetime(2026, 7, 9, 8, 0, tzinfo=UTC)


def test_summarize_hand_computed():
    # errors (f - a): +100, -300, +200, 0  -> |e| = 100,300,200,0
    pairs = [(1100, 1000), (700, 1000), (2200, 2000), (500, 500)]
    s = analysis.summarize(pairs)
    assert s["n"] == 4
    assert s["mae"] == 150.0
    assert s["bias"] == 0.0
    assert s["rmse"] == round(math.sqrt((100**2 + 300**2 + 200**2) / 4), 1)
    assert s["wape_pct"] == round(600 / 4500 * 100, 2)
    assert s["max_abs"] == 300.0


def test_quantile_interpolation():
    assert analysis.quantile([1, 2, 3, 4, 5], 0.5) == 3
    assert analysis.quantile([0, 10], 0.25) == 2.5
    assert analysis.quantile([], 0.5) is None


def _constant_bias_store(bias=100.0, step_minutes=30):
    """Actual ramps within each day; every forecast = actual + bias."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 2, tzinfo=UTC)
    actuals, t = [], start
    while t < end:
        actuals.append((iso(t), 3000 + (t.hour * 2 + t.minute // 30) * 100))
        t += timedelta(minutes=30)
    a = dict(actuals)
    fcs, pub = [], datetime(2025, 12, 31, tzinfo=UTC)
    while pub < datetime(2026, 2, 1, tzinfo=UTC):
        for m in range(step_minutes, 48 * 60 + 1, step_minutes):
            tgt = iso(pub + timedelta(minutes=m))
            if tgt in a:
                fcs.append((tgt, iso(pub), a[tgt] + bias))
        pub += timedelta(hours=6)
    return DataStore.from_records({"source": "test"}, actuals, fcs)


def test_hourly_forecasts_only_compared_on_matching_timestamps():
    store = _constant_bias_store(100, step_minutes=60)
    out = analysis.accuracy_payload(store, date(2026, 1, 5), date(2026, 1, 5), time(9, 0))
    assert out["overall"]["n"] == 24  # off-the-hour actuals have no forecast -> not scored
    assert out["overall"]["mae"] == 100.0
    dec = analysis.decision_payload(store, date(2026, 1, 5), time(9, 0))
    assert dec["coverage"] == {"points": 24, "expected": 24}


def test_constant_bias_yields_exact_metrics_and_band():
    store = _constant_bias_store(100)
    out = analysis.accuracy_payload(store, date(2026, 1, 5), date(2026, 1, 9), time(9, 0))
    o = out["overall"]
    assert o["mae"] == o["rmse"] == o["bias"] == 100.0
    assert o["n"] == 5 * 48
    assert len(out["by_day"]) == 5 and len(out["by_hour"]) == 24

    dec = analysis.decision_payload(store, date(2026, 1, 20), time(9, 0))
    assert dec["band"]["p10"] == dec["band"]["p90"] == 100.0
    # with constant +100 error the band collapses to forecast-100 == actual
    pt = next(s for s in dec["series"] if s["forecast"] is not None)
    assert pt["lower"] == pt["upper"] == pt["actual"]


def test_band_uses_only_days_up_to_d_minus_2_and_is_absent_without_history():
    store = _constant_bias_store(100)
    assert analysis.error_band(store, date(2026, 1, 2), time(9, 0)) is None
    # Make D-1 (Jan 9) terrible; it must NOT influence the band for Jan 10.
    for tgt in list(store.forecasts):
        if tgt.date() == date(2026, 1, 9):
            pubs, gens = store.forecasts[tgt]
            store.forecasts[tgt] = (pubs, [g + 50000 for g in gens])
    store.day_cache.clear()
    band = analysis.error_band(store, date(2026, 1, 10), time(9, 0))
    assert band["p90"] == 100.0


@pytest.fixture()
def client():
    store = _constant_bias_store(100)
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_endpoints(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    meta = client.get("/api/meta").json()
    assert meta["delivery_days"][0] == "2026-01-02" and meta["delivery_days"][-1] == "2026-02-01"

    d = client.get("/api/decision", params={"delivery_date": "2026-01-15", "cutoff": "09:00"}).json()
    assert d["coverage"]["expected"] == 48
    assert d["forecast_runs"]["latest_publish"] <= d["cutoff_utc"]

    a = client.get("/api/accuracy", params={"start": "2026-01-02", "end": "2026-01-31"}).json()
    assert a["overall"]["mae"] == 100.0 and len(a["timeseries"]) == 30 * 48

    h = client.get("/api/horizon", params={"start": "2026-01-02", "end": "2026-01-31"}).json()
    assert h["by_horizon"] and h["by_horizon"][0]["from_h"] == 0


def test_api_validation(client):
    assert client.get("/api/decision", params={"delivery_date": "2026-03-01"}).status_code == 422
    assert client.get("/api/decision", params={"delivery_date": "2026-01-15", "cutoff": "25:99"}).status_code == 422
    assert client.get("/api/accuracy", params={"start": "2026-01-10", "end": "2026-01-05"}).status_code == 422
