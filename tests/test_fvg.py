"""FVG/IFVG detection tests, edge cases included."""

import pandas as pd
import pytest

from tests.conftest import make_df
from trading_os.core.fvg import (Direction, FVGStatus, FVGTracker,
                                 InversionEvent, RetestEvent,
                                 detect_unmitigated_fvgs)

TICK = 0.25


def feed(tracker: FVGTracker, df: pd.DataFrame):
    events = []
    for i, (ts, row) in enumerate(df.iterrows()):
        events += [(i, ev) for ev in tracker.update(
            i, ts, row["open"], row["high"], row["low"], row["close"])]
    return events


def tracker(**kw) -> FVGTracker:
    defaults = dict(tick_size=TICK, min_gap_ticks=4, invalidation_mode="close",
                    wick_fill_kills=True, fvg_max_age_bars=1000,
                    ifvg_max_age_bars=1000, max_retests=1)
    defaults.update(kw)
    return FVGTracker(**defaults)


# ---------------------------------------------------------------- formation

def test_bullish_fvg_detected():
    # c1 high=100, c3 low=101.5 -> gap of 1.5 = 6 ticks >= 4
    df = make_df([(99, 100, 98.5, 99.8),        # c1
                  (100, 101.6, 99.9, 101.5),    # c2 (impulse)
                  (101.6, 102.5, 101.5, 102.3)])  # c3
    t = tracker()
    feed(t, df)
    assert len(t.fvgs) == 1
    f = t.fvgs[0]
    assert f.direction == Direction.BULLISH
    assert f.bottom == 100 and f.top == 101.5
    assert f.status == FVGStatus.ACTIVE


def test_bearish_fvg_detected():
    df = make_df([(102, 102.5, 101.5, 101.6),
                  (101.5, 101.6, 99.9, 100),
                  (99.9, 100.0, 98.5, 99)])   # high(c3)=100 < low(c1)=101.5
    t = tracker()
    feed(t, df)
    assert len(t.fvgs) == 1
    f = t.fvgs[0]
    assert f.direction == Direction.BEARISH
    assert f.bottom == 100.0 and f.top == 101.5


def test_no_fvg_when_candles_overlap():
    df = make_df([(100, 101, 99, 100.5),
                  (100.5, 101.5, 100, 101),
                  (101, 102, 100.8, 101.5)])  # low(c3)=100.8 < high(c1)=101
    t = tracker()
    feed(t, df)
    assert t.fvgs == []


def test_gap_below_min_size_ignored():
    # gap = 0.5 = 2 ticks < min 4 ticks
    df = make_df([(99, 100, 98.5, 99.8),
                  (100, 100.6, 99.9, 100.5),
                  (100.5, 101, 100.5, 100.9)])
    t = tracker(min_gap_ticks=4)
    feed(t, df)
    assert t.fvgs == []
    t2 = tracker(min_gap_ticks=2)
    feed(t2, df)
    assert len(t2.fvgs) == 1


def test_gap_exactly_min_size_detected():
    # gap = 1.0 = exactly 4 ticks -> accepted (>=)
    df = make_df([(99, 100, 98.5, 99.8),
                  (100, 101.1, 99.9, 101),
                  (101, 102, 101.0, 101.8)])
    t = tracker(min_gap_ticks=4)
    feed(t, df)
    assert len(t.fvgs) == 1


# ---------------------------------------------------------------- inversion

def _bullish_fvg_bars():
    """Three bars creating a bullish FVG zone [100, 101.5]."""
    return [(99, 100, 98.5, 99.8), (100, 101.6, 99.9, 101.5), (101.6, 102.5, 101.5, 102.3)]


def test_inversion_on_close_through():
    df = make_df(_bullish_fvg_bars() + [(102.3, 102.4, 99.5, 99.6)])  # close 99.6 < 100
    t = tracker()
    events = feed(t, df)
    inversions = [ev for _, ev in events if isinstance(ev, InversionEvent)]
    assert len(inversions) == 1
    assert t.fvgs[0].status == FVGStatus.INVERTED
    assert t.fvgs[0].ifvg_direction == Direction.BEARISH


def test_wick_through_is_not_inversion():
    # wick to 99.5 below the zone but close back inside at 100.5
    df = make_df(_bullish_fvg_bars() + [(102.3, 102.4, 99.5, 100.5)])
    t = tracker(wick_fill_kills=True)
    events = feed(t, df)
    assert not [ev for _, ev in events if isinstance(ev, InversionEvent)]
    assert t.fvgs[0].status == FVGStatus.FILLED  # fully wicked through -> dead


def test_wick_fill_keeps_active_when_configured():
    df = make_df(_bullish_fvg_bars() + [(102.3, 102.4, 99.5, 100.5)])
    t = tracker(wick_fill_kills=False)
    feed(t, df)
    assert t.fvgs[0].status == FVGStatus.ACTIVE


def test_body_mode_requires_full_body_beyond():
    # close below bottom but open above -> "close" mode inverts, "body" does not
    bar = (100.5, 102.4, 99.5, 99.6)
    df = make_df(_bullish_fvg_bars() + [bar])
    t_close = tracker(invalidation_mode="close")
    assert [ev for _, ev in feed(t_close, df) if isinstance(ev, InversionEvent)]
    t_body = tracker(invalidation_mode="body")
    assert not [ev for _, ev in feed(t_body, df) if isinstance(ev, InversionEvent)]
    # now a bar with open AND close below -> body mode inverts
    df2 = make_df(_bullish_fvg_bars() + [(99.8, 99.9, 99.0, 99.2)])
    t_body2 = tracker(invalidation_mode="body")
    assert [ev for _, ev in feed(t_body2, df2) if isinstance(ev, InversionEvent)]


def test_close_exactly_on_boundary_is_not_inversion():
    # close == bottom (100) : pas de clôture FRANCHE en dessous
    df = make_df(_bullish_fvg_bars() + [(102.3, 102.4, 100.0, 100.0)])
    t = tracker(wick_fill_kills=False)
    events = feed(t, df)
    assert not [ev for _, ev in events if isinstance(ev, InversionEvent)]


# ---------------------------------------------------------------- retest

def test_retest_after_inversion_emits_event():
    df = make_df(_bullish_fvg_bars() + [
        (102.3, 102.4, 99.5, 99.6),   # inversion (close < 100)
        (99.6, 99.8, 99.0, 99.2),     # drifts lower, no touch
        (99.2, 100.3, 99.1, 99.9),    # rallies back into zone (high 100.3 >= 100)
    ])
    t = tracker()
    events = feed(t, df)
    retests = [ev for _, ev in events if isinstance(ev, RetestEvent)]
    assert len(retests) == 1
    assert retests[0].fvg.status == FVGStatus.CONSUMED  # max_retests=1


def test_reclaim_kills_inverted_zone():
    df = make_df(_bullish_fvg_bars() + [
        (102.3, 102.4, 99.5, 99.6),    # inversion
        (99.6, 102.0, 99.5, 101.9),    # decisive close back ABOVE top (101.5) -> reclaimed
        (101.9, 102.0, 99.9, 100.0),   # would-be retest, must NOT fire
    ])
    t = tracker()
    events = feed(t, df)
    assert not [ev for _, ev in events if isinstance(ev, RetestEvent)]
    assert t.fvgs[0].status == FVGStatus.CONSUMED


def test_fvg_expiry():
    bars = _bullish_fvg_bars() + [(102.3, 102.5, 102.0, 102.4)] * 12
    df = make_df(bars)
    t = tracker(fvg_max_age_bars=10)
    feed(t, df)
    assert t.fvgs[0].status == FVGStatus.EXPIRED


def test_unmitigated_scan():
    # one bullish FVG never revisited -> unmitigated
    df = make_df(_bullish_fvg_bars() + [(102.3, 103, 102.2, 102.8)])
    zones = detect_unmitigated_fvgs(df, TICK, min_gap_ticks=4)
    assert len(zones) == 1
    assert zones[0].bottom == 100 and zones[0].top == 101.5
    assert zones[0].status == FVGStatus.ACTIVE
