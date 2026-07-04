"""Liquidity-target mode (default per the user's methodology): the target is the
nearest CONFIRMED opposing swing, with a minimum-RR filter."""

import pytest

from tests.conftest import make_df
from tests.test_engine import SETUP_BARS, cfg
from trading_os.backtest.engine import run_backtest

# A confirmed swing low at 97.00 (strength 2: two higher lows on each side),
# formed well before the IFVG setup so it is usable without lookahead.
PRIOR_SWING_BARS = [
    (100.0, 100.5, 99.0, 99.5),
    (99.5, 100.0, 98.0, 98.5),
    (98.5, 99.0, 97.0, 98.0),    # swing low 97.00
    (98.0, 99.5, 97.5, 99.0),
    (99.0, 100.0, 98.5, 99.8),
]


def liquidity_cfg(min_rr: float):
    base = cfg()
    base["ifvg"]["target"] = {"mode": "liquidity", "fixed_rr": 2.0,
                              "liquidity_min_rr": min_rr, "swing_strength": 2}
    return base


def test_short_targets_prior_swing_low():
    bars = PRIOR_SWING_BARS + SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),   # retest -> short filled at 100.00
        (99.9, 100.0, 96.9, 97.5),   # sweeps the 97.00 target
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, liquidity_cfg(min_rr=1.5), "ES")
    assert len(res.trades) == 1
    t = res.trades.iloc[0]
    # entry 100, stop 102 (risk 2.0) -> target = swing low 97.00, RR = 1.5
    assert t["target"] == pytest.approx(97.0)
    assert t["exit_reason"] == "target"
    assert t["gross_r"] == pytest.approx(1.5)


def test_setup_skipped_when_rr_to_liquidity_too_low():
    bars = PRIOR_SWING_BARS + SETUP_BARS + [
        (99.2, 100.3, 99.1, 99.9),
        (99.9, 100.0, 96.9, 97.5),
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, liquidity_cfg(min_rr=2.0), "ES")  # 1.5 < 2.0 exigé
    assert res.trades.empty
    assert res.skipped_low_rr == 1
