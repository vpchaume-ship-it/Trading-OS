"""Key ICT levels for the premarket report.

Sessions follow CME futures convention: the trading day runs 18:00 -> 17:00 NY.
* NDOG (New Day Opening Gap): gap between the 17:00 settlement-area close and
  the 18:00 reopen. Kept while not fully filled.
* NWOG (New Week Opening Gap): Friday 17:00 close -> Sunday 18:00 open.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trading_os.core.fvg import FVG, detect_unmitigated_fvgs
from trading_os.core.swings import LiquidityPool, find_equal_levels, find_swings
from trading_os.data.loader import resample


@dataclass
class OpeningGap:
    kind: str                 # "NDOG" | "NWOG"
    close_time: pd.Timestamp  # end of previous session
    open_time: pd.Timestamp
    low: float                # bottom of the gap zone
    high: float


def daily_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Daily OHLC on the 18:00->17:00 NY futures day."""
    return resample(df, "1d")


def previous_day_levels(df: pd.DataFrame) -> dict:
    d = daily_sessions(df)
    if len(d) < 2:
        return {}
    prev = d.iloc[-2]
    return {"pdh": prev["high"], "pdl": prev["low"], "pdc": prev["close"]}


def previous_week_levels(df: pd.DataFrame) -> dict:
    w = df.resample("W-FRI").agg({"high": "max", "low": "min"}).dropna()
    if len(w) < 2:
        return {}
    prev = w.iloc[-2]
    return {"pwh": prev["high"], "pwl": prev["low"]}


def opening_gaps(df: pd.DataFrame, lookback_days: int = 20) -> list[OpeningGap]:
    """Unfilled NDOG/NWOG over the recent past."""
    d = daily_sessions(df)
    gaps: list[OpeningGap] = []
    d = d.tail(lookback_days + 1)
    for i in range(1, len(d)):
        prev_close = d["close"].iloc[i - 1]
        open_ = d["open"].iloc[i]
        if open_ == prev_close:
            continue
        lo, hi = min(prev_close, open_), max(prev_close, open_)
        after = df[df.index >= d.index[i]]
        # filled once price has traded through the whole gap zone
        filled = ((after["low"] <= lo) & (after["high"] >= lo)).any() if open_ > prev_close \
            else ((after["high"] >= hi) & (after["low"] <= hi)).any()
        if not filled:
            kind = "NWOG" if d.index[i].weekday() == 6 else "NDOG"  # Sunday reopen
            gaps.append(OpeningGap(kind, d.index[i - 1], d.index[i], lo, hi))
    return gaps


def htf_unmitigated_fvgs(df: pd.DataFrame, timeframes: list[str],
                         tick_size: float) -> dict[str, list[FVG]]:
    out: dict[str, list[FVG]] = {}
    for tf in timeframes:
        htf = resample(df, tf)
        out[tf] = detect_unmitigated_fvgs(htf, tick_size)[-10:]  # 10 most recent
    return out


def liquidity_pools(df: pd.DataFrame, tick_size: float, tolerance_ticks: int,
                    strength: int, lookback_bars: int = 2000) -> list[LiquidityPool]:
    recent = df.tail(lookback_bars)
    swings = find_swings(recent, strength)
    return find_equal_levels(swings, tick_size, tolerance_ticks)
