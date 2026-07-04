"""Trade journal: one CSV of forward-test trades + helpers for stats.

Columns: timestamp entry/exit, symbol, direction, prices, R result, killzone,
news context, source (semi_auto / manual_sync), notes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

COLUMNS = ["entry_time", "exit_time", "symbol", "direction", "qty", "entry", "exit",
           "stop", "risk_usd", "pnl_usd", "net_r", "killzone", "in_ntz",
           "source", "notes"]


@dataclass
class JournalEntry:
    entry_time: str
    exit_time: str
    symbol: str
    direction: str
    qty: int
    entry: float
    exit: float
    stop: float | None
    risk_usd: float | None
    pnl_usd: float
    net_r: float | None
    killzone: str
    in_ntz: bool
    source: str
    notes: str = ""


class Journal:
    def __init__(self, journal_dir: str | Path):
        self.dir = Path(journal_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.trades_csv = self.dir / "trades.csv"

    def load(self) -> pd.DataFrame:
        if not self.trades_csv.exists():
            return pd.DataFrame(columns=COLUMNS)
        return pd.read_csv(self.trades_csv)

    def append(self, entries: list[JournalEntry]) -> int:
        """Append entries, dedup on (entry_time, symbol, entry, exit)."""
        if not entries:
            return 0
        old = self.load()
        new = pd.DataFrame([asdict(e) for e in entries])
        merged = pd.concat([old, new], ignore_index=True).drop_duplicates(
            subset=["entry_time", "symbol", "entry", "exit"])
        added = len(merged) - len(old)
        merged.to_csv(self.trades_csv, index=False)
        return added

    def killzone_stats(self) -> pd.DataFrame:
        """Personal historical stats per killzone (for the premarket report)."""
        df = self.load()
        if df.empty or df["net_r"].dropna().empty:
            return pd.DataFrame()
        df = df.dropna(subset=["net_r"])
        g = df.groupby("killzone")["net_r"]
        return pd.DataFrame({
            "trades": g.size(),
            "win_rate": g.apply(lambda s: (s > 0).mean()).round(3),
            "avg_r": g.mean().round(3),
            "total_r": g.sum().round(2),
        })
