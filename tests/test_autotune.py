"""Auto-tune strategy selection: guardrails and fallback."""

from trading_os.webapp.insights import FALLBACK_NAME, select_strategy


def row(variant, inst, n, exp, pf):
    return {"variant": variant, "instrument": inst, "tf": "5min",
            "n_trades": n, "expectancy_r": exp, "profit_factor": pf}


def test_picks_best_defensible_variant():
    rows = [
        row("Prise partielle, tous grades", "NQ", 22, 1.51, 2.1),
        row("Trailing 1R sans cible", "NQ", 21, 1.88, 2.7),
    ]
    sel = select_strategy(rows, "NQ")
    assert sel["variant"] == "Trailing 1R sans cible"
    assert sel["patch"] == {"min_rating": 0, "exit_mode": "trail"}


def test_fallback_when_no_variant_qualifies():
    rows = [
        row("Prise partielle, tous grades", "ES", 9, 0.16, 1.5),  # < 10 trades
        row("Trailing 1R sans cible", "ES", 11, -0.28, 0.7),      # espérance négative
    ]
    sel = select_strategy(rows, "ES")
    assert sel["variant"] == FALLBACK_NAME
    assert sel["patch"] == {}


def test_instruments_are_independent():
    rows = [row("Trailing 1R sans cible", "NQ", 30, 1.0, 2.0)]
    assert select_strategy(rows, "ES")["variant"] == FALLBACK_NAME
    assert select_strategy(rows, "NQ")["variant"] == "Trailing 1R sans cible"
