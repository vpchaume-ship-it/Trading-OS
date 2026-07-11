"""Boucle d'auto-ajustement des paramètres SECONDAIRES de la stratégie IFVG.

Philosophie (verrouillée) :
* Le socle du wiki — sweep de niveau de session + IFVG + V-shape, killzone
  NY AM, entrée/sortie choisies par l'autotune — est INTOUCHABLE : seules les
  clés listées dans ADJUSTABLE peuvent bouger, dans des bornes dures.
* Une seule nouvelle décision par jour, evidence-gated (jamais moins de
  MIN_EVIDENCE trades derrière une règle), réversible, datée, expliquée en
  français et affichée sur le dashboard.
* Le risque ne peut JAMAIS être augmenté au-dessus de 1× le sizing de base ;
  en drawdown il est réduit. Le stop ne descend jamais sous 1 tick de buffer.
* Anti-overfitting : un ajustement qui n'améliore pas l'espérance après
  ADOPTION_REVIEW_TRADES nouveaux trades est auto-annulé ; un filtre horaire
  expire de lui-même (l'évidence ne peut plus se renouveler une fois la
  tranche coupée).

État persisté dans data/adjustments.json ; fonctions pures autour, testables.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

# ----------------------------------------------------------- garde-fous durs
# Clés ajustables et bornes ABSOLUES (le code refuse tout le reste).
ADJUSTABLE = {
    "stop_buffer_ticks": (1, 6),        # jamais < 1 tick, jamais > 6
    "liquidity_min_rr": (1.5, 3.0),     # un RR plancher reste obligatoire
    "risk_scale": (0.25, 1.0),          # réduction seulement — 1.0 = plafond DUR
    "entry_window": None,               # doit rester DANS la killzone, ≥ 60 min
}
KILLZONE = ("09:30", "11:30")           # bornes de la fenêtre NY AM (heure NY)
MIN_WINDOW_MIN = 60
MIN_EVIDENCE = 8                        # trades minimum derrière chaque règle
MAX_NEW_PER_DAY = 1
WINDOW_EXPIRY_DAYS = 28                 # un filtre horaire se rejuge à neuf
ADOPTION_REVIEW_TRADES = 10             # anti-overfit : bilan après N trades
REVERT_IF_EXP_DROPS = 0.30              # en R/trade vs l'adoption

STATE_PATH = "data/adjustments.json"


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def clamp(key: str, value):
    """Borne une valeur ajustable ; refuse toute clé hors ADJUSTABLE (socle gelé)."""
    if key not in ADJUSTABLE:
        raise ValueError(f"clé non ajustable (socle IFVG gelé) : {key}")
    if key == "entry_window":
        lo, hi = max(_mins(value["start"]), _mins(KILLZONE[0])), \
                 min(_mins(value["end"]), _mins(KILLZONE[1]))
        if hi - lo < MIN_WINDOW_MIN:
            raise ValueError("fenêtre d'entrée < 60 min ou hors killzone")
        return {"start": f"{lo // 60:02d}:{lo % 60:02d}", "end": f"{hi // 60:02d}:{hi % 60:02d}"}
    lo, hi = ADJUSTABLE[key]
    return min(max(value, lo), hi)


# ----------------------------------------------------------- état persistant

def load_state(path: str = STATE_PATH) -> dict:
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"active": {}, "history": []}


def save_state(state: dict, path: str = STATE_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def as_patch(active: dict) -> dict:
    """Overrides moteur (risk_scale est du sizing, pas du moteur)."""
    return {k: v for k, v in active.items() if k != "risk_scale"}


def _adopt(state: dict, today: str, key: str, from_v, to_v, reason: str,
           evidence: str, n_total: int, adoption_exp: float) -> None:
    to_v = clamp(key, to_v)
    state["active"][key] = to_v
    state["history"].append({
        "date": today, "key": key, "from": from_v, "to": to_v,
        "reason": reason, "evidence": evidence, "status": "active",
        "n_at_adoption": n_total, "exp_at_adoption": round(adoption_exp, 3)})


def _revert(state: dict, key: str, why: str, today: str) -> None:
    state["active"].pop(key, None)
    for h in reversed(state["history"]):
        if h["key"] == key and h["status"] == "active":
            h["status"] = "annulé"
            h["revert_date"] = today
            h["revert_reason"] = why
            break


def compare_adjusted(state: dict, base_stats: dict | None, adj_stats: dict | None,
                     n_base_now: int, today: str | None = None) -> tuple[dict, list[str]]:
    """Anti-overfit par MESURE DIRECTE : si, après ADOPTION_REVIEW_TRADES
    nouveaux trades, la config ajustée fait moins bien que le socle (espérance
    inférieure de REVERT_IF_EXP_DROPS/3 R ou plus), le dernier ajustement adopté
    est annulé — l'ajustement doit prouver qu'il paie, pas l'inverse."""
    today = today or date.today().isoformat()
    notes: list[str] = []
    active = [h for h in state["history"] if h["status"] == "active"]
    if not active or not base_stats or not adj_stats \
            or base_stats.get("n_trades", 0) == 0 or adj_stats.get("n_trades", 0) == 0:
        return state, notes
    latest = max(active, key=lambda h: h["date"])
    n_new = n_base_now - latest.get("n_at_adoption", 0)
    gap = adj_stats["expectancy_r"] - base_stats["expectancy_r"]
    if n_new >= ADOPTION_REVIEW_TRADES and gap < -REVERT_IF_EXP_DROPS / 3:
        _revert(state, latest["key"],
                f"la config ajustée sous-performe le socle ({gap:+.2f} R/trade "
                f"après {n_new} nouveaux trades)", today)
        notes.append(f"Ajustement « {latest['key']} » annulé : le socle fait mieux.")
    return state, notes


# ----------------------------------------------------------- la boucle

def step(review: dict | None, state: dict, base: dict,
         today: str | None = None) -> tuple[dict, list[str]]:
    """Un pas quotidien : maintenance (expiry / anti-overfit / restauration)
    puis AU PLUS UNE nouvelle décision, gated par l'évidence.

    base = valeurs de référence de config.yaml {stop_buffer_ticks, liquidity_min_rr}.
    Retourne (state, notes françaises pour le log/dashboard)."""
    today = today or date.today().isoformat()
    notes: list[str] = []
    if review is None:
        return state, notes

    # -- maintenance 1 : expiration des filtres horaires (l'évidence coupée
    #    ne peut plus se contredire elle-même → on rejuge à neuf)
    for h in state["history"]:
        if (h["key"] == "entry_window" and h["status"] == "active"
                and date.fromisoformat(h["date"]) + timedelta(days=WINDOW_EXPIRY_DAYS)
                <= date.fromisoformat(today)):
            _revert(state, "entry_window", "expiration programmée (28 j) — re-jugement à neuf", today)
            notes.append("Filtre horaire expiré (28 j) : fenêtre complète restaurée.")

    # -- maintenance 2 : l'anti-overfit par comparaison DIRECTE ajusté-vs-socle
    #    est fait par compare_adjusted() (appelé par le build, qui possède les
    #    deux runs). Audit 2026-07-11 : l'ancienne comparaison « espérance socle
    #    maintenant vs à l'adoption » mesurait la dérive du marché, pas l'effet
    #    de l'ajustement — supprimée.

    # -- maintenance 3 : restauration du risque plein quand le DD est résorbé
    if "risk_scale" in state["active"] and review["at_equity_high"] \
            and review["last10_sum"] > 0:
        _revert(state, "risk_scale", "drawdown résorbé (nouveau plus-haut d'equity)", today)
        notes.append("Risque restauré à 1× : nouveau plus-haut d'equity.")

    # -- au plus UNE nouvelle décision par jour
    if any(h["date"] == today and h["status"] == "active" for h in state["history"]):
        return state, notes
    exp_now = review["long"]["expectancy_r"]

    # R1 (protection, priorité absolue) : drawdown -> réduire la taille
    if "risk_scale" not in state["active"] \
            and (review["dd_long_r"] <= -5.0 or review["last10_sum"] <= -3.0):
        _adopt(state, today, "risk_scale", 1.0, 0.5,
               "réduction du risque en drawdown (protection du capital, jamais l'inverse)",
               f"DD 30j {review['dd_long_r']:.1f} R · 10 derniers trades "
               f"{review['last10_sum']:+.1f} R", review["n_total"], exp_now)
        notes.append("Risque réduit à 0.5× (~100 $/trade) le temps du drawdown.")
        return state, notes

    # R2 : tranche horaire structurellement perdante -> filtrer (dans la killzone)
    if "entry_window" not in state["active"]:
        b = review["by_bucket"]
        pairs = [("09:30-10:30", "10:30-11:30"), ("10:30-11:30", "09:30-10:30")]
        for bad, good in pairs:
            if (b[bad]["n"] >= MIN_EVIDENCE and b[good]["n"] >= MIN_EVIDENCE
                    and b[bad]["pf"] < 0.8 and b[good]["pf"] >= 1.2):
                start, end = good.split("-")
                _adopt(state, today, "entry_window", None, {"start": start, "end": end},
                       f"tranche {bad} filtrée : PF {b[bad]['pf']:.2f} sur "
                       f"{b[bad]['n']} trades (l'autre tranche : PF {b[good]['pf']:.2f})",
                       f"{bad}: n={b[bad]['n']} PF={b[bad]['pf']:.2f} · "
                       f"{good}: n={b[good]['n']} PF={b[good]['pf']:.2f}",
                       review["n_total"], exp_now)
                notes.append(f"Entrées limitées à {good} (tranche {bad} en PF < 0.8).")
                return state, notes

    # R3 : stops touchés sur la barre d'entrée -> +1 tick de buffer
    cur_buf = state["active"].get("stop_buffer_ticks", base["stop_buffer_ticks"])
    if review["n_losers_long"] >= MIN_EVIDENCE and review["same_bar_stop_share"] >= 0.4 \
            and cur_buf < ADJUSTABLE["stop_buffer_ticks"][1]:
        _adopt(state, today, "stop_buffer_ticks", cur_buf, cur_buf + 1,
               f"{review['same_bar_stop_share']:.0%} des pertes = stop sur la barre "
               "d'entrée : buffer élargi d'1 tick (le stop reste obligatoire)",
               f"{review['n_losers_long']} pertes 30j, part same-bar "
               f"{review['same_bar_stop_share']:.0%}", review["n_total"], exp_now)
        notes.append(f"Stop élargi : buffer {cur_buf} → {cur_buf + 1} ticks.")
        return state, notes

    # R4 : les RR courts détruisent de la valeur -> relever le plancher RR
    cur_rr = state["active"].get("liquidity_min_rr", base["liquidity_min_rr"])
    if (review["low_rr"]["n"] >= MIN_EVIDENCE and review["high_rr"]["n"] >= MIN_EVIDENCE
            and review["low_rr"]["pf"] < 0.8 and review["high_rr"]["pf"] >= 1.2
            and cur_rr < 2.5):
        _adopt(state, today, "liquidity_min_rr", cur_rr, 2.5,
               f"les cibles RR < 2.5 perdent (PF {review['low_rr']['pf']:.2f}) quand "
               f"les RR ≥ 2.5 paient (PF {review['high_rr']['pf']:.2f})",
               f"low: n={review['low_rr']['n']} PF={review['low_rr']['pf']:.2f} · "
               f"high: n={review['high_rr']['n']} PF={review['high_rr']['pf']:.2f}",
               review["n_total"], exp_now)
        notes.append("Plancher RR relevé à 2.5 (les cibles courtes perdaient).")
        return state, notes

    return state, notes
