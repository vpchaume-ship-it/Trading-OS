import pandas as pd

from trading_os.core.timeutils import NY, Killzones

CFG = {
    "london": {"start": "02:00", "end": "05:00"},
    "ny_am": {"start": "08:30", "end": "11:00"},
    "ny_pm": {"start": "13:30", "end": "16:00"},
}


def ts(hhmm: str) -> pd.Timestamp:
    return pd.Timestamp(f"2024-03-04 {hhmm}", tz=NY)


def test_labels():
    kz = Killzones(CFG)
    assert kz.label(ts("03:00")) == "london"
    assert kz.label(ts("08:30")) == "ny_am"     # start inclusive
    assert kz.label(ts("11:00")) is None        # end exclusive
    assert kz.label(ts("14:00")) == "ny_pm"
    assert kz.label(ts("20:00")) is None


def test_allowed_filter():
    kz = Killzones(CFG)
    assert kz.in_any(ts("03:00"), ["ny_am"]) is False
    assert kz.in_any(ts("09:00"), ["ny_am"]) is True
    assert kz.in_any(ts("09:00")) is True
