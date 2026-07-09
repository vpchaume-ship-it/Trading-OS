#!/usr/bin/env python3
"""Régénère wiki/hot.md — l'« état courant » du projet — à partir de
wiki/log.md et data/strategy_state.json. Stdlib uniquement, ne plante jamais :
en cas de fichier manquant, il génère ce qu'il peut. Le bloc « Next Actions »
(entre les marqueurs next-actions:start/end) est préservé entre régénérations.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

WIKI = Path(__file__).resolve().parent
ROOT = WIKI.parent
HOT = WIKI / "hot.md"
N_LOG = 8

BANNER = ("<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN\n"
          "     (sauf le bloc \"Next Actions\", préservé entre régénérations). -->")
NA_START, NA_END = "<!-- next-actions:start -->", "<!-- next-actions:end -->"


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def last_log_entries(n: int = N_LOG) -> list[str]:
    lines = [l for l in read(WIKI / "log.md").splitlines() if l.startswith("## [")]
    return lines[-n:]


def strategy_state() -> list[str]:
    raw = read(ROOT / "data" / "strategy_state.json")
    if not raw:
        return ["- (pas de data/strategy_state.json)"]
    try:
        d = json.loads(raw)
    except ValueError:
        return ["- (strategy_state.json illisible)"]
    out = [f"- Auto-réglage du {d.get('chosen_at', '?')}"]
    for inst, sel in (d.get("instruments") or {}).items():
        v = sel.get("variant", "?") if isinstance(sel, dict) else "?"
        r = sel.get("reason", "") if isinstance(sel, dict) else ""
        out.append(f"- **{inst}** : {v}" + (f" — {r}" if r else ""))
    return out


def preserved_next_actions() -> str:
    m = re.search(re.escape(NA_START) + r"(.*?)" + re.escape(NA_END),
                  read(HOT), re.S)
    body = m.group(1).strip() if m else ""
    return body or "- (à remplir)"


def wiki_counts() -> str:
    parts = []
    for sub in ("experiences", "concepts", "research", "reference"):
        n = len(list((WIKI / sub).glob("*.md"))) if (WIKI / sub).is_dir() else 0
        parts.append(f"{n} {sub}")
    return " · ".join(parts)


def main() -> None:
    logs = last_log_entries()
    content = "\n".join([
        BANNER,
        f"# État courant — {date.today().isoformat()}",
        "",
        "## Stratégie auto-réglée",
        *strategy_state(),
        "",
        f"## Wiki ({wiki_counts()})",
        "Entrées récentes du journal :",
        *([f"- {l.removeprefix('## ')}" for l in logs] or ["- (log vide)"]),
        "",
        "## Next Actions",
        NA_START,
        preserved_next_actions(),
        NA_END,
        "",
    ])
    try:
        HOT.write_text(content, encoding="utf-8")
        print(f"hot.md régénéré ({len(logs)} entrées de log)")
    except OSError as e:  # jamais bloquant
        print(f"update_hot: écriture impossible ({e})")


if __name__ == "__main__":
    main()
