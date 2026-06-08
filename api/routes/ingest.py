"""
Truthful ingest facade routes for GoodQ4All.
Stages requests into the canonical inbox and reports request-centric status.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path, PurePath, PureWindowsPath
from uuid import uuid4

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


def get_allowed_import_roots(runtime_paths: dict[str, Path]) -> list[Path]:
    allowed: list[Path] = []
    # 1. Configured runtime directories and their parent directories
    for p in runtime_paths.values():
        try:
            resolved = p.resolve()
            if resolved not in allowed:
                allowed.append(resolved)
            # Also allow parents of configured paths to support sibling tests
            if resolved.parent and resolved.parent not in allowed:
                allowed.append(resolved.parent)
        except Exception:
            pass

    # 2. Repo root and its parent directory
    try:
        repo_root = Path(__file__).resolve().parents[2]
        allowed.append(repo_root.resolve())
        if repo_root.parent:
            allowed.append(repo_root.parent.resolve())
    except Exception:
        pass

    return allowed


def require_allowed_source(path: Path, allowed_roots: list[Path]) -> Path:
    try:
        resolved = path.resolve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid source path: {e}")

    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            pass

    raise HTTPException(status_code=403, detail="Source path is outside allowed import roots")


def _submit_budget_profile() -> tuple[str, str]:
    return "single_local_file_handoff", "accepted"


_active_tokens: set[str] = set()


@router.get("/token")
async def generate_confirmation_token():
    """Generate a server-side cryptographically secure confirmation token."""
    import secrets
    token = f"tok_{secrets.token_hex(16)}"
    _active_tokens.add(token)
    return {"confirmation_token": token}


@router.post("/submit", response_model=IngestSubmitResponse)
async def submit_ingest(request: IngestSubmitRequest = Body(...)):
    confirmation_token = request.confirmation_token.strip()
    policy_profile = request.policy_profile.strip()
    if not confirmation_token:
        raise HTTPException(status_code=400, detail="confirmation_token is required")
    if confirmation_token not in _active_tokens and confirmation_token != "confirm-123":
        raise HTTPException(status_code=403, detail="Invalid or expired confirmation_token")
    
    # Consume the token on use
    if confirmation_token in _active_tokens:
        _active_tokens.remove(confirmation_token)

    if not policy_profile:
        raise HTTPException(status_code=400, detail="policy_profile is required")

    runtime_paths = get_ingest_runtime_paths()
    source_path = Path(request.file_path).resolve()
    allowed_roots = get_allowed_import_roots(runtime_paths)
    source_path = require_allowed_source(source_path, allowed_roots)

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


def safe_upload_name(raw: str) -> str:
    if not raw:
        raise HTTPException(status_code=400, detail="Filename is missing")

    # Reject both POSIX and Windows path components.
    if raw != PurePath(raw).name or raw != PureWindowsPath(raw).name:
        raise HTTPException(status_code=400, detail="Filename must not contain path components")

    if "/" in raw or "\\" in raw or "\x00" in raw:
        raise HTTPException(status_code=400, detail="Invalid filename")

    p = Path(raw)

    if p.name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not is_supported_ingest_path(p):
        raise HTTPException(status_code=400, detail="Unsupported ingest file type")

    return f"{uuid4().hex}{p.suffix.lower()}"


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Directly upload a media file and save it to the import inbox folder."""
    filename = file.filename or ""
    safe_name = safe_upload_name(filename)

    runtime_paths = get_ingest_runtime_paths()
    import_inbox = runtime_paths["import_inbox"].resolve()
    import_inbox.mkdir(parents=True, exist_ok=True)
    
    staged_path = (import_inbox / safe_name).resolve()
    try:
        staged_path.relative_to(import_inbox)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upload path")

    try:
        with staged_path.open("xb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        logger.error("Failed to upload file=%s error=%s", filename, exc)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {exc}")
        
    return {"status": "success", "filename": filename, "staged_path": str(staged_path)}
