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


def fetch_daily(instrument: str, range_: str = "6mo") -> pd.DataFrame:
    return fetch(instrument, range_, "1d")


def fetch_h1(instrument: str, range_: str = "60d") -> pd.DataFrame:
    return fetch(instrument, range_, "1h")
