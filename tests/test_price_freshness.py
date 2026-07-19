"""Le prix affiché doit être la cotation live/close (spot Yahoo), pas la
dernière bougie H1 complète (qui fige le prix hors killzone)."""

import pandas as pd

from trading_os.data import yahoo


def test_spot_returns_none_on_network_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no net")
    monkeypatch.setattr(yahoo.requests, "get", boom)
    assert yahoo.spot("NQ") is None


def test_spot_reads_regular_market_price(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"chart": {"result": [{"meta": {
                "regularMarketPrice": 28773.25,
                "regularMarketTime": 1784321999}}]}}
    monkeypatch.setattr(yahoo.requests, "get", lambda *a, **k: _Resp())
    price, when = yahoo.spot("NQ")
    assert price == 28773.25
    assert isinstance(when, pd.Timestamp)
    assert str(when.tz) == "America/New_York"


def test_instrument_data_prefers_spot(monkeypatch):
    """instrument_data doit afficher le prix spot même si la dernière bougie
    H1 est bien plus ancienne (cas marché fermé)."""
    from trading_os.webapp import build

    # spot renvoie une valeur fraîche distincte de toute bougie
    ts = pd.Timestamp("2026-07-17 16:59:00", tz="America/New_York")
    monkeypatch.setattr(build, "spot", lambda name: (28773.25, ts), raising=False)
    monkeypatch.setattr("trading_os.data.yahoo.spot", lambda name: (28773.25, ts))

    # jeux de données minimalistes : >=3 sessions daily, un peu de H1
    idx_d = pd.date_range("2026-07-10", periods=6, freq="D", tz="America/New_York")
    daily = pd.DataFrame({"open": 29000.0, "high": 29500.0, "low": 28500.0,
                          "close": 29225.75, "volume": 1}, index=idx_d)
    idx_h = pd.date_range("2026-07-17 08:00", periods=2, freq="h",
                          tz="America/New_York")
    h1 = pd.DataFrame({"open": 28600.0, "high": 28650.0, "low": 28590.0,
                       "close": 28623.25, "volume": 1}, index=idx_h)

    cfg = {"instruments": {"NQ": {"tick_size": 0.25}},
           "ifvg": {"min_gap_ticks": 4}}
    monkeypatch.setattr(build, "datetime",
                        _FixedNow(pd.Timestamp("2026-07-18 09:00",
                                               tz="America/New_York")))
    d = build.instrument_data("NQ", cfg, {"NQ": (daily, h1)})
    assert d is not None
    # le prix vient du spot (28773.25), PAS de la bougie H1 (28623.25)
    assert d["price"] == 28773.25


class _FixedNow:
    """Remplace build.datetime.now(tz) par un instant fixe."""
    def __init__(self, ts):
        self._ts = ts

    def now(self, tz=None):
        return self._ts.to_pydatetime() if tz is None else \
            self._ts.tz_convert(tz).to_pydatetime()
