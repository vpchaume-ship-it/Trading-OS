---
type: concept
updated: 2026-07-12
---
# École des presque

Mécanisme d'apprentissage de cadence : mesurer, sans y toucher, ce que le
[[../experiences/2026-07-preenregistrement-dodgy|socle gelé]] rejette d'un
cheveu, pour promouvoir plus tard — sur évidence — les « presque » qui gagnent.

**Comment** (`backtest/nearmiss.py`) : un run moteur SÉPARÉ avec seuils
assouplis (V ≥ 12 ticks, RR ≥ 1.5, 2 trades/jour). Chaque trade porte ses
métriques mesurées (`vs_ticks`, `tgt_rr`, `nth_of_day`, ajoutées au moteur).
Pour chaque dimension, on isole la cohorte = les trades qui passeraient en
relâchant CETTE dimension seule (les autres au niveau gelé). C'est l'unité de
promotion : « relâcher le V à 15 ticks ajoute N trades qui ont fait Y ».

**Premier passage (24 mois NQ, 2026-07-12)** :
- 2ᵉ setup du jour : **9 trades, +0.43 R** → *candidat* (≥ 8 tr, espérance +) ;
- RR court (1.5–2) : 6 tr, -0.16 R → à surveiller ;
- V mou (12–20 ticks) : 0 trade.

Le seul candidat (2ᵉ trade/jour) est bien plus faible que le socle (+1.48 R) et
juste au seuil d'évidence : à **valider en forward** avant toute promotion. Le
module MESURE et propose ; il ne touche jamais le socle gelé (garde-fou).
