"""Performance metrics and breakdowns for backtest / forward-test trades."""

from __future__ import annotations

import numpy as np
import pandas as pd


def summary(trades: pd.DataFrame) -> dict:
    """Global stats on a trades frame (uses net R, costs included)."""
    if trades.empty:
        return {"n_trades": 0}
    r = trades["net_r"]
    wins, losses = r[r > 0], r[r <= 0]
    gross_profit = wins.sum()
    gross_loss = -losses.sum()
    equity = r.cumsum()
    dd = equity - equity.cummax()
    return {
        "n_trades": len(trades),
        "win_rate": len(wins) / len(trades),
        "avg_r": r.mean(),
        "avg_win_r": wins.mean() if len(wins) else 0.0,
        "avg_loss_r": losses.mean() if len(losses) else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float("inf"),
        "expectancy_r": r.mean(),                    # espérance par trade en R
        "total_r": r.sum(),
        "total_pnl_usd": trades["pnl_usd"].sum(),
        "max_drawdown_r": dd.min(),
        "max_consecutive_losses": _max_streak(r <= 0),
        "best_r": r.max(),
        "worst_r": r.min(),
    }


def _max_streak(mask: pd.Series) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def stability(trades: pd.DataFrame) -> dict | None:
    """Edge degradation check (prop-firm evaluator view): compare the first and
    second halves of the trade sequence. Returns None below 8 trades (halves
    too thin to mean anything)."""
    if len(trades) < 8:
        return None
    mid = len(trades) // 2
    a, b = trades["net_r"].iloc[:mid], trades["net_r"].iloc[mid:]
    h = lambda s: {"n": len(s), "win_rate": float((s > 0).mean()),
                   "expectancy_r": float(s.mean())}
    first, second = h(a), h(b)
    d = second["expectancy_r"] - first["expectancy_r"]
    if second["expectancy_r"] <= 0 < first["expectancy_r"]:
        verdict = "degrade"          # l'edge a disparu sur la période récente
    elif d < -0.25:
        verdict = "faiblit"
    elif d > 0.25:
        verdict = "renforce"
    else:
        verdict = "stable"
    return {"first": first, "second": second, "verdict": verdict}


def breakdown(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    """Stats grouped by a column (killzone, weekday, in_ntz, direction...)."""
    if trades.empty or by not in trades.columns:
        return pd.DataFrame()
    g = trades.groupby(by)["net_r"]
    out = pd.DataFrame({
        "trades": g.size(),
        "win_rate": g.apply(lambda s: (s > 0).mean()),
        "avg_r": g.mean(),
        "total_r": g.sum(),
    })
    if by == "weekday":
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Sunday"]
        out = out.reindex([d for d in order if d in out.index])
    return out.round(3)
