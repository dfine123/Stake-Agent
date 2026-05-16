"""Tests for compute_bet_size."""

from decimal import Decimal

import pytest

from engine.brain.bet_sizer import compute_bet_size
from engine.personas.recovery import RecoveryState
from engine.personas.steady import SteadyPersona

_PERSONA = SteadyPersona()
_MIN = Decimal("0.00000100")
_MAX = Decimal("1.00000000")


def _size(
    bankroll: Decimal,
    step: int = 0,
    last_5: list[bool] | None = None,
    min_bet: Decimal = _MIN,
    max_bet: Decimal = _MAX,
) -> Decimal:
    return compute_bet_size(
        _PERSONA, bankroll, RecoveryState(step=step), last_5 or [], min_bet, max_bet
    )


# ---------------------------------------------------------------------------
# Basic sizing
# ---------------------------------------------------------------------------

def test_steady_state_is_one_percent():
    result = _size(Decimal("1"), last_5=[True, False])
    # 1% of 1 = 0.01, Martingale step 0 (factor 1.0)
    assert result == Decimal("0.01")


def test_heater_is_one_point_25_pct():
    # 3+ wins in last 5
    result = _size(Decimal("1"), last_5=[True, True, True, False, False])
    assert result == Decimal("0.0125")


def test_cold_streak_is_0_75_pct():
    # 3+ losses in last 5
    result = _size(Decimal("1"), last_5=[False, False, False, True, True])
    assert result == Decimal("0.0075")


def test_empty_last_5_is_steady():
    result = _size(Decimal("1"), last_5=[])
    assert result == Decimal("0.01")


# ---------------------------------------------------------------------------
# Martingale scaling
# ---------------------------------------------------------------------------

def test_martingale_step_1():
    # step=1 → base * 1.5
    result = _size(Decimal("1"), step=1)
    assert result == Decimal("0.01") * Decimal("1.5")


def test_martingale_step_2():
    # step=2 → base * 1.5^2 = 2.25
    result = _size(Decimal("1"), step=2)
    assert result == Decimal("0.01") * Decimal("1.5") * Decimal("1.5")


def test_martingale_step_3_capped():
    # step=3 → max steps reached, same as step 3
    result = _size(Decimal("1"), step=3)
    expected = Decimal("0.01") * Decimal("1.5") ** 3
    assert result == expected


# ---------------------------------------------------------------------------
# Clamping
# ---------------------------------------------------------------------------

def test_clamp_to_min():
    # Tiny bankroll → raw bet below min
    result = _size(Decimal("0.000001"), min_bet=Decimal("0.0001"))
    assert result == Decimal("0.0001")


def test_clamp_to_max():
    # Huge bankroll → raw bet above max
    result = _size(Decimal("1000"), max_bet=Decimal("0.5"))
    assert result == Decimal("0.5")


def test_no_clamp_in_range():
    result = _size(Decimal("1"), min_bet=Decimal("0.001"), max_bet=Decimal("1.0"))
    # 1% of 1 = 0.01, within [0.001, 1.0]
    assert result == Decimal("0.01")


def test_min_equals_max_returns_min():
    fixed = Decimal("0.005")
    result = _size(Decimal("1"), min_bet=fixed, max_bet=fixed)
    assert result == fixed
