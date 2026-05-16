"""GameAdapter base class and BetResult type.

Every game adapter implements this interface. The orchestrator only talks to
games through GameAdapter — nothing else calls adapters directly.
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

        `params` is game-specific — roll target, pick count, mine count, etc.
        The adapter validates the params it expects and raises ValueError for
        anything missing or out of range.
        """

    @abstractmethod
    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        """Return the params dict this persona would use for this game.

        Receives the Persona and Vibes objects (both defined in Task 1.7).
        Using Any here so the adapter compiles before those types exist.
        """

    @abstractmethod
    def min_bet(self, currency: str) -> Decimal: ...

    @abstractmethod
    def max_bet(self, currency: str) -> Decimal: ...
