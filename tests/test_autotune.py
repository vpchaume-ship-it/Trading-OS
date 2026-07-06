"""Auto-tune strategy selection: guardrails and fallback."""

from trading_os.webapp.insights import FALLBACK_NAME, select_strategy


def row(variant, inst, n, exp, pf, wr=0.35):
    return {"variant": variant, "instrument": inst, "tf": "5min", "win_rate": wr,
            "n_trades": n, "expectancy_r": exp, "profit_factor": pf}


def test_picks_highest_winrate_among_profitable():
    # both clear the guardrails; selection favours the higher win rate
    rows = [
        row("Prise partielle, tous grades", "NQ", 42, 0.34, 1.65, wr=0.33),
        row("Sortie classique (full)", "NQ", 42, 0.95, 2.13, wr=0.24),
    ]
    sel = select_strategy(rows, "NQ")
    assert sel["variant"] == "Prise partielle, tous grades"


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
