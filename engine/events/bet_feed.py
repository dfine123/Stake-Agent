"""Rich-printed colored bet feed for the terminal.

Subscribes to the event bus and prints session lifecycle + bet outcomes.
Green wins, red losses, gold big wins (≥50× multiplier).
"""

from __future__ import annotations

from rich.console import Console

from engine.events import bus as events


class BetFeedUI:
    """Phase 1 terminal UI. Phase 3 replaces this with the Electron renderer."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    def subscribe(self, bus: events.EventBus) -> None:
        bus.subscribe(events.SESSION_START,        self._on_session_start)
        bus.subscribe(events.SESSION_END,          self._on_session_end)
        bus.subscribe(events.BET_SETTLED,          self._on_bet_settled)
        bus.subscribe(events.VAULT_EXECUTED,       self._on_vault_executed)
        bus.subscribe(events.SECONDARY_TARGET_HIT, self._on_secondary_hit)
        bus.subscribe(events.TOP_TARGET_HIT,       self._on_top_hit)
        bus.subscribe(events.STOP_LOSS_HIT,        self._on_stop_loss)

    # ------------------------------------------------------------------
    # Handlers — all sync, called by the bus's await-if-awaitable branch
    # ------------------------------------------------------------------

    def _on_session_start(self, payload: dict) -> None:
        currency = payload.get("currency", "?")
        persona = payload.get("persona", "?")
        bal = payload.get("start_balance", "?")
        self._console.rule(f"[bold cyan]SESSION START[/]  {persona} · {currency} · balance {bal}")

    def _on_session_end(self, payload: dict) -> None:
        reason = payload.get("end_reason", "halted")
        end_bal = payload.get("end_balance", "?")
        net = payload.get("net_pl", "?")
        self._console.rule(f"[bold magenta]SESSION END[/]  {reason} · end {end_bal} · net {net}")

    def _on_bet_settled(self, payload: dict) -> None:
        result = payload["result"]
        game = payload["game"]
        amount = payload["amount"]
        currency = payload["currency"]
        mult = result["multiplier"]
        payout = result["payout"]

        if result["won"]:
            color = "gold1" if mult >= 50 else ("yellow" if mult >= 10 else "green")
            tag = "WIN"
        else:
            color = "red"
            tag = "LOSS"

        self._console.print(
            f"[{color}]{tag}[/]  {game:<6} {amount} {currency}  "
            f"→ payout {payout}  ({mult:.2f}×)"
        )

    def _on_vault_executed(self, payload: dict) -> None:
        amt = payload.get("amount", "?")
        cur = payload.get("currency", "?")
        self._console.print(f"[bold blue]VAULT[/]   moved {amt} {cur} to vault")

    def _on_secondary_hit(self, payload: dict) -> None:
        bal = payload.get("balance", "?")
        self._console.print(f"[bold blue]SECONDARY TARGET[/]  balance {bal} — vaulting excess")

    def _on_top_hit(self, payload: dict) -> None:
        bal = payload.get("balance", "?")
        self._console.print(f"[bold green]TOP TARGET HIT[/]  balance {bal} — halting")

    def _on_stop_loss(self, payload: dict) -> None:
        bal = payload.get("balance", "?")
        self._console.print(f"[bold red]STOP LOSS HIT[/]  balance {bal} — halting")
