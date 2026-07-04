"""Backtest engine tests on synthetic scenarios (fills, costs, filters)."""

import pandas as pd
import pytest

from tests.conftest import make_df
from trading_os.backtest.engine import run_backtest


def cfg(**overrides):
    base = {
        "instruments": {"ES": {"tick_size": 0.25, "tick_value": 12.50,
                               "micro_tick_value": 1.25, "mt5_symbol": "ES"}},
        "killzones": {"london": {"start": "02:00", "end": "05:00"},
                      "ny_am": {"start": "08:30", "end": "11:00"},
                      "ny_pm": {"start": "13:30", "end": "16:00"}},
        "ifvg": {"timeframe": "1min", "min_gap_ticks": 4, "invalidation_mode": "close",
                 "wick_fill_kills": True, "fvg_max_age_bars": 1000,
                 "ifvg_max_age_bars": 1000, "retest_entry": "proximal",
                 "stop_buffer_ticks": 2, "max_retests_per_zone": 1,
                 "allowed_killzones": ["london", "ny_am", "ny_pm"],
                 "target": {"mode": "fixed_rr", "fixed_rr": 2.0,
                            "liquidity_min_rr": 1.5, "swing_strength": 3}},
        "backtest": {"instrument": "ES", "contract": "mini", "csv_file": "",
                     "eod_flat_time": "16:55",
                     "costs": {"commission_per_side": {"mini": 2.25, "micro": 0.85},
                               "slippage_ticks_stop": 1, "slippage_ticks_entry": 0},
                     "respect_no_trade_zones": True, "news_history_csv": ""},
        "news": {"no_trade_zone": {"minutes_before": 30, "minutes_after": 15}},
    }
    base["ifvg"].update(overrides)
    return base


# Bullish FVG [100, 101.5] then inversion -> bearish IFVG, short setup:
# entry proximal 100.00, stop 101.5 + 2 ticks = 102.00 (risk 8 ticks), target RR2 = 96.00
SETUP_BARS = [
    (99, 100, 98.5, 99.8),          # c1
    (100, 101.6, 99.9, 101.5),      # c2
    (101.6, 102.5, 101.5, 102.3),   # c3 -> FVG formed
    (102.3, 102.4, 99.5, 99.6),     # decisive close below 100 -> inversion
    (99.6, 99.8, 99.0, 99.2),       # drift, no touch
]


def test_short_trade_hits_target():
    bars = SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),  # retest -> limit short filled at 100.00
        (99.9, 100.0, 95.9, 96.2),  # target 96 hit
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(), "ES")
    assert len(res.trades) == 1
    t = res.trades.iloc[0]
    assert t["direction"] == "bearish"
    assert t["entry"] == 100.0 and t["stop"] == 102.0 and t["target"] == 96.0
    assert t["exit_reason"] == "target"
    assert t["gross_r"] == pytest.approx(2.0)
    # net: +16 ticks * 12.5$ - 4.5$ commission / (8 ticks * 12.5$) = 1.955
    assert t["net_r"] == pytest.approx(1.955)
    assert t["killzone"] == "ny_am"


def test_no_fill_on_inversion_bar_itself():
    """The inversion bar's own high must not fill the order (no lookahead)."""
    bars = SETUP_BARS + [(99.2, 100.3, 99.1, 99.9), (99.9, 100.0, 95.9, 96.2)]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(), "ES")
    # entry must happen on the retest bar (index 5), not on the inversion bar (index 3)
    assert res.trades.iloc[0]["entry_time"] == df.index[5]


def test_conservative_stop_when_bar_hits_both():
    bars = SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),   # fill short at 100
        (99.9, 102.5, 95.0, 96.0),   # bar crosses BOTH stop (102) and target (96)
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(), "ES")
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop"
    # stop 102 + 1 tick slippage = 102.25 -> -9 ticks; net_r = (-9*12.5 - 4.5)/100
    assert t["exit_price"] == pytest.approx(102.25)
    assert t["net_r"] == pytest.approx(-1.17)


def test_same_bar_stop_on_entry_bar():
    bars = SETUP_BARS + [
        (99.2, 102.6, 99.1, 99.9),   # retest fills at 100 AND high crosses stop 102
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(), "ES")
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop"
    assert t["entry_time"] == t["exit_time"]


def test_retest_outside_killzone_is_skipped():
    # retest at 12:35 NY (between ny_am and ny_pm) -> setup consumed, no trade
    bars = SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),
        (99.9, 100.0, 95.9, 96.2),
    ]
    df = make_df(bars, start="2024-03-04 12:30")
    res = run_backtest(df, cfg(), "ES")
    assert res.trades.empty


def test_eod_flat_closes_open_position():
    bars = SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),   # fill short at 100 (15:35 with start below)
        (99.9, 100.0, 99.5, 99.8),
        (99.8, 99.9, 99.4, 99.5),    # 16:55+ -> forced flat (never hit stop/target)
    ] + [(99.5, 99.6, 99.3, 99.4)] * 80
    df = make_df(bars, start="2024-03-04 15:30")
    res = run_backtest(df, cfg(), "ES")
    assert len(res.trades) == 1
    assert res.trades.iloc[0]["exit_reason"] == "eod_flat"
