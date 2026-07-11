"""Risk management calibré profil « sniper » (WR bas, gains larges).

Mathématiques des séries perdantes pour un WR donné :
* p_streak(k, n, wr) — probabilité EXACTE (prog. dynamique) d'observer au
  moins k pertes consécutives sur n trades.
* expected_max_streak(n, wr) ≈ ln(n)/ln(1/p) — ordre de grandeur attendu.
* streak_p99(n, wr) — plus petite série k telle que P(≥k) ≤ 1 %.
* recommended_risk_usd(...) — taille telle que la série p99 (bornée à
  SURVIVE_STREAK_MIN) ne consomme qu'une fraction du budget de perte.
* streak_alert(trades, wr) — la série RÉELLE en cours dépasse-t-elle la
  prévision statistique du modèle ? -> alerte visuelle dashboard.

Aucune de ces fonctions n'augmente jamais le risque au-delà du plafond dur
(HARD_RISK_CAP_USD) — cohérent avec feedback.ADJUSTABLE["risk_scale"].
"""

from __future__ import annotations

import math

import pandas as pd

HARD_RISK_CAP_USD = 250.0      # 0.5 % d'un compte 50k — plafond ABSOLU
RISK_FLOOR_USD = 50.0          # en dessous, un micro NQ ne se size plus
SURVIVE_STREAK_MIN = 15        # le capital doit encaisser AU MOINS 15 pertes
BUDGET_FRACTION = 0.75         # ... en ne consommant que 75 % du budget de perte


def p_streak(k: int, n: int, wr: float) -> float:
    """P(au moins k pertes consécutives sur n trades), pertes iid de proba 1-wr.
    DP sur l'état « longueur de la série perdante courante » — exact, O(n·k)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    q = 1.0 - wr
    # états 0..k-1 = série courante sans avoir atteint k ; absorbant = atteint
    state = [0.0] * k
    state[0] = 1.0
    hit = 0.0
    for _ in range(n):
        nxt = [0.0] * k
        win_mass = sum(state) * wr
        nxt[0] = win_mass
        for j in range(k - 1):
            nxt[j + 1] += state[j] * q
        hit += state[k - 1] * q
        state = nxt
    return min(hit, 1.0)


def expected_max_streak(n: int, wr: float) -> float:
    q = max(min(1.0 - wr, 0.999), 1e-9)
    return math.log(max(n, 2)) / math.log(1.0 / q)


def streak_p99(n: int, wr: float) -> int:
    """Plus petite série k telle que P(≥k sur n trades) ≤ 1 %."""
    for k in range(1, n + 1):
        if p_streak(k, n, wr) <= 0.01:
            return k
    return n


def recommended_risk_usd(wr: float, loss_budget_usd: float,
                         horizon_trades: int = 100) -> dict:
    """Risque/trade tel que la série p99 (≥ SURVIVE_STREAK_MIN) ne consomme
    que BUDGET_FRACTION du budget de perte. Borné dur [floor, cap]."""
    wr = min(max(wr, 0.05), 0.95)
    k99 = max(streak_p99(horizon_trades, wr), SURVIVE_STREAK_MIN)
    raw = loss_budget_usd * BUDGET_FRACTION / k99
    risk = max(RISK_FLOOR_USD, min(HARD_RISK_CAP_USD, round(raw / 5) * 5))
    return {"risk_usd": risk, "streak_p99": k99,
            "survives": int(loss_budget_usd // risk),
            "pct_50k": risk / 50_000}


def current_loss_streak(trades: pd.DataFrame) -> int:
    if trades is None or trades.empty:
        return 0
    r = trades.sort_values("exit_time")["net_r"].to_numpy()
    n = 0
    for v in r[::-1]:
        if v <= 0:
            n += 1
        else:
            break
    return n


def streak_alert(trades: pd.DataFrame, wr: float,
                 horizon_trades: int = 100) -> dict:
    """Compare la série perdante EN COURS à la prévision du modèle."""
    cur = current_loss_streak(trades)
    exp = expected_max_streak(horizon_trades, wr)
    p99 = streak_p99(horizon_trades, wr)
    level = "ok"
    if cur >= p99:
        level = "alerte"       # au-delà du p99 : le modèle est peut-être cassé
    elif cur >= round(exp):
        level = "attention"    # dans la queue attendue, vigilance
    return {"current": cur, "expected_max": exp, "p99": p99, "level": level,
            "p_current": p_streak(max(cur, 1), horizon_trades, wr)}
