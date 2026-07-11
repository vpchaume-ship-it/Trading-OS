#!/usr/bin/env python3
"""Génère wiki/journal/YYYY-MM-DD.md — une page par jour tradé par la config
pré-enregistrée (data/trades_current.csv, écrit par le build du matin).

C'est le corpus d'entraînement de la « discrétion » : chaque setup mécanique y
est consigné avec son contexte ; le LLM annote les pages en session (bloc
« Lecture », préservé entre régénérations) et en tire des règles candidates.
Stdlib + pandas ; ne plante jamais le build. Idempotent : les stats sont
régénérées, les annotations manuelles/LLM conservées.
"""

from __future__ import annotations

import re
from pathlib import Path

WIKI = Path(__file__).resolve().parent
CSV = WIKI.parent / "data" / "trades_current.csv"
OUT = WIKI / "journal"
MARK = ("<!-- lecture:start -->", "<!-- lecture:end -->")


def _kept_reading(path: Path) -> str:
    if not path.exists():
        return "- (à annoter en session)"
    m = re.search(re.escape(MARK[0]) + r"(.*?)" + re.escape(MARK[1]),
                  path.read_text(encoding="utf-8"), re.S)
    body = m.group(1).strip() if m else ""
    return body or "- (à annoter en session)"


def main() -> None:
    import pandas as pd
    if not CSV.exists():
        print("journal: pas de trades_current.csv — rien à générer")
        return
    t = pd.read_csv(CSV)
    if t.empty:
        return
    # utc=True : un historique long mélange les offsets EDT (-04) et EST (-05)
    t["exit_time"] = pd.to_datetime(t["exit_time"], utc=True).dt.tz_convert("America/New_York")
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True).dt.tz_convert("America/New_York")
    OUT.mkdir(exist_ok=True)
    n_new = 0
    for day, g in t.groupby(t["exit_time"].dt.date):
        p = OUT / f"{day}.md"
        r = g["net_r"]
        rows = "".join(
            f"| {pd.Timestamp(x.entry_time):%H:%M} | {x.direction} | "
            f"{x.net_r:+.2f} R | {x.exit_reason} | {x.grade or '—'} |\n"
            for x in g.itertuples())
        body = f"""---
type: journal
updated: {day}
resultat_r: {r.sum():+.2f}
---
# Journal — {day}

{len(g)} trade(s) [[../concepts/ifvg|IFVG]] (config pré-enregistrée,
[[../experiences/2026-07-sweep-session-vshape|socle sweep+V-shape]]) :
**{r.sum():+.2f} R** · WR {(r > 0).mean():.0%}

| entrée | sens | R net | sortie | grade |
|---|---|---|---|---|
{rows}
## Lecture (annotation LLM/humaine — préservée)
{MARK[0]}
{_kept_reading(p)}
{MARK[1]}
"""
        if not p.exists() or p.read_text(encoding="utf-8") != body:
            p.write_text(body, encoding="utf-8")
            n_new += 1
    print(f"journal: {n_new} page(s) écrites/màj ({len(t)} trades)")


if __name__ == "__main__":
    main()
