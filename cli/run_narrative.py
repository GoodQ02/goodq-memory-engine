from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from lib.run_narrative import render_run_narrative
from lib.run_summary import summarize_run_with_status

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a GoodQ ingestion run narrative (read-only)."
    )
    parser.add_argument("run_id", help="Run ID (UUID)")
    args = parser.parse_args()

    run_id = args.run_id.strip()
    if not UUID_RE.match(run_id):
        print("invalid run_id", file=sys.stderr)
        return 2

    summary, status = summarize_run_with_status(run_id)
    if status == "no_artifacts":
        print("no observability artifacts available", file=sys.stderr)
        return 2
    if status == "not_found":
        print("run_id not found", file=sys.stderr)
        return 2

    narrative = render_run_narrative(summary or {})
    sys.stdout.write(narrative)
    return 0


if __name__ == "__main__":
    sys.exit(main())
