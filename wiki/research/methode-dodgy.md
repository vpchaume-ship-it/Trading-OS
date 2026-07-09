---
type: research
updated: 2026-07-09
source: recherche publique (YouTube recaps, tradezella, scribd, communauté)
---
# Méthode Dodgy (DodgysDD)

Trader de référence de l'utilisateur (~70 % WR revendiqué, NQ uniquement).

**Modèle reconstitué** :
- NQ, session New York, 1 minute.
- Sweep de liquidité d'un **niveau clé** (PDH/PDL, swing majeur) → formation
  d'un [[concepts/ifvg|IFVG]] → entrée sur la **clôture de la bougie
  d'inversion** (agressif, pas d'attente du retest — précision utilisateur).
- Cible = liquidité opposée (EQH/EQL, ITH/ITL). Confluences : premium/discount,
  SMT ES/NQ, momentum sans chop.
- Gestion : prises partielles (scale-out).

**Ce que le backtest en a retenu** : la *structure* est codée (sweep, IFVG,
cibles liquidité, scale-out, killzone NY AM) ; son entrée agressive backteste
moins bien que le retest ([[experiences/2026-07-entree-inversion-vs-retest]]) ;
son ~70 % de WR est discrétionnaire, hors de portée mécanique. Le meilleur
rapprochement obtenu : 47 % WR via [[experiences/2026-07-sweep-session-vshape]].

Doc historique : `knowledge/CONCORDANCE.md` (section Dodgy).
