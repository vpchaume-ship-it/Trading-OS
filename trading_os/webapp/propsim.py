"""Prop-firm evaluation simulator — Lucid 50K Flex rules by default.

Replays the headline backtest's trades day by day with realistic micro sizing
and applies the eval rules:
* profit target, EOD-trailing Max Loss Limit (intraday ignored, per Lucid),
* minimum trading days, 50% consistency rule,
* contract cap.

Sources (règles vérifiées en ligne, à re-vérifier avant toute éval réelle) :
tradetanto.com, proptradingvibes.com, damnpropfirms.com — Lucid 50K Flex :
target $3 000, MLL $2 000 trailing EOD, pas de daily loss limit, min 2 jours,
consistance 50 %, 40 micros max.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

DEFAULT_RULES = {
    "name": "Lucid 50K Pro",
    "start_balance": 50_000.0,
    "profit_target": 3_000.0,
    "max_loss_limit": 2_000.0,      # trailing EOD (suit le plus haut solde de clôture)
    "daily_loss_limit": 1_200.0,    # stop journalier intraday (Pro) ; 0 = aucun
    "lock_at_start": True,          # le plancher se fige au solde initial une fois atteint
    "min_days": 1,                  # Pro : passable en 1 jour
    "consistency_pct": 0,           # Pro : PAS de règle de consistance en éval (0 = off)
    "max_micros": 40,
    "risk_per_trade_usd": 200.0,    # sizing simulé (10 % du MLL)
}


@dataclass
class PropSimResult:
    status: str                  # "reussie" | "echouee" | "en_cours"
    detail: str
    days: int = 0
    trades: int = 0
    final_pnl: float = 0.0
    worst_day: float = 0.0
    best_day: float = 0.0
    avg_micros: float = 0.0
    consistency_ok: bool = True
    daily_pnl: list = field(default_factory=list)


def simulate(trades: pd.DataFrame, spec: dict, rules: dict | None = None) -> PropSimResult | None:
    """trades = backtest output (1 mini contract); spec = instrument config."""
    rules = {**DEFAULT_RULES, **(rules or {})}
    if trades is None or trades.empty:
        return None
    micro_val = spec["micro_tick_value"]
    mini_val = spec["tick_value"]
    commission_micro = 2 * 0.85          # aller-retour par micro
    commission_mini = 2 * 2.25

    rows = []
    for _, t in trades.iterrows():
        risk_usd_micro = t["risk_ticks"] * micro_val
        n = max(1, min(int(rules["max_micros"]),
                       math.floor(rules["risk_per_trade_usd"] / risk_usd_micro)))
        # convert 1-mini pnl to n micros: strip mini commission, scale ticks, re-add
        gross_mini = t["pnl_usd"] + commission_mini
        pnl = gross_mini * (micro_val / mini_val) * n - commission_micro * n
        rows.append({"day": pd.Timestamp(t["exit_time"]).date(), "pnl": pnl, "n": n})
    df = pd.DataFrame(rows)
    daily = df.groupby("day")["pnl"].sum()

    daily_limit = rules.get("daily_loss_limit", 0) or 0
    cons_pct = rules.get("consistency_pct", 0) or 0
    balance = rules["start_balance"]
    floor = balance - rules["max_loss_limit"]
    peak = balance
    total = 0.0
    for i, (day, pnl) in enumerate(daily.items(), start=1):
        # stop journalier intraday (Pro) : une journée qui perd plus que la limite
        if daily_limit and pnl <= -daily_limit:
            return PropSimResult(
                "echouee",
                f"Daily Loss Limit dépassé au jour {i} ({day:%d/%m}) : "
                f"{pnl:,.0f} $ ≤ -{daily_limit:,.0f} $".replace(",", " "),
                days=i, trades=len(df[df['day'] <= day]), final_pnl=total + pnl,
                worst_day=float(daily.min()), best_day=float(daily.max()),
                avg_micros=float(df["n"].mean()), daily_pnl=list(daily[:i]))
        balance += pnl
        total += pnl
        if balance <= floor:                      # MLL vérifié à la clôture (EOD)
            return PropSimResult(
                "echouee",
                f"Max Loss Limit touché au jour {i} ({day:%d/%m}) : solde "
                f"{balance:,.0f} $ ≤ plancher {floor:,.0f} $".replace(",", " "),
                days=i, trades=len(df[df['day'] <= day]), final_pnl=total,
                worst_day=float(daily.min()), best_day=float(daily.max()),
                avg_micros=float(df["n"].mean()), daily_pnl=list(daily[:i]))
        # trailing EOD : le plancher suit le meilleur solde de clôture
        if balance > peak:
            peak = balance
            new_floor = peak - rules["max_loss_limit"]
            if rules["lock_at_start"]:
                new_floor = min(new_floor, rules["start_balance"])
            floor = max(floor, new_floor)
        best_day = float(daily[:i].max())
        consistency_ok = cons_pct == 0 or total <= 0 or best_day <= total * cons_pct / 100
        if (total >= rules["profit_target"] and i >= rules["min_days"]
                and consistency_ok):
            note = "" if cons_pct == 0 else ", règle de consistance respectée"
            return PropSimResult(
                "reussie",
                f"Objectif {rules['profit_target']:,.0f} $ atteint en {i} jour(s) "
                f"de trading{note}".replace(",", " "),
                days=i, trades=len(df[df['day'] <= day]), final_pnl=total,
                worst_day=float(daily.min()), best_day=best_day,
                avg_micros=float(df["n"].mean()), consistency_ok=True,
                daily_pnl=list(daily[:i]))

    best_day = float(daily.max())
    consistency_ok = cons_pct == 0 or total <= 0 or best_day <= total * cons_pct / 100
    detail = (f"Éval toujours en cours après {len(daily)} jours : "
              f"{total:+,.0f} $ / objectif {rules['profit_target']:,.0f} $").replace(",", " ")
    if total >= rules["profit_target"] and not consistency_ok:
        detail += f" — objectif atteint mais consistance {cons_pct} % non respectée"
    return PropSimResult("en_cours", detail, days=len(daily), trades=len(df),
                         final_pnl=total, worst_day=float(daily.min()),
                         best_day=best_day, avg_micros=float(df["n"].mean()),
                         consistency_ok=consistency_ok, daily_pnl=list(daily))
