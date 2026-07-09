# Trading OS

Système de recherche/backtest ICT IFVG (ES/NQ futures, 1 minute), **démo/paper
uniquement** — des garde-fous codés en dur interdisent le trading réel. Langue
du projet : français. Tests : `python -m pytest tests/ -q` (PYTHONPATH=racine).

## Wiki

Ce dépôt a un wiki maintenu par le LLM dans `wiki/` — sa mémoire persistante
entre les sessions. Deux règles PERMANENTES :

1. **Avant tout travail substantiel** : lire `wiki/index.md` PUIS
   `wiki/Failed Ideas/ledger.md` (pour ne pas refaire une impasse connue).
2. **Avant de terminer** : mettre à jour la ou les pages wiki concernées,
   appendre une ligne datée à `wiki/log.md`, et ajouter une ligne au registre
   Failed Ideas pour toute idée abandonnée.

Règles associées :
- Conventions, templates et workflows : `wiki/SCHEMA.md`.
- **Immutabilité** : le wiki LIE les sources brutes (PDFs de `knowledge/`,
  données de `data/`, code, sorties) et ne recopie jamais leur contenu comme
  source de vérité.
- `wiki/hot.md` est auto-généré par `wiki/update_hot.py` (hook Stop) — ne
  jamais l'éditer à la main, sauf son bloc « Next Actions ».
- `.obsidian/graph.json` est réécrit par Obsidian quand il tourne : ne l'éditer
  que si Obsidian est fermé.
