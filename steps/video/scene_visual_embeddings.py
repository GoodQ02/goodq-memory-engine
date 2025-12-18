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

logger = logging.getLogger(__name__)


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
    
    # Determine processing directory
    video_id = item.get('id', Path(video_path).stem)
    paths_cfg = (cfg.get('paths') or {}) if isinstance(cfg, dict) else {}
    processing_root = paths_cfg.get('processing')
    if not processing_root:
        data_root = paths_cfg.get('data_root', 'L:/_DATA/GoodQ_Data')
        processing_root = os.path.join(data_root, 'processing')
    processing_dir = os.path.join(processing_root, str(video_id))
    os.makedirs(processing_dir, exist_ok=True)
    
    # Load scene manifest from Phase 5
    scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
    if not os.path.exists(scene_manifest_path):
        alt_path = os.path.join(processing_dir, 'scene_manifest.json')
        if os.path.exists(alt_path):
            logger.warning(f"[PHASE6] Using legacy scene_manifest.json at: {alt_path}")
            scene_manifest_path = alt_path
        else:
            logger.warning(f"Scene manifest not found: {scene_manifest_path}")
            logger.info("Phase 6 requires Phase 5 scene detection to run first")
            return {"phase6_status": "skipped", "reason": "no_scene_manifest"}
    
    with open(scene_manifest_path, 'r', encoding='utf-8') as f:
        scene_data = json.load(f)
    
    scenes = scene_data.get('scenes', [])
    if not scenes:
        logger.warning("No scenes found in manifest")
        return {"phase6_status": "skipped", "reason": "no_scenes"}
    
    logger.info(f"[PHASE6] Processing {len(scenes)} scenes for video: {video_id}")
    
    # === STEP 1: Extract Frames ===
    extraction_strategy = phase6_cfg.get('frame_sampling_strategy', 'uniform')
    frames_per_scene = phase6_cfg.get('frames_per_scene', 3)
    
    logger.info(f"[PHASE6] Extracting frames: {frames_per_scene} per scene, strategy={extraction_strategy}")
    
    scene_frames = extract_scene_frames(
        video_path=video_path,
        scenes=scenes,
        output_base_dir=os.path.join(processing_dir, 'video'),
        strategy=extraction_strategy,
        frames_per_scene=frames_per_scene
    )
    
    if not scene_frames:
        logger.error("Frame extraction failed")
        return {"phase6_status": "error", "error": "frame_extraction_failed"}
    
    # === STEP 2: Generate CLIP Embeddings ===
    batch_size = phase6_cfg.get('max_gpu_batch_size', 8)
    
    logger.info("[PHASE6] Generating CLIP embeddings")
    clip_embeddings = embed_scene_frames(scene_frames, model_type='clip', batch_size=batch_size)
    
    # === STEP 3: Generate DINO Embeddings ===
    logger.info("[PHASE6] Generating DINO embeddings")
    dino_embeddings = embed_scene_frames(scene_frames, model_type='dino', batch_size=batch_size)
    
    # === STEP 4: Pool to Scene-Level ===
    pooling_strategy = phase6_cfg.get('pooling_strategy', 'mean')
    
    logger.info(f"[PHASE6] Pooling embeddings using '{pooling_strategy}' strategy")
    
    pooled_clip = pool_multiple_scenes(clip_embeddings, strategy=pooling_strategy)
    pooled_dino = pool_multiple_scenes(dino_embeddings, strategy=pooling_strategy)
    
    # === STEP 5: Store in Qdrant ===
    retrieval_cfg = phase6_cfg.get('retrieval', {})
    if retrieval_cfg.get('enable', True):
        logger.info("[PHASE6] Storing embeddings in Qdrant")
        
        # Store CLIP embeddings
        clip_collection = phase6_cfg.get('clip_collection', 'goodq_clip_scenes')
        clip_client = QdrantClient(QdrantConfig(
            host=cfg.get('qdrant_host', 'http://127.0.0.1:6333'),
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
            clip_client.upsert(clip_points)
            logger.info(f"  [SYMBOL] Stored {len(clip_points)} CLIP scene embeddings")
        
        # Store DINO embeddings
        dino_collection = phase6_cfg.get('dino_collection', 'goodq_dino_scenes')
        dino_client = QdrantClient(QdrantConfig(
            host=cfg.get('qdrant_host', 'http://127.0.0.1:6333'),
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
            dino_client.upsert(dino_points)
            logger.info(f"  [SYMBOL] Stored {len(dino_points)} DINO scene embeddings")
    
    # === STEP 6: Update Scene Manifest ===
    # Add embedding IDs to scene metadata
    for scene in scenes:
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
    scene_data['phase6_complete'] = True
    scene_data['embedding_stats'] = {
        'clip_scenes': len(pooled_clip),
        'dino_scenes': len(pooled_dino),
        'total_frames': sum(len(f) for f in scene_frames.values()),
        'pooling_strategy': pooling_strategy
    }
    
    with open(scene_manifest_path, 'w', encoding='utf-8') as f:
        json.dump(scene_data, f, indent=2)
    
    logger.info(f"[PHASE6] [OK] Complete! Processed {len(pooled_clip)} scenes with visual embeddings")
    
    return {
        "phase6_status": "complete",
        "scenes_processed": len(pooled_clip),
        "clip_embeddings": len(pooled_clip),
        "dino_embeddings": len(pooled_dino),
        "total_frames": sum(len(f) for f in scene_frames.values()),
        "scene_manifest_path": scene_manifest_path
    }
