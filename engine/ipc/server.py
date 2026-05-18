"""Python-side IPC server — reads JSON commands from stdin, writes JSON to stdout.

Message framing: newline-delimited JSON. One message per line, flushed immediately.

Schema:
  Command  (Electron → Python): {"id": uuid, "type": "command",  "name": str, "payload": dict, "ts": iso8601}
  Response (Python → Electron): {"id": uuid, "type": "response", "name": str, "ok": bool, "payload": dict, "ts": iso8601}
  Event    (Python → Electron): {"id": uuid, "type": "event",    "name": str, "payload": dict, "ts": iso8601}
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from engine.brain.orchestrator import Orchestrator
from engine.config import (
    Credentials,
    Session,
    SessionConfig,
    StopLoss,
    Vibes,
)
from engine.events import bus as event_names
from engine.events.bus import EventBus
from engine.stake.client import StakeAPIError, StakeAuthError, StakeClient
from engine.stake.preflight import get_preflight_data

# All event bus event names the orchestrator can emit — forwarded over IPC.
_BUS_EVENTS = [
    event_names.SESSION_START,
    event_names.SESSION_END,
    event_names.BET_PLACED,
    event_names.BET_SETTLED,
    event_names.WON_SMALL,
    event_names.WON_MEDIUM,
    event_names.WON_BIG,
    event_names.LOST,
    event_names.VAULT_EXECUTED,
    event_names.SECONDARY_TARGET_HIT,
    event_names.TOP_TARGET_HIT,
    event_names.STOP_LOSS_HIT,
]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class IPCServer:
    """Async stdio IPC server. One instance per process lifetime."""

    def __init__(self) -> None:
        self._session_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._pause_event: asyncio.Event | None = None
        self._session_bus: EventBus | None = None

    # ── Output helpers ────────────────────────────────────────────────────────

    def _send(self, msg: dict) -> None:
        """Write one newline-terminated JSON message to stdout and flush."""
        line = json.dumps(msg, default=str) + "\n"
        sys.stdout.buffer.write(line.encode("utf-8"))
        sys.stdout.buffer.flush()

    def respond(self, cmd_id: str, name: str, payload: dict, ok: bool = True) -> None:
        self._send({"id": cmd_id, "type": "response", "name": name,
                    "ok": ok, "payload": payload, "ts": _ts()})

    def emit(self, name: str, payload: dict) -> None:
        self._send({"id": str(uuid4()), "type": "event",
                    "name": name, "payload": payload, "ts": _ts()})

    def log(self, level: str, message: str) -> None:
        self.emit("log", {"level": level, "message": message})

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Read stdin line-by-line and dispatch commands until EOF."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader),
            sys.stdin.buffer,
        )

        self.log("info", "IPC server ready")

        while True:
            try:
                raw = await reader.readline()
            except Exception:
                break
            if not raw:
                break  # EOF — Electron process gone

            raw = raw.strip()
            if not raw:
                continue

            try:
                msg = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.emit("error", {"message": f"bad JSON: {exc}"})
                continue

            # Dispatch each command as a separate task so the read loop stays
            # responsive (e.g. panic while a slow preflight is running).
            asyncio.create_task(self._dispatch(msg))

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, msg: dict) -> None:
        name   = msg.get("name", "")
        cmd_id = msg.get("id") or str(uuid4())
        payload = msg.get("payload") or {}

        try:
            handlers = {
                "get_status":     self._cmd_get_status,
                "preflight":      self._cmd_preflight,
                "get_balance":    self._cmd_get_balance,
                "start_session":  self._cmd_start_session,
                "pause_session":  self._cmd_pause_session,
                "resume_session": self._cmd_resume_session,
                "stop_session":   self._cmd_stop_session,
                "panic":          self._cmd_panic,
            }
            handler = handlers.get(name)
            if handler is None:
                self.respond(cmd_id, name, {"error": f"unknown command: {name!r}"}, ok=False)
                return
            await handler(cmd_id, payload)
        except Exception as exc:
            self.respond(cmd_id, name,
                         {"error": str(exc), "type": type(exc).__name__}, ok=False)

    # ── Command handlers ──────────────────────────────────────────────────────

    async def _cmd_get_status(self, cmd_id: str, _payload: dict) -> None:
        running = bool(self._session_task and not self._session_task.done())
        paused  = running and bool(self._pause_event and not self._pause_event.is_set())
        self.respond(cmd_id, "get_status", {"session_running": running, "paused": paused})

    async def _cmd_preflight(self, cmd_id: str, payload: dict) -> None:
        token    = payload.get("stake_token", "").strip()
        currency = payload.get("currency", "btc")

        if not token:
            self.respond(cmd_id, "preflight", {"error": "stake_token required"}, ok=False)
            return

        def debug_hook(direction: str, data: dict) -> None:
            self.emit(f"debug_{direction}", data)

        try:
            cfg = _minimal_config(token, currency)
        except Exception as exc:
            self.respond(cmd_id, "preflight", {"error": str(exc)}, ok=False)
            return

        try:
            result = await get_preflight_data(cfg, debug_hook=debug_hook)
        except (StakeAuthError, StakeAPIError) as exc:
            self.respond(cmd_id, "preflight",
                         {"error": str(exc), "type": type(exc).__name__}, ok=False)
            return

        self.respond(cmd_id, "preflight", {
            "balance":     str(result["balance"]),
            "rate":        str(result["rate"]),
            "balance_usd": str(result["balance_usd"]),
            "currency":    currency,
        })

    async def _cmd_get_balance(self, cmd_id: str, payload: dict) -> None:
        token    = payload.get("stake_token", "").strip()
        currency = payload.get("currency", "btc")

        if not token:
            self.respond(cmd_id, "get_balance", {"error": "stake_token required"}, ok=False)
            return

        def debug_hook(direction: str, data: dict) -> None:
            self.emit(f"debug_{direction}", data)

        try:
            async with StakeClient(token, debug_hook=debug_hook) as client:
                balance = await client.get_balance(currency)
                rate    = await client.get_currency_rate(currency)
        except (StakeAuthError, StakeAPIError) as exc:
            self.respond(cmd_id, "get_balance",
                         {"error": str(exc), "type": type(exc).__name__}, ok=False)
            return

        self.respond(cmd_id, "get_balance", {
            "balance":     str(balance),
            "rate":        str(rate),
            "balance_usd": str(balance * rate),
            "currency":    currency,
        })

    async def _cmd_start_session(self, cmd_id: str, payload: dict) -> None:
        if self._session_task and not self._session_task.done():
            self.respond(cmd_id, "start_session",
                         {"error": "session already running"}, ok=False)
            return

        try:
            cfg = SessionConfig.model_validate(payload)
        except Exception as exc:
            self.respond(cmd_id, "start_session", {"error": str(exc)}, ok=False)
            return

        self._stop_event  = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused initially
        self._session_bus = EventBus()

        # Forward every engine bus event as an IPC event.
        for ev in _BUS_EVENTS:
            def _make_fwd(event_name: str):
                def fwd(p: dict) -> None:
                    self.emit(event_name, p)
                return fwd
            self._session_bus.subscribe(ev, _make_fwd(ev))

        def debug_hook(direction: str, data: dict) -> None:
            self.emit(f"debug_{direction}", data)

        orch = Orchestrator(
            cfg,
            db_path=payload.get("_db_path"),
            dry_run=bool(payload.get("_dry_run", False)),
            bus=self._session_bus,
            stop_event=self._stop_event,
            pause_event=self._pause_event,
            debug_hook=debug_hook,
        )

        self.respond(cmd_id, "start_session", {"status": "starting"})

        async def _run() -> None:
            try:
                end_reason = await orch.run()
                self.emit("session_completed", {"end_reason": end_reason})
            except asyncio.CancelledError:
                self.emit("session_completed", {"end_reason": "panic"})
            except Exception as exc:
                self.emit("error", {"message": str(exc), "type": type(exc).__name__})
                self.emit("session_completed", {"end_reason": "error"})
            finally:
                self._session_task  = None
                self._stop_event    = None
                self._pause_event   = None

        self._session_task = asyncio.create_task(_run())

    async def _cmd_pause_session(self, cmd_id: str, _payload: dict) -> None:
        if not self._pause_event:
            self.respond(cmd_id, "pause_session",
                         {"error": "no active session"}, ok=False)
            return
        self._pause_event.clear()
        self.respond(cmd_id, "pause_session", {"status": "paused"})

    async def _cmd_resume_session(self, cmd_id: str, _payload: dict) -> None:
        if not self._pause_event:
            self.respond(cmd_id, "resume_session",
                         {"error": "no active session"}, ok=False)
            return
        self._pause_event.set()
        self.respond(cmd_id, "resume_session", {"status": "resumed"})

    async def _cmd_stop_session(self, cmd_id: str, _payload: dict) -> None:
        if not self._stop_event:
            self.respond(cmd_id, "stop_session",
                         {"error": "no active session"}, ok=False)
            return
        self._stop_event.set()
        if self._pause_event:
            self._pause_event.set()  # unblock if paused so loop can check stop
        self.respond(cmd_id, "stop_session", {"status": "stopping"})

    async def _cmd_panic(self, cmd_id: str, _payload: dict) -> None:
        # Cancel the task immediately — does not wait for clean loop exit.
        if self._session_task and not self._session_task.done():
            self._session_task.cancel()
        if self._stop_event:
            self._stop_event.set()
        if self._pause_event:
            self._pause_event.set()
        self.respond(cmd_id, "panic", {"status": "halted"})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minimal_config(token: str, currency: str) -> SessionConfig:
    """Minimal valid SessionConfig for auth-only operations (preflight, balance)."""
    return SessionConfig(
        credentials=Credentials(stake_access_token=token),
        session=Session(
            currency=currency,  # type: ignore[arg-type]
            top_target_usd=Decimal("999999"),
            secondary_target_usd=Decimal("999998"),
            persona="steady",
            games_enabled=["dice"],
            stop_loss=StopLoss(enabled=False),
            vibes=Vibes(bake_into_seed=False),
        ),
    )


async def serve() -> None:
    """Entry point called by `engine main serve`."""
    server = IPCServer()
    await server.run()
