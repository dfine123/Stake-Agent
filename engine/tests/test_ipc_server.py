"""Tests for IPC server command handlers.

We don't spawn a real subprocess — we instantiate the IPCServer in-process
and capture its output by intercepting `_send`.
"""

from __future__ import annotations

import asyncio

import pytest

from engine.ipc.server import IPCServer, _format_validation_error
from engine.config import SessionConfig
from pydantic import ValidationError


@pytest.fixture
def server():
    """An IPCServer with _send patched to capture outbound messages."""
    s = IPCServer()
    s.sent = []
    s._send = lambda msg: s.sent.append(msg)
    return s


def _valid_payload(**overrides) -> dict:
    payload = {
        "credentials": {"stake_access_token": "tok_abc123"},
        "session": {
            "currency": "usdt",
            "top_target_usd": 500,
            "secondary_target_usd": 250,
            "persona": "steady",
            "games_enabled": ["dice"],
            "stop_loss": {"enabled": False, "mode": "fixed_floor", "value": 0},
            "vibes": {
                "text": "",
                "lucky_numbers": [],
                "bake_into_seed": True,
                "influence_game_choice": True,
            },
        },
    }
    payload.update(overrides)
    return payload


# ── _format_validation_error ─────────────────────────────────────────────────

def test_format_validation_error_returns_structured_detail():
    try:
        SessionConfig.model_validate({"credentials": {}, "session": {}})
    except ValidationError as exc:
        out = _format_validation_error(exc)

    assert "error" in out
    assert "detail" in out
    assert isinstance(out["detail"], list)
    assert len(out["detail"]) > 0
    # Each detail item has loc, msg, type
    for e in out["detail"]:
        assert "loc" in e and isinstance(e["loc"], str)
        assert "msg" in e
        assert "type" in e


# ── validate_config command ──────────────────────────────────────────────────

def test_validate_config_accepts_valid_payload(server):
    asyncio.run(server._cmd_validate_config("cmd-1", _valid_payload()))
    assert len(server.sent) == 1
    msg = server.sent[0]
    assert msg["ok"] is True
    assert msg["payload"]["valid"] is True


def test_validate_config_rejects_missing_token(server):
    bad = _valid_payload()
    bad["credentials"] = {}  # no stake_access_token
    asyncio.run(server._cmd_validate_config("cmd-2", bad))
    msg = server.sent[0]
    assert msg["ok"] is False
    assert "detail" in msg["payload"]
    locs = [e["loc"] for e in msg["payload"]["detail"]]
    assert any("stake_access_token" in l for l in locs)


def test_validate_config_rejects_secondary_above_top(server):
    bad = _valid_payload()
    bad["session"]["secondary_target_usd"] = 600  # > top of 500
    asyncio.run(server._cmd_validate_config("cmd-3", bad))
    msg = server.sent[0]
    assert msg["ok"] is False
    detail = msg["payload"]["detail"]
    assert any("secondary" in e["msg"].lower() or "secondary" in e["loc"].lower()
               for e in detail)


def test_validate_config_rejects_empty_games(server):
    bad = _valid_payload()
    bad["session"]["games_enabled"] = []
    asyncio.run(server._cmd_validate_config("cmd-4", bad))
    msg = server.sent[0]
    assert msg["ok"] is False


# ── get_config_schema command ────────────────────────────────────────────────

def test_get_config_schema_returns_pydantic_schema(server):
    asyncio.run(server._cmd_get_config_schema("cmd-5", {}))
    msg = server.sent[0]
    assert msg["ok"] is True
    schema = msg["payload"]["schema"]
    # Pydantic v2 schemas have $defs / properties at top level
    assert isinstance(schema, dict)
    assert "properties" in schema or "$defs" in schema
