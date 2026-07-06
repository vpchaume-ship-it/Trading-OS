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
from trading_os.data.deep import load_deep

MIN_1M_BARS = 5_000    # ~1 semaine de séance 1m — dès qu'on l'a, le 1m prime
                       # (timeframe d'exécution fidèle à la méthode Dodgy)
DEEP_CAP = 95_000      # ~4 mois de 1m : borne le temps de build (~10 s/run)


def select_backtest_df(instrument: str, directory: str = "data"):
    """Best available execution frame: deep Dukascopy 1m > Yahoo 1m > Yahoo 5m.
    Returns (df, timeframe_str, source_label) or (None, None, None)."""
    deep = load_deep(instrument, directory)
    if deep is not None and len(deep) >= MIN_1M_BARS:
        if len(deep) > DEEP_CAP:
            deep = deep.tail(DEEP_CAP)
        return deep, "1min", "Dukascopy 1m (historique profond)"
    y1 = load_accumulated(Path(directory) / f"yahoo_{instrument}_1m.csv")
    if y1 is not None and len(y1) >= MIN_1M_BARS:
        return y1, "1min", "Yahoo 1m"
    y5 = load_accumulated(Path(directory) / f"yahoo_{instrument}_5m.csv")
    if y5 is not None and len(y5) >= 500:
        return y5, "5min", "Yahoo 5m"
    return None, None, None


def dashboard_backtest(cfg: dict, instrument: str, directory: str = "data",
                       patch: dict | None = None) -> dict | None:
    """patch = auto-tuned ifvg overrides chosen by insights.select_strategy."""
    df, tf, source = select_backtest_df(instrument, directory)
    if df is None:
        return None

    from trading_os.webapp.insights import apply_patch
    cfg2 = copy.deepcopy(cfg)
    cfg2["ifvg"]["timeframe"] = tf
    apply_patch(cfg2, patch or {})
    result = run_backtest(df, cfg2, instrument)
    if result.trades.empty:
        return {"tf": tf, "n_bars": len(df), "start": df.index[0], "end": df.index[-1],
                "source": source, "stats": {"n_trades": 0}, "trades": result.trades,
                "by_grade": None, "by_kz": None}
    return {
        "tf": tf, "n_bars": len(df), "source": source,
        "start": df.index[0], "end": df.index[-1],
        "stats": summary(result.trades),
        "trades": result.trades,
        "by_grade": breakdown(result.trades, "grade"),
        "by_kz": breakdown(result.trades, "killzone"),
    }
