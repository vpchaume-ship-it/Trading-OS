"""Grow an intraday dataset from Yahoo, day after day, without MT5.

Yahoo only serves ~7 days of 1m and ~60 days of 5m — but fetched every weekday
and merged into a committed CSV, the 1m history grows without limit. The daily
routine runs this, then commits data/yahoo_*.csv to the branch so the dataset
survives ephemeral cloud sessions.

Usage:  python -m trading_os.data.accumulate
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_os.core.timeutils import NY
from trading_os.data.yahoo import backfill_1m, clean_intraday, fetch

FETCH_PLAN = [("5m", "60d", "5m", 5)]     # le 1m est géré séparément (backfill 4 semaines)


def load_accumulated(path: str | Path) -> pd.DataFrame | None:
    path = Path(path)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    idx = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(NY)
    df = df.drop(columns=["timestamp"]).set_index(idx)
    df.index.name = "timestamp"
    return df.sort_index()


def accumulate(instrument: str, directory: str | Path = "data") -> dict[str, tuple[Path, int]]:
    """Fetch fresh Yahoo intraday data and merge into the committed CSVs.

    Returns {interval: (path, n_total_bars)}.
    """
    def _merge_save(path: Path, fresh: pd.DataFrame, minutes: int) -> int:
        old = load_accumulated(path)
        merged = fresh if old is None else pd.concat([old, fresh])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        merged = clean_intraday(merged, minutes)   # drop artifacts + forming bar
        path.parent.mkdir(parents=True, exist_ok=True)
        to_save = merged.copy()
        to_save.index = to_save.index.tz_convert("UTC")   # stable round-trip
        to_save.to_csv(path)
        return len(merged)

    out: dict[str, tuple[Path, int]] = {}
    for interval, range_, suffix, minutes in FETCH_PLAN:
        path = Path(directory) / f"yahoo_{instrument}_{suffix}.csv"
        out[interval] = (path, _merge_save(path, fetch(instrument, range_, interval), minutes))
    # 1m : backfill 4 semaines (Yahoo ~30 j max), fusionné dans l'historique cumulé
    p1 = Path(directory) / f"yahoo_{instrument}_1m.csv"
    out["1m"] = (p1, _merge_save(p1, backfill_1m(instrument, weeks=4), 1))
    return out


def main() -> None:
    import os
    for instrument in ("NQ",):    # NQ seul tradé ; ES (réf. SMT) vient du flux live
        try:
            result = accumulate(instrument)
            parts = ", ".join(f"{k}: {n:,} barres" for k, (_, n) in result.items())
            print(f"✓ {instrument} — {parts}")
        except Exception as exc:
            print(f"✗ {instrument} — {exc}")
    # Historique profond Dukascopy : extension incrémentale quotidienne, sinon
    # la fenêtre du backtest reste figée à la dernière barre stockée (le deep
    # est prioritaire sur Yahoo dans select_backtest_df). C'est l'étape LENTE
    # (~90 s) : inutile en intraday (le backtest 24 mois est la référence gelée,
    # pas besoin de fraîcheur 5 min) → TOS_SKIP_DEEP=1 la saute pour un refresh
    # rapide. L'extension quotidienne du matin garde le deep à jour.
    if os.environ.get("TOS_SKIP_DEEP") == "1":
        print("↷ deep Dukascopy sauté (refresh intraday rapide)")
        return
    try:
        from trading_os.data.deep import refresh_deep
        n = refresh_deep("NQ")
        print(f"✓ NQ profond — {n:,} barres 1m après extension")
    except Exception as exc:
        print(f"✗ NQ profond — {exc} (le backtest continue sur l'existant)")


if __name__ == "__main__":
    main()
