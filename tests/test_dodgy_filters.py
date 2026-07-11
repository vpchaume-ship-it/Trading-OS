"""Filtres Dodgy : divergence SMT ES/NQ + discipline 1 trade/jour."""

import pandas as pd

from tests.conftest import make_df
from tests.test_engine import SETUP_BARS, cfg
from trading_os.backtest.engine import run_backtest

FILL = [(99.2, 100.3, 99.1, 99.9), (99.9, 100.0, 95.9, 96.2)]
FLAT = [(100.0, 100.8, 99.5, 100.5)] * 45   # préambule : fenêtres SMT complètes


def dfs(sib_new_high: bool):
    df = make_df(FLAT + SETUP_BARS + FILL, start="2024-03-04 08:35")
    if sib_new_high:   # ES fait AUSSI un nouveau plus-haut -> pas de divergence
        sib_bars = FLAT + [(100, 106.0 + i, 99.5, 101) for i in range(len(SETUP_BARS + FILL))]
    else:              # ES reste sous ses plus-hauts -> divergence (trap NQ seul)
        sib_bars = FLAT + [(100, 100.6, 99.5, 100.2)] * len(SETUP_BARS + FILL)
    sib = make_df(sib_bars, start="2024-03-04 08:35")
    return df, sib


def test_smt_divergence_validates_setup():
    df, sib = dfs(sib_new_high=False)
    res = run_backtest(df, cfg(setup={"require_smt": True}), "ES", sib_df=sib)
    assert len(res.trades) == 1 and res.skipped_no_smt == 0


def test_smt_no_divergence_blocks_setup():
    df, sib = dfs(sib_new_high=True)
    res = run_backtest(df, cfg(setup={"require_smt": True}), "ES", sib_df=sib)
    assert res.trades.empty and res.skipped_no_smt >= 1


def test_smt_inactive_without_sibling():
    df, _ = dfs(sib_new_high=True)
    res = run_backtest(df, cfg(setup={"require_smt": True}), "ES", sib_df=None)
    assert len(res.trades) == 1      # pas de données ES -> filtre inactif


def test_daily_cap_limits_to_one_trade():
    seq = SETUP_BARS + FILL
    df = make_df(FLAT + seq + seq, start="2024-03-04 08:35")   # 2 setups le même jour
    res0 = run_backtest(df, cfg(max_trades_per_day=0), "ES")
    res1 = run_backtest(df, cfg(max_trades_per_day=1), "ES")
    assert len(res0.trades) == 2
    assert len(res1.trades) == 1 and res1.skipped_daily_cap >= 1
