"""Météo du risque — l'équivalent « lite » de la carte de tensions Glint.trade,
construit sur des jauges gratuites (Yahoo) : VIX (peur), or (fuite vers la
qualité), dollar (stress global). Verdict RISK-ON / NEUTRE / RISK-OFF affiché
en tuile héro du dashboard.

Lecture trader : RISK-OFF ne veut pas dire « ne pas trader » — il veut dire
volatilité élevée, cibles atteintes plus vite, stops respectés à la lettre,
et méfiance sur les longs NQ à contre-tendance.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskWeather:
    verdict: str           # "risk_on" | "neutre" | "risk_off"
    score: int             # négatif = risk-off
    vix: float
    vix_chg: float         # variation 1 jour (points)
    gold_chg_pct: float    # variation 1 jour (%)
    dxy_chg_pct: float
    detail: str


def score_risk(vix: float, vix_chg: float,
               gold_chg_pct: float, dxy_chg_pct: float) -> tuple[str, int]:
    """Score mécanique -6..+6. Seuils volontairement francs : la tuile doit
    trancher, pas nuancer."""
    s = 0
    s += 2 if vix < 15 else (1 if vix < 18 else (-1 if vix < 25 else -3))
    s += -2 if vix_chg > 2 else (-1 if vix_chg > 0.8 else (1 if vix_chg < -0.8 else 0))
    s += -1 if gold_chg_pct > 1.0 else (1 if gold_chg_pct < -0.7 else 0)
    s += -1 if abs(dxy_chg_pct) > 0.6 else 0
    verdict = "risk_on" if s >= 2 else ("risk_off" if s <= -2 else "neutre")
    return verdict, s


def risk_weather() -> RiskWeather | None:
    """None si les flux sont indisponibles (le dashboard omet la tuile)."""
    from trading_os.data.yahoo import fetch_daily
    try:
        vix_d = fetch_daily("^VIX", "1mo")
        gold_d = fetch_daily("GC=F", "1mo")
        dxy_d = fetch_daily("DX-Y.NYB", "1mo")
        if min(len(vix_d), len(gold_d), len(dxy_d)) < 2:
            return None
        vix, vix_prev = float(vix_d["close"].iloc[-1]), float(vix_d["close"].iloc[-2])
        g, g_prev = float(gold_d["close"].iloc[-1]), float(gold_d["close"].iloc[-2])
        x, x_prev = float(dxy_d["close"].iloc[-1]), float(dxy_d["close"].iloc[-2])
    except Exception:
        return None
    vix_chg = vix - vix_prev
    gold_chg = (g / g_prev - 1) * 100
    dxy_chg = (x / x_prev - 1) * 100
    verdict, score = score_risk(vix, vix_chg, gold_chg, dxy_chg)
    detail = (f"VIX {vix:.1f} ({vix_chg:+.1f}) · or {gold_chg:+.1f} % · "
              f"DXY {dxy_chg:+.1f} %")
    return RiskWeather(verdict, score, vix, vix_chg, gold_chg, dxy_chg, detail)
