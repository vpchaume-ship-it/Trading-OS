"""Grow an intraday dataset from Yahoo, day after day, without MT5.

Yahoo only serves ~7 days of 1m and ~60 days of 5m — but fetched every weekday
and merged into a committed CSV, the 1m history grows without limit. The daily
routine runs this, then commits data/yahoo_*.csv to the branch so the dataset
survives ephemeral cloud sessions.

Usage:  python -m trading_os.data.accumulate
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_os.core.timeutils import NY
from trading_os.data.yahoo import fetch

FETCH_PLAN = [("1m", "7d", "1m"), ("5m", "60d", "5m")]


def load_accumulated(path: str | Path) -> pd.DataFrame | None:
    path = Path(path)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    idx = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(NY)
    df = df.drop(columns=["timestamp"]).set_index(idx)
    df.index.name = "timestamp"
    return df.sort_index()


def accumulate(instrument: str, directory: str | Path = "data") -> dict[str, tuple[Path, int]]:
    """Fetch fresh Yahoo intraday data and merge into the committed CSVs.

    Returns {interval: (path, n_total_bars)}.
    """
    out: dict[str, tuple[Path, int]] = {}
    for interval, range_, suffix in FETCH_PLAN:
        path = Path(directory) / f"yahoo_{instrument}_{suffix}.csv"
        fresh = fetch(instrument, range_, interval)
        old = load_accumulated(path)
        merged = fresh if old is None else pd.concat([old, fresh])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        path.parent.mkdir(parents=True, exist_ok=True)
        # store timestamps in UTC ISO form for a stable round-trip
        to_save = merged.copy()
        to_save.index = to_save.index.tz_convert("UTC")
        to_save.to_csv(path)
        out[interval] = (path, len(merged))
    return out


def main() -> None:
    for instrument in ("ES", "NQ"):
        try:
            result = accumulate(instrument)
            parts = ", ".join(f"{k}: {n:,} barres" for k, (_, n) in result.items())
            print(f"✓ {instrument} — {parts}")
        except Exception as exc:
            print(f"✗ {instrument} — {exc}")


if __name__ == "__main__":
    main()
