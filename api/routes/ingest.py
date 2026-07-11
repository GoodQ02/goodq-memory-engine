"""Governed local ingest request staging.

The API may prepare and authorize a request, but Watchdog remains the canonical
execution owner. No file is exposed to the watched inbox before an exact-scope
operator confirmation is atomically claimed.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any, BinaryIO, Type
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from agents.mini_agent_client import MiniAgentClient, ReentrantFileLock
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
    INGEST_REQUEST_ID_PATTERN,
    IngestCancelRequest,
    IngestConfirmRequest,
    IngestPrepareRequest,
    IngestStatusResponse,
    IngestSubmitResponse,
)
from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

AUTHORIZATION_OPERATION = "stage_ingest_request"
AUTHORIZATION_TTL_SECONDS = 600
DEFAULT_MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024


class _UploadSizeExceeded(MultiPartException):
    pass


class _BudgetedMultiPartParser(MultiPartParser):
    """Enforce file bytes while Starlette streams a multipart request."""

    def __init__(self, *args: Any, max_file_size: int, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.max_file_size = max_file_size
        self._current_file_size = 0

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._current_file_size = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self._current_file_size += end - start
            if self._current_file_size > self.max_file_size:
                raise _UploadSizeExceeded("Upload exceeds configured size limit")
        super().on_part_data(data, start, end)


async def _parse_budgeted_multipart(http_request: Request):
    parser = _BudgetedMultiPartParser(
        http_request.headers,
        http_request.stream(),
        max_files=1,
        max_fields=2,
        max_part_size=64 * 1024,
        max_file_size=get_max_upload_size(),
    )
    try:
        return await parser.parse()
    except _UploadSizeExceeded as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except MultiPartException as exc:
        raise HTTPException(status_code=400, detail="Invalid multipart request") from exc


INGEST_SUBMIT_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["action", "file_path", "policy_profile"],
                            "properties": {
                                "action": {"type": "string", "enum": ["prepare"]},
                                "file_path": {"type": "string"},
                                "policy_profile": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "required": [
                                "action",
                                "request_id",
                                "confirmation_token",
                            ],
                            "properties": {
                                "action": {"type": "string", "enum": ["confirm"]},
                                "request_id": {
                                    "type": "string",
                                    "pattern": INGEST_REQUEST_ID_PATTERN,
                                },
                                "confirmation_token": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "required": [
                                "action",
                                "request_id",
                                "confirmation_token",
                            ],
                            "properties": {
                                "action": {"type": "string", "enum": ["cancel"]},
                                "request_id": {
                                    "type": "string",
                                    "pattern": INGEST_REQUEST_ID_PATTERN,
                                },
                                "confirmation_token": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    ],
                    "discriminator": {"propertyName": "action"},
                }
            },
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["action", "file", "policy_profile"],
                    "properties": {
                        "action": {"type": "string", "enum": ["prepare"]},
                        "file": {"type": "string", "format": "binary"},
                        "policy_profile": {"type": "string"},
                    },
                }
            },
        },
    }
}

INGEST_ERROR_RESPONSES = {
    201: {"model": IngestSubmitResponse, "description": "Request prepared"},
    202: {"model": IngestSubmitResponse, "description": "Request staged"},
    400: {"description": "Invalid request"},
    403: {"description": "Authorization rejected"},
    404: {"description": "Request or source not found"},
    409: {"description": "Request state conflict"},
    410: {"description": "Confirmation expired"},
    413: {"description": "Upload exceeds configured size limit"},
    415: {"description": "Unsupported content type"},
    422: {"description": "Invalid request body"},
    500: {"description": "Staging failure"},
}


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


@lru_cache(maxsize=1)
def get_ingest_authority() -> MiniAgentClient:
    return MiniAgentClient(profile="safe")


def get_max_upload_size() -> int:
    cfg = load_configs({})
    return int((cfg.get("api") or {}).get("max_upload_size", DEFAULT_MAX_UPLOAD_SIZE))


def get_max_pending_bytes() -> int:
    cfg = load_configs({})
    api_cfg = cfg.get("api") or {}
    return int(api_cfg.get("max_pending_ingest_bytes", get_max_upload_size()))


def _ensure_local_supported_file(file_path: Path) -> None:
    if str(file_path).startswith("\\\\"):
        raise HTTPException(status_code=400, detail="Network paths are not supported")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not is_supported_ingest_path(file_path):
        raise HTTPException(status_code=400, detail="Unsupported ingest file type")


def get_allowed_import_roots(runtime_paths: dict[str, Path]) -> list[Path]:
    allowed: list[Path] = []
    for value in runtime_paths.values():
        try:
            resolved = value.resolve()
            if resolved not in allowed:
                allowed.append(resolved)
            if resolved.parent not in allowed:
                allowed.append(resolved.parent)
        except OSError:
            logger.debug("Could not resolve configured ingest root", exc_info=True)

    repo_root = Path(__file__).resolve().parents[2]
    for candidate in (repo_root.resolve(), repo_root.parent.resolve()):
        if candidate not in allowed:
            allowed.append(candidate)
    return allowed


def require_allowed_source(path: Path, allowed_roots: list[Path]) -> Path:
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid source path") from exc

    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    raise HTTPException(status_code=403, detail="Source path is outside allowed import roots")


def _submit_budget_profile() -> tuple[str, str]:
    return "single_local_file_handoff", "accepted"


def _require_policy_profile(policy_profile: str) -> str:
    profile = policy_profile.strip()
    if not profile:
        raise HTTPException(status_code=400, detail="policy_profile is required")
    return profile


def _require_loopback_client(http_request: Request) -> None:
    client = http_request.client
    if client is None or client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(
            status_code=403,
            detail="Ingest mutation is restricted to the local operator",
        )


def _place_staged_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)


def _place_pending_for_verification(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)


def _record_lock(ledger: IngestRequestLedger, request_id: str) -> ReentrantFileLock:
    lock_dir = ledger.requests_dir / ".locks"
    return ReentrantFileLock(lock_dir / f"{request_id}.lock")


def _request_expired(record: dict[str, Any], now: datetime) -> bool:
    expires_at = record.get("confirmation_expires_at")
    timestamp = str(
        expires_at
        or record.get("last_updated_at")
        or record.get("created_at")
        or ""
    )
    observed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    if expires_at:
        return now > observed_at
    return (now - observed_at).total_seconds() > AUTHORIZATION_TTL_SECONDS


def _recover_or_expire_incomplete_requests(
    ledger: IngestRequestLedger,
    runtime_paths: dict[str, Path],
) -> None:
    now = datetime.now(timezone.utc)
    cleanup_lock = ReentrantFileLock(ledger.requests_dir / ".cleanup.lock")
    with cleanup_lock.lock():
        for record_path in sorted(ledger.requests_dir.glob("ingest_*.json")):
            try:
                request_id = record_path.stem
                candidate = ledger.load(request_id)
                if candidate is None or str(candidate.get("status") or "") not in {
                    "receiving",
                    "pending_confirmation",
                    "authorizing",
                    "canceling",
                    "cancel_failed",
                    "staging",
                }:
                    continue
                with _record_lock(ledger, request_id).lock():
                    record = ledger.load(request_id)
                    if record is None:
                        continue
                    status = str(record.get("status") or "")
                    if status == "staging":
                        _finalize_staging_file(
                            ledger=ledger,
                            record=record,
                            runtime_paths=runtime_paths,
                        )
                        continue
                    if status == "cancel_failed":
                        pending_value = record.get("pending_path")
                        if pending_value:
                            Path(str(pending_value)).unlink(missing_ok=True)
                        ledger.update_record(
                            request_id,
                            status="canceled",
                            partial_path=None,
                            pending_path=None,
                            verification_path=None,
                            confirmation_token_present=False,
                            confirmation_token_sha256=None,
                            error=None,
                        )
                        continue
                    if status not in {
                        "receiving",
                        "pending_confirmation",
                        "authorizing",
                        "canceling",
                    } or not _request_expired(record, now):
                        continue
                    for key in ("partial_path", "pending_path", "verification_path"):
                        value = record.get(key)
                        if value:
                            Path(str(value)).unlink(missing_ok=True)
                    ledger.update_record(
                        request_id,
                        status="expired",
                        partial_path=None,
                        pending_path=None,
                        verification_path=None,
                        confirmation_token_present=False,
                        confirmation_token_sha256=None,
                        error=None,
                    )
            except Exception:
                logger.error(
                    "Failed to expire stale ingest request record=%s",
                    record_path.name,
                    exc_info=True,
                )


def _pending_storage_bytes(pending_dir: Path) -> int:
    total = 0
    for item in pending_dir.iterdir():
        try:
            if item.is_file():
                total += item.stat().st_size
        except FileNotFoundError:
            # A concurrent confirmation/cancellation may consume the copy.
            continue
    return total


def _authorization_scope(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": str(record["request_id"]),
        "file_sha256": str(record["file_sha256"]),
        "size_bytes": int(record["size_bytes"]),
        "original_name": str(record["original_name"]),
        "policy_profile": str(record["policy_profile"]),
    }


def _token_fingerprint(confirmation_token: str) -> str:
    return hashlib.sha256(confirmation_token.encode("utf-8")).hexdigest()


def _require_matching_confirmation_token(
    record: dict[str, Any],
    confirmation_token: str,
) -> None:
    expected = str(record.get("confirmation_token_sha256") or "")
    observed = _token_fingerprint(confirmation_token)
    if not expected or observed != expected:
        raise HTTPException(status_code=403, detail="Confirmation rejected")


def _authority_error_code(envelope: dict[str, Any]) -> str:
    errors = envelope.get("errors") or []
    if errors and isinstance(errors[0], dict):
        return str(errors[0].get("code") or "")
    return ""


def _public_submit_response(
    record: dict[str, Any],
    *,
    confirmation_token: str | None = None,
    confirmation_expires_at: str | None = None,
) -> IngestSubmitResponse:
    status = str(record.get("status") or "unknown")
    return IngestSubmitResponse(
        request_id=str(record["request_id"]),
        status=status,
        original_name=record.get("original_name"),
        file_sha256=record.get("file_sha256") or None,
        size_bytes=record.get("size_bytes"),
        policy_profile=record.get("policy_profile"),
        confirmation_required=status == "pending_confirmation",
        confirmation_token=confirmation_token,
        confirmation_expires_at=confirmation_expires_at,
        queue_depth_snapshot=record.get("queue_depth_snapshot"),
        watchdog_detection_window_seconds=record.get(
            "watchdog_detection_window_seconds"
        ),
        pickup_estimate=record.get("pickup_estimate") or DEFAULT_PICKUP_ESTIMATE,
        budget_scope=record.get("budget_scope"),
        budget_status=record.get("budget_status"),
        duplicate_of_run_id=record.get("duplicate_of_run_id"),
    )


def _public_status_response(record: dict[str, Any]) -> IngestStatusResponse:
    return IngestStatusResponse(
        request_id=str(record["request_id"]),
        status=str(record.get("status") or "unknown"),
        original_name=record.get("original_name"),
        file_sha256=record.get("file_sha256") or None,
        size_bytes=record.get("size_bytes"),
        policy_profile=record.get("policy_profile"),
        confirmation_required=record.get("status") == "pending_confirmation",
        queue_depth_snapshot=record.get("queue_depth_snapshot"),
        watchdog_detection_window_seconds=record.get(
            "watchdog_detection_window_seconds"
        ),
        pickup_estimate=record.get("pickup_estimate") or DEFAULT_PICKUP_ESTIMATE,
        budget_scope=record.get("budget_scope"),
        budget_status=record.get("budget_status"),
        duplicate_of_run_id=record.get("duplicate_of_run_id"),
        run_id=record.get("run_id"),
        error=record.get("error"),
        created_at=str(record["created_at"]),
        last_observed_at=record.get("last_observed_at"),
        completed_at=record.get("completed_at"),
    )


def _raise_authority_error(envelope: dict[str, Any]) -> None:
    code = _authority_error_code(envelope)
    if code == "token_expired":
        raise HTTPException(status_code=410, detail="Confirmation token expired")
    if code in {"confirmation_token_store_error", "audit_log_error"}:
        raise HTTPException(status_code=500, detail="Authorization evidence unavailable")
    raise HTTPException(status_code=403, detail="Confirmation rejected")


def _validate_model(model: Type[BaseModel], payload: object) -> BaseModel:
    try:
        if hasattr(model, "model_validate"):
            return model.model_validate(payload)
        return model.parse_obj(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid ingest submit request") from exc


def _copy_stream_with_budget(source: BinaryIO, destination: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    max_bytes = get_max_upload_size()
    with destination.open("xb") as target:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail="Upload exceeds configured size limit",
                )
            digest.update(chunk)
            target.write(chunk)
        target.flush()
        os.fsync(target.fileno())
    return digest.hexdigest(), size_bytes


def _prepare_stream(
    stream: BinaryIO,
    *,
    source_path: Path,
    source_kind: str,
    original_name: str,
    policy_profile: str,
    runtime_paths: dict[str, Path],
) -> tuple[IngestSubmitResponse, int]:
    profile = _require_policy_profile(policy_profile)
    staged_basename = safe_upload_name(original_name)
    ledger = get_ingest_request_ledger(runtime_paths)
    _recover_or_expire_incomplete_requests(ledger, runtime_paths)
    request_id = ledger.allocate_request_id()
    pending_dir = ledger.requests_dir / ".pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    pending_path = pending_dir / f"{request_id}__{staged_basename}"
    partial_path = pending_dir / f".{request_id}.part"
    budget_scope, budget_status = _submit_budget_profile()

    ledger.create_record(
        source_path=source_path,
        staged_path=None,
        file_hash="",
        confirmation_token_present=False,
        policy_profile=profile,
        queue_depth_snapshot=count_supported_inbox_items(
            runtime_paths["import_inbox"]
        ),
        watchdog_detection_window_seconds=(
            DEFAULT_WATCHDOG_DETECTION_WINDOW_SECONDS
        ),
        budget_scope=budget_scope,
        budget_status=budget_status,
        request_id=request_id,
        original_name=original_name,
        status="receiving",
        partial_path=partial_path,
        pending_path=pending_path,
        source_kind=source_kind,
        size_bytes=0,
        staged_basename=staged_basename,
    )

    try:
        file_sha256, size_bytes = _copy_stream_with_budget(stream, partial_path)
        os.replace(partial_path, pending_path)
    except HTTPException as exc:
        partial_path.unlink(missing_ok=True)
        pending_path.unlink(missing_ok=True)
        ledger.update_record(
            request_id,
            status="stage_failed",
            partial_path=None,
            pending_path=None,
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        partial_path.unlink(missing_ok=True)
        pending_path.unlink(missing_ok=True)
        ledger.update_record(
            request_id,
            status="stage_failed",
            partial_path=None,
            pending_path=None,
            error="Failed to prepare ingest request",
        )
        logger.error(
            "Failed to prepare ingest request request_id=%s error=%s",
            request_id,
            type(exc).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to prepare ingest request") from exc

    registry = load_watchdog_registry(runtime_paths["watchdog_state_file"])
    existing = registry.get(file_sha256)
    if existing and str(existing.get("status") or "").lower() == "success":
        pending_path.unlink(missing_ok=True)
        record = ledger.update_record(
            request_id,
            status="duplicate",
            partial_path=None,
            pending_path=None,
            file_sha256=file_sha256,
            size_bytes=size_bytes,
            duplicate_of_run_id=existing.get("run_id"),
            error=None,
        )
        return _public_submit_response(record), 200

    if _pending_storage_bytes(pending_dir) > get_max_pending_bytes():
        pending_path.unlink(missing_ok=True)
        ledger.update_record(
            request_id,
            status="stage_failed",
            partial_path=None,
            pending_path=None,
            file_sha256=file_sha256,
            size_bytes=size_bytes,
            error="Pending staging budget exceeded",
        )
        raise HTTPException(status_code=413, detail="Pending staging budget exceeded")

    record = ledger.update_record(
        request_id,
        status="pending_confirmation",
        partial_path=None,
        file_sha256=file_sha256,
        size_bytes=size_bytes,
        error=None,
    )
    authority = get_ingest_authority()
    envelope, return_code = authority.authorize_action(
        prompt="Prepare one exact staged ingestion request",
        mode="ops",
        tool_name=AUTHORIZATION_OPERATION,
        tool_args=_authorization_scope(record),
    )
    token = str((envelope.get("result") or {}).get("confirmation_token") or "")
    if return_code != 3 or not token:
        pending_path.unlink(missing_ok=True)
        ledger.update_record(
            request_id,
            status="authorization_failed",
            pending_path=None,
            error="Authorization could not be issued",
        )
        _raise_authority_error(envelope)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=AUTHORIZATION_TTL_SECONDS)
    ).isoformat()
    record = ledger.update_record(
        request_id,
        confirmation_token_present=True,
        confirmation_token_sha256=_token_fingerprint(token),
        confirmation_expires_at=expires_at,
    )
    return (
        _public_submit_response(
            record,
            confirmation_token=token,
            confirmation_expires_at=expires_at,
        ),
        201,
    )


def _prepare_local_request(
    request: IngestPrepareRequest,
) -> tuple[IngestSubmitResponse, int]:
    runtime_paths = get_ingest_runtime_paths()
    source_path = require_allowed_source(
        Path(request.file_path),
        get_allowed_import_roots(runtime_paths),
    )
    _ensure_local_supported_file(source_path)
    with source_path.open("rb") as stream:
        return _prepare_stream(
            stream,
            source_path=source_path,
            source_kind="local_path",
            original_name=source_path.name,
            policy_profile=request.policy_profile,
            runtime_paths=runtime_paths,
        )


async def _prepare_uploaded_request(
    file: StarletteUploadFile,
    *,
    policy_profile: str,
) -> tuple[IngestSubmitResponse, int]:
    original_name = file.filename or ""
    safe_upload_name(original_name)
    runtime_paths = get_ingest_runtime_paths()
    return _prepare_stream(
        file.file,
        source_path=Path(original_name),
        source_kind="upload",
        original_name=original_name,
        policy_profile=policy_profile,
        runtime_paths=runtime_paths,
    )


def _load_request_for_transition(
    ledger: IngestRequestLedger,
    request_id: str,
) -> dict[str, Any]:
    record = ledger.load(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ingest request not found")
    return record


def _mark_integrity_failed(
    ledger: IngestRequestLedger,
    request_id: str,
    *paths: Path,
) -> None:
    for path in paths:
        if str(path) not in {"", "."}:
            path.unlink(missing_ok=True)
    ledger.update_record(
        request_id,
        status="integrity_failed",
        pending_path=None,
        verification_path=None,
        confirmation_token_present=False,
        confirmation_token_sha256=None,
        error="Prepared file integrity mismatch",
    )


def _reconcile_staging_runtime_evidence(
    *,
    ledger: IngestRequestLedger,
    record: dict[str, Any],
    runtime_paths: dict[str, Path],
) -> dict[str, Any] | None:
    observed = resolve_ingest_request_status(record, runtime_paths)
    status = str(observed.get("status") or "")
    if status not in {"processing", "completed", "failed"}:
        return None
    return ledger.update_record(
        str(record["request_id"]),
        status=status,
        partial_path=None,
        pending_path=None,
        verification_path=None,
        confirmation_token_present=False,
        confirmation_token_sha256=None,
        run_id=observed.get("run_id"),
        completed_at=observed.get("completed_at"),
        error=observed.get("error"),
    )


def _verify_visible_staged_or_reconcile(
    *,
    ledger: IngestRequestLedger,
    record: dict[str, Any],
    runtime_paths: dict[str, Path],
    staged_path: Path,
    pending_path: Path,
    verification_path: Path,
) -> dict[str, Any] | None:
    try:
        mismatch = (
            compute_file_hash(staged_path) != str(record["file_sha256"])
            or staged_path.stat().st_size != int(record["size_bytes"])
        )
    except FileNotFoundError:
        reconciled = _reconcile_staging_runtime_evidence(
            ledger=ledger,
            record=record,
            runtime_paths=runtime_paths,
        )
        if reconciled is not None:
            return reconciled
        raise
    if mismatch:
        _mark_integrity_failed(
            ledger,
            str(record["request_id"]),
            pending_path,
            verification_path,
            staged_path,
        )
        raise HTTPException(status_code=409, detail="Prepared file integrity mismatch")
    return None


def _finalize_staging_file(
    *,
    ledger: IngestRequestLedger,
    record: dict[str, Any],
    runtime_paths: dict[str, Path],
) -> dict[str, Any]:
    request_id = str(record["request_id"])
    pending_path = Path(str(record.get("pending_path") or ""))
    verification_path = Path(str(record.get("verification_path") or ""))
    staged_path = Path(str(record.get("staged_path") or ""))
    expected_hash = str(record["file_sha256"])
    expected_size = int(record["size_bytes"])

    if staged_path.is_file():
        reconciled = _verify_visible_staged_or_reconcile(
            ledger=ledger,
            record=record,
            runtime_paths=runtime_paths,
            staged_path=staged_path,
            pending_path=pending_path,
            verification_path=verification_path,
        )
        if reconciled is not None:
            return reconciled
    else:
        reconciled = _reconcile_staging_runtime_evidence(
            ledger=ledger,
            record=record,
            runtime_paths=runtime_paths,
        )
        if reconciled is not None:
            return reconciled
        if not verification_path.is_file():
            if not pending_path.is_file():
                _mark_integrity_failed(
                    ledger,
                    request_id,
                    pending_path,
                    verification_path,
                )
                raise HTTPException(status_code=409, detail="Prepared file is unavailable")
            _place_pending_for_verification(pending_path, verification_path)

        if (
            compute_file_hash(verification_path) != expected_hash
            or verification_path.stat().st_size != expected_size
        ):
            _mark_integrity_failed(
                ledger,
                request_id,
                pending_path,
                verification_path,
            )
            raise HTTPException(status_code=409, detail="Prepared file integrity mismatch")

        _place_staged_file(verification_path, staged_path)
        reconciled = _verify_visible_staged_or_reconcile(
            ledger=ledger,
            record=record,
            runtime_paths=runtime_paths,
            staged_path=staged_path,
            pending_path=pending_path,
            verification_path=verification_path,
        )
        if reconciled is not None:
            return reconciled

    return ledger.update_record(
        request_id,
        status="staged",
        pending_path=None,
        verification_path=None,
        confirmation_token_sha256=None,
        queue_depth_snapshot=count_supported_inbox_items(
            runtime_paths["import_inbox"]
        ),
        error=None,
    )


def _confirm_pending_request(
    request: IngestConfirmRequest,
) -> tuple[IngestSubmitResponse, int]:
    runtime_paths = get_ingest_runtime_paths()
    ledger = get_ingest_request_ledger(runtime_paths)
    with _record_lock(ledger, request.request_id).lock():
        record = _load_request_for_transition(ledger, request.request_id)
        original_status = str(record.get("status") or "")
        if original_status not in {"pending_confirmation", "authorizing", "staging"}:
            raise HTTPException(status_code=409, detail="Request is not pending confirmation")
        _require_matching_confirmation_token(record, request.confirmation_token)

        pending_path = Path(str(record.get("pending_path") or ""))
        staged_name = f"{request.request_id}__{record['staged_basename']}"
        staged_path = runtime_paths["import_inbox"] / staged_name
        verification_path = runtime_paths["import_inbox"] / (
            f".{request.request_id}.verification.part"
        )

        if original_status != "staging":
            if not pending_path.is_file():
                _mark_integrity_failed(ledger, request.request_id, pending_path)
                raise HTTPException(status_code=409, detail="Prepared file is unavailable")
            if (
                compute_file_hash(pending_path) != record.get("file_sha256")
                or pending_path.stat().st_size != record.get("size_bytes")
            ):
                authority = get_ingest_authority()
                try:
                    authority.revoke_action_authorization(
                        prompt="Cancel an integrity-failed staged ingestion request",
                        mode="ops",
                        tool_name=AUTHORIZATION_OPERATION,
                        tool_args=_authorization_scope(record),
                        confirmation_token=request.confirmation_token,
                    )
                except Exception:
                    logger.error(
                        "Failed to revoke integrity-failed authorization request_id=%s",
                        request.request_id,
                        exc_info=True,
                    )
                _mark_integrity_failed(ledger, request.request_id, pending_path)
                raise HTTPException(status_code=409, detail="Prepared file integrity mismatch")

            if original_status == "pending_confirmation":
                record = ledger.update_record(
                    request.request_id,
                    status="authorizing",
                )

            authority = get_ingest_authority()
            envelope, return_code = authority.authorize_action(
                prompt="Confirm one exact staged ingestion request",
                mode="ops",
                tool_name=AUTHORIZATION_OPERATION,
                tool_args=_authorization_scope(record),
                confirm=True,
                confirmation_token=request.confirmation_token,
            )
            error_code = _authority_error_code(envelope)
            recovered_claim = (
                original_status == "authorizing"
                and error_code == "token_already_used"
            )
            if return_code != 0 and not recovered_claim:
                if error_code in {"audit_log_error", "confirmation_token_store_error"}:
                    pending_path.unlink(missing_ok=True)
                    ledger.update_record(
                        request.request_id,
                        status="authorization_failed",
                        pending_path=None,
                        confirmation_token_present=False,
                        confirmation_token_sha256=None,
                        error="Authorization evidence unavailable",
                    )
                else:
                    ledger.update_record(
                        request.request_id,
                        status="pending_confirmation",
                    )
                _raise_authority_error(envelope)

            record = ledger.update_record(
                request.request_id,
                status="staging",
                staged_path=str(staged_path),
                staged_name=staged_name,
                verification_path=str(verification_path),
                confirmation_token_present=False,
                authorization_confirmed_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            record = _finalize_staging_file(
                ledger=ledger,
                record=record,
                runtime_paths=runtime_paths,
            )
        except HTTPException:
            raise
        except Exception as exc:
            pending_path.unlink(missing_ok=True)
            verification_path.unlink(missing_ok=True)
            staged_path.unlink(missing_ok=True)
            try:
                ledger.update_record(
                    request.request_id,
                    status="stage_failed",
                    pending_path=None,
                    verification_path=None,
                    confirmation_token_sha256=None,
                    error="Failed to stage ingest request",
                )
            except Exception:
                logger.error(
                    "Failed to persist ingest staging failure request_id=%s",
                    request.request_id,
                    exc_info=True,
                )
            logger.error(
                "Failed to stage ingest request request_id=%s error=%s",
                request.request_id,
                type(exc).__name__,
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="Failed to stage ingest request") from exc

        return _public_submit_response(record), 202


def _cancel_pending_request(
    request: IngestCancelRequest,
) -> tuple[IngestSubmitResponse, int]:
    runtime_paths = get_ingest_runtime_paths()
    ledger = get_ingest_request_ledger(runtime_paths)
    with _record_lock(ledger, request.request_id).lock():
        record = _load_request_for_transition(ledger, request.request_id)
        if record.get("status") == "canceled":
            return _public_submit_response(record), 200
        original_status = str(record.get("status") or "")
        if original_status not in {
            "pending_confirmation",
            "canceling",
            "cancel_failed",
        }:
            raise HTTPException(status_code=409, detail="Request is not pending confirmation")
        _require_matching_confirmation_token(record, request.confirmation_token)

        if original_status == "pending_confirmation":
            record = ledger.update_record(
                request.request_id,
                status="canceling",
            )

        authority = get_ingest_authority()
        envelope, return_code = authority.revoke_action_authorization(
            prompt="Cancel one exact staged ingestion request",
            mode="ops",
            tool_name=AUTHORIZATION_OPERATION,
            tool_args=_authorization_scope(record),
            confirmation_token=request.confirmation_token,
        )
        error_code = _authority_error_code(envelope)
        recovered_revocation = (
            original_status in {"canceling", "cancel_failed"}
            and error_code == "invalid_confirmation_token"
        )
        if return_code != 0 and not recovered_revocation:
            if error_code not in {
                "audit_log_error",
                "confirmation_token_store_error",
            }:
                ledger.update_record(
                    request.request_id,
                    status="pending_confirmation",
                )
            _raise_authority_error(envelope)

        pending_path = Path(str(record.get("pending_path") or ""))
        try:
            if str(pending_path) not in {"", "."}:
                pending_path.unlink(missing_ok=True)
        except OSError as exc:
            ledger.update_record(
                request.request_id,
                status="cancel_failed",
                error="Failed to remove pending ingest request",
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to cancel ingest request",
            ) from exc
        record = ledger.update_record(
            request.request_id,
            status="canceled",
            pending_path=None,
            confirmation_token_present=False,
            confirmation_token_sha256=None,
            canceled_at=datetime.now(timezone.utc).isoformat(),
            error=None,
        )
        return _public_submit_response(record), 200


def _validate_json_submit(payload: object) -> BaseModel:
    action = payload.get("action") if isinstance(payload, dict) else None
    model_by_action: dict[str, Type[BaseModel]] = {
        "prepare": IngestPrepareRequest,
        "confirm": IngestConfirmRequest,
        "cancel": IngestCancelRequest,
    }
    model = model_by_action.get(str(action))
    if model is None:
        raise HTTPException(status_code=422, detail="Invalid ingest submit action")
    return _validate_model(model, payload)


@router.post(
    "/submit",
    response_model=IngestSubmitResponse,
    responses=INGEST_ERROR_RESPONSES,
    openapi_extra=INGEST_SUBMIT_OPENAPI,
)
async def submit_ingest(
    http_request: Request,
    response: Response,
) -> IngestSubmitResponse:
    _require_loopback_client(http_request)
    content_type = http_request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await _parse_budgeted_multipart(http_request)
        if str(form.get("action") or "") != "prepare":
            raise HTTPException(status_code=422, detail="Multipart action must be prepare")
        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=422, detail="file is required")
        result, status_code = await _prepare_uploaded_request(
            file,
            policy_profile=str(form.get("policy_profile") or ""),
        )
    elif content_type.startswith("application/json"):
        try:
            payload = await http_request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON request") from exc
        parsed = _validate_json_submit(payload)
        if isinstance(parsed, IngestPrepareRequest):
            result, status_code = _prepare_local_request(parsed)
        elif isinstance(parsed, IngestConfirmRequest):
            result, status_code = _confirm_pending_request(parsed)
        else:
            result, status_code = _cancel_pending_request(parsed)
    else:
        raise HTTPException(status_code=415, detail="Unsupported content type")

    response.status_code = status_code
    response.headers["Location"] = f"/api/ingest/status/{result.request_id}"
    return result


@router.get("/status/{request_id}", response_model=IngestStatusResponse)
async def get_ingest_status(request_id: str) -> IngestStatusResponse:
    runtime_paths = get_ingest_runtime_paths()
    ledger = get_ingest_request_ledger(runtime_paths)
    try:
        record = ledger.load(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ingest request ID") from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Ingest request not found")
    resolved = resolve_ingest_request_status(record, runtime_paths)
    return _public_status_response(resolved)


def safe_upload_name(raw: str) -> str:
    if not raw:
        raise HTTPException(status_code=400, detail="Filename is missing")
    if raw != PurePath(raw).name or raw != PureWindowsPath(raw).name:
        raise HTTPException(status_code=400, detail="Filename must not contain path components")
    if "/" in raw or "\\" in raw or any(
        ord(character) < 32 or ord(character) == 127 for character in raw
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = Path(raw)
    if path.name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not is_supported_ingest_path(path):
        raise HTTPException(status_code=400, detail="Unsupported ingest file type")
    return f"{uuid4().hex}{path.suffix.lower()}"
