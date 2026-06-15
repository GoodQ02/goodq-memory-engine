from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import os

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional guard
    cv2 = None


def _probe_video_duration(path: str) -> Optional[float]:
    """Best-effort duration probe for fallback scene manifests."""
    try:
        import imageio_ffmpeg  # type: ignore

        _, secs = imageio_ffmpeg.count_frames_and_secs(path)
        if secs and float(secs) > 0:
            return float(secs)
    except Exception as e:
        print(f"[WARN] Duration probe via imageio_ffmpeg failed: {type(e).__name__}: {str(e)}")

    if cv2 is None:
        return None
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        cap.release()
        if fps > 0 and frame_count > 0:
            return frame_count / fps
    except Exception as e:
        print(f"[WARN] Duration probe via cv2 failed: {type(e).__name__}: {str(e)}")
    return None


def _get_video_dimensions(path: str) -> Tuple[float, float, int, int]:
    """Probes the video file using cv2 to extract duration, fps, width, height."""
    duration = 0.0
    fps = 23.976
    width = 0
    height = 0
    if cv2 is None:
        return duration, fps, width, height
    try:
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 23.976)
            frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if fps > 0 and frame_count > 0:
                duration = frame_count / fps
            cap.release()
    except Exception as e:
        print(f"[WARN] Failed to get video dimensions via cv2: {e}")
    return duration, fps, width, height


def _load_ucf_ledger() -> Any:
    """Dynamically imports ucf_ledger from the skill scripts directory."""
    import importlib.util
    import sys
    from pathlib import Path
    
    current_file = Path(__file__).resolve()
    repo_root = current_file.parents[2]  # steps/video_scene_detect/step.py -> parents[2] is repo_root
    ucf_ledger_path = repo_root / '.agents' / 'skills' / 'ucf-invariant-anchor' / 'scripts' / 'ucf_ledger.py'
    
    if not ucf_ledger_path.exists():
        raise FileNotFoundError(f"ucf_ledger.py not found at {ucf_ledger_path}")
    
    spec = importlib.util.spec_from_file_location("ucf_ledger", str(ucf_ledger_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for ucf_ledger at {ucf_ledger_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules["ucf_ledger"] = module
    spec.loader.exec_module(module)
    return module


def _load_params(cfg: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load scene detection parameters with robust fallback handling.
    Supports multiple config formats and prevents None/invalid values.
    """
    
    # Try unified config.yaml format (root level)
    video_cfg = cfg.get('video', {})
    if video_cfg is None:
        video_cfg = {}
    
    # If not found, try legacy format (nested under 'config')
    if not video_cfg and 'config' in cfg:
        video_cfg = cfg['config'].get('video', {})
        if video_cfg is None:
            video_cfg = {}
    
    # Get scene config - try both naming conventions
    scene_cfg = video_cfg.get('scene_detect', video_cfg.get('scene_detection', {}))
    if scene_cfg is None:
        scene_cfg = {}
    
    # Get overrides from item
    overrides = item.get('scene_detect', {})
    if not isinstance(overrides, dict):
        overrides = {}
    
    # Robust parameter extraction with proper None handling
    def safe_get(override_val, cfg_val, default_val):
        """Get value with None-safe fallback chain."""
        if override_val is not None:
            return override_val
        if cfg_val is not None:
            return cfg_val
        return default_val
    
    threshold_val = safe_get(
        overrides.get('threshold'),
        scene_cfg.get('threshold'),
        30.0
    )
    
    min_scene_val = safe_get(
        overrides.get('min_scene_len_sec'),
        scene_cfg.get('min_scene_len_sec') or scene_cfg.get('min_scene_len'),
        300.0
    )
    
    params = {
        'threshold': float(threshold_val),
        'min_scene_len_sec': float(min_scene_val),
        'max_scenes': int(safe_get(overrides.get('max_scenes'), scene_cfg.get('max_scenes'), 0)),
    }
    
    # Final safety checks
    if params['min_scene_len_sec'] <= 0:
        params['min_scene_len_sec'] = 300.0
    if params['threshold'] <= 0:
        params['threshold'] = 30.0
    if params['max_scenes'] < 0:
        params['max_scenes'] = 0
    return params


def _fallback_single_scene(duration: Optional[float], path: Optional[str] = None) -> List[Dict[str, Any]]:
    resolved_duration: Optional[float] = None
    if duration and duration > 0:
        resolved_duration = float(duration)
    elif path and os.path.isfile(path):
        resolved_duration = _probe_video_duration(path)
        if resolved_duration and resolved_duration > 0:
            print(f"[SCENE] Fallback duration probe succeeded: {resolved_duration:.3f}s")
    end = float(resolved_duration) if resolved_duration and resolved_duration > 0 else 0.0
    return [
        {
            'index': 0,
            'start': 0.0,
            'end': round(end, 3),
            'duration': round(end, 3),
            'confidence': 1.0,
            'strategy': 'fallback',
        }
    ]


def _detect_with_scenedetect(path: str, threshold: float, min_scene_len_sec: float) -> Dict[str, Any]:
    """
    Scene detection with GPU acceleration when available
    Falls back to CPU-based PySceneDetect if GPU fails
    """
    # Try GPU acceleration first
    try:
        import torch
        if torch.cuda.is_available():
            print("[SCENE] Using GPU-accelerated scene detection")
            from .gpu_scene_detect import detect_scenes_gpu
            result = detect_scenes_gpu(path, threshold, min_scene_len_sec)
            return result
        else:
            print("[SCENE] GPU not available, using CPU-based detection")
    except Exception as e:
        print(f"[SCENE] GPU detection failed ({str(e)}), falling back to CPU")
    
    # Fallback to CPU-based PySceneDetect
    print("[SCENE] Using CPU-based PySceneDetect")
    from scenedetect import open_video, SceneManager, StatsManager
    from scenedetect.detectors import ContentDetector

    video = open_video(path)
    stats_manager = StatsManager()
    scene_manager = SceneManager(stats_manager=stats_manager)
    try:
        frame_rate = float(video.frame_rate) if getattr(video, 'frame_rate', None) else None
    except Exception as e:
        frame_rate = None
    if frame_rate and frame_rate > 0:
        min_len_frames = max(1, int(round(frame_rate * min_scene_len_sec)))
    else:
        min_len_frames = None
    detector = ContentDetector(threshold=threshold, min_scene_len=min_len_frames)
    scene_manager.add_detector(detector)
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list() or []
    scenes: List[Dict[str, Any]] = []
    scores: List[float] = []
    try:
        duration = float(video.duration) if getattr(video, 'duration', None) else None
    except Exception as e:
        duration = None
    for idx, (start_time, end_time) in enumerate(scene_list):
        start_sec = float(start_time.get_seconds() or 0.0)
        end_sec = float(end_time.get_seconds() or start_sec)
        try:
            metrics = stats_manager.get_metrics(start_time)
        except TypeError as e:
            try:
                metrics = stats_manager.get_metrics(start_time, ['content_val'])
            except Exception as e:
                metrics = None
        except Exception as e:
            metrics = None
        score = 0.0
        if metrics:
            try:
                score = float(metrics.get('content_val', 0.0) or 0.0)
            except Exception as e:
                score = 0.0
        scores.append(score)
        scenes.append(
            {
                'index': idx,
                'start': round(start_sec, 3),
                'end': round(end_sec, 3),
                'duration': round(max(0.0, end_sec - start_sec), 3),
                'score': score,
            }
        )
    max_score = max(scores) if scores else 0.0
    for entry in scenes:
        if max_score > 0:
            entry['confidence'] = round(float(entry.get('score', 0.0)) / max_score, 4)
        else:
            entry['confidence'] = 0.5
        entry.pop('score', None)
    try:
        video.release()
    except Exception as e:
        print(f'[ERROR] Exception in step.py line 115: {str(e)}')
        pass
    return {'scenes': scenes, 'duration': duration}


def video_scene_detect(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Import progress tracker
    try:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to import progress tracker: {e}")
        tracker = None
    
    path = item.get('source_path')
    if not isinstance(path, str) or not os.path.isfile(path):
        return {
            'scenes': _fallback_single_scene(None, path if isinstance(path, str) else None),
            'scene_meta': {
                'status': 'missing_file',
                'reason': 'source_path not found',
            },
        }
    
    filename = os.path.basename(path)
    params = _load_params(cfg, item)
    
    # Update progress
    if tracker:
        tracker.update_step("video_scene_detect", 2, {
            "details": f"Detecting scenes (threshold={params['threshold']}, min_len={params['min_scene_len_sec']}s)"
        })
    
    print(f"[SCENE] Detecting scenes in {filename}")
    print(f"[SCENE] Parameters: threshold={params['threshold']}, min_scene_len={params['min_scene_len_sec']}s")
    
    try:
        detection = _detect_with_scenedetect(path, params['threshold'], params['min_scene_len_sec'])
        scenes = detection.get('scenes', [])
        if not scenes:
            scenes = _fallback_single_scene(detection.get('duration'), path)
            status = 'fallback_single_scene'
            print(f"[SCENE] No scenes detected, using fallback single scene")
        else:
            status = 'ok'
            print(f"[SCENE] Detected {len(scenes)} scenes")
        error_msg = None
    except Exception as exc:
        print(f"[ERROR] Scene detection failed: {exc}")
        scenes = _fallback_single_scene(None, path)
        status = 'error'
        error_msg = str(exc)
        if tracker:
            tracker.add_error(f"Scene detection failed: {str(exc)}", "video_scene_detect")

    max_scenes = params['max_scenes']
    if max_scenes and len(scenes) > max_scenes:
        scenes = scenes[:max_scenes]
        print(f"[SCENE] Truncated to {max_scenes} scenes")
    
    # Update progress with results
    if tracker:
        tracker.complete_step("video_scene_detect", {
            "scene_count": len(scenes),
            "status": status
        })

    meta = {
        'status': status,
        'engine': 'scenedetect',
        'threshold': params['threshold'],
        'min_scene_len_sec': params['min_scene_len_sec'],
        'scene_count': len(scenes),
    }
    if error_msg:
        meta['error'] = error_msg

    # --- UCF Integration Hook ---
    try:
        video_hash = item.get('video_hash') or item.get('video_id')
        if video_hash and path and os.path.isfile(path):
            print(f"[UCF] Initializing UCF database registration for video_hash: {video_hash}")
            # Resolve epoch_id
            db_dir = cfg.get('paths', {}).get('db_dir')
            epoch_id = os.path.basename(db_dir) if db_dir else "unknown_epoch"
            
            # Resolve run_id
            run_id = os.getenv("GOODQ_RUN_ID") or cfg.get('run', {}).get('id') or "unknown_run"
            
            # Dynamically import ucf_ledger.py
            ucf_module = _load_ucf_ledger()
            UCFLedgerClient = ucf_module.UCFLedgerClient
            
            # Determine database path
            if db_dir:
                from pathlib import Path
                data_root = os.getenv("GOODQ_DATA_ROOT") or cfg.get('paths', {}).get('data_root')
                if data_root:
                    root_path = Path(data_root)
                    if root_path.name == "GoodQ_Data":
                        root_path = root_path.parent
                    ucf_db_dir = root_path / 'epochs' / epoch_id / 'ucf'
                else:
                    ucf_db_dir = Path(db_dir) / 'ucf'
                ucf_db_dir.mkdir(parents=True, exist_ok=True)
                ucf_db_path = ucf_db_dir / 'ucf_ledger.db'
                
                client = UCFLedgerClient(str(ucf_db_path))
                client.init_schema()
                
                # Probe video properties for media_sources registration
                probe_dur, fps, width, height = _get_video_dimensions(path)
                resolved_dur = probe_dur if probe_dur > 0 else (detection.get('duration') or 0.0)
                
                # Register media source
                client.register_media(
                    video_hash=video_hash,
                    file_path=path,
                    duration=resolved_dur,
                    fps=fps,
                    width=width,
                    height=height
                )
                print(f"[UCF] Media source registered: {path} ({resolved_dur:.3f}s, {fps:.2f} fps, {width}x{height})")
                
                # Log context frames for each scene
                logged_count = 0
                for scene in scenes:
                    start_val = scene.get('start', 0.0)
                    end_val = scene.get('end', 0.0)
                    idx_val = scene.get('index', 0)
                    confidence_val = scene.get('confidence', 1.0)
                    
                    payload = {
                        "scene_index": idx_val,
                        "duration": scene.get('duration', 0.0),
                        "engine": "scenedetect",
                        "threshold": params['threshold']
                    }
                    
                    client.log_frame(
                        video_hash=video_hash,
                        epoch_id=epoch_id,
                        run_id=run_id,
                        t_start=start_val,
                        t_end=end_val,
                        modality="video",
                        worker_name="video_scene_detect",
                        model_tag="scenedetect",
                        confidence=confidence_val,
                        source_artifact_id=f"scene_{idx_val:04d}",
                        payload=payload
                    )
                    logged_count += 1
                
                print(f"[UCF] Logged {logged_count} scene context frames to UCF ledger.")
                client.close()
            else:
                print("[WARN] [UCF] cfg['paths']['db_dir'] not found. Skipping UCF ledger write.")
        else:
            print("[WARN] [UCF] video_hash or source_path not available. Skipping UCF ledger write.")
    except Exception as e:
        print(f"[WARN] [UCF] UCF registration failed: {type(e).__name__}: {str(e)}")
        # Do not crash the entire ingestion step if UCF logging fails

    return {
        'scenes': scenes,
        'scene_meta': meta,
    }
