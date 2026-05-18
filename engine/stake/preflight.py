"""Pre-flight check — verifies Stake auth and prints a session summary.

run_preflight() fetches balance + rate and prints a Rich summary.
get_preflight_data() is the pure-data version used by the IPC server.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from rich.console import Console
from rich.table import Table

from engine.config import SessionConfig
from engine.stake.client import StakeAPIError, StakeAuthError, StakeClient


async def get_preflight_data(
    cfg: SessionConfig,
    debug_hook: Callable | None = None,
) -> dict:
    """Fetch balance + rate from Stake. Returns plain dict, no printing.

    Returns:
        {"balance": Decimal, "rate": Decimal, "balance_usd": Decimal}
    """
    currency = cfg.session.currency
    async with StakeClient(cfg.credentials.stake_access_token, debug_hook=debug_hook) as client:
        balance = await client.get_balance(currency)
        rate = await client.get_currency_rate(currency)
    return {"balance": balance, "rate": rate, "balance_usd": balance * rate}


async def run_preflight(
    cfg: SessionConfig,
    console: Console | None = None,
    debug_hook: Callable | None = None,
) -> dict:
    """Authenticate with Stake, print a session summary, return balance info.

    Returns:
        dict with keys: balance (Decimal), rate (Decimal), balance_usd (Decimal)

    Raises:
        StakeAuthError: if the access token is rejected.
        StakeAPIError:  if any Stake API call fails.
    """
    con = console or Console()
    session = cfg.session
    currency = session.currency

    con.rule("[bold cyan]GambleAgent — Pre-flight[/]")

    result = await get_preflight_data(cfg, debug_hook=debug_hook)
    balance = result["balance"]
    rate = result["rate"]
    balance_usd = result["balance_usd"]

    needed_usd = max(Decimal("0"), session.top_target_usd - balance_usd)

    con.print(f"[bold green]✓[/] Stake auth OK")
    con.print()

    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()

    t.add_row("Balance",    f"{balance} {currency.upper()}  [dim](≈ ${balance_usd:,.2f} USD)[/]")
    t.add_row("Currency",   currency.upper())
    t.add_row("Persona",    session.persona)
    t.add_row("Games",      ", ".join(session.games_enabled))
    t.add_row("Top target", f"${session.top_target_usd:,.2f}  [dim](need +${needed_usd:,.2f})[/]")
    t.add_row("Secondary",  f"${session.secondary_target_usd:,.2f}")
    if session.stop_loss.enabled:
        t.add_row(
            "Stop-loss",
            f"{session.stop_loss.mode}  {session.stop_loss.value}"
            f"{'%' if session.stop_loss.mode == 'pct_of_start' else ''}",
        )
    else:
        t.add_row("Stop-loss", "[dim]off[/]")

    if session.vibes.text or session.vibes.lucky_numbers:
        vibe_str = session.vibes.text or ""
        if session.vibes.lucky_numbers:
            vibe_str += f"  lucky={session.vibes.lucky_numbers}"
        t.add_row("Vibes", vibe_str.strip())

    con.print(t)
    con.print()

    if balance_usd >= session.top_target_usd:
        con.print(
            "[bold yellow]⚠[/]  Balance is already at or above the top target. "
            "The session will halt immediately without placing any bets."
        )
    elif balance_usd >= session.secondary_target_usd:
        con.print(
            "[bold yellow]⚠[/]  Balance is already above the secondary target. "
            "A vault deposit will fire on the first loop iteration."
        )

    return result
