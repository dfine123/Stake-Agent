"""Event bus.

All side effects of the bet loop route through here. The bet loop emits;
subscribers consume. Designed so subscribers can be sync or async functions.

Phase 1 subscribers: BetFeedUI, SqliteLogger.
Phase 2 adds: commentary_engine, notification_system.
Phase 3 adds: avatar_controller (no engine changes needed).
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

# ---------------------------------------------------------------------------
# Event names — string constants to avoid typos.
# Phase 1 emits this subset; Phase 2 will add heater/cold/recovery/tilt events.
# ---------------------------------------------------------------------------

SESSION_START         = "session_start"
SESSION_END           = "session_end"
BET_PLACED            = "bet_placed"
BET_SETTLED           = "bet_settled"
WON_SMALL             = "won_small"          # multiplier in [2x, 10x)
WON_MEDIUM            = "won_medium"         # multiplier in [10x, 50x)
WON_BIG               = "won_big"            # multiplier >= 50x
LOST                  = "lost"
VAULT_EXECUTED        = "vault_executed"
SECONDARY_TARGET_HIT  = "secondary_target_hit"
TOP_TARGET_HIT        = "top_target_hit"
STOP_LOSS_HIT         = "stop_loss_hit"


Handler = Callable[[dict], Any | Awaitable[Any]]


class EventBus:
    """In-process pub/sub. Subscribers fire in registration order.

    Exceptions from subscribers propagate. The orchestrator is expected to
    treat a subscriber crash (notably the SQLite logger) as a session-halting
    event — losing audit trail is worse than continuing to bet.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = {}

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._subscribers.setdefault(event_name, []).append(handler)

    async def emit(self, event_name: str, payload: dict | None = None) -> None:
        payload = payload or {}
        for handler in self._subscribers.get(event_name, []):
            result = handler(payload)
            if inspect.isawaitable(result):
                await result
