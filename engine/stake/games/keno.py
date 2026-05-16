"""Keno game adapter.

Stake Originals — Keno.

Mutation shape: UNVERIFIED. Built from the diceRoll pattern (Seuntjie900/DiceBot).
On first live call, if Stake rejects the mutation, capture the real shape from
DevTools (Network → graphql, place a keno bet) and update _KENO_BET_MUTATION.

Stake Keno public info:
  - 1–10 spots selected from 1–40
  - 4 risk levels: Classic, Low, Medium, High
  - 10 numbers drawn per bet
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from engine.stake.client import StakeClient
from engine.stake.games.base import BetResult, GameAdapter, parse_bet_response

# Risk enum values — UNVERIFIED casing. Verify on first live call.
KENO_RISKS = ("classic", "low", "medium", "high")

# UNVERIFIED — best-guess shape, mirrors the confirmed diceRoll pattern.
_KENO_BET_MUTATION = """
mutation GambleAgentKenoBet(
  $amount: Float!
  $currency: CurrencyEnum!
  $identifier: String!
  $risk: CasinoGameKenoRiskEnum!
  $selected: [Float!]!
) {
  kenoBet(
    amount: $amount
    currency: $currency
    identifier: $identifier
    risk: $risk
    selected: $selected
  ) {
    id
    nonce
    currency
    amount
    payout
    state {
      ... on CasinoGameKeno {
        drawnNumbers
        selectedNumbers
        risk
      }
    }
    createdAt
    serverSeed { seedHash nonce }
    clientSeed { seed }
    user {
      balances { available { amount currency } }
    }
  }
}
"""


class KenoAdapter(GameAdapter):
    """Stake Originals Keno adapter.

    params expected by place_bet():
      selected: list[int]  — 1–10 picks, each 1–40, no duplicates
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
        if any(not isinstance(n, int) or not (1 <= n <= 40) for n in selected):
            raise ValueError(f"keno 'selected' values must be ints in [1, 40], got {selected}")
        if len(set(selected)) != len(selected):
            raise ValueError(f"keno 'selected' contains duplicates: {selected}")
        if risk not in KENO_RISKS:
            raise ValueError(f"keno 'risk' must be one of {KENO_RISKS}, got {risk!r}")

        variables = {
            "amount": float(amount),
            "currency": currency.lower(),
            "identifier": uuid.uuid4().hex,
            "risk": risk,
            "selected": [float(n) for n in selected],
        }

        data = await self._client._gql(_KENO_BET_MUTATION, variables)
        return parse_bet_response(data, "kenoBet", amount)

    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        # Steady: 5–6 picks classic difficulty, using lucky_numbers if in [1, 40].
        return persona.keno_params(bankroll, vibes)
