---
type: hub
updated: 2026-07-09
---
# Journal (append-only)

> Une ligne datée par événement : `## [YYYY-MM-DD] <type> | <quoi> | <résultat>`.
> Types : setup, experience, ingest, decision, lint, bugfix, routine.
> On n'édite JAMAIS une entrée existante — on ajoute seulement.
> Parseable : `grep "^## \[" wiki/log.md | tail -5` donne les 5 dernières entrées.

## [2026-07-09] setup | Création du wiki LLM (hubs, experiences/concepts/research/reference, Failed Ideas, SCHEMA, CLAUDE.md, update_hot.py, hooks, Obsidian) | opérationnel, seedé avec la connaissance du projet
## [2026-07-07] experience | Modèle utilisateur sweep session + IFVG + V-shape codé et backtesté (NQ 120k barres) | WR 32→47 %, +1.58R, PF 3.64 — retenu comme défaut
## [2026-07-07] decision | min_rating 9 → 0 : la qualité du setup vient du contexte (sweep+V-shape), pas de la note de bougie | config.yaml + grille auto-tune refaite
## [2026-07-09] bugfix | Tests des nouveaux filtres (sweep session, V-shape) sur scénarios synthétiques 2 jours | 66/66 passent ; CONCORDANCE.md mis à jour ; Next Actions posées
