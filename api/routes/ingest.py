"""
Truthful ingest facade routes for GoodQ4All.
Stages requests into the canonical inbox and reports request-centric status.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body, UploadFile, File

from api.utils.ingest_requests import (
    DEFAULT_PICKUP_ESTIMATE,
    DEFAULT_WATCHDOG_DETECTION_WINDOW_SECONDS,
    IngestRequestLedger,
    compute_file_hash,
    count_supported_inbox_items,
    is_supported_ingest_path,
    load_watchdog_registry,
    resolve_ingest_request_status,
)
from api.utils.response_models import (
    IngestStatusResponse,
    IngestSubmitRequest,
    IngestSubmitResponse,
)
from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def get_ingest_runtime_paths() -> dict[str, Path]:
    cfg = load_configs({})
    runtime_paths = get_runtime_paths(
        cfg,
        "import_inbox",
        "processing",
        "processed",
        "failed",
        "watchdog_state_file",
        "ingest_requests",
        require_canonical=False,
    )
    return {key: Path(value).resolve() for key, value in runtime_paths.items()}


def get_ingest_request_ledger(
    runtime_paths: dict[str, Path] | None = None,
) -> IngestRequestLedger:
    paths = runtime_paths or get_ingest_runtime_paths()
    return IngestRequestLedger(paths["ingest_requests"])


def _ensure_local_supported_file(file_path: Path) -> None:
    if str(file_path).startswith("\\\\"):
        raise HTTPException(status_code=400, detail="Network paths are not supported")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not is_supported_ingest_path(file_path):
        raise HTTPException(status_code=400, detail="Unsupported ingest file type")


def _submit_budget_profile() -> tuple[str, str]:
    return "single_local_file_handoff", "accepted"


@router.post("/submit", response_model=IngestSubmitResponse)
async def submit_ingest(request: IngestSubmitRequest = Body(...)):
    confirmation_token = request.confirmation_token.strip()
    policy_profile = request.policy_profile.strip()
    if not confirmation_token:
        raise HTTPException(status_code=400, detail="confirmation_token is required")
    if not policy_profile:
        raise HTTPException(status_code=400, detail="policy_profile is required")

    source_path = Path(request.file_path).resolve()
    _ensure_local_supported_file(source_path)

    runtime_paths = get_ingest_runtime_paths()
    ledger = get_ingest_request_ledger(runtime_paths)
    file_hash = compute_file_hash(source_path)
    registry = load_watchdog_registry(runtime_paths["watchdog_state_file"])
    budget_scope, budget_status = _submit_budget_profile()

    existing = registry.get(file_hash)
    if existing and existing.get("status") == "success":
        record = ledger.create_record(
            source_path=source_path,
            staged_path=None,
            file_hash=file_hash,
            confirmation_token_present=True,
            policy_profile=policy_profile,
            queue_depth_snapshot=count_supported_inbox_items(runtime_paths["import_inbox"]),
            watchdog_detection_window_seconds=DEFAULT_WATCHDOG_DETECTION_WINDOW_SECONDS,
            budget_scope=budget_scope,
            budget_status=budget_status,
            duplicate_of_run_id=existing.get("run_id"),
        )
        return IngestSubmitResponse(**record)

    request_id = ledger.allocate_request_id()
    staged_path = runtime_paths["import_inbox"] / f"{request_id}__{source_path.name}"
    runtime_paths["import_inbox"].mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source_path, staged_path)
    except Exception as exc:
        logger.error("Failed to stage ingest request file=%s error=%s", source_path, exc)
        raise HTTPException(status_code=500, detail="Failed to stage ingest request") from exc

    record = ledger.create_record(
        source_path=source_path,
        staged_path=staged_path,
        file_hash=file_hash,
        confirmation_token_present=True,
        policy_profile=policy_profile,
        queue_depth_snapshot=count_supported_inbox_items(runtime_paths["import_inbox"]),
        watchdog_detection_window_seconds=DEFAULT_WATCHDOG_DETECTION_WINDOW_SECONDS,
        budget_scope=budget_scope,
        budget_status=budget_status,
        request_id=request_id,
    )
    return IngestSubmitResponse(**record)


@router.get("/status/{request_id}", response_model=IngestStatusResponse)
async def get_ingest_status(request_id: str):
    runtime_paths = get_ingest_runtime_paths()
    ledger = get_ingest_request_ledger(runtime_paths)
    record = ledger.load(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ingest request not found")
    resolved = resolve_ingest_request_status(record, runtime_paths)
    resolved.setdefault("pickup_estimate", DEFAULT_PICKUP_ESTIMATE)
    return IngestStatusResponse(**resolved)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Directly upload a media file and save it to the import inbox folder."""
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is missing")
    
    if not is_supported_ingest_path(Path(filename)):
        raise HTTPException(status_code=400, detail="Unsupported ingest file type")

    runtime_paths = get_ingest_runtime_paths()
    import_inbox = runtime_paths["import_inbox"]
    import_inbox.mkdir(parents=True, exist_ok=True)
    
    staged_path = import_inbox / filename
    try:
        with staged_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        logger.error("Failed to upload file=%s error=%s", filename, exc)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {exc}")
        
    return {"status": "success", "filename": filename, "staged_path": str(staged_path)}
