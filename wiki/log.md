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
## [2026-07-13] decision | Ajout du « Professional Trader Mindset » dans CLAUDE.md (règles de raisonnement trader pro, défauts adaptés : MNQ, 1m/HTF, NY AM, 1 % risque) | actif à chaque session
## [2026-07-13] ingest | Vidéo TikTok « second brain Claude+Obsidian » (graphe dense auto-alimenté) analysée image par image | fiche de route PC créée (journal auto-généré = multiplicateur de nœuds à coût token nul)
## [2026-07-13] experience | Dashboard backtest rendu réellement évolutif : historique d'auto-réglage persistant (strategy_history.csv, delta vs veille), check de dégradation d'edge (1ʳᵉ vs 2ᵉ moitié), segment DD max sur l'equity | 71 tests verts ; premier snapshot : NQ 43 % WR +0.91R PF 2.45 (30 trades), ES négatif en fallback
## [2026-07-13] bugfix | Débordement horizontal mobile (150 px) : .card-head flex sans wrap + min-width:auto sur .price/.card, aggravé par les noms de variantes longs | vérifié à 390/360 px via Chromium headless : 0 px
## [2026-07-13] decision | Retrait de la section « Éval prop firm — Lucid 50K Pro » du dashboard (demande utilisateur) | module propsim.py et config conservés, réactivable
## [2026-07-13] ingest | Vidéo @huss.trades « Peak News Sources » (ForexFactory/Walter Bloomberg/FinancialJuice/Glint) | fil macro Google News RSS + météo du risque VIX/or/DXY ajoutés au dashboard ; X/FinancialJuice directs non faisables gratuitement (API payante)
## [2026-07-13] decision | Fil macro brut remplacé par une PRÉVISION news (verdict bullish/bearish/neutre indices + 3 moteurs pondérés) — demande utilisateur « je veux juste bullish ou bearish » | lexique directionnel + ratio sur titres directionnels seulement ; faux positifs « rate hike » de compagnies de gaz/électricité blacklistés
## [2026-07-10] decision | ES retiré comme instrument tradé : NQ uniquement (guards MNQ seul, config/CLI/deep/accumulate NQ, CSV ES supprimés, défauts = retest + prise partielle) ; ES conservé comme référence SMT au build | pytest complet à vérifier
## [2026-07-11] setup | Rafraîchissement intraday du dashboard : 2 triggers cron (13:30-16:30 UTC, semaine) + porte killzone NY DST-proof dans scripts/intraday_update.sh + build --light qui rejoue strategy_state.json (autotune strictement 1×/jour, anti-overfitting) | build léger 11 s vs plusieurs min ; 82 tests verts
## [2026-07-11] bugfix | Patches VARIANTS rendus explicites (entry_timing + exit_mode) : depuis le passage des défauts à retest+scale, 3 variantes sur 4 tournaient identiques sous des étiquettes fausses | test anti-doublon ajouté ; l'autotune du matin redevient une vraie comparaison
