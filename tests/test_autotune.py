"""Auto-tune strategy selection: guardrails and fallback."""

from trading_os.webapp.insights import FALLBACK_NAME, select_strategy


def row(variant, inst, n, exp, pf):
    return {"variant": variant, "instrument": inst, "tf": "5min",
            "n_trades": n, "expectancy_r": exp, "profit_factor": pf}


def test_picks_best_defensible_variant():
    rows = [
        row("Sans filtre de grade", "NQ", 22, 1.51, 2.1),
        row("Entrée milieu de zone", "NQ", 21, 1.88, 2.7),
        row("Cible RR fixe 2:1", "NQ", 97, -0.20, 0.8),
    ]
    sel = select_strategy(rows, "NQ")
    assert sel["variant"] == "Entrée milieu de zone"
    assert sel["patch"] == {"min_rating": 0, "retest_entry": "midpoint"}


def test_fallback_when_no_variant_qualifies():
    rows = [
        row("Sans filtre de grade", "ES", 9, 0.16, 1.5),    # < 10 trades
        row("Entrée milieu de zone", "ES", 11, -0.28, 0.7),  # espérance négative
        row("Cible RR fixe 2:1", "ES", 68, 0.02, 1.05),      # PF trop faible
    ]
    sel = select_strategy(rows, "ES")
    assert sel["variant"] == FALLBACK_NAME
    assert sel["patch"] == {}


def test_instruments_are_independent():
    rows = [row("Sans filtre de grade", "NQ", 30, 1.0, 2.0)]
    assert select_strategy(rows, "ES")["variant"] == FALLBACK_NAME
    assert select_strategy(rows, "NQ")["variant"] == "Sans filtre de grade"
