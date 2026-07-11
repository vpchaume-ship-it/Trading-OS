<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN
     (sauf le bloc "Next Actions", préservé entre régénérations). -->
# État courant — 2026-07-11

## Stratégie auto-réglée
- Auto-réglage du 2026-07-11T19:42:38
- **NQ** : Sweep session + V-shape (clôture inversion) — config PRÉ-ENREGISTRÉE le 2026-07-11 — 25 trades · WR 40% · +1.38 R · PF 3.21

## Wiki (4 experiences · 7 concepts · 3 research · 2 reference)
Entrées récentes du journal :
- [2026-07-11] setup | Rafraîchissement intraday du dashboard : 2 triggers cron (13:30-16:30 UTC, semaine) + porte killzone NY DST-proof dans scripts/intraday_update.sh + build --light qui rejoue strategy_state.json (autotune strictement 1×/jour, anti-overfitting) | build léger 11 s vs plusieurs min ; 82 tests verts
- [2026-07-11] bugfix | Patches VARIANTS rendus explicites (entry_timing + exit_mode) : depuis le passage des défauts à retest+scale, 3 variantes sur 4 tournaient identiques sous des étiquettes fausses | test anti-doublon ajouté ; l'autotune du matin redevient une vraie comparaison
- [2026-07-11] bugfix | La fenêtre backtest était FIGÉE au 6/7 (repéré par l'utilisateur sur capture) : la routine du matin n'étendait pas l'historique profond Dukascopy, prioritaire sur Yahoo | refresh_deep("NQ") incrémental branché dans accumulate.main() ; deep 341k barres jusqu'au 10/7, fenêtre glissante 95k confirmée (01/04→10/07) ; autotune re-choisit retest+partielle (27 trades, WR 41 %, +1.02 R, PF 2.54)
- [2026-07-11] decision | Audit sécurité repo public : AUCUN secret dans les fichiers ni dans tout l'historique (identifiants Tradovate jamais committés, .env jamais versionné, .env.example = placeholders) ; PDFs knowledge/ conservés (contenu non payant, confirmé par l'utilisateur) | reste optionnel : email perso dans les métadonnées d'auteur des commits GitHub
- [2026-07-11] experience | Boucle d'auto-ajustement livrée : diagnose.py (pourquoi quotidien : tranches horaires/NTZ/RR/stops same-bar/DD) + feedback.py (4 règles evidence-gated ≥8 trades, 1 décision/jour, garde-fous durs codés, anti-overfit auto-revert, expiry 28 j) + fenêtre d'entrée moteur + section dashboard transparente (actifs, socle vs ajusté, historique, diagnostic) | 91 tests verts ; 1er passage : aucun ajustement (pas d'évidence) — comportement attendu
- [2026-07-11] bugfix | AUDIT QA complet : C1 lookahead niveaux overnight (fenêtre en formation utilisée par ses propres setups + jour calendaire vs jour de trading CME — dimanche soir = « veille » du lundi) ; C2 slippage 0 sur l'entrée marché inversion_close ; M1 fill limite au touch (optimiste) → trade-through strict ; M2 ordre annulé gratuitement sur barre de reclaim → rempli puis stoppé ; M3 anti-overfit feedback mesurait la dérive du marché → comparaison directe ajusté-vs-socle | 99 tests verts ; chiffres corrigés : retest+partielle 41 %→23 % WR (+0.13 R), inversion 25 % WR +0.93 R PF 2.19 retenue par l'autotune — l'edge survit, le WR flatteur était de l'exécution optimiste
- [2026-07-11] experience | Production : walk-forward (30 j train → 10 j test figé, variantes backtestées 1× puis plis en pandas pur), fenêtre 12 mois par date (341k barres, 21 s/run), risklab profil sniper (DP exacte des séries perdantes, sizing borné dur 50-250 $, alerte série > p99) | 106 tests verts · VERDICT OOS : 31 plis, 10 trades, -0.45 R/trade, PF 0.52 — l'edge in-sample était du biais de sélection ; sizing plancher 50 $ tant que l'OOS n'est pas positif
- [2026-07-11] decision | PRÉ-ENREGISTREMENT (gel de config) : entrée Dodgy clôture inversion + sweep session + V-shape + 1 trade/jour + cible liquidité ≥2R — 24 mois : 25 tr · 40 % WR · +1.38 R · PF 3.21 · DD -4.1 R | SMT bloquante abandonnée (4-11 tr/24 mois) ; sélection quotidienne abandonnée (bruit) ; WF rétrospectif non conclusif → le forward depuis le gel est LA validation ; journal/ auto-généré (25 pages) = corpus discrétion ; 110 tests verts

## Next Actions
<!-- next-actions:start -->
- FORWARD depuis le gel (2026-07-11) : ne rien toucher au socle avant ≥ 15 trades hors-échantillon — le dashboard les compte (« 🔒 depuis le gel »).
- Annoter les pages journal/ (« Lecture ») à chaque session : c'est le corpus d'où sortiront les prochaines règles candidates.
- Ne PAS re-calibrer vshape/plis WF pour faire plaisir aux chiffres (méta-overfitting — voir leçons 7-8).
- Premier lint du wiki : 25 pages journal ajoutées, vérifier les orphelines.
<!-- next-actions:end -->
