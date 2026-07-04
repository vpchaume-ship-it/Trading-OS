"""Time helpers: New York timezone, killzones, sessions.

All strategy logic runs in America/New_York time (ICT convention).
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


class Killzones:
    """Killzone labelling from config: {'london': {'start': '02:00', 'end': '05:00'}, ...}."""

    def __init__(self, cfg_killzones: dict):
        self.zones: list[tuple[str, time, time]] = [
            (name, parse_hhmm(z["start"]), parse_hhmm(z["end"]))
            for name, z in cfg_killzones.items()
        ]

    def label(self, ts: datetime | pd.Timestamp) -> str | None:
        """Return killzone name for a NY-tz timestamp, or None. End bound exclusive."""
        t = ts.time()
        for name, start, end in self.zones:
            if start <= t < end:
                return name
        return None

    def in_any(self, ts, allowed: list[str] | None = None) -> bool:
        kz = self.label(ts)
        if kz is None:
            return False
        return allowed is None or kz in allowed


def to_ny(df: pd.DataFrame, source_tz: str) -> pd.DataFrame:
    """Localize a naive DatetimeIndex to source_tz and convert to New York time."""
    out = df.copy()
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is None:
        idx = idx.tz_localize(source_tz, nonexistent="shift_forward", ambiguous=False)
    out.index = idx.tz_convert(NY)
    return out.sort_index()
