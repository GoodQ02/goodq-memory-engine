from __future__ import annotations

import argparse
import contextlib
import io
import json
from typing import Any, Dict, Iterable, Optional, Tuple

from lib.persistent_store_alignment import build_persistent_store_alignment


def _load_configs() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        from steps.common.config_loader import load_configs

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            cfg = load_configs({})
        noise = buf.getvalue().strip() or None
        if not isinstance(cfg, dict):
            return None, f"load_configs returned {type(cfg)}"
        return cfg, noise
    except Exception as exc:
        return None, str(exc)


def _cfg_paths(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}


def _render_human(report: Dict[str, Any]) -> str:
    canonical = report.get("canonical") if isinstance(report, dict) else {}
    memory = report.get("memory") if isinstance(report, dict) else {}
    kg = report.get("knowledge_graph") if isinstance(report, dict) else {}
    alignment = report.get("alignment") if isinstance(report, dict) else {}
    boundary = report.get("safety_boundary") if isinstance(report, dict) else {}

    lines = [
        "GoodQ Persistent Store Alignment Audit",
        f"Status: {report.get('status', 'unknown')}",
        f"Canonical scenes: {alignment.get('canonical_scene_count', 0)} across {canonical.get('video_count', 0)} video(s)",
        (
            "Memory: "
            f"present={memory.get('scene_rows_present', 0)} "
            f"missing={memory.get('missing_scene_count', 0)} "
            f"segments={memory.get('segment_rows', 0)}"
        ),
        (
            "Knowledge Graph: "
            f"present={kg.get('scene_rows_present', 0)} "
            f"missing={kg.get('missing_scene_count', 0)} "
            f"media_nodes={kg.get('media_nodes', 0)} "
            f"node_media_links={kg.get('node_media_links', 0)}"
        ),
        "Current-run vector proof: not inferred from persistent scene presence.",
        (
            "Safety: "
            f"read_only={boundary.get('read_only') is True} "
            f"databases_mutated={boundary.get('databases_mutated') is True} "
            f"ingestion_triggered={boundary.get('ingestion_triggered') is True}"
        ),
    ]
    warnings = alignment.get("warnings") if isinstance(alignment, dict) else None
    if warnings:
        lines.append("Warnings:")
        for warning in warnings[:12]:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only persistent store alignment audit")
    parser.add_argument("--scene-results", required=True, help="Existing scene_ingest_results.json to inspect")
    parser.add_argument("--memory-db", help="Existing memory.db path. Defaults to configured path when omitted.")
    parser.add_argument("--knowledge-graph-db", help="Existing knowledge_graph.db path. Defaults to configured path when omitted.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg = None
    if not args.memory_db or not args.knowledge_graph_db:
        cfg, _ = _load_configs()
    paths = _cfg_paths(cfg)

    report = build_persistent_store_alignment(
        scene_results_path=args.scene_results,
        memory_db_path=args.memory_db or paths.get("db_path"),
        knowledge_graph_db_path=args.knowledge_graph_db or paths.get("knowledge_graph_db"),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(_render_human(report))
    return 0 if report.get("status") in {"ok", "warn", "empty"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
