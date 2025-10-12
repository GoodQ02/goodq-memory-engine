from __future__ import annotations
from typing import Any, Dict, List, Optional, Set
import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import re
import typer

from goodq4all.steps.common.config_loader import load_configs
from goodq4all.steps.common.memory import ensure_scene, register_scene_bundle, scene_has_materialized, get_scene_meta, list_scenes_for_video
from goodq4all.steps.common.tag_utils import canonicalize_taxonomy
from goodq4all.steps.common.tool_paths import resolve_ffmpeg
from goodq4all.steps.common.step_logger import log_step_run

# Knowledge graph integration
try:
    from lib.knowledge_graph import KnowledgeGraph
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False

APP = typer.Typer(help='Scene-first ingestion orchestrator for GoodQ')
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_DIR = Path(os.environ.get('HF_HOME', 'L:/models'))

# Populated by CLI options at runtime
VERBOSE: bool = False
STEP_TIMEOUT: Optional[int] = None

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
    'audio_diarize',
    'audio_transcribe',
    'audio_speaker_merge',
    'audio_music_events',
    'audio_time_hints',
    'audio_emotion',
    'sentiment',
    'emotion_classify',
    'tagger',
    'audio_embed_clap',
]



def _build_knowledge_graph_from_results(results: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build knowledge graph from ingestion results"""
    if not KNOWLEDGE_GRAPH_AVAILABLE:
        if VERBOSE:
            typer.echo('[kg] Knowledge graph module not available, skipping')
        return None
    
    try:
        data_dir = Path(cfg.get('data_dir', 'data'))
        graph_db_path = data_dir / 'knowledge_graph.db'
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
                    entity_id = kg.add_node('object', label, {'confidence': confidence}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, confidence)
    
    # Tags
    tags = keyframe.get('tags', [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str):
                entity_id = kg.add_node('concept', tag, {}, timestamp)
                kg.link_node_to_media(entity_id, media_id, 0.5)
    
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
        entity_id = kg.add_node('concept', 'speech', {'transcript': transcript[:100]}, timestamp)
        kg.link_node_to_media(entity_id, media_id, 0.9)
    
    # Speaker diarization
    speakers = audio.get('speakers', [])
    if isinstance(speakers, list):
        for speaker in speakers:
            if isinstance(speaker, dict):
                speaker_id = speaker.get('speaker', speaker.get('label'))
                if speaker_id:
                    entity_id = kg.add_node('person', f'speaker_{speaker_id}', {}, timestamp)
                    kg.link_node_to_media(entity_id, media_id, 0.7)
    
    # Audio emotions
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



OUTPUT_DROP_KEYS: Set[str] = {'modality', 'scene_id', 'scene_index', 'video_hash'}


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


def _write_cfg_snapshot(cfg: Dict[str, Any], workspace: Path) -> Path:
    cfg_path = workspace / '_resolved_config.json'
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    return cfg_path


def _base_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault('PYTHONNOUSERSITE', '0')
    env.setdefault('HF_HUB_ENABLE_HF_TRANSFER', '1')
    env.setdefault('HF_HOME', str(DEFAULT_MODELS_DIR))
    env.setdefault('TORCH_HOME', str(DEFAULT_MODELS_DIR))
    env.setdefault('PYTHONPATH', str(REPO_ROOT.parent))
    return env


def _run_step(env_name: str, step_name: str, payload: Dict[str, Any], cfg_json: Path) -> Dict[str, Any]:
    work_env = _base_env()
    tmp_dir = Path(tempfile.mkdtemp(prefix='ingest_step_'))
    try:
        in_path = tmp_dir / 'input.json'
        out_path = tmp_dir / 'output.json'
        in_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        cmd = [
            'conda', 'run', '-n', env_name,
            'python', '-m', 'goodq4all.cli.step_runner',
            '--step', step_name,
            '--in', str(in_path),
            '--out', str(out_path),
            '--cfg', str(cfg_json),
        ]
        start_ts = time.perf_counter()
        if VERBOSE:
            typer.echo(f'[step] -> {step_name} ({env_name})')
        try:
            result = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                env=work_env,
                timeout=STEP_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            if VERBOSE:
                typer.echo(f'[step] !! {step_name} ({env_name}) timed out after {STEP_TIMEOUT}s', err=True)
            raise RuntimeError(f"Step {step_name} timed out after {STEP_TIMEOUT}s") from exc
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            raise RuntimeError(f"Step {step_name} failed ({env_name})`nSTDOUT: {stdout}`nSTDERR: {stderr}")
        duration = time.perf_counter() - start_ts
        if VERBOSE:
            typer.echo(f'[step] <- {step_name} ({env_name}) [{duration:.1f}s]')
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
        except Exception:
            pass



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
    }
    if scene_id is not None:
        item['scene_id'] = scene_id
    if scene_index is not None:
        item['scene_index'] = scene_index
    if source_path:
        item['source_path'] = source_path
    for step_name in step_names:
        log_step_run(cfg, step_name, item, 0.0, 'skipped', extra=extra_payload)


def _extract_keyframe(ffmpeg: str, video_path: Path, scene: Dict[str, Any], dest_dir: Path) -> Path:
    _ensure_dir(dest_dir)
    duration = float(scene.get('duration', 0.0) or 0.0)
    start = float(scene.get('start', 0.0) or 0.0)
    timestamp = start + (duration / 2.0) if duration > 0 else start
    outfile = dest_dir / f"scene_{scene.get('index', 0):04d}.jpg"
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to extract keyframe: {result.stderr}")
    if not outfile.exists():
        raise RuntimeError('Keyframe extraction did not produce a file')
    return outfile


def _extract_audio_chunk(ffmpeg: str, video_path: Path, scene: Dict[str, Any], dest_dir: Path) -> Path:
    _ensure_dir(dest_dir)
    start = float(scene.get('start', 0.0) or 0.0)
    end = float(scene.get('end', start) or start)
    duration = max(0.1, end - start)
    outfile = dest_dir / f"scene_{scene.get('index', 0):04d}.wav"
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to extract audio chunk: {result.stderr}")
    if not outfile.exists():
        raise RuntimeError('Audio chunk extraction did not produce a file')
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
    frame_path = _extract_keyframe(ffmpeg, video_path, scene, frame_dir)
    scene_index = scene.get('index')
    duration = float(scene.get('duration', 0.0) or 0.0)
    start = float(scene.get('start', 0.0) or 0.0)
    frame_timestamp = start + (duration / 2.0) if duration > 0 else start

    item: Dict[str, Any] = {
        'modality': 'image',
        'source_path': str(frame_path),
        'scene_id': scene_id,
        'video_hash': video_hash,
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
    merge('goodq_emotion_classify', 'tagger')

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
            'video_hash': video_hash,
        }
        _run_step('goodq_text_embed', 'text_embed', text_payload, cfg_json)
        item['frame_text'] = frame_text

    canonicalize_taxonomy(item)

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
    video_hash: str,
    scene_id: str,
) -> Dict[str, Any]:
    audio_path = _extract_audio_chunk(ffmpeg, video_path, scene, audio_dir)
    start = float(scene.get('start', 0.0) or 0.0)
    end = float(scene.get('end', start) or start)

    item: Dict[str, Any] = {
        'modality': 'audio',
        'source_path': str(audio_path),
        'scene_id': scene_id,
        'video_hash': video_hash,
        'scene': {
            'start': start,
            'end': end,
            'duration': end - start,
        },
    }

    def merge(env_name: str, step_name: str) -> None:
        result = _run_step(env_name, step_name, item, cfg_json)
        if isinstance(result, dict):
            item.update(result)

    merge('goodq_audio_metadata', 'audio_metadata')
    merge('goodq_audio_diarize', 'audio_diarize')
    merge('goodq_audio_transcribe', 'audio_transcribe')
    merge('goodq_audio_transcribe', 'audio_speaker_merge')
    merge('goodq_audio_transcribe', 'audio_music_events')
    merge('goodq_audio_transcribe', 'audio_time_hints')
    merge('goodq_audio_emotion', 'audio_emotion')

    transcript = item.get('transcript') if isinstance(item.get('transcript'), str) else ''
    if transcript:
        text_payload = {
            'modality': 'audio_transcript',
            'source_path': str(audio_path),
            'text': transcript,
            'scene_id': scene_id,
            'video_hash': video_hash,
        }
        _run_step('goodq_text_embed', 'text_embed', text_payload, cfg_json)

    merge('goodq_sentiment', 'sentiment')
    merge('goodq_emotion_classify', 'emotion_classify')
    merge('goodq_emotion_classify', 'tagger')
    merge('goodq_audio_embed', 'audio_embed_clap')

    canonicalize_taxonomy(item)

    return {
        'path': str(audio_path),
        'start': start,
        'end': end,
        'data': item,
    }


def _detect_scenes(cfg_json: Path, video_path: Path, overrides: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'modality': 'video',
        'source_path': str(video_path),
    }
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
    input_dir: Path = typer.Option(Path('import_inbox'), help='Directory containing videos to ingest'),
    output: Path = typer.Option(Path('logs/scene_ingest_results.json'), help='Path to write JSON results'),
    workspace: Path = typer.Option(Path('logs/scene_ingest'), help='Workspace directory for artifacts'),
    max_videos: int = typer.Option(0, help='Maximum number of videos to process (0 = all)'),
    max_scenes: int = typer.Option(0, help='Maximum scenes per video (0 = all)'),
    scene_threshold: Optional[float] = typer.Option(None, help='Override PySceneDetect content threshold'),
    min_scene_seconds: Optional[float] = typer.Option(None, help='Minimum scene length in seconds'),
    force_reprocess: bool = typer.Option(False, '--force', help='Force reprocessing even if scenes already exist in database'),
    verbose: bool = typer.Option(False, '--verbose', help='Emit per-step progress messages'),
    step_timeout: Optional[int] = typer.Option(None, '--step-timeout', help='Abort a step if it exceeds this many seconds'),
) -> None:
    global VERBOSE, STEP_TIMEOUT
    VERBOSE = verbose
    STEP_TIMEOUT = step_timeout
    input_dir = input_dir.resolve()
    workspace = workspace.resolve()
    output = output.resolve()

    if not input_dir.exists():
        raise typer.BadParameter(f'Input directory not found: {input_dir}')

    _ensure_dir(workspace)

    cfg = load_configs({})
    run_context = {
        'id': str(uuid.uuid4()),
        'pipeline': 'scene_ingest_cli',
        'started_at': datetime.utcnow().isoformat(),
        'timer_unit': 'ms',
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
    except Exception:
        pass
    existing_run = cfg.get('run') if isinstance(cfg, dict) else None
    if isinstance(existing_run, dict):
        existing_run.update(run_context)
        cfg['run'] = existing_run
    else:
        cfg['run'] = run_context
    
    # Add force_reprocess flag to config
    cfg['force_reprocess'] = force_reprocess
    cfg_json = _write_cfg_snapshot(cfg, workspace)

    ffmpeg = resolve_ffmpeg(cfg) or 'ffmpeg'

    video_patterns = ('*.mp4', '*.mov', '*.mkv', '*.avi', '*.webm')
    videos: List[Path] = []
    for pattern in video_patterns:
        videos.extend(sorted(input_dir.glob(pattern)))
    if not videos:
        typer.echo('No videos found to process.')
        return
    if max_videos and len(videos) > max_videos:
        videos = videos[:max_videos]

    results: List[Dict[str, Any]] = []

    for video_path in videos:
        typer.echo(f'Processing video: {video_path.name}')
        typer.echo(f'  Full path: {video_path}')
        typer.echo(f'  Exists: {video_path.exists()}')
        typer.echo(f'  Size: {video_path.stat().st_size / 1024**2:.2f} MB' if video_path.exists() else '  Size: N/A')
        video_hash = _compute_sha256(video_path)
        scene_overrides: Dict[str, Any] = {}
        if max_scenes:
            scene_overrides['max_scenes'] = max_scenes
        if scene_threshold is not None:
            scene_overrides['threshold'] = scene_threshold
        if min_scene_seconds is not None:
            scene_overrides['min_scene_len_sec'] = min_scene_seconds

        stored_manifest = list_scenes_for_video(cfg, video_hash)
        reuse_scenes = bool(stored_manifest.get('scenes'))
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
            detection = _detect_scenes(cfg_json, video_path, scene_overrides)
            scenes = detection.get('scenes', [])
            detection_meta = detection.get('meta') or {}
            manifest_hasher = hashlib.sha256()
            for seg in scenes:
                start = float(seg.get('start', 0.0) or 0.0)
                end = float(seg.get('end', start) or start)
                manifest_hasher.update(f"{start:.6f}|{end:.6f}|".encode('utf-8'))
            detection_meta['scene_manifest_hash'] = manifest_hasher.hexdigest()
            detection['meta'] = detection_meta

        video_workspace = _ensure_dir(workspace / video_path.stem)
        frame_dir = _ensure_dir(video_workspace / 'frames')
        audio_dir = _ensure_dir(video_workspace / 'audio')

        scene_outputs: List[Dict[str, Any]] = []
        for scene in scenes:
            scene_start = float(scene.get('start', 0.0) or 0.0)
            scene_end = float(scene.get('end', scene_start) or scene_start)
            scene_index = scene.get('index')
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
                        frame_info = _process_frame(cfg_json, ffmpeg, video_path, scene, frame_dir, video_hash, scene_id)
                    except Exception as exc:  # noqa: BLE001
                        frame_error = str(exc)
                        typer.echo(f'[ERROR] Frame extraction failed for scene {scene_index}: {frame_error}', err=True)

            if skip_audio:
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
                        audio_info = _process_audio(cfg_json, ffmpeg, video_path, scene, audio_dir, video_hash, scene_id)
                    except Exception as exc:  # noqa: BLE001
                        audio_error = str(exc)
                        typer.echo(f'[ERROR] Audio extraction failed for scene {scene_index}: {audio_error}', err=True)

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

            scene_record: Dict[str, Any] = {
                'scene_id': scene_id,
                'index': scene.get('index'),
                'start': scene.get('start'),
                'end': scene.get('end'),
                'duration': scene.get('duration'),
                'confidence': scene.get('confidence'),
                'persistence': persist_result,
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
                    scene_record['audio'] = formatted_audio
                else:
                    scene_record['audio'] = audio_info
            elif audio_error:
                scene_record['audio_error'] = audio_error
            if error_payload:
                scene_record['errors'] = error_payload

            scene_outputs.append(scene_record)

        results.append({
            'video_path': str(video_path),
            'video_hash': video_hash,
            'scene_meta': detection_meta,
            'scenes': scene_outputs,
        })

    # Build knowledge graph from results
    kg_result = _build_knowledge_graph_from_results(results, cfg)
    if kg_result and kg_result.get('status') == 'success':
        if VERBOSE:
            typer.echo(f"[kg] Knowledge graph built successfully: {kg_result.get('statistics', {})}")

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
            raise typer.Exit(code=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    typer.echo(f'Wrote results to {output}')


if __name__ == '__main__':
    APP()





