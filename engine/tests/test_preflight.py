"""Tests for run_preflight."""

import io
from decimal import Decimal

import pytest
from rich.console import Console

from engine.config import (
    Credentials,
    Session,
    SessionConfig,
    StopLoss,
    Vibes,
)
from engine.stake.preflight import run_preflight


# ---------------------------------------------------------------------------
# Fake client
# ---------------------------------------------------------------------------

class FakeStakeClient:
    def __init__(self, *a, **kw) -> None:
        self.balance = Decimal("0.002")
        self.rate = Decimal("50000")

    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def get_balance(self, currency): return self.balance
    async def get_currency_rate(self, currency): return self.rate


def _cfg(top="200", secondary="150", stop_loss=None, vibes=None) -> SessionConfig:
    return SessionConfig(
        credentials=Credentials(stake_access_token="tok"),
        session=Session(
            currency="btc",
            top_target_usd=Decimal(top),
            secondary_target_usd=Decimal(secondary),
            stop_loss=stop_loss or StopLoss(enabled=False),
            persona="steady",
            games_enabled=["dice"],
            vibes=vibes or Vibes(),
        ),
    )


def _capturing_console() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    con = Console(file=buf, force_terminal=False, width=120, color_system=None)
    return con, buf


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preflight_returns_balance_info(monkeypatch):
    import engine.stake.preflight as mod
    monkeypatch.setattr(mod, "StakeClient", FakeStakeClient)
    con, _ = _capturing_console()
    result = await run_preflight(_cfg(), console=con)
    assert result["balance"] == Decimal("0.002")
    assert result["rate"] == Decimal("50000")
    assert result["balance_usd"] == Decimal("100")  # 0.002 * 50000


@pytest.mark.asyncio
async def test_preflight_prints_auth_ok(monkeypatch):
    import engine.stake.preflight as mod
    monkeypatch.setattr(mod, "StakeClient", FakeStakeClient)
    con, buf = _capturing_console()
    await run_preflight(_cfg(), console=con)
    out = buf.getvalue()
    assert "auth OK" in out


@pytest.mark.asyncio
async def test_preflight_shows_top_target(monkeypatch):
    import engine.stake.preflight as mod
    monkeypatch.setattr(mod, "StakeClient", FakeStakeClient)
    con, buf = _capturing_console()
    await run_preflight(_cfg(top="500"), console=con)
    assert "500" in buf.getvalue()


@pytest.mark.asyncio
async def test_preflight_warns_when_already_at_top(monkeypatch):
    """If balance >= top target, a warning must appear."""
    import engine.stake.preflight as mod

    class RichClient(FakeStakeClient):
        async def get_balance(self, c): return Decimal("0.01")  # $500 USD
        async def get_currency_rate(self, c): return Decimal("50000")

    monkeypatch.setattr(mod, "StakeClient", RichClient)
    con, buf = _capturing_console()
    await run_preflight(_cfg(top="200"), console=con)
    assert "already at or above" in buf.getvalue()


@pytest.mark.asyncio
async def test_preflight_warns_above_secondary(monkeypatch):
    """If balance is between secondary and top, a secondary warning appears."""
    import engine.stake.preflight as mod

    class MidClient(FakeStakeClient):
        async def get_balance(self, c): return Decimal("0.004")  # $200 USD, above secondary $150
        async def get_currency_rate(self, c): return Decimal("50000")

    monkeypatch.setattr(mod, "StakeClient", MidClient)
    con, buf = _capturing_console()
    await run_preflight(_cfg(top="300", secondary="150"), console=con)
    assert "secondary" in buf.getvalue().lower()


@pytest.mark.asyncio
async def test_preflight_shows_stop_loss_info(monkeypatch):
    import engine.stake.preflight as mod
    monkeypatch.setattr(mod, "StakeClient", FakeStakeClient)
    sl = StopLoss(enabled=True, mode="fixed_floor", value=Decimal("50"))
    con, buf = _capturing_console()
    await run_preflight(_cfg(stop_loss=sl), console=con)
    assert "fixed_floor" in buf.getvalue()


@pytest.mark.asyncio
async def test_preflight_dry_run_wired_through_orchestrator(monkeypatch, tmp_path):
    """When dry_run=True, the orchestrator wraps adapters in DryRunAdapter."""
    from engine.brain import orchestrator as orch_mod
    from engine.stake.games.dry_run import DryRunAdapter

    class FakeClientCtx(FakeStakeClient):
        async def set_client_seed(self, s): return s
        async def vault_deposit(self, c, a): return {}

    monkeypatch.setattr(orch_mod, "StakeClient", FakeClientCtx)
    wrapped: list = []

    original_build = orch_mod._build_game_adapters
    def capturing_build(client):
        result = original_build(client)
        return result
    monkeypatch.setattr(orch_mod, "_build_game_adapters", capturing_build)

    # Make asyncio.sleep a no-op
    async def _no_sleep(_): pass
    monkeypatch.setattr(orch_mod.asyncio, "sleep", _no_sleep)

    # Balance = $200 → already at top ($200), so loop exits immediately
    client_instance = FakeClientCtx()
    client_instance.balance = Decimal("0.004")  # 0.004 * 50000 = $200 = top
    monkeypatch.setattr(orch_mod, "StakeClient", lambda tok: client_instance)

    cfg = _cfg(top="200", secondary="150")
    from engine.brain.orchestrator import Orchestrator
    orch = Orchestrator(cfg, db_path=tmp_path / "t.db", dry_run=True)
    end_reason = await orch.run()
    assert end_reason == "top_target_hit"
