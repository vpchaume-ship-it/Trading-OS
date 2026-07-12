"""École des presque — mesure ce que la config gelée REJETTE de peu.

Idée (demande utilisateur) : le socle gelé ne prend que 25 trades/24 mois car
il exige un V ≥ 20 ticks, un RR ≥ 2 et le 1er setup du jour. Beaucoup de setups
échouent d'un cheveu à UN seul de ces critères. On les mesure séparément :

  * on relance le moteur avec des seuils ASSOUPLIS (V ≥ 12, RR ≥ 1.5, 2/jour) —
    run SÉPARÉ, le socle gelé n'est jamais touché ;
  * chaque trade porte ses métriques (vs_ticks, tgt_rr, nth_of_day) ;
  * pour chaque dimension, on isole la cohorte « presque » = les trades qui
    passeraient si on relâchait CETTE dimension seule (les autres restant au
    niveau gelé). C'est l'unité de promotion : « relâcher le V à 15 ticks
    ajoute N trades qui ont fait Y ».

Une cohorte n'est promue que sur évidence (≥ MIN_TRADES et espérance positive) —
la promotion elle-même reste une décision humaine/LLM, jamais automatique sur le
socle gelé. Ce module ne fait que MESURER et proposer.
"""

from __future__ import annotations

import copy

import pandas as pd

from trading_os.backtest.engine import run_backtest
from trading_os.backtest.metrics import summary

# Seuils gelés (le socle) — lus depuis la config au runtime, défauts ici.
FROZEN = {"vs_ticks": 20.0, "tgt_rr": 2.0, "nth": 1}
# Planchers du run assoupli : jusqu'où on ose regarder.
RELAX = {"vs_ticks": 12.0, "tgt_rr": 1.5, "nth": 2}
MIN_TRADES = 8          # évidence minimale pour proposer une promotion
MIN_EXPECTANCY = 0.10   # R/trade net


def _relaxed_cfg(cfg: dict) -> dict:
    c = copy.deepcopy(cfg)
    s = c["ifvg"].setdefault("setup", {})
    s["vshape_min_move_ticks"] = RELAX["vs_ticks"]
    c["ifvg"]["target"]["liquidity_min_rr"] = RELAX["tgt_rr"]
    c["ifvg"]["max_trades_per_day"] = RELAX["nth"]
    return c


def _frozen_of(cfg: dict) -> dict:
    s = cfg["ifvg"].get("setup", {})
    return {"vs_ticks": float(s.get("vshape_min_move_ticks", FROZEN["vs_ticks"])),
            "tgt_rr": float(cfg["ifvg"]["target"].get("liquidity_min_rr", FROZEN["tgt_rr"])),
            "nth": int(cfg["ifvg"].get("max_trades_per_day", FROZEN["nth"]) or FROZEN["nth"])}


def _cohort(t: pd.DataFrame, dim: str, fr: dict):
    """Trades qui passeraient en relâchant `dim` SEULE (autres dims au gel)."""
    others_ok = pd.Series(True, index=t.index)
    if dim != "vs_ticks":
        others_ok &= t["vs_ticks"] >= fr["vs_ticks"]
    if dim != "tgt_rr":
        others_ok &= t["tgt_rr"] >= fr["tgt_rr"]
    if dim != "nth":
        others_ok &= t["nth_of_day"] <= fr["nth"]
    if dim == "vs_ticks":
        near = (t["vs_ticks"] >= RELAX["vs_ticks"]) & (t["vs_ticks"] < fr["vs_ticks"])
    elif dim == "tgt_rr":
        near = (t["tgt_rr"] >= RELAX["tgt_rr"]) & (t["tgt_rr"] < fr["tgt_rr"])
    else:
        near = (t["nth_of_day"] > fr["nth"]) & (t["nth_of_day"] <= RELAX["nth"])
    return t[others_ok & near]


LABELS = {"vs_ticks": "V-shape plus mou (12–20 ticks)",
          "tgt_rr": "RR plus court (1.5–2)",
          "nth": "2ᵉ setup du jour"}


def analyse(cfg: dict, instrument: str, directory: str = "data") -> dict | None:
    """Retourne {frozen: stats socle, cohorts: [...]} ou None si pas de données."""
    from trading_os.webapp.stats import load_smt_sibling, select_backtest_df
    months = cfg.get("backtest", {}).get("history_months")
    df, tf, _ = select_backtest_df(instrument, directory, months=months)
    if df is None:
        return None
    fr = _frozen_of(cfg)
    c = _relaxed_cfg(cfg)
    c["ifvg"]["timeframe"] = tf
    sib = load_smt_sibling(c, instrument, directory)
    res = run_backtest(df, c, instrument, sib_df=sib)
    t = res.trades
    if t.empty or "vs_ticks" not in t.columns:
        return None
    # socle = ce qui passe TOUS les seuils gelés
    core = t[(t["vs_ticks"] >= fr["vs_ticks"]) & (t["tgt_rr"] >= fr["tgt_rr"])
             & (t["nth_of_day"] <= fr["nth"])]
    cohorts = []
    for dim in ("vs_ticks", "tgt_rr", "nth"):
        g = _cohort(t, dim, fr)
        s = summary(g) if not g.empty else {"n_trades": 0}
        promotable = (s.get("n_trades", 0) >= MIN_TRADES
                      and s.get("expectancy_r", 0) >= MIN_EXPECTANCY)
        cohorts.append({"dim": dim, "label": LABELS[dim], "stats": s,
                        "promotable": promotable})
    cohorts.sort(key=lambda co: (co["promotable"], co["stats"].get("n_trades", 0)),
                 reverse=True)
    return {"frozen": summary(core) if not core.empty else {"n_trades": 0},
            "cohorts": cohorts, "min_trades": MIN_TRADES}


PATH = "data/nearmiss.json"


def save(result: dict | None, path: str = PATH) -> None:
    import json
    from pathlib import Path
    if result is None:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # stats numpy -> float pour un JSON propre
    clean = {"frozen": {k: (float(v) if isinstance(v, (int, float)) else v)
                        for k, v in result["frozen"].items()},
             "min_trades": result["min_trades"],
             "cohorts": [{"dim": co["dim"], "label": co["label"],
                          "promotable": bool(co["promotable"]),
                          "stats": {k: (float(v) if isinstance(v, (int, float)) else v)
                                    for k, v in co["stats"].items()}}
                         for co in result["cohorts"]]}
    p.write_text(json.dumps(clean, ensure_ascii=False), encoding="utf-8")


def load(path: str = PATH) -> dict | None:
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
