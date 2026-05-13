from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.identity_ledger import (
    build_identity_ledger,
    rebuild_identity_graph_from_manifests,
    write_identity_ledger_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a clean identity ledger from persisted scene manifests.")
    parser.add_argument(
        "--processing-root",
        default=os.environ.get("GOODQ_PROCESSING_ROOT", ""),
        help="Root processing directory containing per-episode folders. Defaults to GOODQ_PROCESSING_ROOT.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "reports" / "identity_control" / "season_control"),
        help="Directory for the rebuilt control graph and ledger outputs.",
    )
    parser.add_argument(
        "--episode-prefix",
        default="01x",
        help="Episode directory prefix to include.",
    )
    args = parser.parse_args()

    if not args.processing_root:
        parser.error("--processing-root or GOODQ_PROCESSING_ROOT is required")

    processing_root = Path(args.processing_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    graph_db_path = output_dir / "season_identity_control.db"
    ledger_json_path = output_dir / "season_identity_ledger_control.json"
    ledger_md_path = output_dir / "season_identity_ledger_control.md"
    rebuild_json_path = output_dir / "season_identity_rebuild_summary.json"

    rebuild_summary = rebuild_identity_graph_from_manifests(
        processing_root=processing_root,
        graph_db_path=graph_db_path,
        episode_prefix=args.episode_prefix,
    )
    ledger = build_identity_ledger(
        graph_db_path=graph_db_path,
        scene_episode_map=rebuild_summary["scene_episode_map"],
        episodes=rebuild_summary["episodes"],
    )

    rebuild_json_path.write_text(json.dumps(rebuild_summary, indent=2), encoding="utf-8")
    ledger_json_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    write_identity_ledger_markdown(ledger, ledger_md_path)

    print(f"REBUILD_SUMMARY={rebuild_json_path}")
    print(f"LEDGER_JSON={ledger_json_path}")
    print(f"LEDGER_MD={ledger_md_path}")
    print(f"GRAPH_DB={graph_db_path}")


if __name__ == "__main__":
    main()
