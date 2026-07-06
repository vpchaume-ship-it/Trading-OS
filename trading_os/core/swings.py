"""Swing points, equal highs/lows (liquidity pools), liquidity targets."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Swing:
    idx: int
    time: pd.Timestamp
    price: float
    kind: str  # "high" | "low"


def find_swings(df: pd.DataFrame, strength: int = 3) -> list[Swing]:
    """Fractal swings: a swing high has `strength` lower highs on each side.

    The swing at index i is only *confirmed* `strength` bars later — callers
    doing bar-by-bar logic must respect that (see swings_confirmed_before).
    """
    highs, lows = df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    w = 2 * strength + 1
    if n < w:
        return []
    from numpy.lib.stride_tricks import sliding_window_view
    hw = sliding_window_view(highs, w)      # rows i-strength..i+strength for center i
    lw = sliding_window_view(lows, w)
    idx = np.arange(strength, n - strength)
    is_high = (highs[strength:n - strength] == hw.max(axis=1)) & \
              ((hw == highs[strength:n - strength][:, None]).sum(axis=1) == 1)
    is_low = (lows[strength:n - strength] == lw.min(axis=1)) & \
             ((lw == lows[strength:n - strength][:, None]).sum(axis=1) == 1)
    times = df.index
    out: list[Swing] = []
    for i in idx[is_high]:
        out.append(Swing(int(i), times[i], float(highs[i]), "high"))
    for i in idx[is_low]:
        out.append(Swing(int(i), times[i], float(lows[i]), "low"))
    out.sort(key=lambda s: s.idx)
    return out


def swings_confirmed_before(swings: list[Swing], bar_idx: int, strength: int) -> list[Swing]:
    """Swings usable at bar_idx without lookahead (confirmation lag applied)."""
    return [s for s in swings if s.idx + strength < bar_idx]


@dataclass
class LiquidityPool:
    kind: str          # "equal_highs" | "equal_lows"
    price: float       # level of the pool (extreme of the group)
    times: list[pd.Timestamp]
    count: int


def find_equal_levels(swings: list[Swing], tick_size: float,
                      tolerance_ticks: int = 2) -> list[LiquidityPool]:
    """Group swing highs/lows within tolerance -> resting liquidity (EQH/EQL)."""
    tol = tolerance_ticks * tick_size
    pools: list[LiquidityPool] = []
    for kind, label in (("high", "equal_highs"), ("low", "equal_lows")):
        pts = sorted([s for s in swings if s.kind == kind], key=lambda s: s.price)
        group: list[Swing] = []
        for s in pts:
            if group and s.price - group[0].price > tol:
                if len(group) >= 2:
                    extreme = max if kind == "high" else min
                    pools.append(LiquidityPool(label, extreme(g.price for g in group),
                                               [g.time for g in group], len(group)))
                group = []
            group.append(s)
        if len(group) >= 2:
            extreme = max if kind == "high" else min
            pools.append(LiquidityPool(label, extreme(g.price for g in group),
                                       [g.time for g in group], len(group)))
    return pools


def nearest_liquidity_target(swings: list[Swing], bar_idx: int, strength: int,
                             price: float, direction: str) -> float | None:
    """Nearest confirmed swing beyond current price in the trade direction.

    direction: "bullish" -> nearest swing high above price (buy-side liquidity);
               "bearish" -> nearest swing low below price.
    """
    usable = swings_confirmed_before(swings, bar_idx, strength)
    if direction == "bullish":
        cands = [s.price for s in usable if s.kind == "high" and s.price > price]
        return min(cands) if cands else None
    cands = [s.price for s in usable if s.kind == "low" and s.price < price]
    return max(cands) if cands else None
