"""Tests for the EventBus."""

import pytest

from engine.events.bus import BET_SETTLED, SESSION_START, EventBus


@pytest.mark.asyncio
async def test_sync_handler_fires():
    bus = EventBus()
    seen = []
    bus.subscribe(SESSION_START, lambda p: seen.append(p))
    await bus.emit(SESSION_START, {"x": 1})
    assert seen == [{"x": 1}]


@pytest.mark.asyncio
async def test_async_handler_fires():
    bus = EventBus()
    seen = []

    async def h(p):
        seen.append(p)

    bus.subscribe(SESSION_START, h)
    await bus.emit(SESSION_START, {"x": 2})
    assert seen == [{"x": 2}]


@pytest.mark.asyncio
async def test_multiple_handlers_fire_in_order():
    bus = EventBus()
    log = []
    bus.subscribe(SESSION_START, lambda p: log.append("a"))
    bus.subscribe(SESSION_START, lambda p: log.append("b"))
    bus.subscribe(SESSION_START, lambda p: log.append("c"))
    await bus.emit(SESSION_START)
    assert log == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_unsubscribed_event_is_noop():
    bus = EventBus()
    await bus.emit(BET_SETTLED, {"any": "thing"})  # nothing happens, no error


@pytest.mark.asyncio
async def test_handler_exception_propagates():
    bus = EventBus()

    def boom(p):
        raise RuntimeError("subscriber failed")

    bus.subscribe(SESSION_START, boom)
    with pytest.raises(RuntimeError, match="subscriber failed"):
        await bus.emit(SESSION_START, {})


@pytest.mark.asyncio
async def test_handlers_isolated_by_event():
    bus = EventBus()
    a, b = [], []
    bus.subscribe(SESSION_START, lambda p: a.append(p))
    bus.subscribe(BET_SETTLED,   lambda p: b.append(p))
    await bus.emit(SESSION_START, {"x": 1})
    assert a == [{"x": 1}]
    assert b == []


@pytest.mark.asyncio
async def test_empty_payload_default():
    bus = EventBus()
    seen = []
    bus.subscribe(SESSION_START, lambda p: seen.append(p))
    await bus.emit(SESSION_START)
    assert seen == [{}]
