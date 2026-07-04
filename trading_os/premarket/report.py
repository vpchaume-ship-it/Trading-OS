"""Daily premarket report (Module 4) — markdown, generated before London or NY."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from trading_os.core.timeutils import NY
from trading_os.data.loader import load_csv
from trading_os.journal.store import Journal
from trading_os.news.calendar import fetch_red_folders, append_history
from trading_os.news.scenarios import build_card, card_markdown
from trading_os.premarket import levels as lv
from trading_os.premarket.bias import BIAS_REMINDER, daily_bias


def _fmt_price(x: float) -> str:
    return f"{x:,.2f}"


def _instrument_section(name: str, csv_path: str, cfg: dict) -> list[str]:
    pcfg = cfg["premarket"]
    spec = cfg["instruments"][name]
    tick = spec["tick_size"]
    lines = [f"## {name}", ""]
    try:
        df = load_csv(csv_path, cfg["data"]["csv_timezone"])
    except FileNotFoundError:
        return lines + [f"_Pas de données ({csv_path} introuvable) — lancer l'export MT5._", ""]

    bias, reason = daily_bias(lv.daily_sessions(df))
    icon = {"haussier": "🟢", "baissier": "🔴", "neutre": "⚪"}[bias]
    lines += [f"### Daily bias (PDH/PDL) : {icon} **{bias.upper()}**",
              f"- {reason}", f"- _{BIAS_REMINDER}_", ""]

    pd_lv = lv.previous_day_levels(df)
    pw_lv = lv.previous_week_levels(df)
    if pd_lv:
        lines += [
            "| Niveau | Prix |", "|---|---|",
            f"| High veille (PDH) | {_fmt_price(pd_lv['pdh'])} |",
            f"| Low veille (PDL) | {_fmt_price(pd_lv['pdl'])} |",
            f"| Close veille (PDC) | {_fmt_price(pd_lv['pdc'])} |",
        ]
    if pw_lv:
        lines += [
            f"| High semaine précédente (PWH) | {_fmt_price(pw_lv['pwh'])} |",
            f"| Low semaine précédente (PWL) | {_fmt_price(pw_lv['pwl'])} |",
        ]
    lines.append("")

    gaps = lv.opening_gaps(df)
    lines.append("### Gaps d'ouverture non comblés (NDOG / NWOG)")
    if gaps:
        for g in gaps:
            lines.append(f"- **{g.kind}** du {g.open_time:%d/%m} : "
                         f"{_fmt_price(g.low)} → {_fmt_price(g.high)}")
    else:
        lines.append("- Aucun gap ouvert récent.")
    lines.append("")

    lines.append("### FVG non mitigés (HTF)")
    fvgs = lv.htf_unmitigated_fvgs(df, cfg["premarket"]["htf_timeframes"], tick)
    for tf, zones in fvgs.items():
        if zones:
            for f in zones:
                lines.append(f"- **{tf} {f.direction.value}** ({f.created_time:%d/%m %H:%M}) : "
                             f"{_fmt_price(f.bottom)} → {_fmt_price(f.top)}")
        else:
            lines.append(f"- {tf} : aucun.")
    lines.append("")

    lines.append("### Liquidité évidente (equal highs/lows)")
    pools = lv.liquidity_pools(df, tick, pcfg["equal_level_tolerance_ticks"],
                               pcfg["swing_strength"])
    if pools:
        pools = sorted(pools, key=lambda p: (-p.count, -p.price))[:12]
        for p in sorted(pools, key=lambda p: -p.price):
            side = "🔼 buy-side" if p.kind == "equal_highs" else "🔽 sell-side"
            lines.append(f"- {side} : {_fmt_price(p.price)} ({p.count} touches)")
    else:
        lines.append("- Aucun pool net détecté sur le lookback récent.")
    lines.append("")
    return lines


def generate(cfg: dict, csv_paths: dict[str, str]) -> Path:
    """csv_paths: {'ES': 'data/ES_1m.csv', 'NQ': 'data/NQ_1m.csv'}."""
    now = datetime.now(NY)
    lines = [f"# Rapport prémarché — {now:%A %d %B %Y} ({now:%H:%M} NY)", ""]

    # --- Red folders du jour + cartes de scénarios --------------------
    lines += ["# 🔴 News à fort impact aujourd'hui", ""]
    ncfg = cfg["news"]["no_trade_zone"]
    try:
        events = fetch_red_folders(cfg)
        append_history(events, cfg["backtest"]["news_history_csv"])
        today = [e for e in events if e.time_ny.date() == now.date()]
        if today:
            for e in today:
                ntz = e.no_trade_zone(ncfg["minutes_before"], ncfg["minutes_after"])
                lines.append(card_markdown(build_card(e), ntz))
        else:
            lines += ["Aucun red folder USD aujourd'hui. Journée technique pure.", ""]
        upcoming = [e for e in events if e.time_ny.date() > now.date()]
        if upcoming:
            lines += ["**À venir cette semaine :** " +
                      ", ".join(f"{e.title} ({e.time_ny:%a %H:%M})" for e in upcoming[:8]), ""]
    except Exception as exc:  # network failure must not kill the report
        lines += [f"_⚠️ Calendrier inaccessible ({exc}) — vérifier manuellement ForexFactory !_", ""]

    # --- Niveaux par instrument ---------------------------------------
    for name in cfg["premarket"]["instruments"]:
        lines += _instrument_section(name, csv_paths.get(name, ""), cfg)

    # --- Killzones + stats personnelles -------------------------------
    lines += ["## Killzones du jour (heure NY)", ""]
    for name, z in cfg["killzones"].items():
        lines.append(f"- **{name}** : {z['start']} → {z['end']}")
    lines.append("")
    stats = Journal(cfg["journal"]["directory"]).killzone_stats()
    if not stats.empty:
        lines += ["### Mes stats historiques par killzone (journal forward test)", "",
                  stats.to_markdown(), ""]
    else:
        lines += ["_Pas encore de trades dans le journal — les stats par killzone "
                  "apparaîtront ici._", ""]

    # --- Checklist discipline ------------------------------------------
    lines += ["## ✅ Checklist avant CHAQUE trade", ""]
    lines += [f"- [ ] {item}" for item in cfg["premarket"]["checklist"]]
    lines += ["", "---", "_Généré par Trading OS — démo uniquement. La carte de scénarios "
              "est une aide à la préparation, pas une prédiction._"]

    out_dir = Path(cfg["journal"]["directory"]) / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"premarket_{now:%Y%m%d}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
