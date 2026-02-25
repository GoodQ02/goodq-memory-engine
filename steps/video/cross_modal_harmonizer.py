"""
Phase 6: Cross-Modal Harmonizer
Fuses scene embeddings with audio, transcript, and metadata into unified temporal index.
Creates the multimodal knowledge graph foundation for retrieval.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import json
import logging
import sqlite3
from pathlib import Path

from steps.common.atomic_io import atomic_write_json

logger = logging.getLogger(__name__)
_PROCESSING_FALLBACK_WARNED = False

try:
    from steps.video.entity_extractor import extract_entities_from_scene, EntityExtractor
    ENTITY_EXTRACTION_AVAILABLE = True
except ImportError:
    ENTITY_EXTRACTION_AVAILABLE = False
    logger.warning("Entity extractor not available")


def load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON file with error handling."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
    return None


def _load_commit_presence(cfg: Dict[str, Any], video_id: str, scene_ids: List[str] | None = None) -> Dict[str, Any]:
    """Best-effort: derive modality presence from committed memory events (authoritative)."""
    paths_cfg = (cfg.get('paths') or {}) if isinstance(cfg, dict) else {}
    db_path = paths_cfg.get('db_path')
    if not db_path and paths_cfg.get('db_dir'):
        db_path = os.path.join(paths_cfg['db_dir'], 'memory.db')

    presence = {
        'available': False,
        'has_audio': False,
        'has_transcripts': False,
        'audio_scene_ids': set(),
        'transcript_scene_ids': set(),
    }

    if not isinstance(db_path, str) or not db_path:
        return presence
    if not os.path.exists(db_path):
        return presence

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        cur = conn.cursor()

        def _has_any_by_video(modality: str) -> bool:
            cur.execute(
                """
                SELECT 1
                FROM memory_commit_events
                WHERE video_id = ?
                  AND modality = ?
                  AND attempted = 1
                  AND committed = 1
                LIMIT 1
                """,
                (video_id, modality),
            )
            return cur.fetchone() is not None

        def _scene_ids_by_video(modality: str) -> set[str]:
            cur.execute(
                """
                SELECT DISTINCT scene_id
                FROM memory_commit_events
                WHERE video_id = ?
                  AND modality = ?
                  AND attempted = 1
                  AND committed = 1
                  AND scene_id IS NOT NULL
                  AND scene_id != ''
                """,
                (video_id, modality),
            )
            return {row[0] for row in cur.fetchall() if row and row[0]}

        def _scene_ids_in(modality: str, scene_ids_list: List[str]) -> set[str]:
            if not scene_ids_list:
                return set()
            placeholders = ",".join("?" for _ in scene_ids_list)
            cur.execute(
                f"""
                SELECT DISTINCT scene_id
                FROM memory_commit_events
                WHERE modality = ?
                  AND attempted = 1
                  AND committed = 1
                  AND scene_id IN ({placeholders})
                """,
                (modality, *scene_ids_list),
            )
            return {row[0] for row in cur.fetchall() if row and row[0]}

        scene_ids_list = [str(sid) for sid in (scene_ids or []) if sid]

        audio_scene_ids = _scene_ids_by_video('audio')
        transcript_scene_ids = _scene_ids_by_video('audio_transcript')
        if scene_ids_list:
            audio_scene_ids |= _scene_ids_in('audio', scene_ids_list)
            transcript_scene_ids |= _scene_ids_in('audio_transcript', scene_ids_list)

        presence['audio_scene_ids'] = audio_scene_ids
        presence['transcript_scene_ids'] = transcript_scene_ids
        presence['has_audio'] = _has_any_by_video('audio') or bool(audio_scene_ids)
        presence['has_transcripts'] = _has_any_by_video('audio_transcript') or bool(transcript_scene_ids)
        presence['available'] = True
        return presence
    except Exception as e:
        logger.warning(f"[HARMONIZER] Failed to query memory_commit_events for presence: {e}")
        return presence
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception as e:
                logger.warning(
                    "[HARMONIZER] Failed to close commit presence DB connection: %s: %s",
                    type(e).__name__,
                    e,
                )


def align_audio_to_scenes(
    scenes: List[Dict[str, Any]],
    audio_segments: List[Dict[str, Any]]
) -> Dict[int, List[int]]:
    """
    Map audio chunks to video scenes based on temporal overlap.
    
    Args:
        scenes: List of scene dicts with 'start' and 'end' times
        audio_segments: List of audio segment dicts with 'start' and 'end'
        
    Returns:
        Dict mapping scene_id -> list of audio chunk IDs
    """
    scene_to_audio = {}
    
    for scene in scenes:
        scene_id = scene.get('id', scene.get('scene_id', 0))
        scene_start = scene.get('start', 0.0)
        scene_end = scene.get('end', 0.0)
        
        overlapping_chunks = []
        
        for chunk in audio_segments:
            chunk_id = chunk.get('id', chunk.get('chunk_id', 0))
            chunk_start = chunk.get('start', 0.0)
            chunk_end = chunk.get('end', 0.0)
            
            # Check for temporal overlap
            if chunk_start < scene_end and chunk_end > scene_start:
                overlapping_chunks.append(chunk_id)
        
        scene_to_audio[scene_id] = overlapping_chunks
    
    return scene_to_audio


def extract_keywords_from_transcript(transcript_segments: List[Dict[str, Any]], top_k: int = 10) -> List[str]:
    """
    Extract keywords from transcript segments (simplified version).
    
    Args:
        transcript_segments: List of transcript segment dicts
        top_k: Number of top keywords to extract
        
    Returns:
        List of keyword strings
    """
    # Simple keyword extraction: collect frequent words (excluding stopwords)
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'them', 'their', 'what', 'which', 'who', 'when', 'where', 'why', 'how'}
    
    word_counts = {}
    
    for segment in transcript_segments:
        text = segment.get('text', '')
        words = text.lower().split()
        
        for word in words:
            # Clean punctuation
            word = word.strip('.,!?;:()[]{}"\'-')
            
            if len(word) > 3 and word not in stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1
    
    # Sort by frequency and return top_k
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:top_k]]


def run_cross_modal_harmonization(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 6 harmonization: Fuse all modalities into unified temporal index.
    
    This step combines:
    - Video scenes (Phase 5)
    - Scene visual embeddings (Phase 6)
    - Audio segmentation (Phase 3)
    - Transcripts (audio pipeline)
    - Diarization (speaker IDs)
    - Object detection (from frames)
    - Metadata tags
    
    Into a single multimodal temporal index suitable for retrieval.
    
    Args:
        item: Enriched item dict
        cfg: Configuration dict
        
    Returns:
        Dict with harmonization status
    """
    # Get video info
    video_path = item.get('source_path')
    video_id = item.get('id', Path(video_path).stem if video_path else 'unknown')
    
    paths_cfg = (cfg.get('paths') or {}) if isinstance(cfg, dict) else {}
    processing_root = paths_cfg.get('processing')
    if not processing_root:
        global _PROCESSING_FALLBACK_WARNED
        data_root = paths_cfg.get('data_root')
        if not data_root:
            host_cfg = (cfg.get('host') or {}) if isinstance(cfg, dict) else {}
            data_root = host_cfg.get('data_root') or os.environ.get("GOODQ_DATA_ROOT")
        if data_root:
            base = Path(str(data_root))
            processing_root = str(base / "processing" if base.name == "GoodQ_Data" else base / "GoodQ_Data" / "processing")
            if not _PROCESSING_FALLBACK_WARNED:
                logger.warning(
                    "cross_modal_harmonizer path fallback used path_key=%s derived_from=%s",
                    "paths.processing",
                    "paths_or_host_data_root",
                )
                _PROCESSING_FALLBACK_WARNED = True
        else:
            processing_root = str(Path.cwd() / "processing")
            if not _PROCESSING_FALLBACK_WARNED:
                logger.warning(
                    "cross_modal_harmonizer path fallback used path_key=%s derived_from=%s",
                    "paths.processing",
                    "cwd",
                )
                _PROCESSING_FALLBACK_WARNED = True
    processing_dir = os.path.join(processing_root, str(video_id))
    
    logger.info(f"[HARMONIZER] Starting cross-modal fusion for {video_id}")
    
    # === LOAD ALL DATA SOURCES ===
    
    # Load scene manifest (Phase 5 + Phase 6)
    scene_manifest_path = item.get("scene_manifest_path")
    if scene_manifest_path and os.path.exists(scene_manifest_path):
        logger.debug(f"Using provided scene_manifest_path: {scene_manifest_path}")
    else:
        # Preferred canonical location
        scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
        
        # Fallback for older or mismatched pipelines
        if not os.path.exists(scene_manifest_path):
            alt_path = os.path.join(processing_dir, 'scene_manifest.json')
            if os.path.exists(alt_path):
                logger.warning(f"[HARMONIZER] Using fallback scene_manifest.json at: {alt_path}")
                scene_manifest_path = alt_path
    
    scene_data = load_json_safe(scene_manifest_path)
    
    if not scene_data:
        logger.warning(f"[HARMONIZER] No scene manifest found at {scene_manifest_path}, skipping harmonization")
        return {
            "harmonization_status": "skipped",
            "reason": "no_scene_manifest",
            "harmonized_scene_count": 0,
            "entity_extraction_available": ENTITY_EXTRACTION_AVAILABLE,
            "entities_extracted": 0,
        }
    
    scenes = scene_data.get('scenes', [])

    # Presence must be derived from committed truth (memory_commit_events), not filesystem heuristics.
    scene_ids_for_video = [str(s.get('id', s.get('scene_id', ''))) for s in scenes if s.get('id') or s.get('scene_id')]
    commit_presence = _load_commit_presence(cfg, str(video_id), scene_ids=scene_ids_for_video)
    audio_scene_ids = commit_presence.get('audio_scene_ids') if commit_presence.get('available') else set()
    transcript_scene_ids = commit_presence.get('transcript_scene_ids') if commit_presence.get('available') else set()
    has_audio_committed = bool(commit_presence.get('has_audio')) if commit_presence.get('available') else None
    has_transcripts_committed = bool(commit_presence.get('has_transcripts')) if commit_presence.get('available') else None
    audio_scene_truth_available = has_audio_committed is False or bool(audio_scene_ids)
    transcript_scene_truth_available = has_transcripts_committed is False or bool(transcript_scene_ids)
    
    # Load audio segmentation (Phase 3)
    segmentation_path = os.path.join(processing_dir, 'audio', 'segmentation.json')
    segmentation_data = load_json_safe(segmentation_path)
    audio_segments = segmentation_data.get('segments', []) if segmentation_data else []
    
    # Load transcript data
    transcript_path = os.path.join(processing_dir, 'audio', 'transcript.json')
    transcript_data = load_json_safe(transcript_path)
    transcript_segments = transcript_data.get('segments', []) if transcript_data else []
    
    # Load diarization data
    diarization_path = os.path.join(processing_dir, 'audio', 'diarization.json')
    diarization_data = load_json_safe(diarization_path)
    speakers = diarization_data.get('speakers', []) if diarization_data else []
    
    # Load object detection results (if available)
    objects_path = os.path.join(processing_dir, 'video', 'detected_objects.json')
    objects_data = load_json_safe(objects_path)
    
    logger.info(f"  Loaded: {len(scenes)} scenes, {len(audio_segments)} audio chunks, {len(transcript_segments)} transcript segments")
    
    # === BUILD TEMPORAL INDEX ===
    
    # Align audio chunks to scenes
    scene_audio_map = align_audio_to_scenes(scenes, audio_segments)
    
    # Build unified multimodal segments
    unified_segments = []
    total_entities_extracted = 0
    
    for scene in scenes:
        scene_id = scene.get('id', scene.get('scene_id', 0))
        scene_start = scene.get('start', 0.0)
        scene_end = scene.get('end', 0.0)
        
        # Get overlapping audio chunks
        audio_chunk_ids = scene_audio_map.get(scene_id, [])
        
        # Get overlapping transcripts
        scene_transcripts = [
            seg for seg in transcript_segments
            if seg.get('start', 0) < scene_end and seg.get('end', 0) > scene_start
        ]
        
        # Extract keywords from transcripts
        keywords = extract_keywords_from_transcript(scene_transcripts, top_k=5)
        
        # Extract entities from all text sources
        scene_entities = []
        if ENTITY_EXTRACTION_AVAILABLE:
            full_transcript = ' '.join(seg.get('text', '') for seg in scene_transcripts)
            caption_text = scene.get('caption', '')
            ocr_text = scene.get('ocr_text', '')
            tags = scene.get('tags', [])
            scene_entity_data = dict(scene)
            scene_entity_data.update({
                'transcription': full_transcript,
                'caption': caption_text,
                'ocr_text': ocr_text,
                'tags': tags,
                'start_time': scene_start,
            })
            entity_result = extract_entities_from_scene(
                scene_data=scene_entity_data,
                scene_id=str(scene_id),
                video_id=str(video_id),
                config=cfg,
            )
            if isinstance(entity_result, dict):
                scene_entities = entity_result.get('entities', []) or []
                total_entities_extracted += int(entity_result.get('entity_count', len(scene_entities)))
        
        # Get speaker IDs (from diarization)
        speaker_ids = []
        for speaker in speakers:
            if speaker.get('start', 0) < scene_end and speaker.get('end', 0) > scene_start:
                spk_id = speaker.get('speaker', 'UNKNOWN')
                if spk_id not in speaker_ids:
                    speaker_ids.append(spk_id)
        
        # Build unified segment
        scene_id_str = str(scene_id)
        has_audio_for_scene = None
        has_transcript_for_scene = None
        if audio_scene_truth_available and isinstance(audio_scene_ids, set):
            has_audio_for_scene = scene_id_str in audio_scene_ids
        if transcript_scene_truth_available and isinstance(transcript_scene_ids, set):
            has_transcript_for_scene = scene_id_str in transcript_scene_ids

        unified_segment = {
            'scene_id': scene_id,
            'start': scene_start,
            'end': scene_end,
            'duration': scene_end - scene_start,
            
            # Visual embeddings
            'clip_id': scene.get('clip_id'),
            'dino_id': scene.get('dino_id'),
            'representative_frame': scene.get('representative_frame'),
            'frame_count': scene.get('frame_count', 0),
            
            # Audio alignment
            'audio_chunks': audio_chunk_ids,
            'speaker_ids': speaker_ids,
            
            # Semantic content
            'keywords': keywords,
            'entities': scene_entities,  # NEW: Extracted entities
            'transcript_segments': [seg.get('text', '') for seg in scene_transcripts],
            'full_transcript': ' '.join(seg.get('text', '') for seg in scene_transcripts),
            
            # Metadata
            'scene_confidence': scene.get('confidence', 0.0),
            'has_visual_embeddings': bool(scene.get('clip_id') and scene.get('dino_id')),
            'has_audio': has_audio_for_scene if has_audio_for_scene is not None else len(audio_chunk_ids) > 0,
            'has_transcript': has_transcript_for_scene if has_transcript_for_scene is not None else len(scene_transcripts) > 0,
            'has_speakers': len(speaker_ids) > 0
        }
        
        # Add detected objects if available
        if objects_data:
            scene_objects = objects_data.get(str(scene_id), {}).get('objects', [])
            unified_segment['detected_objects'] = scene_objects
        
        unified_segments.append(unified_segment)
    
    # === CREATE TEMPORAL INDEX ===
    
    # Aggregate all entities across segments
    all_entities = []
    entity_counts = {}
    for seg in unified_segments:
        for entity in seg.get('entities', []):
            all_entities.append(entity)
            entity_text = entity.get('text', '').lower()
            entity_type = entity.get('type', 'UNKNOWN')
            key = f"{entity_text}:{entity_type}"
            entity_counts[key] = entity_counts.get(key, 0) + 1
    
    # Get top entities
    top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    
    temporal_index = {
        'version': 1,
        'video_id': video_id,
        'video_path': video_path,
        'total_scenes': len(scenes),
        'total_duration': max(s.get('end', 0) for s in scenes) if scenes else 0,
        
        # Multimodal segments
        'segments': unified_segments,
        
        # Extracted entities
        'total_entities': len(all_entities),
        'unique_entities': len(entity_counts),
        'top_entities': [
            {'entity': k.split(':')[0], 'type': k.split(':')[1], 'count': v}
            for k, v in top_entities
        ],
        
        # Global metadata
        'has_visual_embeddings': any(s.get('has_visual_embeddings') for s in unified_segments),
        'has_audio': has_audio_committed if has_audio_committed is not None else any(s.get('has_audio') for s in unified_segments),
        'has_transcripts': has_transcripts_committed if has_transcripts_committed is not None else any(s.get('has_transcript') for s in unified_segments),
        
        # Processing metadata
        'phase5_complete': scene_data.get('phase5_complete', False),
        'phase6_complete': scene_data.get('phase6_complete', False),
        'phase6_harmonized': True
    }
    
    # === SAVE TEMPORAL INDEX ===
    
    temporal_index_path = os.path.join(processing_dir, 'temporal_index.json')
    os.makedirs(os.path.dirname(temporal_index_path), exist_ok=True)
    atomic_write_json(Path(temporal_index_path), temporal_index)
    
    logger.info(f"[HARMONIZER] [OK] Created temporal index with {len(unified_segments)} multimodal segments")
    logger.info(f"  Saved: {temporal_index_path}")
    
    return {
        'harmonization_status': 'complete',
        'temporal_index_path': temporal_index_path,
        'unified_segments': len(unified_segments),
        'harmonized_scene_count': len(unified_segments),
        'has_visual': temporal_index['has_visual_embeddings'],
        'has_audio': temporal_index['has_audio'],
        'has_transcripts': temporal_index['has_transcripts'],
        'entity_extraction_available': ENTITY_EXTRACTION_AVAILABLE,
        'entities_extracted': total_entities_extracted,
    }
