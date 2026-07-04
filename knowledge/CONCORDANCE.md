# Concordance PDF ↔ implémentation

Analyse des trois documents de `knowledge/` face au code (mise à jour : 2026-07-04).

## ✅ Concordances (rien à changer)

| Concept | PDF | Implémentation |
|---|---|---|
| Inversion (IFVG) | Daily Bias p.27-29 : « un FVG échoue quand le prix clôture de l'autre côté ; le FVG haussier devient résistance » | `core/fvg.py` : clôture franche au-delà de la borne opposée → la zone change de polarité |
| Inversion haussière | « FVG baissier clôturé au-dessus → Bullish IFVG » | `FVG.ifvg_direction` retourne l'opposé du gap d'origine |
| PDH/PDL comme liquidité | Daily Bias p.40 : « pools de liquidité naturels » | `premarket/levels.py` + swings/EQH-EQL |
| Judas / première impulsion piégeuse | (implicite dans les warnings news) | Rappel systématique du Module 1 |

## 🔧 Alignements appliqués au code suite à vos PDF

1. **Fenêtre de trading 9:30–11:30 NY** — les deux PDF sont explicites (« avoid Asian
   or London sessions », schémas « Trading window 9:30→11:30 »). La config par
   défaut n'autorise plus que `ny_am` (redéfinie 09:30–11:30). London/NY PM restent
   définies pour comparaison en backtest.
2. **Notation de l'inversion /10** (Candle Closure Ratings) — implémentée dans
   `core/rating.py` : force de la bougie /4, vitesse d'inversion /3, qualité RR
   (clôture proche du bord de zone) /3. Grades A+→F, filtre `ifvg.min_rating`,
   répartition par grade dans les rapports de backtest, grade affiché dans les
   alertes semi-auto.
3. **Daily bias PDH/PDL** (Daily Bias, outil 4) — implémenté dans
   `premarket/bias.py` et affiché en tête de chaque section instrument du rapport
   prémarché, avec rappel de confirmation CISD 1H.

## ⚖️ Points d'arbitrage (dites-moi comment trancher)

1. **Clôture corps entier vs simple clôture** — le PDF IFVG Rating (grades A-/B) dit
   que dans le chop « the trade can't take place until the body closes fully
   over/under the FVG ». Le code offre les deux (`ifvg.invalidation_mode: close|body`),
   défaut actuel : `close`. → Passer le défaut à `body` ? Le backtest peut comparer les deux.
2. **Critères contextuels non codés du rating Dodgy** — liquidity sweep préalable,
   « delivery from another FVG », premium/discount, FVG « singulier », cibles parmi
   les 7 (EQH/EQL/ITH/ITL/data highs-lows/LRLR). La notation codée couvre la bougie
   d'inversion (Candle Closure /10) ; ces critères de contexte demandent un
   jugement de lecture de marché. Codables partiellement (sweep préalable,
   premium/discount vs range du jour) si vous voulez une v2 du score.
3. **Cibles** — vos PDF privilégient la liquidité (EQH/EQL, ITH/ITL) plutôt qu'un RR
   fixe. Le mode `target.mode: liquidity` existe déjà (swing confirmé le plus proche) ;
   défaut actuel : `fixed_rr 2.0`. → Basculer le défaut sur `liquidity` ?
4. **Timeframe d'entrée** — Daily Bias (M15 orderflow) : M15 + M5 + M1 alignés avant
   toute entrée M1. Le backtest actuel travaille sur un seul timeframe (1m par votre
   choix). Un filtre multi-timeframe (orderflow M15/M5 aligné) est codable en v2 —
   à prioriser si le backtest 1m brut montre trop de faux signaux.

## ⚠️ Limites d'extraction

`Candle_Closure_Ratings.pdf` et `Dodgys_IFVG_Rating_System.pdf` sont des slides
graphiques : l'extraction texte de l'indexeur y est pauvre. Leur contenu a été lu
et intégré manuellement dans ce document et dans `core/rating.py`.
