"""Daily bias via PDH/PDL — implements tool 4 of the knowledge/ Daily Bias PDF.

Rules (previous completed day vs the day before it):
* breaks and closes above PDH        -> bullish (target: next PDH)
* sweeps PDL but does NOT close below -> bullish (respected PDL, target PDH)
* breaks and closes below PDL        -> bearish
* sweeps PDH but does NOT close above -> bearish (failed at PDH, target PDL)
* oscillates inside the range        -> neutral (wait for breakout or FTD)

The PDF's other tools (IRL/ERL draw, OHLC/OLHC profile, M15 orderflow with
CISD confirmation) are judgement calls made at the screen — the report states
the mechanical PDH/PDL read and reminds you to confirm with 1H CISD.
"""

from __future__ import annotations

import pandas as pd


def daily_bias(daily: pd.DataFrame) -> tuple[str, str]:
    """daily: completed daily sessions OHLC (18:00->17:00 NY). Returns (bias, reason)."""
    if len(daily) < 2:
        return "neutre", "Pas assez d'historique quotidien pour lire un biais."
    ref, last = daily.iloc[-2], daily.iloc[-1]
    pdh, pdl = ref["high"], ref["low"]

    if last["close"] > pdh:
        return ("haussier", f"La veille a cassé ET clôturé au-dessus du PDH ({pdh:,.2f}) "
                "→ continuation attendue vers le prochain pool de liquidité haut.")
    if last["close"] < pdl:
        return ("baissier", f"La veille a cassé ET clôturé sous le PDL ({pdl:,.2f}) "
                "→ continuation attendue vers le prochain pool de liquidité bas.")
    if last["low"] < pdl and last["close"] > pdl:
        return ("haussier", f"La veille a balayé le PDL ({pdl:,.2f}) sans clôturer dessous "
                "(liquidité prise, niveau respecté) → cible : le PDH.")
    if last["high"] > pdh and last["close"] < pdh:
        return ("baissier", f"La veille a balayé le PDH ({pdh:,.2f}) sans clôturer au-dessus "
                "(échec au niveau) → cible : le PDL.")
    return ("neutre", "La veille a oscillé entre PDH et PDL sans les déplacer "
            "→ attendre une cassure franche ou un failure-to-displace (FTD).")


BIAS_REMINDER = ("Rappel méthodologie (PDF Daily Bias) : le biais mécanique PDH/PDL doit être "
                 "confirmé par un CISD 1H au contact du niveau avant toute exécution, et la "
                 "fenêtre de trading recommandée est 9:30–11:30 NY uniquement.")
