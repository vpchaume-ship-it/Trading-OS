"""Configuration automatique MT5 → Trading OS — UNE SEULE COMMANDE, sous Windows,
avec le terminal MT5 ouvert et connecté à votre compte demo :

    pip install MetaTrader5 pandas
    python scripts/mt5_setup.py --days 365

Le script :
  1. se connecte au terminal MT5 ouvert ;
  2. cherche les symboles indices US disponibles chez votre broker
     (ES/MES/US500/SP500… pour le S&P, NQ/MNQ/USTEC/NAS100… pour le Nasdaq) ;
  3. détecte le fuseau horaire du serveur MT5 (comparaison de la dernière
     barre M1 avec l'heure UTC réelle) ;
  4. met à jour config.yaml automatiquement (mt5_symbol + data.csv_timezone) ;
  5. exporte l'historique 1m vers data/ES_1m.csv et data/NQ_1m.csv.

Ensuite, sur n'importe quelle machine : python -m trading_os.cli → menu 2 (backtest)
ou menu 4 (rapport prémarché). Pour le temps réel du mode semi-auto :
    python scripts/export_mt5.py --symbol <SYMBOLE> --watch --out data/live.csv
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from export_mt5 import fetch, get_mt5  # même dossier scripts/

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG = PROJECT_ROOT / "config.yaml"

# Noms possibles selon les brokers (futures CME, micros, CFD indices)
CANDIDATES = {
    "ES": ["ES", "MES", "US500", "SP500", "SPX500", "US.500", "S&P500", "SPI"],
    "NQ": ["NQ", "MNQ", "USTEC", "NAS100", "US100", "USTECH", "NASDAQ"],
}


def find_symbol(mt5, wanted: list[str]) -> str | None:
    symbols = [s.name for s in (mt5.symbols_get() or [])]
    uppers = {s.upper(): s for s in symbols}
    for cand in wanted:                      # 1) correspondance exacte
        if cand in uppers:
            return uppers[cand]
    for cand in wanted:                      # 2) préfixe (ex: ESZ25, US500.cash)
        for up, real in uppers.items():
            if up.startswith(cand):
                return real
    for cand in wanted:                      # 3) sous-chaîne
        for up, real in uppers.items():
            if cand in up:
                return real
    return None


def server_timezone(mt5, symbol: str) -> str:
    """MT5 timestamps = heure serveur encodée comme epoch. L'écart avec l'heure
    UTC réelle donne l'offset du serveur → nom POSIX Etc/GMT (signe inversé)."""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
    if rates is None or not len(rates):
        return "UTC"
    server_now = float(rates[0]["time"]) + 60.0          # fin de la barre courante
    utc_now = datetime.now(timezone.utc).timestamp()
    offset = round((server_now - utc_now) / 3600)
    if offset == 0:
        return "UTC"
    # POSIX inverse le signe : Etc/GMT-3 == UTC+3
    return f"Etc/GMT{'-' if offset > 0 else '+'}{abs(offset)}"


def patch_config(instrument: str, symbol: str, tz: str) -> None:
    text = CONFIG.read_text(encoding="utf-8")
    text = re.sub(rf'(?s)(  {instrument}:.*?mt5_symbol: )"[^"]*"',
                  rf'\1"{symbol}"', text, count=1)
    text = re.sub(r'(csv_timezone: )"[^"]*"', rf'\1"{tz}"', text, count=1)
    CONFIG.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Configuration automatique MT5 -> Trading OS")
    ap.add_argument("--days", type=int, default=365, help="historique 1m à exporter")
    args = ap.parse_args()

    mt5 = get_mt5()
    info = mt5.account_info()
    if info is None:
        sys.exit("Aucun compte connecté dans le terminal MT5.")
    if not getattr(info, "trade_mode", 0) == 0:   # 0 = ACCOUNT_TRADE_MODE_DEMO
        print("⚠️  ATTENTION : le compte MT5 connecté ne semble PAS être un compte demo.")
    print(f"Compte : {info.login} — {info.server} — {info.currency}")

    tz = None
    from datetime import timedelta
    end = datetime.now(timezone.utc)
    for instrument, wanted in CANDIDATES.items():
        symbol = find_symbol(mt5, wanted)
        if symbol is None:
            print(f"✗ {instrument} : aucun symbole trouvé parmi {wanted}.")
            print("  → Ouvrez le Market Watch (Ctrl+M), clic droit → 'Tout afficher',")
            print("    puis relancez, ou exportez manuellement avec export_mt5.py.")
            continue
        mt5.symbol_select(symbol, True)
        if tz is None:
            tz = server_timezone(mt5, symbol)
            print(f"Fuseau serveur détecté : {tz}")
        out = PROJECT_ROOT / "data" / f"{instrument}_1m.csv"
        print(f"✓ {instrument} → symbole broker {symbol!r} ; export {args.days} jours…")
        df = fetch(mt5, symbol, end - timedelta(days=args.days), end)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"  {len(df):,} barres 1m → {out}")
        patch_config(instrument, symbol, tz or "UTC")

    print("\nconfig.yaml mis à jour. Prochaine étape :")
    print("  python -m trading_os.cli   → menu 2 (backtest) ou 4 (rapport prémarché)")


if __name__ == "__main__":
    main()
