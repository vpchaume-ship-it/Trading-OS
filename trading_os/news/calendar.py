"""ForexFactory economic calendar: fetch, filter USD high-impact (red folders),
compute no-trade zones, and accumulate history for backtest labelling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from trading_os.core.timeutils import NY


@dataclass
class NewsEvent:
    title: str
    time_ny: datetime
    impact: str
    currency: str
    forecast: str
    previous: str

    def no_trade_zone(self, before_min: int, after_min: int) -> tuple[datetime, datetime]:
        return (self.time_ny - timedelta(minutes=before_min),
                self.time_ny + timedelta(minutes=after_min))


def fetch_red_folders(cfg: dict) -> list[NewsEvent]:
    """Current-week USD high-impact events from the public ForexFactory JSON feed."""
    ncfg = cfg["news"]
    resp = requests.get(ncfg["feed_url"], timeout=20,
                        headers={"User-Agent": "TradingOS/0.1 (personal research)"})
    resp.raise_for_status()
    events: list[NewsEvent] = []
    for item in resp.json():
        if item.get("country") != ncfg["currency"]:
            continue
        if item.get("impact") != ncfg["impact"]:
            continue
        # feed dates are ISO8601 with offset, e.g. "2026-07-01T08:30:00-04:00"
        ts = pd.Timestamp(item["date"]).tz_convert(NY).to_pydatetime()
        events.append(NewsEvent(
            title=item.get("title", "?"), time_ny=ts,
            impact=item.get("impact", ""), currency=item.get("country", ""),
            forecast=str(item.get("forecast", "") or "n/d"),
            previous=str(item.get("previous", "") or "n/d"),
        ))
    return sorted(events, key=lambda e: e.time_ny)


def append_history(events: list[NewsEvent], history_csv: str | Path) -> int:
    """Accumulate red folders into the history CSV used by the backtest NTZ filter.

    Returns the number of new rows added (dedup on datetime+title).
    """
    path = Path(history_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame([{"datetime_ny": e.time_ny.isoformat(), "title": e.title,
                         "forecast": e.forecast, "previous": e.previous}
                        for e in events])
    if new.empty:
        return 0
    if path.exists():
        old = pd.read_csv(path)
        merged = pd.concat([old, new]).drop_duplicates(subset=["datetime_ny", "title"])
        added = len(merged) - len(old)
    else:
        merged, added = new.drop_duplicates(subset=["datetime_ny", "title"]), len(new)
    merged.sort_values("datetime_ny").to_csv(path, index=False)
    return added
