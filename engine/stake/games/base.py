"""GameAdapter base class, BetResult, and shared parsing helpers.

Every game adapter implements GameAdapter. The orchestrator only talks to
games through this interface.

Casino games go over REST: POST https://stake.com/_api/casino/{name}/{action}.
The base class owns the round-trip; subclasses declare three class attributes
(`name`, `action`, `response_key`) and one method (`_build_request`).
"""

from __future__ import annotations

import secrets
import string
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
    "sol":  Decimal("0.001"),
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


# Stake's UI generates 21-char nanoids (alphabet [A-Za-z0-9_-]) as the per-bet
# `identifier`. The identifier acts as Stake's idempotency key — resending the
# same id returns the same bet rather than double-charging. Match the format so
# our requests look identical to those Stake's own web client sends.
_NANOID_ALPHABET = string.ascii_letters + string.digits + "_-"
_NANOID_LEN = 21


def gen_identifier() -> str:
    return "".join(secrets.choice(_NANOID_ALPHABET) for _ in range(_NANOID_LEN))


def parse_bet_response(body: dict, response_key: str, amount: Decimal) -> BetResult:
    """Parse a Stake casino-bet response body into a BetResult.

    REST shape (observed for dice & keno):
        { "<response_key>": { "payout": float, "payoutMultiplier": float, ... } }

    Win/loss is determined by `payoutMultiplier > 0` when present (precise
    server-side value); falls back to `payout > 0` for legacy GraphQL responses
    that don't include the multiplier field.
    """
    bet = body.get(response_key, {})
    payout = Decimal(str(bet.get("payout", 0)))

    pm_raw = bet.get("payoutMultiplier")
    if pm_raw is not None:
        multiplier = float(pm_raw)
        won = multiplier > 0
    else:
        won = payout > Decimal("0")
        multiplier = float(payout / amount) if won else 0.0

    return BetResult(won=won, payout=payout, multiplier=multiplier, raw=bet)


class GameAdapter(ABC):
    """Base class for every Stake Originals adapter.

    Concrete REST adapters declare three class attributes and implement
    `_build_request` — the base class handles the actual HTTP round-trip and
    response parsing.

    Legacy GraphQL adapters and wrappers (DryRunAdapter, test fakes) may
    override `place_bet` directly; in that case `_build_request` is unused.
    """

    name: str           # game URL slug (e.g. "dice") — also the orchestrator's key
    action: str         # action URL slug (e.g. "roll", "bet")
    response_key: str   # top-level key in the JSON response body (e.g. "diceRoll")

    def _build_request(self, amount: Decimal, currency: str, params: dict) -> dict:
        """Validate `params` and return the JSON body for the POST.

        Must include `identifier` (idempotency key) — use `gen_identifier()`.
        Override in any subclass that uses the default `place_bet`.
        """
        raise NotImplementedError

    async def place_bet(
        self,
        amount: Decimal,
        currency: str,
        params: dict,
    ) -> BetResult:
        """Place one bet and return the settled result.

        Default flow: build request → POST /_api/casino/{name}/{action} → parse.
        Subclasses with non-standard transports (e.g. DryRunAdapter) override.
        """
        body = self._build_request(amount, currency, params)
        resp = await self._client.casino_bet(self.name, self.action, body)  # type: ignore[attr-defined]
        return parse_bet_response(resp, self.response_key, amount)

    @abstractmethod
    def persona_params(self, persona: Any, bankroll: Decimal, vibes: Any) -> dict:
        """Return the params dict this persona would use for this game.

        Receives the Persona and Vibes objects. Using Any here so adapters
        compile before those types exist.
        """

    def min_bet(self, currency: str) -> Decimal:
        return MIN_BETS.get(currency.lower(), Decimal("0.00000001"))

    def max_bet(self, currency: str) -> Decimal:
        return MAX_BETS.get(currency.lower(), Decimal("1"))
