"""Walk-forward (sélection train figée sur test) + maths des séries perdantes."""

import numpy as np
import pandas as pd

from trading_os.backtest import risklab
from trading_os.backtest.walkforward import walk_forward


def stream(days_r: dict[int, float], start="2026-01-05") -> pd.DataFrame:
    """Un trade par jour ouvré : {jour_index: net_r}."""
    base = pd.Timestamp(start, tz="America/New_York")
    rows = []
    for d, r in days_r.items():
        t = base + pd.Timedelta(days=d, hours=10)
        rows.append({"entry_time": t, "exit_time": t, "net_r": r,
                     "exit_reason": "target" if r > 0 else "stop",
                     "entry": 100.0, "stop": 99.0, "target": 103.0,
                     "in_ntz": False, "pnl_usd": r * 100})
    return pd.DataFrame(rows)


def test_walkforward_selects_on_train_and_freezes_on_test():
    # variante A : gagnante pendant le train du pli 1 (jours 0-29), perdante après
    a = stream({**{d: 1.5 for d in range(0, 26, 2)},        # 13 wins sur le train
                **{d: -1.0 for d in range(30, 40, 2)}})     # test : 5 pertes
    # variante B : perdante sur le train (ne doit pas être choisie au pli 1)
    b = stream({**{d: -1.0 for d in range(0, 26, 2)},
                **{d: 2.0 for d in range(30, 40, 2)}})
    wf = walk_forward({"A": a, "B": b}, "NQ", train_days=30, test_days=10)
    assert wf is not None and wf["folds"]
    f1 = wf["folds"][0]
    assert f1["variant"] == "A"                  # choisie sur le train…
    assert f1["n_test"] == 5 and f1["test_total_r"] < 0   # …et FIGÉE sur le test
    # les trades OOS du pli 1 sont bien ceux de A (pertes), pas ceux de B
    et = pd.to_datetime(wf["trades"]["exit_time"])
    fold1 = wf["trades"][(et >= f1["test_start"]) & (et < f1["test_end"])]
    assert (fold1["net_r"] < 0).all()


def test_walkforward_fallback_fold_trades_nothing():
    # aucun flux ne passe les garde-fous sur le train -> pli « prudence », 0 trade
    # (le flux continue dans la fenêtre test : ces trades ne doivent PAS compter)
    a = stream({**{d: -1.0 for d in range(0, 26, 2)}, 32: -1.0, 36: 2.0})
    wf = walk_forward({"A": a}, "NQ", train_days=30, test_days=10)
    assert wf is not None
    assert all(f["fallback"] for f in wf["folds"])
    assert wf["stats"]["n_trades"] == 0


def test_walkforward_none_without_full_fold():
    a = stream({d: 1.0 for d in range(5)})       # 5 jours < 30 j de train
    assert walk_forward({"A": a}, "NQ") is None


# ---- risklab ----------------------------------------------------------------

def test_p_streak_bounds():
    assert risklab.p_streak(1, 10, wr=1.0) == 0.0          # jamais de perte
    assert risklab.p_streak(3, 3, wr=0.0) == 1.0           # que des pertes
    # WR 20 % : 10 pertes d'affilée sur 100 trades = fréquent, 35 = rare
    assert risklab.p_streak(10, 100, 0.20) > 0.5
    assert risklab.p_streak(25, 100, 0.20) < 0.10   # queue, mais pas exceptionnel
    assert risklab.p_streak(35, 100, 0.20) < 0.01


def test_streak_p99_monotonic_in_wr():
    assert risklab.streak_p99(100, 0.20) > risklab.streak_p99(100, 0.50)


def test_recommended_risk_respects_hard_bounds_and_survival():
    rec = risklab.recommended_risk_usd(wr=0.20, loss_budget_usd=2000)
    assert risklab.RISK_FLOOR_USD <= rec["risk_usd"] <= risklab.HARD_RISK_CAP_USD
    assert rec["survives"] >= risklab.SURVIVE_STREAK_MIN
    # même un WR fantaisiste ne dépasse jamais le plafond dur
    rec_hi = risklab.recommended_risk_usd(wr=0.95, loss_budget_usd=100_000)
    assert rec_hi["risk_usd"] <= risklab.HARD_RISK_CAP_USD


def test_streak_alert_levels():
    t_ok = stream({0: 2.0, 1: -1.0})
    assert risklab.streak_alert(t_ok, wr=0.20)["level"] == "ok"
    # au niveau attendu (~21) -> attention ; au-delà du p99 (~30+) -> alerte
    t_warn = stream({d: -1.0 for d in range(22)})
    assert risklab.streak_alert(t_warn, wr=0.20)["level"] == "attention"
    t_bad = stream({d: -1.0 for d in range(40)})
    al = risklab.streak_alert(t_bad, wr=0.20)
    assert al["current"] == 40 and al["level"] == "alerte"
