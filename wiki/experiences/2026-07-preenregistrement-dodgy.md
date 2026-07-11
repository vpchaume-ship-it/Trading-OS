---
type: experience
updated: 2026-07-11
verdict: retenue — CONFIG GELÉE (pré-enregistrement)
---
# Pré-enregistrement : entrée Dodgy + 1 trade/jour (config gelée le 2026-07-11)

**Hypothèse** : se rapprocher de Dodgy = son entrée (clôture d'inversion), sa
discipline (LE setup du matin, pas trois), son ciblage (liquidité, RR ≥ 2), sur
le socle sweep session + [[../concepts/v-shape|V-shape]].

**Résultats 24 mois** (Dukascopy NQ 1m, 2024-07→2026-07, moteur post-audit,
coûts/slippage marché inclus, `max_trades_per_day: 1`) :

| Config | n | WR | Esp. | PF | DD |
|---|---|---|---|---|---|
| **Clôture inversion, cible pleine (GELÉE)** | **25** | **40 %** | **+1.38 R** | **3.21** | **-4.1 R** |
| Retest, cible pleine | 51 | 24 % | +1.65 R | 2.88 | -16.0 R |
| Retest + partielle | 51 | 29 % | +0.50 R | 1.61 | -18.6 R |

Le plafond 1 trade/jour est un vrai edge de discipline (retest+partielle :
+0.13 R sans cap → +0.50 R avec). La SMT bloquante est abandonnée
([[../Failed Ideas/ledger|ledger]]).

**Validation** : le walk-forward rétrospectif est NON CONCLUSIF à cette cadence
(~18 trades OOS, signe instable : -0.64 R en 180/45, +0.44 R en 120/30 — en
choisir un serait du méta-overfitting). D'où le **pré-enregistrement** : config
figée, plus aucune sélection quotidienne ; chaque jour depuis le 2026-07-11 est
du VRAI hors-échantillon, compté sur le dashboard (« depuis le gel »).
Critère de jugement : ≥ 15 trades forward avant toute conclusion (~7 mois).

**Discrétion** : chaque trade génère sa page [[../journal/|journal]] (25 pages
seedées) ; les annotations « Lecture » en session forment le corpus d'où
sortiront les prochaines règles candidates.
