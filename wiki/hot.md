<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN
     (sauf le bloc "Next Actions", préservé entre régénérations). -->
# État courant — 2026-07-11

## Stratégie auto-réglée
- Auto-réglage du 2026-07-11T08:55:46
- **NQ** : Sweep session + V-shape (clôture inversion) — 30 trades · WR 43% · +0.91 R/trade · PF 2.45

## Wiki (3 experiences · 5 concepts · 3 research · 2 reference)
Entrées récentes du journal :
- [2026-07-13] experience | Dashboard backtest rendu réellement évolutif : historique d'auto-réglage persistant (strategy_history.csv, delta vs veille), check de dégradation d'edge (1ʳᵉ vs 2ᵉ moitié), segment DD max sur l'equity | 71 tests verts ; premier snapshot : NQ 43 % WR +0.91R PF 2.45 (30 trades), ES négatif en fallback
- [2026-07-13] bugfix | Débordement horizontal mobile (150 px) : .card-head flex sans wrap + min-width:auto sur .price/.card, aggravé par les noms de variantes longs | vérifié à 390/360 px via Chromium headless : 0 px
- [2026-07-13] decision | Retrait de la section « Éval prop firm — Lucid 50K Pro » du dashboard (demande utilisateur) | module propsim.py et config conservés, réactivable
- [2026-07-13] ingest | Vidéo @huss.trades « Peak News Sources » (ForexFactory/Walter Bloomberg/FinancialJuice/Glint) | fil macro Google News RSS + météo du risque VIX/or/DXY ajoutés au dashboard ; X/FinancialJuice directs non faisables gratuitement (API payante)
- [2026-07-13] decision | Fil macro brut remplacé par une PRÉVISION news (verdict bullish/bearish/neutre indices + 3 moteurs pondérés) — demande utilisateur « je veux juste bullish ou bearish » | lexique directionnel + ratio sur titres directionnels seulement ; faux positifs « rate hike » de compagnies de gaz/électricité blacklistés
- [2026-07-10] decision | ES retiré comme instrument tradé : NQ uniquement (guards MNQ seul, config/CLI/deep/accumulate NQ, CSV ES supprimés, défauts = retest + prise partielle) ; ES conservé comme référence SMT au build | pytest complet à vérifier
- [2026-07-11] setup | Rafraîchissement intraday du dashboard : 2 triggers cron (13:30-16:30 UTC, semaine) + porte killzone NY DST-proof dans scripts/intraday_update.sh + build --light qui rejoue strategy_state.json (autotune strictement 1×/jour, anti-overfitting) | build léger 11 s vs plusieurs min ; 82 tests verts
- [2026-07-11] bugfix | Patches VARIANTS rendus explicites (entry_timing + exit_mode) : depuis le passage des défauts à retest+scale, 3 variantes sur 4 tournaient identiques sous des étiquettes fausses | test anti-doublon ajouté ; l'autotune du matin redevient une vraie comparaison

## Next Actions
<!-- next-actions:start -->
- Laisser l'échantillon grossir : 30 trades NQ sur le modèle sweep+V-shape, re-juger à ~60.
- Calibrer `vshape_min_move_ticks`/`vshape_max_bars` (20/8 posés a priori, jamais grid-searchés) — attention overfit.
- Premier lint du wiki quand ~10 pages de plus existeront.
<!-- next-actions:end -->
