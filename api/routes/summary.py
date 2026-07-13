"""
Summary API routes for GoodQ4All.
Provides dashboard, entity profile aggregation, and custom collections.
"""
from __future__ import annotations

import logging
import hashlib
import hmac
from pathlib import Path
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
    SaveCollectionResponse
)
from api.utils.loaders import DataLoader
from api.utils.action_jobs import ActionJobLedger, ActionJobTransitionError
from lib import summary_aggregator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summary", tags=["summary"])

_data_loader = None

_VIDEO_SUMMARY_JOB_OPERATION = "video_summary.generate"
_VIDEO_SUMMARY_AUTH_OPERATION = "generate_video_summary"
_SUMMARY_OWNER_INSTANCE = f"summary-api-{uuid.uuid4().hex}"


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


@router.post("/collections", response_model=SaveCollectionResponse)
async def create_collection(request: SaveCollectionRequest = Body(...)):
    """
    Create a new manual playlist highlight collection.
    """
    db_path = _get_kg_db_path()
    try:
        req_dict = request.dict()
        new_col = summary_aggregator.add_collection(db_path, req_dict)
        return SaveCollectionResponse(
            success=True,
            message=f"Collection '{request.name}' successfully created.",
            collection=new_col
        )
    except Exception as e:
        logger.error(f"Failed to create collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_id}", response_model=dict)
async def delete_collection(
    collection_id: str = PathParam(..., description="Unique ID of the collection to soft-delete")
):
    """
    Soft-delete a custom collection.
    """
    db_path = _get_kg_db_path()
    try:
        success = summary_aggregator.soft_delete_collection(db_path, collection_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Active collection not found for ID: {collection_id}")
        return {"success": True, "message": f"Collection '{collection_id}' was soft-deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

    ledger = _get_summary_job_ledger(cfg)
    scope = _summary_job_scope(video_hash)
    if job_id is not None:
        try:
            record = ledger.load(job_id)
        except ValueError:
            record = None
        if (
            record is None
            or record.get("operation") != _VIDEO_SUMMARY_JOB_OPERATION
            or record.get("scope") != scope
        ):
            raise HTTPException(status_code=404, detail="Summary job not found")
    else:
        record = ledger.latest(
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
        if record.get("owner_instance") != _SUMMARY_OWNER_INSTANCE:
            raise HTTPException(
                status_code=409,
                detail={"code": "job_owner_changed", "job": _public_summary_job(record)},
            )
        if record.get("state") != "pending_confirmation":
            raise HTTPException(
                status_code=409,
                detail={"code": "job_not_confirmable", "job": _public_summary_job(record)},
            )
        fingerprint = hashlib.sha256(confirmation_token.encode("utf-8")).hexdigest()
        if not isinstance(record.get("token_fingerprint"), str) or not hmac.compare_digest(
            record["token_fingerprint"], fingerprint
        ):
            raise HTTPException(status_code=403, detail="Confirmation token mismatch")

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
                detail={"code": "job_not_confirmable", "job": _public_summary_job(current)},
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
        if not authorized:
            error_code = _authorization_error_code(envelope)
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
