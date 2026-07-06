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

## ⚖️ Arbitrages (décisions du 2026-07-04)

1. **Cibles = liquidité opposée** — ✅ TRANCHÉ : `target.mode: liquidity` est le
   défaut (swing confirmé le plus proche, RR minimal `liquidity_min_rr`).
   `fixed_rr` reste disponible pour comparaison en backtest.
2. **Filtre multi-timeframe M15+M5+M1** — ✅ TRANCHÉ : non nécessaire, abandonné.
3. **Clôture simple vs corps entier (`invalidation_mode`)** — ✅ TRANCHÉ : `close`
   (le prix de clôture passe la borne suffit). `body` reste disponible dans
   config.yaml pour comparaison en backtest.
4. **Critères contextuels non codés du rating Dodgy** — liquidity sweep préalable,
   « delivery from another FVG », premium/discount, FVG « singulier ». La notation
   codée couvre la bougie d'inversion (/10) ; ces critères de contexte restent un
   jugement de lecture de marché (codables partiellement en v2 si souhaité).

## ⚠️ Limites d'extraction

`Candle_Closure_Ratings.pdf` et `Dodgys_IFVG_Rating_System.pdf` sont des slides
graphiques : l'extraction texte de l'indexeur y est pauvre. Leur contenu a été lu
et intégré manuellement dans ce document et dans `core/rating.py`.

## Étude de la méthode Dodgy (DodgysDD) — juillet 2026

Recherche publique (tradezella, scribd, communauté). Modèle de Dodgy :
- **NQ, session New York** uniquement, sur du 1 minute.
- Entrée = **balayage de liquidité d'un niveau clé (PDH/PDL, swing majeur)** →
  formation d'un **IFVG** (par mèche OU clôture) → entrée au retest.
- Cible = liquidité opposée. Corrélation ES/NQ (SMT) en confluence.
- « Trap » : le balayage piège la liquidité avant le vrai mouvement.

Traduction dans le backtest (validée sur ~5 mois de NQ 1m profond) :
- Le filtre `require_sweep` exige déjà un balayage avant le FVG. En rendant le
  swing **plus significatif** (`swing_strength: 5` au lieu de 3, proxy du
  niveau PDH/PDL), le backtest s'améliore nettement :
  - sortie classique : 58 trades, **+1.71 R/trade, PF 3.07** (26 % WR)
  - prise partielle : 58 trades, **36 % WR**, +0.77 R, PF 2.07
- L'auto-réglage privilégie le win rate parmi les configs rentables → il
  retient la prise partielle (36 % WR) pour NQ.

Limite : reproduire son ~70 % de win rate reste hors de portée mécanique — sa
sélection A+ (qualité du displacement, SMT, jugement du contexte) est
discrétionnaire. Le backtest est fidèle à la *structure* du modèle, pas à son œil.
