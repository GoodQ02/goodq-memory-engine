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
    except:
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
    return {
        'scenes': scenes,
        'scene_meta': meta,
    }
