"""GambleAgent engine entry point.

Phase 1: CLI prototype. Run with:
    python -m engine.main run --config session.yaml
"""

import argparse
import sys

from pydantic import ValidationError

from engine.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gambleagent",
        description="GambleAgent — autonomous Stake.com session runner",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a session from a config file")
    run.add_argument("--config", required=True, help="Path to session YAML config")

    validate = sub.add_parser("validate", help="Validate a config file and exit")
    validate.add_argument("--config", required=True, help="Path to session YAML config")

    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, ValidationError, ValueError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    if args.command == "validate":
        print(f"config OK: {args.config}")
        s = cfg.session
        print(f"  currency={s.currency} persona={s.persona} games={s.games_enabled}")
        print(f"  top_target_usd={s.top_target_usd} secondary_target_usd={s.secondary_target_usd}")
        print(f"  stop_loss={'on' if s.stop_loss.enabled else 'off'}")
        return 0

    if args.command == "run":
        print(f"[scaffolding] loaded config: {args.config}")
        print("[scaffolding] session loop not implemented yet (Task 1.10)")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
