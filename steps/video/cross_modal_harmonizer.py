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
from pathlib import Path

logger = logging.getLogger(__name__)


def load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON file with error handling."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
    return None


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
    
    data_root = cfg.get('data_root', 'L:/_DATA/GoodQ_Data')
    processing_dir = os.path.join(data_root, 'processing', video_id)
    
    logger.info(f"[HARMONIZER] Starting cross-modal fusion for {video_id}")
    
    # === LOAD ALL DATA SOURCES ===
    
    # Load scene manifest (Phase 5 + Phase 6)
    scene_manifest_path = os.path.join(processing_dir, 'video', 'scene_manifest.json')
    scene_data = load_json_safe(scene_manifest_path)
    
    if not scene_data:
        logger.warning("No scene manifest found, skipping harmonization")
        return {"harmonization_status": "skipped", "reason": "no_scene_manifest"}
    
    scenes = scene_data.get('scenes', [])
    
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
        
        # Get speaker IDs (from diarization)
        speaker_ids = []
        for speaker in speakers:
            if speaker.get('start', 0) < scene_end and speaker.get('end', 0) > scene_start:
                spk_id = speaker.get('speaker', 'UNKNOWN')
                if spk_id not in speaker_ids:
                    speaker_ids.append(spk_id)
        
        # Build unified segment
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
            'transcript_segments': [seg.get('text', '') for seg in scene_transcripts],
            'full_transcript': ' '.join(seg.get('text', '') for seg in scene_transcripts),
            
            # Metadata
            'scene_confidence': scene.get('confidence', 0.0),
            'has_visual_embeddings': bool(scene.get('clip_id') and scene.get('dino_id')),
            'has_audio': len(audio_chunk_ids) > 0,
            'has_transcript': len(scene_transcripts) > 0,
            'has_speakers': len(speaker_ids) > 0
        }
        
        # Add detected objects if available
        if objects_data:
            scene_objects = objects_data.get(str(scene_id), {}).get('objects', [])
            unified_segment['detected_objects'] = scene_objects
        
        unified_segments.append(unified_segment)
    
    # === CREATE TEMPORAL INDEX ===
    
    temporal_index = {
        'version': 1,
        'video_id': video_id,
        'video_path': video_path,
        'total_scenes': len(scenes),
        'total_duration': max(s.get('end', 0) for s in scenes) if scenes else 0,
        
        # Multimodal segments
        'segments': unified_segments,
        
        # Global metadata
        'has_visual_embeddings': any(s.get('has_visual_embeddings') for s in unified_segments),
        'has_audio': any(s.get('has_audio') for s in unified_segments),
        'has_transcripts': any(s.get('has_transcript') for s in unified_segments),
        
        # Processing metadata
        'phase5_complete': scene_data.get('phase5_complete', False),
        'phase6_complete': scene_data.get('phase6_complete', False),
        'phase6_harmonized': True
    }
    
    # === SAVE TEMPORAL INDEX ===
    
    temporal_index_path = os.path.join(processing_dir, 'temporal_index.json')
    os.makedirs(os.path.dirname(temporal_index_path), exist_ok=True)
    
    with open(temporal_index_path, 'w', encoding='utf-8') as f:
        json.dump(temporal_index, f, indent=2)
    
    logger.info(f"[HARMONIZER] [OK] Created temporal index with {len(unified_segments)} multimodal segments")
    logger.info(f"  Saved: {temporal_index_path}")
    
    return {
        'harmonization_status': 'complete',
        'temporal_index_path': temporal_index_path,
        'unified_segments': len(unified_segments),
        'has_visual': temporal_index['has_visual_embeddings'],
        'has_audio': temporal_index['has_audio'],
        'has_transcripts': temporal_index['has_transcripts']
    }
