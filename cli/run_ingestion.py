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
from steps.common.config_redaction import redact_config
from steps.common.atomic_io import atomic_write_json
from steps.common.memory import ensure_scene, register_scene_bundle, scene_has_materialized, get_scene_meta, list_scenes_for_video
from steps.common.tag_utils import (
    canonicalize_taxonomy,
    is_valid_entity_token,
    merge_tag_sources,
    normalize_entity_token,
)
from steps.common.tool_paths import resolve_ffmpeg, resolve_conda
from steps.common.step_logger import log_step_run
from steps.common.profile_config import is_baseline, require_wsl_audio, wsl_audio_auto_enabled
from lib.observability.observer import PipelineObserver
from scripts.wsl_audio_preflight import probe_wsl_audio_runtime

_OPTIONAL_DIRECT_ENV_FALLBACK_STEPS = {"sentiment", "audio_embed_clap"}
_PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS = os.name == 'nt'
_SYNTHETIC_SPEAKER_PATTERN = re.compile(r"^(?:speaker|face)_\d+$", re.IGNORECASE)
_SYNTHETIC_IDENTITY_PATTERN = re.compile(r"^(?:unknown(?:_\d+)?|speaker_\d+|face_\d+|person_\d+)$", re.IGNORECASE)


def _is_synthetic_speaker_label(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(_SYNTHETIC_SPEAKER_PATTERN.fullmatch(value.strip()))


def _scoped_synthetic_speaker_name(scope_value: Any, speaker_label: Any) -> Optional[str]:
    if not _is_synthetic_speaker_label(speaker_label):
        return None
    scope_text = str(scope_value or "").strip()
    speaker_text = str(speaker_label or "").strip()
    if not scope_text or not speaker_text:
        return None
    scope_token = re.sub(r"[^A-Za-z0-9_]+", "_", scope_text).strip("_") or "scene"
    speaker_token = re.sub(r"[^A-Za-z0-9_]+", "_", speaker_text).strip("_") or "speaker"
    return f"{scope_token}__{speaker_token.lower()}"


def _resolve_named_person_identity(raw_identity: Any) -> Optional[str]:
    candidate = raw_identity
    if isinstance(raw_identity, dict):
        candidate = (
            raw_identity.get("name")
            or raw_identity.get("identity")
            or raw_identity.get("person")
            or raw_identity.get("speaker_id")
            or raw_identity.get("speaker")
            or raw_identity.get("label")
        )
    if candidate is None:
        return None
    raw_text = str(candidate).strip()
    if not raw_text or _SYNTHETIC_IDENTITY_PATTERN.fullmatch(raw_text):
        return None
    normalized = normalize_entity_token(raw_text)
    if not normalized or _SYNTHETIC_IDENTITY_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _resolve_audio_speaker_identity(raw_speaker: Any) -> Optional[tuple[str, str]]:
    candidate = None
    if isinstance(raw_speaker, dict):
        candidate = (
            raw_speaker.get("name")
            or raw_speaker.get("identity")
            or raw_speaker.get("person")
            or raw_speaker.get("speaker_id")
            or raw_speaker.get("speaker")
            or raw_speaker.get("label")
        )
    else:
        candidate = raw_speaker

    raw_text = str(candidate).strip() if candidate is not None else ""
    if raw_text and _is_synthetic_speaker_label(raw_text):
        return ("speaker", raw_text)

    normalized = _resolve_named_person_identity(candidate)
    if not normalized:
        return None
    return ("person", normalized)


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
    from steps.common.progress_tracker import get_tracker, step_context, update_step, set_total_steps, finish_processing
    PROGRESS_TRACKING_AVAILABLE = True
except ImportError:
    PROGRESS_TRACKING_AVAILABLE = False
    # Compatibility shims keep the runtime CPU-safe when progress tracking is absent.
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
    def set_total_steps(*args, **kwargs):
        pass
    def finish_processing(*args, **kwargs):
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

try:
    from steps.video.entity_extractor import extract_entities_from_scene
    VISION_ENTITY_EXTRACTION_AVAILABLE = True
except ImportError:
    VISION_ENTITY_EXTRACTION_AVAILABLE = False
    logger.warning(
        "run_ingestion warning context=%s error=%s",
        "vision_entity_extractor.import",
        "ImportError",
    )

APP = typer.Typer(help='Scene-first ingestion orchestrator for GoodQ')

def _deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge_dicts(base[key], value)
        else:
            base[key] = value


def _load_runtime_cfg_snapshot(cfg_json: Optional[Path] = None) -> Dict[str, Any]:
    base_cfg = load_configs({})
    if cfg_json and cfg_json.exists():
        try:
            raw = cfg_json.read_text(encoding='utf-8').strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    merged = dict(base_cfg) if isinstance(base_cfg, dict) else {}
                    _deep_merge_dicts(merged, parsed)
                    return merged
        except Exception as e:
            logger.warning(
                "run_ingestion warning context=%s error=%s",
                "runtime_cfg_snapshot",
                e,
            )
    return base_cfg if isinstance(base_cfg, dict) else {}


def _resolve_models_dir(
    cfg: Optional[Dict[str, Any]] = None,
    *,
    cfg_json: Optional[Path] = None,
) -> Path:
    cfg_payload = cfg if isinstance(cfg, dict) else _load_runtime_cfg_snapshot(cfg_json)
    runtime_paths = get_runtime_paths(cfg_payload, "models_cache", require_canonical=False)
    return Path(runtime_paths["models_cache"]).resolve()


def _resolve_processing_root(cfg: Dict[str, Any]) -> Path:
    runtime_paths = get_runtime_paths(cfg, "processing", require_canonical=False)
    return Path(runtime_paths["processing"]).resolve()


def _parse_step_result_json(
    raw: str,
    *,
    step_name: str,
    env_name: str,
    source: str,
) -> Dict[str, Any]:
    payload = raw.strip()
    if not payload:
        return {}
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        preview = payload.splitlines()[0][:200]
        raise RuntimeError(
            f"Step {step_name} returned invalid JSON from {source} ({env_name}): "
            f"{exc.msg} at line {exc.lineno} column {exc.colno}; preview={preview!r}"
        ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(
            f"Step {step_name} returned non-object JSON from {source} ({env_name})"
        )
    return parsed

# Populated by CLI options at runtime
VERBOSE: bool = False
# Timeout per step in seconds - prevents infinite hangs
# Audio steps (diarize, transcribe) can take 5-10 min for long scenes
# Image steps should complete in <30s
DEFAULT_STEP_TIMEOUT: int = 1800
STEP_TIMEOUT: Optional[int] = DEFAULT_STEP_TIMEOUT  # 30 minutes max per step
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


def _resolve_step_timeout_value(step_timeout: Optional[int]) -> Optional[int]:
    if step_timeout is None:
        return DEFAULT_STEP_TIMEOUT
    try:
        parsed = int(step_timeout)
    except (TypeError, ValueError):
        return DEFAULT_STEP_TIMEOUT
    return parsed if parsed > 0 else None


_PHASE6_MANIFEST_TOP_LEVEL_KEYS = (
    'phase6_complete',
    'phase6_status',
    'phase6_error',
    'phase6_vector_commit',
    'embedding_stats',
)
_PHASE6_MANIFEST_SCENE_KEYS = (
    'clip_id',
    'clip_dim',
    'dino_id',
    'dino_dim',
    'frame_count',
    'frame_paths',
    'representative_frame',
)


def _merge_prior_phase6_manifest_state(
    new_manifest: Dict[str, Any],
    existing_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(existing_manifest, dict):
        return new_manifest

    merged = dict(new_manifest)
    for key in _PHASE6_MANIFEST_TOP_LEVEL_KEYS:
        if key in existing_manifest and key not in merged:
            merged[key] = existing_manifest[key]

    new_scenes = merged.get('scenes')
    old_scenes = existing_manifest.get('scenes')
    if not isinstance(new_scenes, list) or not isinstance(old_scenes, list):
        return merged

    prior_by_identity: Dict[tuple[Any, Any], Dict[str, Any]] = {}
    for scene in old_scenes:
        if not isinstance(scene, dict):
            continue
        identity = (scene.get('scene_id'), scene.get('index'))
        prior_by_identity[identity] = scene

    preserved_scenes: List[Dict[str, Any]] = []
    for scene in new_scenes:
        if not isinstance(scene, dict):
            preserved_scenes.append(scene)
            continue
        identity = (scene.get('scene_id'), scene.get('index'))
        prior = prior_by_identity.get(identity)
        if not isinstance(prior, dict):
            preserved_scenes.append(scene)
            continue
        merged_scene = dict(scene)
        for key in _PHASE6_MANIFEST_SCENE_KEYS:
            if key in prior and key not in merged_scene:
                merged_scene[key] = prior[key]
        preserved_scenes.append(merged_scene)

    merged['scenes'] = preserved_scenes
    return merged


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
NATIVE_CRASH_RETRY_STEPS: Set[str] = {'tagger', 'sentiment'}
MAX_NATIVE_STEP_RETRIES: int = 1


def _apply_env_overrides(
    env: Dict[str, str],
    overrides: Optional[Dict[str, Optional[str]]],
) -> Dict[str, str]:
    if not overrides:
        return env
    updated = dict(env)
    for key, value in overrides.items():
        if value is None:
            updated.pop(key, None)
        else:
            updated[key] = value
    return updated


def _resolve_native_retry_strategy(
    step_name: str,
    retry_attempt: int,
) -> tuple[int, Optional[Dict[str, Optional[str]]], Optional[str]]:
    if step_name == 'image_caption':
        if retry_attempt == 1:
            return (
                2,
                {
                    'GOODQ_IMAGE_CAPTION_DISABLE_AMP': '1',
                    'GOODQ_IMAGE_CAPTION_FORCE_CPU': None,
                },
                'gpu_amp_disabled',
            )
        if retry_attempt == 2:
            return (
                2,
                {
                    'GOODQ_IMAGE_CAPTION_DISABLE_AMP': '1',
                    'GOODQ_IMAGE_CAPTION_FORCE_CPU': '1',
                },
                'cpu_fallback',
            )
        return (2, None, None)
    if step_name == 'object_detect':
        if retry_attempt == 1:
            return (
                1,
                {
                    'GOODQ_OBJECT_DETECT_FORCE_CPU': '1',
                },
                'cpu_fallback',
            )
        return (1, None, None)
    if step_name == 'image_embed_dino':
        if retry_attempt == 1:
            return (
                2,
                {
                    'GOODQ_DINO_DISABLE_AMP': '1',
                    'GOODQ_DINO_FORCE_CPU': None,
                },
                'gpu_amp_disabled',
            )
        if retry_attempt == 2:
            return (
                2,
                {
                    'GOODQ_DINO_DISABLE_AMP': '1',
                    'GOODQ_DINO_FORCE_CPU': '1',
                },
                'cpu_fallback',
            )
        return (2, None, None)
    if step_name in NATIVE_CRASH_RETRY_STEPS:
        return (MAX_NATIVE_STEP_RETRIES, None, None)
    return (0, None, None)



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
                face_node_id = kg.add_node('face', f'media_{media_id}_face_{idx}', {'face_detected': True}, timestamp)
                kg.link_node_to_media(face_node_id, media_id, confidence, {'bbox': bbox, 'face_index': idx})

                identity_name = _resolve_named_person_identity(face)
                if identity_name:
                    person_node_id = kg.add_node('person', identity_name, {'face_detected': True}, timestamp)
                    kg.link_node_to_media(person_node_id, media_id, confidence, {'bbox': bbox, 'face_index': idx})
                    kg.add_edge(
                        face_node_id,
                        person_node_id,
                        'identity_evidence',
                        float(confidence),
                        {'source': 'scene_face_detection'},
                    )
    
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
    scene_scope = audio.get('scene_id') or f'media_{media_id}'

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
                speaker_identity = _resolve_audio_speaker_identity(segment)
                text = segment.get('text', '')
                if speaker_identity:
                    node_type, speaker_name = speaker_identity
                    node_name = speaker_name
                    node_props = {'transcript_sample': text[:100]}
                    if node_type == 'speaker':
                        scoped_name = _scoped_synthetic_speaker_name(scene_scope, speaker_name)
                        if scoped_name:
                            node_name = scoped_name
                            node_props['speaker_label'] = speaker_name
                            node_props['scene_id'] = scene_scope
                    entity_id = kg.add_node(node_type, node_name, node_props, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.8, {
                        'start': segment.get('start'),
                        'end': segment.get('end'),
                        'text': text
                    })
                    if node_type == 'person':
                        speaker_node_id = kg.add_node('speaker', speaker_name, {'transcript_sample': text[:100]}, timestamp)
                        kg.link_node_to_media(speaker_node_id, media_id, 0.8, {
                            'start': segment.get('start'),
                            'end': segment.get('end'),
                            'text': text
                        })
                        kg.add_edge(
                            speaker_node_id,
                            entity_id,
                            'identity_evidence',
                            0.8,
                            {'source': 'speaker_transcript'},
                        )
    
    # Fallback: Speaker diarization (if speaker_transcript not available)
    if not speaker_transcript:
        speakers = audio.get('speakers', [])
        if isinstance(speakers, list):
            for speaker in speakers:
                speaker_identity = _resolve_audio_speaker_identity(speaker)
                if speaker_identity:
                    node_type, speaker_name = speaker_identity
                    node_name = speaker_name
                    node_props = {}
                    if node_type == 'speaker':
                        scoped_name = _scoped_synthetic_speaker_name(scene_scope, speaker_name)
                        if scoped_name:
                            node_name = scoped_name
                            node_props['speaker_label'] = speaker_name
                            node_props['scene_id'] = scene_scope
                    entity_id = kg.add_node(node_type, node_name, node_props, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.7)
                    if node_type == 'person':
                        speaker_node_id = kg.add_node('speaker', speaker_name, {}, timestamp)
                        kg.link_node_to_media(speaker_node_id, media_id, 0.7)
                        kg.add_edge(
                            speaker_node_id,
                            entity_id,
                            'identity_evidence',
                            0.7,
                            {'source': 'speaker_ids'},
                        )
    
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


def _promote_metadata_time_hints(audio_payload: Any) -> None:
    if not isinstance(audio_payload, dict):
        return
    if isinstance(audio_payload.get('metadata_time_hints'), dict):
        return
    audio_meta = audio_payload.get('audio_meta')
    if not isinstance(audio_meta, dict):
        return
    tag_time_hints = audio_meta.get('tag_time_hints')
    if isinstance(tag_time_hints, dict):
        audio_payload['metadata_time_hints'] = tag_time_hints


def _time_hints_have_values(time_hints: Any) -> bool:
    if not isinstance(time_hints, dict):
        return False
    for key, value in time_hints.items():
        if str(key).strip().lower() == 'first_seen_ts':
            continue
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _merge_time_hint_dicts(*hint_sources: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for hints in hint_sources:
        if not isinstance(hints, dict):
            continue
        for key, value in hints.items():
            if value in (None, '', []):
                continue
            if isinstance(value, list):
                existing = merged.setdefault(key, [])
                if not isinstance(existing, list):
                    continue
                for item in value:
                    if item not in existing:
                        existing.append(item)
                continue
            if isinstance(value, dict):
                existing_dict = merged.setdefault(key, {})
                if isinstance(existing_dict, dict):
                    existing_dict.update(value)
                continue
            merged[key] = value
    return merged


def _resolve_scene_time_hints(audio_payload: Dict[str, Any], frame_payload: Dict[str, Any]) -> Dict[str, Any]:
    audio_hints = audio_payload.get('time_hints')
    frame_hints = frame_payload.get('time_hints')
    if _time_hints_have_values(audio_hints) and _time_hints_have_values(frame_hints):
        return _merge_time_hint_dicts(audio_hints, frame_hints)
    if _time_hints_have_values(audio_hints):
        return audio_hints
    if _time_hints_have_values(frame_hints):
        return frame_hints
    return audio_hints if isinstance(audio_hints, dict) else {}


def _build_kg_scene_data(
    scene: Dict[str, Any],
    *,
    scene_id: str,
    video_id: str,
    frame_data: Optional[Dict[str, Any]],
    audio_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    frame_payload = frame_data if isinstance(frame_data, dict) else {}
    audio_payload = audio_data if isinstance(audio_data, dict) else {}
    _promote_metadata_time_hints(audio_payload)
    audio_speaker_ids = _extract_speaker_ids(audio_payload)
    merged_entities: List[Any] = []
    for modality_data in (frame_payload, audio_payload):
        typed_entities = modality_data.get('ner_entities')
        fallback_entities = modality_data.get('entities')
        detail_entities = modality_data.get('entity_details')
        if isinstance(typed_entities, list) and typed_entities:
            merged_entities.extend(typed_entities)
        if isinstance(fallback_entities, list):
            merged_entities.extend(fallback_entities)
        elif isinstance(fallback_entities, str) and fallback_entities.strip():
            merged_entities.append(fallback_entities.strip())
        if isinstance(detail_entities, list):
            merged_entities.extend(detail_entities)

    return {
        'scene_id': scene_id,
        'video_id': video_id,
        'index': scene.get('index'),
        'start': scene.get('start'),
        'end': scene.get('end'),
        'transcript': audio_payload.get('transcript') or audio_payload.get('full_text'),
        'caption': frame_payload.get('caption'),
        'ocr_text': frame_payload.get('ocr_text'),
        'objects': frame_payload.get('objects'),
        'faces': frame_payload.get('faces'),
        'tags': frame_payload.get('tags'),
        'entities': merged_entities,
        'location': frame_payload.get('location') or audio_payload.get('location'),
        'locations': frame_payload.get('locations') or audio_payload.get('locations'),
        'emotion': audio_payload.get('emotion'),
        'speakers': audio_payload.get('speakers'),
        'speaker_ids': audio_speaker_ids,
        'speaker_count': audio_payload.get('speaker_count', len(audio_speaker_ids)),
        'speaker_transcript': audio_payload.get('speaker_transcript'),
        'diarization': audio_payload.get('diarization'),
        'speaker_segments': audio_payload.get('speaker_segments'),
        'speaker_voice_signatures': audio_payload.get('speaker_voice_signatures'),
        'speaker_voice_signature_meta': audio_payload.get('speaker_voice_signature_meta'),
        'music_events': audio_payload.get('music_events'),
        'time_hints': _resolve_scene_time_hints(audio_payload, frame_payload),
        'metadata_time_hints': audio_payload.get('metadata_time_hints'),
        'keyframe': frame_payload,
        'audio': audio_payload,
    }


def _persist_frame_semantic_entities(
    item: Dict[str, Any],
    *,
    scene_id: str,
    video_id: str,
) -> None:
    """
    Derive safe, non-object vision semantics from the already-materialized frame payload.

    This persists useful location/person/concept signals into the keyframe payload so
    downstream consumers do not have to wait for Phase 6 harmonization to see them.
    Objects remain in the dedicated object path and are not duplicated here.
    """
    if not VISION_ENTITY_EXTRACTION_AVAILABLE or not isinstance(item, dict):
        return

    scene_data = {
        "keyframe": dict(item),
        "start_time": item.get("timestamp") or 0.0,
    }
    try:
        entity_result = extract_entities_from_scene(
            scene_data=scene_data,
            scene_id=scene_id,
            video_id=video_id,
            config={},
        )
    except Exception as e:
        logger.warning(
            "run_ingestion warning context=%s scene_id=%s video_id=%s error=%s",
            "frame_semantic_entities",
            scene_id,
            video_id,
            e,
        )
        return

    if not isinstance(entity_result, dict):
        return

    raw_entities = entity_result.get("entities")
    if not isinstance(raw_entities, list):
        return

    semantic_labels: List[str] = []
    semantic_details: List[Dict[str, Any]] = []
    location_names: List[str] = []
    location_details: List[Dict[str, Any]] = []

    for entity in raw_entities:
        if not isinstance(entity, dict):
            continue
        name = normalize_entity_token(entity.get("name"))
        entity_type = str(entity.get("entity_type") or "").strip().lower()
        if not name or not entity_type or entity_type == "object":
            continue
        if not is_valid_entity_token(name):
            continue

        confidence_raw = entity.get("confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else 0.7
        except Exception:
            confidence = 0.7
        confidence = max(0.0, min(confidence, 1.0))

        semantic_labels.append(name)
        detail = {
            "label": name,
            "type": entity_type.upper(),
            "score": round(confidence * 10.0, 3),
            "sources": ["vision_semantic"],
        }
        semantic_details.append(detail)
        if entity_type == "location":
            location_names.append(name)
            location_details.append(detail)

    if not semantic_details:
        item.setdefault("vision_semantic_meta", {"status": "ok", "entity_count": 0, "location_count": 0})
        return

    existing_entities = item.get("entities") if isinstance(item.get("entities"), list) else []
    item["entities"] = merge_tag_sources(
        existing_entities,
        semantic_labels,
        validator=is_valid_entity_token,
        normalizer=normalize_entity_token,
    )

    existing_entity_details = item.get("entity_details") if isinstance(item.get("entity_details"), list) else []
    existing_detail_keys = {
        (
            str(detail.get("label") or "").strip().casefold(),
            str(detail.get("type") or "").strip().upper(),
        )
        for detail in existing_entity_details
        if isinstance(detail, dict)
    }
    merged_entity_details: List[Dict[str, Any]] = list(existing_entity_details)
    for detail in semantic_details:
        detail_key = (
            str(detail.get("label") or "").strip().casefold(),
            str(detail.get("type") or "").strip().upper(),
        )
        if detail_key in existing_detail_keys:
            continue
        merged_entity_details.append(detail)
        existing_detail_keys.add(detail_key)
    item["entity_details"] = merged_entity_details

    if location_names:
        existing_locations = item.get("locations") if isinstance(item.get("locations"), list) else []
        item["locations"] = merge_tag_sources(
            existing_locations,
            location_names,
            validator=is_valid_entity_token,
            normalizer=normalize_entity_token,
        )
        if not item.get("location"):
            item["location"] = item["locations"][0]

    item["vision_semantic_entities"] = semantic_details
    item["vision_semantic_meta"] = {
        "status": "ok",
        "entity_count": len(semantic_details),
        "location_count": len(location_details),
    }


def _coerce_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _offset_timestamped_segments(segments: Any, offset: float) -> Any:
    if not isinstance(segments, list) or abs(offset) < 1e-9:
        return segments

    normalized: List[Any] = []
    for segment in segments:
        if not isinstance(segment, dict):
            normalized.append(segment)
            continue
        segment_copy = dict(segment)
        start_val = _coerce_optional_float(segment_copy.get("start"))
        if start_val is not None:
            segment_copy["start"] = start_val + offset
        end_val = _coerce_optional_float(segment_copy.get("end"))
        if end_val is not None:
            segment_copy["end"] = end_val + offset
        if isinstance(segment_copy.get("words"), list):
            segment_copy["words"] = _offset_timestamped_segments(segment_copy["words"], offset)
        if isinstance(segment_copy.get("segments"), list):
            segment_copy["segments"] = _offset_timestamped_segments(segment_copy["segments"], offset)
        normalized.append(segment_copy)
    return normalized


def _offset_local_audio_result_to_scene(result: Any, scene_start: float) -> Any:
    """
    Normalize local transcription output onto the absolute scene timeline.

    The local audio transcription step works on extracted scene chunks, so its
    segment timestamps are scene-relative by construction. Downstream memory and
    harmonization logic align transcript and speaker segments against absolute
    video scene ranges, so translate those local timestamps before they fan out.
    """
    if not isinstance(result, dict) or abs(scene_start) < 1e-9:
        return result

    normalized = dict(result)
    if isinstance(normalized.get("segments"), list):
        normalized["segments"] = _offset_timestamped_segments(normalized["segments"], scene_start)

    transcript_meta = normalized.get("transcript_meta")
    if isinstance(transcript_meta, dict):
        transcript_meta_copy = dict(transcript_meta)
        if isinstance(transcript_meta_copy.get("segments"), list):
            transcript_meta_copy["segments"] = _offset_timestamped_segments(
                transcript_meta_copy["segments"],
                scene_start,
            )
        if isinstance(transcript_meta_copy.get("chunks"), list):
            transcript_meta_copy["chunks"] = _offset_timestamped_segments(
                transcript_meta_copy["chunks"],
                scene_start,
            )
        normalized["transcript_meta"] = transcript_meta_copy

    return normalized


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


def _audio_backend_events_since(
    run_context: Optional[Dict[str, Any]],
    start_index: int,
) -> List[Dict[str, Any]]:
    if not isinstance(run_context, dict):
        return []
    events = run_context.get('audio_backend_events')
    if not isinstance(events, list):
        return []
    start_index = max(0, int(start_index or 0))
    return [dict(event) for event in events[start_index:] if isinstance(event, dict)]


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
    host_cfg = cfg.get('host') if isinstance(cfg, dict) else {}
    cfg_wsl_distro = (
        str(host_cfg.get('wsl_distro')).strip()
        if isinstance(host_cfg, dict) and host_cfg.get('wsl_distro') is not None
        else ''
    )
    explicit_wsl_distro = str(os.environ.get("GOODQ_WSL_DISTRO") or "").strip()
    distro_candidates: List[tuple[str, str]] = []
    seen_distros: Set[str] = set()

    def _add_distro_candidate(source: str, value: str) -> None:
        normalized = str(value or "").strip()
        if not normalized or normalized.lower() in {'auto', 'unset'} or normalized in seen_distros:
            return
        seen_distros.add(normalized)
        distro_candidates.append((source, normalized))

    _add_distro_candidate('env', explicit_wsl_distro)
    _add_distro_candidate('config', cfg_wsl_distro)
    _add_distro_candidate('default', 'Ubuntu')
    primary_distro_source, wsl_distro = distro_candidates[0] if distro_candidates else ('default', 'Ubuntu')
    contract: Dict[str, Any] = {
        'mode': 'auto',
        'requested_wsl': requested_wsl,
        'require_wsl_audio': require_wsl,
        'wsl_command_available': bool(shutil.which('wsl')),
        'wsl_distro': wsl_distro,
        'wsl_distro_source': primary_distro_source,
        'wsl_user': None,
        'wsl_workspace': None,
        'wsl_audio_workspace': None,
        'workspace_ready': False,
        'wsl_runtime_ready': False,
        'wsl_abi_ready': False,
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
    contract['wsl_user'] = wsl_user
    explicit_workspace = str(os.environ.get("GOODQ_WSL_WORKSPACE") or "").strip()
    default_workspace = f"/home/{wsl_user}/goodq_audio"
    workspace_candidates: List[tuple[str, str]] = []
    seen_workspaces: Set[str] = set()

    def _add_workspace_candidate(source: str, value: str) -> None:
        normalized = str(value or "").strip().rstrip("/")
        if not normalized or normalized in seen_workspaces:
            return
        seen_workspaces.add(normalized)
        workspace_candidates.append((source, normalized))

    _add_workspace_candidate('env', explicit_workspace)
    _add_workspace_candidate('config', cfg_wsl_workspace)
    _add_workspace_candidate('default', default_workspace)

    failed_workspaces: List[str] = []
    probe_failures: List[str] = []
    attempted_targets: List[str] = []
    degraded_workspaces: List[str] = []

    for distro_source, candidate_distro in distro_candidates:
        for workspace_source, audio_workspace in workspace_candidates:
            workspace = audio_workspace
            contract['wsl_distro'] = candidate_distro
            contract['wsl_distro_source'] = distro_source
            contract['wsl_workspace'] = workspace
            contract['wsl_audio_workspace'] = audio_workspace
            contract['wsl_workspace_source'] = workspace_source
            attempted_targets.append(f"{candidate_distro}:{audio_workspace}")
            try:
                probe = probe_wsl_audio_runtime(candidate_distro, audio_workspace)
                workspace_ready = bool(probe.get('workspace_ready'))
                runtime_ready = bool(probe.get('runtime_ready'))
                abi_ready = bool(probe.get('abi_ready'))
                contract['workspace_ready'] = workspace_ready
                contract['wsl_runtime_ready'] = runtime_ready
                contract['wsl_abi_ready'] = abi_ready
                contract['wsl_runtime_detail'] = str(probe.get('detail') or '')
                if runtime_ready and abi_ready:
                    contract['selected'] = 'wsl'
                    contract['reason'] = 'wsl_runtime_ready'
                    fallback_notes: List[str] = []
                    if explicit_wsl_distro and distro_source != 'env':
                        fallback_notes.append(
                            f"GOODQ_WSL_DISTRO={explicit_wsl_distro} was unavailable; using {candidate_distro} from {distro_source}."
                        )
                    if explicit_workspace and workspace_source != 'env':
                        fallback_notes.append(
                            f"GOODQ_WSL_WORKSPACE={explicit_workspace} was unavailable; using {audio_workspace} from {workspace_source}."
                        )
                    if fallback_notes:
                        contract['workspace_check_message'] = " ".join(fallback_notes)
                    if wsl_user:
                        os.environ["GOODQ_WSL_USER"] = wsl_user
                    os.environ["GOODQ_WSL_DISTRO"] = candidate_distro
                    os.environ["GOODQ_WSL_WORKSPACE"] = workspace
                    return contract
                if runtime_ready and not abi_ready:
                    degraded_workspaces.append(
                        f"{candidate_distro}:{audio_workspace} ({probe.get('detail') or 'abi degraded'})"
                    )
                    continue
                failed_workspaces.append(
                    f"{candidate_distro}:{audio_workspace} ({probe.get('detail') or 'not ready'})"
                )
            except Exception as e:
                probe_failures.append(f"{candidate_distro}:{audio_workspace}: {e}")

    tried_workspaces = ", ".join(failed_workspaces or attempted_targets)
    if probe_failures:
        message = (
            "WSL workspace preflight failed; "
            f"tried={tried_workspaces}; errors={' | '.join(probe_failures)}"
        )
        if require_wsl:
            raise RuntimeError(message)
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_workspace_preflight_failed'
        contract['workspace_check_message'] = message
        return contract

    if degraded_workspaces:
        message = (
            "WSL workspace is transcription-ready but ABI-degraded; "
            f"tried={', '.join(degraded_workspaces)}. "
            "Canonical ingestion will not select WSL until abi_ready=true."
        )
        if require_wsl:
            raise RuntimeError(message)
        contract['selected'] = 'none'
        contract['reason'] = 'wsl_workspace_abi_degraded'
        contract['workspace_check_message'] = message
        return contract

    message = (
        f"WSL workspace not found, tried={tried_workspaces}. "
        "Set GOODQ_WSL_DISTRO, GOODQ_WSL_USER and GOODQ_WSL_WORKSPACE for deterministic host setup."
    )
    if require_wsl:
        raise RuntimeError(message)
    contract['selected'] = 'none'
    contract['reason'] = 'wsl_workspace_missing'
    contract['workspace_check_message'] = message
    return contract


def _resolve_segmentation_activation(cfg: Dict[str, Any]) -> str:
    env_mode = str(os.getenv("GOODQ_SEGMENTATION_MODE") or "").strip().lower()
    env_backend = str(os.getenv("GOODQ_SEGMENTATION_BACKEND") or "").strip().lower()
    if env_mode == "authoritative" and env_backend in {"seg_p5", "segmentation_phase5"}:
        return "authoritative"
    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict):
        return 'off'
    raw_value = str(segmentation_cfg.get('activation') or 'off').strip().lower()
    if raw_value in {'off', 'shadow', 'authoritative'}:
        return raw_value
    return 'off'


def _resolve_scene_backend_contract(cfg: Dict[str, Any]) -> Dict[str, Any]:
    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    segmentation_enabled = bool(segmentation_cfg.get('enabled', True)) if isinstance(segmentation_cfg, dict) else False
    activation = _resolve_segmentation_activation(cfg)
    env_mode = str(os.getenv("GOODQ_SEGMENTATION_MODE") or "").strip().lower()
    env_backend = str(os.getenv("GOODQ_SEGMENTATION_BACKEND") or "").strip().lower()

    contract: Dict[str, Any] = {
        'segmentation_enabled': segmentation_enabled,
        'segmentation_activation': activation,
        'scene_backend_selected': 'legacy_scene_detect',
        'scene_backend_effective': 'legacy_scene_detect',
        'scene_backend_effective_reason': 'legacy_scene_detect_default',
        'authoritative_cutover_supported': False,
    }

    if not segmentation_enabled:
        contract['scene_backend_effective_reason'] = 'segmentation_config_disabled'
        return contract

    if env_mode == 'authoritative' and env_backend in {'seg_p5', 'segmentation_phase5'}:
        contract['scene_backend_selected'] = 'segmentation_phase5'
        contract['scene_backend_effective'] = 'segmentation_phase5'
        contract['scene_backend_effective_reason'] = 'segmentation_authoritative_env_override'
        contract['authoritative_cutover_supported'] = True
        return contract

    if activation == 'shadow':
        contract['scene_backend_selected'] = 'segmentation_phase5_shadow_compare'
        contract['scene_backend_effective_reason'] = 'segmentation_shadow_compare_legacy_authority'
        return contract

    if activation == 'authoritative':
        contract['scene_backend_selected'] = 'segmentation_phase5'
        contract['scene_backend_effective_reason'] = 'segmentation_authoritative_not_enabled'
        return contract

    return contract


def _resolve_scene_backend_dispatch(scene_backend_contract: Dict[str, Any]) -> Dict[str, str]:
    effective_backend = str(scene_backend_contract.get('scene_backend_effective') or 'legacy_scene_detect').strip().lower()
    if effective_backend == 'segmentation_phase5':
        return {
            'env_name': 'goodq_core',
            'step_name': 'video_scene_segmentation',
        }
    return {
        'env_name': 'goodq_video_scene_detect',
        'step_name': 'video_scene_detect',
    }


def _run_segmentation_authoritative_scene_backend(
    video_path: Path,
    processing_dir: Path,
    cfg: Dict[str, Any],
    *,
    scene_backend_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    contract = scene_backend_contract if isinstance(scene_backend_contract, dict) else {
        'scene_backend_selected': 'segmentation_phase5',
        'scene_backend_effective': 'segmentation_phase5',
        'scene_backend_effective_reason': 'segmentation_authoritative_env_override',
    }

    from steps.audio.segmentation import PhasedSegmentationEngine

    authoritative_root = processing_dir / "_segmentation_authoritative"
    engine = PhasedSegmentationEngine(cfg)
    run_result = engine.run_full_pipeline(
        str(video_path),
        str(authoritative_root),
        skip_phases=['phase4', 'phase6'],
    )

    phase_results = run_result.get('phase_results') if isinstance(run_result, dict) else {}
    phase5_result = phase_results.get('phase5') if isinstance(phase_results, dict) else {}
    scene_manifest_path = phase5_result.get('scene_manifest_path') if isinstance(phase5_result, dict) else None
    scene_manifest = _safe_read_json_dict(scene_manifest_path)
    raw_scenes = scene_manifest.get('scenes') if isinstance(scene_manifest, dict) else None
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise RuntimeError("SEG_P5 authoritative cutover produced no scene manifest scenes")

    scenes: List[Dict[str, Any]] = []
    manifest_hasher = hashlib.sha256()
    for idx, raw_scene in enumerate(raw_scenes):
        if not isinstance(raw_scene, dict):
            continue
        start = float(raw_scene.get('start', 0.0) or 0.0)
        end = float(raw_scene.get('end', start) or start)
        duration = round(max(0.0, end - start), 3)
        manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
        scenes.append(
            {
                'index': int(raw_scene.get('index', idx) or idx),
                'start': start,
                'end': end,
                'duration': duration,
                'confidence': float(raw_scene.get('confidence', 0.5) or 0.5),
            }
        )

    if not scenes:
        raise RuntimeError("SEG_P5 authoritative cutover produced no usable scenes")

    return {
        'scenes': scenes,
        'meta': {
            'status': 'ok',
            'engine': 'segmentation_phase5',
            'scene_count': len(scenes),
            'scene_manifest_path': scene_manifest_path,
            'scene_manifest_hash': manifest_hasher.hexdigest(),
            'orchestration': {
                'scene_backend_selected': contract.get('scene_backend_selected'),
                'scene_backend_effective': contract.get('scene_backend_effective'),
                'scene_backend_effective_reason': contract.get('scene_backend_effective_reason'),
                'step_env': 'goodq_core',
                'step_name': 'segmentation_phase5_authoritative',
            },
        },
    }


def _resolve_phase6_audio_source_contract(
    cfg: Dict[str, Any],
    segmentation_shadow_overlay: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    overlay_requested = _segmentation_shadow_audio_overlay_enabled(cfg)
    contract: Dict[str, Any] = {
        'phase6_audio_source_selected': 'segmentation_shadow_audio_overlay' if overlay_requested else 'live_audio_artifacts',
        'phase6_audio_source_effective': 'live_audio_artifacts',
        'phase6_audio_source_effective_reason': 'live_audio_artifacts_default',
    }

    if not overlay_requested:
        return contract

    if isinstance(segmentation_shadow_overlay, dict) and segmentation_shadow_overlay.get('enabled'):
        contract['phase6_audio_source_effective'] = 'segmentation_shadow_audio_overlay'
        contract['phase6_audio_source_effective_reason'] = str(
            segmentation_shadow_overlay.get('reason') or 'segmentation_shadow_audio_overlay_ready'
        )
        return contract

    if isinstance(segmentation_shadow_overlay, dict):
        contract['phase6_audio_source_effective_reason'] = str(
            segmentation_shadow_overlay.get('reason') or 'segmentation_shadow_audio_overlay_not_ready'
        )
    else:
        contract['phase6_audio_source_effective_reason'] = 'segmentation_shadow_audio_overlay_not_resolved'
    return contract


def _resolve_ingest_orchestration_contract(
    cfg: Dict[str, Any],
    *,
    audio_runtime_contract: Optional[Dict[str, Any]] = None,
    segmentation_shadow: Optional[Dict[str, Any]] = None,
    segmentation_shadow_overlay: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scene_backend = _resolve_scene_backend_contract(cfg)
    phase6_audio_source = _resolve_phase6_audio_source_contract(cfg, segmentation_shadow_overlay)
    audio_backend = str((audio_runtime_contract or {}).get('selected') or 'none').strip().lower() or 'none'
    shadow_status = str((segmentation_shadow or {}).get('status') or '').strip().lower()
    shadow_reason = str((segmentation_shadow or {}).get('reason') or '').strip().lower()

    return {
        'version': 1,
        'execution_owner': 'cli.run_ingestion',
        'step_execution_owner': 'cli.step_runner',
        'persistence_owner': 'steps.common.memory',
        'persistence_functions': [
            'ensure_scene',
            'scene_has_materialized',
            'register_scene_bundle',
        ],
        'phase6_owner': 'live_phase6',
        'segmentation_activation': scene_backend['segmentation_activation'],
        'segmentation_enabled': scene_backend['segmentation_enabled'],
        'scene_backend_selected': scene_backend['scene_backend_selected'],
        'scene_backend_effective': scene_backend['scene_backend_effective'],
        'scene_backend_effective_reason': scene_backend['scene_backend_effective_reason'],
        'phase6_audio_source_selected': phase6_audio_source['phase6_audio_source_selected'],
        'phase6_audio_source_effective': phase6_audio_source['phase6_audio_source_effective'],
        'phase6_audio_source_effective_reason': phase6_audio_source['phase6_audio_source_effective_reason'],
        'audio_runtime_backend': audio_backend,
        'segmentation_shadow_status': shadow_status or 'not_run',
        'segmentation_shadow_reason': shadow_reason or 'not_run',
        'authoritative_cutover_supported': bool(scene_backend['authoritative_cutover_supported']),
    }


def _safe_read_json_dict(path_value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(path_value, (str, Path)):
        return None
    try:
        path = Path(path_value)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else None
    except Exception as e:
        logger.debug(
            "run_ingestion warning context=%s error=%s",
            "segmentation_shadow.read_json",
            e,
        )
        return None


def _rehydrate_video_result_scenes_from_manifest(
    video_result: Dict[str, Any],
    scene_manifest_path: Any,
) -> bool:
    manifest = _safe_read_json_dict(scene_manifest_path)
    raw_scenes = manifest.get('scenes') if isinstance(manifest, dict) else None
    if not isinstance(raw_scenes, list):
        return False
    canonical_scenes: List[Dict[str, Any]] = []
    for scene in raw_scenes:
        if not isinstance(scene, dict):
            continue
        projected_scene = dict(scene)
        scene_context_llm = scene.get('scene_context_llm')
        if isinstance(scene_context_llm, dict):
            projected_scene.setdefault('summary', scene_context_llm.get('narrative_summary'))
            projected_scene.setdefault('tags', scene_context_llm.get('context_tags'))
            projected_scene.setdefault('key_moments', scene_context_llm.get('key_moments'))
        canonical_scenes.append(projected_scene)
    if not canonical_scenes:
        return False
    video_result['scenes'] = canonical_scenes
    return True


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _segment_has_transcript(segment: Any) -> bool:
    if not isinstance(segment, dict):
        return False
    transcript = segment.get('transcript')
    if isinstance(transcript, str) and transcript.strip():
        return True
    transcript_segments = segment.get('transcript_segments')
    if isinstance(transcript_segments, list):
        return _has_meaningful_audio_segments(
            [item for item in transcript_segments if isinstance(item, dict)]
        )
    words = segment.get('words')
    if isinstance(words, list):
        return any(
            isinstance(word, dict) and isinstance(word.get('word'), str) and word.get('word', '').strip()
            for word in words
        )
    return False


def _extract_segment_speaker_ids(segment: Any) -> List[str]:
    if not isinstance(segment, dict):
        return []
    speaker_ids: List[str] = []

    def _append(raw: Any) -> None:
        if not isinstance(raw, str):
            return
        speaker = raw.strip()
        if speaker and speaker not in speaker_ids:
            speaker_ids.append(speaker)

    for key in ('primary_speaker', 'speaker'):
        _append(segment.get(key))

    speakers = segment.get('speakers')
    if isinstance(speakers, list):
        for speaker in speakers:
            if isinstance(speaker, str):
                _append(speaker)
            elif isinstance(speaker, dict):
                _append(speaker.get('speaker_id') or speaker.get('speaker') or speaker.get('label'))

    diarization = segment.get('diarization')
    if isinstance(diarization, list):
        for item in diarization:
            if isinstance(item, dict):
                _append(item.get('speaker'))

    return speaker_ids


def _compute_scene_coverages(scene_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    scenes = [scene for scene in scene_outputs if isinstance(scene, dict)]
    total = len(scenes)
    transcript_scene_count = 0
    speaker_scene_count = 0

    for scene in scenes:
        audio_payload = _extract_audio_payload(scene)
        transcript_text = _extract_transcript_text(audio_payload)
        segments = _extract_segments(audio_payload)
        if transcript_text or _has_meaningful_audio_segments(segments):
            transcript_scene_count += 1
        if _extract_speaker_ids(audio_payload):
            speaker_scene_count += 1

    return {
        'scene_count': total,
        'transcript_scene_count': transcript_scene_count,
        'speaker_scene_count': speaker_scene_count,
        'transcript_coverage': _ratio(transcript_scene_count, total),
        'speaker_coverage': _ratio(speaker_scene_count, total),
    }


def _compute_segment_coverages(segments: Any) -> Dict[str, Any]:
    normalized = [segment for segment in segments if isinstance(segment, dict)] if isinstance(segments, list) else []
    total = len(normalized)
    transcript_segment_count = 0
    speaker_segment_count = 0

    for segment in normalized:
        if _segment_has_transcript(segment):
            transcript_segment_count += 1
        if _extract_segment_speaker_ids(segment):
            speaker_segment_count += 1

    return {
        'segment_count': total,
        'transcript_segment_count': transcript_segment_count,
        'speaker_segment_count': speaker_segment_count,
        'transcript_coverage': _ratio(transcript_segment_count, total),
        'speaker_coverage': _ratio(speaker_segment_count, total),
    }


def _compute_temporal_index_completeness(temporal_index: Optional[Dict[str, Any]]) -> float:
    if not isinstance(temporal_index, dict):
        return 0.0
    checks = [
        isinstance(temporal_index.get('segments'), list),
        temporal_index.get('total_scenes') is not None,
        'has_audio' in temporal_index,
        'has_transcripts' in temporal_index,
        'phase5_complete' in temporal_index,
        'phase6_complete' in temporal_index,
        'phase6_harmonized' in temporal_index,
    ]
    return _ratio(sum(1 for check in checks if check), len(checks))


def _compute_shadow_alignment_score(scene_manifest: Optional[Dict[str, Any]]) -> float:
    if not isinstance(scene_manifest, dict):
        return 0.0
    aligned_segments = scene_manifest.get('aligned_segments')
    if not isinstance(aligned_segments, list) or not aligned_segments:
        return 0.0
    aligned_count = 0
    for segment in aligned_segments:
        if not isinstance(segment, dict):
            continue
        if bool(segment.get('scene_aligned')) or int(segment.get('scene_count') or 0) > 0:
            aligned_count += 1
    return _ratio(aligned_count, len(aligned_segments))


def _normalize_scene_boundaries(raw_scenes: Any) -> List[Dict[str, float]]:
    normalized: List[Dict[str, float]] = []
    scenes = raw_scenes
    if isinstance(raw_scenes, dict):
        scenes = raw_scenes.get('scenes')
    if not isinstance(scenes, list):
        return normalized
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        start = _coerce_optional_float(scene.get('start'))
        end = _coerce_optional_float(scene.get('end'))
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        normalized.append(
            {
                'start': float(start),
                'end': float(end),
                'duration': max(0.0, float(end) - float(start)),
            }
        )
    return normalized


def _scene_overlap_duration(left: Dict[str, float], right: Dict[str, float]) -> float:
    return max(0.0, min(float(left['end']), float(right['end'])) - max(float(left['start']), float(right['start'])))


def _compute_scene_backend_comparison(
    scene_outputs: List[Dict[str, Any]],
    shadow_scene_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    live_scenes = _normalize_scene_boundaries(scene_outputs)
    shadow_scenes = _normalize_scene_boundaries(shadow_scene_manifest)

    claimed_shadow: Set[int] = set()
    matched_count = 0
    overlap_duration_total = 0.0
    boundary_deltas: List[float] = []

    for live_scene in live_scenes:
        best_idx: Optional[int] = None
        best_overlap = 0.0
        for idx, shadow_scene in enumerate(shadow_scenes):
            if idx in claimed_shadow:
                continue
            overlap = _scene_overlap_duration(live_scene, shadow_scene)
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = idx
        if best_idx is None or best_overlap <= 0.0:
            continue
        claimed_shadow.add(best_idx)
        matched_count += 1
        overlap_duration_total += best_overlap
        shadow_scene = shadow_scenes[best_idx]
        boundary_deltas.append(
            (
                abs(float(live_scene['start']) - float(shadow_scene['start']))
                + abs(float(live_scene['end']) - float(shadow_scene['end']))
            ) / 2.0
        )

    total_live_duration = sum(float(scene['duration']) for scene in live_scenes)
    boundary_delta_mean = sum(boundary_deltas) / len(boundary_deltas) if boundary_deltas else 0.0
    boundary_delta_max = max(boundary_deltas) if boundary_deltas else 0.0

    return {
        'live_scene_count': len(live_scenes),
        'shadow_scene_count': len(shadow_scenes),
        'matched_scene_count': matched_count,
        'matched_scene_ratio_live': _ratio(matched_count, len(live_scenes)),
        'matched_scene_ratio_shadow': _ratio(len(claimed_shadow), len(shadow_scenes)),
        'duration_coverage': _ratio(int(overlap_duration_total * 1000), int(total_live_duration * 1000)) if total_live_duration > 0 else 0.0,
        'boundary_delta_mean_sec': boundary_delta_mean,
        'boundary_delta_max_sec': boundary_delta_max,
    }


def _compute_shadow_temporal_readiness(
    shadow_result: Dict[str, Any],
    segmentation_manifest: Optional[Dict[str, Any]],
    scene_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(segmentation_manifest, dict):
        checks = {
            'segments': isinstance(segmentation_manifest.get('segments'), list),
            'frame_index': isinstance(segmentation_manifest.get('frame_index'), list),
            'summary': isinstance(segmentation_manifest.get('summary'), dict),
            'processing': isinstance(segmentation_manifest.get('processing'), dict),
            'source': isinstance(segmentation_manifest.get('source'), dict),
        }
        score = _ratio(sum(1 for passed in checks.values() if passed), len(checks))
        return {
            'score': score,
            'basis': 'shadow_segmentation_manifest',
            'checks': checks,
        }

    skip_phases = shadow_result.get('skip_phases')
    checks = {
        'audio_manifest': bool(shadow_result.get('audio_manifest_path')),
        'scene_manifest': isinstance(scene_manifest, dict),
        'phase4_manifest': bool(shadow_result.get('phase4_manifest_path')),
        'phase6_manifest': bool(shadow_result.get('segmentation_manifest_path')),
        'validation': isinstance(shadow_result.get('validation'), dict),
        'phase6_requested': 'phase6' not in skip_phases if isinstance(skip_phases, list) else True,
    }
    score = _ratio(sum(1 for passed in checks.values() if passed), len(checks))
    return {
        'score': score,
        'basis': 'shadow_temporal_readiness',
        'checks': checks,
    }


def _build_segmentation_shadow_metrics(
    scene_outputs: List[Dict[str, Any]],
    temporal_index: Optional[Dict[str, Any]],
    shadow_result: Dict[str, Any],
) -> Dict[str, Any]:
    current = _compute_scene_coverages(scene_outputs)
    current_temporal_completeness = _compute_temporal_index_completeness(temporal_index)

    shadow_scene_manifest = _safe_read_json_dict(shadow_result.get('scene_manifest_path'))
    shadow_segmentation_manifest = _safe_read_json_dict(shadow_result.get('segmentation_manifest_path'))
    shadow_phase4_manifest = _safe_read_json_dict(shadow_result.get('phase4_manifest_path'))

    shadow_scene_count = 0
    if isinstance(shadow_scene_manifest, dict):
        if shadow_scene_manifest.get('total_scenes') is not None:
            try:
                shadow_scene_count = int(shadow_scene_manifest.get('total_scenes') or 0)
            except (TypeError, ValueError):
                shadow_scene_count = 0
        elif isinstance(shadow_scene_manifest.get('scenes'), list):
            shadow_scene_count = len(shadow_scene_manifest.get('scenes') or [])

    shadow_validation = shadow_result.get('validation') if isinstance(shadow_result.get('validation'), dict) else {}
    shadow_validation_stats = shadow_validation.get('stats') if isinstance(shadow_validation, dict) else {}

    if isinstance(shadow_validation_stats, dict):
        shadow_transcript_coverage = float(shadow_validation_stats.get('transcript_coverage') or 0.0)
        shadow_speaker_coverage = float(shadow_validation_stats.get('speaker_coverage') or 0.0)
        shadow_segment_count = int(shadow_validation_stats.get('total_segments') or 0)
    else:
        shadow_segments = None
        if isinstance(shadow_segmentation_manifest, dict):
            shadow_segments = shadow_segmentation_manifest.get('segments')
        if shadow_segments is None and isinstance(shadow_phase4_manifest, dict):
            shadow_segments = shadow_phase4_manifest.get('segments') or shadow_phase4_manifest.get('chunks')
        shadow_coverages = _compute_segment_coverages(shadow_segments)
        shadow_transcript_coverage = float(shadow_coverages['transcript_coverage'])
        shadow_speaker_coverage = float(shadow_coverages['speaker_coverage'])
        shadow_segment_count = int(shadow_coverages['segment_count'])

    shadow_alignment_score = _compute_shadow_alignment_score(shadow_scene_manifest)
    scene_backend_comparison = _compute_scene_backend_comparison(scene_outputs, shadow_scene_manifest)
    shadow_temporal = _compute_shadow_temporal_readiness(
        shadow_result,
        shadow_segmentation_manifest,
        shadow_scene_manifest,
    )
    shadow_temporal_completeness = float(shadow_temporal['score'])

    return {
        'version': 1,
        'activation': shadow_result.get('activation'),
        'status': shadow_result.get('status'),
        'scene_count_current': current['scene_count'],
        'scene_count_shadow': shadow_scene_count,
        'scene_count_delta': shadow_scene_count - current['scene_count'],
        'transcript_coverage_current': current['transcript_coverage'],
        'transcript_coverage_shadow': shadow_transcript_coverage,
        'transcript_coverage_delta': shadow_transcript_coverage - current['transcript_coverage'],
        'speaker_coverage_current': current['speaker_coverage'],
        'speaker_coverage_shadow': shadow_speaker_coverage,
        'speaker_coverage_delta': shadow_speaker_coverage - current['speaker_coverage'],
        'alignment_score': shadow_alignment_score,
        'scene_backend_match_ratio_live': scene_backend_comparison['matched_scene_ratio_live'],
        'scene_backend_match_ratio_shadow': scene_backend_comparison['matched_scene_ratio_shadow'],
        'scene_backend_duration_coverage': scene_backend_comparison['duration_coverage'],
        'scene_backend_boundary_delta_mean_sec': scene_backend_comparison['boundary_delta_mean_sec'],
        'temporal_index_completeness_current': current_temporal_completeness,
        'temporal_index_completeness_shadow': shadow_temporal_completeness,
        'temporal_index_completeness_delta': shadow_temporal_completeness - current_temporal_completeness,
        'temporal_index_completeness_basis': shadow_temporal.get('basis'),
        'current': {
            **current,
            'temporal_index_completeness': current_temporal_completeness,
        },
        'shadow': {
            'scene_count': shadow_scene_count,
            'segment_count': shadow_segment_count,
            'transcript_coverage': shadow_transcript_coverage,
            'speaker_coverage': shadow_speaker_coverage,
            'alignment_score': shadow_alignment_score,
            'scene_backend_comparison': scene_backend_comparison,
            'temporal_index_completeness': shadow_temporal_completeness,
            'temporal_index_completeness_checks': shadow_temporal.get('checks'),
        },
        'files': {
            'summary_path': shadow_result.get('summary_path'),
            'audio_manifest_path': shadow_result.get('audio_manifest_path'),
            'phase4_manifest_path': shadow_result.get('phase4_manifest_path'),
            'scene_manifest_path': shadow_result.get('scene_manifest_path'),
            'segmentation_manifest_path': shadow_result.get('segmentation_manifest_path'),
        },
    }


def _attach_segmentation_shadow_metrics(
    cfg: Dict[str, Any],
    scene_outputs: List[Dict[str, Any]],
    temporal_index: Optional[Dict[str, Any]],
    shadow_result: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(shadow_result, dict):
        return shadow_result
    if shadow_result.get('status') not in {'complete', 'partial'}:
        return shadow_result

    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict) or not segmentation_cfg.get('metrics_output', True):
        return shadow_result

    summary_path = shadow_result.get('summary_path')
    if not isinstance(summary_path, str) or not summary_path.strip():
        return shadow_result

    metrics = _build_segmentation_shadow_metrics(scene_outputs, temporal_index, shadow_result)
    metrics_path = Path(summary_path).parent / 'shadow_metrics.json'
    atomic_write_json(metrics_path, metrics)

    updated = dict(shadow_result)
    updated['metrics'] = metrics
    updated['metrics_path'] = str(metrics_path)
    return updated


def _segmentation_shadow_audio_overlay_enabled(cfg: Dict[str, Any]) -> bool:
    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict):
        return False
    return _resolve_segmentation_activation(cfg) == 'shadow' and bool(
        segmentation_cfg.get('shadow_audio_overlay', False)
    )


def _prepare_segmentation_shadow_audio_overlay(
    cfg: Dict[str, Any],
    shadow_result: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'enabled': False,
        'reason': 'segmentation_shadow_audio_overlay_disabled',
    }
    if not _segmentation_shadow_audio_overlay_enabled(cfg):
        return result
    if not isinstance(shadow_result, dict):
        return result
    if shadow_result.get('status') != 'complete':
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_requires_complete_shadow_run',
        }

    summary_path = shadow_result.get('summary_path')
    phase4_manifest_path = shadow_result.get('phase4_manifest_path')
    if not isinstance(summary_path, str) or not summary_path.strip():
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_missing_summary',
        }
    if not isinstance(phase4_manifest_path, str) or not phase4_manifest_path.strip():
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_missing_phase4_manifest',
        }

    phase4_manifest = _safe_read_json_dict(phase4_manifest_path)
    if not isinstance(phase4_manifest, dict):
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_invalid_phase4_manifest',
        }

    phase4_segments = phase4_manifest.get('segments') or phase4_manifest.get('chunks') or []
    segments = [segment for segment in phase4_segments if isinstance(segment, dict)]
    if not segments:
        return {
            **result,
            'reason': 'segmentation_shadow_audio_overlay_no_segments',
        }

    overlay_dir = Path(summary_path).parent / 'phase6_audio_overlay'
    overlay_dir.mkdir(parents=True, exist_ok=True)

    transcript_segments: List[Dict[str, Any]] = []
    diarization_segments: List[Dict[str, Any]] = []
    speaker_stats: Dict[str, Dict[str, Any]] = {}
    full_text_parts: List[str] = []
    language: Optional[str] = None

    for segment in segments:
        start = segment.get('start')
        end = segment.get('end')
        transcript = segment.get('transcript')
        transcript = transcript.strip() if isinstance(transcript, str) else ''
        if transcript:
            full_text_parts.append(transcript)

        raw_transcript_segments = segment.get('transcript_segments')
        if isinstance(raw_transcript_segments, list):
            for item in raw_transcript_segments:
                if not isinstance(item, dict):
                    continue
                transcript_entry = dict(item)
                transcript_entry.setdefault('start', start)
                transcript_entry.setdefault('end', end)
                transcript_segments.append(transcript_entry)
        elif transcript:
            transcript_segments.append(
                {
                    'start': start,
                    'end': end,
                    'text': transcript,
                    'words': [],
                }
            )

        if language is None:
            raw_language = segment.get('language')
            if isinstance(raw_language, str) and raw_language.strip():
                language = raw_language.strip()

        raw_diarization = segment.get('diarization')
        if isinstance(raw_diarization, list):
            for item in raw_diarization:
                if not isinstance(item, dict):
                    continue
                diarization_entry = dict(item)
                diarization_entry.setdefault('start', start)
                diarization_entry.setdefault('end', end)
                diarization_segments.append(diarization_entry)
                speaker_id = diarization_entry.get('speaker')
                if isinstance(speaker_id, str) and speaker_id.strip():
                    normalized_id = speaker_id.strip()
                    speaker_stats.setdefault(
                        normalized_id,
                        {
                            'speaker_id': normalized_id,
                            'total_duration': 0.0,
                            'segment_count': 0,
                        },
                    )
                    duration_value = _coerce_optional_float(diarization_entry.get('duration'))
                    if duration_value is None:
                        start_value = _coerce_optional_float(diarization_entry.get('start'))
                        end_value = _coerce_optional_float(diarization_entry.get('end'))
                        if start_value is not None and end_value is not None:
                            duration_value = max(0.0, end_value - start_value)
                    speaker_stats[normalized_id]['total_duration'] += float(duration_value or 0.0)
                    speaker_stats[normalized_id]['segment_count'] += 1

        raw_speakers = segment.get('speakers')
        if isinstance(raw_speakers, list):
            for item in raw_speakers:
                if isinstance(item, dict):
                    speaker_id = item.get('speaker_id') or item.get('speaker') or item.get('label')
                    if isinstance(speaker_id, str) and speaker_id.strip():
                        normalized_id = speaker_id.strip()
                        speaker_stats.setdefault(
                            normalized_id,
                            {
                                'speaker_id': normalized_id,
                                'total_duration': float(item.get('total_duration') or 0.0),
                                'segment_count': int(item.get('segment_count') or 0),
                            },
                        )

    speakers = sorted(
        speaker_stats.values(),
        key=lambda speaker: (
            -float(speaker.get('total_duration') or 0.0),
            str(speaker.get('speaker_id') or ''),
        ),
    )
    full_text = " ".join(part for part in full_text_parts if part).strip()

    atomic_write_json(
        overlay_dir / 'segmentation.json',
        {
            'segments': segments,
        },
    )
    atomic_write_json(
        overlay_dir / 'transcript.json',
        {
            'segments': transcript_segments,
            'full_text': full_text,
            'language': language or 'en',
        },
    )
    atomic_write_json(
        overlay_dir / 'diarization.json',
        {
            'speakers': speakers,
            'segments': diarization_segments,
        },
    )

    return {
        'enabled': True,
        'reason': 'segmentation_shadow_audio_overlay_ready',
        'audio_artifact_dir': str(overlay_dir),
        'segment_count': len(segments),
        'transcript_segment_count': len(transcript_segments),
        'diarization_segment_count': len(diarization_segments),
        'speaker_count': len(speakers),
    }


def _run_segmentation_shadow_pipeline(
    video_path: Path,
    processing_dir: Path,
    cfg: Dict[str, Any],
    audio_runtime_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    activation = _resolve_segmentation_activation(cfg)
    result: Dict[str, Any] = {
        'activation': activation,
        'status': 'off',
        'reason': 'segmentation_shadow_disabled',
        'skip_phases': [],
    }
    if activation == 'off':
        return result
    if activation == 'authoritative':
        return {
            **result,
            'status': 'unsupported',
            'reason': 'segmentation_authoritative_not_enabled',
        }

    segmentation_cfg = cfg.get('segmentation') if isinstance(cfg, dict) else {}
    if not isinstance(segmentation_cfg, dict) or not segmentation_cfg.get('enabled', True):
        return {
            **result,
            'status': 'disabled',
            'reason': 'segmentation_config_disabled',
        }

    skip_phases: List[str] = []
    if isinstance(audio_runtime_contract, dict):
        selected_backend = str(audio_runtime_contract.get('selected') or '').strip().lower()
        if selected_backend != 'wsl':
            skip_phases.extend(['phase4', 'phase6'])

    try:
        from steps.audio.segmentation import PhasedSegmentationEngine

        shadow_root = processing_dir / "_segmentation_shadow"
        engine = PhasedSegmentationEngine(cfg)
        shadow_run = engine.run_full_pipeline(
            str(video_path),
            str(shadow_root),
            skip_phases=skip_phases,
        )
        phase_results = shadow_run.get('phase_results') if isinstance(shadow_run, dict) else {}
        phase3_result = phase_results.get('phase3') if isinstance(phase_results, dict) else {}
        phase5_result = phase_results.get('phase5') if isinstance(phase_results, dict) else {}
        phase6_result = phase_results.get('phase6') if isinstance(phase_results, dict) else {}
        summary: Dict[str, Any] = {
            'activation': activation,
            'status': 'complete' if not skip_phases else 'partial',
            'reason': 'segmentation_shadow_complete' if not skip_phases else 'segmentation_shadow_partial',
            'skip_phases': list(skip_phases),
            'output_dir': shadow_run.get('output_dir') if isinstance(shadow_run, dict) else None,
            'audio_manifest_path': phase3_result.get('audio_manifest_path') if isinstance(phase3_result, dict) else None,
            'phase4_manifest_path': (
                str(Path(shadow_run['output_dir']) / 'metadata' / 'segmentation_enhanced.json')
                if isinstance(shadow_run, dict) and shadow_run.get('output_dir')
                else None
            ),
            'scene_manifest_path': phase5_result.get('scene_manifest_path') if isinstance(phase5_result, dict) else None,
            'video_scenes_path': phase5_result.get('video_scenes_path') if isinstance(phase5_result, dict) else None,
            'segmentation_manifest_path': phase6_result.get('manifest_path') if isinstance(phase6_result, dict) else None,
            'validation': phase6_result.get('validation') if isinstance(phase6_result, dict) else None,
            'timings': shadow_run.get('timings') if isinstance(shadow_run, dict) else None,
        }
        summary_path = shadow_root / "shadow_summary.json"
        atomic_write_json(summary_path, summary)
        summary['summary_path'] = str(summary_path)
        return summary
    except Exception as e:
        logger.warning(
            "run_ingestion warning context=%s error=%s",
            "segmentation_shadow",
            e,
        )
        return {
            **result,
            'status': 'error',
            'reason': 'segmentation_shadow_failed',
            'error': str(e),
            'skip_phases': list(skip_phases),
        }


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


_STEP_FAILURE_RE = re.compile(
    r"^Step (?P<step>[A-Za-z0-9_]+) failed \((?P<env>[^)]+)\)"
    r"(?: \[returncode=(?P<returncode>-?\d+)\])?",
    re.MULTILINE,
)


def _tail_text(value: Any, *, max_chars: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _extract_labeled_output(raw_text: str, label: str) -> str:
    if label == "STDOUT":
        pattern = r"(?:^|\n)STDOUT:(.*?)(?=\nSTDERR:|\Z)"
    else:
        pattern = r"(?:^|\n)STDERR:(.*)\Z"
    match = re.search(pattern, raw_text, flags=re.DOTALL)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _extract_step_failure_details(error: Any, *, stage_label: str = "Step") -> Dict[str, Optional[str]]:
    raw_message = str(error or "").strip()
    details: Dict[str, Optional[str]] = {
        "step": None,
        "env": None,
        "returncode": None,
        "raw_message": raw_message or None,
        "message": None,
    }
    if not raw_message:
        details["message"] = f"{stage_label} failed with no error details"
        return details

    match = _STEP_FAILURE_RE.search(raw_message)
    if match:
        details["step"] = match.group("step")
        details["env"] = match.group("env")
        details["returncode"] = match.group("returncode")

    stdout_tail = _tail_text(_extract_labeled_output(raw_message, "STDOUT"))
    stderr_tail = _tail_text(_extract_labeled_output(raw_message, "STDERR"))

    message_parts: List[str] = []
    if details["step"] and details["env"]:
        headline = f"{stage_label} step {details['step']} failed ({details['env']})"
        if details["returncode"]:
            headline += f" [returncode={details['returncode']}]"
        message_parts.append(headline)
    else:
        message_parts.append(_tail_text(raw_message, max_chars=800))

    if stdout_tail:
        message_parts.append(f"STDOUT tail: {stdout_tail}")
    if stderr_tail:
        message_parts.append(f"STDERR tail: {stderr_tail}")
    if match and not stdout_tail and not stderr_tail:
        message_parts.append("No stdout/stderr captured from failing step")

    details["message"] = "\n".join(message_parts)
    return details


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
    transcript_duration = None
    if isinstance(transcript_meta, dict) and transcript_meta.get('duration') is not None:
        transcript_duration = _coerce_float(transcript_meta.get('duration'))
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

    if transcript_status == 'success' and not transcript_text and transcript_duration == 0.0:
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
    redacted_cfg = redact_config(serializable_cfg, include_local_values=True)
    _atomic_write_json(cfg_path, redacted_cfg, indent=2)
    return cfg_path


def _normalize_host_profile_name(raw: Any) -> str:
    value = str(raw or "").strip().upper()
    if value in {"BASELINE", "GPU_ENHANCED"}:
        return value
    return ""


def _load_host_runtime_overrides(cfg_json: Optional[Path]) -> Dict[str, Any]:
    if cfg_json is None or not cfg_json.exists():
        return {}
    try:
        raw = cfg_json.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        parsed = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    host_cfg = parsed.get("host")
    if not isinstance(host_cfg, dict):
        return {}
    return host_cfg


def _base_env(cfg_json: Optional[Path] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault('PYTHONNOUSERSITE', '1')
    env.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '1')
    models_root = _resolve_models_dir(cfg_json=cfg_json)
    env['HF_HOME'] = str(models_root)
    env['TORCH_HOME'] = str(models_root)
    # Add parent of REPO_ROOT to PYTHONPATH so "goodq4all.steps" can be imported.
    env['PYTHONPATH'] = str(REPO_ROOT.parent)
    
    # GPU Resource Management - Pin to GPU 0
    env['CUDA_VISIBLE_DEVICES'] = '0'

    host_cfg = _load_host_runtime_overrides(cfg_json)
    host_profile = _normalize_host_profile_name(host_cfg.get("profile") or env.get("GOODQ_HOST_PROFILE"))
    if host_profile:
        env["GOODQ_HOST_PROFILE"] = host_profile

    require_gpu_override = host_cfg.get("require_gpu")
    if isinstance(require_gpu_override, bool):
        env["GOODQ_REQUIRE_GPU"] = "1" if require_gpu_override else "0"
    elif host_profile == "BASELINE":
        # Baseline profile is CPU-safe by contract. Clear stale shell exports so
        # sidecar steps like OCR/CLAP do not inherit an accidental GPU requirement.
        env["GOODQ_REQUIRE_GPU"] = "0"

    require_wsl_audio_override = host_cfg.get("require_wsl_audio")
    if isinstance(require_wsl_audio_override, bool):
        env["GOODQ_REQUIRE_WSL_AUDIO"] = "1" if require_wsl_audio_override else "0"

    if host_profile == "BASELINE":
        env["GOODQ_NO_AUTO_GPU"] = "1"
    elif host_profile:
        env.pop("GOODQ_NO_AUTO_GPU", None)
    
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
    _step_env_overrides: Optional[Dict[str, Optional[str]]] = None,
    _native_retry_mode: Optional[str] = None,
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
        prefer_direct_env_python = bool(
            _prefer_direct_env_python
            or (
                _PREFER_DIRECT_ENV_PYTHON_ON_WINDOWS
                and direct_env_python is not None
            )
        )

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
                prefer_direct_env_python=prefer_direct_env_python
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
        if launcher_kind == "direct_env_python" and direct_env_python:
            env_python_path = Path(direct_env_python)
            if env_python_path.parent.name.lower() == 'bin':
                env_root = env_python_path.parent.parent
                env_bin = env_python_path.parent
            else:
                env_root = env_python_path.parent
                env_bin = env_root / 'Scripts'
            if step_env is work_env:
                step_env = dict(work_env)
            step_env['CONDA_DEFAULT_ENV'] = env_name
            step_env['CONDA_PREFIX'] = str(env_root)
            path_entries = [str(env_root)]
            if env_bin.exists():
                path_entries.append(str(env_bin))
            existing_path = step_env.get('PATH', '')
            if existing_path:
                path_entries.append(existing_path)
            step_env['PATH'] = os.pathsep.join(path_entries)
        step_env = _apply_env_overrides(step_env, _step_env_overrides)

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
        if _native_retry_mode:
            observer_meta["native_retry_mode"] = _native_retry_mode
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
                                _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                                _prefer_direct_env_python=_prefer_direct_env_python,
                                _step_env_overrides=_step_env_overrides,
                                _native_retry_mode=_native_retry_mode,
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
                    _step_env_overrides=_step_env_overrides,
                    _native_retry_mode=_native_retry_mode,
                )

            error_msg = (
                f"Step {step_name} failed ({env_name}) [returncode={result.returncode}]\n"
                f"STDOUT: {stdout}\n"
                f"STDERR: {stderr}"
            )
            if observer:
                observer.step_error(
                    observer_step,
                    error=f"returncode_{result.returncode}",
                    metadata=observer_meta,
                )

            is_native_crash = _is_windows_native_crash(result.returncode)
            retry_limit, retry_env_overrides, retry_mode = _resolve_native_retry_strategy(
                step_name,
                _native_retry_attempt + 1,
            )
            if is_native_crash and _native_retry_attempt < retry_limit:
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
                    "[RUN] Native crash detected for step=%s return_code=%s status_code=0x%08X retry=%s/%s mode=%s",
                    step_name,
                    result.returncode,
                    status_code,
                    retry_attempt,
                    retry_limit,
                    retry_mode or "default",
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
                            f"(0x{status_code:08X}); retrying via {retry_mode or 'default'}"
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
                    _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                    _prefer_direct_env_python=_prefer_direct_env_python,
                    _step_env_overrides=retry_env_overrides,
                    _native_retry_mode=retry_mode,
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
                                _direct_env_fallback_attempt=_direct_env_fallback_attempt,
                                _prefer_direct_env_python=_prefer_direct_env_python,
                                _step_env_overrides=_step_env_overrides,
                                _native_retry_mode=_native_retry_mode,
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
            output = out_path.read_text(encoding='utf-8')
            return _parse_step_result_json(
                output,
                step_name=step_name,
                env_name=env_name,
                source="output.json",
            )
        stdout = result.stdout
        return _parse_step_result_json(
            stdout,
            step_name=step_name,
            env_name=env_name,
            source="stdout",
        )
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

    merge('goodq_image_caption', 'image_ocr')
    merge('goodq_image_caption', 'image_caption')
    merge('goodq_object_detect', 'object_detect')
    merge('goodq_face_embed', 'face_embed')
    merge('goodq_image_caption', 'image_embed_dino')
    merge('goodq_image_caption', 'image_embed_clip')
    merge('goodq_core', 'tagger')
    canonicalize_taxonomy(item)
    _persist_frame_semantic_entities(
        item,
        scene_id=scene_id,
        video_id=video_hash,
    )

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
        text_embed_result = _run_step('goodq_text_embed', 'text_embed', text_payload, cfg_json)
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
            audio_cfg = cfg_payload.get('audio')
            if not isinstance(audio_cfg, dict):
                audio_cfg = {}
                cfg_payload['audio'] = audio_cfg
            tx_cfg = audio_cfg.get('transcribe')
            if not isinstance(tx_cfg, dict):
                tx_cfg = {}
                audio_cfg['transcribe'] = tx_cfg
            # Local fallback must not recurse back into the WSL path we are explicitly downgrading from.
            tx_cfg['use_wsl2'] = False
            local_item = {
                'source_path': str(audio_path),
                'path': str(audio_path),
                'scene_id': scene_id,
                'scene_index': scene.get('index'),
                'video_hash': video_hash,
                'video_id': video_hash,
            }
            prior_require_wsl_audio = os.environ.get('GOODQ_REQUIRE_WSL_AUDIO')
            os.environ['GOODQ_REQUIRE_WSL_AUDIO'] = '0'
            try:
                local_result = local_audio_transcribe(local_item, cfg_payload)
            finally:
                if prior_require_wsl_audio is None:
                    os.environ.pop('GOODQ_REQUIRE_WSL_AUDIO', None)
                else:
                    os.environ['GOODQ_REQUIRE_WSL_AUDIO'] = prior_require_wsl_audio
            if isinstance(local_result, dict):
                local_result = _offset_local_audio_result_to_scene(local_result, start)
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

    def log_unified_audio_attempt(
        result_payload: Optional[Dict[str, Any]],
        duration_ms: float,
        *,
        error_text: Optional[str] = None,
        status_override: Optional[str] = None,
    ) -> None:
        step_item = dict(item)
        extra: Dict[str, Any] = {
            'backend': 'wsl',
            'requested_backend': contract_selected,
        }
        if isinstance(result_payload, dict):
            reason = result_payload.get('bridge_error_reason')
            if isinstance(reason, str) and reason.strip():
                extra['reason'] = reason.strip()
            details = result_payload.get('bridge_error_details')
            if isinstance(details, dict) and details:
                extra['bridge_error_details'] = details
            env_warnings = result_payload.get('bridge_env_warnings')
            if isinstance(env_warnings, list) and env_warnings:
                extra['bridge_env_warnings'] = env_warnings
        log_step_run(
            _get_step_log_cfg(),
            'audio_unified_wsl2',
            step_item,
            duration_ms,
            status_override or ('error' if error_text else 'ok'),
            error_text,
            extra=extra,
        )

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
                unified_started = time.perf_counter()
                unified_result = audio_unified_wsl2(str(audio_path), scene_id=scene_id, duration=end-start)
                unified_duration_ms = (time.perf_counter() - unified_started) * 1000.0
                if isinstance(unified_result, dict):
                    item.update(unified_result)
                    item['audio_backend_selected'] = contract_selected
                    item['audio_backend_reason'] = contract_reason
                    if str(unified_result.get('status', '')).strip().lower() == 'error':
                        error_text = str(
                            unified_result.get('error')
                            or unified_result.get('bridge_error_reason')
                            or 'WSL unified audio error'
                        ).strip()
                        log_unified_audio_attempt(
                            unified_result,
                            unified_duration_ms,
                            error_text=error_text,
                            status_override='error',
                        )
                        unavailable_details: Dict[str, Any] = {
                            'reason': str(unified_result.get('bridge_error_reason') or 'wsl_unified_error'),
                            'error': error_text,
                        }
                        bridge_details = unified_result.get('bridge_error_details')
                        if isinstance(bridge_details, dict) and bridge_details:
                            unavailable_details['bridge_error_details'] = bridge_details
                        env_warnings = unified_result.get('bridge_env_warnings')
                        if isinstance(env_warnings, list) and env_warnings:
                            unavailable_details['bridge_env_warnings'] = env_warnings
                        item['audio_backend_unavailable_details'] = unavailable_details
                        logger.warning(
                            "[AUDIO] WSL2 unified audio returned structured error scene_id=%s reason=%s error=%s; downgrading to local fallback",
                            scene_id,
                            unavailable_details['reason'],
                            error_text,
                        )
                        run_local_audio_fallback('wsl_unified_error_fallback')
                    else:
                        log_unified_audio_attempt(unified_result, unified_duration_ms)
                        _set_effective_backend('wsl', 'wsl_unified_success')
            except Exception as unified_error:
                unified_duration_ms = (time.perf_counter() - unified_started) * 1000.0 if 'unified_started' in locals() else 0.0
                log_unified_audio_attempt(
                    None,
                    unified_duration_ms,
                    error_text=str(unified_error),
                    status_override='error',
                )
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
        text_embed_result = _run_step('goodq_text_embed', 'text_embed', text_payload, cfg_json)
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
    scene_backend_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    backend_contract = scene_backend_contract if isinstance(scene_backend_contract, dict) else {
        'scene_backend_selected': 'legacy_scene_detect',
        'scene_backend_effective': 'legacy_scene_detect',
        'scene_backend_effective_reason': 'legacy_scene_detect_default',
    }
    dispatch = _resolve_scene_backend_dispatch(backend_contract)
    payload: Dict[str, Any] = {
        'modality': 'video',
        'source_path': str(video_path),
    }
    if video_id:
        payload['video_id'] = str(video_id)
        payload['video_hash'] = str(video_id)
    if overrides:
        payload['scene_detect'] = overrides
    result = _run_step(dispatch['env_name'], dispatch['step_name'], payload, cfg_json)
    scenes = result.get('scenes') if isinstance(result, dict) else None
    if not scenes:
        scenes = [{'index': 0, 'start': 0.0, 'end': 0.0, 'duration': 0.0, 'confidence': 1.0}]
    for scene in scenes:
        start = float(scene.get('start', 0.0) or 0.0)
        end = float(scene.get('end', start) or start)
        scene['duration'] = round(max(0.0, end - start), 3)
        scene.setdefault('confidence', 0.5)
    meta = result.get('scene_meta') if isinstance(result, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    meta['orchestration'] = {
        'scene_backend_selected': backend_contract.get('scene_backend_selected'),
        'scene_backend_effective': backend_contract.get('scene_backend_effective'),
        'scene_backend_effective_reason': backend_contract.get('scene_backend_effective_reason'),
        'step_env': dispatch['env_name'],
        'step_name': dispatch['step_name'],
    }
    return {
        'scenes': scenes,
        'meta': meta,
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
    STEP_TIMEOUT = _resolve_step_timeout_value(step_timeout)

    base_cfg = load_configs({})
    cfg: Dict[str, Any] = dict(base_cfg) if isinstance(base_cfg, dict) else {}
    required_runtime_keys: List[str] = []
    if input_dir is None:
        required_runtime_keys.append("import_inbox")
    if output is None:
        required_runtime_keys.append("output_directory")
    if workspace is None:
        required_runtime_keys.append("processing")

    runtime_paths = (
        get_runtime_paths(cfg, *required_runtime_keys, require_canonical=False)
        if required_runtime_keys
        else {}
    )
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
        
        tracker = get_tracker() if PROGRESS_TRACKING_AVAILABLE else None

        # Initialize progress tracking
        if PROGRESS_TRACKING_AVAILABLE:
            tracker.start_processing(video_path.name, total_steps=4, run_id=run_id)
        audio_backend_event_start = len(run_context.get('audio_backend_events') or [])
        
        scene_overrides: Dict[str, Any] = {}
        if max_scenes:
            scene_overrides['max_scenes'] = max_scenes
        if scene_threshold is not None:
            scene_overrides['threshold'] = scene_threshold
        if min_scene_seconds is not None:
            scene_overrides['min_scene_len_sec'] = min_scene_seconds
        phase6_enabled = cfg.get('phase6', {}).get('enabled', True)

        stored_manifest = list_scenes_for_video(cfg, video_hash)
        force_redetect = cfg.get('force_reprocess', False)
        reuse_scenes = bool(stored_manifest.get('scenes')) and not force_redetect
        
        if force_redetect and stored_manifest.get('scenes'):
            if VERBOSE:
                typer.echo(f'[INFO] Force reprocess enabled - ignoring {len(stored_manifest.get("scenes", []))} stored scenes, will re-detect')

        processing_dir = _ensure_dir(processing_root / video_path.stem)
        frame_dir = _ensure_dir(processing_dir / 'video' / 'frames')
        audio_artifact_dir = _ensure_dir(processing_dir / 'audio')
        audio_dir = _ensure_dir(audio_artifact_dir / 'chunks')
        run_context['audio_artifact_dir'] = str(audio_artifact_dir)
        
        if reuse_scenes:
            scene_backend_contract = _resolve_scene_backend_contract(cfg)
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
            if not isinstance(detection_meta, dict):
                detection_meta = {}
            detection_meta.setdefault(
                'orchestration',
                {
                    'scene_backend_selected': scene_backend_contract.get('scene_backend_selected'),
                    'scene_backend_effective': scene_backend_contract.get('scene_backend_effective'),
                    'scene_backend_effective_reason': 'scene_manifest_reuse',
                    'step_env': 'scene_manifest_reuse',
                    'step_name': 'scene_manifest_reuse',
                },
            )
            if 'scene_manifest_hash' not in detection_meta or not detection_meta['scene_manifest_hash']:
                manifest_hasher = hashlib.sha256()
                for seg in scenes:
                    start = float(seg.get('start', 0.0) or 0.0)
                    end = float(seg.get('end', start) or start)
                    manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
                detection_meta['scene_manifest_hash'] = manifest_hasher.hexdigest()
            detection = {'scenes': scenes, 'meta': detection_meta}
            if tracker is not None:
                total_progress_steps = 1 + len(scenes) + (2 if phase6_enabled and len(scenes) > 0 else 0)
                tracker.set_total_steps(total_progress_steps)
                tracker.update_step("Scene Reuse", 1, {"scenes_found": len(scenes), "video_id": video_hash})
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
            if tracker is not None:
                tracker.update_step("Scene Detection", 1, {"scenes_to_detect": "analyzing video"})

            scene_backend_contract = _resolve_scene_backend_contract(cfg)
            if scene_backend_contract.get('scene_backend_effective') == 'segmentation_phase5':
                detection = _run_segmentation_authoritative_scene_backend(
                    video_path,
                    processing_dir,
                    cfg,
                    scene_backend_contract=scene_backend_contract,
                )
            else:
                detection = _detect_scenes(
                    cfg_json,
                    video_path,
                    scene_overrides,
                    video_id=video_hash,
                    scene_backend_contract=scene_backend_contract,
                )
            scenes = detection.get('scenes', [])
            
            if tracker is not None:
                total_progress_steps = 1 + len(scenes) + (2 if phase6_enabled and len(scenes) > 0 else 0)
                tracker.set_total_steps(total_progress_steps)
                tracker.update_step("Scene Detection Complete", 1, {"scenes_found": len(scenes), "video_id": video_hash})
            
            detection_meta = detection.get('meta') or {}
            manifest_hasher = hashlib.sha256()
            for seg in scenes:
                start = float(seg.get('start', 0.0) or 0.0)
                end = float(seg.get('end', start) or start)
                manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
            detection_meta['scene_manifest_hash'] = manifest_hasher.hexdigest()
            detection['meta'] = detection_meta

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
            if tracker is not None:
                tracker.update_step(
                    f"Scene {scene_num}/{total_scenes}",
                    1 + scene_num,
                    {
                        "scene_index": scene_index,
                        "scenes_total": total_scenes,
                        "video_id": video_hash,
                    },
                )
            
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
            frame_error_raw: Optional[str] = None
            frame_error_step: Optional[str] = None
            frame_error_env: Optional[str] = None
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
                        frame_failure = _extract_step_failure_details(exc, stage_label='Keyframe')
                        frame_error = frame_failure.get('message') or str(exc)
                        frame_error_raw = frame_failure.get('raw_message')
                        frame_error_step = frame_failure.get('step')
                        frame_error_env = frame_failure.get('env')
                        step_suffix = f" step={frame_error_step}" if frame_error_step else ""
                        typer.echo(
                            f'[ERROR] Keyframe processing failed for scene {scene_index}{step_suffix}: {frame_error}',
                            err=True,
                        )

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
                if frame_error_raw and frame_error_raw != frame_error:
                    error_payload['frame_raw'] = frame_error_raw
                if frame_error_step:
                    error_payload['frame_step'] = frame_error_step
                if frame_error_env:
                    error_payload['frame_env'] = frame_error_env
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
                kg_scene_data = _build_kg_scene_data(
                    scene,
                    scene_id=scene_id,
                    video_id=video_hash,
                    frame_data=frame_data,
                    audio_data=audio_data,
                )
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
                if frame_error_raw and frame_error_raw != frame_error:
                    scene_record['keyframe_error_raw'] = frame_error_raw
                if frame_error_step:
                    scene_record['keyframe_error_step'] = frame_error_step
                if frame_error_env:
                    scene_record['keyframe_error_env'] = frame_error_env
            if audio_info:
                formatted_audio = _merge_step_output(audio_info)
                if formatted_audio:
                    _promote_metadata_time_hints(formatted_audio)
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
            'audio_backend_events': _audio_backend_events_since(run_context, audio_backend_event_start),
            'audio_runtime_contract': audio_runtime_contract,
            'phase5_complete': True,
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

        segmentation_shadow_result = _run_segmentation_shadow_pipeline(
            video_path,
            processing_dir,
            cfg,
            audio_runtime_contract=audio_runtime_contract,
        )
        segmentation_shadow_overlay = _prepare_segmentation_shadow_audio_overlay(
            cfg,
            segmentation_shadow_result,
        )
        orchestration_contract = _resolve_ingest_orchestration_contract(
            cfg,
            audio_runtime_contract=audio_runtime_contract,
            segmentation_shadow=segmentation_shadow_result,
            segmentation_shadow_overlay=segmentation_shadow_overlay,
        )
        video_result['orchestration'] = orchestration_contract
        phase6_audio_artifact_dir = Path(
            segmentation_shadow_overlay.get('audio_artifact_dir')
        ) if segmentation_shadow_overlay.get('enabled') else audio_artifact_dir
        video_result['phase6_audio_artifact_dir'] = str(phase6_audio_artifact_dir)
        if segmentation_shadow_overlay.get('enabled'):
            video_result['phase6_audio_overlay'] = segmentation_shadow_overlay
        
        # ============================================================
        # PHASE 6: VISUAL EMBEDDINGS + MULTIMODAL HARMONIZATION
        # ============================================================
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
                'audio_artifact_dir': str(phase6_audio_artifact_dir),
                'scene_manifest_path': str(processing_dir / 'video' / 'scene_manifest.json'),
                'scenes': scene_outputs,
                'video_hash': video_hash,
            }
            
            # Write scene_manifest.json for Phase 6 to consume
            scene_manifest = {
                'video_id': video_hash,
                'video_path': str(video_path),
                'phase5_complete': True,
                'total_scenes': len(scene_outputs),
                'content_summary': content_summary,
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
            scene_manifest_path = processing_dir / 'video' / 'scene_manifest.json'
            scene_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            existing_scene_manifest: Optional[Dict[str, Any]] = None
            if scene_manifest_path.exists():
                try:
                    existing_scene_manifest = json.loads(scene_manifest_path.read_text(encoding='utf-8'))
                except Exception as e:
                    logger.warning(
                        "run_ingestion warning context=%s error=%s",
                        "phase6_manifest_prior_state",
                        e,
                    )
            atomic_write_json(
                scene_manifest_path,
                _merge_prior_phase6_manifest_state(scene_manifest, existing_scene_manifest),
            )
            
            try:
                # Phase 6a: Scene Visual Embeddings (CLIP + DINO)
                typer.echo('[PHASE 6a] Generating scene visual embeddings...')
                embeddings_result = _run_step('goodq_core', 'scene_visual_embeddings', phase6_item, cfg_json)
                if tracker is not None:
                    tracker.update_step(
                        "Phase 6a",
                        total_scenes + 2,
                        {"stage": "scene_visual_embeddings", "video_id": video_hash},
                    )
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
                if tracker is not None:
                    tracker.update_step(
                        "Phase 6b",
                        total_scenes + 3,
                        {"stage": "cross_modal_harmonization", "video_id": video_hash},
                    )
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
                        if _rehydrate_video_result_scenes_from_manifest(
                            video_result,
                            phase6_item.get('scene_manifest_path'),
                        ):
                            video_result['content_summary'] = _aggregate_content_summary(
                                video_result.get('scenes', [])
                            )
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

        segmentation_shadow_result = _attach_segmentation_shadow_metrics(
            cfg,
            scene_outputs,
            video_result.get('temporal_index'),
            segmentation_shadow_result,
        )
        segmentation_shadow_result = dict(segmentation_shadow_result)
        shadow_metrics = segmentation_shadow_result.get('metrics') if isinstance(segmentation_shadow_result.get('metrics'), dict) else {}
        if isinstance(video_result.get('orchestration'), dict) and isinstance(shadow_metrics, dict):
            orchestration_contract = dict(video_result['orchestration'])
            scene_backend_comparison = shadow_metrics.get('shadow', {}).get('scene_backend_comparison')
            if isinstance(scene_backend_comparison, dict):
                orchestration_contract['scene_backend_comparison'] = scene_backend_comparison
                video_result['orchestration'] = orchestration_contract
        segmentation_shadow_result['orchestration'] = orchestration_contract
        if segmentation_shadow_overlay.get('enabled'):
            segmentation_shadow_result['phase6_audio_overlay'] = segmentation_shadow_overlay
        video_result['segmentation_shadow'] = segmentation_shadow_result

        video_result['qdrant_ok'] = _merge_store_statuses(scene_qdrant_status, phase6_qdrant_status)
        video_result['faiss_ok'] = _merge_store_statuses(scene_faiss_status, phase6_faiss_status)
        video_result['modality_status'] = _aggregate_modality_status(scene_outputs, phase6_embeddings_result)
        
        results.append(video_result)
        if tracker is not None:
            finish_processing("completed")

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
            if PROGRESS_TRACKING_AVAILABLE:
                finish_processing("failed")
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
