from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from lib.run_summary import summarize_run_with_status

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


def _format_text(summary: Dict[str, Any]) -> str:
    header = summary.get("run_header") or {}
    overview = summary.get("file_job_overview") or {}
    errors = summary.get("errors_warnings") or {}
    outcome = summary.get("outcome_classification") or {}

    lines = [
        f"run_id: {header.get('run_id', 'unknown')}",
        f"start_time: {header.get('start_time', 'unknown')}",
        f"end_time: {header.get('end_time', 'unknown')}",
        f"total_duration_seconds: {header.get('total_duration_seconds', 'unknown')}",
        f"trigger_source: {header.get('trigger_source', 'unknown')}",
        f"input_files: {len(overview.get('input_files') or [])}",
        f"scenes_processed: {overview.get('scenes_processed', 'unknown')}",
        f"steps_executed: {overview.get('steps_executed', 0)}",
        f"errors: {len(errors.get('errors') or [])}",
        f"warnings: {len(errors.get('warnings') or [])}",
        f"outcome_status: {outcome.get('status', 'unknown')}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a GoodQ ingestion run (read-only).")
    parser.add_argument("run_id", help="Run ID (UUID)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
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

    if args.format == "text":
        print(_format_text(summary or {}))
        return 0

    if args.pretty:
        payload = json.dumps(summary, indent=2, ensure_ascii=True)
    else:
        payload = json.dumps(summary, separators=(",", ":"), ensure_ascii=True)
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
