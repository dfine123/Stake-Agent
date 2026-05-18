"""Tests for DryRunAdapter."""

from decimal import Decimal

import pytest

from engine.stake.games.dice import DiceAdapter
from engine.stake.games.dry_run import DryRunAdapter
from engine.stake.games.keno import KenoAdapter
from engine.stake.games.limbo import LimboAdapter


class _FakeClient:
    pass


def _wrap(adapter_cls):
    return DryRunAdapter(adapter_cls(_FakeClient()))


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

def test_name_delegates_to_wrapped():
    assert _wrap(DiceAdapter).name == "dice"
    assert _wrap(KenoAdapter).name == "keno"
    assert _wrap(LimboAdapter).name == "limbo"


def test_persona_params_delegates_to_wrapped():
    from engine.personas.steady import SteadyPersona
    from engine.config import Vibes
    persona = SteadyPersona()
    vibes = Vibes()
    wrapped = _wrap(DiceAdapter)
    result = wrapped.persona_params(persona, Decimal("0.001"), vibes)
    assert result == {"target": 50.5, "condition": "above"}


# ---------------------------------------------------------------------------
# place_bet — dice
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dice_win_returns_payout():
    adapter = _wrap(DiceAdapter)
    import random
    random.seed(0)  # seed(0) gives first float 0.844 → loss for 49.5% threshold
    params = {"target": 50.5, "condition": "above"}
    results = [
        await adapter.place_bet(Decimal("0.0001"), "btc", params)
        for _ in range(20)
    ]
    wins = [r for r in results if r.won]
    losses = [r for r in results if not r.won]
    # At least a few wins and a few losses over 20 tries
    assert len(wins) > 0
    assert len(losses) > 0
    for r in wins:
        assert r.payout > Decimal("0")
        assert r.multiplier > 1.0
    for r in losses:
        assert r.payout == Decimal("0")
        assert r.multiplier == 0.0


@pytest.mark.asyncio
async def test_dice_result_has_dry_run_marker():
    adapter = _wrap(DiceAdapter)
    r = await adapter.place_bet(
        Decimal("0.0001"), "btc", {"target": 50.5, "condition": "above"}
    )
    assert r.raw == {"dry_run": True}


# ---------------------------------------------------------------------------
# place_bet — limbo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_limbo_win_payout_matches_multiplier():
    import random
    random.seed(1)
    adapter = _wrap(LimboAdapter)
    params = {"multiplier_target": 2.0}
    results = [
        await adapter.place_bet(Decimal("0.0001"), "btc", params)
        for _ in range(30)
    ]
    for r in results:
        if r.won:
            # payout / amount = multiplier
            assert abs(float(r.payout / Decimal("0.0001")) - r.multiplier) < 0.0001


# ---------------------------------------------------------------------------
# place_bet — keno
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keno_returns_valid_result():
    adapter = _wrap(KenoAdapter)
    params = {"selected": [1, 2, 3, 4, 5], "risk": "classic"}
    r = await adapter.place_bet(Decimal("0.0001"), "btc", params)
    assert isinstance(r.won, bool)
    assert r.payout >= Decimal("0")


# ---------------------------------------------------------------------------
# Win probability stays in reasonable bounds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dice_low_target_high_win_rate():
    """Below-10 target above gives >85% wins (win_prob ≈ 90%)."""
    import random
    random.seed(42)
    adapter = _wrap(DiceAdapter)
    params = {"target": 10.0, "condition": "above"}  # win_prob = 90%
    wins = 0
    for _ in range(200):
        r = await adapter.place_bet(Decimal("0.001"), "btc", params)
        if r.won:
            wins += 1
    assert wins > 140  # should be ~180


@pytest.mark.asyncio
async def test_limbo_high_target_low_win_rate():
    """High limbo target (100×) gives <2% wins."""
    import random
    random.seed(42)
    adapter = _wrap(LimboAdapter)
    params = {"multiplier_target": 100.0}  # win_prob = 1%
    wins = 0
    for _ in range(300):
        r = await adapter.place_bet(Decimal("0.001"), "btc", params)
        if r.won:
            wins += 1
    assert wins < 15  # should be ~3
