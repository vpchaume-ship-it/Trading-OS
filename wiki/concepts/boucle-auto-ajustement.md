---
type: concept
updated: 2026-07-11
---
# Boucle d'auto-ajustement (feedback)

Optimisation continue des paramètres SECONDAIRES de la stratégie — le socle
([[concepts/sweep-de-liquidite|sweep session]] + [[concepts/ifvg|IFVG]] +
[[concepts/v-shape|V-shape]], killzone, entrée/sortie de l'autotune) est
**gelé par code** (`ADJUSTABLE` dans `backtest/feedback.py`).

**Cycle quotidien** (build du matin uniquement) :
1. `diagnose.daily_review()` — le POURQUOI : tranches horaires, jours, NTZ,
   RR visé, stops same-bar, DD 30 j, bullets français affichés au dashboard.
2. `feedback.step()` — maintenance (expiration 28 j des filtres horaires,
   annulation anti-overfit après 10 trades si l'espérance baisse, restauration
   du risque au nouveau plus-haut d'equity) puis AU PLUS UNE décision :
   - R1 drawdown → risk_scale 0.5× (protection, jamais d'augmentation) ;
   - R2 tranche horaire PF < 0.8 (n ≥ 8) → fenêtre d'entrée réduite ;
   - R3 ≥ 40 % de stops sur la barre d'entrée → buffer +1 tick ;
   - R4 RR courts perdants → plancher RR 2.5.
3. Rebuild avec overrides + comparaison socle vs ajusté affichée.

**Garde-fous durs** (constantes, non configurables) : risque ≤ 1× (~200 $),
stop obligatoire (buffer 1–6 ticks), RR plancher 1.5–3.0, fenêtre ⊂ killzone
et ≥ 60 min, évidence ≥ 8 trades, 1 décision/jour, tout est réversible, daté
et journalisé (`data/adjustments.json`, affiché au dashboard).

Premier passage (2026-07-11) : **aucun ajustement adopté** — pas d'asymétrie
statistiquement exploitable sur la fenêtre. C'est le comportement attendu.
