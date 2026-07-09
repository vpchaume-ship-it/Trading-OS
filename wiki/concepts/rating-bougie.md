---
type: concept
updated: 2026-07-09
---
# Rating de bougie /10 (Candle Closure Ratings)

Note de la bougie d'inversion : force /4 + vitesse d'inversion /3 + qualité RR
/3 → grades A+ (10) … F (<3). Code : `trading_os/core/rating.py`. Source :
PDFs Dodgy ([[research/pdfs-ict]]).

**Statut 2026-07-07 : rétrogradé de critère de filtre à information affichée.**
`min_rating` est passé de 9 (A/A+ seulement) à 0 : le filtre A/A+ ne laissait
que 6 trades sur 120k barres et discriminait moins bien que le contexte
sweep-session + V-shape (voir [[Failed Ideas/ledger]]). La note reste calculée
et affichée par trade dans les rapports.
