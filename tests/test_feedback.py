"""Boucle d'auto-ajustement : garde-fous durs, évidence, réversibilité."""

import pandas as pd
import pytest

from tests.conftest import make_df
from tests.test_engine import SETUP_BARS, cfg
from trading_os.backtest import feedback
from trading_os.backtest.diagnose import daily_review
from trading_os.backtest.engine import run_backtest

BASE = {"stop_buffer_ticks": 2, "liquidity_min_rr": 2.0}


def review_stub(**kw):
    rv = {"n_total": 40, "n_long": 30, "n_short": 8,
          "long": {"n": 30, "win_rate": 0.4, "expectancy_r": 0.5, "pf": 1.8},
          "short": {"n": 8, "win_rate": 0.4, "expectancy_r": 0.5, "pf": 1.8},
          "last10_sum": 2.0, "dd_long_r": -2.0, "at_equity_high": False,
          "by_bucket": {"09:30-10:30": {"n": 10, "pf": 1.5, "win_rate": .5, "expectancy_r": .6},
                        "10:30-11:30": {"n": 10, "pf": 1.4, "win_rate": .5, "expectancy_r": .5}},
          "n_losers_long": 5, "same_bar_stop_share": 0.1,
          "low_rr": {"n": 10, "pf": 1.5, "win_rate": .5, "expectancy_r": .4},
          "high_rr": {"n": 10, "pf": 1.5, "win_rate": .5, "expectancy_r": .4},
          "ntz": {"n": 0, "pf": 0, "win_rate": 0, "expectancy_r": 0}, "bullets": []}
    rv.update(kw)
    return rv


def test_frozen_core_rejected():
    with pytest.raises(ValueError):
        feedback.clamp("sweep_mode", "swing")     # socle gelé
    with pytest.raises(ValueError):
        feedback.clamp("require_vshape", False)


def test_clamp_bounds():
    assert feedback.clamp("stop_buffer_ticks", 99) == 6
    assert feedback.clamp("risk_scale", 2.0) == 1.0      # jamais > 1×
    assert feedback.clamp("liquidity_min_rr", 0.5) == 1.5
    with pytest.raises(ValueError):
        feedback.clamp("entry_window", {"start": "09:30", "end": "10:00"})  # < 60 min


def test_drawdown_throttle_then_restore():
    st = {"active": {}, "history": []}
    st, notes = feedback.step(review_stub(last10_sum=-4.0), st, BASE, today="2026-07-11")
    assert st["active"]["risk_scale"] == 0.5 and notes
    # drawdown résorbé -> restauration
    st, notes = feedback.step(review_stub(at_equity_high=True, last10_sum=1.5),
                              st, BASE, today="2026-07-14")
    assert "risk_scale" not in st["active"]
    assert st["history"][0]["status"] == "annulé"


def test_bucket_filter_needs_evidence():
    weak = review_stub(by_bucket={
        "09:30-10:30": {"n": 5, "pf": 0.3, "win_rate": .2, "expectancy_r": -1},
        "10:30-11:30": {"n": 5, "pf": 2.0, "win_rate": .6, "expectancy_r": 1}})
    st, _ = feedback.step(weak, {"active": {}, "history": []}, BASE, today="2026-07-11")
    assert "entry_window" not in st["active"]      # n < 8 -> pas d'action
    strong = review_stub(by_bucket={
        "09:30-10:30": {"n": 9, "pf": 0.5, "win_rate": .2, "expectancy_r": -1},
        "10:30-11:30": {"n": 9, "pf": 1.6, "win_rate": .6, "expectancy_r": 1}})
    st, _ = feedback.step(strong, {"active": {}, "history": []}, BASE, today="2026-07-11")
    assert st["active"]["entry_window"] == {"start": "10:30", "end": "11:30"}


def test_one_decision_per_day():
    rv = review_stub(last10_sum=-4.0, same_bar_stop_share=0.6, n_losers_long=10)
    st, _ = feedback.step(rv, {"active": {}, "history": []}, BASE, today="2026-07-11")
    assert len([h for h in st["history"] if h["status"] == "active"]) == 1
    # même jour, second passage : rien de neuf
    st, _ = feedback.step(rv, st, BASE, today="2026-07-11")
    assert len(st["history"]) == 1


def test_window_expiry():
    st = {"active": {"entry_window": {"start": "09:30", "end": "10:30"}},
          "history": [{"date": "2026-06-01", "key": "entry_window", "from": None,
                       "to": {"start": "09:30", "end": "10:30"}, "reason": "x",
                       "evidence": "x", "status": "active", "n_at_adoption": 10,
                       "exp_at_adoption": 0.5}]}
    st, notes = feedback.step(review_stub(), st, BASE, today="2026-07-11")
    assert "entry_window" not in st["active"] and st["history"][0]["status"] == "annulé"


def test_antioverfit_revert():
    st = {"active": {"stop_buffer_ticks": 3},
          "history": [{"date": "2026-07-01", "key": "stop_buffer_ticks", "from": 2,
                       "to": 3, "reason": "x", "evidence": "x", "status": "active",
                       "n_at_adoption": 20, "exp_at_adoption": 0.9}]}
    rv = review_stub(n_total=35)                     # 15 nouveaux trades
    rv["long"]["expectancy_r"] = 0.3                 # -0.6 R vs adoption
    st, _ = feedback.step(rv, st, BASE, today="2026-07-11")
    assert "stop_buffer_ticks" not in st["active"]


def test_engine_entry_window_blocks_trades():
    bars = SETUP_BARS + [(99.2, 100.3, 99.1, 99.9), (99.9, 100.0, 95.9, 96.2)]
    df = make_df(bars, start="2024-03-04 09:30")
    c = cfg(entry_window={"start": "08:30", "end": "09:00"})   # retest hors fenêtre
    res = run_backtest(df, c, "ES")
    assert res.trades.empty and res.skipped_entry_window >= 1


def test_daily_review_on_synthetic_trades():
    now = pd.Timestamp("2026-07-10 10:00", tz="America/New_York")
    t = pd.DataFrame({
        "entry_time": [now - pd.Timedelta(days=i) for i in range(12)],
        "exit_time": [now - pd.Timedelta(days=i) for i in range(12)],
        "net_r": [1.5, -1, 1.2, -1, 2.0, -1, 1.1, -1, 1.8, -1, 1.4, -1],
        "exit_reason": ["target", "stop"] * 6,
        "entry": [100.0] * 12, "stop": [99.0] * 12, "target": [103.0] * 12,
        "in_ntz": [False] * 12})
    rv = daily_review(t)
    assert rv is not None and rv["n_total"] == 12 and rv["bullets"]
