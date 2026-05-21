from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

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
_INTERRUPTED_CONFIG_FILES = (
    Path("_resolved_config.json"),
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
        if root_log.is_file():
            root_payload = _load_json(root_log)
            if not isinstance(root_payload, dict):
                continue
            runs.append(_build_run_index_entry(candidate, root_payload, root_log))
            continue

        scene_results_path = candidate / "output" / "scene_ingest_results.json"
        if scene_results_path.is_file():
            scene_results_payload = _load_json_any(scene_results_path)
            runs.append(_build_standalone_scene_results_entry(candidate, scene_results_payload, scene_results_path))
            continue

        interrupted_config_path = _find_interrupted_config(candidate)
        if interrupted_config_path is not None:
            interrupted_payload = _load_json(interrupted_config_path) or {}
            runs.append(_build_interrupted_ingestion_entry(candidate, interrupted_payload, interrupted_config_path))

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


def _load_json_any(path: Path) -> Any:
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
        "run_kind": "structured_experiment",
        "scope": "experiment_log",
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


def _build_standalone_scene_results_entry(run_root: Path, payload: Any, scene_results_path: Path) -> Dict[str, Any]:
    scene_count = _count_scene_results(payload)
    video_names = _scene_results_video_names(payload)
    episode = video_names[0] if len(video_names) == 1 else f"{len(video_names)} videos" if video_names else "Standalone scene results"

    return {
        "run_id": run_root.name,
        "run_kind": "standalone_scene_results",
        "scope": "scene_ingest_results",
        "run_root": str(run_root),
        "root_log_path": None,
        "scene_results_path": str(scene_results_path),
        "status": "completed" if scene_count > 0 else "unknown",
        "epoch": None,
        "source_dir": None,
        "started_at": None,
        "episodes_total": 1 if scene_count > 0 else 0,
        "episodes_completed": 1 if scene_count > 0 else 0,
        "episodes_failed": 0,
        "episodes_running": 0,
        "episodes_pending": 0,
        "scenes_processed": scene_count,
        "latest_episode": {
            "episode": episode,
            "status": "completed" if scene_count > 0 else "unknown",
            "run_dir": str(run_root),
            "scene_count": scene_count,
            "files_read": [str(scene_results_path)],
            "canonical_episode_artifacts": [],
            "errors": [],
            "warnings": [],
        },
        "_sort_ts": scene_results_path.stat().st_mtime,
    }


def _find_interrupted_config(run_root: Path) -> Optional[Path]:
    for relative_path in _INTERRUPTED_CONFIG_FILES:
        candidate = run_root / relative_path
        if candidate.is_file():
            return candidate
    return None


def _build_interrupted_ingestion_entry(run_root: Path, payload: Dict[str, Any], config_path: Path) -> Dict[str, Any]:
    run_cfg = payload.get("run")
    if not isinstance(run_cfg, dict):
        run_cfg = {}
    paths_cfg = payload.get("paths")
    if not isinstance(paths_cfg, dict):
        paths_cfg = {}
    qdrant_cfg = payload.get("qdrant")
    if not isinstance(qdrant_cfg, dict):
        qdrant_cfg = {}
    qdrant_collections = _normalized_collection_map(qdrant_cfg.get("collections"))

    runtime_run_id = _first_text(
        run_cfg.get("id"),
        run_cfg.get("run_id"),
        payload.get("runtime_run_id"),
        payload.get("run_id"),
    )
    epoch = _first_text(run_cfg.get("epoch"), payload.get("epoch"))
    source_dir = _first_text(run_cfg.get("source_dir"), payload.get("source_dir"))
    started_at = _first_text(run_cfg.get("started_at"), payload.get("started_at"), payload.get("ts_utc"))

    latest_episode = {
        "episode": run_root.name,
        "status": "interrupted",
        "run_dir": str(run_root),
        "scene_count": 0,
        "files_read": [str(config_path)],
        "canonical_episode_artifacts": [],
        "errors": [],
        "warnings": ["final_scene_ingest_results_missing"],
    }

    return {
        "run_id": run_root.name,
        "runtime_run_id": runtime_run_id,
        "run_kind": "interrupted_ingestion",
        "scope": "resolved_config_only",
        "run_root": str(run_root),
        "root_log_path": None,
        "config_path": str(config_path),
        "status": "interrupted",
        "epoch": epoch,
        "source_dir": source_dir,
        "started_at": started_at,
        "data_root": _first_text(paths_cfg.get("data_root")),
        "qdrant_collections": qdrant_collections,
        "episodes_total": 1,
        "episodes_completed": 0,
        "episodes_failed": 0,
        "episodes_running": 0,
        "episodes_pending": 0,
        "scenes_processed": 0,
        "latest_episode": latest_episode,
        "_sort_ts": config_path.stat().st_mtime,
    }


def _iter_scene_result_items(payload: Any) -> Iterator[Dict[str, Any]]:
    if isinstance(payload, dict):
        yield payload
        return
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item


def _count_scene_results(payload: Any) -> int:
    if isinstance(payload, list) and all(isinstance(item, dict) and not isinstance(item.get("scenes"), list) for item in payload):
        return len(payload)

    total = 0
    for item in _iter_scene_result_items(payload):
        scenes = item.get("scenes")
        if isinstance(scenes, list):
            total += len([scene for scene in scenes if isinstance(scene, dict)])
    return total


def _scene_results_video_names(payload: Any) -> List[str]:
    names: List[str] = []
    for item in _iter_scene_result_items(payload):
        value = item.get("video_name") or item.get("episode") or item.get("video_id")
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in names:
            names.append(text)
    return names


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalized_collection_map(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw, dict):
            raw = raw.get("name")
        text = _first_text(raw)
        if text:
            out[key] = text
    return out


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
