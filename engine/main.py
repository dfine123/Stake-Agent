"""GambleAgent engine entry point.

Phase 1: CLI prototype. Run with:
    python -m engine.main run --config session.yaml

Subcommands:
    validate   — parse and validate config, print summary, exit (no network)
    preflight  — validate config + authenticate with Stake + show balance
    run        — run a full session (add --dry-run to simulate without bets)
"""

import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError
from rich.console import Console

from engine.brain.orchestrator import Orchestrator
from engine.config import load_config
from engine.stake.client import StakeAPIError, StakeAuthError
from engine.stake.preflight import run_preflight

_console = Console()


def _load_config_with_prompt(path: str) -> object:
    """Load config; fall back to interactive token prompt if YAML has a placeholder.

    In Phase 3 the Electron UI supplies the token directly — this prompt is
    the CLI equivalent of that onboarding step.
    """
    try:
        return load_config(path)
    except (ValidationError, ValueError) as first_err:
        if "stake_access_token" not in str(first_err):
            raise

    # Token is missing / placeholder — ask the user exactly once.
    _console.print()
    _console.print("[bold]Stake access token not set.[/]  "
                   "Paste the value of the [cyan]x-access-token[/] header "
                   "from your browser's DevTools (Network → any graphql request).")
    try:
        token = getpass.getpass("  Access token: ").strip()
    except (KeyboardInterrupt, EOFError):
        _console.print("\n[dim]aborted[/]")
        raise SystemExit(130)

    if not token:
        _console.print("[red]No token entered — cannot continue.[/]")
        raise SystemExit(2)

    return load_config(path, token_override=token)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gambleagent",
        description="GambleAgent — autonomous Stake.com session runner",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- validate ----
    val_p = sub.add_parser("validate", help="Validate a config file and exit (no network)")
    val_p.add_argument("--config", required=True, metavar="FILE")

    # ---- preflight ----
    pre_p = sub.add_parser("preflight", help="Verify Stake auth and print session summary")
    pre_p.add_argument("--config", required=True, metavar="FILE")

    # ---- run ----
    run_p = sub.add_parser("run", help="Run a betting session")
    run_p.add_argument("--config", required=True, metavar="FILE")
    run_p.add_argument(
        "--db", default=None, metavar="FILE",
        help="SQLite DB path (default: platform-appropriate data dir)",
    )
    run_p.add_argument(
        "--dry-run", action="store_true",
        help="Simulate bets without placing them (no real money at risk)",
    )
    run_p.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip the pre-run confirmation prompt",
    )

    args = parser.parse_args()

    try:
        cfg = _load_config_with_prompt(args.config)
    except FileNotFoundError as e:
        _console.print(f"[red]config not found:[/] {e}", highlight=False)
        return 2
    except (ValidationError, ValueError) as e:
        _console.print(f"[red]config error:[/] {e}", highlight=False)
        return 2
    except SystemExit as e:
        return int(e.code)

    # ------------------------------------------------------------------
    # validate
    # ------------------------------------------------------------------
    if args.command == "validate":
        s = cfg.session
        _console.print(f"[green]config OK:[/] {args.config}")
        _console.print(f"  currency={s.currency}  persona={s.persona}  games={s.games_enabled}")
        _console.print(f"  top_target_usd={s.top_target_usd}  secondary_target_usd={s.secondary_target_usd}")
        _console.print(f"  stop_loss={'on (' + s.stop_loss.mode + ')' if s.stop_loss.enabled else 'off'}")
        return 0

    # ------------------------------------------------------------------
    # preflight
    # ------------------------------------------------------------------
    if args.command == "preflight":
        try:
            asyncio.run(run_preflight(cfg, console=_console))
        except StakeAuthError as e:
            _console.print(f"[red]auth error:[/] {e}", highlight=False)
            return 1
        except StakeAPIError as e:
            _console.print(f"[red]API error:[/] {e}", highlight=False)
            return 1
        except KeyboardInterrupt:
            return 130
        return 0

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------
    if args.command == "run":
        if args.dry_run:
            _console.print("[yellow]DRY RUN — no real bets will be placed[/]")

        # Pre-run preflight (always runs; also shows the warning if already at target)
        try:
            asyncio.run(run_preflight(cfg, console=_console))
        except StakeAuthError as e:
            _console.print(f"[red]auth error:[/] {e}", highlight=False)
            return 1
        except StakeAPIError as e:
            _console.print(f"[red]API error:[/] {e}", highlight=False)
            return 1
        except KeyboardInterrupt:
            return 130

        if not args.yes and not args.dry_run:
            try:
                _console.print("Press [bold]Enter[/] to begin betting, [bold]Ctrl-C[/] to abort … ",
                                end="")
                input()
            except (KeyboardInterrupt, EOFError):
                _console.print("\n[dim]aborted[/]")
                return 130

        orch = Orchestrator(cfg, db_path=args.db, dry_run=args.dry_run)
        try:
            end_reason = asyncio.run(orch.run())
        except StakeAuthError as e:
            _console.print(f"\n[red]auth error mid-session:[/] {e}", highlight=False)
            return 1
        except StakeAPIError as e:
            _console.print(f"\n[red]API error mid-session:[/] {e}", highlight=False)
            return 1
        except KeyboardInterrupt:
            _console.print("\n[dim]session interrupted[/]")
            return 130
        _console.print(f"[bold]session ended:[/] {end_reason}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
