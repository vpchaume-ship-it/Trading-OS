---
type: experience
updated: 2026-07-09
verdict: retest gagne mécaniquement
---
# Entrée sur clôture d'inversion (Dodgy) vs entrée au retest

**Hypothèse** : Dodgy entre au marché sur la CLÔTURE de la bougie qui inverse le
FVG (pas au retest). Reproduire son entrée devrait rapprocher son win rate.

**Implémentation** : `ifvg.entry_timing: "inversion_close"` — entrée = close de
la bougie d'inversion, stop au-delà de son extrême.

**Résultat** (NQ 120k barres, avec sweep session + V-shape) : inversion_close
21 trades, 24 % WR, +0.86R, PF 2.08 — contre retest 30 trades, 33-47 % WR selon
la sortie, PF 3.6-5.6. L'entrée agressive paie un prix d'entrée pire et subit
plus de bruit.

**Verdict** : mécaniquement, le retest domine. L'entrée de Dodgy fonctionne pour
LUI parce que sa sélection est discrétionnaire — c'est son edge, pas codable.
Conservée comme variante témoin dans la grille d'auto-réglage.

**Voir aussi** : [[research/methode-dodgy]], [[lessons]] (leçon 3).
