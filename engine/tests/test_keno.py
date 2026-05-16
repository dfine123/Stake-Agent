"""Unit tests for Keno adapter param validation and result parsing."""

from decimal import Decimal

import pytest

from engine.stake.games.base import parse_bet_response
from engine.stake.games.keno import KenoAdapter


def _win_response() -> dict:
    return {
        "kenoBet": {
            "id": "k1",
            "nonce": 1,
            "currency": "btc",
            "amount": 0.0001,
            "payout": 0.0003,
            "state": {
                "drawnNumbers": [3, 7, 11, 14, 20, 23, 29, 30, 35, 38],
                "selectedNumbers": [7, 11, 23],
                "risk": "classic",
            },
        }
    }


class _FakeClient:
    async def _gql(self, *a, **kw):
        raise AssertionError("should not reach network in param tests")


def _adapter() -> KenoAdapter:
    return KenoAdapter(_FakeClient())  # type: ignore[arg-type]


def test_parse_win():
    r = parse_bet_response(_win_response(), "kenoBet", Decimal("0.0001"))
    assert r.won is True
    assert r.payout == Decimal("0.0003")
    assert abs(r.multiplier - 3.0) < 0.001


@pytest.mark.asyncio
async def test_empty_selected_raises():
    with pytest.raises(ValueError, match="non-empty list"):
        await _adapter().place_bet(Decimal("0.0001"), "btc", {"selected": [], "risk": "classic"})


@pytest.mark.asyncio
async def test_too_many_picks_raises():
    with pytest.raises(ValueError, match="max 10"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"selected": list(range(1, 12)), "risk": "classic"}
        )


@pytest.mark.asyncio
async def test_out_of_range_pick_raises():
    with pytest.raises(ValueError, match=r"\[1, 40\]"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"selected": [7, 41], "risk": "classic"}
        )


@pytest.mark.asyncio
async def test_duplicate_picks_raise():
    with pytest.raises(ValueError, match="duplicates"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"selected": [7, 7, 11], "risk": "classic"}
        )


@pytest.mark.asyncio
async def test_invalid_risk_raises():
    with pytest.raises(ValueError, match="risk"):
        await _adapter().place_bet(
            Decimal("0.0001"), "btc", {"selected": [1, 2, 3], "risk": "extreme"}
        )
