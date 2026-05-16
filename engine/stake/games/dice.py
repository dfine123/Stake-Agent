"""Dice game adapter.

Stake Originals — Dice.

Confirmed mutation shape: Seuntjie900/DiceBot PD.cs + Stake.cs
  mutation field:    diceRoll
  state inline type: CasinoGameDice
  condition enum:    CasinoGameDiceConditionEnum  (values: "above" | "below")
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from engine.stake.client import StakeClient
from engine.stake.games.base import BetResult, GameAdapter, parse_bet_response

CONDITION_ABOVE = "above"
CONDITION_BELOW = "below"

# CONFIRMED mutation — Seuntjie900/DiceBot PD.cs DiceBotDiceBet
_DICE_BET_MUTATION = """
mutation GambleAgentDiceBet(
  $amount: Float!
  $target: Float!
  $condition: CasinoGameDiceConditionEnum!
  $currency: CurrencyEnum!
  $identifier: String!
) {
  diceRoll(
    amount: $amount
    target: $target
    condition: $condition
    currency: $currency
    identifier: $identifier
  ) {
    id
    nonce
    currency
    amount
    payout
    state {
      ... on CasinoGameDice {
        result
        target
        condition
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


class DiceAdapter(GameAdapter):
    """Stake Originals Dice adapter.

    params expected by place_bet():
      target:    float — roll target, 0.01–99.99 (e.g. 50.5)
      condition: str   — "above" | "below"
    """

    name = "dice"

    def __init__(self, client: StakeClient) -> None:
        self._client = client

    async def place_bet(
        self,
        amount: Decimal,
        currency: str,
        params: dict,
    ) -> BetResult:
        target = params.get("target")
        condition = params.get("condition", "")

        if target is None:
            raise ValueError("dice params missing 'target'")
        if condition not in (CONDITION_ABOVE, CONDITION_BELOW):
            raise ValueError(f"dice 'condition' must be 'above' or 'below', got {condition!r}")
        if not (0.01 <= float(target) <= 99.99):
            raise ValueError(f"dice 'target' must be in [0.01, 99.99], got {target}")

        variables = {
            "amount": float(amount),
            "target": float(target),
            "condition": condition,
            "currency": currency.lower(),
            "identifier": uuid.uuid4().hex,
        }

        data = await self._client._gql(_DICE_BET_MUTATION, variables)
        return parse_bet_response(data, "diceRoll", amount)

    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        # Steady: rolls above 50.5 (≈2x payout, ~49.5% win chance).
        return persona.dice_params(bankroll, vibes)
