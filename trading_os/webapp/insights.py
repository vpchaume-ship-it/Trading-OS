"""Backtest-driven conclusions for the dashboard.

Every morning, the engine is run over a small grid of strategy variants on the
accumulated dataset. The comparison table + auto-written conclusions show what
the data currently supports (grade filter, invalidation mode, target mode,
entry point), with an explicit small-sample / overfitting caveat. As the
dataset grows daily, the conclusions sharpen.
"""

from __future__ import annotations

import copy

import pandas as pd

from trading_os.backtest.engine import run_backtest
from trading_os.backtest.metrics import summary
from trading_os.data.accumulate import load_accumulated
from trading_os.webapp.stats import MIN_1M_BARS

# (nom affiché, patch appliqué sur cfg["ifvg"])
VARIANTS: list[tuple[str, dict]] = [
    # Modèle utilisateur = sweep de niveau de session + IFVG + V-shape (dans la
    # config de base). La grille explore le TIMING d'entrée et la GESTION de sortie
    # par-dessus ce modèle. Chaque variante = 1 backtest complet.
    # Patches EXPLICITES (timing + sortie) : l'étiquette doit rester vraie même
    # si les défauts de config.yaml changent.
    ("Sweep session + V-shape (clôture inversion)",
     {"entry_timing": "inversion_close", "exit_mode": "full"}),
    ("Sweep session + V-shape (retest, cible pleine)",
     {"entry_timing": "retest", "exit_mode": "full"}),
    ("Sweep session + V-shape (retest + prise partielle)",
     {"entry_timing": "retest", "exit_mode": "scale"}),
    # témoin : le même modèle SANS le filtre V-shape, pour mesurer son apport.
    ("Sweep session sans V-shape (retest + partielle)",
     {"entry_timing": "retest", "exit_mode": "scale", "no_vshape": True}),
]


def apply_patch(cfg: dict, patch: dict) -> None:
    """Apply a variant patch onto cfg['ifvg'] (mutates cfg in place)."""
    for k, v in patch.items():
        if k == "target_mode":
            cfg["ifvg"]["target"]["mode"] = v
        elif k in ("liq_min_rr", "liquidity_min_rr"):
            cfg["ifvg"]["target"]["liquidity_min_rr"] = v
        elif k == "exit_mode":
            cfg["ifvg"].setdefault("exit", {})["mode"] = v
        elif k == "no_sweep":
            cfg["ifvg"].setdefault("setup", {})["require_sweep"] = not v
        elif k == "no_vshape":
            cfg["ifvg"].setdefault("setup", {})["require_vshape"] = not v
        elif k == "no_pd":
            cfg["ifvg"].setdefault("setup", {})["require_pd"] = not v
        else:
            cfg["ifvg"][k] = v


def run_variants(cfg: dict, instrument: str, directory: str = "data") -> list[dict]:
    from trading_os.webapp.stats import select_backtest_df
    df, tf, _ = select_backtest_df(instrument, directory)
    if df is None:
        return []
    rows = []
    for name, patch in VARIANTS:
        c = copy.deepcopy(cfg)
        c["ifvg"]["timeframe"] = tf
        apply_patch(c, patch)
        res = run_backtest(df, c, instrument)
        s = summary(res.trades)
        rows.append({"variant": name, "instrument": instrument, "tf": tf, **s})
    return rows


# ------------------------------------------------------------ auto-tune

# Garde-fous du choix automatique : une variante n'est retenue que si elle est
# statistiquement défendable sur l'échantillon courant.
GUARDS = {"min_trades": 10, "min_expectancy": 0.10, "min_pf": 1.20}
PATCHES = {name: patch for name, patch in VARIANTS}
FALLBACK_NAME = "Prudence — A/A+ uniquement (défaut)"
STATE_PATH = "data/strategy_state.json"


def select_strategy(rows: list[dict], instrument: str) -> dict:
    """Pick the best defensible variant for one instrument, or the safe fallback."""
    cand = [r for r in rows if r["instrument"] == instrument
            and r["n_trades"] >= GUARDS["min_trades"]
            and r["expectancy_r"] >= GUARDS["min_expectancy"]
            and r["profit_factor"] >= GUARDS["min_pf"]]
    if not cand:
        return {"variant": FALLBACK_NAME, "patch": {},
                "reason": ("aucune variante ne passe les garde-fous "
                           f"(≥{GUARDS['min_trades']} trades, "
                           f"≥{GUARDS['min_expectancy']:+.2f} R/trade, "
                           f"PF ≥{GUARDS['min_pf']:.2f}) — collecte en cours")}
    # Objectif utilisateur : le win rate le plus élevé qui reste rentable
    # (les garde-fous ci-dessus garantissent déjà la rentabilité). Départage
    # par l'espérance puis le profit factor.
    best = max(cand, key=lambda r: (r["win_rate"], r["expectancy_r"], r["profit_factor"]))
    return {"variant": best["variant"], "patch": PATCHES[best["variant"]],
            "reason": (f"{best['n_trades']} trades · WR {best['win_rate']:.0%} · "
                       f"{best['expectancy_r']:+.2f} R/trade · PF {best['profit_factor']:.2f}")}


def save_state(state: dict, path: str = STATE_PATH) -> None:
    import json
    from datetime import datetime
    from pathlib import Path
    payload = {"chosen_at": datetime.now().isoformat(timespec="seconds"),
               "guards": GUARDS, "instruments": state}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


HISTORY_PATH = "data/strategy_history.csv"


def append_history(state: dict, bt: dict, path: str = HISTORY_PATH) -> None:
    """One row per instrument per build: the auto-tuned choice and its stats.
    This is what lets the dashboard SHOW the self-evolution over time.
    Idempotent per day (a rebuild the same day replaces that day's rows)."""
    from datetime import date
    from pathlib import Path
    today = date.today().isoformat()
    rows = []
    for inst, sel in state.items():
        d = (bt or {}).get(inst) or {}
        s = d.get("stats") or {}
        rows.append({"date": today, "instrument": inst,
                     "variant": sel.get("variant", "?"),
                     "n_trades": s.get("n_trades", 0),
                     "win_rate": round(s.get("win_rate", 0.0), 4),
                     "expectancy_r": round(s.get("expectancy_r", 0.0), 4),
                     "profit_factor": round(min(s.get("profit_factor", 0.0), 99.0), 4),
                     "total_r": round(s.get("total_r", 0.0), 2)})
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        hist = pd.read_csv(p, dtype={"date": str})
        hist = hist[hist["date"] != today]                 # rebuild same day
        hist = pd.concat([hist, pd.DataFrame(rows)], ignore_index=True)
    else:
        hist = pd.DataFrame(rows)
    hist.to_csv(p, index=False)


def load_history(path: str = HISTORY_PATH) -> pd.DataFrame | None:
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return None
    try:
        h = pd.read_csv(p, dtype={"date": str})
        return h if not h.empty else None
    except Exception:
        return None


def load_state(path: str = STATE_PATH) -> dict | None:
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def saved_state(instruments: list[str], path: str = STATE_PATH) -> dict:
    """Rejoue le choix d'auto-réglage PERSISTÉ (strategy_state.json) sans
    relancer la grille — pour les rebuilds intraday. L'autotune ne tourne
    qu'une fois par jour (au build du matin) : le re-régler en cours de
    session serait de l'overfitting intraday. Fallback prudent si absent."""
    payload = load_state(path) or {}
    saved = payload.get("instruments", {})
    out = {}
    for inst in instruments:
        sel = saved.get(inst)
        if isinstance(sel, dict) and "variant" in sel:
            out[inst] = {"variant": sel["variant"],
                         "patch": sel.get("patch", PATCHES.get(sel["variant"], {})),
                         "reason": sel.get("reason", "") + " · réglage du matin (figé en intraday)"}
        else:
            out[inst] = {"variant": FALLBACK_NAME, "patch": {},
                         "reason": "aucun réglage sauvegardé — fallback prudent"}
    return out


def conclusions(rows: list[dict]) -> list[str]:
    """Auto-written French conclusions from the variant grid (all instruments)."""
    if not rows:
        return ["Pas encore assez de données accumulées pour comparer les variantes."]
    out: list[str] = []
    df = pd.DataFrame(rows)

    base = df[df["variant"].str.startswith("Config actuelle")]
    base_trades = int(base["n_trades"].sum()) if not base.empty else 0
    if base_trades == 0:
        out.append("Aucun setup noté A ou A+ sur la période testée : sur ce timeframe, "
                   "le critère de vitesse d'inversion est exigeant. Le filtre reste en "
                   "place — les setups A apparaîtront surtout quand le backtest basculera "
                   "sur les données 1m accumulées.")
    elif base_trades < 10:
        out.append(f"Seulement {base_trades} setup(s) A/A+ sur la période : échantillon "
                   "trop mince pour conclure — le dataset grandit chaque matin.")

    # le filtre de grade paie-t-il ?
    nof = df[df["variant"] == "Sans filtre de grade"]
    amoins = df[df["variant"].str.startswith("Grade ≥ A-")]
    if not nof.empty and not amoins.empty and nof["n_trades"].sum() >= 10:
        e_nof = float((nof["expectancy_r"] * nof["n_trades"]).sum() / max(nof["n_trades"].sum(), 1))
        e_am = float((amoins["expectancy_r"] * amoins["n_trades"]).sum() / max(amoins["n_trades"].sum(), 1))
        if amoins["n_trades"].sum() >= 5:
            if e_am > e_nof + 0.05:
                out.append(f"Le filtre de grade est confirmé par les données : ≥ A- donne "
                           f"{e_am:+.2f} R/trade contre {e_nof:+.2f} R sans filtre.")
            elif e_nof > e_am + 0.05:
                out.append(f"Attention : sur cet échantillon, le filtre de grade ne paie pas "
                           f"encore ({e_am:+.2f} R filtré vs {e_nof:+.2f} R sans filtre). "
                           "À réévaluer quand l'historique 1m sera suffisant.")

    # meilleure variante exploitable
    eligible = df[(df["n_trades"] >= 8)]
    if not eligible.empty:
        best = eligible.loc[eligible["expectancy_r"].idxmax()]
        if best["expectancy_r"] > 0:
            out.append(f"Piste la plus solide actuellement : « {best['variant']} » sur "
                       f"{best['instrument']} ({best['n_trades']:.0f} trades, "
                       f"{best['expectancy_r']:+.2f} R/trade, PF {best['profit_factor']:.2f}).")
        negative = eligible[eligible["expectancy_r"] <= 0]
        if len(negative) == len(eligible):
            out.append("Aucune variante n'est positive sur cet échantillon — prudence : "
                       "rester en démo et laisser les données s'accumuler avant d'en tirer "
                       "des règles.")

    # comparaison ES vs NQ
    per_inst = df[df["variant"] == "Sans filtre de grade"].groupby("instrument")["expectancy_r"].mean()
    if len(per_inst) == 2:
        best_i, worst_i = per_inst.idxmax(), per_inst.idxmin()
        if per_inst[best_i] - per_inst[worst_i] > 0.3:
            out.append(f"Le modèle IFVG répond nettement mieux sur {best_i} "
                       f"({per_inst[best_i]:+.2f} R) que sur {worst_i} "
                       f"({per_inst[worst_i]:+.2f} R) sur cette période.")

    out.append("⚠️ Ces comparaisons portent sur un échantillon court en données "
               "indicatives : c'est une boussole, pas une vérité. Ne durcir une règle "
               "qu'après confirmation sur plusieurs semaines ET en forward test.")
    return out
