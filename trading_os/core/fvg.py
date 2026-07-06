"""FVG / IFVG detection (ICT methodology).

Definitions implemented here — flag any conflict with the knowledge/ PDFs:

* Bullish FVG: on three consecutive candles c1, c2, c3, a gap exists when
  low(c3) > high(c1). Zone = [high(c1), low(c3)] (bottom, top). Acts as support.
* Bearish FVG: high(c3) < low(c1). Zone = [high(c3), low(c1)]. Acts as resistance.
* Inversion (IFVG): a FVG is invalidated by a decisive close through its far
  side (config: close only, or full candle body). The zone then flips polarity:
  an invalidated bullish FVG becomes a bearish IFVG (resistance) and vice versa.
  The trade setup is the retest of the inverted zone.
* A full wick-through without a decisive close does NOT create an inversion;
  depending on config it kills the FVG (fully filled) or leaves it active.

Everything is incremental (bar by bar) so the same tracker is used by the
backtest and by the real-time semi-auto monitor — no lookahead by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

import pandas as pd


class Direction(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class FVGStatus(str, Enum):
    ACTIVE = "active"        # gap formed, not yet invalidated
    INVERTED = "inverted"    # decisively closed through -> tradable IFVG zone
    FILLED = "filled"        # fully wicked through without decisive close (dead)
    EXPIRED = "expired"      # too old without interaction
    CONSUMED = "consumed"    # IFVG retested max times, or reclaimed


@dataclass
class FVG:
    direction: Direction          # direction of the ORIGINAL gap
    created_idx: int              # index of c3 (bar completing the gap)
    created_time: pd.Timestamp
    bottom: float                 # zone low price
    top: float                    # zone high price
    status: FVGStatus = FVGStatus.ACTIVE
    inverted_idx: int | None = None
    inverted_time: pd.Timestamp | None = None
    retests: int = 0

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def ifvg_direction(self) -> Direction:
        """Trade direction of the zone once inverted (opposite of the gap)."""
        return Direction.BEARISH if self.direction == Direction.BULLISH else Direction.BULLISH


@dataclass
class InversionEvent:
    fvg: FVG
    idx: int
    time: pd.Timestamp


@dataclass
class RetestEvent:
    """Price traded back into an inverted zone on this bar."""
    fvg: FVG
    idx: int
    time: pd.Timestamp


@dataclass
class FVGTracker:
    """Incremental FVG/IFVG state machine.

    Feed completed bars in order via update(); it yields Inversion/Retest events.
    """

    tick_size: float
    min_gap_ticks: int = 4
    invalidation_mode: str = "close"      # "close" | "body"
    wick_fill_kills: bool = True
    fvg_max_age_bars: int = 240
    ifvg_max_age_bars: int = 120
    max_retests: int = 1

    fvgs: list[FVG] = field(default_factory=list)          # append-only, full history
    _active: list[FVG] = field(default_factory=list)       # pruned scan list (perf)
    _h1: float | None = None  # high of c1 (two bars ago)
    _l1: float | None = None
    _h2: float | None = None
    _l2: float | None = None
    _n: int = 0

    # ---- helpers -------------------------------------------------------

    def _decisive_beyond(self, o: float, c: float, level: float, below: bool) -> bool:
        """True if the bar closes decisively below (below=True) or above the level."""
        if self.invalidation_mode == "body":
            return (max(o, c) < level) if below else (min(o, c) > level)
        return (c < level) if below else (c > level)

    # ---- main entry point ---------------------------------------------

    def update(self, idx: int, time: pd.Timestamp, o: float, h: float,
               l: float, c: float) -> Iterator[InversionEvent | RetestEvent]:
        """Process one completed bar; yield events triggered by this bar."""
        # 1) lifecycle of existing zones. Only ACTIVE/INVERTED zones are scanned
        # (self._active); terminal ones drop out so the whole backtest stays O(n)
        # instead of O(n²) on long 1m histories. self.fvgs keeps the full history.
        if self._active:
            survivors = []
            for f in self._active:
                if f.status == FVGStatus.ACTIVE:
                    yield from self._update_active(f, idx, time, o, h, l, c)
                elif f.status == FVGStatus.INVERTED:
                    yield from self._update_inverted(f, idx, time, o, h, l, c)
                if f.status in (FVGStatus.ACTIVE, FVGStatus.INVERTED):
                    survivors.append(f)
            self._active = survivors

        # 2) new FVG formation with this bar as c3
        if self._h1 is not None:
            min_size = self.min_gap_ticks * self.tick_size
            new = None
            if l - self._h1 >= min_size:  # bullish gap: low(c3) above high(c1)
                new = FVG(Direction.BULLISH, idx, time, bottom=self._h1, top=l)
            elif self._l1 - h >= min_size:  # bearish gap
                new = FVG(Direction.BEARISH, idx, time, bottom=h, top=self._l1)
            if new is not None:
                self.fvgs.append(new)
                self._active.append(new)

        # 3) shift the 3-candle window
        self._h1, self._l1 = self._h2, self._l2
        self._h2, self._l2 = h, l
        self._n = idx

    def _update_active(self, f: FVG, idx, time, o, h, l, c):
        if idx - f.created_idx > self.fvg_max_age_bars:
            f.status = FVGStatus.EXPIRED
            return
        if f.direction == Direction.BULLISH:
            # far side = bottom; invalidation is a decisive close below it
            if self._decisive_beyond(o, c, f.bottom, below=True):
                f.status, f.inverted_idx, f.inverted_time = FVGStatus.INVERTED, idx, time
                yield InversionEvent(f, idx, time)
            elif self.wick_fill_kills and l <= f.bottom:
                f.status = FVGStatus.FILLED
        else:
            if self._decisive_beyond(o, c, f.top, below=False):
                f.status, f.inverted_idx, f.inverted_time = FVGStatus.INVERTED, idx, time
                yield InversionEvent(f, idx, time)
            elif self.wick_fill_kills and h >= f.top:
                f.status = FVGStatus.FILLED

    def _update_inverted(self, f: FVG, idx, time, o, h, l, c):
        assert f.inverted_idx is not None
        if idx - f.inverted_idx > self.ifvg_max_age_bars:
            f.status = FVGStatus.EXPIRED
            return
        if f.ifvg_direction == Direction.BEARISH:
            # price is below the zone; a decisive close back above the top reclaims it
            if self._decisive_beyond(o, c, f.top, below=False):
                f.status = FVGStatus.CONSUMED
                return
            if h >= f.bottom:  # traded back into the zone from below
                f.retests += 1
                yield RetestEvent(f, idx, time)
                if f.retests >= self.max_retests:
                    f.status = FVGStatus.CONSUMED
        else:
            if self._decisive_beyond(o, c, f.bottom, below=True):
                f.status = FVGStatus.CONSUMED
                return
            if l <= f.top:  # traded back into the zone from above
                f.retests += 1
                yield RetestEvent(f, idx, time)
                if f.retests >= self.max_retests:
                    f.status = FVGStatus.CONSUMED


def detect_unmitigated_fvgs(df: pd.DataFrame, tick_size: float,
                            min_gap_ticks: int = 1) -> list[FVG]:
    """Scan a full OHLC frame and return FVGs never fully filled (premarket report).

    A zone is considered mitigated here as soon as price fully trades through it
    (wick counts) after formation.
    """
    tracker = FVGTracker(tick_size=tick_size, min_gap_ticks=min_gap_ticks,
                         wick_fill_kills=True,
                         fvg_max_age_bars=10 ** 9, ifvg_max_age_bars=10 ** 9)
    for i, (ts, row) in enumerate(df.iterrows()):
        for _ in tracker.update(i, ts, row["open"], row["high"], row["low"], row["close"]):
            pass
    return [f for f in tracker.fvgs if f.status == FVGStatus.ACTIVE]
