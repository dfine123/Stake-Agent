"""GambleAgent engine entry point.

Phase 1: CLI prototype. Run with:
    python -m engine.main run --config session.yaml
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gambleagent",
        description="GambleAgent — autonomous Stake.com session runner",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a session from a config file")
    run.add_argument(
        "--config",
        required=True,
        help="Path to session YAML config",
    )

    args = parser.parse_args()

    if args.command == "run":
        print(f"[scaffolding] would load config: {args.config}")
        print("[scaffolding] session loop not implemented yet (Task 1.10)")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
