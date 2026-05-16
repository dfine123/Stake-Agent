"""SQLite logger — subscribes to the event bus and persists every bet.

Crash recovery and post-session analysis depend on this. If a write fails,
the exception propagates and the orchestrator halts the session (per house
rule: losing the audit trail is worse than continuing to bet).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from engine.events import bus as events

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def default_db_path() -> Path:
    """Platform-appropriate default DB location."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GambleAgent" / "sessions.db"
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "GambleAgent" / "sessions.db"
    return Path.home() / ".local" / "share" / "gambleagent" / "sessions.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteLogger:
    """One instance per session. Owns its session_id once session_start fires."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_db_path()
        self._db: aiosqlite.Connection | None = None
        self._session_id: int | None = None

    @property
    def session_id(self) -> int | None:
        return self._session_id

    async def start(self) -> None:
        """Open connection and apply schema. Idempotent."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.executescript(_SCHEMA_PATH.read_text())
        await self._db.commit()

    async def stop(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    def subscribe(self, bus: events.EventBus) -> None:
        bus.subscribe(events.SESSION_START,  self._on_session_start)
        bus.subscribe(events.SESSION_END,    self._on_session_end)
        bus.subscribe(events.BET_SETTLED,    self._on_bet_settled)
        bus.subscribe(events.VAULT_EXECUTED, self._on_vault_executed)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _on_session_start(self, payload: dict) -> None:
        assert self._db is not None, "SqliteLogger.start() not called"
        cursor = await self._db.execute(
            """
            INSERT INTO sessions
                (started_at, currency, persona, top_target_usd,
                 secondary_target_usd, start_balance, vibe_seed, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                payload["currency"],
                payload["persona"],
                str(payload.get("top_target_usd", "")),
                str(payload.get("secondary_target_usd", "")),
                str(payload.get("start_balance", "")),
                payload.get("vibe_seed"),
                json.dumps(payload.get("config", {}), default=str),
            ),
        )
        self._session_id = cursor.lastrowid
        await self._db.commit()

    async def _on_session_end(self, payload: dict) -> None:
        assert self._db is not None
        if self._session_id is None:
            return  # session_start never fired; nothing to update
        await self._db.execute(
            """
            UPDATE sessions
               SET ended_at = ?, end_balance = ?, end_reason = ?
             WHERE id = ?
            """,
            (
                _now(),
                str(payload.get("end_balance", "")),
                payload.get("end_reason", ""),
                self._session_id,
            ),
        )
        await self._db.commit()

    async def _on_bet_settled(self, payload: dict) -> None:
        assert self._db is not None
        if self._session_id is None:
            return  # safety: skip if we somehow got a bet before session_start
        result = payload["result"]
        await self._db.execute(
            """
            INSERT INTO bets
                (session_id, placed_at, settled_at, game, amount, currency,
                 params_json, won, payout, multiplier, stake_bet_id, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._session_id,
                payload.get("placed_at", _now()),
                _now(),
                payload["game"],
                str(payload["amount"]),
                payload["currency"],
                json.dumps(payload.get("params", {}), default=str),
                1 if result["won"] else 0,
                str(result["payout"]),
                float(result["multiplier"]),
                (result.get("raw") or {}).get("id"),
                json.dumps(result.get("raw", {}), default=str),
            ),
        )
        await self._db.commit()

    async def _on_vault_executed(self, payload: dict) -> None:
        assert self._db is not None
        if self._session_id is None:
            return
        await self._db.execute(
            """
            INSERT INTO vault_events (session_id, executed_at, currency, amount)
            VALUES (?, ?, ?, ?)
            """,
            (self._session_id, _now(), payload["currency"], str(payload["amount"])),
        )
        await self._db.commit()
