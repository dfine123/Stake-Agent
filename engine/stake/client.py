"""Stake.com GraphQL client for GambleAgent.

Endpoint: https://api.stake.com/graphql
Auth:     x-access-token header (token from browser DevTools → Network → any graphql request)

Query/mutation source confidence:
  CONFIRMED   — verified against Seuntjie900/DiceBot PD.cs (real reverse-engineering)
  UNVERIFIED  — best-guess shape; must be captured from DevTools before relying on it
                (see docs/stake-api-notes.md for capture instructions)
"""

from __future__ import annotations

import asyncio
import random
from decimal import Decimal

import httpx

GRAPHQL_ENDPOINT = "https://api.stake.com/graphql"
_JITTER = 0.20


def _jitter(base: float) -> float:
    return base * (1 + random.uniform(-_JITTER, _JITTER))


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class StakeAPIError(Exception):
    """Unexpected or error response from Stake."""

    def __init__(self, message: str, raw: object = None) -> None:
        super().__init__(message)
        self.raw = raw


class StakeAuthError(StakeAPIError):
    """Access token rejected or expired."""


# ---------------------------------------------------------------------------
# Queries / mutations
# ---------------------------------------------------------------------------

# CONFIRMED — Seuntjie900/DiceBot PD.cs "DiceBotGetBalance" query
_BALANCE_QUERY = """
query GambleAgentBalance {
  user {
    id
    balances {
      available {
        amount
        currency
      }
    }
    activeClientSeed { seed }
    activeServerSeed  { seedHash nonce }
  }
}
"""

# CONFIRMED — Seuntjie900/DiceBot PD.cs "DiceBotRotateSeed" mutation
# changeClientSeed(seed:) sets client seed; rotateServerSeed rotates server seed.
# Both run together so the pair is always consistent.
_ROTATE_SEED_MUTATION = """
mutation GambleAgentRotateSeed($seed: String!) {
  rotateServerSeed { seed seedHash nonce }
  changeClientSeed(seed: $seed) { seed }
}
"""

# UNVERIFIED — query shape guessed; must confirm via DevTools.
# Capture: log into stake.com, Network tab → filter "graphql", look for a request
# that returns per-currency USD prices, then update this query and _parse_rate().
_CURRENCY_RATE_QUERY = """
query GambleAgentCurrencyRates {
  info {
    currencies {
      name
      usdPrice
    }
  }
}
"""

# UNVERIFIED — mutation shape guessed; must confirm via DevTools.
# Capture: DevTools → Network → filter "graphql", move funds into vault, inspect request.
# Update the mutation string AND _parse_vault_deposit() if the response shape differs.
_VAULT_DEPOSIT_MUTATION = """
mutation GambleAgentVaultDeposit($currency: CurrencyEnum!, $amount: Float!) {
  vaultDeposit(currency: $currency, amount: $amount) {
    id
  }
}
"""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class StakeClient:
    """Async Stake.com GraphQL client.

    Usage:
        async with StakeClient(token) as client:
            balance = await client.get_balance("btc")
    """

    def __init__(self, access_token: str) -> None:
        self._http = httpx.AsyncClient(
            headers={
                "content-type": "application/json",
                "x-access-token": access_token,
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "StakeClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _gql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL request. Applies ±20% jitter before every call."""
        await asyncio.sleep(_jitter(0.15))

        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            resp = await self._http.post(GRAPHQL_ENDPOINT, json=payload)
        except httpx.RequestError as exc:
            raise StakeAPIError(f"network error: {exc}") from exc

        if resp.status_code == 401:
            raise StakeAuthError(
                "access token rejected (401) — re-paste your x-access-token from DevTools"
            )
        if resp.status_code == 403:
            raise StakeAuthError(
                "access forbidden (403) — token may be expired or Cloudflare is blocking"
            )
        if resp.status_code != 200:
            raise StakeAPIError(f"HTTP {resp.status_code}: {resp.text[:400]}")

        try:
            body = resp.json()
        except Exception as exc:
            raise StakeAPIError(f"non-JSON response: {resp.text[:400]}") from exc

        if "errors" in body:
            errors = body["errors"]
            msg = errors[0].get("message", str(errors[0])) if errors else "unknown GraphQL error"
            if any(kw in msg.lower() for kw in ("not authenticated", "unauthorized", "unauthenticated")):
                raise StakeAuthError(f"auth error in response: {msg}")
            raise StakeAPIError(f"GraphQL error: {msg}", raw=body)

        if "data" not in body:
            raise StakeAPIError(
                f"response missing 'data' key: {str(body)[:400]}", raw=body
            )

        return body["data"]  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_balance(self, currency: str) -> Decimal:
        """Return available (non-vault) balance for *currency* (e.g. 'btc').

        Query shape: CONFIRMED (DiceBot PD.cs).
        """
        data = await self._gql(_BALANCE_QUERY)
        available: list[dict] = (
            data.get("user", {}).get("balances", {}).get("available", [])
        )
        target = currency.lower()
        for entry in available:
            if entry.get("currency", "").lower() == target:
                return Decimal(str(entry["amount"]))
        raise StakeAPIError(
            f"currency {currency!r} not found in balance response "
            f"(got: {[e.get('currency') for e in available]})"
        )

    async def get_currency_rate(self, currency: str) -> Decimal:
        """Return USD price for 1 unit of *currency*.

        Query shape: UNVERIFIED — if this raises StakeAPIError with 'verify query',
        capture the real query from DevTools and update _CURRENCY_RATE_QUERY.
        See docs/stake-api-notes.md for instructions.
        """
        if currency.lower() == "usdt":
            return Decimal("1")  # USDT is pegged 1:1 to USD by definition

        data = await self._gql(_CURRENCY_RATE_QUERY)
        currencies: list[dict] = data.get("info", {}).get("currencies", [])
        target = currency.lower()
        for entry in currencies:
            if entry.get("name", "").lower() == target:
                raw = entry.get("usdPrice")
                if raw is None:
                    raise StakeAPIError(
                        f"'usdPrice' field missing for {currency!r} — "
                        "verify _CURRENCY_RATE_QUERY shape via DevTools"
                    )
                return Decimal(str(raw))
        raise StakeAPIError(
            f"currency {currency!r} not in rate response — "
            "verify _CURRENCY_RATE_QUERY shape via DevTools"
        )

    async def set_client_seed(self, seed: str) -> str:
        """Set the Stake client seed for provably fair. Returns confirmed new seed.

        Mutation shape: CONFIRMED (DiceBot PD.cs — changeClientSeed).
        Also rotates the server seed so the pair is always fresh together.
        """
        data = await self._gql(_ROTATE_SEED_MUTATION, {"seed": seed})
        new_seed: str | None = data.get("changeClientSeed", {}).get("seed")
        if new_seed is None:
            raise StakeAPIError(
                "set_client_seed: 'changeClientSeed.seed' missing in response",
                raw=data,
            )
        return new_seed

    async def vault_deposit(self, currency: str, amount: Decimal) -> dict:
        """Move *amount* of *currency* from betting balance to vault.

        Mutation shape: UNVERIFIED — if this raises, capture the real mutation from
        DevTools (transfer funds to vault while network tab is open) and update
        _VAULT_DEPOSIT_MUTATION. See docs/stake-api-notes.md.
        """
        data = await self._gql(
            _VAULT_DEPOSIT_MUTATION,
            {"currency": currency.lower(), "amount": float(amount)},
        )
        result = data.get("vaultDeposit")
        if result is None:
            raise StakeAPIError(
                "vault_deposit: 'vaultDeposit' key missing in response — "
                "mutation shape needs DevTools verification",
                raw=data,
            )
        return result  # type: ignore[return-value]
