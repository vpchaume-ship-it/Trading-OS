"""Deep 1m history from Dukascopy (free) — E-mini S&P 500 / Nasdaq 100 proxies.

Dukascopy serves ~10 years of clean 1m OHLC for the S&P 500 and Nasdaq 100
index CFDs, which track ES / NQ tick-for-tick in structure. Perfect for a
statistically meaningful IFVG backtest without a paid API. Absolute price level
differs slightly from the futures (cash vs future basis) but the method is
self-relative (gaps, inversions, R multiples), so results transfer.

Stored gzipped in data/deep_{ES,NQ}_1m.csv.gz (committed so the deep sample
survives ephemeral cloud sessions). The daily routine extends it incrementally.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from trading_os.core.timeutils import NY

DUKA_INSTRUMENT = {"ES": "INSTRUMENT_IDX_AMERICA_E_SANDP_500",
                   "NQ": "INSTRUMENT_IDX_AMERICA_E_NQ_100"}


def _deep_path(instrument: str, directory: str = "data") -> Path:
    return Path(directory) / f"deep_{instrument}_1m.csv.gz"


def load_deep(instrument: str, directory: str = "data") -> pd.DataFrame | None:
    path = _deep_path(instrument, directory)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    idx = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(NY)
    df = df.drop(columns=["timestamp"]).set_index(idx)
    df.index.name = "timestamp"
    return df.sort_index()


def _fetch(instrument: str, start: datetime, end: datetime) -> pd.DataFrame:
    import dukascopy_python
    from dukascopy_python import instruments as ins
    df = dukascopy_python.fetch(
        getattr(ins, DUKA_INSTRUMENT[instrument]),
        dukascopy_python.INTERVAL_MIN_1, dukascopy_python.OFFER_SIDE_BID,
        start, end)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.index = pd.DatetimeIndex(df.index).tz_convert(NY)
    df.index.name = "timestamp"
    return df.dropna(subset=["open", "high", "low", "close"])


def refresh_deep(instrument: str, months: int = 12, directory: str = "data") -> int:
    """Fetch/extend the deep 1m set. Returns total bar count after merge.

    First run pulls `months` back; later runs only append from the last stored
    bar to now (cheap incremental update for the daily routine).
    """
    existing = load_deep(instrument, directory)
    now = datetime.now(timezone.utc)
    if existing is None or existing.empty:
        start = now - timedelta(days=30 * months)
    else:
        start = existing.index[-1].tz_convert("UTC").to_pydatetime() - timedelta(minutes=1)
    fresh = _fetch(instrument, start, now)
    merged = fresh if existing is None else pd.concat([existing, fresh])
    if merged.empty:
        return 0
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    path = _deep_path(instrument, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = merged.copy()
    out.index = out.index.tz_convert("UTC")
    out.to_csv(path, compression="gzip")
    return len(merged)


def main() -> None:
    import sys
    months = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    for inst in ("ES", "NQ"):
        try:
            n = refresh_deep(inst, months)
            print(f"✓ {inst} — {n:,} barres 1m dans {_deep_path(inst)}")
        except Exception as exc:
            print(f"✗ {inst} — {exc}")


if __name__ == "__main__":
    main()
