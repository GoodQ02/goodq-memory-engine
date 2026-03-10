from __future__ import annotations
from typing import Any, Dict, List, Optional, Set
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Setup logger
logger = logging.getLogger(__name__)

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import re
import typer

from steps.common.config_loader import get_runtime_paths, load_configs
from steps.common.atomic_io import atomic_write_json
from steps.common.memory import ensure_scene, register_scene_bundle, scene_has_materialized, get_scene_meta, list_scenes_for_video
from steps.common.tag_utils import canonicalize_taxonomy
from steps.common.tool_paths import resolve_ffmpeg, resolve_conda
from steps.common.step_logger import log_step_run
from steps.common.profile_config import is_baseline, require_wsl_audio, wsl_audio_auto_enabled
from lib.observability.observer import PipelineObserver

_OPTIONAL_DIRECT_ENV_FALLBACK_STEPS = {"sentiment", "audio_embed_clap"}


def _patch_typer_help_for_click_8_2() -> None:
    """
    Typer 0.9.0 + Click 8.2.x: rich help calls `param.make_metavar()` without ctx.
    Click 8.2 requires `make_metavar(self, ctx)`, causing `--help` to crash on Py3.13.
    Patch is safe and affects help rendering only.
    """
    try:
        import inspect
        import click
    except Exception as e:
        logger.debug(
            "run_ingestion warning context=%s error=%s",
            "typer_help_patch.import",
            e,
        )
        return

    make_metavar = getattr(click.core.Parameter, "make_metavar", None)
    if make_metavar is None or getattr(make_metavar, "_goodq_patched", False):
        return
    try:
        sig = inspect.signature(make_metavar)
    except Exception as e:
        logger.debug(
            "run_ingestion warning context=%s error=%s",
            "typer_help_patch.signature",
            e,
        )
        return
    if "ctx" not in sig.parameters:
        return

    orig = make_metavar

    def _make_metavar_compat(self, ctx=None):  # type: ignore[no-untyped-def]
        if ctx is None:
            ctx = click.get_current_context(silent=True)
            if ctx is None:
                ctx = click.Context(click.Command("goodq"))
        return orig(self, ctx)

    _make_metavar_compat._goodq_patched = True  # type: ignore[attr-defined]
    click.core.Parameter.make_metavar = _make_metavar_compat  # type: ignore[assignment]


# Progress tracking
try:
    from steps.common.progress_tracker import get_tracker, step_context, update_step
    PROGRESS_TRACKING_AVAILABLE = True
except ImportError:
    PROGRESS_TRACKING_AVAILABLE = False
    # Fallback stubs
    class DummyTracker:
        def step_context(self, *args, **kwargs):
            from contextlib import contextmanager
            @contextmanager
            def dummy():
                yield self
            return dummy()
    def get_tracker():
        return DummyTracker()
    def update_step(*args, **kwargs):
        pass
    step_context = lambda *args, **kwargs: DummyTracker().step_context(*args, **kwargs)

# Control Agent integration
try:
    from agents.control_agent import (
        ControlAgent,
        CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT,
        CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT,
    )
    CONTROL_AGENT_AVAILABLE = True
except ImportError:
    CONTROL_AGENT_AVAILABLE = False
    ControlAgent = None
    CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT = "disabled_no_llm_client"
    CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT = "Control Agent module unavailable"
    logger.warning(
        "run_ingestion warning context=%s error=%s",
        "control_agent.import",
        "ImportError",
    )

# Knowledge graph integration
try:
    from lib.knowledge_graph import KnowledgeGraph
    from lib.kg_realtime_integration import update_kg_for_scene, build_scene_relationships
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    logger.warning(
        "run_ingestion warning context=%s error=%s",
        "knowledge_graph.import",
        "ImportError",
    )

APP = typer.Typer(help='Scene-first ingestion orchestrator for GoodQ')

def _load_runtime_cfg_snapshot(cfg_json: Optional[Path] = None) -> Dict[str, Any]:
    if cfg_json and cfg_json.exists():
        try:
            raw = cfg_json.read_text(encoding='utf-8').strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except Exception as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "runtime_cfg_snapshot",
                e,
            )
    return load_configs({})


def _resolve_models_dir(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    cfg_json: Optional[Path] = None,
) -> Path:
    cfg_payload = cfg if isinstance(cfg, dict) else _load_runtime_cfg_snapshot(cfg_json)
    runtime_paths = get_runtime_paths(cfg_payload, "models_cache")
    return Path(runtime_paths["models_cache"]).resolve()


def _resolve_processing_root(cfg: Dict[str, Any]) -> Path:
    runtime_paths = get_runtime_paths(cfg)
    return Path(runtime_paths["processing"]).resolve()

# Populated by CLI options at runtime
VERBOSE: bool = False
# Timeout per step in seconds - prevents infinite hangs
# Audio steps (diarize, transcribe) can take 5-10 min for long scenes
# Image steps should complete in <30s
STEP_TIMEOUT: Optional[int] = 1800  # 30 minutes max per step
MAX_HEALER_RETRIES: int = 3
_CURRENT_RUN_CONTEXT: Optional[Dict[str, Any]] = None
_PIPELINE_OBSERVER: Optional[PipelineObserver] = None


def _control_agent_runtime_enabled() -> bool:
    if not CONTROL_AGENT_AVAILABLE:
        return False
    if not isinstance(_CURRENT_RUN_CONTEXT, dict):
        return False
    status = _CURRENT_RUN_CONTEXT.get('control_agent_status')
    if status is None:
        # Backward-compatible default for direct _run_step() calls in tests/harnesses.
        return True
    return status == 'initialized'


def _observer() -> Optional[PipelineObserver]:
    global _PIPELINE_OBSERVER
    if _PIPELINE_OBSERVER is None or not _PIPELINE_OBSERVER.enabled:
        return None
    return _PIPELINE_OBSERVER


def run_ingestion(video_path: str, cfg: Optional[Dict] = None):
    """
    Main ingestion entrypoint - runs direct_ingestion pipeline
    
    Args:
        video_path: Path to video file to ingest
        cfg: Optional config dict (will load from config.yaml if not provided)
    
    Returns:
        Dict containing ingestion results
    """
    from pipelines.direct_ingestion import run_direct_ingestion
    
    if cfg is None:
        cfg = load_configs({})
    
    return run_direct_ingestion(video_path, cfg)

IMAGE_PIPELINE_STEPS = [
    'image_ocr',
    'image_caption',
    'object_detect',
    'face_embed',
    'image_embed_dino',
    'image_embed_clip',
    'tagger',
]

AUDIO_PIPELINE_STEPS = [
    'audio_metadata',
    # Legacy audio steps replaced by WSL2 GPU-accelerated versions
    # 'audio_diarize',  # Now using audio_wsl2_bridge
    # 'audio_transcribe',  # Now using audio_wsl2_bridge
    'audio_speaker_merge',
    'audio_music_events',
    'audio_time_hints',
    'audio_emotion',
    'sentiment',
    'emotion_classify',
    'tagger',
    'audio_embed_clap',
]

# Native-heavy NLP subprocesses can sporadically crash under unrestricted thread fan-out.
# Apply conservative thread caps only for these subprocess steps.
SUBPROCESS_THREAD_CAP_STEPS: Set[str] = {
    'tagger',
    'sentiment',
    'emotion_classify',
}
SUBPROCESS_THREAD_CAP_ENV: Dict[str, str] = {
    'OMP_NUM_THREADS': '1',
    'MKL_NUM_THREADS': '1',
    'NUMEXPR_MAX_THREADS': '1',
    'TOKENIZERS_PARALLELISM': 'false',
}
SUBPROCESS_AUDIO_OPENMP_GUARD_STEPS: Set[str] = {'audio_embed_clap'}
SUBPROCESS_AUDIO_OPENMP_GUARD_ENV: Dict[str, str] = {
    'KMP_DUPLICATE_LIB_OK': 'TRUE',
    'OMP_NUM_THREADS': '1',
    'MKL_NUM_THREADS': '1',
}
NATIVE_CRASH_RETRY_STEPS: Set[str] = {'tagger'}
MAX_NATIVE_STEP_RETRIES: int = 1



def _build_knowledge_graph_from_results(results: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build knowledge graph from ingestion results"""
    if not KNOWLEDGE_GRAPH_AVAILABLE:
        if VERBOSE:
            typer.echo('[kg] Knowledge graph module not available, skipping')
        return None
    
    try:
        runtime_paths = get_runtime_paths(cfg)
        graph_db_path = Path(runtime_paths['knowledge_graph_db']).resolve()
        graph_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        if VERBOSE:
            typer.echo(f'[kg] Building knowledge graph at {graph_db_path}')
        
        with KnowledgeGraph(str(graph_db_path)) as kg:
            for video_result in results:
                video_path = video_result.get('video_path', '')
                scenes = video_result.get('scenes', [])
                
                for scene in scenes:
                    scene_idx = scene.get('index', 0)
                    scene_id = scene.get('scene_id', f'scene_{scene_idx:04d}')
                    start_time = scene.get('start', 0.0)
                    end_time = scene.get('end', start_time)
                    
                    # Add media node for this scene
                    media_props = {
                        'duration': end_time - start_time,
                        'confidence': scene.get('confidence', 0.0),
                        'video_path': video_path
                    }
                    media_id = kg.add_media_node(
                        media_type='video_scene',
                        media_path=video_path,
                        scene_id=scene_id,
                        timestamp_start=start_time,
                        timestamp_end=end_time,
                        properties=media_props
                    )
                    
                    # Process keyframe data
                    keyframe = scene.get('keyframe')
                    if isinstance(keyframe, dict):
                        _process_keyframe_entities(kg, keyframe, media_id, start_time)
                    
                    # Process audio data
                    audio = scene.get('audio')
                    if isinstance(audio, dict):
                        _process_audio_entities(kg, audio, media_id, start_time)
                    
                    # Create temporal event for scene
                    kg.add_temporal_event(
                        event_type='scene_change',
                        timestamp=start_time,
                        duration=end_time - start_time,
                        properties={'scene_id': scene_id, 'confidence': scene.get('confidence', 0.0)}
                    )
            
            # Build relationships
            _build_kg_relationships(kg)
            
            # Get statistics
            stats = kg.get_statistics()
            
            if VERBOSE:
                typer.echo(f'[kg] Knowledge graph complete: {stats}')
            
            return {
                'graph_db_path': str(graph_db_path),
                'statistics': stats,
                'status': 'success'
            }
    
    except Exception as exc:
        logger.warning(
            "run_ingestion warning context=%s error=%s",
            "knowledge_graph.build",
            exc,
        )
        if VERBOSE:
            typer.echo(f'[kg] Knowledge graph build failed: {exc}', err=True)
        return {'status': 'failed', 'error': str(exc)}


def _process_keyframe_entities(kg: Any, keyframe: Dict[str, Any], media_id: int, timestamp: float) -> None:
    """Extract and add entities from keyframe data"""
    # Objects detected
    detections = keyframe.get('detections', [])
    if isinstance(detections, list):
        for det in detections:
            if isinstance(det, dict):
                label = det.get('label', det.get('class'))
                confidence = det.get('confidence', det.get('score', 0.0))
                if label and confidence > 0.3:
                    bbox = det.get('bbox', [])
                    entity_id = kg.add_node('object', label, {'confidence': confidence}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, confidence, {'bbox': bbox})
    
    # Faces detected
    faces = keyframe.get('faces', [])
    if isinstance(faces, list):
        for idx, face in enumerate(faces):
            if isinstance(face, dict):
                confidence = face.get('confidence', face.get('score', 1.0))
                bbox = face.get('bbox', [])
                face_id = face.get('identity', f'unknown_{idx}')
                entity_id = kg.add_node('person', f'face_{face_id}', {'face_detected': True}, timestamp)
                kg.link_node_to_media(entity_id, media_id, confidence, {'bbox': bbox, 'face_index': idx})
    
    # Caption/Description
    caption = keyframe.get('caption')
    if caption and isinstance(caption, str):
        entity_id = kg.add_node('description', 'scene_caption', {'text': caption}, timestamp)
        kg.link_node_to_media(entity_id, media_id, 0.9)
    
    # Tags
    tags = keyframe.get('tags', [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str):
                entity_id = kg.add_node('concept', tag, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.5)
    
    # Entities (named entities)
    entities = keyframe.get('entities', [])
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, str):
                entity_id = kg.add_node('entity', entity, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.7)
    
    # Emotions
    emotions = keyframe.get('emotions', [])
    if isinstance(emotions, list):
        for emotion in emotions:
            if isinstance(emotion, str):
                entity_id = kg.add_node('emotion', emotion, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.5)
    
    # OCR text locations
    ocr_text = keyframe.get('ocr_text')
    if ocr_text:
        entity_id = kg.add_node('concept', 'text_overlay', {'text': ocr_text[:100]}, timestamp)
        kg.link_node_to_media(entity_id, media_id, 0.8)


def _process_audio_entities(kg: Any, audio: Dict[str, Any], media_id: int, timestamp: float) -> None:
    """Extract and add entities from audio data"""
    # Transcript
    transcript = audio.get('transcript')
    if transcript:
        entity_id = kg.add_node('concept', 'speech', {'transcript': transcript[:200]}, timestamp)
        kg.link_node_to_media(entity_id, media_id, 0.9)
    
    # Sentiment
    sentiment = audio.get('sentiment')
    if isinstance(sentiment, dict):
        label = sentiment.get('label')
        score = sentiment.get('score', 0.5)
        if label:
            entity_id = kg.add_node('sentiment', label.lower(), {'score': score}, timestamp)
            kg.link_node_to_media(entity_id, media_id, score)
    
    # Emotions from audio (can be dict with scores or list)
    emotions = audio.get('emotions')
    if emotions:
        if isinstance(emotions, dict):
            for emotion_name, emotion_score in emotions.items():
                if emotion_score > 0.3:
                    entity_id = kg.add_node('emotion', emotion_name, {'score': emotion_score}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, emotion_score)
        elif isinstance(emotions, list):
            for emotion in emotions:
                if isinstance(emotion, str):
                    entity_id = kg.add_node('emotion', emotion, {}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.6)
    
    # Audio emotion (fallback/alternative field)
    audio_emotion = audio.get('audio_emotion')
    if audio_emotion:
        if isinstance(audio_emotion, str):
            entity_id = kg.add_node('emotion', audio_emotion, {}, timestamp)
            kg.link_node_to_media(entity_id, media_id, 0.6)
        elif isinstance(audio_emotion, dict):
            top_emotion = audio_emotion.get('top_emotion')
            if top_emotion:
                entity_id = kg.add_node('emotion', top_emotion, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.6)
    
    # Speaker transcripts (detailed speaker segments)
    speaker_transcript = audio.get('speaker_transcript', [])
    if isinstance(speaker_transcript, list):
        for segment in speaker_transcript:
            if isinstance(segment, dict):
                speaker_id = segment.get('speaker')
                text = segment.get('text', '')
                if speaker_id:
                    entity_id = kg.add_node('person', f'speaker_{speaker_id}', {'transcript_sample': text[:100]}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.8, {
                        'start': segment.get('start'),
                        'end': segment.get('end'),
                        'text': text
                    })
    
    # Fallback: Speaker diarization (if speaker_transcript not available)
    if not speaker_transcript:
        speakers = audio.get('speakers', [])
        if isinstance(speakers, list):
            for speaker in speakers:
                if isinstance(speaker, str):
                    entity_id = kg.add_node('person', f'speaker_{speaker}', {}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.7)
                elif isinstance(speaker, dict):
                    speaker_id = speaker.get('speaker', speaker.get('label'))
                    if speaker_id:
                        entity_id = kg.add_node('person', f'speaker_{speaker_id}', {}, timestamp)
                        kg.link_node_to_media(entity_id, media_id, 0.7)
    
    # Entities (named entities from transcript)
    entities = audio.get('entities', [])
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, str):
                entity_id = kg.add_node('entity', entity, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.7)
    
    # Music events
    music_events = audio.get('music_events', [])
    if isinstance(music_events, list):
        for event in music_events:
            if isinstance(event, dict):
                event_type = event.get('type', 'music')
                confidence = event.get('confidence', 0.5)
                entity_id = kg.add_node('audio_event', f'music_{event_type}', {'confidence': confidence}, timestamp)
                kg.link_node_to_media(entity_id, media_id, confidence, {
                    'start': event.get('start'),
                    'end': event.get('end')
                })
    
    # Time hints (temporal context)
    time_hints = audio.get('time_hints', {})
    if isinstance(time_hints, dict):
        for hint_type, hints in time_hints.items():
            if isinstance(hints, list) and hints:
                for hint in hints:
                    entity_id = kg.add_node('temporal_context', f'{hint_type}_{hint}', {}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.6)
    
    # Tags from audio
    tags = audio.get('tags', [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str):
                entity_id = kg.add_node('concept', tag, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.5)


def _build_kg_relationships(kg: Any) -> None:
    """Build co-occurrence, temporal, and semantic relationships"""
    # Co-occurrence: entities appearing together in same media
    cursor = kg.conn.cursor()
    cursor.execute("""
        SELECT e1.id, e2.id, COUNT(*) as co_count
        FROM node_media nm1
        JOIN node_media nm2 ON nm1.media_id = nm2.media_id
        JOIN nodes e1 ON nm1.node_id = e1.id
        JOIN nodes e2 ON nm2.node_id = e2.id
        WHERE e1.id < e2.id
        GROUP BY e1.id, e2.id
        HAVING co_count >= 2
    """)
    
    for row in cursor.fetchall():
        kg.add_edge(
            row[0], row[1], 'co_occurs',
            weight=float(row[2]),
            properties={'count': row[2]}
        )
    
    # Temporal: entities in adjacent time windows (within 10 seconds)
    cursor.execute("""
        SELECT DISTINCT n1.id, n2.id
        FROM media_nodes m1
        JOIN media_nodes m2 ON ABS(m1.timestamp_start - m2.timestamp_start) <= 10
        JOIN node_media nm1 ON m1.id = nm1.media_id
        JOIN node_media nm2 ON m2.id = nm2.media_id
        JOIN nodes n1 ON nm1.node_id = n1.id
        JOIN nodes n2 ON nm2.node_id = n2.id
        WHERE n1.id < n2.id
        AND m1.id != m2.id
    """)
    
    for row in cursor.fetchall():
        kg.add_edge(
            row[0], row[1], 'temporal_proximity',
            weight=0.5
        )



OUTPUT_DROP_KEYS: Set[str] = {'modality', 'scene_id', 'scene_index', 'video_hash', 'video_id'}


def _merge_step_output(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    merged: Dict[str, Any] = {k: v for k, v in result.items() if k != 'data'}
    data = result.get('data')
    if isinstance(data, dict):
        raw = dict(data)
        for key, value in raw.items():
            if key in OUTPUT_DROP_KEYS:
                continue
            if key == 'source_path' and 'path' in merged:
                continue
            merged.setdefault(key, value)
        merged['raw'] = raw
    return merged


def _extract_speaker_ids(audio_payload: Any) -> List[str]:
    if not isinstance(audio_payload, dict):
        return []

    speaker_ids: List[str] = []

    def _append_speaker(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        speaker = raw.strip()
        if speaker and speaker not in speaker_ids:
            speaker_ids.append(speaker)

    speakers = audio_payload.get('speakers')
    if isinstance(speakers, list):
        for speaker in speakers:
            if isinstance(speaker, str):
                _append_speaker(speaker)
            elif isinstance(speaker, dict):
                _append_speaker(speaker.get('speaker', speaker.get('label')))

    for key in ('speaker_transcript', 'speaker_segments', 'diarization'):
        segments = audio_payload.get(key)
        if not isinstance(segments, list):
            continue
        for segment in segments:
            if isinstance(segment, dict):
                _append_speaker(segment.get('speaker'))

    return speaker_ids


def _infer_audio_backend_fields(
    audio_info: Optional[Dict[str, Any]],
    *,
    skip_audio: bool,
    audio_error: Optional[str],
) -> Dict[str, str]:
    if audio_error:
        return {
            'audio_backend_selected': 'none',
            'audio_backend_reason': 'audio_processing_error',
        }

    if not isinstance(audio_info, dict):
        return {
            'audio_backend_selected': 'none',
            'audio_backend_reason': 'dedupe_skipped' if skip_audio else 'no_audio_stream',
        }

    candidates: List[Dict[str, Any]] = [audio_info]
    data = audio_info.get('data')
    raw = audio_info.get('raw')
    if isinstance(data, dict):
        candidates.append(data)
    if isinstance(raw, dict):
        candidates.append(raw)

    for candidate in candidates:
        selected = candidate.get('audio_backend_selected')
        reason = candidate.get('audio_backend_reason')
        if isinstance(selected, str) and selected in {'wsl', 'windows', 'none'}:
            return {
                'audio_backend_selected': selected,
                'audio_backend_reason': (
                    reason if isinstance(reason, str) and reason.strip() else 'explicit_backend_marker'
                ),
            }

    transcript_meta: Dict[str, Any] = {}
    for candidate in candidates:
        meta = candidate.get('transcript_meta')
        if isinstance(meta, dict):
            transcript_meta = meta
            break

    method = str(transcript_meta.get('method') or '').strip().lower()
    status = str(transcript_meta.get('status') or '').strip().lower()

    def _has_segments(value: Any) -> bool:
        return isinstance(value, list) and len(value) > 0

    has_transcript = False
    has_segments = False
    for candidate in candidates:
        if isinstance(candidate.get('transcript'), str) and candidate.get('transcript', '').strip():
            has_transcript = True
        if _has_segments(candidate.get('segments')):
            has_segments = True

    if method in {'wsl2_gpu', 'wsl_faster_whisper_venv'}:
        reason = f'wsl_transcript_{status}' if status else 'wsl_transcript_selected'
        return {'audio_backend_selected': 'wsl', 'audio_backend_reason': reason}

    if has_transcript or has_segments:
        return {
            'audio_backend_selected': 'windows',
            'audio_backend_reason': f'windows_transcript_{status}' if status else 'windows_transcript_available',
        }

    if status:
        return {'audio_backend_selected': 'none', 'audio_backend_reason': f'unavailable_backend_{status}'}

    return {'audio_backend_selected': 'none', 'audio_backend_reason': 'unavailable_backend'}


def _read_audio_backend_marker(audio_info: Optional[Dict[str, Any]], key: str) -> Any:
    if not isinstance(audio_info, dict):
        return None
    candidates: List[Dict[str, Any]] = [audio_info]
    data = audio_info.get('data')
    raw = audio_info.get('raw')
    if isinstance(data, dict):
        candidates.append(data)
    if isinstance(raw, dict):
        candidates.append(raw)
    for candidate in candidates:
        if key in candidate:
            return candidate.get(key)
    return None


def _record_audio_backend_event(run_context: Optional[Dict[str, Any]], event: Dict[str, Any]) -> None:
    if not isinstance(run_context, dict):
        return
    events = run_context.get('audio_backend_events')
    if not isinstance(events, list):
        events = []
        run_context['audio_backend_events'] = events
    events.append(dict(event))


def _resolve_audio_backend_attribution(
    audio_info: Optional[Dict[str, Any]],
    *,
    skip_audio: bool,
    audio_error: Optional[str],
    audio_runtime_contract: Optional[Dict[str, Any]],
    run_context: Optional[Dict[str, Any]],
    scene_id: str,
    scene_index: Any,
) -> Dict[str, Any]:
    inferred_effective = _infer_audio_backend_fields(
        audio_info,
        skip_audio=skip_audio,
        audio_error=audio_error,
    )
    selected = 'none'
    selected_reason = 'runtime_contract_unset'
    if isinstance(audio_runtime_contract, dict):
        contract_selected = audio_runtime_contract.get('selected')
        contract_reason = audio_runtime_contract.get('reason')
        if isinstance(contract_selected, str) and contract_selected.strip().lower() in {'wsl', 'windows', 'none'}:
            selected = contract_selected.strip().lower()
            if isinstance(contract_reason, str) and contract_reason.strip():
                selected_reason = contract_reason.strip()
            else:
                selected_reason = 'runtime_contract_selected'
    if selected_reason == 'runtime_contract_unset':
        selected = inferred_effective['audio_backend_selected']
        selected_reason = 'scene_inferred_selected'

    explicit_effective = _read_audio_backend_marker(audio_info, 'audio_backend_effective')
    explicit_effective_reason = _read_audio_backend_marker(audio_info, 'audio_backend_effective_reason')
    if isinstance(explicit_effective, str) and explicit_effective.strip().lower() in {'wsl', 'windows', 'none', 'failed'}:
        effective = explicit_effective.strip().lower()
        if isinstance(explicit_effective_reason, str) and explicit_effective_reason.strip():
            effective_reason = explicit_effective_reason.strip()
        else:
            effective_reason = 'explicit_effective_marker'
    else:
        effective = inferred_effective['audio_backend_selected']
        effective_reason = inferred_effective['audio_backend_reason']

    if isinstance(audio_error, str) and audio_error.strip():
        effective = 'failed'
        effective_reason = 'audio_processing_error'

    downgraded = selected in {'wsl', 'windows'} and effective in {'wsl', 'windows', 'none', 'failed'} and selected != effective
    downgrade_reason: Optional[str] = None
    downgrade_details: Dict[str, Any] = {}
    downgrade_ts_utc: Optional[str] = None
    if downgraded:
        if audio_error:
            downgrade_reason = 'audio_processing_error'
            downgrade_details['audio_error'] = audio_error
        elif selected == 'wsl' and effective == 'windows':
            downgrade_reason = 'wsl_to_windows_fallback'
        elif selected == 'wsl' and effective == 'failed':
            downgrade_reason = 'wsl_processing_failed'
        elif selected == 'wsl' and effective == 'none':
            downgrade_reason = 'wsl_unavailable_in_scene'
        elif selected == 'windows' and effective == 'failed':
            downgrade_reason = 'windows_processing_failed'
        elif selected == 'windows' and effective == 'none':
            downgrade_reason = 'windows_unavailable_in_scene'
        else:
            downgrade_reason = f'{selected}_to_{effective}'
        downgrade_ts_utc = datetime.now(timezone.utc).isoformat()
        downgrade_details['selected_reason'] = selected_reason
        downgrade_details['effective_reason'] = effective_reason
        unavailable_details = _read_audio_backend_marker(audio_info, 'audio_backend_unavailable_details')
        if isinstance(unavailable_details, dict) and unavailable_details:
            downgrade_details['backend_unavailable'] = dict(unavailable_details)
        elif downgrade_reason in {'windows_unavailable_in_scene', 'wsl_unavailable_in_scene'}:
            transcript_meta = _read_audio_backend_marker(audio_info, 'transcript_meta')
            if isinstance(transcript_meta, dict):
                downgrade_details['transcript_status'] = transcript_meta.get('status')
                downgrade_details['transcript_engine'] = transcript_meta.get('engine')
                downgrade_details['transcript_model'] = transcript_meta.get('model')
                downgrade_details['transcript_device'] = transcript_meta.get('device')
        _record_audio_backend_event(
            run_context,
            {
                'scene_id': scene_id,
                'scene_index': scene_index,
                'selected': selected,
                'effective': effective,
                'downgrade_reason': downgrade_reason,
                'details': dict(downgrade_details),
                'ts_utc': downgrade_ts_utc,
            },
        )

    return {
        'audio_backend_selected': selected,
        'audio_backend_reason': selected_reason,
        'audio_backend_effective': effective,
        'audio_backend_effective_reason': effective_reason,
        'audio_backend_downgraded': downgraded,
        'audio_backend_downgrade_reason': downgrade_reason,
        'audio_backend_downgrade_ts': downgrade_ts_utc,
        'audio_backend_downgrade_details': downgrade_details,
    }


def _normalize_vector_store_status(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() == 'not_attempted':
        return 'not_attempted'
    if value is None:
        return None
    return bool(value)


def _aggregate_audio_backend(
    scene_outputs: List[Dict[str, Any]],
    *,
    field: str = 'audio_backend_selected',
) -> str:
    """
    Deterministic run-level backend reducer.

    Rules:
    - mixed: scenes include both wsl and windows
    - wsl: at least one scene uses wsl, and none use windows
    - windows: at least one scene uses windows, and none use wsl
    - failed: at least one scene reports failed and no wsl/windows present
    - none: no scenes report wsl/windows/failed
    """
    used_wsl = False
    used_windows = False
    used_failed = False

    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue
        backend = scene.get(field)
        if not isinstance(backend, str):
            continue
        normalized = backend.strip().lower()
        if normalized == 'wsl':
            used_wsl = True
        elif normalized == 'windows':
            used_windows = True
        elif normalized == 'failed':
            used_failed = True

    if used_wsl and used_windows:
        return 'mixed'
    if used_wsl:
        return 'wsl'
    if used_windows:
        return 'windows'
    if used_failed:
        return 'failed'
    return 'none'


def _resolve_audio_runtime_contract(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve audio backend contract once per run.
    This prevents per-scene backend discovery drift.
    """
    require_wsl = require_wsl_audio()
    requested_wsl = bool(wsl_audio_auto_enabled() or require_wsl)
    wsl_distro = str(os.environ.get("GOODQ_WSL_DISTRO") or "Ubuntu").strip() or "Ubuntu"
    contract: Dict[str, Any] = {
        'mode': 'auto',
        'requested_wsl': requested_wsl,
        'require_wsl_audio': require_wsl,
        'wsl_command_available': bool(shutil.which('wsl')),
        'wsl_distro': wsl_distro,
        'wsl_user': None,
        'wsl_workspace': None,
        'wsl_audio_workspace': None,
        'workspace_ready': False,
        'selected': 'none',
        'reason': 'unresolved',
    }

    if not requested_wsl:
        contract['selected'] = 'windows'
        contract['reason'] = 'profile_wsl_disabled'
        return contract

    if not contract['wsl_command_available']:
        if require_wsl:
            raise RuntimeError("GOODQ_REQUIRE_WSL_AUDIO=1 but wsl command is unavailable.")
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_command_unavailable'
        return contract

    host_cfg = cfg.get('host') if isinstance(cfg, dict) else {}
    cfg_wsl_user = (
        str(host_cfg.get('wsl_user')).strip()
        if isinstance(host_cfg, dict) and host_cfg.get('wsl_user') is not None
        else ''
    )
    explicit_wsl_user = str(os.environ.get("GOODQ_WSL_USER") or "").strip()
    if not explicit_wsl_user and cfg_wsl_user and cfg_wsl_user.lower() not in {'auto', 'unset'}:
        explicit_wsl_user = cfg_wsl_user

    if explicit_wsl_user:
        wsl_user = explicit_wsl_user
    else:
        if require_wsl:
            raise RuntimeError(
                "GOODQ_REQUIRE_WSL_AUDIO=1 requires GOODQ_WSL_USER to be set explicitly."
            )
        wsl_user = ''
        for candidate in (os.environ.get("USER"), os.environ.get("USERNAME"), os.environ.get("LOGNAME")):
            if candidate:
                wsl_user = str(candidate).strip()
                break
        if not wsl_user:
            wsl_user = 'user'

    cfg_wsl_workspace = (
        str(host_cfg.get('wsl_workspace')).strip()
        if isinstance(host_cfg, dict) and host_cfg.get('wsl_workspace') is not None
        else ''
    )
    explicit_workspace = str(os.environ.get("GOODQ_WSL_WORKSPACE") or "").strip()
    workspace = explicit_workspace or cfg_wsl_workspace or f"/home/{wsl_user}/goodq_audio"
    audio_workspace = workspace.rstrip("/")
    contract['wsl_user'] = wsl_user
    contract['wsl_workspace'] = workspace
    contract['wsl_audio_workspace'] = audio_workspace

    # Export resolved identity for downstream subprocesses so all steps share one contract.
    if wsl_user:
        os.environ.setdefault("GOODQ_WSL_USER", wsl_user)
    if workspace:
        os.environ.setdefault("GOODQ_WSL_WORKSPACE", workspace)

    try:
        check = subprocess.run(
            [
                "wsl",
                "-d",
                wsl_distro,
                "--",
                "bash",
                "-lc",
                (
                    f"test -d '{audio_workspace}' && "
                    f"test -f '{audio_workspace}/setup_cuda_env.sh' && "
                    f"test -f '{audio_workspace}/process_audio.py'"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        ready = check.returncode == 0
        contract['workspace_ready'] = ready
        if ready:
            contract['selected'] = 'wsl'
            contract['reason'] = 'wsl_workspace_ready'
            return contract
        message = (
            f"WSL workspace not found for distro={wsl_distro}, workspace={audio_workspace}. "
            "Set GOODQ_WSL_USER and GOODQ_WSL_WORKSPACE for deterministic host setup."
        )
        if require_wsl:
            raise RuntimeError(message)
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_workspace_missing'
        contract['workspace_check_message'] = message
        return contract
    except Exception as e:
        message = (
            f"WSL workspace preflight failed for distro={wsl_distro}, workspace={audio_workspace}: {e}"
        )
        if require_wsl:
            raise RuntimeError(message) from e
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_workspace_preflight_failed'
        contract['workspace_check_message'] = message
        return contract


def _merge_modality_state(current: str, candidate: str) -> str:
    rank = {
        'not_attempted': 0,
        'unavailable': 1,
        'available': 2,
    }
    current_norm = str(current or '').strip().lower()
    candidate_norm = str(candidate or '').strip().lower()
    if current_norm not in rank:
        current_norm = 'not_attempted'
    if candidate_norm not in rank:
        candidate_norm = 'not_attempted'
    return candidate_norm if rank[candidate_norm] > rank[current_norm] else current_norm


def _status_dict_to_modality_state(status_dict: Any) -> str:
    if not isinstance(status_dict, dict):
        return 'not_attempted'
    raw_status = status_dict.get('status')
    if not isinstance(raw_status, str):
        return 'not_attempted'
    status = raw_status.strip().lower()
    if status in {'ok', 'success', 'complete'}:
        return 'available'
    if status in {'unavailable', 'error', 'failed'}:
        return 'unavailable'
    if status in {
        'no_text',
        'no_file',
        'no_index_path',
        'no_audio_stream',
        'no_audio_output',
        'skipped',
        'dedupe_skipped',
    }:
        return 'not_attempted'
    return 'not_attempted'


def _aggregate_modality_status(
    scene_outputs: List[Dict[str, Any]],
    phase6_embeddings_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    status = {
        'vision_clip': 'not_attempted',
        'vision_dino': 'not_attempted',
        'text_embed': 'not_attempted',
        'audio_embed': 'not_attempted',
    }

    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue

        keyframe = scene.get('keyframe')
        if isinstance(keyframe, dict):
            if keyframe.get('clip_embedding') is not None:
                status['vision_clip'] = _merge_modality_state(status['vision_clip'], 'available')
            status['vision_clip'] = _merge_modality_state(
                status['vision_clip'],
                _status_dict_to_modality_state(keyframe.get('clip_meta')),
            )
            if keyframe.get('dino_embedding') is not None:
                status['vision_dino'] = _merge_modality_state(status['vision_dino'], 'available')
            status['vision_dino'] = _merge_modality_state(
                status['vision_dino'],
                _status_dict_to_modality_state(keyframe.get('dino_meta')),
            )
            status['text_embed'] = _merge_modality_state(
                status['text_embed'],
                _status_dict_to_modality_state(keyframe.get('frame_text_embed_meta')),
            )

        audio = scene.get('audio')
        if isinstance(audio, dict):
            if audio.get('clap_embedding') is not None:
                status['audio_embed'] = _merge_modality_state(status['audio_embed'], 'available')
            status['audio_embed'] = _merge_modality_state(
                status['audio_embed'],
                _status_dict_to_modality_state(audio.get('clap_meta')),
            )
            status['text_embed'] = _merge_modality_state(
                status['text_embed'],
                _status_dict_to_modality_state(audio.get('audio_text_embed_meta')),
            )

    if isinstance(phase6_embeddings_result, dict):
        clip_written = _coerce_nonnegative_int(phase6_embeddings_result.get('scene_clip_vectors_written'))
        dino_written = _coerce_nonnegative_int(phase6_embeddings_result.get('scene_dino_vectors_written'))
        clip_attempted = _coerce_nonnegative_int(phase6_embeddings_result.get('clip_embeddings'))
        dino_attempted = _coerce_nonnegative_int(phase6_embeddings_result.get('dino_embeddings'))
        if bool(phase6_embeddings_result.get('clip_committed')) or clip_written > 0:
            status['vision_clip'] = 'available'
        elif clip_attempted > 0:
            status['vision_clip'] = _merge_modality_state(status['vision_clip'], 'unavailable')
        if bool(phase6_embeddings_result.get('dino_committed')) or dino_written > 0:
            status['vision_dino'] = 'available'
        elif dino_attempted > 0:
            status['vision_dino'] = _merge_modality_state(status['vision_dino'], 'unavailable')

    return status


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_content_empty_duration_threshold(cfg: Dict[str, Any]) -> float:
    run_cfg = cfg.get('run') if isinstance(cfg, dict) else None
    if isinstance(run_cfg, dict):
        configured = run_cfg.get('content_empty_duration_threshold_sec')
        threshold = _coerce_float(configured, default=1.0)
        return threshold if threshold >= 0.0 else 1.0
    return 1.0


def _extract_audio_payload(scene: Dict[str, Any]) -> Dict[str, Any]:
    audio = scene.get('audio')
    return audio if isinstance(audio, dict) else {}


def _extract_transcript_text(audio_payload: Dict[str, Any]) -> str:
    for key in ('transcript', 'full_text'):
        value = audio_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raw = audio_payload.get('raw')
    if isinstance(raw, dict):
        for key in ('transcript', 'full_text'):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ''


def _extract_segments(audio_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments = audio_payload.get('segments')
    if isinstance(segments, list):
        return [seg for seg in segments if isinstance(seg, dict)]
    raw = audio_payload.get('raw')
    if isinstance(raw, dict) and isinstance(raw.get('segments'), list):
        return [seg for seg in raw.get('segments') if isinstance(seg, dict)]
    return []


def _has_meaningful_audio_segments(segments: List[Dict[str, Any]]) -> bool:
    for segment in segments:
        text = segment.get('text')
        if isinstance(text, str) and text.strip():
            return True
    return False


def _scene_has_processing_error(scene: Dict[str, Any]) -> bool:
    for key in ('audio_error', 'frame_error', 'keyframe_error', 'step_error'):
        value = scene.get(key)
        if isinstance(value, str) and value.strip():
            return True

    errors = scene.get('errors')
    if isinstance(errors, dict):
        for value in errors.values():
            if isinstance(value, str) and value.strip():
                return True

    reason = scene.get('audio_backend_reason')
    if isinstance(reason, str) and reason == 'audio_processing_error':
        return True

    return False


def _classify_scene_content(
    scene: Dict[str, Any],
    *,
    empty_duration_threshold_sec: float,
) -> str:
    """
    Deterministic scene-level content classification.
    Allowed values: signal | empty | processing_error
    """
    if _scene_has_processing_error(scene):
        return 'processing_error'

    duration = _coerce_float(scene.get('duration'))
    audio_payload = _extract_audio_payload(scene)
    transcript_meta = audio_payload.get('transcript_meta')
    transcript_status = (
        str(transcript_meta.get('status', '')).strip().lower()
        if isinstance(transcript_meta, dict)
        else ''
    )
    transcript_duration = (
        _coerce_float(transcript_meta.get('duration'))
        if isinstance(transcript_meta, dict)
        else None
    )
    transcript_text = _extract_transcript_text(audio_payload)
    segments = _extract_segments(audio_payload)
    has_meaningful_segments = _has_meaningful_audio_segments(segments)

    audio_meta = audio_payload.get('audio_meta')
    audio_path = audio_payload.get('path')
    audio_present = bool(
        (isinstance(audio_path, str) and audio_path.strip())
        or isinstance(audio_meta, dict)
        or segments
        or transcript_text
    )

    if duration < empty_duration_threshold_sec:
        return 'empty'

    if transcript_status == 'success' and (not transcript_text or transcript_duration == 0.0):
        return 'empty'

    if audio_present and not transcript_text and not has_meaningful_segments:
        return 'empty'

    return 'signal'


def _aggregate_content_summary(scene_outputs: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {
        'signal': 0,
        'empty': 0,
        'processing_error': 0,
    }
    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue
        state = scene.get('content_state')
        if isinstance(state, str) and state in summary:
            summary[state] += 1
        else:
            summary['signal'] += 1
    return summary


def _coerce_nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _resolve_store_status_for_points(points_attempted: Any, raw_status: Any) -> Any:
    points = _coerce_nonnegative_int(points_attempted)
    if points <= 0:
        return 'not_attempted'
    normalized = _normalize_vector_store_status(raw_status)
    if isinstance(normalized, bool):
        return normalized
    # Deterministic truth: attempted writes must resolve to a concrete boolean.
    return False


def _aggregate_scene_store_status(scene_outputs: List[Dict[str, Any]], store_key: str) -> Any:
    attempted = 0
    statuses: List[bool] = []

    for scene in scene_outputs:
        if not isinstance(scene, dict):
            continue
        persistence = scene.get('persistence')
        if not isinstance(persistence, dict):
            continue
        points = _coerce_nonnegative_int(persistence.get('vector_points_attempted'))
        attempted += points
        if points <= 0:
            continue
        status = _resolve_store_status_for_points(points, persistence.get(store_key))
        if isinstance(status, bool):
            statuses.append(status)
        else:
            statuses.append(False)

    if attempted <= 0:
        return 'not_attempted'
    return False if any(not s for s in statuses) else True


def _merge_store_statuses(*statuses: Any) -> Any:
    normalized = [_normalize_vector_store_status(s) for s in statuses]
    if any(s is False for s in normalized):
        return False
    if any(s is True for s in normalized):
        return True
    return 'not_attempted'


def _compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write_json(path: Path, data: Any, *, indent: Optional[int] = 2) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding='utf-8')
    os.replace(tmp, path)


_SENSITIVE_SNAPSHOT_KEYS: Set[str] = {
    'token',
    'ha_token',
    'hf_token',
    'huggingface_token',
    'pyannote_token',
    'access_token',
    'refresh_token',
    'id_token',
    'api_key',
    'apikey',
    'secret',
    'client_secret',
    'password',
    'passwd',
    'authorization',
    'bearer_token',
}
_JWT_LIKE_RE = re.compile(r'^[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}$')


def _is_sensitive_snapshot_key(key: str) -> bool:
    normalized = re.sub(r'[^a-z0-9]+', '_', key.strip().lower()).strip('_')
    if not normalized:
        return False
    if normalized in _SENSITIVE_SNAPSHOT_KEYS:
        return True
    if normalized.endswith('_token'):
        return True
    if normalized.endswith('_secret'):
        return True
    if normalized.endswith('_password'):
        return True
    return False


def _redact_sensitive_snapshot_values(obj: Any, key_hint: Optional[str] = None) -> Any:
    if isinstance(obj, dict):
        redacted: Dict[str, Any] = {}
        for key, value in obj.items():
            sensitive = isinstance(key, str) and _is_sensitive_snapshot_key(key)
            redacted[key] = '***REDACTED***' if sensitive else _redact_sensitive_snapshot_values(value, key if isinstance(key, str) else key_hint)
        return redacted
    if isinstance(obj, list):
        return [_redact_sensitive_snapshot_values(item, key_hint) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_redact_sensitive_snapshot_values(item, key_hint) for item in obj)
    if isinstance(obj, str):
        if key_hint and _is_sensitive_snapshot_key(key_hint):
            return '***REDACTED***'
        text = obj.strip()
        if _JWT_LIKE_RE.fullmatch(text):
            return '***REDACTED***'
        return obj
    return obj


def _write_cfg_snapshot(cfg: Dict[str, Any], workspace: Path) -> Path:
    cfg_path = workspace / '_resolved_config.json'
    
    # Convert config to JSON-serializable format
    def make_json_serializable(obj):
        # Handle typer OptionInfo objects - extract the actual default value
        if hasattr(obj, 'default'):
            return make_json_serializable(obj.default)
        elif isinstance(obj, dict):
            return {k: make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_json_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # For other non-serializable objects, convert to string as last resort
            return str(obj)
    
    serializable_cfg = make_json_serializable(cfg)
    redacted_cfg = _redact_sensitive_snapshot_values(serializable_cfg)
    _atomic_write_json(cfg_path, redacted_cfg, indent=2)
    return cfg_path


def _base_env(cfg_json: Optional[Path] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault('PYTHONNOUSERSITE', '0')
    env.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '1')
    models_root = _resolve_models_dir(cfg_json=cfg_json)
    env['HF_HOME'] = str(models_root)
    env['TORCH_HOME'] = str(models_root)
    # Add parent of REPO_ROOT to PYTHONPATH so "goodq4all.steps" can be imported.
    env['PYTHONPATH'] = str(REPO_ROOT.parent)
    
    # GPU Resource Management - Pin to GPU 0
    env['CUDA_VISIBLE_DEVICES'] = '0'
    
    # Enable deterministic CUDA operations for reproducibility (optional)
    # Uncomment if reproducibility is needed (slight performance cost)
    # env['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    # env['PYTHONHASHSEED'] = '1337'
    
    return env


def _persist_healer_retry_metadata(cfg_json: Path) -> None:
    global _CURRENT_RUN_CONTEXT
    if not isinstance(_CURRENT_RUN_CONTEXT, dict):
        return
    try:
        cfg_data: Dict[str, Any] = {}
        if cfg_json.exists():
            raw = cfg_json.read_text(encoding='utf-8').strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    cfg_data = parsed
        run_meta = cfg_data.get('run')
        if not isinstance(run_meta, dict):
            run_meta = {}
        run_meta['healer_retry_count'] = int(_CURRENT_RUN_CONTEXT.get('healer_retry_count', 0) or 0)
        by_step = _CURRENT_RUN_CONTEXT.get('healer_retry_by_step') or {}
        run_meta['healer_retry_by_step'] = dict(by_step) if isinstance(by_step, dict) else {}
        run_meta['native_retry_count'] = int(_CURRENT_RUN_CONTEXT.get('native_retry_count', 0) or 0)
        native_by_step = _CURRENT_RUN_CONTEXT.get('native_retry_by_step') or {}
        run_meta['native_retry_by_step'] = dict(native_by_step) if isinstance(native_by_step, dict) else {}
        warnings = _CURRENT_RUN_CONTEXT.get('warnings') or []
        run_meta['warnings'] = list(warnings) if isinstance(warnings, list) else []
        cfg_data['run'] = run_meta
        _atomic_write_json(cfg_json, cfg_data, indent=2)
    except Exception as e:
        logger.warning("[RUN] Failed to persist healer retry metadata: %s", e)


def _record_run_warning(
    cfg_json: Path,
    *,
    code: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    global _CURRENT_RUN_CONTEXT
    if not isinstance(_CURRENT_RUN_CONTEXT, dict):
        return
    warnings = _CURRENT_RUN_CONTEXT.get('warnings')
    if not isinstance(warnings, list):
        warnings = []
        _CURRENT_RUN_CONTEXT['warnings'] = warnings
    warnings.append(
        {
            'code': code,
            'message': message,
            'context': dict(context or {}),
            'ts_utc': datetime.now(timezone.utc).isoformat(),
        }
    )
    _persist_healer_retry_metadata(cfg_json)


def _record_healer_retry(step_name: str, cfg_json: Path) -> None:
    global _CURRENT_RUN_CONTEXT
    if isinstance(_CURRENT_RUN_CONTEXT, dict):
        current_count = int(_CURRENT_RUN_CONTEXT.get('healer_retry_count', 0) or 0)
        _CURRENT_RUN_CONTEXT['healer_retry_count'] = current_count + 1
        by_step = _CURRENT_RUN_CONTEXT.get('healer_retry_by_step')
        if not isinstance(by_step, dict):
            by_step = {}
            _CURRENT_RUN_CONTEXT['healer_retry_by_step'] = by_step
        by_step[step_name] = int(by_step.get(step_name, 0) or 0) + 1
    _persist_healer_retry_metadata(cfg_json)


def _normalize_windows_status_code(return_code: int) -> int:
    return (int(return_code) + (1 << 32)) & 0xFFFFFFFF


def _is_windows_native_crash(return_code: int) -> bool:
    # Native Windows exception family: 0xC0000000 - 0xCFFFFFFF.
    status_code = _normalize_windows_status_code(return_code)
    return (status_code & 0xF0000000) == 0xC0000000


def _record_native_retry(
    step_name: str,
    cfg_json: Path,
    return_code: int,
    attempt: int,
    env_fingerprint: Optional[str] = None,
) -> None:
    global _CURRENT_RUN_CONTEXT
    status_code = _normalize_windows_status_code(return_code)
    if isinstance(_CURRENT_RUN_CONTEXT, dict):
        current_count = int(_CURRENT_RUN_CONTEXT.get('native_retry_count', 0) or 0)
        _CURRENT_RUN_CONTEXT['native_retry_count'] = current_count + 1
        by_step = _CURRENT_RUN_CONTEXT.get('native_retry_by_step')
        if not isinstance(by_step, dict):
            by_step = {}
            _CURRENT_RUN_CONTEXT['native_retry_by_step'] = by_step
        by_step[step_name] = int(by_step.get(step_name, 0) or 0) + 1
    context = {
        'step': step_name,
        'return_code': int(return_code),
        'status_code_hex': f"0x{status_code:08X}",
        'attempt': int(attempt),
    }
    if env_fingerprint:
        context['env_fingerprint'] = env_fingerprint
    _record_run_warning(
        cfg_json,
        code='native_crash_retry',
        message='Retrying step after native subprocess crash',
        context=context,
    )


def _run_step(
    env_name: str,
    step_name: str,
    payload: Dict[str, Any],
    cfg_json: Path,
    _healer_retry_attempt: int = 0,
    _native_retry_attempt: int = 0,
    _direct_env_fallback_attempt: int = 0,
    _prefer_direct_env_python: bool = False,
) -> Dict[str, Any]:
    work_env = _base_env(cfg_json)
    
    # Convert payload to JSON-serializable format
    def make_json_serializable(obj):
        # Handle typer OptionInfo objects - extract the actual default value
        if hasattr(obj, 'default'):
            return make_json_serializable(obj.default)
        elif isinstance(obj, dict):
            return {k: make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_json_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # For other non-serializable objects, convert to string as last resort
            return str(obj)
    
    tmp_dir = Path(tempfile.mkdtemp(prefix='ingest_step_'))
    try:
        in_path = tmp_dir / 'input.json'
        out_path = tmp_dir / 'output.json'
        serializable_payload = make_json_serializable(payload)
        in_path.write_text(json.dumps(serializable_payload, ensure_ascii=False), encoding='utf-8')
        
        # Resolve conda path to handle subprocess PATH issues across hosts.
        conda_exe = resolve_conda()
        conda_available = False
        if os.path.isabs(conda_exe):
            conda_available = os.path.exists(conda_exe)
        else:
            conda_available = shutil.which(conda_exe) is not None

        def _resolve_env_python_for_step_fallback(name: str) -> Optional[str]:
            try:
                from configs.python_paths import get_env_python

                env_python = get_env_python(name)
            except Exception as e:
                logger.warning(
                    "run_ingestion warning context=%s error=%s",
                    "direct_env_python.resolve",
                    e,
                )
                return None
            if env_python and Path(env_python).exists():
                return str(env_python)
            return None

        direct_env_python = _resolve_env_python_for_step_fallback(env_name)

        def _build_step_runner_cmd(*, prefer_direct_env_python: bool) -> tuple[List[str], str]:
            if prefer_direct_env_python:
                if not direct_env_python:
                    raise RuntimeError(
                        f"Direct interpreter fallback unavailable for env={env_name} step={step_name}"
                    )
                return (
                    [
                        direct_env_python,
                        str(REPO_ROOT / 'cli' / 'step_runner.py'),
                        '--step', step_name,
                        '--in', str(in_path),
                        '--out', str(out_path),
                        '--cfg', str(cfg_json),
                    ],
                    "direct_env_python",
                )
            if conda_available:
                return (
                    [
                        conda_exe, 'run', '-n', env_name,
                        '--no-capture-output',  # Let output flow through
                        'python', str(REPO_ROOT / 'cli' / 'step_runner.py'),  # Use absolute path instead of -m
                        '--step', step_name,
                        '--in', str(in_path),
                        '--out', str(out_path),
                        '--cfg', str(cfg_json),
                    ],
                    "conda_run",
                )
            raise RuntimeError(
                "Conda unavailable for step execution "
                f"(step={step_name}, env={env_name}, conda_exe={conda_exe}). "
                "Bare interpreter fallback is disabled."
            )

        try:
            cmd, launcher_kind = _build_step_runner_cmd(
                prefer_direct_env_python=_prefer_direct_env_python
            )
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("run_ingestion abort: step_command_build_failed step=%s env=%s error=%s", step_name, env_name, e)
            raise

        if not conda_available and launcher_kind != "direct_env_python":
            error_msg = (
                "Conda unavailable for step execution "
                f"(step={step_name}, env={env_name}, conda_exe={conda_exe}). "
                "Bare interpreter fallback is disabled."
            )
            logger.error("run_ingestion abort: %s", error_msg)
            raise RuntimeError(error_msg)
        
        # CRITICAL: Ensure PYTHONPATH is available in conda env
        work_env['CONDA_PREFIX_1'] = work_env.get('CONDA_PREFIX', '')
        # Ensure PYTHONPATH points to repo parent so goodq4all.steps can be imported.
        parent_dir = str(REPO_ROOT.parent)
        if 'PYTHONPATH' not in work_env or parent_dir not in work_env['PYTHONPATH']:
            existing_path = work_env.get('PYTHONPATH', '')
            work_env['PYTHONPATH'] = (
                f"{parent_dir}{os.pathsep}{existing_path}" if existing_path else parent_dir
            )

        step_env = work_env
        if step_name in SUBPROCESS_THREAD_CAP_STEPS:
            step_env = dict(work_env)
            for env_key, env_value in SUBPROCESS_THREAD_CAP_ENV.items():
                step_env.setdefault(env_key, env_value)
        if step_name in SUBPROCESS_AUDIO_OPENMP_GUARD_STEPS:
            if step_env is work_env:
                step_env = dict(work_env)
            for env_key, env_value in SUBPROCESS_AUDIO_OPENMP_GUARD_ENV.items():
                step_env.setdefault(env_key, env_value)

        start_ts = time.perf_counter()
        observer = _observer()
        observer_step = f"step.{step_name}"
        observer_meta: Dict[str, Any] = {"env": env_name}
        payload_video_id = payload.get('video_id') or payload.get('video_hash')
        if payload_video_id is not None:
            observer_meta["video_id"] = str(payload_video_id)
        payload_scene_id = payload.get('scene_id')
        if payload_scene_id is not None:
            observer_meta["scene_id"] = str(payload_scene_id)
        payload_scene_index = payload.get('scene_index')
        if payload_scene_index is not None:
            observer_meta["scene_index"] = payload_scene_index
        elif isinstance(payload.get('scene'), dict) and payload['scene'].get('index') is not None:
            observer_meta["scene_index"] = payload['scene'].get('index')
        observer_meta["attempt"] = max(int(_healer_retry_attempt), int(_native_retry_attempt)) + 1
        observer_meta["healer_retry_attempt"] = int(_healer_retry_attempt)
        observer_meta["native_retry_attempt"] = int(_native_retry_attempt)
        observer_meta["launcher"] = launcher_kind
        observer_meta["direct_env_fallback_attempt"] = int(_direct_env_fallback_attempt)
        if VERBOSE:
            typer.echo(f'[step] -> {step_name} ({env_name}) [{launcher_kind}]')
        stop_heartbeat = (lambda: None)
        process: Optional[subprocess.Popen[str]] = None
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=step_env,
            )
            observer_meta["subprocess_pid"] = int(process.pid)
            if observer:
                observer.step_start(observer_step, metadata=observer_meta)
                stop_heartbeat = observer.begin_heartbeat(observer_step, metadata=observer_meta)
            try:
                stdout_text, stderr_text = process.communicate(timeout=STEP_TIMEOUT)
            finally:
                stop_heartbeat()
            result = subprocess.CompletedProcess(
                cmd,
                process.returncode if process.returncode is not None else 1,
                stdout_text or '',
                stderr_text or '',
            )
        except subprocess.TimeoutExpired as exc:
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    process.communicate(timeout=5)
                except Exception:
                    pass
            if observer:
                observer.step_error(
                    observer_step,
                    error=f"timeout_after_{STEP_TIMEOUT}s",
                    metadata=observer_meta,
                )
            if VERBOSE:
                typer.echo(f'[step] !! {step_name} ({env_name}) timed out after {STEP_TIMEOUT}s', err=True)

            if _control_agent_runtime_enabled():
                try:
                    agent = ControlAgent()
                    healing_result = agent.auto_heal_failure(
                        error=exc,
                        step_name=step_name,
                        context={'env': env_name, 'timeout': STEP_TIMEOUT}
                    )

                    if healing_result.get('success'):
                        if _healer_retry_attempt >= MAX_HEALER_RETRIES:
                            logger.warning("Healer retry ceiling reached for step=%s", step_name)
                            typer.echo(f"[heal] [WARN] Healer retry ceiling reached for step={step_name}", err=True)
                        else:
                            _record_healer_retry(step_name, cfg_json)
                            typer.echo("[heal] [PASS] Timeout healed, retrying step...", err=True)
                            # Retry the step with the same payload after healing actions
                            return _run_step(
                                env_name,
                                step_name,
                                payload,
                                cfg_json,
                                _healer_retry_attempt=_healer_retry_attempt + 1,
                                _native_retry_attempt=_native_retry_attempt,
                            )
                    else:
                        typer.echo(f"[heal] [FAIL] Could not heal timeout: {healing_result.get('recommendation', 'No strategy')}", err=True)
                except Exception as heal_error:
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "control_agent.auto_heal_timeout",
                        heal_error,
                    )
                    typer.echo(f"[heal] [WARN] Healing failed: {heal_error}", err=True)

            raise RuntimeError(f"Step {step_name} timed out after {STEP_TIMEOUT}s") from exc
        
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            combined_output = f"{stdout}\n{stderr}".lower()

            should_try_direct_env_fallback = (
                launcher_kind == "conda_run"
                and step_name in _OPTIONAL_DIRECT_ENV_FALLBACK_STEPS
                and _direct_env_fallback_attempt == 0
                and direct_env_python is not None
                and (
                    "conda.cli.main_run:execute(127)" in combined_output
                    or "failed to run 'conda activate" in combined_output
                    or (
                        "__conda_tmp_" in combined_output
                        and (
                            "being used by another process" in combined_output
                            or "cannot access the file because it is being used by another process" in combined_output
                        )
                    )
                )
            )
            if should_try_direct_env_fallback:
                logger.warning(
                    "[RUN] Conda launcher failed for optional step=%s env=%s; retrying via direct env python",
                    step_name,
                    env_name,
                )
                if VERBOSE:
                    typer.echo(
                        f"[retry] [WARN] Conda launcher failed for {step_name}; retrying via direct env python",
                        err=True,
                    )
                return _run_step(
                    env_name,
                    step_name,
                    payload,
                    cfg_json,
                    _healer_retry_attempt=_healer_retry_attempt,
                    _native_retry_attempt=_native_retry_attempt,
                    _direct_env_fallback_attempt=1,
                    _prefer_direct_env_python=True,
                )

            error_msg = f"Step {step_name} failed ({env_name})\nSTDOUT: {stdout}\nSTDERR: {stderr}"
            if observer:
                observer.step_error(
                    observer_step,
                    error=f"returncode_{result.returncode}",
                    metadata=observer_meta,
                )

            is_native_crash = _is_windows_native_crash(result.returncode)
            if (
                step_name in NATIVE_CRASH_RETRY_STEPS
                and is_native_crash
                and _native_retry_attempt < MAX_NATIVE_STEP_RETRIES
            ):
                retry_attempt = _native_retry_attempt + 1
                env_fingerprint_line: Optional[str] = None
                for stderr_line in stderr.splitlines():
                    if 'subprocess_env_fingerprint' in stderr_line:
                        env_fingerprint_line = stderr_line.strip()
                        break
                _record_native_retry(
                    step_name,
                    cfg_json,
                    result.returncode,
                    retry_attempt,
                    env_fingerprint=env_fingerprint_line,
                )
                status_code = _normalize_windows_status_code(result.returncode)
                logger.warning(
                    "[RUN] Native crash detected for step=%s return_code=%s status_code=0x%08X retry=%s/%s",
                    step_name,
                    result.returncode,
                    status_code,
                    retry_attempt,
                    MAX_NATIVE_STEP_RETRIES,
                )
                if env_fingerprint_line:
                    logger.warning(
                        "[RUN] Native crash env fingerprint step=%s %s",
                        step_name,
                        env_fingerprint_line,
                    )
                if VERBOSE:
                    typer.echo(
                        (
                            f"[retry] [WARN] Native crash for {step_name} "
                            f"(0x{status_code:08X}); retrying once"
                        ),
                        err=True,
                    )
                return _run_step(
                    env_name,
                    step_name,
                    payload,
                    cfg_json,
                    _healer_retry_attempt=_healer_retry_attempt,
                    _native_retry_attempt=retry_attempt,
                )

            if _control_agent_runtime_enabled():
                try:
                    agent = ControlAgent()
                    healing_result = agent.auto_heal_failure(
                        error=RuntimeError(error_msg),
                        step_name=step_name,
                        context={
                            'env': env_name,
                            'returncode': result.returncode,
                            'stdout': stdout[:500],  # First 500 chars
                            'stderr': stderr[:500],
                        }
                    )

                    if healing_result.get('success'):
                        if _healer_retry_attempt >= MAX_HEALER_RETRIES:
                            logger.warning("Healer retry ceiling reached for step=%s", step_name)
                            typer.echo(f"[heal] [WARN] Healer retry ceiling reached for step={step_name}", err=True)
                        else:
                            _record_healer_retry(step_name, cfg_json)
                            typer.echo("[heal] [PASS] Step failure healed, retrying...", err=True)
                            # Retry the same step after healing actions
                            return _run_step(
                                env_name,
                                step_name,
                                payload,
                                cfg_json,
                                _healer_retry_attempt=_healer_retry_attempt + 1,
                                _native_retry_attempt=_native_retry_attempt,
                            )
                    else:
                        typer.echo("[heal] [FAIL] Could not heal failure", err=True)
                        if healing_result.get('recommendation'):
                            typer.echo(f"[heal] [SYMBOL] Suggestion: {healing_result['recommendation'][:200]}", err=True)
                except Exception as heal_error:
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "control_agent.auto_heal_failure",
                        heal_error,
                    )
                    typer.echo(f"[heal] [WARN] Healing attempt failed: {heal_error}", err=True)

            raise RuntimeError(error_msg)
        duration = time.perf_counter() - start_ts
        if observer:
            observer.step_end(
                observer_step,
                metadata={
                    **observer_meta,
                    "duration_sec": round(duration, 3),
                },
            )
        if VERBOSE:
            typer.echo(f'[step] <- {step_name} ({env_name}) [{duration:.1f}s]')
        
        # PHASE 3: Learn from successful execution
        if _control_agent_runtime_enabled():
            try:
                agent = ControlAgent()
                agent.learn_from_success(
                    step_name=step_name,
                    execution_time_seconds=duration,
                    config_used={'env': env_name, 'timeout': STEP_TIMEOUT},
                    context={'models_root': str(models_root)}
                )
            except Exception as e:
                logger.warning(
                    "run_ingestion warning context=%s error=%s",
                    "control_agent.learn_from_success",
                    e,
                )
                _record_run_warning(
                    cfg_json,
                    code='control_agent_learn_failed',
                    message=str(e),
                    context={'step': step_name, 'env': env_name},
                )
        
        if out_path.exists():
            output = out_path.read_text(encoding='utf-8').strip()
            return json.loads(output) if output else {}
        stdout = result.stdout.strip()
        return json.loads(stdout) if stdout else {}
    finally:
        try:
            for child in tmp_dir.iterdir():
                child.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except Exception as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "step_temp_cleanup",
                e,
            )



def _log_skipped_steps(
    cfg: Dict[str, Any],
    step_names: List[str],
    *,
    modality: str,
    video_hash: str,
    scene_id: str,
    scene_index: Optional[int],
    source_path: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    extra_payload: Dict[str, Any] = {'reason': 'dedupe'}
    if isinstance(extra, dict):
        extra_payload.update(extra)
    item: Dict[str, Any] = {
        'modality': modality,
        'video_hash': video_hash,
        'video_id': video_hash,
    }
    if scene_id is not None:
        item['scene_id'] = scene_id
    if scene_index is not None:
        item['scene_index'] = scene_index
    if source_path:
        item['source_path'] = source_path
    for step_name in step_names:
        log_step_run(cfg, step_name, item, 0.0, 'skipped', extra=extra_payload)


def _extract_keyframe(
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    dest_dir: Path,
    *,
    scene_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    _ensure_dir(dest_dir)
    duration = float(scene.get('duration', 0.0) or 0.0)
    start = float(scene.get('start', 0.0) or 0.0)
    timestamp = start + (duration / 2.0) if duration > 0 else start
    outfile = dest_dir / f"scene_{scene.get('index', 0):04d}.jpg"
    observer = _observer()
    observer_step = "ffmpeg.extract_keyframe"
    observer_meta = {
        "video": str(video_path),
        "scene_index": scene.get('index', 0),
    }
    if scene_id is not None:
        observer_meta["scene_id"] = str(scene_id)
    if video_id is not None:
        observer_meta["video_id"] = str(video_id)
    cmd = [
        ffmpeg,
        '-hide_banner',
        '-loglevel', 'error',
        '-ss', f'{timestamp:.3f}',
        '-i', str(video_path),
        '-frames:v', '1',
        '-y',
        str(outfile),
    ]
    stop_heartbeat = (lambda: None)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    observer_meta["subprocess_pid"] = int(process.pid)
    if observer:
        observer.step_start(observer_step, metadata=observer_meta)
        stop_heartbeat = observer.begin_heartbeat(observer_step, metadata=observer_meta)
    try:
        stdout_text, stderr_text = process.communicate()
    finally:
        stop_heartbeat()
    result = subprocess.CompletedProcess(
        cmd,
        process.returncode if process.returncode is not None else 1,
        stdout_text or '',
        stderr_text or '',
    )
    if result.returncode != 0:
        if observer:
            observer.step_error(
                observer_step,
                error=f"returncode_{result.returncode}",
                metadata=observer_meta,
            )
        raise RuntimeError(f"ffmpeg failed to extract keyframe: {result.stderr}")
    if not outfile.exists():
        if observer:
            observer.step_error(
                observer_step,
                error="output_missing",
                metadata=observer_meta,
            )
        raise RuntimeError('Keyframe extraction did not produce a file')
    if observer:
        observer.step_end(observer_step, metadata=observer_meta)
    return outfile


def _extract_audio_chunk(
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    dest_dir: Path,
    *,
    scene_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Optional[Path]:
    """Extract audio chunk - returns None if video has no audio"""
    _ensure_dir(dest_dir)
    start = float(scene.get('start', 0.0) or 0.0)
    end = float(scene.get('end', start) or start)
    duration = max(0.1, end - start)
    outfile = dest_dir / f"scene_{scene.get('index', 0):04d}.wav"
    observer = _observer()
    observer_step = "ffmpeg.extract_audio_chunk"
    observer_meta = {
        "video": str(video_path),
        "scene_index": scene.get('index', 0),
        "duration_sec": round(duration, 3),
    }
    if scene_id is not None:
        observer_meta["scene_id"] = str(scene_id)
    if video_id is not None:
        observer_meta["video_id"] = str(video_id)
    cmd = [
        ffmpeg,
        '-hide_banner',
        '-loglevel', 'error',
        '-ss', f'{start:.3f}',
        '-i', str(video_path),
        '-t', f'{duration:.3f}',
        '-ac', '1',
        '-ar', '16000',
        '-vn',
        '-acodec', 'pcm_s16le',
        '-y',
        str(outfile),
    ]
    stop_heartbeat = (lambda: None)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    observer_meta["subprocess_pid"] = int(process.pid)
    if observer:
        observer.step_start(observer_step, metadata=observer_meta)
        stop_heartbeat = observer.begin_heartbeat(observer_step, metadata=observer_meta)
    try:
        stdout_text, stderr_text = process.communicate()
    finally:
        stop_heartbeat()
    result = subprocess.CompletedProcess(
        cmd,
        process.returncode if process.returncode is not None else 1,
        stdout_text or '',
        stderr_text or '',
    )
    if result.returncode != 0:
        # Check if error is due to no audio stream
        if 'does not contain any stream' in result.stderr or 'Stream specifier' in result.stderr:
            # Video has no audio - this is OK, return None
            if observer:
                observer.step_end(observer_step, metadata={**observer_meta, "status": "no_audio_stream"})
            return None
        if observer:
            observer.step_error(
                observer_step,
                error=f"returncode_{result.returncode}",
                metadata=observer_meta,
            )
        raise RuntimeError(f"ffmpeg failed to extract audio chunk: {result.stderr}")
    if not outfile.exists():
        # If no file was created but no error, video likely has no audio
        if observer:
            observer.step_end(observer_step, metadata={**observer_meta, "status": "no_audio_output"})
        return None
    if observer:
        observer.step_end(observer_step, metadata=observer_meta)
    return outfile


def _process_frame(
    cfg_json: Path,
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    frame_dir: Path,
    video_hash: str,
    scene_id: str,
) -> Dict[str, Any]:
    frame_path = _extract_keyframe(
        ffmpeg,
        video_path,
        scene,
        frame_dir,
        scene_id=scene_id,
        video_id=video_hash,
    )
    scene_index = scene.get('index')
    duration = float(scene.get('duration', 0.0) or 0.0)
    start = float(scene.get('start', 0.0) or 0.0)
    frame_timestamp = start + (duration / 2.0) if duration > 0 else start

    item: Dict[str, Any] = {
        'modality': 'image',
        'source_path': str(frame_path),
        'scene_id': scene_id,
        'video_hash': video_hash,
        'video_id': video_hash,
        'scene_index': scene_index,
        'timestamp': frame_timestamp,
        'scene': {
            'start': start,
            'end': start + duration,
            'duration': duration,
        },
    }

    def merge(env_name: str, step_name: str) -> None:
        result = _run_step(env_name, step_name, item, cfg_json)
        if isinstance(result, dict):
            item.update(result)

    merge('goodq_core', 'image_ocr')
    merge('goodq_core', 'image_caption')
    merge('goodq_core', 'object_detect')
    merge('goodq_core', 'face_embed')
    merge('goodq_core', 'image_embed_dino')
    merge('goodq_core', 'image_embed_clip')
    merge('goodq_core', 'tagger')
    canonicalize_taxonomy(item)

    frame_text_parts: List[str] = []
    if isinstance(item.get('ocr_text'), str):
        frame_text_parts.append(item['ocr_text'])
    if isinstance(item.get('caption'), str):
        frame_text_parts.append(item['caption'])
    frame_text = ' '.join(part.strip() for part in frame_text_parts if part).strip()
    if frame_text:
        text_payload = {
            'modality': 'frame_text',
            'source_path': str(frame_path),
            'frame_text': frame_text,
            'scene_id': scene_id,
            'scene_index': scene_index,
            'video_hash': video_hash,
            'video_id': video_hash,
            'ner_entities': item.get('ner_entities'),
            'tags': item.get('tags'),
            'entities': item.get('entities'),
            'location': item.get('location'),
            'locations': item.get('locations'),
            'scene': item.get('scene'),
        }
        text_embed_result = _run_step('goodq_core', 'text_embed', text_payload, cfg_json)
        if isinstance(text_embed_result, dict):
            frame_text_embed_meta = text_embed_result.get('embedding_meta')
            if isinstance(frame_text_embed_meta, dict):
                item['frame_text_embed_meta'] = frame_text_embed_meta
        item['frame_text'] = frame_text

    return {
        'path': str(frame_path),
        'timestamp': frame_timestamp,
        'data': item,
    }


def _process_audio(
    cfg_json: Path,
    ffmpeg: str,
    video_path: Path,
    scene: Dict[str, Any],
    audio_dir: Path,
    audio_artifact_dir: Path,
    video_hash: str,
    scene_id: str,
    audio_runtime_contract: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Process audio for scene - returns None if video has no audio"""
    audio_path = _extract_audio_chunk(
        ffmpeg,
        video_path,
        scene,
        audio_dir,
        scene_id=scene_id,
        video_id=video_hash,
    )
    
    # If no audio was extracted, return None
    if audio_path is None:
        return None
    
    start = float(scene.get('start', 0.0) or 0.0)
    end = float(scene.get('end', start) or start)

    item: Dict[str, Any] = {
        'modality': 'audio',
        'source_path': str(audio_path),
        'scene_id': scene_id,
        'scene_index': scene.get('index'),
        'video_hash': video_hash,
        'video_id': video_hash,
        'scene': {
            'start': start,
            'end': end,
            'duration': end - start,
        },
    }
    contract_selected = 'none'
    contract_reason = 'runtime_contract_unset'
    if isinstance(audio_runtime_contract, dict):
        selected_value = audio_runtime_contract.get('selected')
        if isinstance(selected_value, str) and selected_value.strip().lower() in {'wsl', 'windows', 'none'}:
            contract_selected = selected_value.strip().lower()
        reason_value = audio_runtime_contract.get('reason')
        if isinstance(reason_value, str) and reason_value.strip():
            contract_reason = reason_value.strip()
        else:
            contract_reason = 'runtime_contract_selected'
    item['audio_backend_selected'] = contract_selected
    item['audio_backend_reason'] = contract_reason
    item['audio_backend_effective'] = 'none'
    item['audio_backend_effective_reason'] = 'not_processed'
    step_log_cfg: Optional[Dict[str, Any]] = None

    def _set_effective_backend(backend: str, reason: str) -> None:
        item['audio_backend_effective'] = backend
        item['audio_backend_effective_reason'] = reason

    def _get_step_log_cfg() -> Dict[str, Any]:
        nonlocal step_log_cfg
        if isinstance(step_log_cfg, dict):
            return step_log_cfg
        try:
            step_log_cfg = json.loads(cfg_json.read_text(encoding='utf-8'))
        except Exception as cfg_error:  # noqa: BLE001
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "optional_audio_step.load_step_log_cfg",
                cfg_error,
            )
            step_log_cfg = {}
        return step_log_cfg

    def merge(env_name: str, step_name: str) -> None:
        result = _run_step(env_name, step_name, item, cfg_json)
        if isinstance(result, dict):
            item.update(result)
            # Selected backend is run-contract truth; downstream steps must not mutate it.
            item['audio_backend_selected'] = contract_selected
            item['audio_backend_reason'] = contract_reason

    def record_optional_audio_step_failure(env_name: str, step_name: str, exc: Exception) -> None:
        error_text = str(exc).strip() or type(exc).__name__
        warning_payload = {
            'step': step_name,
            'env': env_name,
            'error': error_text,
        }
        warnings = item.get('audio_step_warnings')
        if not isinstance(warnings, list):
            warnings = []
            item['audio_step_warnings'] = warnings
        warnings.append(warning_payload)
        status_meta_field = {
            'sentiment': 'sentiment_meta',
            'emotion_classify': 'emotion_meta',
            'audio_embed_clap': 'clap_meta',
        }.get(step_name)
        if status_meta_field:
            status_meta = item.get(status_meta_field)
            if not isinstance(status_meta, dict):
                status_meta = {}
            status_meta.update(
                {
                    'status': 'error',
                    'error': error_text,
                }
            )
            item[status_meta_field] = status_meta
        if step_name == 'sentiment':
            item.setdefault('sentiment', None)
        elif step_name == 'emotion_classify':
            item.setdefault('emotions', None)
        logger.warning(
            "[AUDIO] Optional step failed env=%s step=%s scene_id=%s scene_index=%s error=%s",
            env_name,
            step_name,
            scene_id,
            scene.get('index'),
            error_text,
        )
        step_extra: Dict[str, Any] = {
            'reason': 'optional_step_failed',
            'optional': True,
            'env': env_name,
        }
        if step_name == 'audio_embed_clap':
            step_extra['embedding_emitted'] = False
            clap_meta = item.get('clap_meta')
            if isinstance(clap_meta, dict):
                step_extra['result_meta'] = {'clap_meta': clap_meta}
        log_step_run(
            _get_step_log_cfg(),
            step_name,
            item,
            0.0,
            'error',
            error_text,
            extra=step_extra,
        )
        _record_run_warning(
            cfg_json,
            code='optional_audio_step_failed',
            message=error_text,
            context={
                'step': step_name,
                'env': env_name,
                'scene_id': scene_id,
                'scene_index': scene.get('index'),
            },
        )

    def merge_optional_audio_step(env_name: str, step_name: str) -> None:
        try:
            merge(env_name, step_name)
        except Exception as exc:  # noqa: BLE001
            # Transcript-bearing scenes should survive late enrichment failures.
            record_optional_audio_step_failure(env_name, step_name, exc)

    def run_local_audio_fallback(reason: str) -> None:
        logger.info(
            "[AUDIO] WSL2 unified path disabled or unavailable; using local CPU-safe transcription fallback"
        )
        try:
            from steps.audio_transcribe.step import audio_transcribe as local_audio_transcribe

            cfg_payload = json.loads(cfg_json.read_text(encoding='utf-8'))
            local_item = {
                'source_path': str(audio_path),
                'path': str(audio_path),
                'scene_id': scene_id,
                'scene_index': scene.get('index'),
                'video_hash': video_hash,
                'video_id': video_hash,
            }
            local_result = local_audio_transcribe(local_item, cfg_payload)
            if isinstance(local_result, dict):
                item.update(local_result)
                item['audio_backend_selected'] = contract_selected
                item['audio_backend_reason'] = contract_reason
                if not isinstance(item.get('segments'), list):
                    transcript_segments = local_result.get('transcript_segments')
                    if isinstance(transcript_segments, list):
                        item['segments'] = transcript_segments
            has_transcript = isinstance(item.get('transcript'), str) and bool(item.get('transcript', '').strip())
            has_segments = isinstance(item.get('segments'), list) and len(item.get('segments')) > 0
            if has_transcript or has_segments:
                _set_effective_backend('windows', reason)
            else:
                transcript_meta = item.get('transcript_meta') if isinstance(item.get('transcript_meta'), dict) else {}
                unavailable_details: Dict[str, Any] = {'reason': 'no_transcript_output'}
                if transcript_meta:
                    unavailable_details.update(
                        {
                            'status': transcript_meta.get('status'),
                            'engine': transcript_meta.get('engine'),
                            'model': transcript_meta.get('model'),
                            'device': transcript_meta.get('device'),
                        }
                    )
                item['audio_backend_unavailable_details'] = unavailable_details
                logger.warning(
                    "[AUDIO] Windows fallback produced no transcript scene_id=%s status=%s engine=%s",
                    scene_id,
                    unavailable_details.get('status'),
                    unavailable_details.get('engine'),
                )
                _set_effective_backend('none', f'{reason}_no_transcript')
        except Exception as fallback_error:
            logger.warning(
                "[AUDIO] Local CPU-safe transcription fallback failed: %s",
                fallback_error,
            )
            _set_effective_backend('failed', f'{reason}_failed')

    merge('goodq_audio_metadata', 'audio_metadata')
    
    # WSL2 unified audio is profile-gated. BASELINE uses CPU-safe local fallback by default.
    if audio_path and audio_path.exists():
        if contract_selected in {'wsl', 'windows', 'none'}:
            use_wsl_unified_audio = contract_selected == 'wsl'
        else:
            use_wsl_unified_audio = bool(wsl_audio_auto_enabled() or require_wsl_audio())
            if use_wsl_unified_audio and shutil.which('wsl') is None:
                logger.warning(
                    "[AUDIO] WSL2 unified audio requested but wsl command unavailable; using local fallback"
                )
                use_wsl_unified_audio = False

        if use_wsl_unified_audio:
            from steps.audio.audio_wsl2_bridge import audio_unified_wsl2

            # Single unified call gets transcription, diarization, emotion, embeddings
            try:
                unified_result = audio_unified_wsl2(str(audio_path), scene_id=scene_id, duration=end-start)
                if isinstance(unified_result, dict):
                    item.update(unified_result)
                    item['audio_backend_selected'] = contract_selected
                    item['audio_backend_reason'] = contract_reason
                    if str(unified_result.get('status', '')).strip().lower() == 'error':
                        _set_effective_backend('failed', 'wsl_unified_error')
                    else:
                        _set_effective_backend('wsl', 'wsl_unified_success')
            except Exception as unified_error:
                logger.warning(
                    "[AUDIO] WSL2 unified audio failed operation=%s scene_id=%s exc_type=%s exc=%s",
                    "audio_unified_wsl2",
                    scene_id,
                    type(unified_error).__name__,
                    unified_error,
                )
                run_local_audio_fallback('wsl_unified_exception_fallback')
        else:
            if contract_selected == 'windows':
                run_local_audio_fallback('windows_contract_selected')
            elif contract_selected == 'none':
                run_local_audio_fallback('contract_selected_none')
            else:
                run_local_audio_fallback('wsl_disabled_fallback')

        # Legacy steps for speaker merge and timing (keep these for now)
        merge('goodq_audio_transcribe', 'audio_speaker_merge')
        merge('goodq_audio_transcribe', 'audio_music_events')
        merge('goodq_audio_transcribe', 'audio_time_hints')

        # Write compatibility JSON files for harmonizer
        # The harmonizer expects separate transcript.json and diarization.json files
        audio_artifact_dir.mkdir(parents=True, exist_ok=True)

        # Write transcript.json
        if item.get('segments') or item.get('transcript'):
            transcript_json = {
                'segments': item.get('segments', []),
                'full_text': item.get('transcript', ''),
                'language': item.get('language', 'en')
            }
            atomic_write_json(audio_artifact_dir / 'transcript.json', transcript_json)
            logger.info(f"[AUDIO] Wrote transcript.json with {len(item.get('segments', []))} segments")

        # Write diarization.json
        if item.get('speaker_segments'):
            diarization_json = {
                'speakers': item.get('speakers', []),
                'segments': item.get('speaker_segments', [])
            }
            atomic_write_json(audio_artifact_dir / 'diarization.json', diarization_json)
    else:
        logger.info(f"[AUDIO] No audio stream in scene {scene_id}, skipping audio processing")

    merge_optional_audio_step('goodq_core', 'sentiment')
    merge_optional_audio_step('goodq_core', 'emotion_classify')
    merge_optional_audio_step('goodq_core', 'tagger')
    merge_optional_audio_step('goodq_audio_embed', 'audio_embed_clap')

    canonicalize_taxonomy(item)
    transcript = item.get('transcript') if isinstance(item.get('transcript'), str) else ''
    if transcript:
        text_payload = {
            'modality': 'audio_transcript',
            'source_path': str(audio_path),
            'text': transcript,
            'scene_id': scene_id,
            'scene_index': scene.get('index'),
            'video_hash': video_hash,
            'video_id': video_hash,
            'ner_entities': item.get('ner_entities'),
            'tags': item.get('tags'),
            'entities': item.get('entities'),
            'location': item.get('location'),
            'locations': item.get('locations'),
            'emotion': item.get('emotion'),
            'emotion_scores': item.get('emotion_scores') or item.get('emotions'),
            'sentiment': item.get('sentiment'),
            'speaker_count': item.get('speaker_count'),
            'scene': item.get('scene'),
        }
        text_embed_result = _run_step('goodq_core', 'text_embed', text_payload, cfg_json)
        if isinstance(text_embed_result, dict):
            audio_text_embed_meta = text_embed_result.get('embedding_meta')
            if isinstance(audio_text_embed_meta, dict):
                item['audio_text_embed_meta'] = audio_text_embed_meta

    return {
        'path': str(audio_path),
        'start': start,
        'end': end,
        'data': item,
    }


def _detect_scenes(
    cfg_json: Path,
    video_path: Path,
    overrides: Dict[str, Any],
    *,
    video_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'modality': 'video',
        'source_path': str(video_path),
    }
    if video_id:
        payload['video_id'] = str(video_id)
        payload['video_hash'] = str(video_id)
    if overrides:
        payload['scene_detect'] = overrides
    result = _run_step('goodq_video_scene_detect', 'video_scene_detect', payload, cfg_json)
    scenes = result.get('scenes') if isinstance(result, dict) else None
    if not scenes:
        scenes = [{'index': 0, 'start': 0.0, 'end': 0.0, 'duration': 0.0, 'confidence': 1.0}]
    for scene in scenes:
        start = float(scene.get('start', 0.0) or 0.0)
        end = float(scene.get('end', start) or start)
        scene['duration'] = round(max(0.0, end - start), 3)
        scene.setdefault('confidence', 0.5)
    return {
        'scenes': scenes,
        'meta': result.get('scene_meta') if isinstance(result, dict) else {},
    }


@APP.command()
def run(
    input_dir: Optional[Path] = typer.Option(None, help='Directory containing videos to ingest'),
    output: Optional[Path] = typer.Option(None, help='Path to write JSON results'),
    workspace: Optional[Path] = typer.Option(None, help='Workspace directory for artifacts'),
    max_videos: int = typer.Option(0, help='Maximum number of videos to process (0 = all)'),
    max_scenes: int = typer.Option(0, help='Maximum scenes per video (0 = all)'),
    scene_threshold: Optional[float] = typer.Option(None, help='Override PySceneDetect content threshold'),
    min_scene_seconds: Optional[float] = typer.Option(None, help='Minimum scene length in seconds'),
    force_reprocess: bool = typer.Option(False, '--force', '--force-reprocess', help='Force reprocessing even if scenes already exist in database'),
    verbose: bool = typer.Option(False, '--verbose', help='Emit per-step progress messages'),
    step_timeout: Optional[int] = typer.Option(None, '--step-timeout', help='Abort a step if it exceeds this many seconds'),
) -> None:
    global VERBOSE, STEP_TIMEOUT, CONTROL_AGENT_AVAILABLE, _CURRENT_RUN_CONTEXT, _PIPELINE_OBSERVER
    VERBOSE = verbose
    # Ensure step_timeout is an int or None, not an OptionInfo object
    if hasattr(step_timeout, 'default'):
        STEP_TIMEOUT = step_timeout.default
    else:
        STEP_TIMEOUT = step_timeout if isinstance(step_timeout, (int, type(None))) else None

    base_cfg = load_configs({})
    cfg: Dict[str, Any] = dict(base_cfg) if isinstance(base_cfg, dict) else {}
    runtime_paths = get_runtime_paths(cfg, "output_directory")
    input_dir = (input_dir or Path(runtime_paths["import_inbox"])).resolve()
    output = (
        output
        or (Path(runtime_paths["output_directory"]) / "scene_ingest_results.json")
    ).resolve()
    workspace = (
        workspace
        or (Path(runtime_paths["processing"]) / "_workspace" / "scene_ingest")
    ).resolve()

    if not input_dir.exists():
        raise typer.BadParameter(f'Input directory not found: {input_dir}')

    _ensure_dir(workspace)
    baseline_wsl_override = bool(is_baseline() and require_wsl_audio())
    profile_override: Optional[str] = None
    profile_override_reason: Optional[str] = None
    knowledge_graph_status = 'active' if KNOWLEDGE_GRAPH_AVAILABLE else 'disabled_import_failure'
    if baseline_wsl_override:
        logger.warning("BASELINE override: WSL audio forced via GOODQ_REQUIRE_WSL_AUDIO=1")
        profile_override = "wsl_audio_forced_in_baseline"
        profile_override_reason = "GOODQ_REQUIRE_WSL_AUDIO=1 while GOODQ_HOST_PROFILE=BASELINE"
    run_context = {
        'id': str(uuid.uuid4()),
        'pipeline': 'scene_ingest_cli',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'timer_unit': 'ms',
        'healer_retry_count': 0,
        'healer_retry_by_step': {},
        'native_retry_count': 0,
        'native_retry_by_step': {},
        'audio_backend_events': [],
        'control_agent_status': (
            'import_unavailable'
            if not CONTROL_AGENT_AVAILABLE
            else CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT
        ),
        'control_agent_reason': (
            None if not CONTROL_AGENT_AVAILABLE else CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT
        ),
        'knowledge_graph_status': knowledge_graph_status,
        'profile_override': profile_override,
        'profile_override_reason': profile_override_reason,
    }
    try:
        git_proc = subprocess.run(
            ['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=False,
        )
        if git_proc.returncode == 0 and git_proc.stdout.strip():
            run_context['git_sha'] = git_proc.stdout.strip()
    except Exception as e:
        logger.warning(
            "run_ingestion warning context=%s error=%s",
            "git_sha_probe",
            e,
        )
        warnings = run_context.get('warnings')
        if not isinstance(warnings, list):
            warnings = []
            run_context['warnings'] = warnings
        warnings.append(
            {
                'code': 'git_sha_probe_failed',
                'message': str(e),
                'ts_utc': datetime.now(timezone.utc).isoformat(),
            }
        )
    run_id = run_context["id"]
    # Expose run id to in-process helpers so warn-once behavior can be scoped per ingestion run.
    os.environ["GOODQ_RUN_ID"] = run_id
    typer.echo(f"[RUN] run_id: {run_id}")
    existing_run = cfg.get('run') if isinstance(cfg, dict) else None
    if isinstance(existing_run, dict):
        run_copy = dict(existing_run)
        run_copy.update(run_context)
        cfg['run'] = run_copy
    else:
        cfg['run'] = run_context
    if isinstance(cfg.get('run'), dict):
        run_context = cfg['run']
    audio_runtime_contract = _resolve_audio_runtime_contract(cfg)
    run_context['audio_runtime_contract'] = dict(audio_runtime_contract)
    logger.info(
        "[AUDIO] Runtime contract selected=%s reason=%s requested_wsl=%s workspace=%s",
        audio_runtime_contract.get('selected'),
        audio_runtime_contract.get('reason'),
        audio_runtime_contract.get('requested_wsl'),
        audio_runtime_contract.get('wsl_audio_workspace'),
    )
    _CURRENT_RUN_CONTEXT = run_context
    _PIPELINE_OBSERVER = PipelineObserver.from_runtime(run_id=run_id, verbose=verbose)
    observer = _observer()
    if observer:
        observer.step_start(
            "pipeline.ingestion",
            metadata={
                "input_dir": str(input_dir),
                "workspace": str(workspace),
                "output": str(output),
            },
        )
    
    # Add force_reprocess flag to config
    cfg['force_reprocess'] = force_reprocess
    cfg_json = _write_cfg_snapshot(cfg, workspace)

    processing_root = _resolve_processing_root(cfg).resolve()

    ffmpeg = resolve_ffmpeg(cfg) or 'ffmpeg'

    video_patterns = ('*.mp4', '*.mov', '*.mkv', '*.avi', '*.webm')
    videos: List[Path] = []
    for pattern in video_patterns:
        videos.extend(sorted(input_dir.glob(pattern)))
    if not videos:
        typer.echo('No videos found to process.')
        if observer:
            observer.step_end("pipeline.ingestion", metadata={"status": "no_videos"})
        if _PIPELINE_OBSERVER is not None:
            _PIPELINE_OBSERVER.close()
        _PIPELINE_OBSERVER = None
        return
    if max_videos and len(videos) > max_videos:
        videos = videos[:max_videos]

    results: List[Dict[str, Any]] = []

    # Initialize Control Agent if available
    control_agent = None
    control_agent_status = (
        'import_unavailable'
        if not CONTROL_AGENT_AVAILABLE
        else CONTROL_AGENT_STATUS_DISABLED_NO_LLM_CLIENT
    )
    control_agent_reason: Optional[str] = (
        None if not CONTROL_AGENT_AVAILABLE else CONTROL_AGENT_DISABLED_REASON_NO_LLM_CLIENT
    )
    if CONTROL_AGENT_AVAILABLE:
        typer.echo("[CONTROL] Control Agent disabled: no llm_client injection")
        # Prevent downstream auto-healing calls from repeatedly attempting no-client construction.
        CONTROL_AGENT_AVAILABLE = False
        control_agent = None

    run_context['control_agent_status'] = control_agent_status
    run_context['control_agent_reason'] = control_agent_reason
    run_context['knowledge_graph_status'] = knowledge_graph_status
    if isinstance(cfg.get('run'), dict):
        cfg['run']['control_agent_status'] = control_agent_status
        cfg['run']['control_agent_reason'] = control_agent_reason
        cfg['run']['knowledge_graph_status'] = knowledge_graph_status
    cfg_json = _write_cfg_snapshot(cfg, workspace)

    if observer:
        observer.step_start(
            "loop.videos",
            total=len(videos),
            metadata={"input_dir": str(input_dir)},
        )

    for video_num, video_path in enumerate(videos, 1):
        video_hash = _compute_sha256(video_path)
        if observer:
            observer.step_progress(
                "loop.videos",
                current=video_num,
                total=len(videos),
                metadata={"video_path": str(video_path), "video_id": video_hash},
            )
        typer.echo(f'Processing video: {video_path.name}')
        typer.echo(f'  Full path: {video_path}')
        typer.echo(f'  Exists: {video_path.exists()}')
        typer.echo(f'  Size: {video_path.stat().st_size / 1024**2:.2f} MB' if video_path.exists() else '  Size: N/A')
        
        # Initialize progress tracking
        if PROGRESS_TRACKING_AVAILABLE:
            tracker = get_tracker()
            # Estimate total steps: scene detection + processing each scene (image+audio pipeline)
            estimated_steps = 3  # scene detection, scene processing, finalization
            tracker.start_processing(video_path.name, total_steps=estimated_steps, run_id=run_id)
        
        scene_overrides: Dict[str, Any] = {}
        if max_scenes:
            scene_overrides['max_scenes'] = max_scenes
        if scene_threshold is not None:
            scene_overrides['threshold'] = scene_threshold
        if min_scene_seconds is not None:
            scene_overrides['min_scene_len_sec'] = min_scene_seconds

        stored_manifest = list_scenes_for_video(cfg, video_hash)
        force_redetect = cfg.get('force_reprocess', False)
        reuse_scenes = bool(stored_manifest.get('scenes')) and not force_redetect
        
        if force_redetect and stored_manifest.get('scenes'):
            if VERBOSE:
                typer.echo(f'[INFO] Force reprocess enabled - ignoring {len(stored_manifest.get("scenes", []))} stored scenes, will re-detect')
        
        if reuse_scenes:
            stored_scenes = []
            for stored in stored_manifest['scenes']:
                meta = stored.get('meta') or {}
                start = meta.get('start', stored.get('start', 0.0))
                end = meta.get('end', stored.get('end', start))
                scene_entry = {
                    'index': meta.get('index', stored.get('index')),
                    'start': start,
                    'end': end,
                    'duration': meta.get('duration', stored.get('duration', max(0.0, (end or 0.0) - (start or 0.0)))),
                    'confidence': meta.get('confidence', 0.5),
                }
                stored_scenes.append(scene_entry)
            scenes = stored_scenes
            detection_meta = stored_manifest.get('detection_meta') or {}
            if 'scene_manifest_hash' not in detection_meta or not detection_meta['scene_manifest_hash']:
                manifest_hasher = hashlib.sha256()
                for seg in scenes:
                    start = float(seg.get('start', 0.0) or 0.0)
                    end = float(seg.get('end', start) or start)
                    manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
                detection_meta['scene_manifest_hash'] = manifest_hasher.hexdigest()
            detection = {'scenes': scenes, 'meta': detection_meta}
            _log_skipped_steps(
                cfg,
                ['video_scene_detect'],
                modality='video',
                video_hash=video_hash,
                scene_id=None,
                scene_index=None,
                source_path=str(video_path),
                extra={'component': 'scene_detect'},
            )
        else:
            if PROGRESS_TRACKING_AVAILABLE:
                tracker = get_tracker()
                tracker.update_step("Scene Detection", 1, {"scenes_to_detect": "analyzing video"})
            
            detection = _detect_scenes(cfg_json, video_path, scene_overrides, video_id=video_hash)
            scenes = detection.get('scenes', [])
            
            if PROGRESS_TRACKING_AVAILABLE:
                tracker = get_tracker()
                tracker.update_step("Scene Detection Complete", 2, {"scenes_found": len(scenes)})
            
            detection_meta = detection.get('meta') or {}
            manifest_hasher = hashlib.sha256()
            for seg in scenes:
                start = float(seg.get('start', 0.0) or 0.0)
                end = float(seg.get('end', start) or start)
                manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
            detection_meta['scene_manifest_hash'] = manifest_hasher.hexdigest()
            detection['meta'] = detection_meta

        processing_dir = _ensure_dir(processing_root / video_path.stem)
        frame_dir = _ensure_dir(processing_dir / 'video' / 'frames')
        audio_artifact_dir = _ensure_dir(processing_dir / 'audio')
        audio_dir = _ensure_dir(audio_artifact_dir / 'chunks')
        run_context['audio_artifact_dir'] = str(audio_artifact_dir)

        scene_outputs: List[Dict[str, Any]] = []
        empty_duration_threshold_sec = _resolve_content_empty_duration_threshold(cfg)
        total_scenes = len(scenes)
        typer.echo(f'\n=== Processing {total_scenes} scenes for {video_path.name} ===\n')
        scene_loop_step = f"loop.scenes.{video_hash[:12]}"
        if observer:
            observer.step_start(
                scene_loop_step,
                total=total_scenes,
                metadata={"video_path": str(video_path), "video_id": video_hash},
            )
        
        for scene_num, scene in enumerate(scenes, 1):
            scene_start = float(scene.get('start', 0.0) or 0.0)
            scene_end = float(scene.get('end', scene_start) or scene_start)
            scene_index = scene.get('index')
            scene_duration = scene.get('duration', scene_end - scene_start)
            if observer:
                observer.step_progress(
                    scene_loop_step,
                    current=scene_num,
                    total=total_scenes,
                    metadata={
                        "video_path": str(video_path),
                        "video_id": video_hash,
                        "scene_index": scene_index,
                    },
                )
            
            # Progress logging
            typer.echo(f'[Scene {scene_num}/{total_scenes}] Processing scene {scene_index}: {scene_start:.1f}s - {scene_end:.1f}s (duration: {scene_duration:.1f}s)')
            
            meta_payload: Dict[str, Any] = {
                'index': scene_index,
                'duration': scene.get('duration'),
                'confidence': scene.get('confidence'),
            }
            if detection_meta:
                meta_payload['detection'] = detection_meta
            scene_id = ensure_scene(cfg, video_hash, scene_start, scene_end, meta_payload)

            existing_meta = get_scene_meta(cfg, scene_id) or {}
            materialized = scene_has_materialized(cfg, scene_id, ['keyframe', 'audio'])
            frame_info: Optional[Dict[str, Any]] = None
            audio_info: Optional[Dict[str, Any]] = None
            frame_error: Optional[str] = None
            audio_error: Optional[str] = None

            # Check if we should skip based on dedupe (unless force_reprocess is enabled)
            force = cfg.get('force_reprocess', False)
            skip_frame = bool(materialized.get('keyframe')) if isinstance(materialized, dict) and not force else False
            skip_audio = bool(materialized.get('audio')) if isinstance(materialized, dict) and not force else False

            if skip_frame:
                keyframe_meta = existing_meta.get('keyframe')
                if isinstance(keyframe_meta, dict):
                    frame_info = keyframe_meta
                _log_skipped_steps(
                    cfg,
                    IMAGE_PIPELINE_STEPS,
                    modality='image',
                    video_hash=video_hash,
                    scene_id=scene_id,
                    scene_index=scene_index,
                    source_path=(frame_info or {}).get('path'),
                    extra={'component': 'frame'},
                )
                _log_skipped_steps(
                    cfg,
                    ['text_embed'],
                    modality='frame_text',
                    video_hash=video_hash,
                    scene_id=scene_id,
                    scene_index=scene_index,
                    source_path=(frame_info or {}).get('path'),
                    extra={'component': 'frame_text'},
                )
            else:
                # Validate video file exists before extraction
                if not video_path.exists():
                    frame_error = f"Video file not found at {video_path} during frame extraction"
                    typer.echo(f'[ERROR] {frame_error}', err=True)
                else:
                    try:
                        typer.echo(f'  [EXTRACT] Extracting keyframe...')
                        frame_info = _process_frame(cfg_json, ffmpeg, video_path, scene, frame_dir, video_hash, scene_id)
                        typer.echo(f'  [OK] Keyframe processed')
                    except Exception as exc:  # noqa: BLE001
                        frame_error = str(exc)
                        typer.echo(f'[ERROR] Frame extraction failed for scene {scene_index}: {frame_error}', err=True)

            if skip_audio:
                if VERBOSE:
                    typer.echo(f'[DEBUG] Skipping audio (using cached data)')
                audio_meta = existing_meta.get('audio')
                if isinstance(audio_meta, dict):
                    audio_info = audio_meta
                _log_skipped_steps(
                    cfg,
                    AUDIO_PIPELINE_STEPS,
                    modality='audio',
                    video_hash=video_hash,
                    scene_id=scene_id,
                    scene_index=scene_index,
                    source_path=(audio_info or {}).get('path'),
                    extra={'component': 'audio'},
                )
                _log_skipped_steps(
                    cfg,
                    ['text_embed'],
                    modality='audio_transcript',
                    video_hash=video_hash,
                    scene_id=scene_id,
                    scene_index=scene_index,
                    source_path=(audio_info or {}).get('path'),
                    extra={'component': 'audio_transcript'},
                )
            else:
                # Validate video file exists before extraction
                if not video_path.exists():
                    audio_error = f"Video file not found at {video_path} during audio extraction"
                    typer.echo(f'[ERROR] {audio_error}', err=True)
                else:
                    try:
                        if VERBOSE:
                            typer.echo(f'[DEBUG] Processing audio (not skipped, force={force})')
                        typer.echo(f'  [EXTRACT] Extracting audio...')
                        audio_info = _process_audio(
                            cfg_json,
                            ffmpeg,
                            video_path,
                            scene,
                            audio_dir,
                            audio_artifact_dir,
                            video_hash,
                            scene_id,
                            audio_runtime_contract=audio_runtime_contract,
                        )
                        if audio_info is None:
                            typer.echo(f'  [OK] No audio track in video (video-only)')
                        else:
                            audio_data = audio_info.get('data', {}) if isinstance(audio_info, dict) else {}
                            if (
                                isinstance(audio_data, dict)
                                and audio_data.get('wsl2_unified') is True
                                and audio_data.get('status') == 'error'
                            ):
                                typer.echo(
                                    f'  [WARN] WSL2 audio processing failed for scene {scene_index}: {audio_data.get("error") or "Unknown error"}',
                                    err=True,
                                )
                                typer.echo(f'  [OK] Audio extracted')
                            else:
                                typer.echo(f'  [OK] Audio processed')
                            if VERBOSE:
                                typer.echo(f'[DEBUG] audio_info returned with keys: {list(audio_info.keys())}')
                    except Exception as exc:  # noqa: BLE001
                        audio_error = str(exc)
                        wav_path = audio_dir / f"scene_{scene_index:04d}.wav" if isinstance(scene_index, int) else None
                        wav_exists = bool(wav_path and wav_path.exists())
                        wav_size = wav_path.stat().st_size if wav_exists else 0
                        typer.echo(
                            f'[ERROR] Audio processing failed for scene {scene_index} (wav_exists={wav_exists}, wav_size={wav_size}): {audio_error}',
                            err=True,
                        )

            audio_backend_fields = _resolve_audio_backend_attribution(
                audio_info,
                skip_audio=skip_audio,
                audio_error=audio_error,
                audio_runtime_contract=audio_runtime_contract,
                run_context=run_context,
                scene_id=scene_id,
                scene_index=scene_index,
            )
            if isinstance(audio_info, dict):
                audio_info['audio_backend_selected'] = audio_backend_fields['audio_backend_selected']
                audio_info['audio_backend_reason'] = audio_backend_fields['audio_backend_reason']
                audio_info['audio_backend_effective'] = audio_backend_fields['audio_backend_effective']
                audio_info['audio_backend_effective_reason'] = audio_backend_fields['audio_backend_effective_reason']
                audio_info['audio_backend_downgraded'] = bool(audio_backend_fields['audio_backend_downgraded'])
                audio_info['audio_backend_downgrade_reason'] = audio_backend_fields['audio_backend_downgrade_reason']
                audio_info['audio_backend_downgrade_ts'] = audio_backend_fields['audio_backend_downgrade_ts']
                audio_info['audio_backend_downgrade_details'] = dict(
                    audio_backend_fields.get('audio_backend_downgrade_details') or {}
                )
                audio_data_for_backend = audio_info.get('data')
                if isinstance(audio_data_for_backend, dict):
                    audio_data_for_backend['audio_backend_selected'] = audio_backend_fields['audio_backend_selected']
                    audio_data_for_backend['audio_backend_reason'] = audio_backend_fields['audio_backend_reason']
                    audio_data_for_backend['audio_backend_effective'] = audio_backend_fields['audio_backend_effective']
                    audio_data_for_backend['audio_backend_effective_reason'] = audio_backend_fields['audio_backend_effective_reason']
                    audio_data_for_backend['audio_backend_downgraded'] = bool(
                        audio_backend_fields['audio_backend_downgraded']
                    )
                    audio_data_for_backend['audio_backend_downgrade_reason'] = audio_backend_fields[
                        'audio_backend_downgrade_reason'
                    ]
                    audio_data_for_backend['audio_backend_downgrade_ts'] = audio_backend_fields[
                        'audio_backend_downgrade_ts'
                    ]
                    audio_data_for_backend['audio_backend_downgrade_details'] = dict(
                        audio_backend_fields.get('audio_backend_downgrade_details') or {}
                    )

            error_payload = {}
            if frame_error:
                error_payload['frame'] = frame_error
            if audio_error:
                error_payload['audio'] = audio_error

            persist_result = register_scene_bundle(
                cfg,
                video_hash=video_hash,
                scene=scene,
                scene_id=scene_id,
                detection_meta=detection_meta,
                frame=frame_info,
                audio=audio_info,
                errors=error_payload or None,
            )

            # Update knowledge graph in real-time
            if KNOWLEDGE_GRAPH_AVAILABLE and cfg.get('knowledge_graph', {}).get('enabled', True):
                # Extract all data for entity extraction
                frame_data = frame_info.get('data', {}) if frame_info else {}
                # Audio data is nested in 'data' key from _process_audio return
                # DEBUG: Check what audio_info contains
                if VERBOSE:
                    typer.echo(f'[DEBUG] audio_info is None: {audio_info is None}')
                    if audio_info:
                        typer.echo(f'[DEBUG] audio_info keys: {list(audio_info.keys())}')
                        typer.echo(f'[DEBUG] audio_info["data"] type: {type(audio_info.get("data"))}')
                
                audio_data = audio_info.get('data', {}) if audio_info else {}
                
                # DEBUG: Check what audio_data contains
                if VERBOSE:
                    typer.echo(f'[DEBUG] audio_data keys: {list(audio_data.keys())}')
                    typer.echo(f'[DEBUG] has transcript: {bool(audio_data.get("transcript"))}')
                    typer.echo(f'[DEBUG] has full_text: {bool(audio_data.get("full_text"))}')
                    if audio_data.get('transcript'):
                        typer.echo(f'[DEBUG] transcript preview: {str(audio_data.get("transcript"))[:50]}...')
                audio_speaker_ids = _extract_speaker_ids(audio_data)
                merged_entities = []
                for modality_data in (frame_data, audio_data):
                    typed_entities = modality_data.get('ner_entities')
                    fallback_entities = modality_data.get('entities')
                    if isinstance(typed_entities, list) and typed_entities:
                        merged_entities.extend(typed_entities)
                        continue
                    if isinstance(fallback_entities, list):
                        merged_entities.extend(fallback_entities)
                    elif isinstance(fallback_entities, str) and fallback_entities.strip():
                        merged_entities.append(fallback_entities.strip())
                
                kg_scene_data = {
                    'index': scene.get('index'),
                    'start': scene.get('start'),
                    'end': scene.get('end'),
                    # Flatten for entity extractor access
                    'transcript': audio_data.get('transcript') or audio_data.get('full_text'),
                    'caption': frame_data.get('caption'),
                    'ocr_text': frame_data.get('ocr_text'),
                    'objects': frame_data.get('objects'),
                    'faces': frame_data.get('faces'),
                    'tags': frame_data.get('tags'),
                    'entities': merged_entities,
                    'location': frame_data.get('location') or audio_data.get('location'),
                    'locations': frame_data.get('locations') or audio_data.get('locations'),
                    'emotion': audio_data.get('emotion'),
                    'speakers': audio_data.get('speakers'),
                    'speaker_ids': audio_speaker_ids,
                    'speaker_count': audio_data.get('speaker_count', len(audio_speaker_ids)),
                    'speaker_transcript': audio_data.get('speaker_transcript'),
                    'diarization': audio_data.get('diarization'),
                    'music_events': audio_data.get('music_events'),
                    'time_hints': audio_data.get('time_hints') or frame_data.get('time_hints'),
                    # Keep full data for other uses
                    'keyframe': frame_data,
                    'audio': audio_data,
                }
                try:
                    kg_stats = update_kg_for_scene(
                        kg_scene_data,
                        scene_id=scene_id,
                        video_id=video_hash,
                        video_path=str(video_path),
                        cfg=cfg,
                    )
                    if VERBOSE and kg_stats:
                        typer.echo(f'[kg] Scene {scene_index}: {kg_stats.get("entities_resolved", 0)} entities resolved')
                except Exception as kg_error:
                    knowledge_graph_status = 'error_runtime'
                    run_context['knowledge_graph_status'] = knowledge_graph_status
                    if isinstance(cfg.get('run'), dict):
                        cfg['run']['knowledge_graph_status'] = knowledge_graph_status
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "knowledge_graph.scene_update",
                        kg_error,
                    )
                    _record_run_warning(
                        cfg_json,
                        code='knowledge_graph_scene_update_failed',
                        message=str(kg_error),
                        context={'scene_id': scene_id, 'scene_index': scene_index},
                    )
                    if VERBOSE:
                        typer.echo(f'[kg] Warning: KG update failed for scene {scene_index}: {kg_error}')

            scene_record: Dict[str, Any] = {
                'scene_id': scene_id,
                'video_id': video_hash,
                'index': scene.get('index'),
                'start': scene.get('start'),
                'end': scene.get('end'),
                'duration': scene.get('duration'),
                'confidence': scene.get('confidence'),
                'persistence': persist_result,
                'audio_backend_selected': audio_backend_fields['audio_backend_selected'],
                'audio_backend_reason': audio_backend_fields['audio_backend_reason'],
                'audio_backend_effective': audio_backend_fields['audio_backend_effective'],
                'audio_backend_effective_reason': audio_backend_fields['audio_backend_effective_reason'],
                'audio_backend_downgraded': bool(audio_backend_fields['audio_backend_downgraded']),
                'audio_backend_downgrade_reason': audio_backend_fields['audio_backend_downgrade_reason'],
                'audio_backend_downgrade_ts': audio_backend_fields['audio_backend_downgrade_ts'],
                'audio_backend_downgrade_details': dict(
                    audio_backend_fields.get('audio_backend_downgrade_details') or {}
                ),
                'vector_points_attempted': (
                    _coerce_nonnegative_int(persist_result.get('vector_points_attempted'))
                    if isinstance(persist_result, dict)
                    else 0
                ),
                'qdrant_ok': (
                    _resolve_store_status_for_points(
                        persist_result.get('vector_points_attempted'),
                        persist_result.get('qdrant_ok'),
                    )
                    if isinstance(persist_result, dict)
                    else 'not_attempted'
                ),
                'faiss_ok': (
                    _resolve_store_status_for_points(
                        persist_result.get('vector_points_attempted'),
                        persist_result.get('faiss_ok'),
                    )
                    if isinstance(persist_result, dict)
                    else 'not_attempted'
                ),
            }
            if frame_info:
                formatted_frame = _merge_step_output(frame_info)
                if formatted_frame:
                    if 'timestamp' not in formatted_frame:
                        start_val = float(scene.get('start', 0.0) or 0.0)
                        duration_val = float(scene.get('duration', 0.0) or 0.0)
                        formatted_frame['timestamp'] = start_val + (duration_val / 2.0 if duration_val > 0 else start_val)
                    scene_record['keyframe'] = formatted_frame
                else:
                    scene_record['keyframe'] = frame_info
            elif frame_error:
                scene_record['keyframe_error'] = frame_error
            if audio_info:
                formatted_audio = _merge_step_output(audio_info)
                if formatted_audio:
                    audio_start_val = scene_start
                    audio_end_val = scene_end
                    if isinstance(audio_info, dict):
                        if audio_info.get('start') is not None:
                            audio_start_val = float(audio_info.get('start'))
                        if audio_info.get('end') is not None:
                            audio_end_val = float(audio_info.get('end'))
                    formatted_audio.setdefault('start', audio_start_val)
                    formatted_audio.setdefault('end', audio_end_val)
                    formatted_audio.setdefault(
                        'audio_backend_selected',
                        audio_backend_fields['audio_backend_selected'],
                    )
                    formatted_audio.setdefault(
                        'audio_backend_reason',
                        audio_backend_fields['audio_backend_reason'],
                    )
                    formatted_audio.setdefault(
                        'audio_backend_effective',
                        audio_backend_fields['audio_backend_effective'],
                    )
                    formatted_audio.setdefault(
                        'audio_backend_effective_reason',
                        audio_backend_fields['audio_backend_effective_reason'],
                    )
                    formatted_audio.setdefault(
                        'audio_backend_downgraded',
                        bool(audio_backend_fields['audio_backend_downgraded']),
                    )
                    formatted_audio.setdefault(
                        'audio_backend_downgrade_reason',
                        audio_backend_fields['audio_backend_downgrade_reason'],
                    )
                    formatted_audio.setdefault(
                        'audio_backend_downgrade_ts',
                        audio_backend_fields['audio_backend_downgrade_ts'],
                    )
                    formatted_audio.setdefault(
                        'audio_backend_downgrade_details',
                        dict(audio_backend_fields.get('audio_backend_downgrade_details') or {}),
                    )
                    speaker_ids = _extract_speaker_ids(formatted_audio)
                    formatted_audio.setdefault('speaker_ids', speaker_ids)
                    formatted_audio.setdefault('speaker_count', len(speaker_ids))
                    scene_record['audio'] = formatted_audio
                else:
                    scene_record['audio'] = audio_info
            elif audio_error:
                scene_record['audio_error'] = audio_error
            scene_record['speaker_ids'] = _extract_speaker_ids(scene_record.get('audio'))
            if error_payload:
                scene_record['errors'] = error_payload
            scene_record['content_state'] = _classify_scene_content(
                scene_record,
                empty_duration_threshold_sec=empty_duration_threshold_sec,
            )

            scene_outputs.append(scene_record)

        if observer:
            observer.step_end(
                scene_loop_step,
                metadata={
                    "video_path": str(video_path),
                    "video_id": video_hash,
                    "processed_scenes": len(scene_outputs),
                },
            )

        scene_qdrant_status = _aggregate_scene_store_status(scene_outputs, 'qdrant_ok')
        scene_faiss_status = _aggregate_scene_store_status(scene_outputs, 'faiss_ok')
        content_summary = _aggregate_content_summary(scene_outputs)
        run_audio_backend_selected = _aggregate_audio_backend(scene_outputs)
        run_audio_backend_effective = _aggregate_audio_backend(
            scene_outputs,
            field='audio_backend_effective',
        )
        run_audio_backend_downgraded = any(
            bool(scene.get('audio_backend_downgraded'))
            for scene in scene_outputs
            if isinstance(scene, dict)
        )
        phase6_embeddings_result: Optional[Dict[str, Any]] = None
        phase6_qdrant_status: Any = 'not_attempted'
        phase6_faiss_status: Any = 'not_attempted'

        video_result = {
            'video_path': str(video_path),
            'video_hash': video_hash,
            'video_id': video_hash,  # Use video_hash as video_id for consistency
            'video_name': video_path.name,
            'audio_artifact_dir': str(audio_artifact_dir),
            'scene_meta': detection_meta,
            'scenes': scene_outputs,
            'audio_backend_selected': run_audio_backend_selected,
            'audio_backend_effective': run_audio_backend_effective,
            'audio_backend_downgraded': run_audio_backend_downgraded,
            'audio_backend_events': list(run_context.get('audio_backend_events') or []),
            'audio_runtime_contract': audio_runtime_contract,
            'content_summary': content_summary,
            'qdrant_ok': scene_qdrant_status,
            'faiss_ok': scene_faiss_status,
            'control_agent_status': control_agent_status,
            'control_agent_reason': control_agent_reason,
            'knowledge_graph_status': knowledge_graph_status,
        }
        if profile_override:
            video_result['profile_override'] = profile_override
            video_result['profile_override_reason'] = profile_override_reason
        
        # ============================================================
        # PHASE 6: VISUAL EMBEDDINGS + MULTIMODAL HARMONIZATION
        # ============================================================
        phase6_enabled = cfg.get('phase6', {}).get('enabled', True)
        if phase6_enabled and scene_outputs:
            if observer:
                observer.step_start(
                    "phase6.pipeline",
                    total=2,
                    metadata={"video_path": str(video_path), "video_id": video_hash},
                )
            typer.echo(f'\n=== Starting Phase 6: Visual Embeddings & Harmonization ===\n')
            
            # Create phase6_item with required structure
            phase6_item = {
                'id': video_hash,
                'source_path': str(video_path),
                'video_id': video_hash,
                'video_storage_key': video_path.stem,
                'video_path': str(video_path),
                'processing_dir': str(processing_dir),
                'audio_artifact_dir': str(audio_artifact_dir),
                'scene_manifest_path': str(processing_dir / 'video' / 'scene_manifest.json'),
                'scenes': scene_outputs,
                'video_hash': video_hash,
            }
            
            # Write scene_manifest.json for Phase 6 to consume
            scene_manifest = {
                'video_id': video_hash,
                'video_path': str(video_path),
                'scenes': [
                    {
                        'video_id': video_hash,
                        'scene_id': s.get('scene_id'),
                        'index': s.get('index'),
                        'start': s.get('start'),
                        'end': s.get('end'),
                        'duration': s.get('duration'),
                        'confidence': s.get('confidence'),
                        'vector_points_attempted': _coerce_nonnegative_int(s.get('vector_points_attempted')),
                        'qdrant_ok': _resolve_store_status_for_points(
                            s.get('vector_points_attempted'),
                            s.get('qdrant_ok'),
                        ),
                        'faiss_ok': _resolve_store_status_for_points(
                            s.get('vector_points_attempted'),
                            s.get('faiss_ok'),
                        ),
                        'content_state': s.get('content_state', 'signal'),
                        'speaker_ids': (
                            s.get('speaker_ids')
                            if isinstance(s.get('speaker_ids'), list)
                            else _extract_speaker_ids(s.get('audio'))
                        ),
                        'speaker_count': len(
                            s.get('speaker_ids')
                            if isinstance(s.get('speaker_ids'), list)
                            else _extract_speaker_ids(s.get('audio'))
                        ),
                        'keyframe': s.get('keyframe', {}),
                        'audio': s.get('audio', {}),
                    }
                    for s in scene_outputs
                ]
            }
            # Phase 5 writes scene manifest into a canonical /video/ directory
            scene_manifest_path = processing_dir / 'video' / 'scene_manifest.json'
            scene_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(scene_manifest_path, scene_manifest)
            
            try:
                # Phase 6a: Scene Visual Embeddings (CLIP + DINO)
                typer.echo('[PHASE 6a] Generating scene visual embeddings...')
                embeddings_result = _run_step('goodq_core', 'scene_visual_embeddings', phase6_item, cfg_json)
                if observer:
                    observer.step_progress(
                        "phase6.pipeline",
                        current=1,
                        total=2,
                        metadata={
                            "stage": "scene_visual_embeddings",
                            "video_path": str(video_path),
                            "video_id": video_hash,
                        },
                    )
                phase6_status = embeddings_result.get('phase6_status') if isinstance(embeddings_result, dict) else None
                phase6a_success = bool(phase6_status == 'complete')
                result_dict = embeddings_result if isinstance(embeddings_result, dict) else embeddings_result
                print("[STAGE10_16_DEBUG] phase6_status:", phase6_status)
                print("[STAGE10_16_DEBUG] phase6_result:", result_dict)
                if isinstance(embeddings_result, dict):
                    phase6_embeddings_result = embeddings_result
                    phase6_item.update(embeddings_result)
                    phase6_qdrant_status = _normalize_vector_store_status(embeddings_result.get('qdrant_ok'))
                    phase6_faiss_status = _normalize_vector_store_status(embeddings_result.get('faiss_ok'))
                    if phase6_qdrant_status is None:
                        phase6_qdrant_status = 'not_attempted'
                    if phase6_faiss_status is None:
                        phase6_faiss_status = 'not_attempted'
                    video_result['phase6_qdrant_ok'] = phase6_qdrant_status
                    video_result['phase6_faiss_ok'] = phase6_faiss_status
                    if phase6a_success:
                        typer.echo('[PHASE 6a] [PASS] Visual embeddings complete')
                    else:
                        typer.echo('[PHASE 6a] [WARN] Visual embeddings did not complete', err=True)
                else:
                    phase6a_success = False
                    typer.echo('[PHASE 6a] [WARN] Visual embeddings returned non-dict result', err=True)
                
                # Phase 6b: Cross-Modal Harmonization
                typer.echo('[PHASE 6b] Running multimodal harmonization...')
                harmonization_result = _run_step('goodq_core', 'cross_modal_harmonization', phase6_item, cfg_json)
                if observer:
                    observer.step_progress(
                        "phase6.pipeline",
                        current=2,
                        total=2,
                        metadata={
                            "stage": "cross_modal_harmonization",
                            "video_path": str(video_path),
                            "video_id": video_hash,
                        },
                    )
                if isinstance(harmonization_result, dict):
                    phase6_item.update(harmonization_result)
                    
                    # Warn if harmonizer skipped
                    if harmonization_result.get('harmonization_status') == 'skipped':
                        reason = harmonization_result.get('reason', 'unknown')
                        typer.echo(f"[PHASE 6b] [WARN] Harmonization skipped: {reason}", err=True)
                        video_result['phase6_complete'] = False
                        video_result['phase6_skipped'] = True
                        video_result['phase6_skip_reason'] = reason
                    else:
                        # Load temporal index from file if path provided
                        temporal_index_path = harmonization_result.get('temporal_index_path')
                        if temporal_index_path and os.path.exists(temporal_index_path):
                            with open(temporal_index_path, 'r', encoding='utf-8') as f:
                                video_result['temporal_index'] = json.load(f)
                        video_result['temporal_index_path'] = temporal_index_path
                        video_result['phase6_complete'] = bool(phase6a_success)
                        if not phase6a_success:
                            typer.echo('[PHASE 6] [WARN] Harmonization complete but Phase 6a failed; keeping phase6_complete=False', err=True)
                        typer.echo('[PHASE 6b] [PASS] Harmonization complete')
                        
                if observer:
                    observer.step_end(
                        "phase6.pipeline",
                        metadata={
                            "video_path": str(video_path),
                            "video_id": video_hash,
                            "status": "complete",
                        },
                    )
                
            except Exception as phase6_error:
                if observer:
                    observer.step_error(
                        "phase6.pipeline",
                        error=str(phase6_error),
                        metadata={"video_path": str(video_path), "video_id": video_hash},
                    )
                typer.echo(f'[PHASE 6] [FAIL] Phase 6 failed: {phase6_error}', err=True)
                video_result['phase6_error'] = str(phase6_error)
                video_result['phase6_complete'] = False
        else:
            if not phase6_enabled:
                typer.echo('[PHASE 6] Skipped (disabled in config)')
            video_result['phase6_complete'] = False

        video_result['qdrant_ok'] = _merge_store_statuses(scene_qdrant_status, phase6_qdrant_status)
        video_result['faiss_ok'] = _merge_store_statuses(scene_faiss_status, phase6_faiss_status)
        video_result['modality_status'] = _aggregate_modality_status(scene_outputs, phase6_embeddings_result)
        
        results.append(video_result)

    if observer:
        observer.step_end("loop.videos", metadata={"processed_videos": len(results)})

    # Canonical ingestion path writes KG incrementally per scene via update_kg_for_scene().
    # Preserve the legacy end-of-run builder for diagnostics/tests, but do not invoke it here.
    if VERBOSE and KNOWLEDGE_GRAPH_AVAILABLE and cfg.get('knowledge_graph', {}).get('enabled', True):
        typer.echo("[kg] Realtime scene updates are canonical; skipping legacy end-of-run rebuild")

    run_context['knowledge_graph_status'] = knowledge_graph_status
    if isinstance(cfg.get('run'), dict):
        cfg['run']['knowledge_graph_status'] = knowledge_graph_status
    for result in results:
        result['knowledge_graph_status'] = knowledge_graph_status

    # Generate LLM summaries for videos (if enabled)
    llm_config = cfg.get('llm', {})
    if llm_config.get('enabled') and llm_config.get('features', {}).get('video_summarization'):
        if VERBOSE:
            typer.echo('[llm] Generating video summaries...')
        
        try:
            from steps.video_summarizer.step import run_step as run_video_summarizer
            
            for result in results:
                video_hash = result.get('video_hash')
                if video_hash and VERBOSE:
                    typer.echo(f'[llm] Summarizing video {video_hash[:16]}...')
                
                summary_result = run_video_summarizer(cfg, video_hash)
                
                if summary_result.get('success'):
                    result['video_summary'] = summary_result.get('summary')
                    result['video_summary_method'] = summary_result.get('method')
                    if VERBOSE:
                        typer.echo(f'[llm] [OK] Video summary generated ({summary_result.get("method")} method)')
                else:
                    if VERBOSE:
                        typer.echo(f'[llm] [FAIL] Video summary failed: {summary_result.get("error")}')
        except ImportError as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "video_summarizer.import",
                e,
            )
            if VERBOSE:
                typer.echo(f'[llm] Video summarizer not available: {e}')
        except Exception as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "video_summarizer.run",
                e,
            )
            if VERBOSE:
                typer.echo(f'[llm] Video summarization error: {e}')

    # Report errors
    total_scenes = 0
    scenes_with_errors = 0
    frame_errors = 0
    audio_errors = 0
    
    for result in results:
        for scene in result.get('scenes', []):
            total_scenes += 1
            errors = scene.get('errors', {})
            if errors:
                scenes_with_errors += 1
                if 'frame' in errors:
                    frame_errors += 1
                if 'audio' in errors:
                    audio_errors += 1

    def _persist_results_artifact() -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(output, results, indent=2)
        typer.echo(f'Wrote results to {output}')
    
    if scenes_with_errors > 0:
        error_rate = (scenes_with_errors / total_scenes * 100) if total_scenes > 0 else 0
        typer.echo(f'\n[WARNING] Extraction errors occurred:', err=True)
        typer.echo(f'  Total scenes: {total_scenes}', err=True)
        typer.echo(f'  Scenes with errors: {scenes_with_errors} ({error_rate:.1f}%)', err=True)
        typer.echo(f'  Frame extraction errors: {frame_errors}', err=True)
        typer.echo(f'  Audio extraction errors: {audio_errors}', err=True)
        
        # Fail if more than 50% of scenes have errors
        if error_rate > 50:
            typer.echo(f'\n[CRITICAL] Over 50% of scenes failed extraction - this indicates a serious problem!', err=True)
            typer.echo(f'Common causes:', err=True)
            typer.echo(f'  - Video file was deleted or moved during processing', err=True)
            typer.echo(f'  - Incorrect file path', err=True)
            typer.echo(f'  - FFmpeg not available or broken', err=True)
            _persist_results_artifact()
            raise typer.Exit(code=1)

    _persist_results_artifact()
    
    # Generate Control Agent final report (best-effort; non-fatal)
    if control_agent:
        try:
            # Stop monitoring if method exists
            if hasattr(control_agent, 'stop_monitoring'):
                control_agent.stop_monitoring()

            report_path = workspace / "control_agent_report.md"
            try:
                control_agent.generate_report(str(report_path), diagnosis={})
                typer.echo(f"[CONTROL] Final report generated: {report_path}")
            except TypeError:
                # Fallback if signature doesn't match
                control_agent.generate_report(str(report_path))
                typer.echo(f"[CONTROL] Final report generated: {report_path}")

            # Display key insights
            if VERBOSE and hasattr(control_agent, 'get_insights'):
                insights = control_agent.get_insights()
                if insights:
                    typer.echo("\n" + "="*80)
                    typer.echo("[BOT] CONTROL AGENT INSIGHTS")
                    typer.echo("="*80)
                    typer.echo(insights)
                    typer.echo("="*80 + "\n")
        except Exception as e:
            typer.echo(f"[WARNING] Final report generation skipped (non-fatal): {e}", err=True)

    if observer:
        observer.step_end(
            "pipeline.ingestion",
            metadata={"status": "completed", "processed_videos": len(results)},
        )
    if _PIPELINE_OBSERVER is not None:
        _PIPELINE_OBSERVER.close()
    _PIPELINE_OBSERVER = None


if __name__ == '__main__':
    _patch_typer_help_for_click_8_2()
    APP()
