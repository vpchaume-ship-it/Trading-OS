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
## [2026-07-11] bugfix | La fenêtre backtest était FIGÉE au 6/7 (repéré par l'utilisateur sur capture) : la routine du matin n'étendait pas l'historique profond Dukascopy, prioritaire sur Yahoo | refresh_deep("NQ") incrémental branché dans accumulate.main() ; deep 341k barres jusqu'au 10/7, fenêtre glissante 95k confirmée (01/04→10/07) ; autotune re-choisit retest+partielle (27 trades, WR 41 %, +1.02 R, PF 2.54)
## [2026-07-11] decision | Audit sécurité repo public : AUCUN secret dans les fichiers ni dans tout l'historique (identifiants Tradovate jamais committés, .env jamais versionné, .env.example = placeholders) ; PDFs knowledge/ conservés (contenu non payant, confirmé par l'utilisateur) | reste optionnel : email perso dans les métadonnées d'auteur des commits GitHub
## [2026-07-11] experience | Boucle d'auto-ajustement livrée : diagnose.py (pourquoi quotidien : tranches horaires/NTZ/RR/stops same-bar/DD) + feedback.py (4 règles evidence-gated ≥8 trades, 1 décision/jour, garde-fous durs codés, anti-overfit auto-revert, expiry 28 j) + fenêtre d'entrée moteur + section dashboard transparente (actifs, socle vs ajusté, historique, diagnostic) | 91 tests verts ; 1er passage : aucun ajustement (pas d'évidence) — comportement attendu
## [2026-07-11] bugfix | AUDIT QA complet : C1 lookahead niveaux overnight (fenêtre en formation utilisée par ses propres setups + jour calendaire vs jour de trading CME — dimanche soir = « veille » du lundi) ; C2 slippage 0 sur l'entrée marché inversion_close ; M1 fill limite au touch (optimiste) → trade-through strict ; M2 ordre annulé gratuitement sur barre de reclaim → rempli puis stoppé ; M3 anti-overfit feedback mesurait la dérive du marché → comparaison directe ajusté-vs-socle | 99 tests verts ; chiffres corrigés : retest+partielle 41 %→23 % WR (+0.13 R), inversion 25 % WR +0.93 R PF 2.19 retenue par l'autotune — l'edge survit, le WR flatteur était de l'exécution optimiste
