"""Evolving backtest stats for the mobile dashboard.

Runs the real IFVG engine on the accumulated Yahoo dataset: 1m as soon as
enough history has been accumulated by the daily routine, 5m (60 days) until
then. The stats therefore improve every morning as the dataset grows.
"""

from __future__ import annotations

import copy
from pathlib import Path

from trading_os.backtest.engine import run_backtest
from trading_os.backtest.metrics import breakdown, summary
from trading_os.data.accumulate import load_accumulated

MIN_1M_BARS = 15_000   # ~2-3 semaines de séance : en dessous, le 5m est plus parlant


def dashboard_backtest(cfg: dict, instrument: str, directory: str = "data") -> dict | None:
    df_1m = load_accumulated(Path(directory) / f"yahoo_{instrument}_1m.csv")
    df_5m = load_accumulated(Path(directory) / f"yahoo_{instrument}_5m.csv")

    if df_1m is not None and len(df_1m) >= MIN_1M_BARS:
        df, tf = df_1m, "1min"
    elif df_5m is not None and len(df_5m) >= 500:
        df, tf = df_5m, "5min"
    else:
        return None

    cfg2 = copy.deepcopy(cfg)
    cfg2["ifvg"]["timeframe"] = tf
    result = run_backtest(df, cfg2, instrument)
    if result.trades.empty:
        return {"tf": tf, "n_bars": len(df), "start": df.index[0], "end": df.index[-1],
                "stats": {"n_trades": 0}, "trades": result.trades,
                "by_grade": None, "by_kz": None}
    return {
        "tf": tf, "n_bars": len(df),
        "start": df.index[0], "end": df.index[-1],
        "stats": summary(result.trades),
        "trades": result.trades,
        "by_grade": breakdown(result.trades, "grade"),
        "by_kz": breakdown(result.trades, "killzone"),
    }
