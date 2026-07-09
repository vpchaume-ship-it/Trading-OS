"""Filtres du modèle utilisateur : sweep de niveau de session + V-shape."""

import pandas as pd

from tests.conftest import make_df
from tests.test_engine import SETUP_BARS, cfg
from trading_os.backtest.engine import run_backtest

# retest puis cible atteinte (mêmes barres que test_engine)
FILL_BARS = [(99.2, 100.3, 99.1, 99.9), (99.9, 100.0, 95.9, 96.2)]


def two_days(day1_high: float) -> pd.DataFrame:
    """Jour 1 : range calme dont le plus haut = PDH ; jour 2 : le scénario IFVG
    short (c3 monte à 102.5 — au-dessus ou non du PDH selon day1_high)."""
    day1 = [(100.0, day1_high, 99.5, 100.5)] + [(100.0, 100.8, 99.5, 100.5)] * 4
    return pd.concat([make_df(day1, start="2024-03-04 09:30"),
                      make_df(SETUP_BARS + FILL_BARS, start="2024-03-05 09:30")])


def test_session_sweep_pass_when_pdh_raided():
    # PDH 101 < 102.5 : la montée qui forme le FVG balaye le niveau de la veille
    df = two_days(day1_high=101.0)
    res = run_backtest(df, cfg(setup={"require_sweep": True, "sweep_mode": "session"}), "ES")
    assert len(res.trades) == 1
    assert res.trades.iloc[0]["direction"] == "bearish"
    assert res.skipped_no_session_sweep == 0


def test_session_sweep_blocks_without_raid():
    # PDH 200 : aucun niveau de session précédente n'est balayé -> pas de trade
    df = two_days(day1_high=200.0)
    res = run_backtest(df, cfg(setup={"require_sweep": True, "sweep_mode": "session"}), "ES")
    assert res.trades.empty
    assert res.skipped_no_session_sweep >= 1


def test_vshape_pass_on_sharp_reversal():
    # extrême 102.5 -> clôture d'inversion 99.6 = 11.6 ticks en 1 barre
    df = make_df(SETUP_BARS + FILL_BARS, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(setup={"require_vshape": True, "vshape_max_bars": 8,
                                      "vshape_min_move_ticks": 10}), "ES")
    assert len(res.trades) == 1
    assert res.skipped_no_vshape == 0


def test_vshape_blocks_shallow_reversal():
    # même renversement mais seuil à 20 ticks : trop peu ample -> filtré
    df = make_df(SETUP_BARS + FILL_BARS, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(setup={"require_vshape": True, "vshape_max_bars": 8,
                                      "vshape_min_move_ticks": 20}), "ES")
    assert res.trades.empty
    assert res.skipped_no_vshape >= 1
