---
type: psychology
updated: 2026-07-13
tags: [psychologie, risque]
---
# Gestion du risque (discipline)

Profil « sniper » assumé : [[../experiences/2026-07-preenregistrement-dodgy|WR
~40 %, gains larges]]. Survivre aux séries perdantes est LA compétence.
- Sizing calculé par `backtest/risklab.py` (série p99, plafond dur 250 $).
- En [[drawdown|drawdown]] : la taille se RÉDUIT, jamais l'inverse
  ([[../concepts/boucle-auto-ajustement|boucle d'auto-ajustement]]).
- Le stop est posé AVANT l'entrée et ne bouge jamais contre soi.
- 1 % max du compte par trade (règle CLAUDE.md).
