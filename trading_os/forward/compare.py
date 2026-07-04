"""Weekly report: forward-test stats vs latest backtest (overfitting detector)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from trading_os.backtest.metrics import summary
from trading_os.core.timeutils import NY
from trading_os.journal.store import Journal


def _latest_backtest_stats(journal_dir: Path) -> tuple[dict, str] | None:
    runs = sorted((journal_dir / "backtests").glob("run_*/trades.csv"))
    if not runs:
        return None
    trades = pd.read_csv(runs[-1])
    return summary(trades), runs[-1].parent.name


def weekly_report(cfg: dict) -> Path:
    journal_dir = Path(cfg["journal"]["directory"])
    now = datetime.now(NY)
    fwd = Journal(journal_dir).load()
    lines = [f"# Rapport hebdomadaire forward vs backtest — semaine du {now:%d/%m/%Y}", ""]

    fwd_r = fwd.dropna(subset=["net_r"]) if not fwd.empty else fwd
    if fwd_r.empty:
        lines += ["_Aucun trade forward avec R renseigné dans le journal._", ""]
    else:
        fstats = summary(fwd_r.rename(columns={"pnl_usd": "pnl_usd"}))
        lines += ["## Forward test (tous trades journalisés avec R)", "",
                  f"- Trades : {fstats['n_trades']} | Win rate : {fstats['win_rate']:.1%} | "
                  f"Espérance : {fstats['expectancy_r']:+.3f} R | "
                  f"Profit factor : {fstats['profit_factor']:.2f}", ""]

    bt = _latest_backtest_stats(journal_dir)
    if bt is None:
        lines += ["_Aucun backtest trouvé — lancer le Module 2 d'abord._", ""]
    else:
        bstats, run = bt
        lines += [f"## Backtest de référence ({run})", "",
                  f"- Trades : {bstats['n_trades']} | Win rate : {bstats['win_rate']:.1%} | "
                  f"Espérance : {bstats['expectancy_r']:+.3f} R | "
                  f"Profit factor : {bstats['profit_factor']:.2f}", ""]

    if bt is not None and not fwd_r.empty:
        gap = fstats["expectancy_r"] - bstats["expectancy_r"]
        lines += ["## Diagnostic overfitting", "",
                  f"- Écart d'espérance forward - backtest : **{gap:+.3f} R/trade**"]
        if gap < -0.3:
            lines.append("- ⚠️ **Dégradation significative** : le forward test sous-performe "
                         "nettement le backtest. Suspecter l'overfitting des paramètres, "
                         "l'exécution (slippage réel) ou un changement de régime de marché. "
                         "NE PAS augmenter la taille.")
        else:
            lines.append("- ✅ Écart dans la tolérance — continuer l'échantillonnage "
                         "(minimum 30-50 trades forward avant toute conclusion).")
    out = journal_dir / "reports" / f"weekly_{now:%Y%m%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
