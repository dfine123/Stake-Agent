"""Tests for Steady persona — all deterministic methods only.

bet_delay() is intentionally non-deterministic and is tested only for range,
not for a specific value.
"""

from decimal import Decimal

import pytest

from engine.personas.recovery import (
    MartingaleConfig,
    RecoveryState,
    apply_martingale,
    next_recovery_state,
)
from engine.personas.steady import SteadyPersona, _select_keno_picks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def persona() -> SteadyPersona:
    return SteadyPersona()


class _Vibes:
    """Minimal vibes stub."""
    def __init__(self, lucky_numbers=None, influence=True):
        self.lucky_numbers = lucky_numbers or []
        self.influence_game_choice = influence


# ---------------------------------------------------------------------------
# bet_size — base percentage
# ---------------------------------------------------------------------------

def test_steady_state_is_one_pct(persona):
    state = RecoveryState(step=0)
    result = persona.bet_size(Decimal("1000"), state, [True, False, True, False])
    assert result == Decimal("10.00")  # exactly 1% — 2W/2L, neither threshold crossed


def test_win_streak_raises_to_1_25_pct(persona):
    state = RecoveryState(step=0)
    result = persona.bet_size(Decimal("1000"), state, [True, True, True, False, True])
    assert result == Decimal("12.5")


def test_loss_streak_drops_to_0_75_pct(persona):
    state = RecoveryState(step=0)
    result = persona.bet_size(Decimal("1000"), state, [False, False, False, True, False])
    assert result == Decimal("7.5")


def test_empty_last_5_gives_steady_state(persona):
    state = RecoveryState(step=0)
    result = persona.bet_size(Decimal("1000"), state, [])
    assert result == Decimal("10.00")


# ---------------------------------------------------------------------------
# bet_size — Martingale
# ---------------------------------------------------------------------------

def test_recovery_step_1(persona):
    state = RecoveryState(step=1)
    base = Decimal("1000") * Decimal("0.01")  # 10
    result = persona.bet_size(Decimal("1000"), state, [])
    assert result == base * Decimal("1.5")


def test_recovery_step_2(persona):
    state = RecoveryState(step=2)
    base = Decimal("1000") * Decimal("0.01")
    result = persona.bet_size(Decimal("1000"), state, [])
    assert result == base * Decimal("2.25")


def test_recovery_step_3(persona):
    state = RecoveryState(step=3)
    base = Decimal("1000") * Decimal("0.01")
    result = persona.bet_size(Decimal("1000"), state, [])
    assert result == base * Decimal("3.375")


# ---------------------------------------------------------------------------
# RecoveryState transitions
# ---------------------------------------------------------------------------

_cfg = MartingaleConfig()


def test_win_resets_step():
    assert next_recovery_state(RecoveryState(step=2), won=True, config=_cfg).step == 0


def test_loss_advances_step():
    assert next_recovery_state(RecoveryState(step=0), won=False, config=_cfg).step == 1


def test_loss_capped_at_max_steps():
    assert next_recovery_state(RecoveryState(step=3), won=False, config=_cfg).step == 3


def test_apply_martingale_at_step_0():
    assert apply_martingale(Decimal("10"), RecoveryState(step=0), _cfg) == Decimal("10")


def test_apply_martingale_at_step_1():
    assert apply_martingale(Decimal("10"), RecoveryState(step=1), _cfg) == Decimal("15")


# ---------------------------------------------------------------------------
# game_weights
# ---------------------------------------------------------------------------

def test_default_weights_sum_to_one(persona):
    w = persona.game_weights(["dice", "keno", "limbo"], _Vibes())
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_default_weights_order(persona):
    w = persona.game_weights(["dice", "keno", "limbo"], _Vibes())
    assert w["dice"] > w["keno"]
    assert w["keno"] == pytest.approx(w["limbo"])


def test_single_game_weight_is_one(persona):
    w = persona.game_weights(["dice"], _Vibes())
    assert w["dice"] == pytest.approx(1.0)


def test_vibe_low_numbers_nudge_dice(persona):
    w_base = persona.game_weights(["dice", "keno", "limbo"], _Vibes())
    w_vibe = persona.game_weights(["dice", "keno", "limbo"], _Vibes(lucky_numbers=[3, 7]))
    assert w_vibe["dice"] > w_base["dice"]


def test_vibe_mid_numbers_nudge_keno(persona):
    w_base = persona.game_weights(["dice", "keno", "limbo"], _Vibes())
    w_vibe = persona.game_weights(["dice", "keno", "limbo"], _Vibes(lucky_numbers=[15, 22]))
    assert w_vibe["keno"] > w_base["keno"]


def test_vibe_high_numbers_nudge_limbo(persona):
    w_base = persona.game_weights(["dice", "keno", "limbo"], _Vibes())
    w_vibe = persona.game_weights(["dice", "keno", "limbo"], _Vibes(lucky_numbers=[33, 38]))
    assert w_vibe["limbo"] > w_base["limbo"]


def test_influence_disabled_ignores_lucky_numbers(persona):
    w_base = persona.game_weights(["dice", "keno", "limbo"], _Vibes())
    w_off  = persona.game_weights(["dice", "keno", "limbo"], _Vibes(lucky_numbers=[3, 7], influence=False))
    assert w_base == pytest.approx(w_off)


def test_weights_renormalize_for_subset(persona):
    w = persona.game_weights(["dice", "keno"], _Vibes())
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert "limbo" not in w


# ---------------------------------------------------------------------------
# Per-game params
# ---------------------------------------------------------------------------

def test_dice_params_fixed(persona):
    p = persona.dice_params(Decimal("1000"), _Vibes())
    assert p == {"target": 50.5, "condition": "above"}


def test_limbo_params_fixed(persona):
    p = persona.limbo_params(Decimal("1000"), _Vibes())
    assert p == {"multiplier_target": 2.0}


def test_keno_params_defaults_when_no_lucky(persona):
    p = persona.keno_params(Decimal("1000"), _Vibes())
    assert p["risk"] == "classic"
    assert len(p["selected"]) == 5
    assert all(1 <= n <= 40 for n in p["selected"])


def test_keno_uses_lucky_numbers_when_valid(persona):
    p = persona.keno_params(Decimal("1000"), _Vibes(lucky_numbers=[3, 9, 17, 25, 33]))
    assert p["selected"] == [3, 9, 17, 25, 33]


def test_keno_pads_when_too_few_lucky(persona):
    p = persona.keno_params(Decimal("1000"), _Vibes(lucky_numbers=[3]))
    assert len(p["selected"]) == 5
    assert 3 in p["selected"]
    assert len(set(p["selected"])) == 5  # no duplicates


def test_keno_deduplicates_lucky_numbers():
    picks = _select_keno_picks(_Vibes(lucky_numbers=[7, 7, 14, 14, 21]))
    assert len(picks) == 5
    assert len(set(picks)) == 5


def test_keno_out_of_range_lucky_ignored(persona):
    p = persona.keno_params(Decimal("1000"), _Vibes(lucky_numbers=[0, 41, 99]))
    assert all(1 <= n <= 40 for n in p["selected"])


# ---------------------------------------------------------------------------
# bet_delay — range only
# ---------------------------------------------------------------------------

def test_bet_delay_in_valid_range(persona):
    # ±20% jitter on [2, 5] → absolute min ~1.6, absolute max ~6.0
    for _ in range(50):
        d = persona.bet_delay()
        assert 1.5 < d < 6.5, f"delay {d} out of expected jitter range"
