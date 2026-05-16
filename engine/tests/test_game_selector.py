"""Tests for pick_game."""

from unittest.mock import patch

import pytest

from engine.brain.game_selector import pick_game
from engine.personas.steady import SteadyPersona

_PERSONA = SteadyPersona()
_GAMES = ["dice", "keno", "limbo"]


class _NoVibes:
    influence_game_choice = False
    lucky_numbers: list = []


_VIBES = _NoVibes()


# ---------------------------------------------------------------------------
# Basic selection
# ---------------------------------------------------------------------------

def test_single_game_always_returns_it():
    for _ in range(10):
        assert pick_game(_PERSONA, ["dice"], _VIBES, []) == "dice"


def test_returns_a_valid_game():
    result = pick_game(_PERSONA, _GAMES, _VIBES, [])
    assert result in _GAMES


def test_no_recent_history_picks_freely():
    # Run 50 times, should see all three games eventually
    seen = set()
    for _ in range(50):
        seen.add(pick_game(_PERSONA, _GAMES, _VIBES, []))
    assert seen == {"dice", "keno", "limbo"}


# ---------------------------------------------------------------------------
# Repeat suppression — same game must not be chosen 3× in a row
# ---------------------------------------------------------------------------

def test_repeat_suppressed_after_two_consecutive():
    """When last 2 were 'dice', dice must not be picked (if other options exist)."""
    results = set()
    for _ in range(30):
        game = pick_game(_PERSONA, _GAMES, _VIBES, ["dice", "dice"])
        results.add(game)
    assert "dice" not in results, "dice should be suppressed after 2 consecutive"


def test_repeat_suppressed_only_on_exact_two_consecutive():
    """If last 2 differ, no suppression happens."""
    seen = set()
    for _ in range(50):
        seen.add(pick_game(_PERSONA, _GAMES, _VIBES, ["dice", "keno"]))
    # All three should be reachable
    assert len(seen) > 1


def test_suppression_waived_when_only_one_game():
    """If there's only one game, repeat rule is waived."""
    for _ in range(10):
        result = pick_game(_PERSONA, ["dice"], _VIBES, ["dice", "dice"])
        assert result == "dice"


def test_suppression_waived_when_only_one_candidate_remains():
    """Two games enabled, one suppressed → only remaining game chosen."""
    seen = set()
    for _ in range(10):
        seen.add(pick_game(_PERSONA, ["dice", "keno"], _VIBES, ["dice", "dice"]))
    assert seen == {"keno"}


# ---------------------------------------------------------------------------
# Weighted selection (statistical)
# ---------------------------------------------------------------------------

def test_dice_selected_more_often_with_vibe_nudge():
    """Lucky numbers in 1–10 should push dice weight up."""

    class LowVibes:
        influence_game_choice = True
        lucky_numbers = [3, 7]  # in 1–10 → +5pp to dice

    counts: dict[str, int] = {"dice": 0, "keno": 0, "limbo": 0}
    for _ in range(300):
        g = pick_game(_PERSONA, _GAMES, LowVibes(), [])
        counts[g] += 1

    # Dice weight = 0.45 / (0.45 + 0.30 + 0.30) ≈ 0.43 → should dominate
    assert counts["dice"] > counts["keno"]
    assert counts["dice"] > counts["limbo"]


def test_deterministic_with_seeded_random():
    """With a fixed RNG seed the result is reproducible."""
    import random
    random.seed(42)
    r1 = pick_game(_PERSONA, _GAMES, _VIBES, [])
    random.seed(42)
    r2 = pick_game(_PERSONA, _GAMES, _VIBES, [])
    assert r1 == r2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_one_entry_in_recent_no_suppression():
    """Only one recent game — not two consecutive yet, no suppression."""
    seen = set()
    for _ in range(50):
        seen.add(pick_game(_PERSONA, _GAMES, _VIBES, ["dice"]))
    # All three still reachable
    assert len(seen) >= 2


def test_empty_games_raises():
    with pytest.raises((ValueError, Exception)):
        pick_game(_PERSONA, [], _VIBES, [])
