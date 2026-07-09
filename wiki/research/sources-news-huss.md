---
type: research
updated: 2026-07-13
source: vidéo TikTok @huss.trades « Peak News Sources for Trading » (43 s)
---
# Sources de news pour le trading (@huss.trades)

Quatre sources recommandées, et leur traduction dans l'app :

| Source vidéo | Rôle | Dans l'app |
|---|---|---|
| Forex Factory | calendrier éco (red folders) | ✅ déjà là : red folders + no-trade zones |
| X — Walter Bloomberg (@DeItaone) | headlines temps réel | ⚠️ API X payante → proxy **fil macro** Google News RSS |
| Financial Juice | fil macro gratuit continu | ⚠️ pas d'API publique → même proxy RSS |
| Glint.trade | carte des tensions géopolitiques | ✅ équivalent lite : **météo du risque** (VIX/or/DXY) |

Implémenté (2026-07-13) : `news/headlines.py` (fil macro 24 h, scoring par
mots-clés Fed/CPI/tarifs/géopolitique, blacklist anti-bruit) et
`premarket/risk.py` (score RISK-ON/NEUTRE/RISK-OFF -6..+6). Tuile héro +
section « Fil macro » sous les red folders, rafraîchies à chaque build.

Limite assumée : le dashboard est reconstruit au prémarché, pas en continu —
on capte le « qu'est-ce qui a bougé cette nuit », pas le breaking intraday.
Le temps réel (squawk) reste le rôle des apps dédiées sur le téléphone.
