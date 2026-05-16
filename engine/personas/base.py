"""Persona base protocol.

A persona is a stateless collection of strategy functions. All state
(recovery step, streaks, session balance) lives in the orchestrator and is
passed into persona methods — personas never mutate anything.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class BasePersona(ABC):
    name: str

    @abstractmethod
    def bet_size(
        self,
        bankroll: Decimal,
        recovery_state: Any,   # RecoveryState — imported by concrete class
        last_5: list[bool],    # True=win, False=loss; most-recent last; may be empty
    ) -> Decimal:
        """Return the intended bet amount. Caller clamps to game min/max."""

    @abstractmethod
    def game_weights(self, enabled_games: list[str], vibes: Any) -> dict[str, float]:
        """Return normalized weights for enabled_games. Must sum to 1.0."""

    @abstractmethod
    def bet_delay(self) -> float:
        """Return seconds to wait before the next bet (jitter included)."""

    @abstractmethod
    def dice_params(self, bankroll: Decimal, vibes: Any) -> dict: ...

    @abstractmethod
    def keno_params(self, bankroll: Decimal, vibes: Any) -> dict: ...

    @abstractmethod
    def limbo_params(self, bankroll: Decimal, vibes: Any) -> dict: ...
