"""Inversion candle rating — implements the 10-point system from the
knowledge/ PDFs (Candle Closure Ratings + Dodgy's IFVG Rating System):

* Candle Strength /4 : the candle that triggers the inversion must show clear
  momentum (body dominates the range, closes decisively).
* Inversion Speed /3 : quick/instant response from the FVG into inversion —
  measured in bars between the gap formation and the inversion.
* Risk to Reward /3  : the inversion candle's closing level relative to the
  zone edge — the closer the close is to the edge, the better the RR.

Total -> grade: 10=A+, 9=A, 8=A-, 7=B+, 6=B, 5=B-, 3-4=C, <3=F.
(F in the PDFs = entry invalid, e.g. key levels already taken before close.)
"""

from __future__ import annotations

from dataclasses import dataclass

from trading_os.core.fvg import FVG, Direction


@dataclass
class InversionRating:
    candle_strength: int   # /4
    inversion_speed: int   # /3
    rr_quality: int        # /3

    @property
    def total(self) -> int:
        return self.candle_strength + self.inversion_speed + self.rr_quality

    @property
    def grade(self) -> str:
        t = self.total
        if t == 10: return "A+"
        if t == 9:  return "A"
        if t == 8:  return "A-"
        if t == 7:  return "B+"
        if t == 6:  return "B"
        if t == 5:  return "B-"
        if t >= 3:  return "C"
        return "F"


def rate_inversion(fvg: FVG, o: float, h: float, l: float, c: float) -> InversionRating:
    """Rate the inversion candle (the bar whose decisive close flipped the FVG)."""
    rng = h - l
    body_ratio = abs(c - o) / rng if rng > 0 else 0.0
    if body_ratio >= 0.70:
        strength = 4
    elif body_ratio >= 0.55:
        strength = 3
    elif body_ratio >= 0.40:
        strength = 2
    elif body_ratio >= 0.25:
        strength = 1
    else:
        strength = 0

    assert fvg.inverted_idx is not None
    bars = fvg.inverted_idx - fvg.created_idx
    if bars <= 3:
        speed = 3        # instant response, delivery straight into inversion
    elif bars <= 10:
        speed = 2
    elif bars <= 30:
        speed = 1
    else:
        speed = 0

    # Overshoot of the close beyond the zone edge, in zone-size multiples.
    # A close right at the edge = perfect RR for the retest entry.
    zone = fvg.size
    if fvg.ifvg_direction == Direction.BEARISH:   # bullish FVG closed below bottom
        overshoot = (fvg.bottom - c) / zone
    else:                                          # bearish FVG closed above top
        overshoot = (c - fvg.top) / zone
    if overshoot <= 0.25:
        rr = 3
    elif overshoot <= 1.0:
        rr = 2
    elif overshoot <= 2.0:
        rr = 1
    else:
        rr = 0

    return InversionRating(strength, speed, rr)
