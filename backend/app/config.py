"""Central configuration. Everything overridable via environment variables."""
import os
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]

# Pre-fetched Elexon data (see scripts/fetch_data.py)
SNAPSHOT_PATH = Path(os.getenv("SNAPSHOT_PATH", ROOT / "data" / "snapshot.json"))
# Built React app, served by FastAPI in the Docker image
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", ROOT / "frontend" / "dist"))

# GB market time. January is GMT (= UTC) but we use the real zone so the logic is
# still correct if someone points the app at a BST month.
LOCAL_TZ = ZoneInfo("Europe/London")

# Day-ahead auction gate closure assumption (UK local time, on the day BEFORE delivery).
# GB day-ahead auctions close mid-morning (roughly 09:20 for EPEX, 09:50 for N2EX), so
# 09:00 is a conservative default: only forecasts published by then could be used.
# The user can change it in the UI.
DEFAULT_CUTOFF = os.getenv("DEFAULT_CUTOFF", "09:00")

# Purchase decisions are made in January 2026 (decision day D-1 in 1..31 Jan)
# => delivery days run 2 Jan 2026 .. 1 Feb 2026.
DECISION_FIRST = date(2026, 1, 1)
DECISION_LAST = date(2026, 1, 31)
DELIVERY_FIRST = date(2026, 1, 2)
DELIVERY_LAST = date(2026, 2, 1)

# Uncertainty band: P10..P90 (80 % interval) of recent forecast errors
BAND_WINDOW_DAYS = 7
BAND_MIN_POINTS = 48
