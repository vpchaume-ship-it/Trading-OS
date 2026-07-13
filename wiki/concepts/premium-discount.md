---
type: concept
updated: 2026-07-13
---
# Premium / Discount

Moitié haute (premium) vs basse (discount) d'une range de référence (équilibre
ICT). On ne vend qu'en premium, on n'achète qu'en discount. Code : `in_pd()`
dans `backtest/engine.py`, actif via `ifvg.setup.require_pd`. Filtre de contexte
du socle, en confluence avec [[sweep-de-liquidite|sweep]] + [[v-shape|V-shape]].
