"""Trading OS — main terminal menu (rich).

Usage:  python -m trading_os.cli
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from trading_os.config import load_config

console = Console()

BANNER = """[bold cyan]TRADING OS[/bold cyan] — ES/NQ · modèle ICT IFVG · [bold red]DÉMO UNIQUEMENT[/bold red]"""


def main_menu() -> None:
    cfg = load_config()
    while True:
        console.print()
        console.print(Panel(BANNER, expand=False))
        table = Table(show_header=False, box=None)
        table.add_row("[bold]1[/bold]", "📰 News à fort impact — red folders & scénarios (Module 1)")
        table.add_row("[bold]2[/bold]", "📊 Backtest IFVG (Module 2)")
        table.add_row("[bold]3[/bold]", "🛰️  Forward test Tradovate DEMO (Module 3)")
        table.add_row("[bold]4[/bold]", "🌅 Rapport prémarché du jour (Module 4)")
        table.add_row("[bold]5[/bold]", "📚 Base de connaissances (PDF ICT)")
        table.add_row("[bold]0[/bold]", "Quitter")
        console.print(table)
        choice = Prompt.ask("Choix", choices=["0", "1", "2", "3", "4", "5"], default="4")
        try:
            if choice == "0":
                console.print("À demain. Discipline > conviction. 👋")
                return
            elif choice == "1":
                menu_news(cfg)
            elif choice == "2":
                menu_backtest(cfg)
            elif choice == "3":
                menu_forward(cfg)
            elif choice == "4":
                menu_premarket(cfg)
            elif choice == "5":
                menu_knowledge(cfg)
        except KeyboardInterrupt:
            console.print("\n[dim]Interrompu — retour au menu.[/dim]")
        except Exception as exc:
            console.print(f"[red]Erreur : {exc}[/red]")


# ---------------------------------------------------------------- Module 1
def menu_news(cfg: dict) -> None:
    from trading_os.news.calendar import append_history, fetch_red_folders
    from trading_os.news.scenarios import build_card, card_markdown

    console.print("[cyan]Récupération du calendrier ForexFactory…[/cyan]")
    events = fetch_red_folders(cfg)
    added = append_history(events, cfg["backtest"]["news_history_csv"])
    console.print(f"{len(events)} red folders USD cette semaine "
                  f"({added} nouveaux ajoutés à l'historique NTZ).\n")
    ncfg = cfg["news"]["no_trade_zone"]
    if not events:
        console.print("[green]Aucun red folder USD cette semaine.[/green]")
        return
    for e in events:
        ntz = e.no_trade_zone(ncfg["minutes_before"], ncfg["minutes_after"])
        console.print(Panel(card_markdown(build_card(e), ntz),
                            title=f"🔴 {e.title}", expand=False))


# ---------------------------------------------------------------- Module 2
def menu_backtest(cfg: dict) -> None:
    from trading_os.backtest.engine import run_backtest
    from trading_os.backtest.metrics import summary
    from trading_os.backtest.report import write_report
    from trading_os.data.loader import load_csv, resample

    instrument = Prompt.ask("Instrument", choices=list(cfg["instruments"]),
                            default=cfg["backtest"]["instrument"])
    default_csv = cfg["backtest"]["csv_file"] or f"data/{instrument}_1m.csv"
    csv_path = Prompt.ask("Fichier CSV 1m", default=default_csv)
    if not Path(csv_path).exists():
        console.print(f"[red]{csv_path} introuvable.[/red] Exporter d'abord depuis MT5 :\n"
                      f"  python scripts/export_mt5.py --symbol "
                      f"{cfg['instruments'][instrument]['mt5_symbol']} --days 365 "
                      f"--out {csv_path}")
        return

    console.print("[cyan]Chargement des données…[/cyan]")
    df = load_csv(csv_path, cfg["data"]["csv_timezone"])
    tf = cfg["ifvg"]["timeframe"]
    if tf not in ("1min", "1m"):
        df = resample(df, tf)
    console.print(f"{len(df):,} barres {tf} · {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}")

    with console.status("Backtest en cours…"):
        result = run_backtest(df, cfg, instrument)
    stats = summary(result.trades)
    if stats["n_trades"] == 0:
        console.print("[yellow]Aucun trade généré — élargir la période ou assouplir "
                      "les paramètres (ifvg.* dans config.yaml).[/yellow]")
    else:
        t = Table(title=f"Résultats {instrument} ({stats['n_trades']} trades, R net)")
        t.add_column("Métrique"); t.add_column("Valeur", justify="right")
        t.add_row("Win rate", f"{stats['win_rate']:.1%}")
        t.add_row("Espérance / trade", f"{stats['expectancy_r']:+.3f} R")
        t.add_row("Profit factor", f"{stats['profit_factor']:.2f}")
        t.add_row("Total", f"{stats['total_r']:+.1f} R ({stats['total_pnl_usd']:+,.0f} $)")
        t.add_row("Drawdown max", f"{stats['max_drawdown_r']:.1f} R")
        console.print(t)
    path = write_report(result, Path(cfg["journal"]["directory"]))
    console.print(f"[green]Rapport écrit : {path}[/green]")


# ---------------------------------------------------------------- Module 3
def menu_forward(cfg: dict) -> None:
    from trading_os.forward.guards import (SafetyViolation, assert_daily_loss_ok)
    from trading_os.forward.journal_sync import realized_pnl_today

    console.print(Panel(
        "[bold red]DEMO UNIQUEMENT[/bold red] — garde-fous codés en dur :\n"
        "URL demo obligatoire · 1 micro contrat max (MES/MNQ) · "
        "limite de perte journalière · pas de trade en no-trade-zone.",
        title="Module 3 — Forward test", expand=False))
    mode = Prompt.ask("Mode", choices=["semi-auto", "journal", "hebdo", "retour"],
                      default="journal")
    try:
        if mode == "retour":
            return
        if mode == "hebdo":
            from trading_os.forward.compare import weekly_report
            path = weekly_report(cfg)
            console.print(f"[green]Rapport hebdomadaire écrit : {path}[/green]")
            return
        # daily loss guard before anything touches the API
        assert_daily_loss_ok(realized_pnl_today(cfg),
                             cfg["forward"]["daily_loss_limit_usd"])
        if mode == "journal":
            from trading_os.forward.journal_sync import sync_journal
            console.print("[cyan]Synchronisation des fills Tradovate demo…[/cyan]")
            added = sync_journal(cfg)
            console.print(f"[green]{added} trade(s) ajouté(s) au journal.[/green]")
        else:
            from trading_os.forward.monitor import run_semi_auto
            instrument = Prompt.ask("Instrument", choices=list(cfg["instruments"]),
                                    default="ES")
            run_semi_auto(cfg, instrument, console)
    except SafetyViolation as sv:
        console.print(f"[bold red]🛑 GARDE-FOU : {sv}[/bold red]")


# ---------------------------------------------------------------- Module 4
def menu_premarket(cfg: dict) -> None:
    from trading_os.premarket.report import generate

    csv_paths = {name: f"data/{name}_1m.csv" for name in cfg["premarket"]["instruments"]}
    console.print("[cyan]Génération du rapport prémarché…[/cyan]")
    path = generate(cfg, csv_paths)
    console.print(f"[green]Rapport écrit : {path}[/green]")
    if Confirm.ask("Afficher dans le terminal ?", default=True):
        from rich.markdown import Markdown
        console.print(Markdown(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------- Knowledge
def menu_knowledge(cfg: dict) -> None:
    from trading_os.knowledge_base.indexer import (build_index, concept_extracts,
                                                   load_index, search)

    action = Prompt.ask("Action", choices=["indexer", "chercher", "concepts", "retour"],
                        default="chercher")
    if action == "retour":
        return
    if action == "indexer":
        console.print("[cyan]Indexation des PDF de knowledge/…[/cyan]")
        index = build_index(cfg)
        console.print(f"[green]{index['n_files']} fichier(s), "
                      f"{len(index['pages'])} pages indexées.[/green]")
        return
    if load_index(cfg) is None:
        console.print("[yellow]Index absent — lancer 'indexer' d'abord "
                      "(déposez vos PDF dans knowledge/).[/yellow]")
        return
    if action == "chercher":
        q = Prompt.ask("Recherche")
        hits = search(cfg, q)
        if not hits:
            console.print("[dim]Aucun résultat.[/dim]")
        for h in hits:
            console.print(f"[bold]{h['file']}[/bold] p.{h['page']} — {h['snippet']}\n")
    else:  # concepts
        extracts = concept_extracts(cfg)
        if not extracts:
            console.print("[dim]Aucun concept suivi trouvé dans les PDF.[/dim]")
        for concept, passages in extracts.items():
            console.print(Panel("\n\n".join(
                f"[bold]{p['file']}[/bold] p.{p['page']} — {p['snippet']}"
                for p in passages), title=f"📖 {concept}", expand=False))
        console.print("[dim]Comparez ces définitions avec celles implémentées "
                      "(docstring de trading_os/core/fvg.py). En cas de conflit, "
                      "signalez-le pour arbitrage.[/dim]")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        sys.exit(0)
