"""Analyse quotidienne du POURQUOI — pas seulement du combien.

Décompose les trades du backtest auto-réglé selon les axes qu'un trader pro
regarde après sa session : tranche horaire de la killzone, jour de semaine,
proximité des news (NTZ), qualité du RR visé, signature des stops (sortie sur
la barre d'entrée = stop trop serré face à la volatilité d'exécution).

Tout est calculé sur le flux de trades net_r (coûts inclus). Ces mesures
nourrissent la boucle d'ajustement (feedback.py) et les bullets « pourquoi »
du dashboard. Fonctions pures — testables sans réseau ni fichier.
"""

from __future__ import annotations

import pandas as pd

# Tranches horaires de la killzone NY AM (heure NY)
BUCKETS = (("09:30-10:30", 9 * 60 + 30, 10 * 60 + 30),
           ("10:30-11:30", 10 * 60 + 30, 11 * 60 + 30))
LONG_WINDOW_DAYS = 30    # fenêtre d'évidence des règles d'ajustement
SHORT_WINDOW_DAYS = 7    # fenêtre des bullets « cette semaine »


def _pf(r: pd.Series) -> float:
    wins, losses = r[r > 0].sum(), -r[r <= 0].sum()
    return float(wins / losses) if losses > 0 else float("inf")


def _block(r: pd.Series) -> dict:
    if len(r) == 0:
        return {"n": 0, "win_rate": 0.0, "expectancy_r": 0.0, "pf": 0.0}
    return {"n": int(len(r)), "win_rate": float((r > 0).mean()),
            "expectancy_r": float(r.mean()), "pf": _pf(r)}


def _minutes(ts) -> int:
    t = pd.Timestamp(ts)
    return t.hour * 60 + t.minute


def daily_review(trades: pd.DataFrame) -> dict | None:
    """Vue d'analyse sur les fenêtres glissantes. None si trop peu de trades."""
    if trades is None or len(trades) < 4:
        return None
    t = trades.copy()
    t["entry_time"] = pd.to_datetime(t["entry_time"])
    t["exit_time"] = pd.to_datetime(t["exit_time"])
    end = t["exit_time"].max()
    long_w = t[t["exit_time"] >= end - pd.Timedelta(days=LONG_WINDOW_DAYS)]
    short_w = t[t["exit_time"] >= end - pd.Timedelta(days=SHORT_WINDOW_DAYS)]

    r_all, r_long = t["net_r"], long_w["net_r"]
    equity = r_all.cumsum()
    dd_long = float((r_long.cumsum() - r_long.cumsum().cummax()).min()) if len(r_long) else 0.0

    by_bucket = {}
    mins = long_w["entry_time"].map(_minutes)
    for label, lo, hi in BUCKETS:
        by_bucket[label] = _block(long_w["net_r"][(mins >= lo) & (mins < hi)])

    losers = long_w[long_w["net_r"] <= 0]
    same_bar = losers[(losers["exit_reason"] == "stop")
                      & (losers["entry_time"] == losers["exit_time"])]
    risk_px = (long_w["entry"] - long_w["stop"]).abs()
    target_rr = (long_w["target"] - long_w["entry"]).abs() / risk_px.where(risk_px > 0)
    low_rr = _block(long_w["net_r"][target_rr < 2.5])
    high_rr = _block(long_w["net_r"][target_rr >= 2.5])

    review = {
        "n_total": int(len(t)),
        "n_long": int(len(long_w)), "n_short": int(len(short_w)),
        "long": _block(r_long), "short": _block(short_w["net_r"]),
        "last10_sum": float(r_all.tail(10).sum()),
        "dd_long_r": dd_long,
        "at_equity_high": bool(len(equity) and equity.iloc[-1] >= equity.max() - 1e-9),
        "by_bucket": by_bucket,
        "n_losers_long": int(len(losers)),
        "same_bar_stop_share": float(len(same_bar) / len(losers)) if len(losers) else 0.0,
        "low_rr": low_rr, "high_rr": high_rr,
        "ntz": _block(long_w["net_r"][long_w["in_ntz"] == True]),   # noqa: E712
    }
    review["bullets"] = _bullets(review)
    return review


def _bullets(rv: dict) -> list[str]:
    """2-4 phrases « pourquoi » en français, uniquement là où l'évidence existe."""
    out = []
    b = rv["by_bucket"]
    b1, b2 = b["09:30-10:30"], b["10:30-11:30"]
    if b1["n"] >= 5 and b2["n"] >= 5 and abs(b1["expectancy_r"] - b2["expectancy_r"]) > 0.4:
        best, worst = (b1, b2) if b1["expectancy_r"] > b2["expectancy_r"] else (b2, b1)
        bl, wl = ("09:30-10:30", "10:30-11:30") if best is b1 else ("10:30-11:30", "09:30-10:30")
        out.append(f"L'edge vient surtout de {bl} ({best['expectancy_r']:+.2f} R/trade, "
                   f"{best['n']} trades) ; {wl} traîne ({worst['expectancy_r']:+.2f} R).")
    if rv["n_losers_long"] >= 6 and rv["same_bar_stop_share"] >= 0.4:
        out.append(f"{rv['same_bar_stop_share']:.0%} des pertes sont des stops touchés "
                   "sur la barre d'entrée même — signature d'un stop trop près de la zone.")
    if rv["low_rr"]["n"] >= 6 and rv["high_rr"]["n"] >= 6 \
            and rv["high_rr"]["pf"] > rv["low_rr"]["pf"] + 0.5:
        out.append(f"Les setups visant un RR ≥ 2.5 paient mieux (PF {rv['high_rr']['pf']:.2f}) "
                   f"que les RR courts (PF {rv['low_rr']['pf']:.2f}).")
    if rv["dd_long_r"] <= -5.0:
        out.append(f"Drawdown de {rv['dd_long_r']:.1f} R sur 30 j — période de fragilité, "
                   "la taille doit se réduire, pas l'inverse.")
    if not out:
        out.append("Pas d'asymétrie exploitable statistiquement sur 30 j — "
                   "le modèle travaille, on n'ajuste rien sans évidence.")
    return out
