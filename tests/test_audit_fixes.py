"""Verrous de l'audit QA 2026-07-11 : lookahead, réalisme d'exécution, feedback."""

import pandas as pd

from tests.conftest import make_df
from tests.test_engine import SETUP_BARS, cfg
from trading_os.backtest import feedback
from trading_os.backtest.engine import run_backtest

FILL_BARS = [(99.2, 100.3, 99.1, 99.9), (99.9, 100.0, 95.9, 96.2)]


# ---- C1 : niveaux de session sans lookahead --------------------------------

def test_overnight_level_frozen_only_after_open():
    """Un FVG formé PENDANT la fenêtre overnight ne peut pas utiliser l'extrême
    de cette même fenêtre (encore en formation) — il retombe sur le PDH/PDL."""
    day1 = [(100.0, 200.0, 99.5, 100.5)] + [(100.0, 100.8, 99.5, 100.5)] * 4  # PDH 200, hors de portée
    # jour 2 : le scénario IFVG se joue à 05:00 (overnight, avant la killzone
    # 08:30) — l'ON high (102.5, la barre c3 elle-même) ne doit PAS servir de niveau
    day2 = SETUP_BARS + FILL_BARS
    df = pd.concat([make_df(day1, start="2024-03-04 09:30"),
                    make_df(day2, start="2024-03-05 05:00")])
    c = cfg(allowed_killzones=["ny_am"],
            setup={"require_sweep": True, "sweep_mode": "session"})
    res = run_backtest(df, c, "ES")
    assert res.trades.empty
    assert res.skipped_no_session_sweep >= 1


def test_overnight_level_usable_in_killzone():
    """Après l'ouverture de la killzone, l'extrême overnight (fenêtre close)
    est un niveau valide : son balayage qualifie le setup."""
    day1 = [(100.0, 200.0, 99.5, 100.5)] + [(100.0, 100.8, 99.5, 100.5)] * 4
    on = [(100.0, 102.0, 99.8, 100.5)] + [(100.0, 100.5, 99.8, 100.2)] * 3  # ON high 102.0
    df = pd.concat([make_df(day1, start="2024-03-04 09:30"),
                    make_df(on, start="2024-03-05 05:00"),
                    make_df(SETUP_BARS + FILL_BARS, start="2024-03-05 08:35")])
    c = cfg(allowed_killzones=["ny_am"],
            setup={"require_sweep": True, "sweep_mode": "session"})
    res = run_backtest(df, c, "ES")   # c3 monte à 102.5 > ON high 102.0 -> sweep
    assert len(res.trades) == 1


def test_trading_day_pdh_skips_sunday_mini_session():
    """Jour de trading CME : les barres du dimanche soir appartiennent au lundi.
    Le « jour précédent » du lundi est vendredi — pas la mini-session du dimanche."""
    friday = [(100.0, 101.0, 99.5, 100.5)] + [(100.0, 100.8, 99.6, 100.4)] * 4
    sunday_eve = [(100.0, 150.0, 99.9, 100.2)] * 2          # spike dimanche 19:00
    monday = SETUP_BARS + FILL_BARS                          # c3 high 102.5
    df = pd.concat([make_df(friday, start="2024-03-01 09:30"),
                    make_df(sunday_eve, start="2024-03-03 19:00"),
                    make_df(monday, start="2024-03-04 09:30")])
    c = cfg(allowed_killzones=["ny_am"],
            setup={"require_sweep": True, "sweep_mode": "session"})
    res = run_backtest(df, c, "ES")
    # PDH du lundi = vendredi (101.0, balayé par 102.5) ; le spike dimanche
    # (150) est de l'overnight du lundi, PAS le jour précédent.
    assert len(res.trades) == 1


# ---- C2 : slippage marché sur l'entrée inversion_close ---------------------

def test_market_entry_pays_slippage():
    bars = SETUP_BARS + [(99.6, 99.8, 95.9, 96.0)]
    df = make_df(bars, start="2024-03-04 09:30")
    c = cfg(entry_timing="inversion_close", min_rating=0,
            target={"mode": "fixed_rr", "fixed_rr": 2.0,
                    "liquidity_min_rr": 1.5, "swing_strength": 3})
    res = run_backtest(df, c, "ES")
    assert len(res.trades) == 1
    t = res.trades.iloc[0]
    # short au marché sur close 99.6 avec 1 tick de slippage -> 99.35
    assert t["entry"] == 99.6 - 0.25


# ---- M1 : fill limite = trade-through strict --------------------------------

def test_limit_touch_alone_does_not_fill():
    bars = SETUP_BARS + [
        (99.2, 100.0, 99.1, 99.5),    # high == entry 100.0 : touch sans traversée
        (99.5, 99.7, 99.0, 99.2),
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(), "ES")
    assert res.trades.empty            # pas de fill au simple touch
    res2 = run_backtest(df, cfg(), "ES")   # sanity: config off -> fill
    c = cfg(); c["backtest"]["fill_requires_through"] = False
    res3 = run_backtest(df, c, "ES")
    assert len(res3.trades) == 1


# ---- M2 : la barre de reclaim remplit puis stoppe (pas d'annulation gratuite)

def test_reclaim_bar_fills_then_stops():
    bars = SETUP_BARS + [
        # touche l'entrée (100.3 > 100.0) puis clôture au-dessus du top (101.5)
        # ET du stop (102.0) : en réel = rempli puis stoppé, pas annulé
        (99.6, 102.6, 99.5, 102.4),
    ]
    df = make_df(bars, start="2024-03-04 09:30")
    res = run_backtest(df, cfg(), "ES")
    assert len(res.trades) == 1
    assert res.trades.iloc[0]["exit_reason"] == "stop"


# ---- M3 : anti-overfit = comparaison directe ajusté vs socle ----------------

def test_compare_adjusted_reverts_underperformer():
    st = {"active": {"stop_buffer_ticks": 3},
          "history": [{"date": "2026-07-01", "key": "stop_buffer_ticks", "from": 2,
                       "to": 3, "reason": "x", "evidence": "x", "status": "active",
                       "n_at_adoption": 20, "exp_at_adoption": 0.9}]}
    base = {"n_trades": 32, "expectancy_r": 0.90}
    adj = {"n_trades": 30, "expectancy_r": 0.60}      # -0.30 R vs socle
    st, notes = feedback.compare_adjusted(st, base, adj, n_base_now=32,
                                          today="2026-07-11")
    assert "stop_buffer_ticks" not in st["active"] and notes


def test_compare_adjusted_keeps_winner():
    st = {"active": {"stop_buffer_ticks": 3},
          "history": [{"date": "2026-07-01", "key": "stop_buffer_ticks", "from": 2,
                       "to": 3, "reason": "x", "evidence": "x", "status": "active",
                       "n_at_adoption": 20, "exp_at_adoption": 0.9}]}
    st, _ = feedback.compare_adjusted(st, {"n_trades": 32, "expectancy_r": 0.9},
                                      {"n_trades": 30, "expectancy_r": 1.1},
                                      n_base_now=32, today="2026-07-11")
    assert st["active"]["stop_buffer_ticks"] == 3
