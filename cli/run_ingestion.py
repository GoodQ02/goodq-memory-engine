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

from zenml_project.steps.common.config_loader import load_configs
from zenml_project.steps.common.memory import ensure_scene, register_scene_bundle, scene_has_materialized, get_scene_meta, list_scenes_for_video
from zenml_project.steps.common.tag_utils import canonicalize_taxonomy
from zenml_project.steps.common.tool_paths import resolve_ffmpeg
from zenml_project.steps.common.step_logger import log_step_run

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
            'python', '-m', 'zenml_project.cli.step_runner',
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

            skip_frame = bool(materialized.get('keyframe')) if isinstance(materialized, dict) else False
            skip_audio = bool(materialized.get('audio')) if isinstance(materialized, dict) else False

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
                try:
                    frame_info = _process_frame(cfg_json, ffmpeg, video_path, scene, frame_dir, video_hash, scene_id)
                except Exception as exc:  # noqa: BLE001
                    frame_error = str(exc)

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
                try:
                    audio_info = _process_audio(cfg_json, ffmpeg, video_path, scene, audio_dir, video_hash, scene_id)
                except Exception as exc:  # noqa: BLE001
                    audio_error = str(exc)

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

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    typer.echo(f'Wrote results to {output}')


if __name__ == '__main__':
    APP()





