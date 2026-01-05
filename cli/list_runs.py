from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from lib.run_index import list_runs_with_cursor


def main() -> int:
    parser = argparse.ArgumentParser(description="List available GoodQ runs (read-only).")
    parser.add_argument("--limit", type=int, default=50, help="Max results (default: 50, max: 200)")
    parser.add_argument("--trigger", help="Filter by trigger (cli|watchdog|unknown)")
    parser.add_argument("--status", help="Filter by status (success|partial_success|failed|unknown)")
    parser.add_argument("--cursor", help="Cursor timestamp (ISO-8601)")
    parser.add_argument("--latest", action="store_true", help="Return only the most recent run")
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 200:
        print("limit must be between 1 and 200", file=sys.stderr)
        return 2

    try:
        runs, _ = list_runs_with_cursor(
            limit=args.limit,
            trigger=args.trigger,
            status=args.status,
            cursor=args.cursor,
            latest=args.latest,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(runs, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
