"""SMT divergence signal and prop-firm evaluation simulator."""

import pandas as pd

from tests.conftest import make_df
from trading_os.premarket.mtf_bias import _smt
from trading_os.webapp.propsim import DEFAULT_RULES, simulate


def _frame(lows, highs):
    """40-bar frame with explicit per-bar low/high (open/close held mid-range)."""
    bars = [(105, h, l, 105) for l, h in zip(lows, highs)]
    return make_df(bars)


def test_smt_bullish_divergence():
    # self prints a LOWER low in the 2nd window; sibling does NOT; highs identical.
    highs = [110] * 40
    self_df = _frame([100] * 20 + [95] + [100] * 19, highs)   # lower low at 95
    sib_df = _frame([100] * 40, highs)                        # sibling holds its low
    assert _smt(self_df, sib_df, "NQ", window=20).vote == 1


def test_smt_bearish_divergence():
    # self prints a HIGHER high in the 2nd window; sibling does NOT; lows identical.
    lows = [100] * 40
    self_df = _frame(lows, [110] * 20 + [115] + [110] * 19)   # higher high at 115
    sib_df = _frame(lows, [110] * 40)
    assert _smt(self_df, sib_df, "ES", window=20).vote == -1


def test_smt_no_signal_when_both_move():
    highs = [110] * 40
    both = _frame([100] * 20 + [95] + [100] * 19, highs)
    assert _smt(both, both.copy(), "NQ", window=20).vote == 0


def test_smt_no_sibling():
    df = _frame([100] * 20 + [95] + [100] * 19, [110] * 40)
    assert _smt(df, None, "NQ").vote == 0


ES_SPEC = {"tick_size": 0.25, "tick_value": 12.50, "micro_tick_value": 1.25}


def _trades(pnls, days):
    """Minimal trades frame: pnl_usd is for 1 MINI; risk 8 ticks."""
    rows = []
    for pnl, day in zip(pnls, days):
        rows.append({"exit_time": pd.Timestamp(f"2026-05-{day:02d} 10:00"),
                     "pnl_usd": pnl, "risk_ticks": 8})
    return pd.DataFrame(rows)


def test_propsim_passes_target():
    # big mini wins -> scaled to micros should still clear $3000 over >=2 days
    trades = _trades([2000, 2000, 2000], [1, 2, 3])
    res = simulate(trades, ES_SPEC)
    assert res.status in ("reussie", "en_cours")
    assert res.final_pnl > 0


def test_propsim_fails_on_max_loss():
    trades = _trades([-3000, -3000], [1, 2])
    res = simulate(trades, ES_SPEC)
    assert res.status == "echouee"
    assert "Max Loss Limit" in res.detail


def test_propsim_none_when_empty():
    assert simulate(pd.DataFrame(), ES_SPEC) is None


def test_propsim_micro_cap_respected():
    trades = _trades([500] * 5, [1, 2, 3, 4, 5])
    res = simulate(trades, ES_SPEC, {"max_micros": 3, "risk_per_trade_usd": 10_000})
    assert res.avg_micros <= 3
