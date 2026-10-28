import argparse
from pathlib import Path

from codex_usage_audit.audit import run_audit

DEMO_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "sessions"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag meter cliffs in Codex CLI session logs."
    )
    parser.add_argument(
        "--sessions", type=Path, default=Path.home() / ".codex" / "sessions"
    )
    parser.add_argument(
        "--threshold", type=float, default=5.0, help="points per reading"
    )
    parser.add_argument(
        "--max-gap",
        type=float,
        default=60.0,
        help="minutes between readings that still count as sudden",
    )
    parser.add_argument(
        "--demo", action="store_true", help="use the bundled fixture logs"
    )
    args = parser.parse_args(argv)
    sessions = DEMO_DIR if args.demo else args.sessions
    print(run_audit(sessions, threshold=args.threshold, max_gap_minutes=args.max_gap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
