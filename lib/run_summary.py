from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib import run_index

logger = logging.getLogger(__name__)


def load_run_summary(run_root: str | Path, reports_root: str | Path | None = None) -> Dict[str, Any]:
    root_path = _resolve_run_root(run_root=run_root, reports_root=reports_root)
    effective_reports_root = run_index.resolve_reports_root(reports_root=root_path.parent)
    root_log = root_path / "experiment_log.json"
    payload = _load_json(root_log)
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"Run root is missing a readable experiment log: {root_path}")

    plan = payload.get("plan")
    if not isinstance(plan, list):
        plan = []

    files_read: List[str] = [str(root_log)]
    canonical_episode_artifacts: List[str] = []
    episode_records: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []
    scenes_processed = 0
    latest_episode_record: Optional[Dict[str, Any]] = None
    latest_episode_ts: Optional[str] = None

    for item in plan:
        record = _load_episode_record(item)
        if record is None:
            continue
        episode_records.append(record)
        files_read.append(record["record_path"])
        files_read.extend(record["files_read"])
        canonical_episode_artifacts.extend(record["canonical_episode_artifacts"])
        scenes_processed += record["scene_count"]
        errors.extend(record["errors"])
        warnings.extend(record["warnings"])
        if record.get("ts_utc") and _is_newer(record["ts_utc"], latest_episode_ts):
            latest_episode_ts = record["ts_utc"]
            latest_episode_record = record

    index_entries = run_index.list_runs(reports_root=effective_reports_root)
    index_entry = next((entry for entry in index_entries if entry["run_id"] == root_path.name), None)
    if index_entry is None:
        index_entry = {
            "run_id": root_path.name,
            "status": str(payload.get("status") or "unknown"),
            "epoch": payload.get("epoch"),
            "source_dir": payload.get("source_dir"),
            "started_at": payload.get("ts_utc"),
            "episodes_total": len(plan),
            "episodes_completed": 0,
            "episodes_failed": 0,
            "episodes_running": 0,
            "episodes_pending": len(plan),
            "latest_episode": None,
        }

    outcome_status = _classify_outcome(index_entry=index_entry, root_status=str(payload.get("status") or "unknown"))
    end_time = latest_episode_ts if outcome_status != "running" else "unknown"
    duration = _duration_seconds(index_entry.get("started_at"), end_time if isinstance(end_time, str) else None)

    latest_episode = latest_episode_record or index_entry.get("latest_episode")
    indexed_latest = index_entry.get("latest_episode")
    if isinstance(indexed_latest, dict):
        indexed_status = str(indexed_latest.get("status") or "").strip().lower()
        if indexed_status in {"pending", "running", "queued", "active", "started"}:
            latest_episode = indexed_latest

    summary = {
        "run_header": {
            "run_id": index_entry["run_id"],
            "epoch": index_entry.get("epoch"),
            "status": index_entry.get("status"),
            "source_dir": index_entry.get("source_dir"),
            "start_time": index_entry.get("started_at"),
            "end_time": end_time,
            "total_duration_seconds": duration if duration is not None else "unknown",
            "trigger_source": payload.get("trigger_source") or "unknown",
        },
        "file_job_overview": {
            "input_files": [item.get("episode") for item in plan if item.get("episode")],
            "episodes_total": index_entry.get("episodes_total", len(plan)),
            "episodes_completed": index_entry.get("episodes_completed", 0),
            "episodes_failed": index_entry.get("episodes_failed", 0),
            "episodes_running": index_entry.get("episodes_running", 0),
            "episodes_pending": index_entry.get("episodes_pending", 0),
            "scenes_processed": scenes_processed,
            "steps_executed": "unknown",
        },
        "audio_wsl2_summary": {
            "jobs_found": "unknown",
            "notes": "not observed",
        },
        "agent_activity": [],
        "errors_warnings": {
            "errors": errors,
            "warnings": warnings,
        },
        "outcome_classification": {
            "status": outcome_status,
        },
        "evidence": {
            "files_read": _dedupe_preserve_order(files_read),
            "canonical_episode_artifacts": _dedupe_preserve_order(canonical_episode_artifacts),
        },
        "latest_episode": latest_episode,
        "episodes": episode_records,
    }
    return summary


def _resolve_run_root(run_root: str | Path, reports_root: str | Path | None = None) -> Path:
    candidate = Path(str(run_root))
    if candidate.is_absolute():
        return candidate
    return run_index.resolve_reports_root(reports_root=reports_root) / candidate


def _load_json(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("run_summary failed to parse path=%s error=%s", path, exc)
        return None


def _load_episode_record(plan_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    run_dir_value = plan_item.get("run_dir")
    if not isinstance(run_dir_value, str) or not run_dir_value.strip():
        return None

    run_dir = Path(run_dir_value)
    record_path = run_dir / "experiment_log.json"
    if not record_path.is_file():
        return None
    payload = _load_json(record_path)
    if not isinstance(payload, dict):
        return None

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    common = metrics.get("common")
    if not isinstance(common, dict):
        common = {}

    files_read: List[str] = []
    canonical_episode_artifacts: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []

    for key in ("output_path", "temporal_index_path", "scene_manifest_path"):
        value = metrics.get(key)
        if isinstance(value, str) and value.strip():
            files_read.append(value)
            if key in {"temporal_index_path", "scene_manifest_path"}:
                canonical_episode_artifacts.append(value)
                if not Path(value).is_file():
                    warnings.append(f"Canonical artifact missing: {value}")

    status = str(payload.get("status") or plan_item.get("status") or "unknown")
    if status.strip().lower() in {"failed", "error"}:
        errors.append(f"Episode failed: {plan_item.get('episode')}")

    return {
        "episode": plan_item.get("episode") or payload.get("episode"),
        "status": status,
        "run_dir": str(run_dir),
        "record_path": str(record_path),
        "ts_utc": payload.get("ts_utc"),
        "scene_count": int(common.get("scene_count") or 0),
        "phase6_complete": bool(common.get("phase6_complete")),
        "qdrant_ok": common.get("qdrant_ok"),
        "files_read": files_read,
        "canonical_episode_artifacts": canonical_episode_artifacts,
        "errors": errors,
        "warnings": warnings,
    }


def _classify_outcome(index_entry: Dict[str, Any], root_status: str) -> str:
    status = str(root_status or index_entry.get("status") or "unknown").strip().lower()
    completed = int(index_entry.get("episodes_completed") or 0)
    failed = int(index_entry.get("episodes_failed") or 0)
    running = int(index_entry.get("episodes_running") or 0)
    pending = int(index_entry.get("episodes_pending") or 0)

    if status == "running" or running > 0 or pending > 0:
        return "running"
    if completed > 0 and failed > 0:
        return "partial_success"
    if failed > 0 and completed == 0:
        return "failed"
    if completed > 0:
        return "success"
    return "unknown"


def _is_newer(candidate: str, current: Optional[str]) -> bool:
    if current is None:
        return True
    candidate_dt = _parse_iso(candidate)
    current_dt = _parse_iso(current)
    if candidate_dt is None:
        return False
    if current_dt is None:
        return True
    return candidate_dt > current_dt


def _duration_seconds(start_time: Any, end_time: Optional[str]) -> Optional[float]:
    start_dt = _parse_iso(start_time) if isinstance(start_time, str) else None
    end_dt = _parse_iso(end_time) if isinstance(end_time, str) else None
    if start_dt is None or end_dt is None:
        return None
    return round((end_dt - start_dt).total_seconds(), 2)


def _parse_iso(value: str | None) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip() or value == "unknown":
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
