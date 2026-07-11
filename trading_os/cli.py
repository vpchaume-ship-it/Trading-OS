"""Trading OS — main terminal application (rich).

Usage:  python -m trading_os.cli
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from trading_os.config import load_config
from trading_os.core.timeutils import NY, Killzones

console = Console()

ACCENT = "bright_cyan"
DIM = "grey58"

_news_cache: list | None = None  # fetched once per session


# ====================================================================== UI

def _fetch_news_once(cfg: dict) -> list:
    global _news_cache
    if _news_cache is None:
        try:
            from trading_os.news.calendar import append_history, fetch_red_folders
            _news_cache = fetch_red_folders(cfg)
            append_history(_news_cache, cfg["backtest"]["news_history_csv"])
        except Exception:
            _news_cache = []
    return _news_cache


def _data_status(cfg: dict) -> Text:
    t = Text()
    for name in cfg["premarket"]["instruments"]:
        p = Path(f"data/{name}_1m.csv")
        if p.exists():
            age_h = (datetime.now().timestamp() - p.stat().st_mtime) / 3600
            style = "green" if age_h < 24 else "yellow"
            t.append(f"● {name} ", style=style)
        else:
            t.append(f"○ {name} ", style="red")
    return t


def _journal_status(cfg: dict) -> str:
    try:
        from trading_os.journal.store import Journal
        df = Journal(cfg["journal"]["directory"]).load()
        if df.empty:
            return "journal vide"
        r = df["net_r"].dropna()
        return f"{len(df)} trades" + (f" · {r.sum():+.1f} R" if len(r) else "")
    except Exception:
        return "journal vide"


def _header(cfg: dict) -> Panel:
    now = datetime.now(NY)
    kz = Killzones(cfg["killzones"]).label(now)
    kz_txt = Text()
    if kz:
        allowed = kz in cfg["ifvg"]["allowed_killzones"]
        kz_txt.append(f"⏱ {kz}", style="bold green" if allowed else "yellow")
        kz_txt.append(" (autorisée)" if allowed else " (non autorisée)", style=DIM)
    else:
        kz_txt.append("⏱ hors killzone", style=DIM)

    news_txt = Text()
    events = _fetch_news_once(cfg)
    today = [e for e in events if e.time_ny.date() == now.date()]
    upcoming = [e for e in today if e.time_ny > now]
    if upcoming:
        nxt = upcoming[0]
        mins = int((nxt.time_ny - now).total_seconds() // 60)
        style = "bold red" if mins <= 45 else "red"
        news_txt.append(f"🔴 {nxt.title} dans {mins // 60}h{mins % 60:02d}", style=style)
    elif today:
        news_txt.append(f"🔴 {len(today)} red folder(s) aujourd'hui (passés)", style=DIM)
    else:
        news_txt.append("✓ aucun red folder aujourd'hui", style="green")

    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(justify="left"); grid.add_column(justify="center")
    grid.add_column(justify="center"); grid.add_column(justify="right")
    grid.add_row(
        Text(f"{now:%a %d %b · %H:%M} NY", style=DIM),
        kz_txt, news_txt,
        Text.assemble(_data_status(cfg), (f"│ {_journal_status(cfg)}", DIM)),
    )

    title = Text()
    title.append("  T R A D I N G   O S  ", style=f"bold black on {ACCENT}")
    title.append("  NQ · ICT IFVG", style="bold white")
    title.append("  ·  DÉMO UNIQUEMENT", style="bold red")

    return Panel(Group(Align.center(title), Rule(style=DIM), grid),
                 box=box.HEAVY, border_style=ACCENT, padding=(0, 1))


def _menu_table() -> Table:
    t = Table(box=box.SIMPLE_HEAD, show_header=False, expand=True,
              padding=(0, 1), pad_edge=False)
    t.add_column("k", style=f"bold {ACCENT}", width=3, justify="center")
    t.add_column("module", style="bold", width=26)
    t.add_column("description", style=DIM)
    t.add_row("1", "📰 News & red folders", "calendrier USD fort impact, scénarios, no-trade-zones")
    t.add_row("2", "📊 Backtest IFVG", "moteur historique : win rate, R, drawdown, rapport + graphes")
    t.add_row("3", "🛰️  Forward test DEMO", "Tradovate demo : semi-auto, journal, rapport hebdo")
    t.add_row("4", "🌅 Rapport prémarché", "biais du jour, niveaux, FVG HTF, liquidité, checklist")
    t.add_row("5", "📚 Connaissances", "vos PDF ICT : indexation, recherche, concordance")
    t.add_row("6", "📱 Dashboard mobile", "génère la page prémarché publiée sur votre téléphone")
    t.add_row("0", "🚪 Quitter", "")
    return t


def main_menu() -> None:
    cfg = load_config()
    while True:
        console.print()
        console.print(_header(cfg))
        console.print(_menu_table())
        choice = Prompt.ask(Text("Choix", style=f"bold {ACCENT}"),
                            choices=["0", "1", "2", "3", "4", "5", "6"], default="4")
        try:
            if choice == "0":
                console.print(Panel("À demain. [bold]Discipline > conviction.[/bold] 👋",
                                    box=box.ROUNDED, border_style=DIM))
                return
            {"1": menu_news, "2": menu_backtest, "3": menu_forward,
             "4": menu_premarket, "5": menu_knowledge,
             "6": menu_dashboard}[choice](cfg)
        except KeyboardInterrupt:
            console.print(f"\n[{DIM}]Interrompu — retour au menu.[/{DIM}]")
        except Exception as exc:
            console.print(Panel(f"{exc}", title="⚠ Erreur", border_style="red",
                                box=box.ROUNDED))


# ---------------------------------------------------------------- Module 1
def menu_news(cfg: dict) -> None:
    from trading_os.news.scenarios import build_card, card_markdown

    console.print(Rule("📰 Red folders de la semaine", style=ACCENT))
    global _news_cache
    _news_cache = None                       # force un rafraîchissement
    events = _fetch_news_once(cfg)
    if not events:
        console.print("[green]Aucun red folder USD cette semaine (ou flux inaccessible).[/green]")
        return
    ncfg = cfg["news"]["no_trade_zone"]
    now = datetime.now(NY)
    for e in events:
        ntz = e.no_trade_zone(ncfg["minutes_before"], ncfg["minutes_after"])
        past = e.time_ny < now
        console.print(Panel(Markdown(card_markdown(build_card(e), ntz)),
                            border_style=DIM if past else "red",
                            box=box.ROUNDED,
                            title=f"[bold]{e.time_ny:%a %H:%M}[/bold] NY"
                                  + (" · passé" if past else "")))


# ---------------------------------------------------------------- Module 2
def menu_backtest(cfg: dict) -> None:
    from trading_os.backtest.engine import run_backtest
    from trading_os.backtest.metrics import breakdown, summary
    from trading_os.backtest.report import write_report
    from trading_os.data.loader import load_csv, resample

    console.print(Rule("📊 Backtest IFVG", style=ACCENT))
    instrument = Prompt.ask("Instrument", choices=list(cfg["instruments"]),
                            default=cfg["backtest"]["instrument"])
    default_csv = cfg["backtest"]["csv_file"] or f"data/{instrument}_1m.csv"
    csv_path = Prompt.ask("Fichier CSV 1m", default=default_csv)
    if not Path(csv_path).exists():
        console.print(Panel(
            f"[red]{csv_path} introuvable.[/red]\n\nExporter d'abord depuis MT5 "
            f"(sur votre machine Windows) :\n[bold]python scripts/export_mt5.py "
            f"--symbol {cfg['instruments'][instrument]['mt5_symbol']} --days 365 "
            f"--out {csv_path}[/bold]", box=box.ROUNDED, border_style="yellow"))
        return

    with console.status(f"[{ACCENT}]Chargement des données…"):
        df = load_csv(csv_path, cfg["data"]["csv_timezone"])
        tf = cfg["ifvg"]["timeframe"]
        if tf not in ("1min", "1m"):
            df = resample(df, tf)
    console.print(f"[{DIM}]{len(df):,} barres {tf} · "
                  f"{df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}[/{DIM}]")

    with console.status(f"[{ACCENT}]Backtest en cours…"):
        result = run_backtest(df, cfg, instrument)
    stats = summary(result.trades)
    if stats["n_trades"] == 0:
        console.print(Panel("Aucun trade généré — élargir la période ou assouplir "
                            "les paramètres (section ifvg de config.yaml).",
                            box=box.ROUNDED, border_style="yellow"))
    else:
        def col(v: float, fmt: str) -> str:
            style = "green" if v > 0 else "red"
            return f"[{style}]{v:{fmt}}[/{style}]"

        t = Table(title=f"Résultats {instrument} — {stats['n_trades']} trades (R net, coûts inclus)",
                  box=box.ROUNDED, border_style=ACCENT, title_style="bold")
        t.add_column("Métrique"); t.add_column("Valeur", justify="right")
        t.add_row("Win rate", f"{stats['win_rate']:.1%}")
        t.add_row("Espérance / trade", col(stats['expectancy_r'], '+.3f') + " R")
        t.add_row("Profit factor", f"{stats['profit_factor']:.2f}")
        t.add_row("Total", col(stats['total_r'], '+.1f') + f" R ({stats['total_pnl_usd']:+,.0f} $)")
        t.add_row("Drawdown max", f"[red]{stats['max_drawdown_r']:.1f} R[/red]")
        t.add_row("Pertes consécutives max", str(stats['max_consecutive_losses']))
        console.print(t)

        by_grade = breakdown(result.trades, "grade")
        if not by_grade.empty:
            g = Table(title="Par grade d'inversion (notation PDF /10)",
                      box=box.SIMPLE, title_style=DIM)
            g.add_column("Grade", style="bold"); g.add_column("Trades", justify="right")
            g.add_column("Win rate", justify="right"); g.add_column("R moyen", justify="right")
            for grade, row in by_grade.iterrows():
                g.add_row(str(grade), str(int(row["trades"])),
                          f"{row['win_rate']:.0%}", f"{row['avg_r']:+.2f}")
            console.print(g)

    path = write_report(result, Path(cfg["journal"]["directory"]))
    console.print(f"[green]✓ Rapport écrit :[/green] {path}")


# ---------------------------------------------------------------- Module 3
def menu_forward(cfg: dict) -> None:
    from trading_os.forward.guards import SafetyViolation, assert_daily_loss_ok
    from trading_os.forward.journal_sync import realized_pnl_today

    console.print(Rule("🛰️  Forward test — Tradovate DEMO", style=ACCENT))
    console.print(Panel(
        "[bold red]DEMO UNIQUEMENT[/bold red] — garde-fous codés en dur :\n"
        "URL demo obligatoire · 1 micro contrat max (MES/MNQ) · limite de perte "
        "journalière · pas de trade en no-trade-zone.",
        box=box.ROUNDED, border_style="red"))
    mode = Prompt.ask("Mode", choices=["semi-auto", "journal", "hebdo", "retour"],
                      default="journal")
    try:
        if mode == "retour":
            return
        if mode == "hebdo":
            from trading_os.forward.compare import weekly_report
            path = weekly_report(cfg)
            console.print(f"[green]✓ Rapport hebdomadaire :[/green] {path}")
            return
        assert_daily_loss_ok(realized_pnl_today(cfg),
                             cfg["forward"]["daily_loss_limit_usd"])
        if mode == "journal":
            from trading_os.forward.journal_sync import sync_journal
            with console.status(f"[{ACCENT}]Synchronisation des fills demo…"):
                added = sync_journal(cfg)
            console.print(f"[green]✓ {added} trade(s) ajouté(s) au journal.[/green]")
        else:
            from trading_os.forward.monitor import run_semi_auto
            instrument = Prompt.ask("Instrument", choices=list(cfg["instruments"]),
                                    default="NQ")
            run_semi_auto(cfg, instrument, console)
    except SafetyViolation as sv:
        console.print(Panel(str(sv), title="🛑 GARDE-FOU", border_style="bold red",
                            box=box.HEAVY))


# ---------------------------------------------------------------- Module 4
def menu_premarket(cfg: dict) -> None:
    from trading_os.premarket.report import generate

    console.print(Rule("🌅 Rapport prémarché", style=ACCENT))
    csv_paths = {name: f"data/{name}_1m.csv" for name in cfg["premarket"]["instruments"]}
    with console.status(f"[{ACCENT}]Génération du rapport…"):
        path = generate(cfg, csv_paths)
    console.print(f"[green]✓ Rapport écrit :[/green] {path}")
    if Confirm.ask("Afficher dans le terminal ?", default=True):
        console.print(Panel(Markdown(Path(path).read_text(encoding="utf-8")),
                            box=box.ROUNDED, border_style=DIM))


# ---------------------------------------------------------------- Dashboard
def menu_dashboard(cfg: dict) -> None:
    from trading_os.webapp.build import build_dashboard

    console.print(Rule("📱 Dashboard mobile", style=ACCENT))
    with console.status(f"[{ACCENT}]Données Yahoo Finance + ForexFactory…"):
        path = build_dashboard(cfg, "journal/reports/dashboard.html")
    console.print(f"[green]✓ Page générée :[/green] {path}")
    console.print(f"[{DIM}]La version téléphone est republiée automatiquement chaque "
                  f"matin de semaine (routine planifiée) — pas besoin de la lancer "
                  f"à la main, sauf pour un rafraîchissement immédiat.[/{DIM}]")


# ---------------------------------------------------------------- Knowledge
def menu_knowledge(cfg: dict) -> None:
    from trading_os.knowledge_base.indexer import (build_index, concept_extracts,
                                                   load_index, search)

    console.print(Rule("📚 Base de connaissances", style=ACCENT))
    action = Prompt.ask("Action", choices=["indexer", "chercher", "concepts", "retour"],
                        default="chercher")
    if action == "retour":
        return
    if action == "indexer":
        with console.status(f"[{ACCENT}]Indexation des PDF…"):
            index = build_index(cfg)
        console.print(f"[green]✓ {index['n_files']} fichier(s), "
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
            console.print(f"[{DIM}]Aucun résultat.[/{DIM}]")
        for h in hits:
            console.print(Panel(h["snippet"], title=f"{h['file']} · p.{h['page']}",
                                box=box.ROUNDED, border_style=DIM))
    else:
        extracts = concept_extracts(cfg)
        if not extracts:
            console.print(f"[{DIM}]Aucun concept suivi trouvé dans le texte des PDF "
                          f"(les slides graphiques s'extraient mal — voir "
                          f"knowledge/CONCORDANCE.md).[/{DIM}]")
        for concept, passages in extracts.items():
            console.print(Panel("\n\n".join(
                f"[bold]{p['file']}[/bold] p.{p['page']} — {p['snippet']}"
                for p in passages), title=f"📖 {concept}", box=box.ROUNDED))
        console.print(f"[{DIM}]Synthèse et points d'arbitrage : "
                      f"knowledge/CONCORDANCE.md[/{DIM}]")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        sys.exit(0)
