"""Exit-management modes: break-even and trailing stop."""

import pytest

from tests.conftest import make_df
from tests.test_engine import SETUP_BARS, cfg
from trading_os.backtest.engine import run_backtest


def exit_cfg(mode, **kw):
    c = cfg()
    c["ifvg"]["exit"] = {"mode": mode, "be_trigger_rr": 1.0, "trail_rr": 1.0, **kw}
    return c


# Short IFVG: entry 100.00, initial stop 102.00 (risk 2.0 = 8 ticks), RR2 target 96.00.

def test_break_even_moves_stop_to_entry():
    # price reaches +1R (98.00) on one bar, then rallies back to 100 next bar
    bars = SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),   # fill short at 100
        (99.9, 100.0, 97.9, 98.5),   # best 97.9 <= 99 (entry - 1R) -> BE armed
        (98.5, 100.6, 98.4, 100.4),  # comes back up, hits BE stop at 100.00
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, exit_cfg("be"), "ES")
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop"
    # BE stop at entry 100 + 1 tick slippage = 100.25 -> tiny loss, not full -1R
    assert t["exit_price"] == pytest.approx(100.25)
    assert -0.2 < t["net_r"] < 0.0


def test_trail_locks_profit_and_ignores_target():
    bars = SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),   # fill short at 100
        (99.9, 100.0, 96.5, 97.0),   # best 96.5; trail stop = 96.5 + 1R(2.0) = 98.5
        (97.0, 99.0, 96.8, 98.9),    # rallies to 99 -> hits trail stop 98.5
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, exit_cfg("trail"), "ES")
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "stop"          # trail never takes the fixed target
    # trail stop 98.5 + 1 tick slippage 0.25 = 98.75 -> +1.25 in price = +0.625R gross
    assert t["exit_price"] == pytest.approx(98.75)
    assert t["gross_r"] == pytest.approx((100 - 98.75) / 2.0)


def test_full_mode_unchanged():
    bars = SETUP_BARS + [(99.2, 100.3, 99.1, 99.9), (99.9, 100.0, 95.9, 96.2)]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, exit_cfg("full"), "ES")
    assert res.trades.iloc[0]["exit_reason"] == "target"
