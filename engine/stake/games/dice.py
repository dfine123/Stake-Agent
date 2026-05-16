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
from engine.stake.games.base import BetResult, GameAdapter

# Condition enum values — casing confirmed from DiceBot Stake.cs EnumName field.
# Verify on first live call; update if Stake rejects.
CONDITION_ABOVE = "above"
CONDITION_BELOW = "below"

# Minimum/maximum bets per currency.
# Stake doesn't publish these; values are conservative estimates.
# Verify on first live call — Stake will return an error if amount is out of range.
_MIN_BETS: dict[str, Decimal] = {
    "btc":  Decimal("0.00000001"),
    "eth":  Decimal("0.00000001"),
    "sol":  Decimal("0.0000001"),
    "usdt": Decimal("0.001"),
    "ltc":  Decimal("0.00000001"),
    "doge": Decimal("0.00001"),
    "trx":  Decimal("0.001"),
}

_MAX_BETS: dict[str, Decimal] = {
    "btc":  Decimal("0.5"),
    "eth":  Decimal("10"),
    "sol":  Decimal("500"),
    "usdt": Decimal("100000"),
    "ltc":  Decimal("100"),
    "doge": Decimal("1000000"),
    "trx":  Decimal("1000000"),
}

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
      balances {
        available { amount currency }
      }
    }
  }
}
"""


class DiceAdapter(GameAdapter):
    """Stake Originals Dice adapter.

    params expected by place_bet():
      target:    float  — roll target, 0.01–99.99  (e.g. 50.5)
      condition: str    — "above" | "below"
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
        target: float = params.get("target")
        condition: str = params.get("condition", "")

        if target is None:
            raise ValueError("dice params missing 'target'")
        if condition not in (CONDITION_ABOVE, CONDITION_BELOW):
            raise ValueError(f"dice 'condition' must be 'above' or 'below', got {condition!r}")
        if not (0.01 <= target <= 99.99):
            raise ValueError(f"dice 'target' must be in [0.01, 99.99], got {target}")

        variables = {
            "amount": float(amount),
            "target": float(target),
            "condition": condition,
            "currency": currency.lower(),
            "identifier": uuid.uuid4().hex,
        }

        data = await self._client._gql(_DICE_BET_MUTATION, variables)
        return _parse_result(data, amount)

    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        # Delegated to the persona in Task 1.7.
        # Steady: always rolls above 50.5 (≈2x payout, ~49.5% win chance).
        return persona.dice_params(bankroll, vibes)

    def min_bet(self, currency: str) -> Decimal:
        return _MIN_BETS.get(currency.lower(), Decimal("0.00000001"))

    def max_bet(self, currency: str) -> Decimal:
        return _MAX_BETS.get(currency.lower(), Decimal("1"))


def _parse_result(data: dict, amount: Decimal) -> BetResult:
    roll = data.get("diceRoll", {})
    payout = Decimal(str(roll.get("payout", 0)))
    won = payout > Decimal("0")
    multiplier = float(payout / amount) if won else 0.0
    return BetResult(won=won, payout=payout, multiplier=multiplier, raw=roll)
