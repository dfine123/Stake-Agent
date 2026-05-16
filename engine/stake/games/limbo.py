"""Limbo game adapter.

Stake Originals — Limbo.

Mutation shape: UNVERIFIED. Built from the diceRoll pattern (Seuntjie900/DiceBot).
On first live call, if Stake rejects the mutation, capture the real shape from
DevTools (Network → graphql, place a limbo bet) and update _LIMBO_BET_MUTATION.

Stake Limbo public info:
  - Pick a target multiplier (>= 1.01)
  - RNG draws a multiplier; you win at the target multiplier if RNG >= target
  - Max win 1,000,000x
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from engine.stake.client import StakeClient
from engine.stake.games.base import BetResult, GameAdapter, parse_bet_response

LIMBO_MIN_MULTIPLIER = 1.01
LIMBO_MAX_MULTIPLIER = 1_000_000.0

# UNVERIFIED — best-guess shape, mirrors the confirmed diceRoll pattern.
# The variable name `multiplierTarget` is the most likely field name on Stake's
# schema; could also be `target`. Verify and adjust on first live call.
_LIMBO_BET_MUTATION = """
mutation GambleAgentLimboBet(
  $amount: Float!
  $currency: CurrencyEnum!
  $identifier: String!
  $multiplierTarget: Float!
) {
  limboBet(
    amount: $amount
    currency: $currency
    identifier: $identifier
    multiplierTarget: $multiplierTarget
  ) {
    id
    nonce
    currency
    amount
    payout
    state {
      ... on CasinoGameLimbo {
        result
        multiplierTarget
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


class LimboAdapter(GameAdapter):
    """Stake Originals Limbo adapter.

    params expected by place_bet():
      multiplier_target: float — target multiplier in [1.01, 1_000_000]
    """

    name = "limbo"

    def __init__(self, client: StakeClient) -> None:
        self._client = client

    async def place_bet(
        self,
        amount: Decimal,
        currency: str,
        params: dict,
    ) -> BetResult:
        target = params.get("multiplier_target")

        if target is None:
            raise ValueError("limbo params missing 'multiplier_target'")
        target_f = float(target)
        if not (LIMBO_MIN_MULTIPLIER <= target_f <= LIMBO_MAX_MULTIPLIER):
            raise ValueError(
                f"limbo 'multiplier_target' must be in "
                f"[{LIMBO_MIN_MULTIPLIER}, {LIMBO_MAX_MULTIPLIER}], got {target_f}"
            )

        variables = {
            "amount": float(amount),
            "currency": currency.lower(),
            "identifier": uuid.uuid4().hex,
            "multiplierTarget": target_f,
        }

        data = await self._client._gql(_LIMBO_BET_MUTATION, variables)
        return parse_bet_response(data, "limboBet", amount)

    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        # Steady: 2x–3x target multiplier.
        return persona.limbo_params(bankroll, vibes)
