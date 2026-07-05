"""Yahoo Finance fallback provider (no MT5 needed) — direct chart API via requests.

Free continuous futures quotes: ES=F, NQ=F. Good enough for HTF levels, daily
bias and the mobile dashboard. Intraday depth is limited (1m ~7d, 1h ~2y), so
serious 1m backtests should still use MT5/CSV exports.
"""

from __future__ import annotations

import pandas as pd
import requests

from trading_os.core.timeutils import NY

YAHOO_SYMBOLS = {"ES": "ES=F", "NQ": "NQ=F"}
_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (TradingOS personal research)"}


def fetch(instrument: str, range_: str = "60d", interval: str = "1h") -> pd.DataFrame:
    """OHLCV frame indexed in New York time for 'ES' or 'NQ'."""
    symbol = YAHOO_SYMBOLS.get(instrument, instrument)
    r = requests.get(_URL.format(symbol=symbol),
                     params={"range": range_, "interval": interval},
                     headers=_HEADERS, timeout=25)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    df = pd.DataFrame(
        {"open": quote["open"], "high": quote["high"], "low": quote["low"],
         "close": quote["close"], "volume": quote["volume"]},
        index=pd.to_datetime(result["timestamp"], unit="s", utc=True))
    df = df.dropna(subset=["open", "high", "low", "close"])
    df.index = df.index.tz_convert(NY)
    df.index.name = "timestamp"
    return df


def clean_intraday(df: pd.DataFrame, interval_minutes: int,
                   now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drop Yahoo artifacts: rows not aligned to the interval grid (the feed
    appends a live-quote row at an arbitrary minute) and the still-forming bar
    (its end lies in the future) — signals must only see completed candles."""
    if df.empty:
        return df
    aligned = df[(df.index.minute % interval_minutes == 0) if interval_minutes < 60
                 else (df.index.minute == 0)]
    now = now or pd.Timestamp.now(tz=NY)
    cutoff = now - pd.Timedelta(minutes=interval_minutes)
    return aligned[aligned.index <= cutoff]


def fetch_window(instrument: str, period1: float, period2: float,
                 interval: str = "1m") -> pd.DataFrame:
    """Fetch an explicit [period1, period2] epoch window (for 1m backfill).

    Yahoo caps 1m at ~7 days per request and ~30 days of history total.
    """
    symbol = YAHOO_SYMBOLS.get(instrument, instrument)
    r = requests.get(_URL.format(symbol=symbol),
                     params={"period1": int(period1), "period2": int(period2),
                             "interval": interval, "includePrePost": "true"},
                     headers=_HEADERS, timeout=25)
    r.raise_for_status()
    chart = r.json()["chart"]
    if chart.get("error"):
        raise RuntimeError(chart["error"].get("code", "yahoo error"))
    result = chart["result"][0]
    if "timestamp" not in result:
        return pd.DataFrame()
    q = result["indicators"]["quote"][0]
    df = pd.DataFrame(
        {"open": q["open"], "high": q["high"], "low": q["low"],
         "close": q["close"], "volume": q["volume"]},
        index=pd.to_datetime(result["timestamp"], unit="s", utc=True))
    df = df.dropna(subset=["open", "high", "low", "close"])
    df.index = df.index.tz_convert(NY)
    df.index.name = "timestamp"
    return df


def backfill_1m(instrument: str, weeks: int = 4) -> pd.DataFrame:
    """Page 1m data back `weeks` weeks, one 7-day window at a time."""
    import time as _time
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    frames = []
    for w in range(weeks):
        end = now - timedelta(days=7 * w)
        start = end - timedelta(days=7)
        try:
            part = fetch_window(instrument, start.timestamp(), end.timestamp(), "1m")
            if not part.empty:
                frames.append(part)
        except Exception:
            break              # Yahoo refuses windows older than ~30d
        _time.sleep(0.8)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    return out[~out.index.duplicated(keep="last")].sort_index()


def fetch_daily(instrument: str, range_: str = "6mo") -> pd.DataFrame:
    return fetch(instrument, range_, "1d")


def fetch_h1(instrument: str, range_: str = "60d") -> pd.DataFrame:
    return fetch(instrument, range_, "1h")
