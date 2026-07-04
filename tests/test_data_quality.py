"""Data-quality fixes: Yahoo intraday cleaning and mixed-offset NTZ parsing."""

import pandas as pd

from tests.conftest import make_df
from trading_os.backtest.engine import _in_ntz, _load_ntz_intervals
from trading_os.data.yahoo import clean_intraday


def test_clean_intraday_drops_misaligned_and_forming_bars():
    now = pd.Timestamp("2024-03-04 10:07", tz="America/New_York")
    idx = pd.DatetimeIndex([
        pd.Timestamp("2024-03-04 09:00", tz="America/New_York"),  # complete
        pd.Timestamp("2024-03-04 09:59", tz="America/New_York"),  # quote artifact
        pd.Timestamp("2024-03-04 10:00", tz="America/New_York"),  # still forming
    ])
    df = pd.DataFrame({"open": 1, "high": 1, "low": 1, "close": 1, "volume": 0},
                      index=idx)
    out = clean_intraday(df, 60, now=now)
    assert list(out.index) == [idx[0]]

    # 5m grid: 10:05 bar completes at 10:10 > now -> dropped
    idx5 = pd.DatetimeIndex([
        pd.Timestamp("2024-03-04 10:00", tz="America/New_York"),
        pd.Timestamp("2024-03-04 10:03", tz="America/New_York"),  # misaligned
        pd.Timestamp("2024-03-04 10:05", tz="America/New_York"),  # forming
    ])
    df5 = pd.DataFrame({"open": 1, "high": 1, "low": 1, "close": 1, "volume": 0},
                       index=idx5)
    out5 = clean_intraday(df5, 5, now=now)
    assert list(out5.index) == [idx5[0]]


def test_ntz_intervals_with_mixed_dst_offsets(tmp_path):
    # un événement en heure d'été (-04:00) et un en heure d'hiver (-05:00)
    csv = tmp_path / "history.csv"
    csv.write_text(
        "datetime_ny,title\n"
        "2026-07-02T08:30:00-04:00,NFP\n"
        "2026-12-10T08:30:00-05:00,CPI\n")
    intervals = _load_ntz_intervals(str(csv), 30, 15)
    assert len(intervals) == 2
    summer = pd.Timestamp("2026-07-02 08:45", tz="America/New_York")
    winter = pd.Timestamp("2026-12-10 08:10", tz="America/New_York")
    outside = pd.Timestamp("2026-12-10 09:00", tz="America/New_York")
    assert _in_ntz(summer, intervals)
    assert _in_ntz(winter, intervals)
    assert not _in_ntz(outside, intervals)
