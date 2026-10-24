"""Thin client for the Elexon Insights (BMRS) stream endpoints.

Only used by scripts/fetch_data.py - the running web app reads a pre-built snapshot,
so the deployed app never depends on Elexon being up.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import httpx

BASE = "https://data.elexon.co.uk/bmrs/api/v1"


class ElexonError(RuntimeError):
    pass


def _get(client: httpx.Client, path: str, params: dict, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            resp = client.get(f"{BASE}{path}", params=params, timeout=60)
            if resp.status_code == 200:
                body = resp.json()
                # stream endpoints return a bare list; tolerate {"data": [...]}
                return body["data"] if isinstance(body, dict) and "data" in body else body
            last = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code < 500 and resp.status_code != 429:
                break  # client error - retrying will not help
        except httpx.HTTPError as exc:
            last = repr(exc)
        time.sleep(2 ** attempt)
    raise ElexonError(f"GET {path} {params} failed: {last}")


def _require(rows: list[dict], keys: tuple[str, ...], what: str):
    if rows and not all(k in rows[0] for k in keys):
        raise ElexonError(
            f"{what}: unexpected response shape. Expected keys {keys}, got {sorted(rows[0])}. "
            "Elexon may have changed the API - check the endpoint docs."
        )


def fetch_actuals(client: httpx.Client, start: date, end: date) -> list[list]:
    """FUELHH wind actuals for settlement dates start..end inclusive -> [[startTime, MW], ...]."""
    out, d = [], start
    while d <= end:
        chunk_end = min(d + timedelta(days=6), end)
        rows = _get(client, "/datasets/FUELHH/stream", {
            "settlementDateFrom": d.isoformat(),
            "settlementDateTo": chunk_end.isoformat(),
            "fuelType": "WIND",
        })
        _require(rows, ("startTime", "generation", "fuelType"), "FUELHH")
        out += [[r["startTime"], r["generation"]] for r in rows if r.get("fuelType") == "WIND"]
        d = chunk_end + timedelta(days=1)
    return out


def fetch_forecasts(client: httpx.Client, pub_from: datetime, pub_to: datetime) -> list[list]:
    """WINDFOR forecasts published in [pub_from, pub_to) -> [[startTime, publishTime, MW], ...]."""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    out, t = [], pub_from
    while t < pub_to:
        t2 = min(t + timedelta(days=1), pub_to)
        rows = _get(client, "/datasets/WINDFOR/stream", {
            "publishDateTimeFrom": t.strftime(fmt),
            "publishDateTimeTo": t2.strftime(fmt),
        })
        _require(rows, ("startTime", "publishTime", "generation"), "WINDFOR")
        out += [[r["startTime"], r["publishTime"], r["generation"]] for r in rows]
        t = t2
    return out
