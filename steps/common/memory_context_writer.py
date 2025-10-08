#!/usr/bin/env python3
"""
Memory Context Writer - Ensures all step results are saved to memory database
This integrates with the existing memory.py to ensure enriched context is captured.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import logging

from steps.steps.common.memory import (
    register_scene_bundle,
    upsert_scene,
    update_fields,
    compute_file_hash
)

logger = logging.getLogger(__name__)


def save_step_context(
    cfg: Dict[str, Any],
    video_hash: str,
    scene: Dict[str, Any],
    scene_id: str,
    step_name: str,
    step_results: Dict[str, Any]
) -> None:
    """
    Save step results to memory database with full context.
    
    This ensures that every step's output is captured in the memory DB
    so that we have rich, queryable context for every scene.
    
    Args:
        cfg: Configuration dictionary
        video_hash: Hash of the video file
        scene: Scene metadata
        scene_id: Unique scene identifier
        step_name: Name of the step that produced results
        step_results: Results from the step
    """
    if not step_results or not isinstance(step_results, dict):
        return
    
    # Get existing scene metadata to merge
    scene_start = float(scene.get('start', 0.0) or 0.0)
    scene_end = float(scene.get('end', scene_start) or scene_start)
    
    # Build enriched metadata
    enriched_meta: Dict[str, Any] = {}
    
    # Map step results to context fields
    if step_name == 'image_caption':
        caption = step_results.get('caption')
        if caption:
            enriched_meta['caption'] = caption
            caption_meta = step_results.get('caption_meta')
            if caption_meta:
                enriched_meta['caption_meta'] = caption_meta
    
    elif step_name == 'object_detect':
        objects = step_results.get('objects')
        if objects:
            enriched_meta['objects'] = objects
            enriched_meta['object_count'] = len(objects)
        detect_meta = step_results.get('detect_meta')
        if detect_meta:
            enriched_meta['detect_meta'] = detect_meta
    
    elif step_name == 'image_ocr':
        ocr_text = step_results.get('ocr_text')
        if ocr_text:
            enriched_meta['ocr_text'] = ocr_text
        ocr_meta = step_results.get('ocr_meta')
        if ocr_meta:
            enriched_meta['ocr_meta'] = ocr_meta
    
    elif step_name == 'audio_transcribe':
        transcript = step_results.get('transcript')
        if transcript:
            enriched_meta['transcript'] = transcript
        transcript_meta = step_results.get('transcript_meta')
        if transcript_meta:
            enriched_meta['transcript_meta'] = transcript_meta
            # Extract segments for deeper analysis
            segments = transcript_meta.get('segments')
            if segments:
                enriched_meta['transcript_segments'] = segments
    
    elif step_name == 'sentiment':
        sentiment = step_results.get('sentiment')
        if sentiment:
            enriched_meta['sentiment'] = sentiment
            # Also store in embeddings table for filtering
            if isinstance(sentiment, dict):
                sentiment_label = sentiment.get('label')
                sentiment_score = sentiment.get('score')
                if sentiment_label:
                    enriched_meta['sentiment_label'] = sentiment_label
                if sentiment_score is not None:
                    enriched_meta['sentiment_score'] = float(sentiment_score)
    
    elif step_name == 'emotion_classify':
        emotions = step_results.get('emotions')
        if emotions:
            enriched_meta['emotions'] = emotions
            # Find dominant emotion
            if isinstance(emotions, list) and emotions:
                enriched_meta['dominant_emotion'] = emotions[0]
            elif isinstance(emotions, dict):
                # If it's a dict, find highest score
                sorted_emotions = sorted(emotions.items(), key=lambda x: x[1], reverse=True)
                if sorted_emotions:
                    enriched_meta['dominant_emotion'] = sorted_emotions[0][0]
    
    elif step_name == 'tagger':
        tags = step_results.get('tags')
        if tags:
            enriched_meta['tags'] = tags
        entities = step_results.get('entities')
        if entities:
            enriched_meta['entities'] = entities
    
    elif step_name == 'audio_emotion':
        audio_emotion = step_results.get('audio_emotion')
        if audio_emotion:
            enriched_meta['audio_emotion'] = audio_emotion
    
    elif step_name == 'audio_diarize':
        diarization = step_results.get('diarization')
        if diarization:
            enriched_meta['diarization'] = diarization
            # Extract speaker list
            speakers = set()
            for seg in diarization:
                if isinstance(seg, dict) and seg.get('speaker'):
                    speakers.add(seg['speaker'])
            if speakers:
                enriched_meta['speakers'] = sorted(list(speakers))
    
    elif step_name in ['image_embed_dino', 'image_embed_clip']:
        # Embedding steps - just note they were computed
        embedding = step_results.get('embedding')
        if embedding:
            enriched_meta[f'{step_name}_computed'] = True
    
    elif step_name == 'face_embed':
        faces = step_results.get('faces')
        if faces:
            enriched_meta['faces'] = faces
            enriched_meta['face_count'] = len(faces)
    
    else:
        # Generic storage for other steps
        for key, value in step_results.items():
            if value is not None and key not in ['status', 'error']:
                enriched_meta[key] = value
    
    # Update scene metadata in database
    if enriched_meta:
        try:
            # Use upsert_scene to merge metadata
            upsert_scene(cfg, video_hash, scene_start, scene_end, enriched_meta)
            logger.debug(f"Saved context for {step_name} on scene {scene_id}")
        except Exception as e:
            logger.error(f"Failed to save context for {step_name}: {e}")


def save_enriched_scene_bundle(
    cfg: Dict[str, Any],
    video_hash: str,
    scene: Dict[str, Any],
    scene_id: str,
    all_step_results: Dict[str, Any]
) -> None:
    """
    Save complete enriched scene bundle with all analysis results.
    
    This is called after all steps have been run on a scene to save
    the complete context in one go.
    
    Args:
        cfg: Configuration dictionary
        video_hash: Hash of the video file
        scene: Scene metadata with timing info
        scene_id: Unique scene identifier
        all_step_results: Dictionary mapping step names to their results
    """
    # Build frame and audio dictionaries
    frame = all_step_results.get('frame', {})
    audio = all_step_results.get('audio', {})
    
    # Aggregate all analysis results into frame/audio data
    frame_data = {}
    audio_data = {}
    errors = {}
    
    # Process image analysis results
    for step in ['image_caption', 'object_detect', 'image_ocr', 'face_embed',
                 'image_embed_dino', 'image_embed_clip', 'image_exif']:
        results = all_step_results.get(step, {})
        if isinstance(results, dict):
            if results.get('error'):
                errors[step] = results['error']
            frame_data.update(results)
    
    # Process audio analysis results
    for step in ['audio_transcribe', 'audio_diarize', 'audio_emotion', 
                 'audio_metadata', 'audio_time_hints', 'audio_music_events',
                 'audio_embed_clap']:
        results = all_step_results.get(step, {})
        if isinstance(results, dict):
            if results.get('error'):
                errors[step] = results['error']
            audio_data.update(results)
    
    # Process universal analysis results (sentiment, emotions, tags)
    for step in ['sentiment', 'emotion_classify', 'tagger', 'text_embed']:
        results = all_step_results.get(step, {})
        if isinstance(results, dict):
            if results.get('error'):
                errors[step] = results['error']
            # These can apply to both visual and audio
            # We'll add them to both contexts
            frame_data.update(results)
            audio_data.update(results)
    
    # Build frame bundle
    frame_path = frame.get('path') or frame.get('source_path')
    frame_bundle = None
    if frame_path:
        frame_bundle = {
            'path': frame_path,
            'data': frame_data,
            'timestamp': scene.get('start', 0.0)
        }
    
    # Build audio bundle
    audio_path = audio.get('path') or audio.get('source_path')
    audio_bundle = None
    if audio_path:
        audio_bundle = {
            'path': audio_path,
            'data': audio_data,
            'start': scene.get('start', 0.0),
            'end': scene.get('end', 0.0)
        }
    
    # Get scene detection metadata
    detection_meta = scene.get('detection_meta') or scene.get('scene_meta')
    
    try:
        # Register the complete scene bundle
        register_scene_bundle(
            cfg,
            video_hash=video_hash,
            scene=scene,
            scene_id=scene_id,
            detection_meta=detection_meta,
            frame=frame_bundle,
            audio=audio_bundle,
            errors=errors if errors else None
        )
        logger.info(f"Registered complete scene bundle for {scene_id}")
    except Exception as e:
        logger.error(f"Failed to register scene bundle for {scene_id}: {e}")


def ensure_frame_hash_in_embeddings(
    cfg: Dict[str, Any],
    frame_path: str,
    scene_id: str,
    step_results: Dict[str, Any]
) -> Optional[str]:
    """
    Ensure frame hash is registered in embeddings table with sentiment/emotion context.
    
    Returns the frame hash.
    """
    frame_hash = compute_file_hash(frame_path)
    if not frame_hash:
        return None
    
    # Extract sentiment and emotion for embedding metadata
    emotions_json = None
    sentiment_label = None
    sentiment_score = None
    
    sentiment = step_results.get('sentiment')
    if isinstance(sentiment, dict):
        sentiment_label = sentiment.get('label')
        sentiment_score = sentiment.get('score')
    
    emotions = step_results.get('emotions')
    if emotions:
        import json
        try:
            emotions_json = json.dumps(emotions, ensure_ascii=False)
        except Exception:
            pass
    
    # Update embedding record with context
    try:
        update_fields(
            cfg,
            frame_hash,
            emotions_json=emotions_json,
            sentiment_label=sentiment_label,
            sentiment_score=sentiment_score
        )
        logger.debug(f"Updated embedding context for frame {frame_hash}")
    except Exception as e:
        logger.error(f"Failed to update embedding context: {e}")
    
    return frame_hash
