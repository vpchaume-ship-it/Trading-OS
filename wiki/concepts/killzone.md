---
type: concept
updated: 2026-07-09
---
# Killzone

Fenêtre horaire de trading autorisée. Décision projet (conforme aux PDFs et à
la pratique de Dodgy) : **NY AM uniquement, 9:30–11:30 heure de New York**.
London (02:00–05:00) et NY PM (13:30–16:00) restent définies pour les stats de
backtest mais sont interdites au trading.

- Config : `killzones` + `ifvg.allowed_killzones: ["ny_am"]`.
- S'y ajoute la no-trade-zone news : 10 min avant/après chaque red folder USD
  (décision utilisateur, session NY).
- Gestion hiver/été automatique via le fuseau `America/New_York`.
