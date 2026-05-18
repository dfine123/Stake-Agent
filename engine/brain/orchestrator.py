"""Session orchestrator — the bet loop.

Wires together: StakeClient, persona, game adapters, TargetTracker,
EventBus, SqliteLogger, BetFeedUI. Owns all session state. Personas and
game adapters are stateless and called as pure functions on each iteration.

The loop:
  1. Refresh balance (in currency), convert to USD via rate.
  2. Check TargetTracker:
       - TOP_TARGET_HIT  → emit and halt.
       - STOP_LOSS_HIT   → emit and halt.
       - SECONDARY_HIT   → vault the excess, emit VAULT_EXECUTED, continue.
  3. Pick a game (game_selector).
  4. Compute bet size (bet_sizer, clamped to game min/max).
  5. Ask the game adapter for params for this persona/bankroll/vibes.
  6. place_bet — await the settled result.
  7. Emit BET_SETTLED (and the win-tier or LOST sub-event).
  8. Update recovery_state, last_5, recent_games.
  9. Sleep persona.bet_delay() (already jittered).
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from engine.brain.bet_sizer import compute_bet_size
from engine.brain.game_selector import pick_game
from engine.brain.targets import TargetEvent, TargetTracker
from engine.config import SessionConfig
from engine.events import bus as events
from engine.events.bet_feed import BetFeedUI
from engine.events.bus import EventBus
from engine.personas.base import BasePersona
from engine.personas.recovery import (
    MartingaleConfig,
    RecoveryState,
    next_recovery_state,
)
from engine.personas.steady import SteadyPersona
from engine.stake.client import StakeClient
from engine.stake.games.base import GameAdapter
from engine.stake.games.dice import DiceAdapter
from engine.stake.games.dry_run import DryRunAdapter
from engine.stake.games.keno import KenoAdapter
from engine.stake.games.limbo import LimboAdapter
from engine.storage.db import SqliteLogger
from engine.vibes.seed_generator import generate_seed

# Win-tier thresholds from CLAUDE.md.
_BIG_MULT = 50.0
_MEDIUM_MULT = 10.0
_SMALL_MULT = 2.0

# Martingale config matches steady persona's internal _MARTINGALE.
_MARTINGALE = MartingaleConfig(factor=Decimal("1.5"), max_steps=3)


def _build_persona(name: str) -> BasePersona:
    if name == "steady":
        return SteadyPersona()
    raise ValueError(f"unknown persona: {name}")


def _build_game_adapters(client: StakeClient) -> dict[str, GameAdapter]:
    """All Phase 1 adapters. Orchestrator picks the ones in enabled_games."""
    return {
        "dice":  DiceAdapter(client),
        "keno":  KenoAdapter(client),
        "limbo": LimboAdapter(client),
    }


class Orchestrator:
    """One-shot session runner. Construct once, await run() once."""

    def __init__(
        self,
        config: SessionConfig,
        db_path: Path | str | None = None,
        dry_run: bool = False,
        bus: EventBus | None = None,
        stop_event: asyncio.Event | None = None,
        pause_event: asyncio.Event | None = None,
        debug_hook: Callable | None = None,
    ) -> None:
        self._config = config
        self._db_path = db_path
        self._dry_run = dry_run
        self._external_bus = bus          # when set: IPC mode, no terminal UI
        self._stop_event = stop_event
        self._pause_event = pause_event
        self._debug_hook = debug_hook

        # State (lives only in the orchestrator — per house rule #8)
        self._recovery = RecoveryState(step=0)
        self._last_5: list[bool] = []
        self._recent_games: list[str] = []

    async def run(self) -> str:
        """Run the session loop until a halting target fires. Returns end_reason."""
        cfg = self._config.session
        persona = _build_persona(cfg.persona)

        # IPC mode: bus is pre-built and subscribers wired externally.
        # CLI mode: create bus here, attach terminal UI.
        if self._external_bus is not None:
            bus = self._external_bus
        else:
            bus = EventBus()
            feed = BetFeedUI()
            feed.subscribe(bus)

        logger = SqliteLogger(self._db_path)
        await logger.start()
        logger.subscribe(bus)

        async with StakeClient(
            self._config.credentials.stake_access_token,
            debug_hook=self._debug_hook,
        ) as client:
            adapters_all = _build_game_adapters(client)
            adapters = {g: adapters_all[g] for g in cfg.games_enabled}
            if self._dry_run:
                adapters = {g: DryRunAdapter(a) for g, a in adapters.items()}

            # Bake vibe → client seed before the first bet.
            if cfg.vibes.bake_into_seed:
                seed = generate_seed(cfg.vibes.text, cfg.vibes.lucky_numbers)
                await client.set_client_seed(seed)

            currency = cfg.currency
            rate = await client.get_currency_rate(currency)
            start_balance = await client.get_balance(currency)
            start_balance_usd = start_balance * rate

            tracker = TargetTracker(
                top_target_usd=cfg.top_target_usd,
                secondary_target_usd=cfg.secondary_target_usd,
                stop_loss=cfg.stop_loss,
                start_balance_usd=start_balance_usd,
            )

            await bus.emit(events.SESSION_START, {
                "currency": currency,
                "persona": persona.name,
                "top_target_usd": cfg.top_target_usd,
                "secondary_target_usd": cfg.secondary_target_usd,
                "start_balance": start_balance,
                "vibe_seed": generate_seed(cfg.vibes.text, cfg.vibes.lucky_numbers),
                "config": cfg.model_dump(mode="json"),
            })

            end_reason = "user_halt"
            end_balance = start_balance
            try:
                end_reason, end_balance = await self._loop(
                    bus, client, persona, adapters, tracker, currency, rate
                )
            finally:
                await bus.emit(events.SESSION_END, {
                    "end_reason": end_reason,
                    "end_balance": end_balance,
                    "net_pl": end_balance - start_balance,
                })
                await logger.stop()

        return end_reason

    async def _loop(
        self,
        bus: EventBus,
        client: StakeClient,
        persona: BasePersona,
        adapters: dict[str, GameAdapter],
        tracker: TargetTracker,
        currency: str,
        rate: Decimal,
    ) -> tuple[str, Decimal]:
        cfg = self._config.session
        enabled = list(adapters.keys())

        while True:
            # Halt if an external stop signal has been set (IPC stop/panic).
            if self._stop_event and self._stop_event.is_set():
                return "user_halt", await client.get_balance(currency)

            # Block here if paused — resumes when pause_event is set again.
            if self._pause_event:
                await self._pause_event.wait()

            balance = await client.get_balance(currency)
            balance_usd = balance * rate

            event = tracker.check(balance_usd)
            if event is TargetEvent.TOP_TARGET_HIT:
                await bus.emit(events.TOP_TARGET_HIT, {"balance": balance, "balance_usd": balance_usd})
                return "top_target_hit", balance
            if event is TargetEvent.STOP_LOSS_HIT:
                await bus.emit(events.STOP_LOSS_HIT, {"balance": balance, "balance_usd": balance_usd})
                return "stop_loss_hit", balance
            if event is TargetEvent.SECONDARY_TARGET_HIT:
                await bus.emit(events.SECONDARY_TARGET_HIT, {"balance": balance, "balance_usd": balance_usd})
                # Vault the USD excess, converted to currency.
                excess_usd = balance_usd - cfg.secondary_target_usd
                vault_amount = excess_usd / rate
                if vault_amount > Decimal("0"):
                    await client.vault_deposit(currency, vault_amount)
                    await bus.emit(events.VAULT_EXECUTED, {
                        "currency": currency, "amount": vault_amount,
                    })
                    # Refresh balance so the bet below sizes off the vaulted amount.
                    balance = await client.get_balance(currency)
                tracker.acknowledge_secondary()
                # Fall through and place a bet this iteration — re-entering the
                # loop top with balance ≈ secondary would re-fire the event
                # forever (excess is 0).

            # ---- Pick game ----
            game = pick_game(persona, enabled, cfg.vibes, self._recent_games)
            adapter = adapters[game]

            # ---- Size the bet ----
            amount = compute_bet_size(
                persona,
                bankroll=balance,
                recovery_state=self._recovery,
                last_5=self._last_5,
                min_bet=adapter.min_bet(currency),
                max_bet=adapter.max_bet(currency),
            )

            params = adapter.persona_params(persona, balance, cfg.vibes)

            # ---- Place bet ----
            await bus.emit(events.BET_PLACED, {
                "game": game, "amount": amount, "currency": currency, "params": params,
            })
            result = await adapter.place_bet(amount, currency, params)

            await bus.emit(events.BET_SETTLED, {
                "game": game,
                "amount": amount,
                "currency": currency,
                "params": params,
                "result": {
                    "won": result.won,
                    "payout": result.payout,
                    "multiplier": result.multiplier,
                    "raw": result.raw,
                },
            })
            await self._emit_outcome_event(bus, result.won, result.multiplier)

            # ---- Update state ----
            self._recovery = next_recovery_state(self._recovery, result.won, _MARTINGALE)
            self._last_5.append(result.won)
            if len(self._last_5) > 5:
                self._last_5 = self._last_5[-5:]
            self._recent_games.append(game)
            if len(self._recent_games) > 5:
                self._recent_games = self._recent_games[-5:]

            await asyncio.sleep(persona.bet_delay())

    @staticmethod
    async def _emit_outcome_event(bus: EventBus, won: bool, multiplier: float) -> None:
        if not won:
            await bus.emit(events.LOST, {"multiplier": multiplier})
            return
        if multiplier >= _BIG_MULT:
            await bus.emit(events.WON_BIG, {"multiplier": multiplier})
        elif multiplier >= _MEDIUM_MULT:
            await bus.emit(events.WON_MEDIUM, {"multiplier": multiplier})
        elif multiplier >= _SMALL_MULT:
            await bus.emit(events.WON_SMALL, {"multiplier": multiplier})
        else:
            # Won, but below 2× threshold — still a win, no sub-event tier.
            pass
