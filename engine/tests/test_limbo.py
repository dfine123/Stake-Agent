"""Unit tests for Limbo adapter param validation and result parsing."""

from decimal import Decimal

import pytest

from engine.stake.games.base import parse_bet_response
from engine.stake.games.limbo import LimboAdapter


def _win_response() -> dict:
    return {
        "limboBet": {
            "id": "L1",
            "nonce": 1,
            "currency": "btc",
            "amount": 0.0001,
            "payout": 0.0002,
            "state": {"result": 2.41, "multiplierTarget": 2.0},
        }
    }


def _loss_response() -> dict:
    return {
        "limboBet": {
            "id": "L2",
            "nonce": 2,
            "currency": "btc",
            "amount": 0.0001,
            "payout": 0.0,
            "state": {"result": 1.21, "multiplierTarget": 2.0},
        }
    }


class _FakeClient:
    async def _gql(self, *a, **kw):
        raise AssertionError("should not reach network in param tests")


def _adapter() -> LimboAdapter:
    return LimboAdapter(_FakeClient())  # type: ignore[arg-type]


def test_parse_win():
    r = parse_bet_response(_win_response(), "limboBet", Decimal("0.0001"))
    assert r.won is True
    assert r.payout == Decimal("0.0002")
    assert abs(r.multiplier - 2.0) < 0.001


def test_parse_loss():
    r = parse_bet_response(_loss_response(), "limboBet", Decimal("0.0001"))
    assert r.won is False
    assert r.payout == Decimal("0")
    assert r.multiplier == 0.0


@pytest.mark.asyncio
async def test_missing_target_raises():
    with pytest.raises(ValueError, match="multiplier_target"):
        await _adapter().place_bet(Decimal("0.0001"), "btc", {})


@pytest.mark.asyncio
async def test_below_min_target_raises():
    with pytest.raises(ValueError, match="multiplier_target"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"multiplier_target": 1.0}
        )


@pytest.mark.asyncio
async def test_above_max_target_raises():
    with pytest.raises(ValueError, match="multiplier_target"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"multiplier_target": 2_000_000}
        )
