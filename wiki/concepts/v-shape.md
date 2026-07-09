---
type: concept
updated: 2026-07-09
---
# V-shape

Renversement **franc** depuis l'extrême balayé jusqu'à l'inversion — pas un
grind lent. Défini mécaniquement par l'utilisateur : le contre-mouvement doit
couvrir ≥ `vshape_min_move_ticks` (20) en ≤ `vshape_max_bars` (8).

- Code : `v_shape()` dans `trading_os/backtest/engine.py`,
  activé par `ifvg.setup.require_vshape: true`.
- **Le filtre le plus payant à ce jour** : WR NQ 32 % → 47 % à lui seul
  ([[experiences/2026-07-sweep-session-vshape]]).
- Intuition : le V témoigne d'un vrai déplacement (displacement) après le trap,
  là où le rating de bougie ne regardait qu'UNE bougie.
