from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REPORTS_ROOT = _REPO_ROOT / "reports" / "fresh_ingest_runs"

_COMPLETED_STATUSES = {"passed", "completed", "success"}
_FAILED_STATUSES = {"failed", "error"}
_RUNNING_STATUSES = {"running", "started", "active"}
_PENDING_STATUSES = {"pending", "queued"}
_ACTIVITY_FILES = (
    Path("ingest.stdout.log"),
    Path("ingest.stderr.log"),
    Path("workspace") / "_resolved_config.json",
)


def resolve_reports_root(reports_root: str | Path | None = None) -> Path:
    explicit = reports_root or os.environ.get("GOODQ_RUN_REPORTS_ROOT")
    if explicit:
        return Path(str(explicit))
    return _DEFAULT_REPORTS_ROOT


def get_run_root(run_id: str, reports_root: str | Path | None = None) -> Path:
    return resolve_reports_root(reports_root=reports_root) / run_id


def list_runs(reports_root: str | Path | None = None, limit: int | None = None) -> List[Dict[str, Any]]:
    root = resolve_reports_root(reports_root=reports_root)
    if not root.exists():
        return []

    runs: List[Dict[str, Any]] = []
    for candidate in root.iterdir():
        if not candidate.is_dir() or candidate.name.startswith("."):
            continue
        root_log = candidate / "experiment_log.json"
        if not root_log.is_file():
            continue
        root_payload = _load_json(root_log)
        if not isinstance(root_payload, dict):
            continue
        runs.append(_build_run_index_entry(candidate, root_payload, root_log))

    runs.sort(key=lambda item: (item.get("_sort_ts", 0.0), item["run_id"]), reverse=True)
    for run in runs:
        run.pop("_sort_ts", None)

    if isinstance(limit, int) and limit >= 0:
        return runs[:limit]
    return runs


def _load_json(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("run_index failed to parse path=%s error=%s", path, exc)
        return None


def _build_run_index_entry(run_root: Path, payload: Dict[str, Any], root_log: Path) -> Dict[str, Any]:
    plan = payload.get("plan")
    if not isinstance(plan, list):
        plan = []

    projected_plan = [_project_plan_item_status(item) for item in plan if isinstance(item, dict)]
    counts = _count_episode_statuses(projected_plan)
    latest_episode = _select_latest_episode(projected_plan)

    return {
        "run_id": run_root.name,
        "run_root": str(run_root),
        "root_log_path": str(root_log),
        "status": str(payload.get("status") or "unknown"),
        "epoch": payload.get("epoch"),
        "source_dir": payload.get("source_dir"),
        "started_at": payload.get("ts_utc"),
        "episodes_total": len(plan),
        "episodes_completed": counts["completed"],
        "episodes_failed": counts["failed"],
        "episodes_running": counts["running"],
        "episodes_pending": counts["pending"],
        "latest_episode": latest_episode,
        "_sort_ts": root_log.stat().st_mtime,
    }


def _count_episode_statuses(plan: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"completed": 0, "failed": 0, "running": 0, "pending": 0}
    for item in plan:
        status = str(item.get("_projected_status") or item.get("status") or "pending").strip().lower()
        if status in _COMPLETED_STATUSES:
            counts["completed"] += 1
        elif status in _FAILED_STATUSES:
            counts["failed"] += 1
        elif status in _RUNNING_STATUSES:
            counts["running"] += 1
        else:
            counts["pending"] += 1
    return counts


def _select_latest_episode(plan: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not plan:
        return None

    for item in plan:
        status = str(item.get("_projected_status") or item.get("status") or "pending").strip().lower()
        if status in _RUNNING_STATUSES or status in _PENDING_STATUSES:
            return {
                "episode": item.get("episode"),
                "status": status,
                "run_dir": item.get("run_dir"),
            }

    item = plan[-1]
    status = str(item.get("_projected_status") or item.get("status") or "unknown").strip().lower()
    return {
        "episode": item.get("episode"),
        "status": status,
        "run_dir": item.get("run_dir"),
    }


def _project_plan_item_status(item: Dict[str, Any]) -> Dict[str, Any]:
    projected = dict(item)
    status = str(item.get("status") or "pending").strip().lower()
    projected["_projected_status"] = status or "pending"

    if projected["_projected_status"] not in _PENDING_STATUSES:
        return projected

    episode_status = _read_episode_record_status(item)
    if episode_status is not None:
        projected["_projected_status"] = episode_status
        return projected

    if _has_active_lane_artifacts(item):
        projected["_projected_status"] = "running"
    return projected


def _read_episode_record_status(item: Dict[str, Any]) -> Optional[str]:
    run_dir_value = item.get("run_dir")
    if not isinstance(run_dir_value, str) or not run_dir_value.strip():
        return None

    record_path = Path(run_dir_value) / "experiment_log.json"
    if not record_path.is_file():
        return None

    payload = _load_json(record_path)
    if not isinstance(payload, dict):
        return None

    status = str(payload.get("status") or "").strip().lower()
    return status or None


def _has_active_lane_artifacts(item: Dict[str, Any]) -> bool:
    run_dir_value = item.get("run_dir")
    if not isinstance(run_dir_value, str) or not run_dir_value.strip():
        return False

    run_dir = Path(run_dir_value)
    if not run_dir.is_dir():
        return False

    for relative_path in _ACTIVITY_FILES:
        candidate = run_dir / relative_path
        if not candidate.exists():
            continue
        try:
            if candidate.stat().st_size > 0:
                return True
        except OSError:
            logger.debug("run_index failed to stat activity file path=%s", candidate)
    return False
