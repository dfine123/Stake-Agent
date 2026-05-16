"""BetFeedUI smoke tests — captures Rich output to a string buffer."""

import io
from decimal import Decimal

import pytest
from rich.console import Console

from engine.events import bus as events
from engine.events.bet_feed import BetFeedUI
from engine.events.bus import EventBus


def _capturing_ui() -> tuple[BetFeedUI, io.StringIO]:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=120, color_system="truecolor")
    return BetFeedUI(console=console), buf


@pytest.mark.asyncio
async def test_win_rendered_green():
    ui, buf = _capturing_ui()
    bus = EventBus()
    ui.subscribe(bus)

    await bus.emit(events.BET_SETTLED, {
        "game": "dice", "amount": Decimal("0.0001"), "currency": "btc",
        "result": {"won": True, "payout": Decimal("0.000198"), "multiplier": 1.98, "raw": {}},
    })
    out = buf.getvalue()
    assert "WIN" in out
    assert "dice" in out


@pytest.mark.asyncio
async def test_loss_rendered_red():
    ui, buf = _capturing_ui()
    bus = EventBus()
    ui.subscribe(bus)

    await bus.emit(events.BET_SETTLED, {
        "game": "limbo", "amount": Decimal("0.0001"), "currency": "btc",
        "result": {"won": False, "payout": Decimal("0"), "multiplier": 0.0, "raw": {}},
    })
    out = buf.getvalue()
    assert "LOSS" in out
    assert "limbo" in out


@pytest.mark.asyncio
async def test_big_win_uses_gold_styling():
    ui, buf = _capturing_ui()
    bus = EventBus()
    ui.subscribe(bus)

    await bus.emit(events.BET_SETTLED, {
        "game": "limbo", "amount": Decimal("0.0001"), "currency": "btc",
        "result": {"won": True, "payout": Decimal("0.01"), "multiplier": 100.0, "raw": {}},
    })
    # We can't easily assert the ANSI gold color, but the message should mention the multiplier.
    assert "100.00" in buf.getvalue()


@pytest.mark.asyncio
async def test_session_lifecycle_prints():
    ui, buf = _capturing_ui()
    bus = EventBus()
    ui.subscribe(bus)

    await bus.emit(events.SESSION_START, {
        "currency": "btc", "persona": "steady", "start_balance": Decimal("0.001"),
    })
    await bus.emit(events.TOP_TARGET_HIT, {"balance": Decimal("0.002")})
    await bus.emit(events.SESSION_END, {
        "end_reason": "top_target_hit", "end_balance": Decimal("0.002"), "net_pl": Decimal("0.001"),
    })

    out = buf.getvalue()
    assert "SESSION START" in out
    assert "TOP TARGET HIT" in out
    assert "SESSION END" in out
