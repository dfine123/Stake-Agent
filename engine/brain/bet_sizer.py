"""Bet sizing — pure function wrapping the persona's bet_size logic.

Separating this from the orchestrator keeps it unit-testable without spinning
up a full session loop.
"""

from __future__ import annotations

from decimal import Decimal

from engine.personas.base import BasePersona
from engine.personas.recovery import RecoveryState


def compute_bet_size(
    persona: BasePersona,
    bankroll: Decimal,
    recovery_state: RecoveryState,
    last_5: list[bool],
    min_bet: Decimal,
    max_bet: Decimal,
) -> Decimal:
    """Return the clamped bet amount for the next wager.

    Delegates sizing logic to the persona (which applies its own percentage
    and Martingale), then clamps the result to the game's [min_bet, max_bet]
    range. Money arithmetic stays in Decimal throughout.

    Args:
        persona:        Active persona instance.
        bankroll:       Current balance in the wagering currency.
        recovery_state: Current Martingale step (0 = base bet).
        last_5:         Boolean win/loss for the last ≤5 bets (most recent last).
        min_bet:        Game minimum for the active currency.
        max_bet:        Game maximum for the active currency.

    Returns:
        Clamped Decimal bet amount. Always >= min_bet and <= max_bet.
    """
    raw = persona.bet_size(bankroll, recovery_state, last_5)
    return max(min_bet, min(raw, max_bet))
