---
type: experience
updated: 2026-07-09
verdict: retenue (mode sortie privilégié pour le WR)
---
# Prise partielle (scale-out)

**Hypothèse** : banker la moitié à +1R et passer le reste à break-even (mécanique
de Dodgy) remonte le win rate sans tuer la rentabilité.

**Implémentation** : `ifvg.exit.mode: "scale"` — à +1R : 0.5R banké, stop du
solde à l'entrée, cible pleine conservée.

**Résultat historique** (NQ, sweep swing) : WR 24 % → 33-36 % en restant
rentable. Avec le modèle [[experiences/2026-07-sweep-session-vshape|sweep
session + V-shape]] : 47 % WR, +1.58R, PF 3.64.

**Verdict** : le levier de sortie le plus efficace pour l'objectif WR de
l'utilisateur. L'auto-réglage le retient pour NQ. Trade-off assumé : espérance
par trade plus basse que la cible pleine (+1.58R vs +3.40R).
