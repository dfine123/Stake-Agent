"""Martingale recovery logic.

Pure functions. The orchestrator owns a RecoveryState instance and passes it
into persona.bet_size() — neither the persona nor the game adapter mutates it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class MartingaleConfig:
    factor: Decimal = Decimal("1.5")
    max_steps: int = 3


@dataclass
class RecoveryState:
    step: int = 0  # 0 = not in recovery; 1..max_steps = in recovery


def next_recovery_state(
    state: RecoveryState,
    won: bool,
    config: MartingaleConfig,
) -> RecoveryState:
    """Return the new RecoveryState after a bet result.

    Any win resets to step 0. Any loss advances step up to max_steps.
    """
    if won:
        return RecoveryState(step=0)
    return RecoveryState(step=min(state.step + 1, config.max_steps))


def apply_martingale(
    base_bet: Decimal,
    state: RecoveryState,
    config: MartingaleConfig,
) -> Decimal:
    """Multiply base_bet by factor^step. Returns base_bet unchanged at step 0."""
    if state.step == 0:
        return base_bet
    return base_bet * (config.factor ** state.step)
