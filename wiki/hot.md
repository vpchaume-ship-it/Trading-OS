<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN
     (sauf le bloc "Next Actions", préservé entre régénérations). -->
# État courant — 2026-07-19

## Stratégie auto-réglée
- Auto-réglage du 2026-07-19T09:00:57
- **NQ** : Sweep session + V-shape (clôture inversion) — config PRÉ-ENREGISTRÉE le 2026-07-11

## Wiki (4 experiences · 18 concepts · 3 research · 2 reference)
Entrées récentes du journal :
- [2026-07-12] experience | École des presque livrée (nearmiss.py) : le moteur mesure vs_ticks/tgt_rr/nth_of_day sur chaque trade ; run assoupli séparé isole par dimension les « presque » (relâcher 1 critère seul) ; panneau dashboard + persistance | 24 mois NQ : candidat = 2ᵉ setup/jour (9 tr, +0.43 R, PROMOUVABLE) ; RR court -0.16 R ; V mou 0 tr — socle jamais touché, promotion = décision sur forward ; 115 tests verts
- [2026-07-13] setup | Session PC : densification du graphe Obsidian — 8 concepts ICT ajoutés (order block, displacement, BOS/CHoCH, judas swing, SMT, premium/discount, EQH/EQL, cible liquidité), tissés entre eux et vers le code | 8 → 16 concepts ; indexés (zéro orphelin)
- [2026-07-13] setup | Session PC suite : cluster psychologie (plan, risque, drawdown, biais, journal — couleur dédiée dans le graphe) + 2 concepts ICT (mitigation block, liquidity void) + page Dataview dashboard.md | wiki 57 → 65 pages, 18 concepts ; NB graph.json édité Obsidian ouvert (voir avertissement)
- [2026-07-13] setup | Vault Obsidian rendu turnkey : .obsidian/ pré-configuré (core-plugins graph/backlinks/recherche/survol activés = zéro téléchargement, app.json, appearance dark, bookmarks index/hot/dashboard/ledger) | à l'ouverture du dossier comme vault, graphe + liens + couleurs fonctionnent immédiatement ; Dataview reste optionnel (bonus)
- [2026-07-13] setup | Onboarding session Cowork : START_HERE.md (accueil humain 30 s + table « où est quoi ») + bloc « Démarrage d'une session » dans CLAUDE.md (3 lectures d'orientation, règle du gel, coordination cloud/local via hooks git) ; README pointe vers START_HERE | une session locale reprend tout le contexte sans réexplication
- [2026-07-16] setup | Dashboard bilingue FR/EN (demande utilisateur « version anglaise ») : passe de post-traitement i18n.py qui enveloppe chaque nœud de texte traduisible en `<span data-en=…>` + bouton toggle dans la barre du haut (auto-détection de la langue navigateur au 1er chargement, choix mémorisé localStorage) ; ZÉRO modif des ~150 sites de rendu → routines quotidienne/intraday inchangées | 1 seule table à maintenir (EXACT + RULES), repli gracieux (nœud non couvert reste FR) ; 110 nœuds enveloppés, 0 fuite française au scan ; 121 tests verts (+6 test_i18n)
- [2026-07-19] bugfix | Prix figé signalé par l'utilisateur (dashboard montrait ~28 623 du matin alors que NQ avait CLÔTURÉ à 28 773) : le prix affiché lisait la dernière bougie H1 COMPLÈTE (retard ≤ 1 h en séance, jamais le close après 16:00). Corrigé → `yahoo.spot()` lit `regularMarketPrice` (meta Yahoo) = vraie dernière cotation / clôture, indépendant de l'horloge conteneur ; niveaux/FVG/biais gardent les bougies complètes | 124 tests verts (+3) ; cause racine du « figé le soir » = le refresh intraday ne tournait QUE pendant la killzone → porte élargie à 9:25–16:20 NY (capte le close)
- [2026-07-19] setup | Rafraîchissement dashboard élargi (demande « auto, ~5 min ») : porte intraday_update.sh 9:25→16:20 NY (séance complète + close, plus seulement la killzone) ; backbone cron 15 min (4 déclencheurs :00/:15/:30/:45, 13-21 UTC, DST-proof, gate NY trim) ; boucle 5 min best-effort (déclencheur au démarrage 9:25 NY qui s'auto-reprogramme via send_later, s'arrête au close) | min cron = 1×/h par déclencheur → 5 min garanti impossible en pur cron ; 15 min fiable + 5 min si session active. Le soir/week-end : plus de rebuild (inutile), le dashboard montre le close

## Next Actions
<!-- next-actions:start -->
- FORWARD depuis le gel (2026-07-11) : ne rien toucher au socle avant ≥ 15 trades hors-échantillon — le dashboard les compte (« 🔒 depuis le gel »).
- Annoter les pages journal/ (« Lecture ») à chaque session : c'est le corpus d'où sortiront les prochaines règles candidates.
- Surveiller le candidat « 2ᵉ setup du jour » (école des presque, +0.43 R/9 tr) en forward — promouvoir seulement s'il tient hors échantillon.
- Ne PAS re-calibrer vshape/plis WF pour faire plaisir aux chiffres (méta-overfitting — voir leçons 7-8).
- Premier lint du wiki : 25 pages journal ajoutées, vérifier les orphelines.
<!-- next-actions:end -->
