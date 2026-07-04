"""Semi-auto mode: real-time IFVG detection on a live-updating CSV
(fed by `scripts/export_mt5.py --watch` running on your Windows machine),
terminal notification, manual validation. The system NEVER enters alone.

Stops immediately on: daily loss limit hit, or a red-folder no-trade zone.
"""

from __future__ import annotations

import time as time_mod
from datetime import datetime

import pandas as pd
from rich.console import Console
from rich.panel import Panel

from trading_os.core.fvg import FVGTracker, InversionEvent, RetestEvent
from trading_os.core.rating import rate_inversion
from trading_os.core.timeutils import NY, Killzones
from trading_os.data.loader import load_csv
from trading_os.forward.guards import assert_daily_loss_ok
from trading_os.forward.journal_sync import realized_pnl_today
from trading_os.news.calendar import fetch_red_folders
from trading_os.premarket.mtf_bias import day_status


def run_semi_auto(cfg: dict, instrument: str, console: Console) -> None:
    fcfg = cfg["forward"]
    icfg = cfg["ifvg"]
    spec = cfg["instruments"][instrument]
    csv_path = fcfg.get("live_csv") or ""
    if not csv_path:
        console.print("[red]forward.live_csv non renseigné dans config.yaml.[/red]")
        console.print("Lancer sur votre machine Windows :\n"
                      f"  python scripts/export_mt5.py --symbol {spec['mt5_symbol']}"
                      " --watch --out data/live.csv\npuis pointer forward.live_csv dessus.")
        return

    kz = Killzones(cfg["killzones"])
    ncfg = cfg["news"]["no_trade_zone"]
    try:
        events = fetch_red_folders(cfg)
        ntz = [e.no_trade_zone(ncfg["minutes_before"], ncfg["minutes_after"]) for e in events]
    except Exception as exc:
        console.print(f"[yellow]Calendrier news inaccessible ({exc}) — "
                      "prudence, NTZ non chargées ![/yellow]")
        ntz = []

    tracker = FVGTracker(
        tick_size=spec["tick_size"], min_gap_ticks=icfg["min_gap_ticks"],
        invalidation_mode=icfg["invalidation_mode"], wick_fill_kills=icfg["wick_fill_kills"],
        fvg_max_age_bars=icfg["fvg_max_age_bars"], ifvg_max_age_bars=icfg["ifvg_max_age_bars"],
        max_retests=icfg["max_retests_per_zone"])

    console.print(Panel(f"Semi-auto {instrument} — détection IFVG en temps réel.\n"
                        "Le système NOTIFIE, vous validez manuellement sur Tradovate demo.\n"
                        "Ctrl+C pour arrêter.", title="Mode semi-auto", style="cyan"))

    last_ts = None
    seen = 0
    ratings: dict[int, object] = {}  # id(fvg) -> InversionRating
    min_rating = icfg.get("min_rating", 0)
    while True:
        # market open? (weekend / NYSE holiday -> pause, no forward test)
        kind, day_label = day_status(datetime.now(NY))
        if kind == "closed":
            console.print(f"[dim]{day_label} — surveillance en pause, "
                          "revérification dans 10 min.[/dim]")
            time_mod.sleep(600)
            continue
        # daily-loss guard, re-checked every cycle
        assert_daily_loss_ok(realized_pnl_today(cfg), fcfg["daily_loss_limit_usd"])
        try:
            df = load_csv(csv_path, cfg["data"]["csv_timezone"])
        except FileNotFoundError:
            console.print(f"[yellow]{csv_path} pas encore créé — attente…[/yellow]")
            time_mod.sleep(fcfg["poll_seconds"]); continue

        # only process bars we haven't seen; the last row may still be forming -> skip it
        closed = df.iloc[:-1]
        new = closed if last_ts is None else closed[closed.index > last_ts]
        for ts, row in new.iterrows():
            for ev in tracker.update(seen, ts, row["open"], row["high"],
                                     row["low"], row["close"]):
                now = datetime.now(NY)
                in_kz = kz.in_any(now, icfg["allowed_killzones"])
                in_ntz = any(a <= now <= b for a, b in ntz)
                if isinstance(ev, InversionEvent):
                    r = rate_inversion(ev.fvg, row["open"], row["high"],
                                       row["low"], row["close"])
                    ratings[id(ev.fvg)] = r
                    console.print(f"[yellow]⚡ {ts:%H:%M} Inversion détectée — "
                                  f"IFVG {ev.fvg.ifvg_direction.value} "
                                  f"{ev.fvg.bottom:.2f}→{ev.fvg.top:.2f} — "
                                  f"grade {r.grade} ({r.total}/10) — "
                                  f"attendre le retest.[/yellow]")
                elif isinstance(ev, RetestEvent):
                    r = ratings.get(id(ev.fvg))
                    if r is not None and r.total < min_rating:
                        console.print(f"[dim]{ts:%H:%M} Retest IFVG grade {r.grade} "
                                      f"({r.total}/10) < seuil A — ignoré.[/dim]")
                        continue
                    if in_ntz:
                        console.print(f"[red]🚫 {ts:%H:%M} Retest IFVG mais NO-TRADE-ZONE "
                                      "news active — on ne touche à rien.[/red]")
                    elif not in_kz:
                        console.print(f"[dim]{ts:%H:%M} Retest IFVG hors killzone — ignoré.[/dim]")
                    else:
                        console.bell()
                        r = ratings.get(id(ev.fvg))
                        grade_line = (f"Grade inversion : {r.grade} ({r.total}/10)\n"
                                      if r else "")
                        console.print(Panel(
                            f"SETUP IFVG {ev.fvg.ifvg_direction.value.upper()} sur {instrument}\n"
                            f"Zone : {ev.fvg.bottom:.2f} → {ev.fvg.top:.2f}\n"
                            f"{grade_line}"
                            f"Stop au-delà de la zone + {icfg['stop_buffer_ticks']} ticks\n"
                            f"Killzone : {kz.label(now)}\n"
                            "→ Validez MANUELLEMENT sur Tradovate demo (1 micro max).",
                            title="🔔 SETUP DÉTECTÉ", style="bold green"))
            seen += 1
        if len(closed):
            last_ts = closed.index[-1]
        time_mod.sleep(fcfg["poll_seconds"])
