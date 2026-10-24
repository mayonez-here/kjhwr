#!/usr/bin/env python
"""Download real Elexon data for January-2026 purchase decisions into data/snapshot.json.

    python scripts/fetch_data.py

Run once from the repo root with internet access. Commit the resulting snapshot so the
deployed app is self-contained.
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import elexon  # noqa: E402


def dedupe(rows, key_len):
    seen = {}
    for r in rows:
        seen[tuple(r[:key_len])] = r  # later rows win
    return sorted(seen.values())


def main():
    out = ROOT / "data" / "snapshot.json"
    # Decisions on 1..31 Jan 2026 -> delivery 2 Jan .. 1 Feb 2026.
    # Actuals: 1 Jan..1 Feb. Forecasts: everything published 31 Dec 00:00Z .. 1 Feb 00:00Z.
    with httpx.Client(headers={"Accept": "application/json"}) as client:
        print("Fetching FUELHH (WIND actuals)...")
        actuals = dedupe(elexon.fetch_actuals(client, date(2026, 1, 1), date(2026, 2, 1)), 1)
        print(f"  {len(actuals)} half-hourly actuals")
        print("Fetching WINDFOR forecasts (one request per publish day)...")
        forecasts = dedupe(elexon.fetch_forecasts(
            client,
            datetime(2025, 12, 31, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
        ), 2)
        print(f"  {len(forecasts)} forecast rows")

    if not actuals or not forecasts:
        sys.exit("No data returned - refusing to write an empty snapshot.")

    snapshot = {
        "meta": {
            "source": "elexon",
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "datasets": ["FUELHH (fuelType=WIND)", "WINDFOR"],
        },
        "actuals": actuals,
        "forecasts": forecasts,
    }
    out.write_text(json.dumps(snapshot, separators=(",", ":")))
    print(f"Wrote {out} ({out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
