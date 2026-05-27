"""Dice game adapter.

Stake Originals — Dice.
GraphQL mutation: diceRoll. Confirmed working 2026-05-27.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from engine.stake.client import StakeClient
from engine.stake.games.base import BetResult, GameAdapter, gen_identifier, parse_bet_response

CONDITION_ABOVE = "above"
CONDITION_BELOW = "below"

_DICE_ROLL_MUTATION = """
mutation DiceRoll($amount: Float!, $currency: CurrencyEnum!, $target: Float!, $condition: CasinoGameDiceConditionEnum!, $identifier: String!) {
  diceRoll(amount: $amount, currency: $currency, target: $target, condition: $condition, identifier: $identifier) {
    id
    active
    amount
    createdAt
    currency
    game
    payout
    payoutMultiplier
    state {
      ... on CasinoGameDice {
        result
        target
        condition
      }
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
            "currency": currency.lower(),
            "target": float(target),
            "condition": condition,
            "identifier": gen_identifier(),
        }

        data = await self._client._gql(_DICE_ROLL_MUTATION, variables)
        return parse_bet_response(data, "diceRoll", amount)

    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        return persona.dice_params(bankroll, vibes)
