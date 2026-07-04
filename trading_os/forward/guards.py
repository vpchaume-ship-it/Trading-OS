"""HARD-CODED safety guards for the forward-test module.

These constants are deliberately NOT configurable: no config value, env var or
CLI flag can loosen them. config.yaml may only be MORE restrictive.
"""

from __future__ import annotations

# The ONLY API base allowed. Any other URL -> refuse to start.
DEMO_BASE_URL = "https://demo.tradovateapi.com/v1"

# Position size cap: 1 contract, micros only.
HARD_MAX_CONTRACTS = 1
HARD_ALLOWED_SYMBOL_PREFIXES = ("MES", "MNQ")

# Absolute daily-loss ceiling (USD). config.forward.daily_loss_limit_usd may be
# lower, never higher.
HARD_DAILY_LOSS_LIMIT_USD = 300.0


class SafetyViolation(RuntimeError):
    """Raised whenever a guard is breached — the module must stop."""


def assert_demo_url(url: str) -> None:
    if not url.startswith(DEMO_BASE_URL):
        raise SafetyViolation(
            f"URL API refusée : {url!r}. Seul l'environnement DEMO "
            f"({DEMO_BASE_URL}) est autorisé. Aucune connexion à un compte réel "
            "ne sera jamais implémentée.")


def assert_order_allowed(symbol: str, qty: int) -> None:
    if qty > HARD_MAX_CONTRACTS:
        raise SafetyViolation(
            f"Taille refusée : {qty} > {HARD_MAX_CONTRACTS} contrat (garde-fou codé en dur).")
    if not symbol.upper().startswith(HARD_ALLOWED_SYMBOL_PREFIXES):
        raise SafetyViolation(
            f"Symbole refusé : {symbol!r}. Micros uniquement : "
            f"{HARD_ALLOWED_SYMBOL_PREFIXES}.")


def effective_daily_loss_limit(configured: float) -> float:
    return min(float(configured), HARD_DAILY_LOSS_LIMIT_USD)


def assert_daily_loss_ok(realized_pnl_today: float, configured_limit: float) -> None:
    limit = effective_daily_loss_limit(configured_limit)
    if realized_pnl_today <= -limit:
        raise SafetyViolation(
            f"Limite de perte journalière atteinte ({realized_pnl_today:+.2f} $ ≤ "
            f"-{limit:.2f} $). Module forward test arrêté pour la journée.")
