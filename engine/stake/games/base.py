"""GameAdapter base class, BetResult, and shared parsing helpers.

Every game adapter implements GameAdapter. The orchestrator only talks to
games through this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class BetResult:
    won: bool
    payout: Decimal   # 0 on loss; gross payout (includes stake) on win
    multiplier: float # payout / amount; 0 on loss
    raw: dict         # full Stake API response for this bet


# Per-currency min/max bets, shared by all adapters.
# Stake doesn't publish these; values are conservative estimates.
# Verify on first live call — Stake will return an error if amount is out of range.
MIN_BETS: dict[str, Decimal] = {
    "btc":  Decimal("0.00000001"),
    "eth":  Decimal("0.00000001"),
    "sol":  Decimal("0.0000001"),
    "usdt": Decimal("0.001"),
    "ltc":  Decimal("0.00000001"),
    "doge": Decimal("0.00001"),
    "trx":  Decimal("0.001"),
}

MAX_BETS: dict[str, Decimal] = {
    "btc":  Decimal("0.5"),
    "eth":  Decimal("10"),
    "sol":  Decimal("500"),
    "usdt": Decimal("100000"),
    "ltc":  Decimal("100"),
    "doge": Decimal("1000000"),
    "trx":  Decimal("1000000"),
}


def parse_bet_response(data: dict, bet_field: str, amount: Decimal) -> BetResult:
    """Parse a Stake bet mutation response into a BetResult.

    All Stake casino bet mutations return the same envelope: a top-level field
    named after the bet (diceRoll, kenoBet, limboBet, ...) containing payout,
    state, seeds, balances. Won is determined by payout > 0; multiplier is
    payout / amount on a win, 0 on a loss.
    """
    bet = data.get(bet_field, {})
    payout = Decimal(str(bet.get("payout", 0)))
    won = payout > Decimal("0")
    multiplier = float(payout / amount) if won else 0.0
    return BetResult(won=won, payout=payout, multiplier=multiplier, raw=bet)


class GameAdapter(ABC):
    name: str

    @abstractmethod
    async def place_bet(
        self,
        amount: Decimal,
        currency: str,
        params: dict,
    ) -> BetResult:
        """Place one bet and return the settled result.

        `params` is game-specific. The adapter validates the params it expects
        and raises ValueError for anything missing or out of range.
        """

    @abstractmethod
    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        """Return the params dict this persona would use for this game.

        Receives the Persona and Vibes objects (both defined in Task 1.7).
        Using Any here so adapters compile before those types exist.
        """

    def min_bet(self, currency: str) -> Decimal:
        return MIN_BETS.get(currency.lower(), Decimal("0.00000001"))

    def max_bet(self, currency: str) -> Decimal:
        return MAX_BETS.get(currency.lower(), Decimal("1"))
