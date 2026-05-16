"""Orchestrator tests — run the bet loop against fake adapters / Stake client.

These tests do NOT hit the network. They patch StakeClient and the game
adapters with in-process fakes that return scripted balances and bet results.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.brain import orchestrator as orch_mod
from engine.brain.orchestrator import Orchestrator
from engine.config import (
    Credentials,
    Session,
    SessionConfig,
    StopLoss,
    Vibes,
)
from engine.stake.games.base import BetResult, GameAdapter


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeStakeClient:
    """In-memory Stake replacement. Balance is mutated by fake adapters."""

    def __init__(self, *_a, **_kw) -> None:
        # Public state the test can read/mutate.
        self.balance = Decimal("0.001")
        self.rate = Decimal("100000")  # 1 BTC = $100,000
        self.seed_set: str | None = None
        self.vault_calls: list[tuple[str, Decimal]] = []

    async def __aenter__(self) -> "FakeStakeClient":
        return self

    async def __aexit__(self, *_a) -> None:
        return None

    async def close(self) -> None:
        return None

    async def get_balance(self, currency: str) -> Decimal:
        return self.balance

    async def get_currency_rate(self, currency: str) -> Decimal:
        return self.rate

    async def set_client_seed(self, seed: str) -> str:
        self.seed_set = seed
        return seed

    async def vault_deposit(self, currency: str, amount: Decimal) -> dict:
        self.vault_calls.append((currency, amount))
        self.balance -= amount
        return {"id": f"vault-{len(self.vault_calls)}"}


class ScriptedDiceAdapter(GameAdapter):
    """Dice adapter whose place_bet returns a scripted sequence of results.

    Each result is a (won: bool, multiplier: float) pair. Balance on the
    fake client is mutated accordingly (subtract amount on loss, add
    (payout - amount) on win).
    """

    name = "dice"

    def __init__(self, client: FakeStakeClient, script: list[tuple[bool, float]]) -> None:
        self._client = client
        self._script = list(script)
        self.calls: list[tuple[Decimal, str, dict]] = []

    async def place_bet(self, amount: Decimal, currency: str, params: dict) -> BetResult:
        self.calls.append((amount, currency, dict(params)))
        won, mult = self._script.pop(0)
        if won:
            payout = amount * Decimal(str(mult))
            self._client.balance += (payout - amount)
            return BetResult(won=True, payout=payout, multiplier=mult, raw={"id": f"b{len(self.calls)}"})
        self._client.balance -= amount
        return BetResult(won=False, payout=Decimal("0"), multiplier=0.0, raw={"id": f"b{len(self.calls)}"})

    def persona_params(self, persona, bankroll, vibes) -> dict:
        return persona.dice_params(bankroll, vibes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(
    *,
    top: str = "200",
    secondary: str = "150",
    stop_loss: StopLoss | None = None,
    bake_seed: bool = True,
) -> SessionConfig:
    return SessionConfig(
        credentials=Credentials(stake_access_token="test-token"),
        session=Session(
            currency="btc",
            top_target_usd=Decimal(top),
            secondary_target_usd=Decimal(secondary),
            stop_loss=stop_loss or StopLoss(enabled=False),
            persona="steady",
            games_enabled=["dice"],
            vibes=Vibes(text="t", lucky_numbers=[1, 2], bake_into_seed=bake_seed,
                        influence_game_choice=False),
        ),
    )


def _patch_runtime(monkeypatch, fake_client: FakeStakeClient, dice: ScriptedDiceAdapter):
    """Patch the orchestrator's runtime deps to use our fakes."""
    monkeypatch.setattr(orch_mod, "StakeClient", lambda token: fake_client)
    monkeypatch.setattr(
        orch_mod, "_build_game_adapters",
        lambda client: {"dice": dice, "keno": dice, "limbo": dice},
    )
    # Skip sleeps so tests finish instantly.
    async def _no_sleep(_s):
        return None
    monkeypatch.setattr(orch_mod.asyncio, "sleep", _no_sleep)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_top_target_halts_loop(monkeypatch, tmp_path):
    """Big multiplier win pushes balance above top target → session ends."""
    client = FakeStakeClient()
    client.balance = Decimal("0.001")          # = $100 USD
    # One huge winning bet → balance vaults past $200 USD top target.
    dice = ScriptedDiceAdapter(client, [(True, 200.0)])
    _patch_runtime(monkeypatch, client, dice)

    cfg = _config(top="200", secondary="150")
    end_reason = await Orchestrator(cfg, db_path=tmp_path / "t.db").run()

    assert end_reason == "top_target_hit"
    assert len(dice.calls) == 1
    assert client.seed_set is not None  # vibe seed was baked


@pytest.mark.asyncio
async def test_stop_loss_halts_loop(monkeypatch, tmp_path):
    """A run of losses drops balance below stop floor → session ends."""
    client = FakeStakeClient()
    client.balance = Decimal("0.001")          # = $100 USD
    # All losses. Floor = $90 USD = 0.0009 BTC. With ~1% bets we'll hit it.
    dice = ScriptedDiceAdapter(client, [(False, 0.0)] * 50)
    _patch_runtime(monkeypatch, client, dice)

    sl = StopLoss(enabled=True, mode="fixed_floor", value=Decimal("90"))
    cfg = _config(top="500", secondary="400", stop_loss=sl)
    end_reason = await Orchestrator(cfg, db_path=tmp_path / "t.db").run()

    assert end_reason == "stop_loss_hit"
    assert len(dice.calls) > 0


@pytest.mark.asyncio
async def test_secondary_triggers_vault(monkeypatch, tmp_path):
    """Crossing secondary triggers vault_deposit; loop continues after."""
    client = FakeStakeClient()
    client.balance = Decimal("0.0016")         # = $160 USD, already above secondary $150

    # Sequence: first iteration triggers vault (drops balance to secondary
    # threshold), then a loss brings it down, then a huge win clears top.
    dice = ScriptedDiceAdapter(client, [(False, 0.0), (True, 200.0)])
    _patch_runtime(monkeypatch, client, dice)

    cfg = _config(top="300", secondary="150")
    end_reason = await Orchestrator(cfg, db_path=tmp_path / "t.db").run()

    assert end_reason == "top_target_hit"
    assert len(client.vault_calls) >= 1
    cur, amt = client.vault_calls[0]
    assert cur == "btc"
    # Excess in BTC = ($160 - $150) / $100,000 = 0.0001
    assert amt == Decimal("0.0001")


@pytest.mark.asyncio
async def test_seed_not_baked_when_disabled(monkeypatch, tmp_path):
    client = FakeStakeClient()
    client.balance = Decimal("0.003")          # already at top
    dice = ScriptedDiceAdapter(client, [(True, 200.0)])  # not used: target hit on entry
    _patch_runtime(monkeypatch, client, dice)

    cfg = _config(top="200", secondary="150", bake_seed=False)
    await Orchestrator(cfg, db_path=tmp_path / "t.db").run()

    assert client.seed_set is None


@pytest.mark.asyncio
async def test_already_at_top_halts_immediately(monkeypatch, tmp_path):
    """If start balance already exceeds top, no bets are placed."""
    client = FakeStakeClient()
    client.balance = Decimal("0.01")           # = $1000 USD, well over $200 top
    dice = ScriptedDiceAdapter(client, [])     # empty script: any bet would IndexError
    _patch_runtime(monkeypatch, client, dice)

    cfg = _config(top="200", secondary="150")
    end_reason = await Orchestrator(cfg, db_path=tmp_path / "t.db").run()

    assert end_reason == "top_target_hit"
    assert dice.calls == []


@pytest.mark.asyncio
async def test_session_logged_to_db(monkeypatch, tmp_path):
    """Bets and the session row land in SQLite."""
    import aiosqlite

    client = FakeStakeClient()
    client.balance = Decimal("0.001")
    dice = ScriptedDiceAdapter(client, [(True, 200.0)])
    _patch_runtime(monkeypatch, client, dice)

    db = tmp_path / "session.db"
    cfg = _config(top="200", secondary="150")
    await Orchestrator(cfg, db_path=db).run()

    async with aiosqlite.connect(db) as conn:
        cur = await conn.execute("SELECT currency, persona, end_reason FROM sessions WHERE id=1")
        row = await cur.fetchone()
        assert row == ("btc", "steady", "top_target_hit")

        cur = await conn.execute("SELECT COUNT(*) FROM bets WHERE session_id=1")
        (count,) = await cur.fetchone()
        assert count == 1
