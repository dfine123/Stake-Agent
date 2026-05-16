"""Unit tests for the Dice adapter result parser and param validation.

No live Stake calls — uses fixture responses shaped from the confirmed
DiceBot mutation spec.
"""

from decimal import Decimal

import pytest

from engine.stake.games.base import parse_bet_response
from engine.stake.games.dice import DiceAdapter


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _win_response(amount: float = 0.0001, payout: float = 0.00019800) -> dict:
    """Fixture: a winning diceRoll response."""
    return {
        "diceRoll": {
            "id": "abc123",
            "nonce": 1,
            "currency": "btc",
            "amount": amount,
            "payout": payout,
            "state": {"result": 73.5, "target": 50.5, "condition": "above"},
            "createdAt": "2026-05-16T00:00:00Z",
            "serverSeed": {"seedHash": "aaa", "nonce": 1},
            "clientSeed": {"seed": "bbb"},
            "user": {
                "balances": {"available": [{"amount": 1.23, "currency": "btc"}]}
            },
        }
    }


def _loss_response(amount: float = 0.0001) -> dict:
    """Fixture: a losing diceRoll response (payout is 0)."""
    r = _win_response(amount=amount, payout=0.0)
    r["diceRoll"]["state"]["result"] = 22.1
    return r


# ---------------------------------------------------------------------------
# _parse_result
# ---------------------------------------------------------------------------

def test_parse_win():
    result = parse_bet_response(_win_response(), "diceRoll", Decimal("0.0001"))
    assert result.won is True
    assert result.payout == Decimal("0.00019800")
    assert abs(result.multiplier - 1.98) < 0.001
    assert result.raw["id"] == "abc123"


def test_parse_loss():
    result = parse_bet_response(_loss_response(), "diceRoll", Decimal("0.0001"))
    assert result.won is False
    assert result.payout == Decimal("0")
    assert result.multiplier == 0.0


def test_parse_preserves_raw():
    raw = _win_response()
    result = parse_bet_response(raw, "diceRoll", Decimal("0.0001"))
    assert result.raw is raw["diceRoll"]


# ---------------------------------------------------------------------------
# param validation (no client needed — just call place_bet via direct param check)
# ---------------------------------------------------------------------------

class _FakeClient:
    async def _gql(self, *a, **kw):  # never called in validation tests
        raise AssertionError("should not reach network in param tests")


def _adapter():
    return DiceAdapter(_FakeClient())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_missing_target_raises():
    with pytest.raises(ValueError, match="missing 'target'"):
        await _adapter().place_bet(Decimal("0.0001"), "btc", {"condition": "above"})


@pytest.mark.asyncio
async def test_invalid_condition_raises():
    with pytest.raises(ValueError, match="condition"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"target": 50.5, "condition": "sideways"}
        )


@pytest.mark.asyncio
async def test_out_of_range_target_raises():
    with pytest.raises(ValueError, match="target"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"target": 100.0, "condition": "above"}
        )


def test_min_bet_returns_decimal():
    assert isinstance(_adapter().min_bet("btc"), Decimal)


def test_max_bet_returns_decimal():
    assert isinstance(_adapter().max_bet("btc"), Decimal)


def test_min_less_than_max():
    a = _adapter()
    for cur in ("btc", "eth", "usdt", "ltc", "doge", "trx"):
        assert a.min_bet(cur) < a.max_bet(cur), f"min >= max for {cur}"
