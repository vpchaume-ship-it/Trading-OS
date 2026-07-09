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
