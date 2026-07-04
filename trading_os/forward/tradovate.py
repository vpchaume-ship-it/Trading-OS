"""Tradovate DEMO REST client (journal sync + account state).

Credentials come from .env (never hard-coded). Every request re-asserts the
demo-only guard. Order placement exists but is guarded to 1 micro contract and
is only used if you explicitly call it — the semi-auto mode NOTIFIES, it does
not trade for you.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from trading_os.forward.guards import (DEMO_BASE_URL, SafetyViolation,
                                       assert_demo_url, assert_order_allowed)


class TradovateDemo:
    def __init__(self):
        load_dotenv()
        self.base = DEMO_BASE_URL
        assert_demo_url(self.base)
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    # ---- auth ----------------------------------------------------------
    def authenticate(self) -> None:
        creds = {
            "name": os.getenv("TRADOVATE_USERNAME"),
            "password": os.getenv("TRADOVATE_PASSWORD"),
            "appId": os.getenv("TRADOVATE_APP_ID", "TradingOS"),
            "appVersion": os.getenv("TRADOVATE_APP_VERSION", "1.0"),
            "cid": os.getenv("TRADOVATE_CID"),
            "sec": os.getenv("TRADOVATE_SECRET"),
        }
        missing = [k for k, v in creds.items() if not v]
        if missing:
            raise SafetyViolation(
                f"Identifiants demo manquants dans .env : {missing}. "
                "Copier .env.example vers .env et le remplir.")
        r = self._post("/auth/accesstokenrequest", creds, auth=False)
        if "accessToken" not in r:
            raise SafetyViolation(f"Authentification demo échouée : {r}")
        self._token = r["accessToken"]
        self._token_expiry = datetime.fromisoformat(
            r["expirationTime"].replace("Z", "+00:00")) if "expirationTime" in r else None

    def _headers(self) -> dict:
        if not self._token:
            self.authenticate()
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: dict | None = None):
        url = self.base + path
        assert_demo_url(url)
        resp = requests.get(url, params=params, headers=self._headers(), timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict, auth: bool = True):
        url = self.base + path
        assert_demo_url(url)
        headers = self._headers() if auth else {}
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ---- account / journal sync -----------------------------------------
    def accounts(self) -> list[dict]:
        return self._get("/account/list")

    def fills_today(self, account_id: int) -> list[dict]:
        """All fills for the account (Tradovate returns the recent set)."""
        fills = self._get("/fill/list")
        today = datetime.now(timezone.utc).date()
        out = []
        for f in fills:
            ts = datetime.fromisoformat(f["timestamp"].replace("Z", "+00:00"))
            if ts.date() == today:
                out.append(f)
        return out

    def fills_all(self) -> list[dict]:
        return self._get("/fill/list")

    def contract_name(self, contract_id: int) -> str:
        return self._get("/contract/item", {"id": contract_id}).get("name", "?")

    def cash_balance(self, account_id: int) -> dict:
        return self._post("/cashBalance/getcashbalancesnapshot",
                          {"accountId": account_id})

    # ---- guarded order placement (semi-auto, manual confirmation only) --
    def place_order(self, account_id: int, symbol: str, action: str, qty: int,
                    order_type: str = "Market") -> dict:
        """Place an order on the DEMO account. Guards re-checked here, hard."""
        assert_order_allowed(symbol, qty)
        if action not in ("Buy", "Sell"):
            raise SafetyViolation(f"Action invalide : {action!r}")
        payload = {
            "accountId": account_id, "action": action, "symbol": symbol,
            "orderQty": qty, "orderType": order_type, "isAutomated": True,
        }
        return self._post("/order/placeorder", payload)
