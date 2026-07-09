---
type: concept
updated: 2026-07-09
---
# Sweep de liquidité

Balayage (mèche au-delà) d'un niveau où repose de la liquidité, juste avant le
renversement — le « trap » qui précède le vrai mouvement. Deux modes dans le
moteur (`ifvg.setup.sweep_mode`) :

- **swing** (ancien) : raid du dernier swing significatif (`swing_strength: 5`
  ≈ proxy PDH/PDL).
- **session** (défaut depuis 2026-07-07) : raid d'un NIVEAU DE SESSION
  précédente — PDH/PDL de la veille ou high/low overnight (Asie+Londres,
  00:00 → ouverture killzone). Plus strict, plus proche du modèle utilisateur.

Sans lookahead : les niveaux de session sont figés avant la killzone NY.
Voir [[experiences/2026-07-sweep-session-vshape]] pour les chiffres.
