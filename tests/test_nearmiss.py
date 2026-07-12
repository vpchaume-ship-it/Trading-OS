"""École des presque : cohortes = trades ajoutés en relâchant 1 critère seul."""

import pandas as pd

from trading_os.backtest import nearmiss


def trades(rows):
    return pd.DataFrame(rows)


FR = {"vs_ticks": 20.0, "tgt_rr": 2.0, "nth": 1}


def test_vshape_cohort_isolates_only_weak_v():
    t = trades([
        {"vs_ticks": 15, "tgt_rr": 2.5, "nth_of_day": 1, "net_r": 1.0},   # V mou seul -> cohorte
        {"vs_ticks": 25, "tgt_rr": 2.5, "nth_of_day": 1, "net_r": 1.0},   # socle -> exclu
        {"vs_ticks": 15, "tgt_rr": 1.6, "nth_of_day": 1, "net_r": 1.0},   # V mou ET RR court -> exclu
        {"vs_ticks": 10, "tgt_rr": 2.5, "nth_of_day": 1, "net_r": 1.0},   # V sous le plancher -> exclu
    ])
    g = nearmiss._cohort(t, "vs_ticks", FR)
    assert len(g) == 1 and g.iloc[0]["vs_ticks"] == 15


def test_nth_cohort_isolates_second_of_day():
    t = trades([
        {"vs_ticks": 25, "tgt_rr": 2.5, "nth_of_day": 2, "net_r": -1.0},  # 2e du jour seul -> cohorte
        {"vs_ticks": 25, "tgt_rr": 2.5, "nth_of_day": 1, "net_r": 1.0},   # socle -> exclu
        {"vs_ticks": 25, "tgt_rr": 2.5, "nth_of_day": 3, "net_r": 1.0},   # au-delà du plancher (2) -> exclu
    ])
    g = nearmiss._cohort(t, "nth", FR)
    assert len(g) == 1 and g.iloc[0]["nth_of_day"] == 2


def test_rr_cohort_bounds():
    t = trades([
        {"vs_ticks": 25, "tgt_rr": 1.7, "nth_of_day": 1, "net_r": 1.0},   # RR court seul -> cohorte
        {"vs_ticks": 25, "tgt_rr": 1.3, "nth_of_day": 1, "net_r": 1.0},   # sous le plancher 1.5 -> exclu
        {"vs_ticks": 25, "tgt_rr": 2.5, "nth_of_day": 1, "net_r": 1.0},   # socle -> exclu
    ])
    g = nearmiss._cohort(t, "tgt_rr", FR)
    assert len(g) == 1 and g.iloc[0]["tgt_rr"] == 1.7


def test_frozen_thresholds_read_from_cfg():
    cfg = {"ifvg": {"setup": {"vshape_min_move_ticks": 18},
                    "target": {"liquidity_min_rr": 2.5}, "max_trades_per_day": 1}}
    fr = nearmiss._frozen_of(cfg)
    assert fr["vs_ticks"] == 18.0 and fr["tgt_rr"] == 2.5 and fr["nth"] == 1


def test_save_load_roundtrip(tmp_path):
    p = str(tmp_path / "nm.json")
    res = {"frozen": {"n_trades": 24, "win_rate": 0.42, "expectancy_r": 1.48},
           "min_trades": 8,
           "cohorts": [{"dim": "nth", "label": "2ᵉ setup du jour", "promotable": True,
                        "stats": {"n_trades": 9, "win_rate": 0.22, "expectancy_r": 0.43}}]}
    nearmiss.save(res, p)
    back = nearmiss.load(p)
    assert back["cohorts"][0]["promotable"] is True
    assert back["cohorts"][0]["stats"]["n_trades"] == 9
    assert nearmiss.load(str(tmp_path / "absent.json")) is None
