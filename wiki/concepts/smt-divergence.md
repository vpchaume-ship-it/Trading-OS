---
type: concept
updated: 2026-07-13
---
# SMT divergence

Divergence ES/NQ (Smart Money Technique) : quand NQ balaye son niveau mais
qu'ES ne balaye PAS le sien (ou l'inverse), le sweep est un vrai trap non
confirmé. Code : `smt_divergent()` dans `backtest/engine.py`, activable par
`ifvg.setup.require_smt`. **Testé en filtre bloquant → abandonné** (4-11
trades/24 mois, ES/NQ trop corrélés — voir [[../Failed Ideas/ledger|ledger]]).
ES reste fetché comme référence au build (carte biais « RÉF. SMT — NON TRADÉ »).
