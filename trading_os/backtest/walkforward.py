"""Validation walk-forward glissante — supprime le biais de sélection in-sample.

Principe : la fenêtre avance par plis (folds). Sur chaque pli, les TRAIN_DAYS
premiers jours servent à choisir la variante (mêmes garde-fous que l'autotune) ;
la variante choisie est alors FIGÉE et ses trades des TEST_DAYS suivants sont
collectés tels quels. Les métriques affichées en tête de dashboard sont le
cumul de ces fenêtres out-of-sample UNIQUEMENT — jamais vues par la sélection.

Architecture : les variantes sont des configs indépendantes du pli, donc chaque
variante est backtestée UNE fois sur tout l'historique (insights.variant_trades)
et la mécanique des plis se joue sur les flux de trades (pandas pur, ~0 coût).
C'est exactement équivalent à relancer le moteur par pli, en ~100× plus rapide.
"""

from __future__ import annotations

import pandas as pd

from trading_os.backtest.metrics import summary
from trading_os.webapp.insights import select_strategy

TRAIN_DAYS = 30
TEST_DAYS = 10


def _fold_stats(trades: pd.DataFrame, t0, t1) -> dict:
    """Stats d'un flux de trades restreint à [t0, t1) (sur l'heure de sortie)."""
    if trades is None or trades.empty:
        return {"n_trades": 0}
    et = pd.to_datetime(trades["exit_time"])
    return summary(trades[(et >= t0) & (et < t1)])


def walk_forward(streams: dict[str, pd.DataFrame], instrument: str,
                 train_days: int = TRAIN_DAYS, test_days: int = TEST_DAYS) -> dict | None:
    """streams = {variante: trades du moteur sur TOUT l'historique}.

    Retourne {"trades": OOS cumulés, "stats": summary OOS, "folds": [...]} ou
    None si l'historique ne couvre pas au moins un pli complet."""
    if not streams:
        return None
    # bornes temporelles = min/max sur l'union des flux
    all_times = pd.concat([pd.to_datetime(t["exit_time"])
                           for t in streams.values() if t is not None and not t.empty])
    if all_times.empty:
        return None
    start, end = all_times.min().normalize(), all_times.max()
    folds, oos_parts = [], []
    t0 = start
    while True:
        train_end = t0 + pd.Timedelta(days=train_days)
        test_end = train_end + pd.Timedelta(days=test_days)
        if train_end >= end:
            break
        # sélection sur le TRAIN uniquement (mêmes garde-fous que l'autotune)
        rows = []
        for name, trades in streams.items():
            s = _fold_stats(trades, t0, train_end)
            rows.append({"variant": name, "instrument": instrument,
                         "tf": "1min", **({"n_trades": 0} | s)})
        sel = select_strategy(rows, instrument)
        chosen = sel["variant"]
        # application FIGÉE sur le TEST (aucune retouche en cours de pli)
        test_trades = pd.DataFrame()
        if chosen in streams and streams[chosen] is not None and not streams[chosen].empty:
            et = pd.to_datetime(streams[chosen]["exit_time"])
            test_trades = streams[chosen][(et >= train_end) & (et < test_end)]
        ts = summary(test_trades) if not test_trades.empty else {"n_trades": 0}
        folds.append({"train_start": t0, "test_start": train_end,
                      "test_end": min(test_end, end), "variant": chosen,
                      "n_test": int(ts.get("n_trades", 0)),
                      "test_total_r": float(ts.get("total_r", 0.0)),
                      "fallback": chosen not in streams})
        if not test_trades.empty:
            oos_parts.append(test_trades)
        t0 = t0 + pd.Timedelta(days=test_days)   # fenêtre glissante
    if not folds:
        return None
    oos = (pd.concat(oos_parts).sort_values("exit_time").reset_index(drop=True)
           if oos_parts else pd.DataFrame())
    return {"trades": oos, "stats": summary(oos) if not oos.empty else {"n_trades": 0},
            "folds": folds}


# ------------------------------------------------ persistance (build léger)

WF_PATH = "data/walkforward.json"


def save_results(wf: dict, path: str = WF_PATH) -> None:
    """Sérialise {instrument: résultat walk_forward} pour le build intraday
    (qui affiche l'OOS du matin sans relancer la grille)."""
    import json
    from pathlib import Path
    out = {}
    for inst, r in (wf or {}).items():
        if not r:
            continue
        trades = r["trades"]
        out[inst] = {
            "stats": {k: (float(v) if isinstance(v, (int, float)) else v)
                      for k, v in r["stats"].items()},
            "folds": [{**f, "train_start": str(f["train_start"]),
                       "test_start": str(f["test_start"]),
                       "test_end": str(f["test_end"])} for f in r["folds"]],
            "trades": trades.assign(
                entry_time=trades["entry_time"].astype(str),
                exit_time=trades["exit_time"].astype(str),
                fvg_created=trades["fvg_created"].astype(str),
                inverted_time=trades["inverted_time"].astype(str),
            ).to_dict(orient="records") if not trades.empty else [],
        }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


def load_results(path: str = WF_PATH) -> dict:
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for inst, r in raw.items():
        trades = pd.DataFrame(r.get("trades", []))
        if not trades.empty:
            for col in ("entry_time", "exit_time"):
                trades[col] = pd.to_datetime(trades[col])
        out[inst] = {"stats": r.get("stats", {"n_trades": 0}),
                     "folds": r.get("folds", []), "trades": trades}
    return out
