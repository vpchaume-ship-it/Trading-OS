---
type: concept
updated: 2026-07-09
---
# IFVG — Inversion Fair Value Gap

Un **FVG** (gap de 3 bougies) qui échoue : le prix clôture franchement de
l'autre côté → la zone change de polarité (un FVG haussier devient résistance,
et inversement). La zone inversée devient tradable dans le sens de l'inversion.

- Code : `trading_os/core/fvg.py` (FVGTracker, machine à états incrémentale).
- Invalidation : `close` (une clôture au-delà de la borne suffit) — arbitrage
  tranché 2026-07-04 ; `body` reste dispo en comparaison.
- Un FVG rempli par mèche sans clôture franche est mort (`wick_fill_kills`).
- Source : PDF Daily Bias p.27-29 (voir [[research/pdfs-ict]]).
