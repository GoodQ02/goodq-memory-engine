"""
Phase 6: Scene Visual Embeddings Orchestrator
Main entry point for generating and storing scene-level visual embeddings.
Integrates frame extraction, embedding generation, pooling, and vector storage.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import json
import logging
from pathlib import Path

from steps.common.atomic_io import atomic_write_json
from steps.common.config_loader import get_runtime_paths

logger = logging.getLogger(__name__)


def _atomic_write_json(path: Path, data: Any) -> None:
    # Backward-compatible wrapper used by existing tests and helper call sites.
    atomic_write_json(path, data)


def _write_scene_manifest(scene_manifest_path: str, scene_data: Dict[str, Any]) -> None:
    _atomic_write_json(Path(scene_manifest_path), scene_data)


def _persist_phase6_failure(scene_manifest_path: str, scene_data: Dict[str, Any], error_reason: str) -> None:
    scene_data['phase6_complete'] = False
    scene_data['phase6_status'] = 'failed'
    scene_data['phase6_error'] = error_reason
    _write_scene_manifest(scene_manifest_path, scene_data)


def _resolve_processing_root(cfg: Dict[str, Any]) -> str:
    runtime_paths = get_runtime_paths(cfg, 'processing', require_canonical=False)
    return str(Path(runtime_paths['processing']).resolve())


def _stage10_18_debug(*parts: Any) -> None:
    line = "[STAGE10_18_DEBUG] " + " ".join(str(p) for p in parts)
    print(line)
    try:
        temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or "."
        debug_log_path = Path(temp_dir) / "stage10_18_debug.log"
        with debug_log_path.open("a", encoding="utf-8") as handle:
            print(line, file=handle)
    except Exception as e:
        logger.warning(
            "[PHASE6] Debug log write failed operation=%s exc_type=%s exc=%s",
            "stage10_18_debug",
            type(e).__name__,
            e,
        )


def run_scene_visual_embeddings(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 6 main orchestration: Extract frames, generate embeddings, pool to scene level.
    
    This step:
    1. Loads scene manifest from Phase 5
    2. Extracts representative frames per scene
    3. Generates CLIP and DINO embeddings for frames
    4. Pools frame embeddings to scene-level representations
    5. Stores embeddings in Qdrant/FAISS
    6. Updates temporal index with embedding IDs
    
    Args:
        item: Enriched item dict with video metadata
        cfg: Configuration dict
        
    Returns:
        Dict with scene embedding metadata
    """
    from steps.video.scene_frame_extractor import extract_scene_frames
    from steps.video.scene_embedder import embed_scene_frames
    from steps.video.embedding_pooler import pool_multiple_scenes
    from steps.common.qdrant_client import QdrantClient, QdrantConfig
    
    # Get Phase 6 config
    phase6_cfg = cfg.get('phase6', {})
    if not phase6_cfg.get('enabled', True):
        logger.info("Phase 6 disabled in config")
        return {"phase6_status": "disabled"}
    
    # Get video path and output directory
    video_path = item.get('source_path')
    if not video_path or not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return {"phase6_status": "error", "error": "video_not_found"}
    
    # Canonical semantic identifier used across KG/vector payload/telemetry.
    video_id_raw = item.get('video_id') or item.get('video_hash') or item.get('id')
    video_id = str(video_id_raw).strip() if video_id_raw is not None else ""
    if not video_id:
        video_id = Path(video_path).stem

    # Storage key may differ from semantic video_id to preserve existing directory layout.
    storage_key_raw = item.get('video_storage_key') or item.get('id') or video_id
    video_storage_key = str(storage_key_raw).strip() if storage_key_raw is not None else video_id
    if not video_storage_key:
        video_storage_key = video_id

    # Determine processing directory (prefer explicit path passed from ingestion orchestrator).
    processing_dir_raw = item.get('processing_dir')
    if isinstance(processing_dir_raw, str) and processing_dir_raw.strip():
        processing_dir = processing_dir_raw
    else:
        processing_root = _resolve_processing_root(cfg)
        processing_dir = os.path.join(processing_root, str(video_storage_key))
    os.makedirs(processing_dir, exist_ok=True)
    
    # Load scene manifest from Phase 5
    scene_manifest_path = item.get('scene_manifest_path')
    if not (isinstance(scene_manifest_path, str) and os.path.exists(scene_manifest_path)):
        scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
    if not os.path.exists(scene_manifest_path):
        alt_path = os.path.join(processing_dir, 'scene_manifest.json')
        if os.path.exists(alt_path):
            logger.warning(f"[PHASE6] Using legacy scene_manifest.json at: {alt_path}")
            scene_manifest_path = alt_path
        else:
            logger.warning(f"Scene manifest not found: {scene_manifest_path}")
            logger.info("Phase 6 requires Phase 5 scene detection to run first")
            return {"video_id": video_id, "phase6_status": "skipped", "reason": "no_scene_manifest"}
    
    with open(scene_manifest_path, 'r', encoding='utf-8') as f:
        scene_data = json.load(f)

    manifest_video_id = scene_data.get('video_id') if isinstance(scene_data, dict) else None
    if isinstance(manifest_video_id, str) and manifest_video_id.strip():
        video_id = manifest_video_id.strip()
    else:
        scene_data['video_id'] = video_id
    scene_data.setdefault('video_hash', video_id)
    
    scenes = scene_data.get('scenes', [])
    if not scenes:
        logger.warning("No scenes found in manifest")
        return {"video_id": video_id, "phase6_status": "skipped", "reason": "no_scenes"}
    
    logger.info(f"[PHASE6] Processing {len(scenes)} scenes for video: {video_id}")
    try:
        # === STEP 1: Extract Frames ===
        extraction_strategy = phase6_cfg.get('frame_sampling_strategy', 'uniform')
        frames_per_scene = phase6_cfg.get('frames_per_scene', 3)
        
        logger.info(f"[PHASE6] Extracting frames: {frames_per_scene} per scene, strategy={extraction_strategy}")
        
        scene_frames = extract_scene_frames(
            video_path=video_path,
            scenes=scenes,
            output_base_dir=os.path.join(processing_dir, 'video'),
            strategy=extraction_strategy,
            frames_per_scene=frames_per_scene,
            cfg=cfg,
        )
        frame_paths: List[str] = []
        for _scene_frames in scene_frames.values():
            if not isinstance(_scene_frames, list):
                continue
            for _frame in _scene_frames:
                if isinstance(_frame, dict):
                    _path = _frame.get('path')
                    if isinstance(_path, str):
                        frame_paths.append(_path)
        _stage10_18_debug("frame_count:", len(frame_paths))
        _stage10_18_debug("first_frame_paths:", frame_paths[:3])
        for _path in frame_paths[:3]:
            _stage10_18_debug("frame_exists:", _path, os.path.exists(_path))
        
        if not scene_frames:
            logger.error("Frame extraction failed")
            try:
                _persist_phase6_failure(scene_manifest_path, scene_data, "frame_extraction_failed")
            except Exception as e:
                logger.warning("[PHASE6] Failed to persist failure manifest state: %s", e)
            return {"video_id": video_id, "phase6_status": "error", "error": "frame_extraction_failed"}
        
        # === STEP 2: Generate CLIP Embeddings ===
        batch_size = phase6_cfg.get('max_gpu_batch_size', 8)
        clip_device = "unknown"
        try:
            from steps.common.gpu_config import configure_gpu as setup_step_gpu
            gpu_cfg = setup_step_gpu("scene_embedder_clip")
            if isinstance(gpu_cfg, dict):
                clip_device = str(gpu_cfg.get("device", "unknown"))
        except Exception as e:
            _stage10_18_debug("clip_device_probe_error:", f"{type(e).__name__}: {e}")
        _stage10_18_debug("clip_device:", clip_device)
        _stage10_18_debug("clip_batch_size:", batch_size)
        _stage10_18_debug("clip_model_id:", "openai/clip-vit-base-patch16")
        
        logger.info("[PHASE6] Generating CLIP embeddings")
        clip_embeddings = embed_scene_frames(scene_frames, model_type='clip', batch_size=batch_size)
        clip_model_loaded = False
        try:
            from steps.video import scene_embedder as _scene_embedder
            clip_model_loaded = bool((_scene_embedder._MODELS.get("clip") or {}).get("model") is not None)
        except Exception as e:
            _stage10_18_debug("clip_model_probe_error:", f"{type(e).__name__}: {e}")
        _stage10_18_debug(f"clip_model_loaded={clip_model_loaded}")
        raw_clip_count = 0
        sample_clip_len: Optional[int] = None
        for _emb_list in clip_embeddings.values():
            if isinstance(_emb_list, list):
                raw_clip_count += len(_emb_list)
                if sample_clip_len is None and _emb_list:
                    try:
                        sample_clip_len = len(_emb_list[0])
                    except Exception as e:
                        logger.warning(
                            "[PHASE6] Failed to probe clip vector length operation=%s exc_type=%s exc=%s",
                            "clip_vector_len_probe",
                            type(e).__name__,
                            e,
                        )
                        sample_clip_len = None
        _stage10_18_debug("raw_clip_embedding_count:", raw_clip_count)
        _stage10_18_debug("raw_clip_embedding_len:", sample_clip_len)
        clip_vector_dim = sample_clip_len or 0
        
        # === STEP 3: Generate DINO Embeddings ===
        logger.info("[PHASE6] Generating DINO embeddings")
        dino_embeddings = embed_scene_frames(scene_frames, model_type='dino', batch_size=batch_size)
        dino_model_loaded = False
        try:
            from steps.video import scene_embedder as _scene_embedder
            dino_model_loaded = bool((_scene_embedder._MODELS.get("dino") or {}).get("model") is not None)
        except Exception as e:
            _stage10_18_debug("dino_model_probe_error:", f"{type(e).__name__}: {e}")
        _stage10_18_debug(f"dino_model_loaded={dino_model_loaded}")
        raw_dino_count = 0
        sample_dino_len: Optional[int] = None
        for _emb_list in dino_embeddings.values():
            if isinstance(_emb_list, list):
                raw_dino_count += len(_emb_list)
                if sample_dino_len is None and _emb_list:
                    try:
                        sample_dino_len = len(_emb_list[0])
                    except Exception as e:
                        logger.warning(
                            "[PHASE6] Failed to probe dino vector length operation=%s exc_type=%s exc=%s",
                            "dino_vector_len_probe",
                            type(e).__name__,
                            e,
                        )
                        sample_dino_len = None
        _stage10_18_debug("raw_dino_embedding_count:", raw_dino_count)
        _stage10_18_debug("raw_dino_embedding_len:", sample_dino_len)
        dino_vector_dim = sample_dino_len or 0

        if frame_paths and (not clip_model_loaded or not dino_model_loaded):
            try:
                _persist_phase6_failure(scene_manifest_path, scene_data, "model_load_failed")
            except Exception as e:
                logger.warning("[PHASE6] Failed to persist failure manifest state: %s", e)
            return {
                "video_id": video_id,
                "phase6_status": "failed",
                "error": "model_load_failed",
                "clip_model_loaded": clip_model_loaded,
                "dino_model_loaded": dino_model_loaded,
                "total_frames": len(frame_paths),
                "clip_vector_dim": clip_vector_dim,
                "dino_vector_dim": dino_vector_dim,
                "scene_clip_vectors_written": 0,
                "scene_dino_vectors_written": 0,
                "gpu_device": clip_device,
            }
        
        # === STEP 4: Pool to Scene-Level ===
        pooling_strategy = phase6_cfg.get('pooling_strategy', 'mean')
        
        logger.info(f"[PHASE6] Pooling embeddings using '{pooling_strategy}' strategy")
        
        pooled_clip = pool_multiple_scenes(clip_embeddings, strategy=pooling_strategy)
        pooled_dino = pool_multiple_scenes(dino_embeddings, strategy=pooling_strategy)
        print("[STAGE10_16_DEBUG] pooled_clip_len:", len(pooled_clip))
        print("[STAGE10_16_DEBUG] pooled_dino_len:", len(pooled_dino))
        scene_clip_vectors_written = 0
        scene_dino_vectors_written = 0
        
        # === STEP 5: Store in Qdrant ===
        retrieval_cfg = phase6_cfg.get('retrieval', {})
        retrieval_enabled = retrieval_cfg.get('enable', True)
        clip_ok = True
        dino_ok = True
        if retrieval_enabled:
            logger.info("[PHASE6] Storing embeddings in Qdrant")
            host_value = cfg.get('qdrant_host', 'http://127.0.0.1:6333')
            clip_collection_name = phase6_cfg.get('clip_collection', 'goodq_clip_scenes')
            dino_collection_name = phase6_cfg.get('dino_collection', 'goodq_dino_scenes')
            print("[STAGE10_16_DEBUG] Phase6 host:", host_value)
            print("[STAGE10_16_DEBUG] clip_collection:", clip_collection_name)
            print("[STAGE10_16_DEBUG] dino_collection:", dino_collection_name)
            
            # Store CLIP embeddings
            clip_collection = clip_collection_name
            clip_client = QdrantClient(QdrantConfig(
                host=host_value,
                collection=clip_collection,
                dim=512,
                distance='Cosine'
            ))
            
            clip_points = []
            for scene_id, embedding in pooled_clip.items():
                point_id = f"clip_scene_{video_id}_{scene_id}"
                clip_points.append({
                    "id": point_id,
                    "vector": embedding.tolist(),
                    "payload": {
                        "video_id": video_id,
                        "scene_id": scene_id,
                        "type": "scene",
                        "model": "clip"
                    }
                })
            
            if clip_points:
                scene_clip_vectors_written = len(clip_points)
                result_clip = clip_client.upsert(clip_points)
                clip_ok = result_clip
                print("[STAGE10_16_DEBUG] upsert_clip_return:", result_clip)
                try:
                    from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_events, utc_now_iso
                    ts_utc = utc_now_iso()
                    emit_memory_commit_events(
                        cfg,
                        [
                            MemoryCommitEvent(
                                ts_utc=ts_utc,
                                scene_id=str((p.get("payload") or {}).get("scene_id")) if (p.get("payload") or {}).get("scene_id") is not None else None,
                                video_id=str((p.get("payload") or {}).get("video_id")) if (p.get("payload") or {}).get("video_id") is not None else None,
                                modality="clip",
                                model="clip",
                                embedding_id=str(p.get("id")) if p.get("id") is not None else None,
                                component="scene_visual_embeddings.clip",
                                targets={
                                    "qdrant": {
                                        "attempted": True,
                                        "committed": bool(clip_ok),
                                        "ref": clip_collection,
                                        "reason": None if clip_ok else "upsert_failed",
                                        "count": len(clip_points),
                                    }
                                },
                                details={"host": getattr(getattr(clip_client, "cfg", None), "host", None)},
                            )
                            for p in clip_points
                            if isinstance(p, dict)
                        ],
                    )
                except Exception as e:
                    _stage10_18_debug("swallowed_exception:", f"{type(e).__name__}: {e}")
                    logger.warning(
                        "[PHASE6] Commit event emission failed operation=%s collection=%s exc_type=%s exc=%s",
                        "emit_memory_commit_events.clip",
                        clip_collection,
                        type(e).__name__,
                        e,
                    )
                logger.info(f"  [SYMBOL] Stored {len(clip_points)} CLIP scene embeddings")
            
            # Store DINO embeddings
            dino_collection = dino_collection_name
            dino_client = QdrantClient(QdrantConfig(
                host=host_value,
                collection=dino_collection,
                dim=768,
                distance='Cosine'
            ))
            
            dino_points = []
            for scene_id, embedding in pooled_dino.items():
                point_id = f"dino_scene_{video_id}_{scene_id}"
                dino_points.append({
                    "id": point_id,
                    "vector": embedding.tolist(),
                    "payload": {
                        "video_id": video_id,
                        "scene_id": scene_id,
                        "type": "scene",
                        "model": "dino"
                    }
                })
            
            if dino_points:
                scene_dino_vectors_written = len(dino_points)
                result_dino = dino_client.upsert(dino_points)
                dino_ok = result_dino
                print("[STAGE10_16_DEBUG] upsert_dino_return:", result_dino)
                try:
                    from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_events, utc_now_iso
                    ts_utc = utc_now_iso()
                    emit_memory_commit_events(
                        cfg,
                        [
                            MemoryCommitEvent(
                                ts_utc=ts_utc,
                                scene_id=str((p.get("payload") or {}).get("scene_id")) if (p.get("payload") or {}).get("scene_id") is not None else None,
                                video_id=str((p.get("payload") or {}).get("video_id")) if (p.get("payload") or {}).get("video_id") is not None else None,
                                modality="dino",
                                model="dino",
                                embedding_id=str(p.get("id")) if p.get("id") is not None else None,
                                component="scene_visual_embeddings.dino",
                                targets={
                                    "qdrant": {
                                        "attempted": True,
                                        "committed": bool(dino_ok),
                                        "ref": dino_collection,
                                        "reason": None if dino_ok else "upsert_failed",
                                        "count": len(dino_points),
                                    }
                                },
                                details={"host": getattr(getattr(dino_client, "cfg", None), "host", None)},
                            )
                            for p in dino_points
                            if isinstance(p, dict)
                        ],
                    )
                except Exception as e:
                    _stage10_18_debug("swallowed_exception:", f"{type(e).__name__}: {e}")
                    logger.warning(
                        "[PHASE6] Commit event emission failed operation=%s collection=%s exc_type=%s exc=%s",
                        "emit_memory_commit_events.dino",
                        dino_collection,
                        type(e).__name__,
                        e,
                    )
                logger.info(f"  [SYMBOL] Stored {len(dino_points)} DINO scene embeddings")
        
        # === STEP 6: Update Scene Manifest ===
        # Add embedding IDs to scene metadata
        for scene in scenes:
            scene.setdefault('video_id', video_id)
            scene_id = scene.get('id', scene.get('scene_id', 0))
            
            if scene_id in pooled_clip:
                scene['clip_id'] = f"clip_scene_{video_id}_{scene_id}"
                scene['clip_dim'] = 512
            
            if scene_id in pooled_dino:
                scene['dino_id'] = f"dino_scene_{video_id}_{scene_id}"
                scene['dino_dim'] = 768
            
            # Add frame info
            if scene_id in scene_frames:
                frames = scene_frames[scene_id]
                scene['frame_count'] = len(frames)
                scene['frame_paths'] = [f['path'] for f in frames]
                if frames:
                    scene['representative_frame'] = frames[len(frames)//2]['path']  # Middle frame
        
        # Save updated manifest
        phase6_vector_points_attempted = int(scene_clip_vectors_written + scene_dino_vectors_written)
        phase6_qdrant_ok: Any = (
            bool(clip_ok and dino_ok)
            if retrieval_enabled and phase6_vector_points_attempted > 0
            else 'not_attempted'
        )
        phase6_faiss_ok: Any = 'not_attempted'
        vector_commit_success = bool(phase6_qdrant_ok is True or phase6_qdrant_ok == 'not_attempted')
        scene_data['phase6_complete'] = vector_commit_success
        scene_data['phase6_vector_commit'] = {
            'enabled': retrieval_enabled,
            'clip_committed': bool(clip_ok),
            'dino_committed': bool(dino_ok),
            'vector_points_attempted': phase6_vector_points_attempted,
            'qdrant_ok': phase6_qdrant_ok,
            'faiss_ok': phase6_faiss_ok,
        }
        scene_data['embedding_stats'] = {
            'clip_scenes': len(pooled_clip),
            'dino_scenes': len(pooled_dino),
            'total_frames': sum(len(f) for f in scene_frames.values()),
            'pooling_strategy': pooling_strategy
        }
        
        _write_scene_manifest(scene_manifest_path, scene_data)
        
        if vector_commit_success:
            logger.info(f"[PHASE6] [OK] Complete! Processed {len(pooled_clip)} scenes with visual embeddings")
        else:
            logger.error(
                "[PHASE6] [FAIL] Vector commit incomplete (clip_ok=%s dino_ok=%s)",
                clip_ok,
                dino_ok,
            )
        
        return {
            "video_id": video_id,
            "phase6_status": "complete" if vector_commit_success else "failed",
            "error": None if vector_commit_success else "vector_commit_failed",
            "scenes_processed": len(pooled_clip),
            "clip_embeddings": len(pooled_clip),
            "dino_embeddings": len(pooled_dino),
            "total_frames": sum(len(f) for f in scene_frames.values()),
            "scene_manifest_path": scene_manifest_path,
            "clip_vector_dim": clip_vector_dim,
            "dino_vector_dim": dino_vector_dim,
            "scene_clip_vectors_written": scene_clip_vectors_written,
            "scene_dino_vectors_written": scene_dino_vectors_written,
            "vector_points_attempted": phase6_vector_points_attempted,
            "clip_committed": bool(clip_ok),
            "dino_committed": bool(dino_ok),
            "qdrant_ok": phase6_qdrant_ok,
            "faiss_ok": phase6_faiss_ok,
            "gpu_device": clip_device,
        }
    except Exception as e:
        logger.exception("[PHASE6] Unhandled exception after manifest load")
        error_reason = f"exception:{type(e).__name__}:{e}"
        try:
            _persist_phase6_failure(scene_manifest_path, scene_data, error_reason)
        except Exception as persist_error:
            logger.warning("[PHASE6] Failed to persist failure manifest state after exception: %s", persist_error)
        return {
            "video_id": video_id,
            "phase6_status": "failed",
            "error": "exception",
            "exc_type": type(e).__name__,
            "exception": str(e),
            "scene_manifest_path": scene_manifest_path,
        }
