"""Backtest charts: equity curve and R distribution (saved as PNG)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def save_charts(trades: pd.DataFrame, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    if trades.empty:
        return paths

    equity = trades["net_r"].cumsum()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(range(1, len(equity) + 1), equity.values, linewidth=1.6)
    ax.fill_between(range(1, len(equity) + 1), equity.values, alpha=0.15)
    ax.axhline(0, linewidth=0.8, color="gray")
    ax.set_title("Equity curve (R cumulés, coûts inclus)")
    ax.set_xlabel("Trade #"); ax.set_ylabel("R cumulés")
    p = out_dir / "equity_curve.png"
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig)
    paths.append(p)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(trades["net_r"], bins=30, edgecolor="white")
    ax.axvline(0, linewidth=0.8, color="gray")
    ax.set_title("Distribution des résultats (R net par trade)")
    ax.set_xlabel("R"); ax.set_ylabel("Nombre de trades")
    p = out_dir / "r_distribution.png"
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig)
    paths.append(p)
    return paths
