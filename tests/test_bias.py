"""Daily bias (PDH/PDL) tests — tool 4 of the Daily Bias PDF."""

import pandas as pd

from trading_os.premarket.bias import daily_bias


def daily(rows):
    idx = pd.date_range("2024-03-04 18:00", periods=len(rows), freq="24h",
                        tz="America/New_York")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


REF = (100, 110, 90, 105)  # PDH=110, PDL=90


def test_break_and_close_above_pdh_is_bullish():
    d = daily([REF, (105, 115, 104, 112)])
    assert daily_bias(d)[0] == "haussier"


def test_sweep_pdl_respected_is_bullish():
    d = daily([REF, (100, 105, 88, 95)])  # low 88 < 90 but close 95 > 90
    assert daily_bias(d)[0] == "haussier"


def test_break_and_close_below_pdl_is_bearish():
    d = daily([REF, (95, 96, 85, 87)])
    assert daily_bias(d)[0] == "baissier"


def test_sweep_pdh_rejected_is_bearish():
    d = daily([REF, (105, 112, 100, 106)])  # high 112 > 110 but close 106 < 110
    assert daily_bias(d)[0] == "baissier"


def test_inside_day_is_neutral():
    d = daily([REF, (100, 108, 95, 102)])
    assert daily_bias(d)[0] == "neutre"


def test_not_enough_history():
    d = daily([REF])
    assert daily_bias(d)[0] == "neutre"
