"""Game selection — weighted random choice with a repeat-suppression rule.

The "don't play the same game 3× in a row" rule prevents degenerate streaks
where one game dominates an entire session. Weights come from the persona,
which already accounts for vibe influence.
"""

from __future__ import annotations

import random
from typing import Any

from engine.personas.base import BasePersona


def pick_game(
    persona: BasePersona,
    enabled_games: list[str],
    vibes: Any,
    recent_games: list[str],
) -> str:
    """Return the next game to play.

    Args:
        persona:       Active persona (provides game_weights).
        enabled_games: Games allowed this session (non-empty).
        vibes:         Vibes object passed to persona.game_weights.
        recent_games:  History of games played, most-recent last. Used to
                       detect 2-in-a-row same game (which would make the next
                       pick a forbidden 3rd consecutive).

    Returns:
        A game name from enabled_games.

    The repeat rule:
        If the last 2 games in recent_games are the same, that game is
        temporarily excluded from the weighted draw. If it is the only game
        available, the rule is waived (can't be avoided).
    """
    if not enabled_games:
        raise ValueError("enabled_games is empty")

    if len(enabled_games) == 1:
        return enabled_games[0]

    weights = persona.game_weights(enabled_games, vibes)

    # Identify if a game must be suppressed (would be 3rd consecutive).
    candidates = list(enabled_games)
    if len(recent_games) >= 2 and recent_games[-1] == recent_games[-2]:
        repeat_game = recent_games[-1]
        filtered = [g for g in candidates if g != repeat_game]
        if filtered:
            candidates = filtered

    candidate_weights = [weights.get(g, 0.0) for g in candidates]
    total = sum(candidate_weights)

    if total == 0:
        # Fallback: uniform over candidates (shouldn't happen with valid persona)
        return random.choice(candidates)

    # Weighted draw without replacement from candidates.
    r = random.uniform(0, total)
    cumulative = 0.0
    for game, w in zip(candidates, candidate_weights):
        cumulative += w
        if r <= cumulative:
            return game

    return candidates[-1]  # floating-point safety
