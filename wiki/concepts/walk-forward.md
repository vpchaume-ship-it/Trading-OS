---
type: concept
updated: 2026-07-11
---
# Validation walk-forward

Fenêtre glissante : **30 j de sélection (train) → 10 j de test FIGÉ**, répétée
sur tout l'historique. Les métriques affichées en tête de dashboard sont le
cumul des fenêtres test uniquement — jamais vues par l'optimisation. Supprime
le biais M4 (sélection in-sample) de l'audit QA.

- Code : `backtest/walkforward.py`. Astuce d'architecture : les variantes étant
  indépendantes du pli, chaque variante est backtestée UNE fois sur tout
  l'historique (`insights.variant_trades`) et les plis se jouent sur les flux
  de trades en pandas pur (~0 coût). Persisté dans `data/walkforward.json`
  pour les rebuilds intraday.
- Les plis où aucune variante ne passe les garde-fous sur le train sont des
  plis « prudence » : ils ne tradent pas (c'est une information, pas un trou).

**Premier verdict (2026-07-11, 12 mois NQ 1m, moteur réaliste)** : 31 plis,
8 tradés, 10 trades OOS, **-0.45 R/trade, PF 0.52, WR 20 %** — l'edge
in-sample (+0.9 R) ne se transfère pas encore hors échantillon. Le « edge »
mesuré jusqu'ici était majoritairement du biais de sélection. Conséquence
risque : sizing plancher 50 $/trade (0.1 %) tant que l'OOS n'est pas positif.
