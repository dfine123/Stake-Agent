"""Steady persona — Phase 1 only persona.

Conservative, consistent play style:
  - Bet 0.75–1.25% of bankroll (base), scaled by recent results
  - 1.5× Martingale on loss, max 3 steps, reset on any win
  - Dice 40% / Keno 30% / Limbo 30% with vibe nudges
  - 2–5 s between bets with ±20% jitter
"""

from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from engine.personas.base import BasePersona
from engine.personas.recovery import MartingaleConfig, RecoveryState, apply_martingale

# Default picks spread across 0–39 when vibes supply no valid keno numbers.
_DEFAULT_KENO_PICKS: list[int] = [7, 14, 21, 28, 35]

# Base game weights before vibe influence.
_BASE_WEIGHTS: dict[str, float] = {"dice": 0.40, "keno": 0.30, "limbo": 0.30}

_MARTINGALE = MartingaleConfig(factor=Decimal("1.5"), max_steps=3)

_JITTER = 0.20


class SteadyPersona(BasePersona):
    """Methodical, middle-of-the-road betting persona.

    Deterministic on every pure method — same inputs always produce the same
    output. bet_delay() is the one exception (intentionally random for jitter).
    """

    name = "steady"

    # ------------------------------------------------------------------
    # Bet sizing
    # ------------------------------------------------------------------

    def bet_size(
        self,
        bankroll: Decimal,
        recovery_state: RecoveryState,
        last_5: list[bool],
    ) -> Decimal:
        """Return intended bet amount before game min/max clamping.

        Base percentage is 0.75–1.25% of bankroll depending on recent results:
          3+ wins in last 5 → 1.25% (mild positive momentum)
          3+ losses in last 5 → 0.75% (pull back slightly)
          otherwise          → 1.00% (steady state)

        Martingale is then applied on top of the base.
        """
        wins = sum(1 for r in last_5 if r)
        losses = len(last_5) - wins

        if wins >= 3:
            pct = Decimal("0.0125")
        elif losses >= 3:
            pct = Decimal("0.0075")
        else:
            pct = Decimal("0.0100")

        base = bankroll * pct
        return apply_martingale(base, recovery_state, _MARTINGALE)

    # ------------------------------------------------------------------
    # Game selection weights
    # ------------------------------------------------------------------

    def game_weights(self, enabled_games: list[str], vibes: Any) -> dict[str, float]:
        """Return normalized weights for the given enabled_games.

        Vibe lucky_numbers nudge weights when influence_game_choice is set:
          any number in 1–10  → +0.05 to dice  (low numbers = precise target)
          any number in 11–30 → +0.05 to keno  (midrange = spread picks)
          any number in 31–40 → +0.05 to limbo (high numbers = high multiplier)

        After nudging, only enabled games are kept and weights are renormalised
        to sum exactly 1.0. Unknown game names in enabled_games get 0 base
        weight but will receive an equal share after normalisation if every
        base weight would otherwise be 0 (fallback: equal distribution).
        """
        weights = dict(_BASE_WEIGHTS)

        if vibes and getattr(vibes, "influence_game_choice", False):
            nums = getattr(vibes, "lucky_numbers", []) or []
            if any(1 <= n <= 10 for n in nums):
                weights["dice"] = weights.get("dice", 0.0) + 0.05
            if any(11 <= n <= 30 for n in nums):
                weights["keno"] = weights.get("keno", 0.0) + 0.05
            if any(31 <= n <= 40 for n in nums):
                weights["limbo"] = weights.get("limbo", 0.0) + 0.05

        active = {g: weights.get(g, 0.0) for g in enabled_games}
        total = sum(active.values())

        if total == 0:
            equal = 1.0 / len(enabled_games)
            return {g: equal for g in enabled_games}

        return {g: v / total for g, v in active.items()}

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    def bet_delay(self) -> float:
        """Return seconds to sleep before the next bet (jitter included).

        Base is uniform over [2, 5]; then ±20% jitter is applied.
        This is intentionally non-deterministic.
        """
        base = random.uniform(2.0, 5.0)
        return base * (1 + random.uniform(-_JITTER, _JITTER))

    # ------------------------------------------------------------------
    # Per-game params
    # ------------------------------------------------------------------

    def dice_params(self, bankroll: Decimal, vibes: Any) -> dict:
        """Steady dice: always rolls above 50.5 (≈2× payout, ~49.5% win)."""
        return {"target": 50.5, "condition": "above"}

    def keno_params(self, bankroll: Decimal, vibes: Any) -> dict:
        """Steady keno: 5 picks, classic risk.

        Picks come from vibes.lucky_numbers filtered to [1, 40]. If fewer than
        5 valid numbers are present, defaults fill the remainder.
        """
        picks = _select_keno_picks(vibes)
        return {"selected": picks, "risk": "classic"}

    def limbo_params(self, bankroll: Decimal, vibes: Any) -> dict:
        """Steady limbo: 2× target multiplier — safe lower end of 2–3× range."""
        return {"multiplier_target": 2.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _select_keno_picks(vibes: Any) -> list[int]:
    """Return exactly 5 unique keno picks in [0, 39].

    Priority: valid lucky_numbers from vibes → filled with defaults.
    Result is deterministic for a given set of lucky_numbers.
    """
    lucky: list[int] = getattr(vibes, "lucky_numbers", []) or []
    valid = [n for n in lucky if isinstance(n, int) and 0 <= n <= 39]

    # Deduplicate while preserving order
    seen: set[int] = set()
    unique: list[int] = []
    for n in valid:
        if n not in seen:
            seen.add(n)
            unique.append(n)

    if len(unique) >= 5:
        return unique[:5]

    # Pad with defaults not already chosen
    for d in _DEFAULT_KENO_PICKS:
        if len(unique) >= 5:
            break
        if d not in seen:
            unique.append(d)
            seen.add(d)

    return unique
