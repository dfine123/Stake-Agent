"""Dry-run game adapter wrapper.

Wraps any GameAdapter and simulates place_bet() without calling the Stake API.
Win probability and payout multiplier are derived from the bet params so the
simulation is statistically representative of the real game.

Used by the orchestrator when --dry-run is passed on the CLI.
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from engine.stake.games.base import BetResult, GameAdapter


def _dice_prob_mult(params: dict) -> tuple[float, float]:
    """(win_probability, payout_multiplier) for a dice bet."""
    target = float(params.get("target", 50.5))
    condition = params.get("condition", "above")
    if condition == "above":
        win_prob = (100.0 - target) / 100.0
    else:
        win_prob = target / 100.0
    win_prob = max(0.001, min(0.999, win_prob))
    payout_mult = 0.99 / win_prob  # Stake's ~1% house edge on dice
    return win_prob, payout_mult


def _limbo_prob_mult(params: dict) -> tuple[float, float]:
    """(win_probability, payout_multiplier) for a limbo bet."""
    target = float(params.get("multiplier_target", 2.0))
    target = max(1.01, target)
    win_prob = 1.0 / target
    win_prob = max(0.001, min(0.999, win_prob))
    return win_prob, target


def _keno_prob_mult(params: dict) -> tuple[float, float]:
    """Rough (win_probability, avg_payout_multiplier) for a keno bet.

    Keno payouts depend on how many spots match; we use a conservative
    approximation. For 5 picks classic: ~30% chance of any payout, ~1.5× avg.
    These numbers give a realistic session P&L trajectory for dry runs.
    """
    return 0.30, 1.50


_GAME_PARAMS: dict[str, Any] = {
    "dice":  _dice_prob_mult,
    "limbo": _limbo_prob_mult,
    "keno":  _keno_prob_mult,
}


class DryRunAdapter(GameAdapter):
    """Simulation wrapper — same interface as a real adapter, no network calls."""

    def __init__(self, wrapped: GameAdapter) -> None:
        self._wrapped = wrapped

    @property  # type: ignore[override]
    def name(self) -> str:
        return self._wrapped.name

    async def place_bet(
        self,
        amount: Decimal,
        currency: str,
        params: dict,
    ) -> BetResult:
        fn = _GAME_PARAMS.get(self.name)
        if fn is None:
            # Unknown game — conservative coin flip at 2×
            win_prob, mult = 0.5, 2.0
        else:
            win_prob, mult = fn(params)

        won = random.random() < win_prob
        if won:
            payout = amount * Decimal(str(round(mult, 8)))
            return BetResult(
                won=True,
                payout=payout,
                multiplier=float(payout / amount),
                raw={"dry_run": True},
            )
        return BetResult(
            won=False,
            payout=Decimal("0"),
            multiplier=0.0,
            raw={"dry_run": True},
        )

    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        return self._wrapped.persona_params(persona, bankroll, vibes)
