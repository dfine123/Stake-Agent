"""Pre-flight check — verifies Stake auth and prints a session summary.

Fetches balance + rate so the user can confirm the session config looks right
before real money changes hands.
"""

from __future__ import annotations

from decimal import Decimal

from rich.console import Console
from rich.table import Table

from engine.config import SessionConfig
from engine.stake.client import StakeAuthError, StakeClient


async def run_preflight(cfg: SessionConfig, console: Console | None = None) -> dict:
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

    async with StakeClient(cfg.credentials.stake_access_token) as client:
        balance = await client.get_balance(currency)
        rate = await client.get_currency_rate(currency)

    balance_usd = balance * rate
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

    return {"balance": balance, "rate": rate, "balance_usd": balance_usd}
