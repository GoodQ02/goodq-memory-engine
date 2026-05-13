"""
GoodQ Control Recurrence Report (read-only).

Invoke:
  python -m cli.control_recurrence_report
  python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --json
  python -m cli.control_recurrence_report --baseline-run-id 20260424_003250_season1_recompare_witness --candidate-run-id 20260424_182406_season2_fresh_witness
  python -m cli.control_recurrence_report --run-id 20260424_182406_season2_fresh_witness --write-md
  python -m cli.control_recurrence_report --list-reports
  python -m cli.control_recurrence_report --recommendations-for 20260424_182406_season2_fresh_witness
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

from lib.control_recurrence_report import (
    build_control_recurrence_comparison,
    build_control_recurrence_report,
    read_report_index,
    render_report_index,
    render_text_comparison,
    render_text_report,
    report_index_path,
    update_report_index,
    write_json_report_file,
    write_markdown_report,
)
from lib.control_recurrence_recommendations import (
    build_recommendation_draft,
    render_recommendation_draft,
)


os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GoodQ Control Recurrence Report (read-only)")
    parser.add_argument("--run-root", help="Path to a reports/fresh_ingest_runs/<run> directory")
    parser.add_argument("--run-id", help="Run directory name under reports/fresh_ingest_runs")
    parser.add_argument("--baseline-run-root", help="Baseline reports/fresh_ingest_runs/<run> directory")
    parser.add_argument("--baseline-run-id", help="Baseline run directory name under reports/fresh_ingest_runs")
    parser.add_argument("--candidate-run-root", help="Candidate reports/fresh_ingest_runs/<run> directory")
    parser.add_argument("--candidate-run-id", help="Candidate run directory name under reports/fresh_ingest_runs")
    parser.add_argument("--reports-root", help="Override reports/fresh_ingest_runs root")
    parser.add_argument("--limit-runs", type=int, default=1, help="Latest report roots to scan when no run is specified")
    parser.add_argument("--step-runs", help="Explicit step_runs.jsonl path")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--limit", type=int, default=12, help="Maximum rows per text section")
    parser.add_argument("--write-md", action="store_true", help="Write deterministic markdown operator artifact")
    parser.add_argument("--write-json-file", action="store_true", help="Write durable JSON operator artifact")
    parser.add_argument("--list-reports", action="store_true", help="List indexed durable recurrence reports")
    parser.add_argument("--recommendations-for", help="Build a read-only recommendation draft for an indexed report id")
    parser.add_argument("--output-dir", help="Artifact output directory (default: reports/control_recurrence)")
    args = parser.parse_args(list(argv) if argv is not None else None)
    output_dir = Path(args.output_dir) if args.output_dir else None

    if args.recommendations_for:
        draft, status_code = build_recommendation_draft(args.recommendations_for, base_dir=output_dir)
        if args.json:
            print(json.dumps(draft, indent=2, ensure_ascii=False))
        else:
            print(render_recommendation_draft(draft))
        return 0 if status_code == 200 and draft.get("status") == "ok" else 2

    if args.list_reports:
        index = read_report_index(output_dir=output_dir)
        if args.json:
            print(json.dumps(index, indent=2, ensure_ascii=False))
        else:
            print(render_report_index(index))
        return 0

    comparison_requested = any(
        (
            args.baseline_run_root,
            args.baseline_run_id,
            args.candidate_run_root,
            args.candidate_run_id,
        )
    )

    try:
        if comparison_requested:
            if not (args.baseline_run_root or args.baseline_run_id):
                print("FAIL: comparison mode requires --baseline-run-id or --baseline-run-root", file=sys.stderr)
                return 2
            if not (args.candidate_run_root or args.candidate_run_id):
                print("FAIL: comparison mode requires --candidate-run-id or --candidate-run-root", file=sys.stderr)
                return 2
            report = build_control_recurrence_comparison(
                baseline_run_root=Path(args.baseline_run_root) if args.baseline_run_root else None,
                baseline_run_id=args.baseline_run_id,
                candidate_run_root=Path(args.candidate_run_root) if args.candidate_run_root else None,
                candidate_run_id=args.candidate_run_id,
                reports_root=Path(args.reports_root) if args.reports_root else None,
            )
            if args.write_md:
                md_path = write_markdown_report(report, output_dir=output_dir)
                print(f"Markdown written: {md_path}", file=sys.stderr)
            if args.write_json_file:
                json_path = write_json_report_file(report, output_dir=output_dir)
                print(f"JSON written: {json_path}", file=sys.stderr)
            if args.write_md or args.write_json_file:
                update_report_index(output_dir=output_dir)
                print(f"Index written: {report_index_path(output_dir=output_dir)}", file=sys.stderr)
            if args.json:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                print(render_text_comparison(report, limit=max(1, int(args.limit or 12))))
            return 0

        report = build_control_recurrence_report(
            run_root=Path(args.run_root) if args.run_root else None,
            run_id=args.run_id,
            reports_root=Path(args.reports_root) if args.reports_root else None,
            limit_runs=max(1, int(args.limit_runs or 1)),
            step_runs_path=Path(args.step_runs) if args.step_runs else None,
        )
        if args.write_md:
            md_path = write_markdown_report(report, output_dir=output_dir)
            print(f"Markdown written: {md_path}", file=sys.stderr)
        if args.write_json_file:
            json_path = write_json_report_file(report, output_dir=output_dir)
            print(f"JSON written: {json_path}", file=sys.stderr)
        if args.write_md or args.write_json_file:
            update_report_index(output_dir=output_dir)
            print(f"Index written: {report_index_path(output_dir=output_dir)}", file=sys.stderr)
    except Exception as exc:
        print(f"FAIL: recurrence report failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_text_report(report, limit=max(1, int(args.limit or 12))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
