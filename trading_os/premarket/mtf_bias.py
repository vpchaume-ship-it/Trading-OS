"""Multi-timeframe bias (D / 4H / 1H) and trading-day status.

Each timeframe gets a mechanical read built from the ICT signals the system
already computes, each one explainable on the dashboard:

* structure  : last two confirmed swing highs/lows -> HH+HL / LL+LH / mixed
* momentum   : last completed candle displaces beyond the previous bar or not
* FVG context: nearest unmitigated FVG — bullish gap under price = support,
               bearish gap above price = resistance
* (D only)   : the PDH/PDL rule from the Daily Bias PDF

Score >= +2 -> bullish, <= -2 -> bearish, otherwise neutral. Deliberately
conservative: one lone signal never flips the pill.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from trading_os.core.fvg import Direction, detect_unmitigated_fvgs
from trading_os.core.swings import find_swings
from trading_os.data.loader import resample
from trading_os.premarket.bias import daily_bias


@dataclass
class Signal:
    name: str
    vote: int          # +1 / 0 / -1
    detail: str


@dataclass
class TFBias:
    tf: str
    bias: str          # haussier / baissier / neutre
    score: int
    signals: list[Signal]


def _structure(df: pd.DataFrame, strength: int) -> Signal:
    swings = find_swings(df.tail(300), strength)
    highs = [s.price for s in swings if s.kind == "high"][-2:]
    lows = [s.price for s in swings if s.kind == "low"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return Signal("structure", 0, "pas assez de swings confirmés")
    hh, hl = highs[1] > highs[0], lows[1] > lows[0]
    if hh and hl:
        return Signal("structure", 1, "HH + HL (structure haussière)")
    if not hh and not hl:
        return Signal("structure", -1, "LH + LL (structure baissière)")
    return Signal("structure", 0, "structure mixte")


def _momentum(df: pd.DataFrame) -> Signal:
    if len(df) < 3:
        return Signal("momentum", 0, "n/d")
    last, prev = df.iloc[-1], df.iloc[-2]
    if last["close"] > prev["high"]:
        return Signal("momentum", 1, "clôture au-dessus du high précédent")
    if last["close"] < prev["low"]:
        return Signal("momentum", -1, "clôture sous le low précédent")
    return Signal("momentum", 0, "pas de déplacement net")


def _fvg_context(df: pd.DataFrame, tick: float, min_gap_ticks: int) -> Signal:
    zones = detect_unmitigated_fvgs(df.tail(400), tick, min_gap_ticks)
    if not zones:
        return Signal("fvg", 0, "aucun FVG actif")
    price = float(df["close"].iloc[-1])

    def dist(f):
        if f.bottom <= price <= f.top:
            return 0.0
        return min(abs(price - f.top), abs(price - f.bottom))

    near = min(zones, key=dist)
    zone = f"{near.bottom:,.2f}–{near.top:,.2f}".replace(",", " ")
    if near.bottom <= price <= near.top:
        if near.direction == Direction.BULLISH:
            return Signal("fvg", 1, f"prix DANS un FVG haussier ({zone})")
        return Signal("fvg", -1, f"prix DANS un FVG baissier ({zone})")
    if near.direction == Direction.BULLISH and near.top < price:
        return Signal("fvg", 1, f"FVG haussier en support sous le prix ({zone})")
    if near.direction == Direction.BEARISH and near.bottom > price:
        return Signal("fvg", -1, f"FVG baissier en résistance au-dessus ({zone})")
    return Signal("fvg", 0, f"FVG le plus proche à contre-position ({zone})")


def _label(score: int) -> str:
    if score >= 2:
        return "haussier"
    if score <= -2:
        return "baissier"
    return "neutre"


def tf_bias(tf: str, df: pd.DataFrame, tick: float, min_gap_ticks: int,
            strength: int = 3, extra: Signal | None = None) -> TFBias:
    signals = [_structure(df, strength), _momentum(df),
               _fvg_context(df, tick, min_gap_ticks)]
    if extra is not None:
        signals.append(extra)
    score = sum(s.vote for s in signals)
    return TFBias(tf, _label(score), score, signals)


def instrument_matrix(h1: pd.DataFrame, daily: pd.DataFrame, tick: float,
                      min_gap_ticks: int) -> list[TFBias]:
    """[D, 4H, 1H] biases for one instrument (daily = completed sessions)."""
    pdhl_bias, pdhl_reason = daily_bias(daily)
    extra = Signal("PDH/PDL", {"haussier": 1, "baissier": -1, "neutre": 0}[pdhl_bias],
                   pdhl_reason)
    h4 = resample(h1, "4h")
    return [
        tf_bias("D", daily, tick, min_gap_ticks, strength=2, extra=extra),
        tf_bias("4H", h4, tick, min_gap_ticks, strength=3),
        tf_bias("1H", h1, tick, min_gap_ticks, strength=3),
    ]


# ------------------------------------------------------------ day status

def day_status(now: datetime) -> tuple[str, str]:
    """('trading'|'closed', label) for the CME index-futures session, NY time."""
    wd = now.weekday()
    if wd == 5 or (wd == 6 and now.hour < 18):
        return "closed", "WEEK-END · marché fermé · réouverture dimanche 18:00 NY"
    holiday = None
    try:
        import holidays as _hol
        holiday = _hol.financial_holidays("NYSE", years=[now.year]).get(now.date())
    except Exception:
        pass
    if holiday:
        return "closed", f"JOUR FÉRIÉ · {holiday} · pas de séance complète"
    if wd == 6:
        return "trading", "Séance du dimanche soir (globex) — patience jusqu'à NY AM"
    return "trading", "JOUR DE TRADING · fenêtre 9:30–11:30 NY"
