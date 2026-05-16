"""Tests for SqliteLogger — writes against a temp DB file (not in-memory because
aiosqlite/sqlite-with-WAL/multi-statement schema works best on real files)."""

from decimal import Decimal
from pathlib import Path

import aiosqlite
import pytest

from engine.events import bus as events
from engine.events.bus import EventBus
from engine.storage.db import SqliteLogger


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.mark.asyncio
async def test_schema_created(db_path: Path):
    logger = SqliteLogger(db_path)
    await logger.start()
    try:
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cur.fetchall()]
        assert "sessions" in tables
        assert "bets" in tables
        assert "vault_events" in tables
    finally:
        await logger.stop()


@pytest.mark.asyncio
async def test_full_session_roundtrip(db_path: Path):
    bus = EventBus()
    logger = SqliteLogger(db_path)
    await logger.start()
    logger.subscribe(bus)

    try:
        await bus.emit(events.SESSION_START, {
            "currency": "btc",
            "persona": "steady",
            "top_target_usd": Decimal("10000"),
            "secondary_target_usd": Decimal("3000"),
            "start_balance": Decimal("0.001"),
            "vibe_seed": "deadbeef",
            "config": {"games_enabled": ["dice"]},
        })
        assert logger.session_id == 1

        await bus.emit(events.BET_SETTLED, {
            "game": "dice",
            "amount": Decimal("0.0001"),
            "currency": "btc",
            "params": {"target": 50.5, "condition": "above"},
            "result": {
                "won": True,
                "payout": Decimal("0.000198"),
                "multiplier": 1.98,
                "raw": {"id": "stake-id-1"},
            },
        })

        await bus.emit(events.BET_SETTLED, {
            "game": "dice",
            "amount": Decimal("0.0001"),
            "currency": "btc",
            "params": {"target": 50.5, "condition": "above"},
            "result": {
                "won": False,
                "payout": Decimal("0"),
                "multiplier": 0.0,
                "raw": {"id": "stake-id-2"},
            },
        })

        await bus.emit(events.VAULT_EXECUTED, {
            "currency": "btc",
            "amount": Decimal("0.0005"),
        })

        await bus.emit(events.SESSION_END, {
            "end_balance": Decimal("0.00099"),
            "end_reason": "user_halt",
        })
    finally:
        await logger.stop()

    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT currency, persona, start_balance, end_balance, end_reason "
            "FROM sessions WHERE id = 1"
        )
        row = await cur.fetchone()
        assert row == ("btc", "steady", "0.001", "0.00099", "user_halt")

        cur = await db.execute(
            "SELECT game, amount, won, payout, multiplier, stake_bet_id "
            "FROM bets WHERE session_id = 1 ORDER BY id"
        )
        bets = await cur.fetchall()
        assert len(bets) == 2
        assert bets[0] == ("dice", "0.0001", 1, "0.000198", 1.98, "stake-id-1")
        assert bets[1] == ("dice", "0.0001", 0, "0", 0.0, "stake-id-2")

        cur = await db.execute(
            "SELECT currency, amount FROM vault_events WHERE session_id = 1"
        )
        assert await cur.fetchall() == [("btc", "0.0005")]


@pytest.mark.asyncio
async def test_session_end_without_start_is_noop(db_path: Path):
    bus = EventBus()
    logger = SqliteLogger(db_path)
    await logger.start()
    logger.subscribe(bus)
    try:
        await bus.emit(events.SESSION_END, {
            "end_balance": Decimal("0"),
            "end_reason": "error",
        })
    finally:
        await logger.stop()
    # No exception, no rows written — just exits cleanly.
