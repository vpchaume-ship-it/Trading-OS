"""Journal-only mode: pull fills from the Tradovate DEMO account, rebuild round
trips (FIFO), enrich with killzone/news context and store them in the journal.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

import pandas as pd

from trading_os.core.timeutils import NY, Killzones
from trading_os.forward.tradovate import TradovateDemo
from trading_os.journal.store import Journal, JournalEntry
from trading_os.news.calendar import NewsEvent


def _round_trips(fills: list[dict]) -> list[dict]:
    """FIFO matching of buy/sell fills per contract -> closed round trips."""
    by_contract: dict[int, list[dict]] = defaultdict(list)
    for f in sorted(fills, key=lambda f: f["timestamp"]):
        by_contract[f["contractId"]].append(f)

    trips: list[dict] = []
    for cid, fs in by_contract.items():
        longs: deque = deque()   # open buy lots
        shorts: deque = deque()  # open sell lots
        for f in fs:
            qty = f.get("qty", 1)
            side_buy = f.get("action") == "Buy"
            for _ in range(int(qty)):
                lot = {"price": f["price"], "time": f["timestamp"]}
                if side_buy:
                    if shorts:  # closes a short
                        open_lot = shorts.popleft()
                        trips.append({"contractId": cid, "direction": "short",
                                      "entry": open_lot["price"], "exit": f["price"],
                                      "entry_time": open_lot["time"], "exit_time": f["timestamp"]})
                    else:
                        longs.append(lot)
                else:
                    if longs:  # closes a long
                        open_lot = longs.popleft()
                        trips.append({"contractId": cid, "direction": "long",
                                      "entry": open_lot["price"], "exit": f["price"],
                                      "entry_time": open_lot["time"], "exit_time": f["timestamp"]})
                    else:
                        shorts.append(lot)
    return trips


def _tick_value_for(symbol: str, cfg: dict) -> tuple[float, float]:
    """(tick_size, tick_value USD) for a Tradovate contract name like MESU5."""
    sym = symbol.upper()
    for name, spec in cfg["instruments"].items():
        if sym.startswith("M" + name):     # MES / MNQ micros
            return spec["tick_size"], spec["micro_tick_value"]
        if sym.startswith(name):
            return spec["tick_size"], spec["tick_value"]
    return 0.25, 1.25


def sync_journal(cfg: dict, ntz_intervals: list[tuple] | None = None) -> int:
    """Fetch demo fills, rebuild trades, append to journal. Returns rows added."""
    api = TradovateDemo()
    api.authenticate()
    fills = api.fills_all()
    if not fills:
        return 0

    kz = Killzones(cfg["killzones"])
    ntz_intervals = ntz_intervals or []
    names: dict[int, str] = {}
    entries: list[JournalEntry] = []

    for t in _round_trips(fills):
        cid = t["contractId"]
        if cid not in names:
            names[cid] = api.contract_name(cid)
        symbol = names[cid]
        tick, tick_val = _tick_value_for(symbol, cfg)
        entry_ts = pd.Timestamp(t["entry_time"]).tz_convert(NY)
        sign = 1 if t["direction"] == "long" else -1
        pnl = sign * (t["exit"] - t["entry"]) / tick * tick_val
        in_ntz = any(a <= entry_ts <= b for a, b in ntz_intervals)
        entries.append(JournalEntry(
            entry_time=entry_ts.isoformat(),
            exit_time=pd.Timestamp(t["exit_time"]).tz_convert(NY).isoformat(),
            symbol=symbol, direction=t["direction"], qty=1,
            entry=t["entry"], exit=t["exit"], stop=None, risk_usd=None,
            pnl_usd=round(pnl, 2), net_r=None,
            killzone=kz.label(entry_ts) or "hors_killzone",
            in_ntz=in_ntz, source="manual_sync",
            notes="R à renseigner manuellement (stop non connu via l'API)",
        ))

    return Journal(cfg["journal"]["directory"]).append(entries)


def realized_pnl_today(cfg: dict) -> float:
    """Realized PnL of the day from the journal (for the daily-loss guard)."""
    df = Journal(cfg["journal"]["directory"]).load()
    if df.empty:
        return 0.0
    today = datetime.now(NY).date().isoformat()
    mask = df["exit_time"].astype(str).str.startswith(today)
    return float(df.loc[mask, "pnl_usd"].sum())
