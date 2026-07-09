"""Stabilité de l'edge + historique d'auto-réglage (évolution du dashboard)."""

import pandas as pd

from trading_os.backtest.metrics import stability
from trading_os.webapp.insights import append_history, load_history


def trades_r(rs):
    return pd.DataFrame({"net_r": rs})


def test_stability_needs_enough_trades():
    assert stability(trades_r([1.0] * 7)) is None


def test_stability_detects_degradation():
    # première moitié gagnante, seconde perdante -> edge dégradé
    st = stability(trades_r([2.0, 2.0, 1.5, 2.0, -1.0, -1.0, -1.0, -1.0]))
    assert st["verdict"] == "degrade"
    assert st["first"]["win_rate"] == 1.0 and st["second"]["win_rate"] == 0.0


def test_stability_stable_edge():
    st = stability(trades_r([1.0, -1.0, 2.0, -1.0, 1.0, -1.0, 2.0, -1.0]))
    assert st["verdict"] in ("stable", "renforce", "faiblit")


def test_history_append_and_same_day_replace(tmp_path):
    p = str(tmp_path / "hist.csv")
    state = {"NQ": {"variant": "V1", "patch": {}}}
    bt = {"NQ": {"stats": {"n_trades": 30, "win_rate": 0.47,
                           "expectancy_r": 1.58, "profit_factor": 3.64,
                           "total_r": 47.4}}}
    append_history(state, bt, path=p)
    append_history(state, bt, path=p)          # rebuild du même jour
    h = load_history(p)
    assert len(h) == 1                          # remplacé, pas dupliqué
    assert h.iloc[0]["variant"] == "V1" and h.iloc[0]["n_trades"] == 30


def test_history_absent_file(tmp_path):
    assert load_history(str(tmp_path / "nope.csv")) is None
