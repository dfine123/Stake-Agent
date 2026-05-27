"""Keno game adapter.

Stake Originals — Keno.
GraphQL mutation: kenoBet. Confirmed working 2026-05-27.

Stake Keno:
  - 1–10 spots selected from 0–39
  - 4 risk levels: classic, low, medium, high
  - 10 numbers drawn per bet
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from engine.stake.client import StakeClient
from engine.stake.games.base import BetResult, GameAdapter, gen_identifier, parse_bet_response

KENO_RISKS = ("classic", "low", "medium", "high")

_KENO_BET_MUTATION = """
mutation KenoBet($amount: Float!, $currency: CurrencyEnum!, $numbers: [Int!]!, $risk: CasinoGameKenoRiskEnum!, $identifier: String!) {
  kenoBet(amount: $amount, currency: $currency, numbers: $numbers, risk: $risk, identifier: $identifier) {
    id
    active
    amount
    createdAt
    currency
    game
    payout
    payoutMultiplier
  }
}
"""


class KenoAdapter(GameAdapter):
    """Stake Originals Keno adapter.

    params expected by place_bet():
      selected: list[int]  — 1–10 picks, each 0–39, no duplicates
      risk:     str        — "classic" | "low" | "medium" | "high"
    """

    name = "keno"

    def __init__(self, client: StakeClient) -> None:
        self._client = client

    async def place_bet(
        self,
        amount: Decimal,
        currency: str,
        params: dict,
    ) -> BetResult:
        selected = params.get("selected")
        risk = params.get("risk", "")

        if not isinstance(selected, list) or not selected:
            raise ValueError("keno params 'selected' must be a non-empty list of ints")
        if len(selected) > 10:
            raise ValueError(f"keno 'selected' max 10 picks, got {len(selected)}")
        if any(not isinstance(n, int) or not (0 <= n <= 39) for n in selected):
            raise ValueError(f"keno 'selected' values must be ints in [0, 39], got {selected}")
        if len(set(selected)) != len(selected):
            raise ValueError(f"keno 'selected' contains duplicates: {selected}")
        if risk not in KENO_RISKS:
            raise ValueError(f"keno 'risk' must be one of {KENO_RISKS}, got {risk!r}")

        variables = {
            "amount": float(amount),
            "currency": currency.lower(),
            "numbers": list(selected),
            "risk": risk,
            "identifier": gen_identifier(),
        }

        data = await self._client._gql(_KENO_BET_MUTATION, variables)
        return parse_bet_response(data, "kenoBet", amount)

    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        return persona.keno_params(bankroll, vibes)
