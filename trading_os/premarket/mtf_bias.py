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


def _smt(df: pd.DataFrame, sib: pd.DataFrame | None, sib_name: str,
         window: int = 20) -> Signal:
    """SMT divergence vs the correlated sibling (ES<->NQ), ICT style.

    Compare the last `window` bars with the `window` before: if exactly one of
    the pair prints a lower low, the crack is bullish; if exactly one prints a
    higher high, bearish. Both or neither -> no signal.
    """
    if sib is None or len(df) < 2 * window or len(sib) < 2 * window:
        return Signal("smt", 0, "pas de comparaison possible")
    a, b = df.tail(2 * window), sib.tail(2 * window)
    self_ll = a["low"].iloc[window:].min() < a["low"].iloc[:window].min()
    sib_ll = b["low"].iloc[window:].min() < b["low"].iloc[:window].min()
    self_hh = a["high"].iloc[window:].max() > a["high"].iloc[:window].max()
    sib_hh = b["high"].iloc[window:].max() > b["high"].iloc[:window].max()
    ll_div, hh_div = self_ll != sib_ll, self_hh != sib_hh
    if ll_div and not hh_div:
        who = "ce marché" if self_ll else sib_name
        return Signal("smt", 1, f"divergence haussière : le plus bas de {who} "
                                "n'est pas confirmé par l'autre")
    if hh_div and not ll_div:
        who = "ce marché" if self_hh else sib_name
        return Signal("smt", -1, f"divergence baissière : le plus haut de {who} "
                                 "n'est pas confirmé par l'autre")
    return Signal("smt", 0, "pas de divergence ES/NQ nette")


def _label(score: int) -> str:
    if score >= 2:
        return "haussier"
    if score <= -2:
        return "baissier"
    return "neutre"


def tf_bias(tf: str, df: pd.DataFrame, tick: float, min_gap_ticks: int,
            strength: int = 3, extras: list[Signal] | None = None) -> TFBias:
    signals = [_structure(df, strength), _momentum(df),
               _fvg_context(df, tick, min_gap_ticks)]
    signals += extras or []
    score = sum(s.vote for s in signals)
    return TFBias(tf, _label(score), score, signals)


def instrument_matrix(h1: pd.DataFrame, daily: pd.DataFrame, tick: float,
                      min_gap_ticks: int,
                      sib_h1: pd.DataFrame | None = None,
                      sib_daily: pd.DataFrame | None = None,
                      sib_name: str = "l'autre indice") -> list[TFBias]:
    """[D, 4H, 1H] biases for one instrument (daily = completed sessions),
    with SMT divergence against the correlated sibling when provided."""
    pdhl_bias, pdhl_reason = daily_bias(daily)
    pdhl = Signal("PDH/PDL", {"haussier": 1, "baissier": -1, "neutre": 0}[pdhl_bias],
                  pdhl_reason)
    h4 = resample(h1, "4h")
    sib_h4 = resample(sib_h1, "4h") if sib_h1 is not None else None
    return [
        tf_bias("D", daily, tick, min_gap_ticks, strength=2,
                extras=[pdhl, _smt(daily, sib_daily, sib_name, window=10)]),
        tf_bias("4H", h4, tick, min_gap_ticks, strength=3,
                extras=[_smt(h4, sib_h4, sib_name)]),
        tf_bias("1H", h1, tick, min_gap_ticks, strength=3,
                extras=[_smt(h1, sib_h1, sib_name)]),
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
