"""
System API routes for GoodQ4All.
Provides system status, control, and management endpoints.
"""
from __future__ import annotations
from typing import List
import logging
import os
import subprocess
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body
from pathlib import Path

from api.utils.response_models import (
    SystemStatus,
    IngestRequest,
    IngestResponse,
    VideoListItem,
    SystemMutationResponse,
    MutationPolicy,
)
from api.utils.loaders import DataLoader
from api.utils.media_projection import thumbnail_projection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])

_data_loader = None
_MUTATION_POLICY = MutationPolicy()
_INGEST_REQUIRED_CAPABILITIES = [
    "explicit confirmation token",
    "policy profile selection",
    "execution budget preflight",
    "checkpointed handoff into the canonical runtime",
    "auditable request and run records",
]
_OPERATOR_ONLY_REQUIRED_CAPABILITIES = [
    "explicit operator intent",
    "confirmation-gated maintenance session",
    "policy profile selection",
    "execution budget preflight",
    "checkpointed maintenance workflow",
    "auditable maintenance records",
]
_INGEST_OPERATOR_SURFACES = [
    "conda run -n goodq_core python -m cli.watchdog",
    "conda run -n goodq_core python -m cli.run_ingestion --input-dir <path>",
    "<GOODQ_DATA_ROOT>/GoodQ_Data/import_inbox",
]
_REINDEX_OPERATOR_SURFACES = [
    "operator-only maintenance workflow",
    "explicit audit before index rebuild",
]
_RELOAD_OPERATOR_SURFACES = [
    "operator-only maintenance workflow",
    "explicit restart or maintenance session after config review",
]


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("[OK] Data loader initialized for system")
    
    return _data_loader


def _build_mutation_response(
    *,
    route: str,
    mode: str,
    message: str,
    canonical_runtime_path: str,
    operator_surfaces: list[str],
    required_capabilities: list[str],
    next_step: str,
) -> SystemMutationResponse:
    return SystemMutationResponse(
        status="disabled",
        allowed=False,
        route=route,
        mode=mode,
        message=message,
        canonical_runtime_path=canonical_runtime_path,
        operator_surfaces=operator_surfaces,
        required_capabilities=required_capabilities,
        next_step=next_step,
        policy=_MUTATION_POLICY,
    )


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    Get current system status.
    
    Returns:
        System health and statistics
    """
    try:
        loader = get_data_loader()
        
        # Check if goodq_core environment is available
        goodq_core_available = False
        try:
            from steps.common.tool_paths import resolve_conda

            conda_exe = resolve_conda()
            result = subprocess.run(
                [conda_exe, 'run', '-n', 'goodq_core', 'python', '-c', 'print("OK")'],
                capture_output=True,
                text=True,
                timeout=5
            )
            goodq_core_available = (result.returncode == 0)
        except Exception:
            pass
        
        # Check Qdrant availability
        qdrant_available = False
        try:
            import requests
            resp = requests.get('http://localhost:6333/collections', timeout=2)
            qdrant_available = (resp.status_code == 200)
        except Exception:
            pass
        
        # Count processed videos
        video_ids = loader.list_processed_videos()
        total_videos = len(video_ids)
        
        # Count total scenes
        total_scenes = 0
        for video_id in video_ids:
            metadata = loader.get_video_metadata(video_id)
            total_scenes += metadata.get('total_scenes', 0)
        
        return SystemStatus(
            status="healthy" if goodq_core_available else "degraded",
            goodq_core_available=goodq_core_available,
            qdrant_available=qdrant_available,
            total_videos_processed=total_videos,
            total_scenes_indexed=total_scenes,
            indexes={
                'goodq_text': 'active' if qdrant_available else 'unknown',
                'goodq_clip_scenes': 'active' if qdrant_available else 'unknown',
                'goodq_dino_scenes': 'active' if qdrant_available else 'unknown'
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/videos", response_model=List[VideoListItem])
async def list_videos():
    """
    List all processed videos.
    
    Returns:
        List of videos with basic metadata
    """
    try:
        loader = get_data_loader()
        video_ids = loader.list_processed_videos()
        
        videos = []
        for video_id in video_ids:
            metadata = loader.get_video_metadata(video_id)
            
            # Get thumbnail projection from the first scene without exposing local paths.
            thumbnail_reference = None
            temporal_index = loader.load_temporal_index(video_id)
            if temporal_index and temporal_index.get('segments'):
                first_segment = temporal_index['segments'][0]
                thumbnail_reference = first_segment.get('representative_frame')
            projected_thumbnail = thumbnail_projection(video_id, thumbnail_reference)
            
            video_item = VideoListItem(
                video_id=video_id,
                title=metadata.get('title', video_id),
                duration=metadata.get('duration'),
                total_scenes=metadata.get('total_scenes'),
                processed_date=(
                    datetime.fromtimestamp(metadata['processed_date']).isoformat()
                    if metadata.get('processed_date')
                    else None
                ),
                **projected_thumbnail,
            )
            videos.append(video_item)
        
        return videos
        
    except Exception as e:
        logger.error(f"Failed to list videos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {str(e)}")


@router.post("/ingest", response_model=IngestResponse)
async def start_ingest(request: IngestRequest = Body(...)):
    """
    Start ingestion of a new file.
    
    Args:
        request: Ingest request with file path and options
        
    Returns:
        Ingest job ID and status
    """
    return IngestResponse(
        job_id="disabled",
        status="disabled",
        allowed=False,
        route="/api/system/ingest",
        mode="future_controlled_facade",
        message=(
            "Ingest stays disabled on the API surface until it can operate as an "
            "explicit, confirmation-gated, policy-driven, budgeted, checkpointed, "
            "and auditable facade over the canonical watchdog/CLI runtime."
        ),
        canonical_runtime_path=(
            "Use the canonical ingest path through cli.watchdog, cli.run_ingestion, "
            "or the configured import_inbox; no supported API mutation facade exists yet."
        ),
        operator_surfaces=_INGEST_OPERATOR_SURFACES,
        required_capabilities=_INGEST_REQUIRED_CAPABILITIES,
        next_step=(
            "Drop files into <GOODQ_DATA_ROOT>/GoodQ_Data/import_inbox for watchdog "
            "or invoke cli.run_ingestion directly."
        ),
        policy=_MUTATION_POLICY,
    )


@router.post("/reindex", response_model=SystemMutationResponse)
async def rebuild_indexes():
    """
    Rebuild all vector indexes.
    
    Returns:
        Success message
    """
    return _build_mutation_response(
        route="/api/system/reindex",
        mode="operator_only",
        message=(
            "Reindex remains operator-only until a real policy-driven maintenance "
            "control plane exists."
        ),
        canonical_runtime_path=(
            "No supported public API facade exists for index rebuilds; use an explicit "
            "operator maintenance workflow after audit."
        ),
        operator_surfaces=_REINDEX_OPERATOR_SURFACES,
        required_capabilities=_OPERATOR_ONLY_REQUIRED_CAPABILITIES,
        next_step=(
            "Keep reindexing in audited operator workflows; do not trigger it through "
            "the public API surface."
        ),
    )


@router.post("/reload", response_model=SystemMutationResponse)
async def reload_config():
    """
    Reload system configuration.
    
    Returns:
        Success message
    """
    return _build_mutation_response(
        route="/api/system/reload",
        mode="operator_only",
        message=(
            "Config reload remains operator-only until a real policy-driven control "
            "plane can make runtime mutation explicit, checkpointed, and auditable."
        ),
        canonical_runtime_path=(
            "No supported public API facade exists for runtime reload; use an explicit "
            "operator maintenance workflow after config review."
        ),
        operator_surfaces=_RELOAD_OPERATOR_SURFACES,
        required_capabilities=_OPERATOR_ONLY_REQUIRED_CAPABILITIES,
        next_step=(
            "Keep runtime reload in explicit operator maintenance sessions; do not "
            "treat it as a casual API mutation."
        ),
    )
