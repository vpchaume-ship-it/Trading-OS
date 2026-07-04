"""Export de données MetaTrader 5 vers CSV — à lancer SUR VOTRE MACHINE WINDOWS
avec le terminal MT5 ouvert et connecté (le package `MetaTrader5` n'existe que
sous Windows).

Exemples :
    # Historique 1m des 2 dernières années pour ES :
    python scripts/export_mt5.py --symbol ES --days 730 --out data/ES_1m.csv

    # Mode watch : ré-exporte les dernières barres toutes les 20 s
    # (alimente le mode semi-auto du module forward test) :
    python scripts/export_mt5.py --symbol ES --watch --out data/ES_live.csv

Le nom exact du symbole dépend de votre broker MT5 (ex: "ES", "ESZ25", "US500").
Vérifiez-le dans l'onglet "Market Watch" du terminal.

Les timestamps exportés sont ceux du serveur MT5 : renseignez le fuseau
correspondant dans config.yaml -> data.csv_timezone (souvent "Etc/GMT-2"
ou "Etc/GMT-3" pendant l'heure d'été, selon le broker).
"""

from __future__ import annotations

import argparse
import sys
import time as time_mod
from datetime import datetime, timedelta, timezone
from pathlib import Path


def get_mt5():
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError:
        sys.exit("Le package MetaTrader5 n'est pas installé (Windows uniquement) : "
                 "pip install MetaTrader5")
    if not mt5.initialize():
        sys.exit(f"Impossible d'initialiser MT5 : {mt5.last_error()} "
                 "(le terminal MT5 doit être ouvert et connecté)")
    return mt5


def fetch(mt5, symbol: str, start: datetime, end: datetime):
    import pandas as pd
    if not mt5.symbol_select(symbol, True):
        sys.exit(f"Symbole introuvable chez votre broker : {symbol!r}")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
    if rates is None or len(rates) == 0:
        sys.exit(f"Aucune donnée reçue pour {symbol} ({mt5.last_error()})")
    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    return df[["timestamp", "open", "high", "low", "close", "tick_volume"]].rename(
        columns={"tick_volume": "volume"})


def main():
    ap = argparse.ArgumentParser(description="Export MT5 -> CSV 1m")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--out", required=True)
    ap.add_argument("--watch", action="store_true",
                    help="ré-exporte les 2 derniers jours en continu (toutes les 20 s)")
    args = ap.parse_args()

    mt5 = get_mt5()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.watch:
        print(f"Mode watch sur {args.symbol} -> {out} (Ctrl+C pour arrêter)")
        while True:
            end = datetime.now(timezone.utc)
            df = fetch(mt5, args.symbol, end - timedelta(days=2), end)
            df.to_csv(out, index=False)
            time_mod.sleep(20)
    else:
        end = datetime.now(timezone.utc)
        df = fetch(mt5, args.symbol, end - timedelta(days=args.days), end)
        df.to_csv(out, index=False)
        print(f"{len(df)} barres 1m exportées -> {out}")


if __name__ == "__main__":
    main()
