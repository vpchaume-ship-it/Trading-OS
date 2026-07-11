---
type: reference
updated: 2026-07-09
---
# Données (routeur)

- **NQ uniquement** (décision 2026-07-10) : seul instrument tradé, backtesté et
  accumulé. ES n'est plus fetché qu'en live (Yahoo) comme référence SMT au build.
- **Historique profond 1m (gratuit)** → Dukascopy via `trading_os/data/deep.py`
  (CFD E-mini NQ), stocké `data/deep_NQ_1m.csv.gz`.
- **Accumulation quotidienne** → Yahoo Finance via `trading_os/data/accumulate.py`
  (`data/yahoo_NQ_1m.csv`, `_5m.csv`) ; nettoyage barres artefacts dans le loader.
- **Sélection backtest** → `trading_os/webapp/stats.py::select_backtest_df`
  (profond > yahoo 1m > yahoo 5m).
- **Limites connues** : données indicatives CFD/ETF-proxy, pas le carnet CME ;
  volume Yahoo peu fiable ; MT5 export CSV possible via `scripts/export_mt5.py`.
