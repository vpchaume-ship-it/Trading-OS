<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN
     (sauf le bloc "Next Actions", préservé entre régénérations). -->
# État courant — 2026-07-11

## Stratégie auto-réglée
- Auto-réglage du 2026-07-11T14:32:20
- **NQ** : Sweep session + V-shape (clôture inversion) — 20 trades · WR 25% · +0.93 R/trade · PF 2.19

## Wiki (3 experiences · 6 concepts · 3 research · 2 reference)
Entrées récentes du journal :
- [2026-07-13] decision | Fil macro brut remplacé par une PRÉVISION news (verdict bullish/bearish/neutre indices + 3 moteurs pondérés) — demande utilisateur « je veux juste bullish ou bearish » | lexique directionnel + ratio sur titres directionnels seulement ; faux positifs « rate hike » de compagnies de gaz/électricité blacklistés
- [2026-07-10] decision | ES retiré comme instrument tradé : NQ uniquement (guards MNQ seul, config/CLI/deep/accumulate NQ, CSV ES supprimés, défauts = retest + prise partielle) ; ES conservé comme référence SMT au build | pytest complet à vérifier
- [2026-07-11] setup | Rafraîchissement intraday du dashboard : 2 triggers cron (13:30-16:30 UTC, semaine) + porte killzone NY DST-proof dans scripts/intraday_update.sh + build --light qui rejoue strategy_state.json (autotune strictement 1×/jour, anti-overfitting) | build léger 11 s vs plusieurs min ; 82 tests verts
- [2026-07-11] bugfix | Patches VARIANTS rendus explicites (entry_timing + exit_mode) : depuis le passage des défauts à retest+scale, 3 variantes sur 4 tournaient identiques sous des étiquettes fausses | test anti-doublon ajouté ; l'autotune du matin redevient une vraie comparaison
- [2026-07-11] bugfix | La fenêtre backtest était FIGÉE au 6/7 (repéré par l'utilisateur sur capture) : la routine du matin n'étendait pas l'historique profond Dukascopy, prioritaire sur Yahoo | refresh_deep("NQ") incrémental branché dans accumulate.main() ; deep 341k barres jusqu'au 10/7, fenêtre glissante 95k confirmée (01/04→10/07) ; autotune re-choisit retest+partielle (27 trades, WR 41 %, +1.02 R, PF 2.54)
- [2026-07-11] decision | Audit sécurité repo public : AUCUN secret dans les fichiers ni dans tout l'historique (identifiants Tradovate jamais committés, .env jamais versionné, .env.example = placeholders) ; PDFs knowledge/ conservés (contenu non payant, confirmé par l'utilisateur) | reste optionnel : email perso dans les métadonnées d'auteur des commits GitHub
- [2026-07-11] experience | Boucle d'auto-ajustement livrée : diagnose.py (pourquoi quotidien : tranches horaires/NTZ/RR/stops same-bar/DD) + feedback.py (4 règles evidence-gated ≥8 trades, 1 décision/jour, garde-fous durs codés, anti-overfit auto-revert, expiry 28 j) + fenêtre d'entrée moteur + section dashboard transparente (actifs, socle vs ajusté, historique, diagnostic) | 91 tests verts ; 1er passage : aucun ajustement (pas d'évidence) — comportement attendu
- [2026-07-11] bugfix | AUDIT QA complet : C1 lookahead niveaux overnight (fenêtre en formation utilisée par ses propres setups + jour calendaire vs jour de trading CME — dimanche soir = « veille » du lundi) ; C2 slippage 0 sur l'entrée marché inversion_close ; M1 fill limite au touch (optimiste) → trade-through strict ; M2 ordre annulé gratuitement sur barre de reclaim → rempli puis stoppé ; M3 anti-overfit feedback mesurait la dérive du marché → comparaison directe ajusté-vs-socle | 99 tests verts ; chiffres corrigés : retest+partielle 41 %→23 % WR (+0.13 R), inversion 25 % WR +0.93 R PF 2.19 retenue par l'autotune — l'edge survit, le WR flatteur était de l'exécution optimiste

## Next Actions
<!-- next-actions:start -->
- Laisser l'échantillon grossir : 30 trades NQ sur le modèle sweep+V-shape, re-juger à ~60.
- Calibrer `vshape_min_move_ticks`/`vshape_max_bars` (20/8 posés a priori, jamais grid-searchés) — attention overfit.
- Premier lint du wiki quand ~10 pages de plus existeront.
<!-- next-actions:end -->
