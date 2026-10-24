"""In-memory data store for actuals and forecasts, loaded from a JSON snapshot."""
from __future__ import annotations

import bisect
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (with or without Z) into an aware UTC datetime."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class DataStore:
    meta: dict
    # target time (UTC) -> actual wind generation in MW
    actuals: dict[datetime, float]
    # target time (UTC) -> (sorted publish times, generation values aligned with them)
    forecasts: dict[datetime, tuple[list[datetime], list[float]]]
    # cache of computed delivery days, keyed by (delivery_date, cutoff_time)
    day_cache: dict = field(default_factory=dict)

    @classmethod
    def from_records(
        cls,
        meta: dict,
        actuals: Iterable[tuple[str, float]],
        forecasts: Iterable[tuple[str, str, float]],
    ) -> "DataStore":
        act = {parse_ts(t): float(g) for t, g in actuals if g is not None}
        tmp: dict[datetime, dict[datetime, float]] = {}
        for start, publish, gen in forecasts:
            if gen is None:
                continue
            # a later duplicate of the same (start, publish) simply overwrites
            tmp.setdefault(parse_ts(start), {})[parse_ts(publish)] = float(gen)
        fc = {}
        for target, by_pub in tmp.items():
            pubs = sorted(by_pub)
            fc[target] = (pubs, [by_pub[p] for p in pubs])
        return cls(meta=meta, actuals=act, forecasts=fc)

    @classmethod
    def load(cls, path: Path) -> "DataStore":
        raw = json.loads(Path(path).read_text())
        return cls.from_records(
            raw.get("meta", {}),
            ((r[0], r[1]) for r in raw["actuals"]),
            ((r[0], r[1], r[2]) for r in raw["forecasts"]),
        )

    def latest_forecast(self, target: datetime, cutoff: datetime):
        """Most recent forecast for `target` published at or before `cutoff`.

        Returns (publish_time, generation_mw) or None. This is the core
        'what did we know at decision time' lookup - nothing published after the
        cutoff can ever be returned, so there is no look-ahead leakage.
        """
        entry = self.forecasts.get(target)
        if not entry:
            return None
        pubs, gens = entry
        i = bisect.bisect_right(pubs, cutoff) - 1
        if i < 0:
            return None
        return pubs[i], gens[i]
