# Trading OS — ES/NQ · modèle ICT IFVG · terminal

Système de trading en terminal pour les futures **ES** et **NQ**, basé sur le modèle
**IFVG (Inversion Fair Value Gap)** de la méthodologie ICT.

> ⚠️ **DÉMO UNIQUEMENT.** Ce projet ne se connecte qu'à l'environnement demo de
> Tradovate. Aucune connexion à un compte réel n'est implémentée, et les
> garde-fous qui l'empêchent sont codés en dur (voir `trading_os/forward/guards.py`).

## Installation

```bash
pip install -r requirements.txt
python -m trading_os.cli        # menu principal
python -m pytest tests/         # lancer les tests
```

## Structure

```
config.yaml                 # TOUT le paramétrage (timeframe, gap min, killzones, coûts…)
trading_os/
  cli.py                    # menu principal (rich)
  core/fvg.py               # détection FVG/IFVG — machine à états, sans lookahead
  core/swings.py            # swings, equal highs/lows (liquidité), cibles
  core/timeutils.py         # killzones, fuseau New York
  data/loader.py            # chargement CSV + resampling (1m -> 5m/1h/4h/daily)
  news/                     # Module 1 — red folders, scénarios, no-trade-zones
  backtest/                 # Module 2 — moteur, coûts, métriques, graphiques, rapport
  forward/                  # Module 3 — Tradovate DEMO, garde-fous, semi-auto, journal
  premarket/                # Module 4 — rapport prémarché quotidien
  knowledge_base/           # indexation de vos PDF ICT
scripts/export_mt5.py       # export MT5 -> CSV (à lancer sur votre machine Windows)
knowledge/                  # déposez vos PDF ici
data/                       # vos CSV de données de marché
journal/                    # trades, rapports de backtest, rapports prémarché
```

## Données de marché (MetaTrader 5)

Le package Python `MetaTrader5` ne fonctionne que **sous Windows avec le terminal
MT5 ouvert**. Le flux de travail est donc :

1. Sur votre machine Windows :
   ```bash
   pip install MetaTrader5 pandas
   python scripts/export_mt5.py --symbol ES --days 730 --out data/ES_1m.csv
   python scripts/export_mt5.py --symbol NQ --days 730 --out data/NQ_1m.csv
   ```
   (le nom du symbole dépend de votre broker — vérifiez le Market Watch)
2. Renseignez `data.csv_timezone` dans `config.yaml` avec le fuseau de votre
   serveur MT5 (souvent `Etc/GMT-2` ou `Etc/GMT-3`).
3. Le backtest et le rapport prémarché lisent ces CSV. Tout autre export CSV
   au format `timestamp,open,high,low,close,volume` fonctionne aussi.

Pour le mode semi-auto (Module 3), lancez l'export en continu :
`python scripts/export_mt5.py --symbol ES --watch --out data/live.csv`
et pointez `forward.live_csv` dessus.

## Les définitions implémentées (à comparer avec vos PDF)

- **FVG haussier** : sur 3 bougies, `low(c3) > high(c1)` → zone `[high(c1), low(c3)]`.
- **FVG baissier** : `high(c3) < low(c1)` → zone `[high(c3), low(c1)]`.
- **Inversion (IFVG)** : clôture **franche** au-delà de la borne opposée
  (`invalidation_mode: close` ou `body`). La zone change de polarité : un FVG
  haussier invalidé devient résistance (IFVG baissier), et inversement.
- Une mèche qui traverse toute la zone **sans clôture franche** n'est PAS une
  inversion (configurable : elle tue le FVG ou le laisse actif).
- **Entrée** : retest de la zone inversée (ordre limite au bord proximal par
  défaut), **stop** au-delà du bord opposé + buffer, **target** RR fixe ou
  liquidité opposée (swing confirmé le plus proche).

Si une définition de vos PDF contredit ceci, le menu *Base de connaissances →
concepts* extrait les passages concernés pour arbitrage.

## Rigueur du backtest

- **Aucun lookahead** : la détection est incrémentale barre par barre ; l'ordre
  limite posé à l'inversion ne peut pas se remplir sur la barre d'inversion
  elle-même (testé dans `tests/test_engine.py`).
- **Fill conservateur** : si une barre peut toucher le stop ET la target, le
  stop est compté. Le stop peut être touché sur la barre d'entrée.
- **Coûts réalistes par défaut** : commission 2,25 $/side (mini) ou 0,85 $/side
  (micro), 1 tick de slippage sur les stops. Tout est dans `config.yaml`.
- Position clôturée d'office à 16:55 NY (`eod_flat_time`).

## Garde-fous du forward test (codés en dur)

- URL API ≠ demo Tradovate → refus de démarrer.
- Taille max **1 contrat micro** (MES/MNQ uniquement).
- Limite de perte journalière (le `config.yaml` ne peut que la durcir, jamais
  la dépasser : plafond dur à 300 $).
- Pas de signal en no-trade-zone news.
- Le mode semi-auto **notifie seulement** — c'est vous qui validez sur Tradovate.

## Rappel

La carte de scénarios news est une aide qualitative, jamais une prédiction. La
réaction initiale aux red folders est souvent piégeuse (judas swing). Respectez
les no-trade-zones (30 min avant / 15 min après chaque red folder).
