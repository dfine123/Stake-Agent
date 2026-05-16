"""Tests for TargetTracker."""

from decimal import Decimal

import pytest

from engine.brain.targets import TargetEvent, TargetTracker
from engine.config import StopLoss


def _tracker(
    top=Decimal("1000"),
    secondary=Decimal("500"),
    stop_loss=None,
    start=Decimal("100"),
) -> TargetTracker:
    sl = stop_loss or StopLoss(enabled=False)
    return TargetTracker(top, secondary, sl, start)


# ---------------------------------------------------------------------------
# Top target
# ---------------------------------------------------------------------------

def test_top_target_exact():
    t = _tracker()
    assert t.check(Decimal("1000")) == TargetEvent.TOP_TARGET_HIT


def test_top_target_over():
    t = _tracker()
    assert t.check(Decimal("1500")) == TargetEvent.TOP_TARGET_HIT


def test_top_target_not_yet():
    t = _tracker()
    # below both top and secondary → no event
    assert t.check(Decimal("400")) is None


# ---------------------------------------------------------------------------
# Secondary target
# ---------------------------------------------------------------------------

def test_secondary_hit_first_time():
    t = _tracker()
    assert t.check(Decimal("500")) == TargetEvent.SECONDARY_TARGET_HIT


def test_secondary_only_fires_once():
    t = _tracker()
    t.check(Decimal("500"))
    # second call at same balance — latch is set, should not fire again
    assert t.check(Decimal("500")) is None


def test_secondary_fires_again_after_acknowledge():
    t = _tracker()
    t.check(Decimal("500"))
    t.acknowledge_secondary()
    assert t.check(Decimal("600")) == TargetEvent.SECONDARY_TARGET_HIT


def test_secondary_not_hit_below():
    t = _tracker()
    assert t.check(Decimal("499")) is None


def test_secondary_above_top_returns_top():
    """When balance is >= top, top takes priority over secondary."""
    t = _tracker(top=Decimal("300"), secondary=Decimal("200"))
    assert t.check(Decimal("400")) == TargetEvent.TOP_TARGET_HIT


# ---------------------------------------------------------------------------
# Stop loss — fixed_floor mode
# ---------------------------------------------------------------------------

def test_stop_loss_fixed_floor_hit():
    sl = StopLoss(enabled=True, mode="fixed_floor", value=Decimal("50"))
    t = _tracker(stop_loss=sl, start=Decimal("100"))
    assert t.check(Decimal("50")) == TargetEvent.STOP_LOSS_HIT


def test_stop_loss_fixed_floor_above_floor():
    sl = StopLoss(enabled=True, mode="fixed_floor", value=Decimal("50"))
    t = _tracker(stop_loss=sl, start=Decimal("100"))
    assert t.check(Decimal("51")) is None


def test_stop_loss_disabled():
    sl = StopLoss(enabled=False, mode="fixed_floor", value=Decimal("50"))
    t = _tracker(stop_loss=sl, start=Decimal("100"))
    assert t.check(Decimal("10")) is None  # even well below the "floor"


# ---------------------------------------------------------------------------
# Stop loss — pct_of_start mode
# ---------------------------------------------------------------------------

def test_stop_loss_pct_of_start_hit():
    # start=100, value=20 → floor = 100 * (1 - 20/100) = 80
    sl = StopLoss(enabled=True, mode="pct_of_start", value=Decimal("20"))
    t = _tracker(stop_loss=sl, start=Decimal("100"))
    assert t.check(Decimal("80")) == TargetEvent.STOP_LOSS_HIT


def test_stop_loss_pct_of_start_above_floor():
    sl = StopLoss(enabled=True, mode="pct_of_start", value=Decimal("20"))
    t = _tracker(stop_loss=sl, start=Decimal("100"))
    assert t.check(Decimal("81")) is None


# ---------------------------------------------------------------------------
# Stop loss — session_loss_cap mode
# ---------------------------------------------------------------------------

def test_stop_loss_session_loss_cap_hit():
    # start=100, value=30 → floor = 100 - 30 = 70
    sl = StopLoss(enabled=True, mode="session_loss_cap", value=Decimal("30"))
    t = _tracker(stop_loss=sl, start=Decimal("100"))
    assert t.check(Decimal("70")) == TargetEvent.STOP_LOSS_HIT


def test_stop_loss_session_loss_cap_above_floor():
    sl = StopLoss(enabled=True, mode="session_loss_cap", value=Decimal("30"))
    t = _tracker(stop_loss=sl, start=Decimal("100"))
    assert t.check(Decimal("71")) is None


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

def test_top_beats_stop_loss():
    """When balance is both above top AND below floor (weird edge case), top wins."""
    sl = StopLoss(enabled=True, mode="fixed_floor", value=Decimal("2000"))
    t = _tracker(top=Decimal("1000"), stop_loss=sl, start=Decimal("100"))
    # balance 1000 >= top AND 1000 <= floor(2000) → top wins
    assert t.check(Decimal("1000")) == TargetEvent.TOP_TARGET_HIT


def test_stop_loss_beats_secondary():
    """When balance is both at secondary AND below floor, stop loss wins."""
    sl = StopLoss(enabled=True, mode="fixed_floor", value=Decimal("600"))
    t = _tracker(top=Decimal("1000"), secondary=Decimal("500"), stop_loss=sl, start=Decimal("700"))
    # balance 550 >= secondary(500), but also 550 <= floor(600) → stop loss
    assert t.check(Decimal("550")) == TargetEvent.STOP_LOSS_HIT
