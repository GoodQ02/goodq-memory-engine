from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from steps.common.atomic_io import atomic_write_json

SUPPORTED_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
SUPPORTED_AUDIO = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}
SUPPORTED_IMAGE = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
SUPPORTED_DOCUMENT = {".pdf", ".txt", ".md", ".doc", ".docx"}
SUPPORTED_INGEST_EXTENSIONS = (
    SUPPORTED_VIDEO | SUPPORTED_AUDIO | SUPPORTED_IMAGE | SUPPORTED_DOCUMENT
)
DEFAULT_WATCHDOG_DETECTION_WINDOW_SECONDS = 5
DEFAULT_PICKUP_ESTIMATE = "best_effort"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_file_hash(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_supported_ingest_path(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_INGEST_EXTENSIONS


def count_supported_inbox_items(import_inbox: Path) -> int:
    if not import_inbox.exists():
        return 0
    return sum(
        1
        for item in import_inbox.iterdir()
        if item.is_file()
        and not item.name.startswith(".")
        and not item.name.startswith("PROCESSED_")
        and not item.name.startswith("FAILED_")
        and is_supported_ingest_path(item)
    )


def load_watchdog_registry(watchdog_state_file: Path) -> Dict[str, Dict[str, Any]]:
    if not watchdog_state_file.exists():
        return {}
    try:
        return json.loads(watchdog_state_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


class IngestRequestLedger:
    def __init__(self, requests_dir: Path | str):
        self.requests_dir = Path(requests_dir)
        self.requests_dir.mkdir(parents=True, exist_ok=True)

    def allocate_request_id(self) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"ingest_{stamp}_{uuid.uuid4().hex[:8]}"

    def record_path(self, request_id: str) -> Path:
        return self.requests_dir / f"{request_id}.json"

    def create_record(
        self,
        *,
        source_path: Path,
        staged_path: Optional[Path],
        file_hash: str,
        confirmation_token_present: bool,
        policy_profile: str,
        queue_depth_snapshot: int,
        watchdog_detection_window_seconds: int,
        budget_scope: str,
        budget_status: str,
        request_id: Optional[str] = None,
        duplicate_of_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_request_id = request_id or self.allocate_request_id()
        created_at = utc_now_iso()
        record: Dict[str, Any] = {
            "request_id": resolved_request_id,
            "status": "duplicate" if duplicate_of_run_id else "staged",
            "source_path": str(source_path),
            "original_name": source_path.name,
            "staged_path": str(staged_path) if staged_path else None,
            "staged_name": staged_path.name if staged_path else None,
            "file_hash": file_hash,
            "policy_profile": policy_profile,
            "confirmation_token_present": confirmation_token_present,
            "queue_depth_snapshot": queue_depth_snapshot,
            "watchdog_detection_window_seconds": watchdog_detection_window_seconds,
            "pickup_estimate": DEFAULT_PICKUP_ESTIMATE,
            "budget_scope": budget_scope,
            "budget_status": budget_status,
            "duplicate_of_run_id": duplicate_of_run_id,
            "created_at": created_at,
            "last_updated_at": created_at,
        }
        atomic_write_json(self.record_path(resolved_request_id), record)
        return record

    def load(self, request_id: str) -> Optional[Dict[str, Any]]:
        path = self.record_path(request_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def resolve_ingest_request_status(
    record: Dict[str, Any],
    runtime_paths: Dict[str, Path],
) -> Dict[str, Any]:
    resolved = dict(record)
    resolved["last_observed_at"] = utc_now_iso()
    resolved["pickup_estimate"] = record.get("pickup_estimate") or DEFAULT_PICKUP_ESTIMATE

    if record.get("status") == "duplicate":
        resolved["status"] = "duplicate"
        return resolved

    file_hash = str(record.get("file_hash") or "")
    registry = load_watchdog_registry(runtime_paths["watchdog_state_file"])
    registry_entry = registry.get(file_hash) if file_hash else None
    if registry_entry:
        registry_status = str(registry_entry.get("status") or "").lower()
        if registry_status == "success":
            resolved["status"] = "completed"
        elif registry_status == "failed":
            resolved["status"] = "failed"
        else:
            resolved["status"] = registry_status or "completed"
        resolved["run_id"] = registry_entry.get("run_id")
        resolved["error"] = registry_entry.get("error")
        resolved["completed_at"] = registry_entry.get("timestamp")
        return resolved

    staged_name = record.get("staged_name")
    if staged_name:
        processing_copy = runtime_paths["processing"] / staged_name
        if processing_copy.exists():
            resolved["status"] = "processing"
            return resolved

    staged_path_value = record.get("staged_path")
    if staged_path_value and Path(staged_path_value).exists():
        resolved["status"] = "waiting_for_watchdog"
        return resolved

    if staged_name:
        if (runtime_paths["processed"] / f"PROCESSED_{staged_name}").exists():
            resolved["status"] = "completed"
            return resolved
        if (runtime_paths["failed"] / f"FAILED_{staged_name}").exists():
            resolved["status"] = "failed"
            return resolved

    resolved["status"] = "orphaned"
    return resolved
