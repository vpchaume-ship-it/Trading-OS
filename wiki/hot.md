<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN
     (sauf le bloc "Next Actions", préservé entre régénérations). -->
# État courant — 2026-07-13

## Stratégie auto-réglée
- Auto-réglage du 2026-07-13T13:21:43
- **NQ** : Sweep session + V-shape (clôture inversion) — config PRÉ-ENREGISTRÉE le 2026-07-11

## Wiki (4 experiences · 16 concepts · 3 research · 2 reference)
Entrées récentes du journal :
- [2026-07-11] bugfix | AUDIT QA complet : C1 lookahead niveaux overnight (fenêtre en formation utilisée par ses propres setups + jour calendaire vs jour de trading CME — dimanche soir = « veille » du lundi) ; C2 slippage 0 sur l'entrée marché inversion_close ; M1 fill limite au touch (optimiste) → trade-through strict ; M2 ordre annulé gratuitement sur barre de reclaim → rempli puis stoppé ; M3 anti-overfit feedback mesurait la dérive du marché → comparaison directe ajusté-vs-socle | 99 tests verts ; chiffres corrigés : retest+partielle 41 %→23 % WR (+0.13 R), inversion 25 % WR +0.93 R PF 2.19 retenue par l'autotune — l'edge survit, le WR flatteur était de l'exécution optimiste
- [2026-07-11] experience | Production : walk-forward (30 j train → 10 j test figé, variantes backtestées 1× puis plis en pandas pur), fenêtre 12 mois par date (341k barres, 21 s/run), risklab profil sniper (DP exacte des séries perdantes, sizing borné dur 50-250 $, alerte série > p99) | 106 tests verts · VERDICT OOS : 31 plis, 10 trades, -0.45 R/trade, PF 0.52 — l'edge in-sample était du biais de sélection ; sizing plancher 50 $ tant que l'OOS n'est pas positif
- [2026-07-11] decision | PRÉ-ENREGISTREMENT (gel de config) : entrée Dodgy clôture inversion + sweep session + V-shape + 1 trade/jour + cible liquidité ≥2R — 24 mois : 25 tr · 40 % WR · +1.38 R · PF 3.21 · DD -4.1 R | SMT bloquante abandonnée (4-11 tr/24 mois) ; sélection quotidienne abandonnée (bruit) ; WF rétrospectif non conclusif → le forward depuis le gel est LA validation ; journal/ auto-généré (25 pages) = corpus discrétion ; 110 tests verts
- [2026-07-11] decision | Dashboard : les 5 sections backtest (walk-forward, risque, backtest, auto-ajustement, conclusions) fusionnées en UNE carte « config gelée style Dodgy » (demande utilisateur) — forward en vedette, référence 24 mois, equity, risque et auto-apprentissage en lignes intégrées | grille de variantes coupée quand une config est pré-enregistrée : build 6 min 30 → 1 min 22
- [2026-07-12] decision | Carte de biais ES rétablie après celle de NQ (demande utilisateur), étiquetée « RÉF. SMT — NON TRADÉ » + tuile héro ES | le flux ES était déjà fetché pour la SMT, seul l'affichage manquait ; NQ reste le seul instrument tradé
- [2026-07-12] experience | Question utilisateur « pourquoi 25 trades/24 mois quand Dodgy en prend 10-20/mois » → entonnoir mesuré : 54 114 inversions IFVG, -74 % sweep session, -9 238 V-shape, -4 677 RR<2, killzone 2 h implicite → 25 ; sweep SWING élargi testé : 26 trades (idem) — le goulot n'est pas le sweep mais V-shape+RR+killzone | la cadence de Dodgy vient des setups que seul son œil qualifie ; mécaniquement, les relâcher dilue l'edge (sans V-shape : 69 tr à +0.18 R, mesuré) — gel maintenu
- [2026-07-12] experience | École des presque livrée (nearmiss.py) : le moteur mesure vs_ticks/tgt_rr/nth_of_day sur chaque trade ; run assoupli séparé isole par dimension les « presque » (relâcher 1 critère seul) ; panneau dashboard + persistance | 24 mois NQ : candidat = 2ᵉ setup/jour (9 tr, +0.43 R, PROMOUVABLE) ; RR court -0.16 R ; V mou 0 tr — socle jamais touché, promotion = décision sur forward ; 115 tests verts
- [2026-07-13] setup | Session PC : densification du graphe Obsidian — 8 concepts ICT ajoutés (order block, displacement, BOS/CHoCH, judas swing, SMT, premium/discount, EQH/EQL, cible liquidité), tissés entre eux et vers le code | 8 → 16 concepts ; indexés (zéro orphelin)

## Next Actions
<!-- next-actions:start -->
- FORWARD depuis le gel (2026-07-11) : ne rien toucher au socle avant ≥ 15 trades hors-échantillon — le dashboard les compte (« 🔒 depuis le gel »).
- Annoter les pages journal/ (« Lecture ») à chaque session : c'est le corpus d'où sortiront les prochaines règles candidates.
- Surveiller le candidat « 2ᵉ setup du jour » (école des presque, +0.43 R/9 tr) en forward — promouvoir seulement s'il tient hors échantillon.
- Ne PAS re-calibrer vshape/plis WF pour faire plaisir aux chiffres (méta-overfitting — voir leçons 7-8).
- Premier lint du wiki : 25 pages journal ajoutées, vérifier les orphelines.
<!-- next-actions:end -->
