"""CSV market-data loading and resampling.

Expected CSV format (produced by scripts/export_mt5.py, or any export):
    timestamp,open,high,low,close,volume
    2024-03-04 09:30:00,5130.25,5131.50,5129.75,5131.00,1250

Column aliases are handled (MT5 exports 'time', 'tick_volume', '<DATE>/<TIME>'…).
Timestamps are localized from data.csv_timezone then converted to New York time.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_os.core.timeutils import to_ny

_ALIASES = {
    "time": "timestamp", "date": "timestamp", "datetime": "timestamp",
    "tick_volume": "volume", "vol": "volume", "real_volume": "volume",
}
REQUIRED = ["open", "high", "low", "close"]


def load_csv(path: str | Path, csv_timezone: str = "UTC") -> pd.DataFrame:
    """Load an OHLCV CSV -> DataFrame indexed by NY-tz timestamps."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier de données introuvable : {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().strip("<>") for c in df.columns]

    # MT5 terminal exports sometimes split date and time
    if "timestamp" not in df.columns and {"date", "time"} <= set(df.columns):
        df["timestamp"] = df["date"].astype(str) + " " + df["time"].astype(str)
        df = df.drop(columns=["date", "time"])
    df = df.rename(columns={k: v for k, v in _ALIASES.items() if k in df.columns})

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path.name}: {missing}. "
                         f"Colonnes trouvées : {list(df.columns)}")
    if "volume" not in df.columns:
        df["volume"] = 0

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")[REQUIRED + ["volume"]].astype(float)
    df = df[~df.index.duplicated(keep="last")]
    return to_ny(df, csv_timezone)


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample 1m data to a higher timeframe ('5min', '15min', '1h', '4h', '1d')."""
    tf = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h",
          "1d": "24h", "d": "24h", "24h": "24h"}.get(timeframe.lower(), timeframe)
    if tf == "1min":
        return df
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    # Futures day starts at 18:00 NY -> anchor daily/4h buckets on 18:00
    offset = "18h" if tf in ("24h", "4h") else None
    return df.resample(tf, offset=offset).agg(agg).dropna(subset=["open"])
