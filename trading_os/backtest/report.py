"""Markdown report generation for a backtest run."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from trading_os.backtest.engine import BacktestResult
from trading_os.backtest.metrics import breakdown, summary
from trading_os.backtest.plots import save_charts


def _fmt_table(df: pd.DataFrame, index_name: str) -> str:
    if df.empty:
        return "_Aucune donnée._\n"
    df = df.copy()
    df.index.name = index_name
    return df.to_markdown() + "\n"


def write_report(result: BacktestResult, journal_dir: Path) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = journal_dir / "backtests" / f"run_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    trades = result.trades
    stats = summary(trades)
    charts = save_charts(trades, out_dir)
    if not trades.empty:
        trades.to_csv(out_dir / "trades.csv", index=False)
    (out_dir / "params.json").write_text(
        json.dumps(result.params, indent=2, default=str), encoding="utf-8")

    lines = [
        f"# Backtest IFVG — {result.params.get('instrument', '?')} — run {run_id}",
        "",
        f"- **Période** : {result.start:%Y-%m-%d} → {result.end:%Y-%m-%d} ({result.n_bars:,} barres)",
        f"- **Timeframe** : {result.params.get('timeframe')}",
        f"- **Paramètres** : gap min {result.params.get('min_gap_ticks')} ticks, "
        f"invalidation `{result.params.get('invalidation_mode')}`, "
        f"entrée `{result.params.get('retest_entry')}`, target `{result.params.get('target')}`",
        f"- **Coûts** : {result.params.get('commission_rt_usd')}$ aller-retour + "
        f"{result.params.get('slippage_ticks_stop')} tick(s) de slippage sur les stops",
        f"- **Setups ignorés** : RR insuffisant : {result.skipped_low_rr}, "
        f"no-trade-zone : {result.skipped_ntz}, position déjà ouverte : {result.skipped_position_busy}, "
        f"notation < {result.params.get('min_rating', 0)}/10 : {result.skipped_low_rating}",
        "",
        "## Résultats globaux (R net, coûts inclus)",
        "",
    ]
    if stats["n_trades"] == 0:
        lines.append("**Aucun trade généré** — élargir la période ou assouplir les paramètres.")
    else:
        lines += [
            f"| Métrique | Valeur |",
            f"|---|---|",
            f"| Trades | {stats['n_trades']} |",
            f"| Win rate | {stats['win_rate']:.1%} |",
            f"| Espérance / trade | {stats['expectancy_r']:+.3f} R |",
            f"| R moyen gagnant / perdant | {stats['avg_win_r']:+.2f} / {stats['avg_loss_r']:+.2f} |",
            f"| Profit factor | {stats['profit_factor']:.2f} |",
            f"| Total | {stats['total_r']:+.1f} R ({stats['total_pnl_usd']:+,.0f} $) |",
            f"| Drawdown max | {stats['max_drawdown_r']:.1f} R |",
            f"| Pertes consécutives max | {stats['max_consecutive_losses']} |",
            "",
            "![Equity curve](equity_curve.png)",
            "![Distribution des R](r_distribution.png)",
            "",
            "## Répartition par killzone", "",
            _fmt_table(breakdown(trades, "killzone"), "killzone"),
            "## Répartition par jour de la semaine", "",
            _fmt_table(breakdown(trades, "weekday"), "jour"),
            "## Répartition par direction", "",
            _fmt_table(breakdown(trades, "direction"), "direction"),
            "## Répartition par grade d'inversion (notation PDF /10)", "",
            _fmt_table(breakdown(trades, "grade"), "grade"),
            "## Contexte news (trade dans une no-trade-zone ?)", "",
            _fmt_table(breakdown(trades, "in_ntz"), "dans_NTZ"),
        ]
    lines += [
        "",
        "---",
        "_Rappel : résultats simulés avec modèle de fill conservateur (stop prioritaire",
        "en cas d'ambiguïté intra-barre). Les performances passées ne préjugent pas des",
        "performances futures. Démo uniquement._",
    ]
    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
