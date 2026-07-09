---
type: experience
updated: 2026-07-09
verdict: retenue
---
# Sweep de niveau de session + IFVG + V-shape

**Hypothèse** (définie par l'utilisateur) : un setup A+ = balayage d'un niveau
de session précédente (PDH/PDL de la veille OU high/low overnight Asie+Londres),
puis [[concepts/ifvg|IFVG]], puis [[concepts/v-shape|V-shape]] (renversement franc).

**Implémentation** : `trading_os/backtest/engine.py` — `swept_session_level()`
et `v_shape()`, activés par `ifvg.setup.sweep_mode: "session"` et
`require_vshape: true`. Sans lookahead (niveaux figés avant la killzone NY).

**Résultat** (NQ, 120 000 barres 1m Dukascopy, fév→juil 2026) :

| Variante | n | WR | Esp. | PF |
|---|---|---|---|---|
| Sweep swing (ancien), retest+partielle | 58 | 36 % | +0.77R | 2.07 |
| Sweep session SANS V-shape | 53 | 32 % | +0.62R | 1.82 |
| **Sweep session + V-shape, retest+partielle** | **30** | **47 %** | **+1.58R** | **3.64** |
| Sweep session + V-shape, retest cible pleine | 30 | 33 % | +3.40R | 5.57 |

**Verdict** : le V-shape seul fait +15 pts de WR. Config par défaut depuis le
2026-07-07 (`min_rating` passé à 0, la qualité vient du contexte). Meilleur WR
atteint en restant rentable. Réserve : 30 trades = échantillon encore mince.

**Voir aussi** : [[experiences/2026-07-entree-inversion-vs-retest]], [[lessons]] (leçons 1-2).
