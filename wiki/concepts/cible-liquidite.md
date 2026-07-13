---
type: concept
updated: 2026-07-13
---
# Cible de liquidité

Sortie du socle : le prochain pool de liquidité opposé (swing confirmé le plus
proche, [[eqh-eql|EQH/EQL]]) dans le sens du trade, avec RR ≥ 2. Code :
`nearest_liquidity_target()` dans `core/swings.py` ; mode `target.mode:
liquidity`. Le RR réel vers la cible est mesuré sur chaque trade
(`tgt_rr`) — dimension de l'[[ecole-des-presque|école des presque]] (RR court =
cohorte à surveiller).
