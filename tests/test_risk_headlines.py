"""Météo du risque (score mécanique) + scoring du fil macro."""

from trading_os.news.headlines import _score
from trading_os.premarket.risk import score_risk


def test_risk_on_calm_vix():
    v, s = score_risk(vix=13.5, vix_chg=-1.2, gold_chg_pct=-0.9, dxy_chg_pct=0.1)
    assert v == "risk_on" and s >= 2


def test_risk_off_vix_spike():
    v, s = score_risk(vix=27.0, vix_chg=3.5, gold_chg_pct=1.8, dxy_chg_pct=0.9)
    assert v == "risk_off" and s <= -2


def test_neutral_middle():
    v, _ = score_risk(vix=16.5, vix_chg=0.2, gold_chg_pct=0.1, dxy_chg_pct=0.2)
    assert v == "neutre"


def test_headline_scoring_prioritizes_fed():
    fed = _score("Powell hints at rate cut as CPI cools")
    noise = _score("Local bakery wins award")
    assert fed >= 6 and noise == 0


def test_headline_noise_blacklist():
    assert _score("Betty J. Powell Obituary Jul 9, 2026") == 0
    assert _score("High school football: Nasdaq East wins") == 0


def test_direction_lexicon():
    from trading_os.news.headlines import direction
    assert direction("Nasdaq rallies as Fed signals rate cut") == 1
    assert direction("Stocks plunge on hot inflation fears") == -1
    assert direction("Fed announces task force members") == 0


def test_news_bias_aggregates():
    from trading_os.news.headlines import Headline, news_bias
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    heads = [Headline("Nasdaq surges on rate cut hopes", "X", now, 5),
             Headline("S&P 500 gains as CPI cools", "Y", now, 5),
             Headline("Minor tensions in shipping", "Z", now, 1)]
    nb = news_bias(heads)
    assert nb["verdict"] == "bullish" and nb["n_bull"] == 2
    assert news_bias([]) is None


def test_utility_rate_hike_is_noise():
    assert _score("Southwest Gas reschedules consumer session on proposed Nevada rate hike") == 0
    assert _score("Duke reduces rate hike request, still faces regulator pushback") == 0
    assert _score("Fed signals rate hike amid sticky inflation") > 0
