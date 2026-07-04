"""Multi-timeframe bias signals and trading-day status."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from tests.conftest import make_df
from trading_os.premarket.mtf_bias import (_label, _momentum, _structure,
                                           day_status)

NY = ZoneInfo("America/New_York")


def test_structure_bullish_hh_hl():
    # ascending zigzag -> HH + HL with strength 1
    lows = [100, 98, 102, 100.5, 104, 102.5, 106]
    bars = [(l + 0.5, l + 2, l, l + 1.5) for l in lows]
    df = make_df(bars)
    assert _structure(df, strength=1).vote == 1


def test_structure_bearish_ll_lh():
    # descending zigzag -> LH + LL (monotonic bars have no swings at all)
    lows = [106, 103, 104.5, 100, 101.5, 97, 98.5]
    bars = [(l + 2.5, l + 3, l, l + 0.7) for l in lows]
    df = make_df(bars)
    assert _structure(df, strength=1).vote == -1


def test_momentum_displacement():
    df = make_df([(100, 101, 99, 100.5), (100.5, 101.5, 100, 101), (101, 102.5, 100.8, 102)])
    assert _momentum(df).vote == 1          # close 102 > prev high 101.5
    df2 = make_df([(100, 101, 99, 100.5), (100.5, 101.5, 100, 101), (101, 101.2, 99.0, 99.5)])
    assert _momentum(df2).vote == -1        # close 99.5 < prev low 100


def test_label_thresholds():
    assert _label(2) == "haussier" and _label(3) == "haussier"
    assert _label(-2) == "baissier"
    for s in (-1, 0, 1):
        assert _label(s) == "neutre"        # un seul signal ne suffit pas


def test_day_status_weekend():
    sat = datetime(2026, 7, 4, 10, 0, tzinfo=NY)
    assert day_status(sat)[0] == "closed"
    sun_evening = datetime(2026, 7, 5, 19, 0, tzinfo=NY)
    assert day_status(sun_evening)[0] == "trading"


def test_day_status_holiday_and_normal():
    # 3 juillet 2026 = Independence Day observé (NYSE fermé)
    holiday = datetime(2026, 7, 3, 10, 0, tzinfo=NY)
    kind, label = day_status(holiday)
    assert kind == "closed" and "FÉRIÉ" in label
    normal = datetime(2026, 7, 1, 10, 0, tzinfo=NY)  # mercredi
    assert day_status(normal)[0] == "trading"
