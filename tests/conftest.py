import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest


def make_df(bars: list[tuple], start="2024-03-04 09:30", freq="1min", tz="America/New_York"):
    """bars: list of (open, high, low, close) -> OHLCV frame with NY-tz index."""
    idx = pd.date_range(start=start, periods=len(bars), freq=freq, tz=tz)
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 100
    return df
