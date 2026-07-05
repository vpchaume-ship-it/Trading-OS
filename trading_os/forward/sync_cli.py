"""Entry point for the daily routine: sync Tradovate DEMO fills into the journal.

Runs only if demo credentials are present in the environment (.env or cloud
env vars). Safe no-op otherwise, so the routine never fails for lack of creds.

    python -m trading_os.forward.sync_cli
"""

from __future__ import annotations

import os

from trading_os.config import load_config


def main() -> None:
    required = ["TRADOVATE_USERNAME", "TRADOVATE_PASSWORD",
                "TRADOVATE_CID", "TRADOVATE_SECRET"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"Sync Tradovate ignorée — identifiants demo manquants : {missing}. "
              "Ajoutez-les à l'environnement pour activer le journal automatique.")
        return
    cfg = load_config()
    try:
        from trading_os.forward.journal_sync import sync_journal
        added = sync_journal(cfg)
        print(f"✓ Journal Tradovate demo synchronisé : {added} trade(s) ajouté(s).")
    except Exception as exc:
        print(f"✗ Sync Tradovate échouée : {exc}")


if __name__ == "__main__":
    main()
