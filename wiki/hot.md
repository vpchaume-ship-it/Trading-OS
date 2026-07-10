<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN
     (sauf le bloc "Next Actions", préservé entre régénérations). -->
# État courant — 2026-07-10

## Stratégie auto-réglée
- Auto-réglage du 2026-07-10T06:55:07
- **ES** : Prudence — A/A+ uniquement (défaut) — aucune variante ne passe les garde-fous (≥10 trades, ≥+0.10 R/trade, PF ≥1.20) — collecte en cours
- **NQ** : Sweep session + V-shape (retest + prise partielle) — 30 trades · WR 43% · +0.91 R/trade · PF 2.45

## Wiki (3 experiences · 5 concepts · 3 research · 2 reference)
Entrées récentes du journal :
- [2026-07-09] bugfix | Tests des nouveaux filtres (sweep session, V-shape) sur scénarios synthétiques 2 jours | 66/66 passent ; CONCORDANCE.md mis à jour ; Next Actions posées
- [2026-07-13] decision | Ajout du « Professional Trader Mindset » dans CLAUDE.md (règles de raisonnement trader pro, défauts adaptés : MNQ, 1m/HTF, NY AM, 1 % risque) | actif à chaque session
- [2026-07-13] ingest | Vidéo TikTok « second brain Claude+Obsidian » (graphe dense auto-alimenté) analysée image par image | fiche de route PC créée (journal auto-généré = multiplicateur de nœuds à coût token nul)
- [2026-07-13] experience | Dashboard backtest rendu réellement évolutif : historique d'auto-réglage persistant (strategy_history.csv, delta vs veille), check de dégradation d'edge (1ʳᵉ vs 2ᵉ moitié), segment DD max sur l'equity | 71 tests verts ; premier snapshot : NQ 43 % WR +0.91R PF 2.45 (30 trades), ES négatif en fallback
- [2026-07-13] bugfix | Débordement horizontal mobile (150 px) : .card-head flex sans wrap + min-width:auto sur .price/.card, aggravé par les noms de variantes longs | vérifié à 390/360 px via Chromium headless : 0 px
- [2026-07-13] decision | Retrait de la section « Éval prop firm — Lucid 50K Pro » du dashboard (demande utilisateur) | module propsim.py et config conservés, réactivable
- [2026-07-13] ingest | Vidéo @huss.trades « Peak News Sources » (ForexFactory/Walter Bloomberg/FinancialJuice/Glint) | fil macro Google News RSS + météo du risque VIX/or/DXY ajoutés au dashboard ; X/FinancialJuice directs non faisables gratuitement (API payante)
- [2026-07-13] decision | Fil macro brut remplacé par une PRÉVISION news (verdict bullish/bearish/neutre indices + 3 moteurs pondérés) — demande utilisateur « je veux juste bullish ou bearish » | lexique directionnel + ratio sur titres directionnels seulement ; faux positifs « rate hike » de compagnies de gaz/électricité blacklistés

## Next Actions
<!-- next-actions:start -->
- Laisser l'échantillon grossir : 30 trades NQ sur le modèle sweep+V-shape, re-juger à ~60.
- ES ne passe toujours pas les garde-fous — vérifier si le V-shape aide ES quand plus de données profondes seront accumulées.
- Calibrer `vshape_min_move_ticks`/`vshape_max_bars` (20/8 posés a priori, jamais grid-searchés) — attention overfit.
- Premier lint du wiki quand ~10 pages de plus existeront.
<!-- next-actions:end -->
