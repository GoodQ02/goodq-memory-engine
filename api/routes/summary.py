"""
Summary API routes for GoodQ4All.
Provides dashboard, entity profile aggregation, and custom collections.
"""
from __future__ import annotations

import logging
import hashlib
import hmac
import json
from pathlib import Path
import re
import time
from typing import List
import uuid
from fastapi import APIRouter, HTTPException, Path as PathParam, Body, BackgroundTasks, Query
from fastapi.responses import JSONResponse
import asyncio

from api.utils.response_models import (
    SummaryDashboardResponse,
    EntityProfileResponse,
    SavedCollectionItem,
    SaveCollectionRequest,
)
from api.utils.loaders import DataLoader
from api.utils.action_jobs import (
    ActionJobLedger,
    ActionJobTransitionError,
    PassiveActionJobReader,
)
from lib import summary_aggregator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summary", tags=["summary"])

_data_loader = None

_VIDEO_SUMMARY_JOB_OPERATION = "video_summary.generate"
_VIDEO_SUMMARY_AUTH_OPERATION = "generate_video_summary"
_COLLECTION_CREATE_AUTH_OPERATION = "create_summary_collection"
_COLLECTION_DELETE_JOB_OPERATION = "summary_collection.delete"
_COLLECTION_DELETE_AUTH_OPERATION = "delete_summary_collection"
_SUMMARY_OWNER_INSTANCE = f"summary-api-{uuid.uuid4().hex}"
_COLLECTION_ACTION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,101}")
_COLLECTION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_ACTION_JOB_ID_RE = re.compile(r"job_[0-9a-f]{32}")
_COLLECTION_EPOCH_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_AUTHORIZATION_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_MAX_COLLECTION_REQUEST_BYTES = 1_000_000


def get_data_loader() -> DataLoader:
    """Lazy-load data loader."""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader


def _get_kg_db_path() -> Path:
    from steps.common.config_loader import load_configs
    cfg = load_configs({})
    return Path(cfg.get("paths", {}).get("knowledge_graph_db", "data/knowledge_graph.db"))


def _get_summary_job_ledger(cfg: dict) -> ActionJobLedger:
    return ActionJobLedger(_get_summary_job_root(cfg))


def _get_summary_job_reader(cfg: dict) -> PassiveActionJobReader:
    return PassiveActionJobReader(_get_summary_job_root(cfg))


def _get_summary_job_root(cfg: dict) -> Path:
    data_root = cfg.get("paths", {}).get("data_root")
    if not isinstance(data_root, str) or not data_root.strip():
        raise ValueError("GoodQ data root is not configured")
    return Path(data_root) / "control" / "action_jobs"


def _get_summary_authority(cfg: dict):
    from agents.mini_agent_client import MiniAgentClient

    return MiniAgentClient(profile="safe")


def _summary_job_scope(video_hash: str) -> dict:
    return {"video_hash": video_hash}


def _public_summary_job(record: dict) -> dict:
    return {
        key: record.get(key)
        for key in (
            "job_id",
            "operation",
            "scope",
            "state",
            "created_at_utc",
            "updated_at_utc",
            "outcome",
            "audit_status",
        )
    }


def _validate_summary_action_body(body: dict) -> str:
    action = body.get("action")
    if action == "prepare" and set(body) == {"action"}:
        return action
    if (
        action == "confirm"
        and set(body) == {"action", "job_id", "confirmation_token"}
        and isinstance(body.get("job_id"), str)
        and body["job_id"].strip()
        and isinstance(body.get("confirmation_token"), str)
        and body["confirmation_token"].strip()
    ):
        return action
    raise HTTPException(status_code=422, detail="Invalid summary action body")


def _authorization_error_code(envelope: object) -> str:
    if not isinstance(envelope, dict):
        return "authorization_failed"
    errors = envelope.get("errors")
    if not isinstance(errors, list):
        return "authorization_failed"
    for error in errors:
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return error["code"]
    return "authorization_failed"


def _parse_collection_request(value: object) -> tuple[SaveCollectionRequest, dict]:
    try:
        request = SaveCollectionRequest.model_validate(value)
        normalized = request.model_dump(mode="python")
        if not request.name.strip() or not request.collection_type.strip():
            raise ValueError("collection identifiers must contain visible characters")
        encoded = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid collection payload") from exc
    if len(encoded) > _MAX_COLLECTION_REQUEST_BYTES:
        raise HTTPException(status_code=422, detail="Collection payload is too large")
    return request, {
        "normalized": normalized,
        "payload_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _parse_collection_action_body(
    body: object,
) -> tuple[str, SaveCollectionRequest, dict]:
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Invalid collection action body")
    action = body.get("action")
    expected_fields = (
        {"action", "collection"}
        if action == "prepare"
        else {
            "action",
            "action_id",
            "epoch_id",
            "payload_sha256",
            "confirmation_token",
            "collection",
        }
        if action == "confirm"
        else set()
    )
    if set(body) != expected_fields:
        raise HTTPException(status_code=422, detail="Invalid collection action body")
    request, payload = _parse_collection_request(body.get("collection"))
    if action == "confirm":
        if (
            not isinstance(body.get("action_id"), str)
            or _COLLECTION_ACTION_ID_RE.fullmatch(body["action_id"]) is None
            or not isinstance(body.get("epoch_id"), str)
            or _COLLECTION_EPOCH_ID_RE.fullmatch(body["epoch_id"]) is None
            or not isinstance(body.get("payload_sha256"), str)
            or _SHA256_RE.fullmatch(body["payload_sha256"]) is None
            or not isinstance(body.get("confirmation_token"), str)
            or not body["confirmation_token"]
            or body["confirmation_token"] != body["confirmation_token"].strip()
        ):
            raise HTTPException(status_code=422, detail="Invalid collection action body")
    return action, request, payload


def _collection_create_scope(
    *,
    action_id: str,
    epoch_id: str,
    payload_sha256: str,
) -> dict:
    return {
        "action_id": action_id,
        "epoch_id": epoch_id,
        "payload_sha256": payload_sha256,
    }


def _public_saved_collection(collection: dict) -> dict:
    """Project durable collection evidence onto the existing public schema."""
    return SavedCollectionItem.model_validate(collection).model_dump(mode="json")


def _collection_create_request_id(
    collection: dict,
    *,
    action_id: str,
    payload_sha256: str,
) -> str:
    for history_entry in collection.get("history", []):
        if (
            history_entry.get("action") == "create"
            and history_entry.get("action_id") == action_id
            and history_entry.get("payload_sha256") == payload_sha256
            and isinstance(history_entry.get("authorization_request_id"), str)
            and _AUTHORIZATION_REQUEST_ID_RE.fullmatch(
                history_entry["authorization_request_id"]
            )
            is not None
        ):
            return history_entry["authorization_request_id"]
    raise RuntimeError("persisted collection authorization evidence is incomplete")


def _record_collection_create_outcome(
    cfg: dict,
    *,
    scope: dict,
    request_id: str,
    status: str,
    mutated: bool,
    duration_ms: int,
    error_codes: list[str],
) -> str:
    try:
        audit = _get_summary_authority(cfg).record_external_execution_outcome(
            operation=_COLLECTION_CREATE_AUTH_OPERATION,
            arguments=scope,
            request_id=request_id,
            mode="ops",
            status=status,
            return_code=0 if status == "succeeded" else 1,
            duration_ms=duration_ms,
            side_effect_report={
                "mutated": mutated,
                "targets": [f"summary-collection:create:{scope['action_id']}"],
            },
            error_codes=error_codes,
        )
        if isinstance(audit, dict) and audit.get("audit_status") == "recorded":
            return "recorded"
    except Exception:
        logger.error(
            "Summary collection create external audit failed for action %s",
            scope["action_id"],
        )
    return "failed"


def _parse_collection_delete_action_body(body: object) -> str:
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Invalid collection delete action body")
    action = body.get("action")
    if action == "prepare" and set(body) == {"action"}:
        return action
    if (
        action == "confirm"
        and set(body)
        == {
            "action",
            "job_id",
            "epoch_id",
            "expected_record_sha256",
            "confirmation_token",
        }
        and isinstance(body.get("job_id"), str)
        and _ACTION_JOB_ID_RE.fullmatch(body["job_id"]) is not None
        and isinstance(body.get("epoch_id"), str)
        and _COLLECTION_EPOCH_ID_RE.fullmatch(body["epoch_id"]) is not None
        and isinstance(body.get("expected_record_sha256"), str)
        and _SHA256_RE.fullmatch(body["expected_record_sha256"]) is not None
        and isinstance(body.get("confirmation_token"), str)
        and bool(body["confirmation_token"])
        and body["confirmation_token"] == body["confirmation_token"].strip()
    ):
        return action
    raise HTTPException(status_code=422, detail="Invalid collection delete action body")


def _collection_delete_scope(
    *,
    epoch_id: str,
    collection_id: str,
    expected_record_sha256: str,
) -> dict:
    return {
        "epoch_id": epoch_id,
        "collection_id": collection_id,
        "expected_record_sha256": expected_record_sha256,
    }


def _find_collection_record(
    db_path: Path,
    collection_id: str,
    *,
    require_active: bool,
) -> dict | None:
    data = summary_aggregator.load_collections(db_path)
    for collection in data["collections"]:
        if collection.get("collection_id") != collection_id:
            continue
        if require_active and collection.get("status") != "active":
            return None
        return collection
    return None


def _collection_delete_request_id(
    collection: dict,
    *,
    job_id: str,
    expected_record_sha256: str,
) -> str:
    for history_entry in collection.get("history", []):
        if (
            history_entry.get("action") == "delete"
            and history_entry.get("job_id") == job_id
            and history_entry.get("expected_record_sha256")
            == expected_record_sha256
            and isinstance(history_entry.get("authorization_request_id"), str)
            and _AUTHORIZATION_REQUEST_ID_RE.fullmatch(
                history_entry["authorization_request_id"]
            )
            is not None
        ):
            return history_entry["authorization_request_id"]
    raise RuntimeError("persisted collection delete evidence is incomplete")


def _validated_collection_delete_receipt(
    db_path: Path,
    *,
    job_id: str,
    scope: dict,
) -> dict | None:
    collection = summary_aggregator.find_collection_by_delete_job(
        db_path,
        job_id=job_id,
        expected_record_sha256=scope["expected_record_sha256"],
    )
    deleted_at = collection.get("deleted_at_utc") if collection is not None else None
    if (
        collection is None
        or collection.get("collection_id") != scope["collection_id"]
        or collection.get("source_epoch") != scope["epoch_id"]
        or collection.get("status") != "deleted"
        or not isinstance(deleted_at, str)
        or not deleted_at.strip()
    ):
        return None
    return collection


def _record_collection_delete_outcome(
    cfg: dict,
    *,
    job_id: str,
    scope: dict,
    request_id: str,
    status: str,
    mutated: bool,
    duration_ms: int,
    error_codes: list[str],
) -> str:
    try:
        audit = _get_summary_authority(cfg).record_external_execution_outcome(
            operation=_COLLECTION_DELETE_AUTH_OPERATION,
            arguments={"job_id": job_id, **scope},
            request_id=request_id,
            mode="ops",
            status=status,
            return_code=0 if status == "succeeded" else 1,
            duration_ms=duration_ms,
            side_effect_report={
                "mutated": mutated,
                "targets": [f"summary-collection:delete:{job_id}"],
            },
            error_codes=error_codes,
        )
        if isinstance(audit, dict) and audit.get("audit_status") == "recorded":
            return "recorded"
    except Exception:
        logger.error(
            "Summary collection delete external audit failed for job %s",
            job_id,
        )
    return "failed"


def _has_complete_summary_authorization(record: dict) -> bool:
    fingerprint = record.get("token_fingerprint")
    request_id = record.get("authorization_request_id")
    return (
        isinstance(fingerprint, str)
        and re.fullmatch(r"[0-9a-f]{64}", fingerprint) is not None
        and isinstance(request_id, str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", request_id) is not None
    )


def _summary_video_hash_from_record(record: dict) -> str:
    scope = record.get("scope")
    if (
        not isinstance(scope, dict)
        or set(scope) != {"video_hash"}
        or not isinstance(scope.get("video_hash"), str)
        or re.fullmatch(r"[a-fA-F0-9]{8,64}", scope["video_hash"]) is None
    ):
        raise ValueError("Persisted video summary job scope is invalid")
    return scope["video_hash"]


def _collection_delete_scope_from_record(record: dict) -> dict:
    scope = record.get("scope")
    if (
        not isinstance(scope, dict)
        or set(scope)
        != {"epoch_id", "collection_id", "expected_record_sha256"}
        or not isinstance(scope.get("epoch_id"), str)
        or _COLLECTION_EPOCH_ID_RE.fullmatch(scope["epoch_id"]) is None
        or not isinstance(scope.get("collection_id"), str)
        or _COLLECTION_ID_RE.fullmatch(scope["collection_id"]) is None
        or not isinstance(scope.get("expected_record_sha256"), str)
        or _SHA256_RE.fullmatch(scope["expected_record_sha256"]) is None
    ):
        raise ValueError("Persisted collection delete job scope is invalid")
    return scope


def _configured_summary_db_path(cfg: dict) -> Path:
    value = cfg.get("paths", {}).get("knowledge_graph_db")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("GoodQ knowledge graph database is not configured")
    return Path(value)


def _advance_collection_delete_to_running(
    ledger: ActionJobLedger,
    record: dict,
) -> dict:
    state = record["state"]
    if state == "authorizing":
        record = ledger.transition(
            record["job_id"],
            expected_states="authorizing",
            new_state="queued",
        )
        state = "queued"
    if state == "queued":
        record = ledger.transition(
            record["job_id"],
            expected_states="queued",
            new_state="running",
        )
    return record


def _reconcile_collection_delete_job(
    cfg: dict,
    ledger: ActionJobLedger,
    record: dict,
) -> None:
    state = str(record.get("state") or "")
    job_id = str(record.get("job_id") or "")
    scope = _collection_delete_scope_from_record(record)

    if state == "pending_confirmation":
        if _has_complete_summary_authorization(record):
            return
        ledger.transition(
            job_id,
            expected_states=state,
            new_state="failed",
            outcome={
                "code": "authorization_interrupted",
                "message": "Collection delete authorization was interrupted by restart",
            },
        )
        return

    db_path = _configured_summary_db_path(cfg)
    receipt = None
    if db_path.is_file() and db_path.parent.name == scope["epoch_id"]:
        receipt = _validated_collection_delete_receipt(
            db_path,
            job_id=job_id,
            scope=scope,
        )

    if state == "authorizing" and receipt is None:
        if _has_complete_summary_authorization(record):
            return
        ledger.transition(
            job_id,
            expected_states=state,
            new_state="failed",
            outcome={
                "code": "authorization_interrupted",
                "message": "Collection delete authorization was interrupted by restart",
            },
        )
        return

    if receipt is not None:
        request_id = _collection_delete_request_id(
            receipt,
            job_id=job_id,
            expected_record_sha256=scope["expected_record_sha256"],
        )
        if not _has_complete_summary_authorization(record):
            raise ValueError(
                "Persisted collection delete authorization evidence is incomplete"
            )
        if not hmac.compare_digest(record["authorization_request_id"], request_id):
            raise ValueError(
                "Persisted collection delete authorization request ID is inconsistent"
            )
        record = _advance_collection_delete_to_running(ledger, record)
        audit_status = _record_collection_delete_outcome(
            cfg,
            job_id=job_id,
            scope=scope,
            request_id=request_id,
            status="succeeded",
            mutated=True,
            duration_ms=0,
            error_codes=[],
        )
        ledger.transition(
            job_id,
            expected_states="running",
            new_state="succeeded",
            outcome={
                "code": "collection_deleted",
                "message": "Collection delete was recovered from durable evidence",
            },
            audit_status=audit_status,
        )
        return

    if state not in {"queued", "running"}:
        raise ValueError("Persisted collection delete job state is invalid")
    if not _has_complete_summary_authorization(record):
        raise ValueError("Persisted collection delete authorization is incomplete")
    request_id = record["authorization_request_id"]
    audit_status = _record_collection_delete_outcome(
        cfg,
        job_id=job_id,
        scope=scope,
        request_id=request_id,
        status="interrupted",
        mutated=False,
        duration_ms=0,
        error_codes=["execution_interrupted"],
    )
    ledger.transition(
        job_id,
        expected_states=state,
        new_state="interrupted",
        outcome={
            "code": "execution_interrupted",
            "message": "Collection delete was interrupted before durable mutation",
        },
        audit_status=audit_status,
    )


def _reconcile_summary_jobs(cfg: dict) -> None:
    root = _get_summary_job_root(cfg)
    if not root.exists():
        return
    ledger = _get_summary_job_ledger(cfg)
    records = ledger.list_prior_owner_records(
        current_owner_instance=_SUMMARY_OWNER_INSTANCE,
        states={"pending_confirmation", "authorizing", "queued", "running"},
    )
    for record in records:
        operation = record.get("operation")
        if operation == _COLLECTION_DELETE_JOB_OPERATION:
            _reconcile_collection_delete_job(cfg, ledger, record)
            continue
        if operation != _VIDEO_SUMMARY_JOB_OPERATION:
            continue
        state = str(record.get("state") or "")
        job_id = str(record.get("job_id") or "")
        if state in {"pending_confirmation", "authorizing"}:
            if _has_complete_summary_authorization(record):
                continue
            ledger.transition(
                job_id,
                expected_states=state,
                new_state="failed",
                outcome={
                    "code": "authorization_interrupted",
                    "message": "Video summary authorization was interrupted by restart",
                },
            )
            continue

        video_hash = _summary_video_hash_from_record(record)
        audit_status = "failed"
        try:
            audit = _get_summary_authority(cfg).record_external_execution_outcome(
                operation=_VIDEO_SUMMARY_AUTH_OPERATION,
                arguments={"job_id": job_id, "video_hash": video_hash},
                request_id=str(record.get("authorization_request_id") or ""),
                mode="ops",
                status="interrupted",
                return_code=1,
                duration_ms=0,
                side_effect_report={
                    "mutated": False,
                    "targets": [f"video-summary:{job_id}"],
                },
                error_codes=["execution_interrupted"],
            )
            if isinstance(audit, dict) and audit.get("audit_status") == "recorded":
                audit_status = "recorded"
        except Exception:
            logger.error("Video summary restart interruption audit failed for job %s", job_id)

        ledger.transition(
            job_id,
            expected_states=state,
            new_state="interrupted",
            outcome={
                "code": "execution_interrupted",
                "message": "Video summary generation was interrupted by restart",
            },
            audit_status=audit_status,
        )


async def _reconcile_summary_jobs_on_startup() -> None:
    from steps.common.config_loader import load_configs

    _reconcile_summary_jobs(load_configs({}))


router.add_event_handler("startup", _reconcile_summary_jobs_on_startup)


@router.get("/dashboard", response_model=SummaryDashboardResponse)
async def get_dashboard():
    """
    Get consolidated dashboard metrics across all ingested videos/scenes.
    """
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")
        
    try:
        loader = get_data_loader()
        data = summary_aggregator.get_summary_dashboard(db_path, loader)
        return data
    except Exception as e:
        logger.error(f"Failed to compile dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_id:path}", response_model=EntityProfileResponse)
async def get_entity_profile(
    entity_id: str = PathParam(..., description="Stable entity identifier (e.g. 'person:Joe')")
):
    """
    Get detailed metrics, co-occurrences, and media timelines for a major entity.
    """
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")
        
    try:
        loader = get_data_loader()
        data = summary_aggregator.get_entity_profile(db_path, loader, entity_id)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to compile profile for {entity_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections", response_model=List[SavedCollectionItem])
async def list_collections():
    """
    List all active operator-saved collections.
    """
    db_path = _get_kg_db_path()
    try:
        data = summary_aggregator.load_collections(db_path)
        collections = data.get("collections") or []
        # Filter out deleted collections
        active_collections = [col for col in collections if col.get("status") == "active"]
        return active_collections
    except Exception as e:
        logger.error(f"Failed to list collections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections", response_model=dict)
async def create_collection(body: dict = Body(...)):
    """Prepare or confirm one exact governed collection create."""
    from steps.common.config_loader import load_configs

    action, _request, payload = _parse_collection_action_body(body)
    db_path = _get_kg_db_path()
    if not db_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Collection epoch database not initialized",
        )
    epoch_id = db_path.parent.name
    if _COLLECTION_EPOCH_ID_RE.fullmatch(epoch_id) is None:
        logger.error("Summary collection epoch identifier is invalid")
        raise HTTPException(status_code=500, detail="Collection epoch is unavailable")
    try:
        cfg = load_configs({})
    except Exception:
        logger.error("Summary collection configuration could not be loaded")
        raise HTTPException(status_code=503, detail="Collection authorization unavailable")

    if action == "prepare":
        action_id = f"action_{uuid.uuid4().hex}"
        scope = _collection_create_scope(
            action_id=action_id,
            epoch_id=epoch_id,
            payload_sha256=payload["payload_sha256"],
        )
        authority = None
        token = None
        try:
            authority = _get_summary_authority(cfg)
            envelope, return_code = authority.authorize_action(
                prompt="Prepare one exact summary collection create",
                mode="ops",
                tool_name=_COLLECTION_CREATE_AUTH_OPERATION,
                tool_args=scope,
            )
            result = envelope.get("result") if isinstance(envelope, dict) else None
            token = result.get("confirmation_token") if isinstance(result, dict) else None
            request_id = envelope.get("request_id") if isinstance(envelope, dict) else None
            if (
                not isinstance(envelope, dict)
                or return_code != 3
                or envelope.get("status") != "needs_confirmation"
                or not isinstance(token, str)
                or not token
                or not isinstance(request_id, str)
                or _AUTHORIZATION_REQUEST_ID_RE.fullmatch(request_id) is None
            ):
                raise RuntimeError("collection authorization was not prepared")
        except Exception:
            logger.error("Failed to prepare summary collection authorization")
            if authority is not None and isinstance(token, str) and token:
                try:
                    authority.revoke_action_authorization(
                        prompt="Revoke unreturned summary collection authorization",
                        mode="ops",
                        tool_name=_COLLECTION_CREATE_AUTH_OPERATION,
                        tool_args=scope,
                        confirmation_token=token,
                    )
                except Exception:
                    logger.error(
                        "Failed to revoke unreturned summary collection authorization"
                    )
            raise HTTPException(
                status_code=503,
                detail="Collection authorization unavailable",
            )
        return {
            "success": True,
            "action_id": action_id,
            "epoch_id": epoch_id,
            "payload_sha256": payload["payload_sha256"],
            "confirmation_token": token,
        }

    action_id = body["action_id"]
    scope = _collection_create_scope(
        action_id=action_id,
        epoch_id=body["epoch_id"],
        payload_sha256=body["payload_sha256"],
    )
    if (
        body["epoch_id"] != epoch_id
        or body["payload_sha256"] != payload["payload_sha256"]
    ):
        raise HTTPException(
            status_code=409,
            detail="Collection confirmation scope mismatch",
        )

    try:
        authority = _get_summary_authority(cfg)
        envelope, return_code = authority.authorize_action(
            prompt="Confirm one exact summary collection create",
            mode="ops",
            tool_name=_COLLECTION_CREATE_AUTH_OPERATION,
            tool_args=scope,
            confirm=True,
            confirmation_token=body["confirmation_token"],
        )
    except Exception:
        logger.error("Summary collection authorization claim failed")
        raise HTTPException(
            status_code=503,
            detail="Collection authorization unavailable",
        )

    if not isinstance(envelope, dict):
        raise HTTPException(
            status_code=503,
            detail="Collection authorization unavailable",
        )
    result = envelope.get("result")
    authorized = (
        return_code == 0
        and envelope.get("status") == "ok"
        and isinstance(result, dict)
        and result.get("allowed") is True
    )
    error_code = _authorization_error_code(envelope)
    recovered = False
    collection = None
    request_id = envelope.get("request_id") if isinstance(envelope, dict) else None
    if not authorized and error_code == "token_already_used":
        try:
            collection = summary_aggregator.find_collection_by_create_action(
                db_path,
                action_id=action_id,
                payload_sha256=payload["payload_sha256"],
            )
            if collection is not None and collection.get("source_epoch") == epoch_id:
                request_id = _collection_create_request_id(
                    collection,
                    action_id=action_id,
                    payload_sha256=payload["payload_sha256"],
                )
                recovered = True
                authorized = True
        except Exception:
            logger.error(
                "Summary collection create recovery evidence is unavailable for action %s",
                action_id,
            )

    if not authorized:
        if error_code == "token_expired":
            detail = "Collection authorization expired"
        elif error_code == "token_already_used":
            detail = "Collection authorization recovery failed"
        else:
            detail = "Collection authorization failed"
        raise HTTPException(status_code=409, detail=detail)
    if (
        not isinstance(request_id, str)
        or _AUTHORIZATION_REQUEST_ID_RE.fullmatch(request_id) is None
    ):
        raise HTTPException(status_code=409, detail="Collection authorization failed")

    started = time.monotonic()
    if not recovered:
        try:
            collection = summary_aggregator.add_collection(
                db_path,
                payload["normalized"],
                mutation_evidence={
                    "action_id": action_id,
                    "payload_sha256": payload["payload_sha256"],
                    "authorization_request_id": request_id,
                },
            )
        except Exception:
            duration_ms = max(0, int((time.monotonic() - started) * 1000))
            _record_collection_create_outcome(
                cfg,
                scope=scope,
                request_id=request_id,
                status="failed",
                mutated=False,
                duration_ms=duration_ms,
                error_codes=["collection_mutation_failed"],
            )
            logger.error(
                "Summary collection create failed for action %s",
                action_id,
            )
            raise HTTPException(status_code=500, detail="Collection mutation failed")

    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    audit_status = _record_collection_create_outcome(
        cfg,
        scope=scope,
        request_id=request_id,
        status="succeeded",
        mutated=True,
        duration_ms=duration_ms,
        error_codes=[],
    )
    return {
        "success": True,
        "message": "Collection successfully created.",
        "collection": _public_saved_collection(collection),
        "action_id": action_id,
        "audit_status": audit_status,
        "recovered": recovered,
    }


@router.delete("/collections/{collection_id}", response_model=dict)
async def delete_collection(
    collection_id: str = PathParam(..., description="Unique ID of the collection to soft-delete"),
    body: dict = Body(...),
):
    """Prepare or confirm one exact governed collection soft-delete."""
    from steps.common.config_loader import load_configs

    action = _parse_collection_delete_action_body(body)
    if _COLLECTION_ID_RE.fullmatch(collection_id) is None:
        raise HTTPException(status_code=422, detail="Invalid collection identifier")
    db_path = _get_kg_db_path()
    if not db_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Collection epoch database not initialized",
        )
    epoch_id = db_path.parent.name
    if _COLLECTION_EPOCH_ID_RE.fullmatch(epoch_id) is None:
        logger.error("Summary collection epoch identifier is invalid")
        raise HTTPException(status_code=500, detail="Collection epoch is unavailable")
    try:
        cfg = load_configs({})
    except Exception:
        logger.error("Summary collection delete control ledger is unavailable")
        raise HTTPException(status_code=503, detail="Collection delete control unavailable")

    if action == "prepare":
        try:
            collection = _find_collection_record(
                db_path,
                collection_id,
                require_active=True,
            )
        except Exception:
            logger.error("Summary collection store could not be read for delete prepare")
            raise HTTPException(status_code=500, detail="Collection store unavailable")
        if collection is None:
            raise HTTPException(status_code=404, detail="Active collection not found")
        if collection.get("source_epoch") != epoch_id:
            raise HTTPException(status_code=409, detail="Collection epoch mismatch")
        try:
            ledger = _get_summary_job_ledger(cfg)
        except Exception:
            logger.error("Summary collection delete control ledger is unavailable")
            raise HTTPException(status_code=503, detail="Collection delete control unavailable")
        scope = _collection_delete_scope(
            epoch_id=epoch_id,
            collection_id=collection_id,
            expected_record_sha256=summary_aggregator.collection_record_sha256(
                collection
            ),
        )
        try:
            record, created = ledger.prepare_or_find_active_with_status(
                operation=_COLLECTION_DELETE_JOB_OPERATION,
                scope=scope,
                owner_instance=_SUMMARY_OWNER_INSTANCE,
            )
        except Exception:
            logger.error("Summary collection delete job preparation failed")
            raise HTTPException(status_code=500, detail="Collection delete control unavailable")
        if not created:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "active_job_exists",
                    "job": _public_summary_job(record),
                },
            )

        authority = None
        token = None
        evidence_persisted = False
        tool_args = {"job_id": record["job_id"], **scope}
        try:
            authority = _get_summary_authority(cfg)
            envelope, return_code = authority.authorize_action(
                prompt="Prepare one exact summary collection delete",
                mode="ops",
                tool_name=_COLLECTION_DELETE_AUTH_OPERATION,
                tool_args=tool_args,
            )
            result = envelope.get("result") if isinstance(envelope, dict) else None
            token = result.get("confirmation_token") if isinstance(result, dict) else None
            request_id = envelope.get("request_id") if isinstance(envelope, dict) else None
            if (
                not isinstance(envelope, dict)
                or return_code != 3
                or envelope.get("status") != "needs_confirmation"
                or not isinstance(token, str)
                or not token
                or not isinstance(request_id, str)
                or _AUTHORIZATION_REQUEST_ID_RE.fullmatch(request_id) is None
            ):
                raise RuntimeError("collection delete authorization was not prepared")
            record = ledger.compare_and_update(
                record["job_id"],
                expected_state="pending_confirmation",
                token_fingerprint=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                authorization_request_id=request_id,
            )
            evidence_persisted = True
        except Exception:
            logger.error("Failed to prepare summary collection delete authorization")
            if (
                authority is not None
                and isinstance(token, str)
                and token
                and not evidence_persisted
            ):
                try:
                    authority.revoke_action_authorization(
                        prompt="Revoke unpersisted summary collection delete authorization",
                        mode="ops",
                        tool_name=_COLLECTION_DELETE_AUTH_OPERATION,
                        tool_args=tool_args,
                        confirmation_token=token,
                    )
                except Exception:
                    logger.error(
                        "Failed to revoke unpersisted summary collection delete authorization"
                    )
            try:
                ledger.transition(
                    record["job_id"],
                    expected_states="pending_confirmation",
                    new_state="failed",
                    outcome={
                        "code": "authorization_prepare_failed",
                        "message": "Collection delete authorization could not be prepared",
                    },
                )
            except Exception:
                logger.error("Failed to persist collection delete preparation failure")
            raise HTTPException(status_code=503, detail="Collection authorization unavailable")
        return {
            "success": True,
            "confirmation_token": token,
            "job": _public_summary_job(record),
        }

    try:
        ledger = _get_summary_job_ledger(cfg)
    except Exception:
        logger.error("Summary collection delete control ledger is unavailable")
        raise HTTPException(status_code=503, detail="Collection delete control unavailable")
    job_id = body["job_id"]
    try:
        record = ledger.load(job_id)
    except ValueError:
        record = None
    scope = _collection_delete_scope(
        epoch_id=body["epoch_id"],
        collection_id=collection_id,
        expected_record_sha256=body["expected_record_sha256"],
    )
    if (
        record is None
        or record.get("operation") != _COLLECTION_DELETE_JOB_OPERATION
        or record.get("scope") != scope
        or body["epoch_id"] != epoch_id
    ):
        raise HTTPException(status_code=404, detail="Collection delete job not found")
    state = record.get("state")
    if state not in {"pending_confirmation", "authorizing"}:
        raise HTTPException(
            status_code=409,
            detail={"code": "job_not_confirmable", "job": _public_summary_job(record)},
        )
    fingerprint = hashlib.sha256(body["confirmation_token"].encode("utf-8")).hexdigest()
    if not isinstance(record.get("token_fingerprint"), str) or not hmac.compare_digest(
        record["token_fingerprint"], fingerprint
    ):
        raise HTTPException(status_code=403, detail="Confirmation token mismatch")

    owner_instance = record.get("owner_instance")
    if owner_instance != _SUMMARY_OWNER_INSTANCE:
        if not _has_complete_summary_authorization(record):
            raise HTTPException(
                status_code=409,
                detail={"code": "job_owner_changed", "job": _public_summary_job(record)},
            )
        try:
            record = ledger.adopt_owner(
                job_id,
                expected_state=state,
                expected_owner_instance=owner_instance,
                new_owner_instance=_SUMMARY_OWNER_INSTANCE,
            )
        except (ActionJobTransitionError, OSError, ValueError):
            current = ledger.load(job_id) or record
            raise HTTPException(
                status_code=409,
                detail={"code": "job_owner_changed", "job": _public_summary_job(current)},
            )
    elif state == "authorizing":
        raise HTTPException(
            status_code=409,
            detail={"code": "job_not_confirmable", "job": _public_summary_job(record)},
        )

    if state == "pending_confirmation":
        try:
            record = ledger.transition(
                job_id,
                expected_states="pending_confirmation",
                new_state="authorizing",
            )
        except (ActionJobTransitionError, OSError, ValueError):
            current = ledger.load(job_id) or record
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_confirmable", "job": _public_summary_job(current)},
            )

    tool_args = {"job_id": job_id, **scope}
    try:
        authority = _get_summary_authority(cfg)
        envelope, return_code = authority.authorize_action(
            prompt="Confirm one exact summary collection delete",
            mode="ops",
            tool_name=_COLLECTION_DELETE_AUTH_OPERATION,
            tool_args=tool_args,
            confirm=True,
            confirmation_token=body["confirmation_token"],
        )
    except Exception:
        logger.error("Summary collection delete authorization claim failed")
        envelope, return_code = {}, 1

    result = envelope.get("result") if isinstance(envelope, dict) else None
    authorized = (
        isinstance(envelope, dict)
        and return_code == 0
        and envelope.get("status") == "ok"
        and isinstance(result, dict)
        and result.get("allowed") is True
    )
    error_code = _authorization_error_code(envelope)
    request_id = envelope.get("request_id") if isinstance(envelope, dict) else None
    recovered = False
    if not authorized and error_code == "token_already_used":
        try:
            collection = _validated_collection_delete_receipt(
                db_path,
                job_id=job_id,
                scope=scope,
            )
            if collection is not None:
                request_id = _collection_delete_request_id(
                    collection,
                    job_id=job_id,
                    expected_record_sha256=scope["expected_record_sha256"],
                )
                recovered = True
                authorized = True
        except Exception:
            logger.error(
                "Summary collection delete recovery evidence is unavailable for job %s",
                job_id,
            )

    if not authorized:
        expired = error_code == "token_expired"
        recovery_failed = error_code == "token_already_used"
        outcome = {
            "code": (
                "authorization_expired"
                if expired
                else "authorization_recovery_failed"
                if recovery_failed
                else "authorization_failed"
            ),
            "message": (
                "Collection delete authorization expired"
                if expired
                else "Collection delete authorization recovery failed"
                if recovery_failed
                else "Collection delete authorization failed"
            ),
        }
        try:
            record = ledger.transition(
                job_id,
                expected_states="authorizing",
                new_state="expired" if expired else "failed",
                outcome=outcome,
            )
        except (ActionJobTransitionError, OSError, ValueError):
            record = ledger.load(job_id) or record
        raise HTTPException(
            status_code=409,
            detail={"code": outcome["code"], "job": _public_summary_job(record)},
        )
    if (
        not isinstance(request_id, str)
        or _AUTHORIZATION_REQUEST_ID_RE.fullmatch(request_id) is None
    ):
        try:
            record = ledger.transition(
                job_id,
                expected_states="authorizing",
                new_state="failed",
                outcome={
                    "code": "authorization_failed",
                    "message": "Collection delete authorization failed",
                },
            )
        except (ActionJobTransitionError, OSError, ValueError):
            record = ledger.load(job_id) or record
        raise HTTPException(
            status_code=409,
            detail={"code": "authorization_failed", "job": _public_summary_job(record)},
        )

    try:
        record = ledger.compare_and_update(
            job_id,
            expected_state="authorizing",
            authorization_request_id=request_id,
        )
    except (ActionJobTransitionError, OSError, ValueError):
        current = ledger.load(job_id) or record
        logger.error(
            "Summary collection delete authorization evidence could not be persisted "
            "for job %s",
            job_id,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "authorization_evidence_pending",
                "job": _public_summary_job(current),
            },
        )

    try:
        record = ledger.transition(
            job_id,
            expected_states="authorizing",
            new_state="queued",
        )
        record = ledger.transition(
            job_id,
            expected_states="queued",
            new_state="running",
        )
    except (ActionJobTransitionError, OSError, ValueError):
        current = ledger.load(job_id) or record
        raise HTTPException(
            status_code=409,
            detail={"code": "job_not_runnable", "job": _public_summary_job(current)},
        )

    started = time.monotonic()
    mutation_error = None
    if not recovered:
        try:
            success = summary_aggregator.soft_delete_collection(
                db_path,
                collection_id,
                mutation_evidence={
                    "job_id": job_id,
                    "expected_record_sha256": scope["expected_record_sha256"],
                    "authorization_request_id": request_id,
                },
            )
            if not success:
                mutation_error = "collection_not_found"
        except summary_aggregator.CollectionStoreConflict:
            mutation_error = "collection_changed"
        except Exception:
            logger.error("Summary collection delete mutation failed for job %s", job_id)
            mutation_error = "collection_mutation_failed"

    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    if mutation_error is not None:
        audit_status = _record_collection_delete_outcome(
            cfg,
            job_id=job_id,
            scope=scope,
            request_id=request_id,
            status="failed",
            mutated=False,
            duration_ms=duration_ms,
            error_codes=[mutation_error],
        )
        messages = {
            "collection_changed": "Collection changed after delete authorization",
            "collection_not_found": "Collection no longer exists",
            "collection_mutation_failed": "Collection delete mutation failed",
        }
        try:
            record = ledger.transition(
                job_id,
                expected_states="running",
                new_state="failed",
                outcome={"code": mutation_error, "message": messages[mutation_error]},
                audit_status=audit_status,
            )
        except (ActionJobTransitionError, OSError, ValueError):
            record = ledger.load(job_id) or record
        raise HTTPException(
            status_code=409 if mutation_error == "collection_changed" else 500,
            detail={"code": mutation_error, "job": _public_summary_job(record)},
        )

    audit_status = _record_collection_delete_outcome(
        cfg,
        job_id=job_id,
        scope=scope,
        request_id=request_id,
        status="succeeded",
        mutated=True,
        duration_ms=duration_ms,
        error_codes=[],
    )
    try:
        record = ledger.transition(
            job_id,
            expected_states="running",
            new_state="succeeded",
            outcome={
                "code": "collection_deleted",
                "message": "Collection was soft-deleted",
            },
            audit_status=audit_status,
        )
    except (ActionJobTransitionError, OSError, ValueError):
        current = ledger.load(job_id) or record
        logger.error("Summary collection delete finalization failed for job %s", job_id)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "collection_finalization_pending",
                "job": _public_summary_job(current),
            },
        )
    return {
        "success": True,
        "recovered": recovered,
        "job": _public_summary_job(record),
    }


async def _generate_summary_worker(job_id: str, video_hash: str, cfg: dict):
    ledger = _get_summary_job_ledger(cfg)
    try:
        record = ledger.transition(
            job_id,
            expected_states="queued",
            new_state="running",
        )
    except (ActionJobTransitionError, FileNotFoundError, ValueError):
        logger.warning("Video summary worker could not claim queued job %s", job_id)
        return

    started = time.monotonic()
    try:
        from steps.video_summarizer.step import run_step as run_video_summarizer

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, run_video_summarizer, cfg, video_hash
        )
        succeeded = isinstance(result, dict) and result.get("success") is True
        outcome = (
            {
                "code": "summary_generated",
                "message": "Video summary generation succeeded",
            }
            if succeeded
            else {
                "code": "summary_generation_failed",
                "message": "Video summary generation reported failure",
            }
        )
    except Exception:
        logger.error("Video summary generation raised an error for job %s", job_id)
        succeeded = False
        outcome = {
            "code": "summary_generation_error",
            "message": "Video summary generation raised an error",
        }

    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    audit_status = "failed"
    try:
        audit = _get_summary_authority(cfg).record_external_execution_outcome(
            operation=_VIDEO_SUMMARY_AUTH_OPERATION,
            arguments={"job_id": job_id, "video_hash": video_hash},
            request_id=str(record.get("authorization_request_id") or ""),
            mode="ops",
            status="succeeded" if succeeded else "failed",
            return_code=0 if succeeded else 1,
            duration_ms=duration_ms,
            side_effect_report={
                "mutated": succeeded,
                "targets": [f"video-summary:{job_id}"],
            },
            error_codes=[] if succeeded else [outcome["code"]],
        )
        if isinstance(audit, dict) and audit.get("audit_status") == "recorded":
            audit_status = "recorded"
    except Exception:
        logger.error("Video summary external audit failed for job %s", job_id)

    try:
        ledger.transition(
            job_id,
            expected_states="running",
            new_state="succeeded" if succeeded else "failed",
            outcome=outcome,
            audit_status=audit_status,
        )
    except (ActionJobTransitionError, FileNotFoundError, ValueError):
        logger.error("Video summary terminal state could not be persisted for job %s", job_id)


@router.get("/capabilities", response_model=dict)
async def get_summary_capabilities():
    """
    Get summary capabilities (e.g. whether LLM features are enabled).
    """
    try:
        from steps.common.config_loader import load_configs
        cfg = load_configs({})
        use_llm = cfg.get('llm', {}).get('features', {}).get('video_summarization', True)
        return {"video_summarization_enabled": bool(use_llm)}
    except Exception as e:
        logger.error(f"Failed to check capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch capabilities")


@router.get("/video/{video_hash}", response_model=dict)
async def get_video_summary(
    video_hash: str = PathParam(..., description="Target video hash")
):
    """
    Get the persisted narrative summary and provenance for a video hash.
    """
    import re
    import sqlite3
    import json
    
    if not video_hash or not re.match(r"^[a-fA-F0-9]{8,64}$", video_hash):
        raise HTTPException(status_code=400, detail="Invalid video hash format")
        
    from steps.common.config_loader import load_configs
    cfg = load_configs({})
    db_path = Path(cfg.get("paths", {}).get("db_path", "data/memory.db"))
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not initialized")
        
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'")
        if not cursor.fetchone():
            conn.close()
            return _check_kg_existence_fallback(video_hash)
            
        cursor.execute("SELECT content, created_at FROM summaries WHERE summary_type='video' AND category='video_summary'")
        rows = cursor.fetchall()
        conn.close()
        
        for content_json, created_at in rows:
            try:
                data = json.loads(content_json)
                if data.get("video_hash") == video_hash:
                    return {
                        "video_hash": video_hash,
                        "summary": data.get("summary", ""),
                        "method": data.get("method", "template"),
                        "provenance": data.get("provenance", {}),
                        "created_at": created_at
                    }
            except Exception:
                continue
                
        return _check_kg_existence_fallback(video_hash)
        
    except sqlite3.Error as se:
        logger.error(f"Database query error: {se}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database query failed")


def _check_kg_existence_fallback(video_hash: str) -> dict:
    import sqlite3
    kg_path = _get_kg_db_path()
    if kg_path.exists():
        try:
            conn_kg = sqlite3.connect(str(kg_path))
            row_kg = conn_kg.execute("SELECT 1 FROM scenes WHERE video_hash=? LIMIT 1", (video_hash,)).fetchone()
            conn_kg.close()
            if row_kg:
                return {
                    "video_hash": video_hash,
                    "summary": "Summary not yet generated for this video.",
                    "method": "none",
                    "provenance": {},
                    "created_at": None
                }
        except Exception as e:
            logger.warning(f"Failed to query KG fallback for existence: {e}")
            
    raise HTTPException(status_code=404, detail="Video summary not found")


@router.get("/video/{video_hash}/status", response_model=dict)
async def get_summary_status(
    video_hash: str = PathParam(..., description="Target video hash to check status"),
    job_id: str | None = Query(None, description="Optional exact summary job ID"),
):
    """
    Return durable summary-job state without mutating lifecycle records.
    """
    import re
    if not video_hash or not re.match(r"^[a-fA-F0-9]{8,64}$", video_hash):
        raise HTTPException(status_code=400, detail="Invalid video hash format")
    from steps.common.config_loader import load_configs

    cfg = load_configs({})
    try:
        root = _get_summary_job_root(cfg)
    except ValueError:
        raise HTTPException(status_code=500, detail="Summary job ledger is unavailable")
    if not root.exists():
        if job_id is not None:
            raise HTTPException(status_code=404, detail="Summary job not found")
        return {"status": "not_started", "job": None}

    reader = _get_summary_job_reader(cfg)
    scope = _summary_job_scope(video_hash)
    if job_id is not None:
        try:
            record = reader.load(job_id)
        except ValueError:
            record = None
        if (
            record is None
            or record.get("operation") != _VIDEO_SUMMARY_JOB_OPERATION
            or record.get("scope") != scope
        ):
            raise HTTPException(status_code=404, detail="Summary job not found")
    else:
        record = reader.latest(
            operation=_VIDEO_SUMMARY_JOB_OPERATION,
            scope=scope,
        )
        if record is None:
            return {"status": "not_started", "job": None}
    return {"status": record["state"], "job": _public_summary_job(record)}


@router.post("/video/{video_hash}/generate", response_model=dict)
async def generate_video_summary(
    background_tasks: BackgroundTasks,
    video_hash: str = PathParam(..., description="Target video hash to summarize"),
    body: dict = Body(...),
):
    """
    Trigger async generation/regeneration of video LLM summary with full audits and checks.
    """
    import re
    import sqlite3
    from steps.common.config_loader import load_configs

    # 1. Input Validation
    if not video_hash or not re.match(r"^[a-fA-F0-9]{8,64}$", video_hash):
        raise HTTPException(status_code=400, detail="Invalid video hash format")
    action = _validate_summary_action_body(body)

    # 2. Database Existence Check
    db_path = _get_kg_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not initialized")

    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT 1 FROM scenes WHERE video_hash=? LIMIT 1", (video_hash,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"Video hash '{video_hash}' not found in database")
    except sqlite3.Error as se:
        logger.error(f"Database query error during video existence check: {se}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database query failed")

    # 3. Durable authorization preparation
    cfg = load_configs({})
    try:
        ledger = _get_summary_job_ledger(cfg)
    except ValueError:
        logger.error("Video summary job ledger configuration is invalid")
        raise HTTPException(status_code=500, detail="Summary job ledger is unavailable")

    if action == "confirm":
        job_id = body["job_id"]
        confirmation_token = body["confirmation_token"]
        try:
            record = ledger.load(job_id)
        except ValueError:
            record = None
        if (
            record is None
            or record.get("operation") != _VIDEO_SUMMARY_JOB_OPERATION
            or record.get("scope") != _summary_job_scope(video_hash)
        ):
            raise HTTPException(status_code=404, detail="Summary job not found")
        state = record.get("state")
        if state not in {"pending_confirmation", "authorizing"}:
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_confirmable", "job": _public_summary_job(record)},
            )
        fingerprint = hashlib.sha256(confirmation_token.encode("utf-8")).hexdigest()
        if not isinstance(record.get("token_fingerprint"), str) or not hmac.compare_digest(
            record["token_fingerprint"], fingerprint
        ):
            raise HTTPException(status_code=403, detail="Confirmation token mismatch")

        recovered_authorizing = False
        owner_instance = record.get("owner_instance")
        if owner_instance != _SUMMARY_OWNER_INSTANCE:
            if not _has_complete_summary_authorization(record):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "job_owner_changed",
                        "job": _public_summary_job(record),
                    },
                )
            try:
                record = ledger.adopt_owner(
                    job_id,
                    expected_state=state,
                    expected_owner_instance=owner_instance,
                    new_owner_instance=_SUMMARY_OWNER_INSTANCE,
                )
            except (ActionJobTransitionError, ValueError):
                current = ledger.load(job_id) or record
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "job_owner_changed",
                        "job": _public_summary_job(current),
                    },
                )
            recovered_authorizing = state == "authorizing"
        elif state == "authorizing":
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_confirmable", "job": _public_summary_job(record)},
            )

        if state == "pending_confirmation":
            try:
                record = ledger.transition(
                    job_id,
                    expected_states="pending_confirmation",
                    new_state="authorizing",
                )
            except ActionJobTransitionError:
                current = ledger.load(job_id) or record
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "job_not_confirmable",
                        "job": _public_summary_job(current),
                    },
                )

        tool_args = {"job_id": job_id, "video_hash": video_hash}
        try:
            authority = _get_summary_authority(cfg)
            envelope, return_code = authority.authorize_action(
                prompt="Confirm one exact video summary",
                mode="ops",
                tool_name=_VIDEO_SUMMARY_AUTH_OPERATION,
                tool_args=tool_args,
                confirm=True,
                confirmation_token=confirmation_token,
            )
        except Exception:
            logger.error("Video summary authorization claim failed")
            envelope, return_code = {}, 1

        result = envelope.get("result") if isinstance(envelope, dict) else None
        authorized = (
            return_code == 0
            and envelope.get("status") == "ok"
            and isinstance(result, dict)
            and result.get("allowed") is True
        )
        error_code = _authorization_error_code(envelope)
        if recovered_authorizing and error_code == "token_already_used":
            authorized = True
        if not authorized:
            expired = error_code == "token_expired"
            try:
                record = ledger.transition(
                    job_id,
                    expected_states="authorizing",
                    new_state="expired" if expired else "failed",
                    outcome={
                        "code": "authorization_expired" if expired else "authorization_failed",
                        "message": (
                            "Video summary authorization expired"
                            if expired
                            else "Video summary authorization failed"
                        ),
                    },
                )
            except ActionJobTransitionError:
                record = ledger.load(job_id) or record
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "authorization_expired" if expired else "authorization_failed",
                    "job": _public_summary_job(record),
                },
            )

        try:
            record = ledger.transition(
                job_id,
                expected_states="authorizing",
                new_state="queued",
            )
        except ActionJobTransitionError:
            current = ledger.load(job_id) or record
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_queueable", "job": _public_summary_job(current)},
            )
        background_tasks.add_task(_generate_summary_worker, job_id, video_hash, cfg)
        return JSONResponse(
            status_code=202,
            content={"success": True, "job": _public_summary_job(record)},
        )

    try:
        record, created = ledger.prepare_or_find_active_with_status(
            operation=_VIDEO_SUMMARY_JOB_OPERATION,
            scope=_summary_job_scope(video_hash),
            owner_instance=_SUMMARY_OWNER_INSTANCE,
        )
    except ValueError:
        logger.error("Video summary job preparation failed")
        raise HTTPException(status_code=500, detail="Summary job ledger is unavailable")

    if not created:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "active_job_exists",
                "job": _public_summary_job(record),
            },
        )

    authority = None
    tool_args = {"job_id": record["job_id"], "video_hash": video_hash}
    token = None
    authorization_evidence_persisted = False
    try:
        authority = _get_summary_authority(cfg)
        envelope, return_code = authority.authorize_action(
            prompt="Prepare one exact video summary",
            mode="ops",
            tool_name=_VIDEO_SUMMARY_AUTH_OPERATION,
            tool_args=tool_args,
        )
        result = envelope.get("result") if isinstance(envelope, dict) else None
        token = result.get("confirmation_token") if isinstance(result, dict) else None
        request_id = envelope.get("request_id") if isinstance(envelope, dict) else None
        if (
            return_code != 3
            or envelope.get("status") != "needs_confirmation"
            or not isinstance(token, str)
            or not token
            or not isinstance(request_id, str)
            or not request_id
        ):
            raise RuntimeError("authorization_not_prepared")
        record = ledger.compare_and_update(
            record["job_id"],
            expected_state="pending_confirmation",
            token_fingerprint=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            authorization_request_id=request_id,
        )
        authorization_evidence_persisted = True
    except Exception:
        logger.error("Failed to prepare video summary authorization")
        if (
            authority is not None
            and isinstance(token, str)
            and token
            and not authorization_evidence_persisted
        ):
            try:
                authority.revoke_action_authorization(
                    prompt="Revoke unpersisted video summary authorization",
                    mode="ops",
                    tool_name=_VIDEO_SUMMARY_AUTH_OPERATION,
                    tool_args=tool_args,
                    confirmation_token=token,
                )
            except Exception:
                logger.error(
                    "Failed to revoke unpersisted video summary authorization"
                )
        try:
            record = ledger.transition(
                record["job_id"],
                expected_states="pending_confirmation",
                new_state="failed",
                outcome={
                    "code": "authorization_prepare_failed",
                    "message": "Video summary authorization could not be prepared",
                },
            )
        except Exception:
            logger.error("Failed to persist video summary preparation failure")
        raise HTTPException(status_code=503, detail="Summary authorization unavailable")

    return {
        "success": True,
        "confirmation_token": token,
        "job": _public_summary_job(record),
    }
