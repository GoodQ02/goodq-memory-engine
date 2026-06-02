"""
System API routes for GoodQ4All.
Provides system status, control, and management endpoints.
"""
from __future__ import annotations
from typing import List
import logging
import os
import json
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
    UnstitchedPattern,
    StitchPreviewRequest,
    StitchPreviewResponse,
    StitchRequest,
    StitchResponse,
    StitchRevokeRequest,
    StitchRevokeResponse,
    ManualMappingsResponse,
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
        
        # Check if goodq_core environment or sandboxed Python is available
        goodq_core_available = False
        try:
            # Check if we are running in a sandboxed installation
            app_root = Path(__file__).resolve().parents[2]  # api/routes/system.py -> app root
            sandbox_python = app_root / "runtime" / "python.exe"
            if sandbox_python.exists():
                result = subprocess.run(
                    [str(sandbox_python), "-c", "import goodq_version; print('OK')"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                goodq_core_available = (result.returncode == 0)
            else:
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
                phase6_complete=metadata.get('phase6_complete', False),
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


def _get_kg_db_path() -> Path:
    from steps.common.config_loader import load_configs
    cfg = load_configs({})
    return Path(cfg.get("paths", {}).get("knowledge_graph_db", "data/knowledge_graph.db"))


@router.get("/identity/unstitched", response_model=List[UnstitchedPattern])
async def get_unstitched_patterns():
    """Get all speaker patterns that are not mapped/stitched to any person."""
    db_path = _get_kg_db_path()
    from lib.knowledge_graph import KnowledgeGraph
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge graph database not found at {db_path}")

    try:
        with KnowledgeGraph(str(db_path)) as kg:
            cur = kg.conn.cursor()
            rows = cur.execute(
                """
                SELECT id, name, properties, occurrence_count
                FROM nodes
                WHERE node_type = 'speaker_pattern'
                  AND id NOT IN (
                      SELECT DISTINCT e.source_id
                      FROM edges e
                      JOIN nodes target ON e.target_id = target.id
                      WHERE e.edge_type IN ('identity_evidence', 'identity_supported')
                        AND target.node_type = 'person'
                  )
                ORDER BY occurrence_count DESC
                """
            ).fetchall()
            
            results = []
            for row in rows:
                props = json.loads(row["properties"]) if isinstance(row["properties"], str) else (row["properties"] or {})
                voiced_seconds = float(props.get("total_voiced_seconds") or 0.0)
                segment_count = int(props.get("signature_count") or 0)
                
                # Fetch a sample transcript excerpt
                pattern_id = int(row["id"])
                sample_rows = cur.execute(
                    """
                    SELECT nm.context
                    FROM node_media nm
                    JOIN edges e ON nm.node_id = e.source_id
                    WHERE e.target_id = ? AND e.edge_type = 'voice_pattern_match'
                    """,
                    (pattern_id,)
                ).fetchall()
                
                sample_transcript = None
                for r in sample_rows:
                    ctx = json.loads(r["context"]) if isinstance(r["context"], str) else (r["context"] or {})
                    text = ctx.get("text")
                    if isinstance(text, str) and text.strip():
                        sample_transcript = text.strip()
                        break
                        
                results.append(
                    UnstitchedPattern(
                        node_id=pattern_id,
                        node_name=str(row["name"]),
                        occurrence_count=int(row["occurrence_count"] or 1),
                        voiced_seconds=voiced_seconds,
                        segment_count=segment_count,
                        sample_transcript=sample_transcript,
                    )
                )
            return results
    except Exception as e:
        logger.error(f"Failed to get unstitched patterns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identity/stitch/preview", response_model=StitchPreviewResponse)
async def preview_stitch(request: StitchPreviewRequest):
    """Preview mapping impact and identify potential name or mapping conflicts."""
    db_path = _get_kg_db_path()
    from lib.knowledge_graph import KnowledgeGraph
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge graph database not found at {db_path}")

    try:
        with KnowledgeGraph(str(db_path)) as kg:
            cur = kg.conn.cursor()
            
            # Find the source pattern id
            source_row = cur.execute(
                "SELECT id FROM nodes WHERE node_type = 'speaker_pattern' AND name = ?",
                (request.source_node_name,)
            ).fetchone()
            
            if not source_row:
                raise HTTPException(status_code=404, detail=f"Source speaker pattern not found: {request.source_node_name}")
                
            source_id = int(source_row["id"])
            
            # Calculate affected scenes and episodes
            counts_row = cur.execute(
                """
                SELECT COUNT(DISTINCT nm.media_id) AS scene_count,
                       COUNT(DISTINCT mn.media_path) AS episode_count
                FROM node_media nm
                JOIN media_nodes mn ON nm.media_id = mn.id
                WHERE nm.node_id = ?
                """,
                (source_id,)
            ).fetchone()
            
            scenes_affected = int(counts_row["scene_count"] or 0) if counts_row else 0
            episodes_affected = int(counts_row["episode_count"] or 0) if counts_row else 0
            
            # Identify conflicts (any existing mappings from this pattern to a different person name)
            conflict_rows = cur.execute(
                """
                SELECT t.name AS person_name, e.edge_type, e.weight
                FROM edges e
                JOIN nodes t ON e.target_id = t.id
                WHERE e.source_id = ?
                  AND e.edge_type IN ('identity_evidence', 'identity_supported')
                  AND t.node_type = 'person'
                  AND t.name != ?
                """,
                (source_id, request.target_person_name)
            ).fetchall()
            
            conflicts = []
            for row in conflict_rows:
                conflicts.append({
                    "conflicting_person": str(row["person_name"]),
                    "edge_type": str(row["edge_type"]),
                    "weight": float(row["weight"])
                })
                
            return StitchPreviewResponse(
                success=True,
                source_node_name=request.source_node_name,
                target_person_name=request.target_person_name,
                scenes_affected=scenes_affected,
                episodes_affected=episodes_affected,
                conflicts=conflicts
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview stitch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identity/stitch", response_model=StitchResponse)
async def execute_stitch(request: StitchRequest):
    """Commit a manual identity mapping, save it to persistent store, and rebuild the identity ledger."""
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation required. Call /preview first.")
        
    db_path = _get_kg_db_path()
    from lib.knowledge_graph import KnowledgeGraph
    from lib.identity_ledger import load_manual_mappings, save_manual_mappings, build_identity_ledger
    import sqlite3
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge graph database not found at {db_path}")

    try:
        with KnowledgeGraph(str(db_path)) as kg:
            cur = kg.conn.cursor()
            
            # Find the source pattern id
            source_row = cur.execute(
                "SELECT id FROM nodes WHERE node_type = 'speaker_pattern' AND name = ?",
                (request.source_node_name,)
            ).fetchone()
            
            if not source_row:
                raise HTTPException(status_code=404, detail=f"Source speaker pattern not found: {request.source_node_name}")
                
            source_id = int(source_row["id"])
            
            # Resolve or create target_id for the person node
            target_id = kg.add_node(
                node_type="person",
                name=request.target_person_name,
                properties={"source": "operator_manual_override"},
                timestamp=None
            )
            
            # Load, update, and save manual mappings JSON
            mappings_data = load_manual_mappings(db_path)
            mappings = mappings_data.setdefault("mappings", [])
            
            # Find if there is an existing mapping for this source_node_name
            existing_mapping = next(
                (m for m in mappings if m.get("source_node_name") == request.source_node_name),
                None
            )
            
            mapping_id = f"map_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            history_entry = {
                "status": "active",
                "timestamp_utc": datetime.utcnow().isoformat() + "Z",
                "operator_note": request.operator_note or ""
            }
            
            if existing_mapping:
                mapping_id = existing_mapping.get("mapping_id", mapping_id)
                existing_mapping["target_person_name"] = request.target_person_name
                existing_mapping["status"] = "active"
                existing_mapping.setdefault("history", []).append(history_entry)
            else:
                mappings.append({
                    "mapping_id": mapping_id,
                    "source_node_type": "speaker_pattern",
                    "source_node_name": request.source_node_name,
                    "target_person_name": request.target_person_name,
                    "status": "active",
                    "history": [history_entry]
                })
                
            save_manual_mappings(db_path, mappings_data)
            
            # Delete any existing manual override edges for this source pattern in the graph database
            rows = cur.execute(
                "SELECT id, properties FROM edges WHERE source_id = ? AND edge_type = 'identity_evidence'",
                (source_id,)
            ).fetchall()
            edge_ids_to_delete = []
            for r in rows:
                props = json.loads(r["properties"]) if isinstance(r["properties"], str) else (r["properties"] or {})
                if props.get("source") == "operator_manual_override":
                    edge_ids_to_delete.append(int(r["id"]))
            if edge_ids_to_delete:
                placeholders = ",".join("?" for _ in edge_ids_to_delete)
                cur.execute(f"DELETE FROM edges WHERE id IN ({placeholders})", edge_ids_to_delete)
                kg.conn.commit()

            # Add mapping to graph database
            edge_id = kg.add_edge(
                source_id=source_id,
                target_id=target_id,
                edge_type="identity_evidence",
                weight=1.0,
                properties={
                    "source": "operator_manual_override",
                    "mapping_id": mapping_id,
                    "operator_note": request.operator_note or ""
                }
            )
            
            # Build scene_episode_map from media_nodes table to refresh ledger metrics
            media_rows = cur.execute("SELECT scene_id, properties FROM media_nodes").fetchall()
            scene_episode_map = {}
            episodes_set = set()
            for r in media_rows:
                scene_id = r["scene_id"]
                if not scene_id:
                    continue
                props = json.loads(r["properties"]) if isinstance(r["properties"], str) else (r["properties"] or {})
                video_id = props.get("video_id")
                if video_id:
                    scene_episode_map[scene_id] = video_id
                    episodes_set.add(video_id)
                    
            episodes = [{"episode": ep} for ep in sorted(episodes_set)]
            
            # Regenerate ledger reports
            ledger = build_identity_ledger(
                graph_db_path=db_path,
                scene_episode_map=scene_episode_map,
                episodes=episodes,
            )
            
            # Save ledger json and markdown next to knowledge_graph.db
            ledger_json_path = db_path.parent / "identity_ledger.json"
            ledger_json_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            
            from lib.identity_ledger import write_identity_ledger_markdown
            write_identity_ledger_markdown(ledger, db_path.parent / "identity_ledger.md")
            
            return StitchResponse(
                success=True,
                message=f"Successfully stitched {request.source_node_name} to {request.target_person_name}.",
                mapping_id=mapping_id,
                edge_id=edge_id
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute stitch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/identity/mappings", response_model=ManualMappingsResponse)
async def get_manual_mappings():
    """Get all manual mappings stored in manual_identity_mappings.json."""
    db_path = _get_kg_db_path()
    from lib.identity_ledger import load_manual_mappings
    try:
        data = load_manual_mappings(db_path)
        return data
    except Exception as e:
        logger.error(f"Failed to load manual mappings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identity/stitch/revoke", response_model=StitchRevokeResponse)
async def revoke_stitch(request: StitchRevokeRequest):
    """Revoke a manual identity mapping using mapping_id (primary) or legacy source_node_name (optional)."""
    db_path = _get_kg_db_path()
    from lib.knowledge_graph import KnowledgeGraph
    from lib.identity_ledger import load_manual_mappings, save_manual_mappings, build_identity_ledger
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge graph database not found at {db_path}")

    try:
        mappings_data = load_manual_mappings(db_path)
        mappings = mappings_data.setdefault("mappings", [])
        
        target_mapping = None
        
        # 1. Lookup by mapping_id
        if request.mapping_id:
            target_mapping = next(
                (m for m in mappings if m.get("mapping_id") == request.mapping_id),
                None
            )
            if not target_mapping:
                raise HTTPException(status_code=404, detail=f"Mapping not found for id: {request.mapping_id}")
                
        # 2. Lookup by legacy source_node_name
        elif request.source_node_name:
            matching_mappings = [
                m for m in mappings
                if m.get("source_node_name") == request.source_node_name and m.get("status") == "active"
            ]
            
            if len(matching_mappings) > 1:
                # Ambiguous legacy lookup conflict (409)
                raise HTTPException(
                    status_code=409,
                    detail=f"Ambiguous mapping request: multiple active mappings match source_node_name '{request.source_node_name}'. Please specify mapping_id."
                )
            elif len(matching_mappings) == 1:
                target_mapping = matching_mappings[0]
            else:
                raise HTTPException(status_code=404, detail=f"No active mapping found for source_node_name: {request.source_node_name}")
                
        else:
            raise HTTPException(status_code=400, detail="Either mapping_id or source_node_name must be provided.")
            
        # Revoke the mapping (idempotency support)
        if target_mapping.get("status") == "revoked":
            return StitchRevokeResponse(
                success=True,
                message=f"Mapping {target_mapping.get('mapping_id')} is already revoked."
            )
            
        # Update status and append to history (retaining previous history)
        target_mapping["status"] = "revoked"
        history_entry = {
            "status": "revoked",
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "operator_note": request.operator_note or "Revoked by operator"
        }
        target_mapping.setdefault("history", []).append(history_entry)
        
        # Save JSON changes
        save_manual_mappings(db_path, mappings_data)
        
        # Database changes must be projection-only.
        # Find and delete matching manual override edge in graph database
        with KnowledgeGraph(str(db_path)) as kg:
            cur = kg.conn.cursor()
            
            rows = cur.execute(
                "SELECT id, properties FROM edges WHERE edge_type = 'identity_evidence'"
            ).fetchall()
            
            edge_ids_to_delete = []
            for r in rows:
                props = json.loads(r["properties"]) if isinstance(r["properties"], str) else (r["properties"] or {})
                if props.get("source") == "operator_manual_override" and props.get("mapping_id") == target_mapping["mapping_id"]:
                    edge_ids_to_delete.append(int(r["id"]))
                    
            if edge_ids_to_delete:
                placeholders = ",".join("?" for _ in edge_ids_to_delete)
                cur.execute(f"DELETE FROM edges WHERE id IN ({placeholders})", edge_ids_to_delete)
                kg.conn.commit()
                
            # Rebuild the identity ledger / read-model only
            media_rows = cur.execute("SELECT scene_id, properties FROM media_nodes").fetchall()
            scene_episode_map = {}
            episodes_set = set()
            for r in media_rows:
                scene_id = r["scene_id"]
                if not scene_id:
                    continue
                props = json.loads(r["properties"]) if isinstance(r["properties"], str) else (r["properties"] or {})
                video_id = props.get("video_id")
                if video_id:
                    scene_episode_map[scene_id] = video_id
                    episodes_set.add(video_id)
                    
            episodes = [{"episode": ep} for ep in sorted(episodes_set)]
            
            ledger = build_identity_ledger(
                graph_db_path=db_path,
                scene_episode_map=scene_episode_map,
                episodes=episodes,
            )
            
            ledger_json_path = db_path.parent / "identity_ledger.json"
            ledger_json_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            
            from lib.identity_ledger import write_identity_ledger_markdown
            write_identity_ledger_markdown(ledger, db_path.parent / "identity_ledger.md")
            
        return StitchRevokeResponse(
            success=True,
            message=f"Successfully revoked mapping {target_mapping.get('mapping_id')} for {target_mapping.get('source_node_name')}."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke stitch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

