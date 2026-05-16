"""Target and stop-loss tracking.

TargetTracker is stateless after construction — call check() on every balance
update to get an event name (matching the event bus constants) or None.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import NamedTuple

from engine.config import StopLoss


class TargetEvent(str, Enum):
    TOP_TARGET_HIT       = "top_target_hit"
    SECONDARY_TARGET_HIT = "secondary_target_hit"
    STOP_LOSS_HIT        = "stop_loss_hit"


class TargetTracker:
    """Tracks session targets against the running balance (in USD).

    Args:
        top_target_usd:       Session ends (win) when balance_usd >= this.
        secondary_target_usd: Vault trigger when balance_usd >= this.
        stop_loss:            StopLoss config (may be disabled).
        start_balance_usd:    Balance at session start (needed for pct modes).
    """

    def __init__(
        self,
        top_target_usd: Decimal,
        secondary_target_usd: Decimal,
        stop_loss: StopLoss,
        start_balance_usd: Decimal,
    ) -> None:
        self._top = top_target_usd
        self._secondary = secondary_target_usd
        self._stop_loss = stop_loss
        self._start = start_balance_usd
        self._secondary_ever_hit = False

        # Pre-compute the fixed stop floor so we don't repeat the switch each call.
        self._stop_floor: Decimal | None = self._compute_floor()

    def _compute_floor(self) -> Decimal | None:
        sl = self._stop_loss
        if not sl.enabled:
            return None
        if sl.mode == "fixed_floor":
            return sl.value
        if sl.mode == "pct_of_start":
            # value is the percentage to drop, e.g. 20 → floor is 80% of start
            return self._start * (1 - sl.value / 100)
        if sl.mode == "session_loss_cap":
            # value is the maximum loss in USD from start
            return self._start - sl.value
        return None  # unreachable with validated config

    def check(self, balance_usd: Decimal) -> TargetEvent | None:
        """Return the highest-priority event for this balance, or None.

        Priority order (highest first):
          1. TOP_TARGET_HIT   — session is over, stop betting
          2. STOP_LOSS_HIT    — session is over, cut losses
          3. SECONDARY_TARGET_HIT — vault excess, keep betting

        SECONDARY_TARGET_HIT fires only once; subsequent calls return None for
        it until the balance climbs to it again after a vault operation.  Since
        the orchestrator is responsible for resetting after vaulting, callers
        that want repeat secondary signals should call acknowledge_secondary()
        after processing the vault.
        """
        if balance_usd >= self._top:
            return TargetEvent.TOP_TARGET_HIT

        if self._stop_floor is not None and balance_usd <= self._stop_floor:
            return TargetEvent.STOP_LOSS_HIT

        if balance_usd >= self._secondary and not self._secondary_ever_hit:
            self._secondary_ever_hit = True
            return TargetEvent.SECONDARY_TARGET_HIT

        return None

    def acknowledge_secondary(self) -> None:
        """Reset the secondary-hit latch so it can fire again after vaulting."""
        self._secondary_ever_hit = False
