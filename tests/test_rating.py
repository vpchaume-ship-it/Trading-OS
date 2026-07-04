"""Inversion rating tests (10-point system from the knowledge/ PDFs)."""

import pandas as pd
import pytest

from trading_os.core.fvg import FVG, Direction
from trading_os.core.rating import InversionRating, rate_inversion


def bullish_fvg(created_idx=2, inverted_idx=4, bottom=100.0, top=101.5) -> FVG:
    f = FVG(Direction.BULLISH, created_idx, pd.Timestamp("2024-03-04 09:32"),
            bottom=bottom, top=top)
    f.inverted_idx = inverted_idx
    return f


def test_a_plus_scenario():
    # Strong full-body candle, instant inversion, close right at the edge
    f = bullish_fvg(created_idx=2, inverted_idx=4)          # 2 bars -> speed 3
    # candle: o=101.4, c=99.8 body=1.6, range h=101.5 l=99.7 = 1.8 -> ratio .89 -> 4
    # overshoot = (100 - 99.8)/1.5 = 0.13 -> rr 3
    r = rate_inversion(f, o=101.4, h=101.5, l=99.7, c=99.8)
    assert (r.candle_strength, r.inversion_speed, r.rr_quality) == (4, 3, 3)
    assert r.total == 10 and r.grade == "A+"


def test_weak_candle_low_grade():
    # tiny body, huge wicks, slow inversion, close far beyond the zone
    f = bullish_fvg(created_idx=2, inverted_idx=50)         # 48 bars -> speed 0
    # body |99.4-99.6|=.2, range 103-96=7 -> ratio .03 -> strength 0
    # overshoot = (100-96.5... c=99.4 wait choose c far: c=96.5 -> (100-96.5)/1.5=2.3 -> rr 0
    r = rate_inversion(f, o=96.7, h=103.0, l=96.0, c=96.5)
    assert r.candle_strength <= 1 and r.inversion_speed == 0 and r.rr_quality == 0
    assert r.grade == "F"


def test_grade_mapping():
    assert InversionRating(4, 3, 3).grade == "A+"
    assert InversionRating(4, 3, 2).grade == "A"
    assert InversionRating(4, 2, 2).grade == "A-"
    assert InversionRating(3, 2, 2).grade == "B+"
    assert InversionRating(2, 2, 2).grade == "B"
    assert InversionRating(2, 2, 1).grade == "B-"
    assert InversionRating(2, 1, 1).grade == "C"
    assert InversionRating(1, 1, 1).grade == "C"
    assert InversionRating(0, 1, 1).grade == "F"


def test_bearish_fvg_overshoot_side():
    # bearish FVG inverted upward: overshoot measured above the top
    f = FVG(Direction.BEARISH, 2, pd.Timestamp("2024-03-04 09:32"),
            bottom=100.0, top=101.5)
    f.inverted_idx = 3
    r = rate_inversion(f, o=100.2, h=101.8, l=100.1, c=101.7)  # 0.2/1.5 above top
    assert r.rr_quality == 3


def test_min_rating_filter_in_engine():
    from tests.test_engine import SETUP_BARS, cfg
    from tests.conftest import make_df
    from trading_os.backtest.engine import run_backtest

    bars = SETUP_BARS + [(99.2, 100.3, 99.1, 99.9), (99.9, 100.0, 95.9, 96.2)]
    df = make_df(bars, start="2024-03-04 09:30")
    base = cfg()
    # inversion bar (102.3,102.4,99.5,99.6): body 2.7/range 2.9 -> 4;
    # speed: created idx2, inverted idx3 -> 3; overshoot (100-99.6)/1.5=0.27 -> rr 2 => 9 (A)
    res = run_backtest(df, base, "ES")
    assert res.trades.iloc[0]["grade"] == "A"
    strict = cfg(min_rating=10)
    res2 = run_backtest(df, strict, "ES")
    assert res2.trades.empty and res2.skipped_low_rating == 1
