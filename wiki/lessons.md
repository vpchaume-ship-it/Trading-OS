---
type: hub
updated: 2026-07-09
---
# Leçons transversales

Synthèse de ce que le projet a appris — mise à jour quand une leçon se confirme
sur plusieurs expériences. Détails et chiffres dans les pages d'expérience liées.

1. **Win rate et rentabilité se marchandent.** Les cibles proches montent le WR
   mais perdent de l'argent après coûts ; les cibles liquidité sont rentables à
   WR bas. Le levier qui réconcilie les deux : la gestion de sortie
   ([[experiences/2026-06-scale-out|scale-out]]) et les filtres de contexte
   ([[experiences/2026-07-sweep-session-vshape|V-shape]]).
2. **Le contexte filtre mieux que la bougie.** Le rating /10 de la bougie
   d'inversion discrimine moins bien que sweep-de-session + V-shape
   (WR 32 % → 47 % sur NQ). `min_rating` est passé à 0.
3. **On ne code pas l'expérience d'un trader.** L'entrée agressive de Dodgy
   backteste moins bien que le retest mécanique — son edge est discrétionnaire
   ([[experiences/2026-07-entree-inversion-vs-retest]]). Coder la *structure*
   du modèle, pas son œil.
4. **Pas de lookahead, jamais.** Chaque filtre doit n'utiliser que des barres
   complètes antérieures ; les niveaux de session (PDH/PDL/overnight) sont
   sûrs car figés avant la killzone NY.
5. **Se méfier des proxys grossiers.** Le filtre de biais « dérive sur 90
   barres » a tué la stratégie NQ (elle fade la dérive). Un filtre plausible
   n'est pas un filtre validé.
6. **Les hypothèses d'exécution pèsent plus que les filtres.** L'audit du
   2026-07-11 (fill au touch → trade-through strict, slippage marché sur
   l'entrée inversion, fills sur barre de reclaim) a fait passer le retest+
   partielle de 41 % WR/+1.02 R à 23 %/+0.13 R sur la même fenêtre. Un
   backtest sans friction réaliste flatte, il n'informe pas.
7. **L'in-sample ment même quand le moteur est honnête.** Walk-forward
   2026-07-11 (12 mois, moteur post-audit) : +0.9 R in-sample → **-0.45 R
   out-of-sample** (10 trades, PF 0.52). La sélection de variante capte du
   bruit ; seul le rendement hors échantillon compte désormais.
8. **À cadence sniper, le walk-forward rétrospectif ne tranche pas.** ~25
   trades/an → ~18 trades OOS dont le signe dépend du calibrage des plis.
   La validation propre : PRÉ-ENREGISTRER la config et laisser le forward
   trancher (gel du 2026-07-11, seuil de jugement ≥ 15 trades).
9. **La discipline est un edge mesurable.** max_trades_per_day 1 (le setup
   du matin, comme Dodgy) : +0.13 R → +0.50 R sur la même config retest.
10. **Les garde-fous d'auto-réglage sont vitaux.** Sans min_trades/expectancy/PF,
   l'auto-tune choisit du bruit (il avait rétrogradé NQ vers une config à 24 %
   WR non voulue).
