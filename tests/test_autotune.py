"""Auto-tune strategy selection: guardrails and fallback."""

from trading_os.webapp.insights import FALLBACK_NAME, select_strategy


def row(variant, inst, n, exp, pf, wr=0.35):
    return {"variant": variant, "instrument": inst, "tf": "5min", "win_rate": wr,
            "n_trades": n, "expectancy_r": exp, "profit_factor": pf}


RETEST = "Sweep session + V-shape (retest, cible pleine)"
SCALE = "Sweep session + V-shape (retest + prise partielle)"


def test_picks_highest_winrate_among_profitable():
    # both clear the guardrails; selection favours the higher win rate
    rows = [
        row(SCALE, "NQ", 42, 0.34, 1.65, wr=0.47),
        row(RETEST, "NQ", 42, 0.95, 2.13, wr=0.33),
    ]
    sel = select_strategy(rows, "NQ")
    assert sel["variant"] == SCALE


def test_fallback_when_no_variant_qualifies():
    rows = [
        row(RETEST, "ES", 9, 0.16, 1.5),                  # < 10 trades
        row(SCALE, "ES", 11, -0.28, 0.7),                 # espérance négative
    ]
    sel = select_strategy(rows, "ES")
    assert sel["variant"] == FALLBACK_NAME
    assert sel["patch"] == {}


def test_instruments_are_independent():
    rows = [row(RETEST, "NQ", 30, 1.0, 2.0)]
    assert select_strategy(rows, "ES")["variant"] == FALLBACK_NAME
    assert select_strategy(rows, "NQ")["variant"] == RETEST
