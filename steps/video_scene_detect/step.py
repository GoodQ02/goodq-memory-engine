from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import os

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional guard
    cv2 = None


def _load_params(cfg: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    # Try both 'scene_detect' and 'scene_detection' for backwards compatibility
    # Config can be nested under 'config' key or at root level
    if 'config' in cfg and 'video' in cfg['config']:
        video_cfg = (cfg['config'].get('video', {}) or {})
    else:
        video_cfg = (cfg.get('video', {}) or {})
    scene_cfg = video_cfg.get('scene_detect', video_cfg.get('scene_detection', {})) or {}
    overrides = item.get('scene_detect') if isinstance(item.get('scene_detect'), dict) else {}
    params = {
        'threshold': float(overrides.get('threshold', scene_cfg.get('threshold', 30.0))),  # Default 30.0 to avoid over-segmentation
        'min_scene_len_sec': float(overrides.get('min_scene_len_sec', scene_cfg.get('min_scene_len_sec', scene_cfg.get('min_scene_len', 300.0)))),  # Default 300.0s (5 minutes) minimum
        'max_scenes': int(overrides.get('max_scenes', scene_cfg.get('max_scenes', 0))),
        'entity_refine': bool(overrides.get('entity_refine', scene_cfg.get('entity_refine', False))),  # CRITICAL: Default FALSE to prevent 2-second scene splits
        'entity_sample_rate': float(overrides.get('entity_sample_rate', scene_cfg.get('entity_sample_rate', 0.5))),
        'entity_min_duration': float(overrides.get('entity_min_duration', scene_cfg.get('entity_min_duration', 300.0))),  # Match min_scene_len_sec default
        'entity_max_samples': int(overrides.get('entity_max_samples', scene_cfg.get('entity_max_samples', 300))),
    }
    if params['min_scene_len_sec'] <= 0:
        params['min_scene_len_sec'] = 300.0  # Fallback to 5 minutes
    if params['threshold'] <= 0:
        params['threshold'] = 30.0  # Fallback to 30.0 to avoid over-segmentation
    if params['max_scenes'] < 0:
        params['max_scenes'] = 0
    if params['entity_sample_rate'] <= 0:
        params['entity_sample_rate'] = 0.5
    if params['entity_min_duration'] <= 0:
        params['entity_min_duration'] = 1.0
    if params['entity_max_samples'] <= 0:
        params['entity_max_samples'] = 300
    return params


def _fallback_single_scene(duration: Optional[float]) -> List[Dict[str, Any]]:
    end = float(duration) if duration and duration > 0 else 0.0
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


def _ensure_detectors() -> Tuple[Optional[Any], Optional[Any]]:  # type: ignore[valid-type]
    if cv2 is None:  # pragma: no cover - optional dependency
        return None, None
    global _HOG_PEOPLE  # type: ignore  # pylint: disable=global-variable-undefined
    global _FACE_CASCADE  # type: ignore  # pylint: disable=global-variable-undefined
    try:
        _HOG_PEOPLE
    except NameError:  # pragma: no cover - lazy init
        _HOG_PEOPLE = None  # type: ignore
    try:
        _FACE_CASCADE
    except NameError:  # pragma: no cover - lazy init
        _FACE_CASCADE = None  # type: ignore

    if _HOG_PEOPLE is None:
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        _HOG_PEOPLE = hog
    if _FACE_CASCADE is None:
        cascade_root = getattr(cv2.data, 'haarcascades', '')
        cascade_path = os.path.join(cascade_root, 'haarcascade_frontalface_default.xml') if cascade_root else ''
        if cascade_path and os.path.isfile(cascade_path):
            _FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
        else:
            print(f'[WARN] _ensure_detectors: Face cascade not found at {cascade_path}')
            _FACE_CASCADE = None
    return _HOG_PEOPLE, _FACE_CASCADE  # type: ignore


def _sample_entity_states(
    path: str,
    start: float,
    end: float,
    sample_rate: float,
    max_samples: int,
) -> List[Dict[str, Any]]:
    hog, face_cascade = _ensure_detectors()
    if cv2 is None or (hog is None and face_cascade is None):
        return []

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():  # pragma: no cover - safety net
        return []

    samples: List[Dict[str, Any]] = []
    step = max(sample_rate, 0.5)
    current = max(start, 0.0)
    end_time = max(end, current)
    grabs = 0

    while current < end_time and grabs < max_samples:
        cap.set(cv2.CAP_PROP_POS_MSEC, current * 1000.0)
        grabbed, frame = cap.read()
        if not grabbed or frame is None:
            break
        frame_small = frame
        height, width = frame_small.shape[:2]
        scale = 640.0 / float(max(width, 1))
        if scale < 1.0:
            frame_small = cv2.resize(frame_small, (int(width * scale), int(height * scale)))

        persons = 0
        faces = 0
        if hog is not None:
            try:
                rects, _ = hog.detectMultiScale(frame_small, winStride=(8, 8), padding=(8, 8), scale=1.05)
                persons = len(rects)
            except Exception:  # pragma: no cover - robustness
                persons = 0
        if face_cascade is not None:
            try:
                gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
                detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
                faces = len(detected)
            except Exception:  # pragma: no cover
                faces = 0

        samples.append({
            'time': round(current, 3),
            'persons': persons,
            'faces': faces,
        })
        grabs += 1
        current += step

    cap.release()

    if not samples:
        return []

    if samples[-1]['time'] < end_time:
        terminal = samples[-1].copy()
        terminal['time'] = round(end_time, 3)
        samples.append(terminal)
    return samples


def _bucketize(count: int) -> int:
    if count <= 0:
        return 0
    if count == 1:
        return 1
    return 2


def _entity_segments(
    samples: List[Dict[str, Any]],
    start: float,
    end: float,
    min_duration: float,
) -> List[Dict[str, Any]]:
    if not samples:
        return []

    segments: List[Dict[str, Any]] = []
    seg_start = start
    prev_state = (_bucketize(samples[0]['persons']), _bucketize(samples[0]['faces']))
    aggregate = {
        'max_persons': samples[0]['persons'],
        'max_faces': samples[0]['faces'],
    }

    for sample in samples[1:]:
        state = (_bucketize(sample['persons']), _bucketize(sample['faces']))
        current_time = sample['time']
        aggregate['max_persons'] = max(aggregate['max_persons'], sample['persons'])
        aggregate['max_faces'] = max(aggregate['max_faces'], sample['faces'])
        if state != prev_state and (current_time - seg_start) >= max(min_duration, 0.5):
            segments.append({
                'start': seg_start,
                'end': current_time,
                'state': prev_state,
                'entity': aggregate,
            })
            seg_start = current_time
            prev_state = state
            aggregate = {
                'max_persons': sample['persons'],
                'max_faces': sample['faces'],
            }

    segments.append({
        'start': seg_start,
        'end': end,
        'state': prev_state,
        'entity': aggregate,
    })

    refined: List[Dict[str, Any]] = []
    for seg in segments:
        duration = seg['end'] - seg['start']
        if refined and duration < max(min_duration, 0.5):
            prev = refined[-1]
            prev['end'] = seg['end']
            prev['entity']['max_persons'] = max(prev['entity']['max_persons'], seg['entity']['max_persons'])
            prev['entity']['max_faces'] = max(prev['entity']['max_faces'], seg['entity']['max_faces'])
        else:
            refined.append(seg)

    for seg in refined:
        seg['start'] = round(seg['start'], 3)
        seg['end'] = round(seg['end'], 3)
        seg['duration'] = round(max(0.0, seg['end'] - seg['start']), 3)
        state = seg['state']
        seg['entity'] = {
            'max_persons': int(seg['entity']['max_persons']),
            'max_faces': int(seg['entity']['max_faces']),
            'has_person': seg['entity']['max_persons'] > 0,
            'has_face': seg['entity']['max_faces'] > 0,
            'persons_bucket': int(state[0]),
            'faces_bucket': int(state[1]),
        }
    return refined


def _refine_scenes_with_entities(
    path: str,
    scenes: List[Dict[str, Any]],
    params: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sample_rate = float(params.get('entity_sample_rate', 1.0) or 1.0)
    min_duration = float(params.get('entity_min_duration', 2.0) or 2.0)
    max_samples = int(params.get('entity_max_samples', 90) or 90)

    entity_meta = {
        'sample_rate': sample_rate,
        'min_duration': min_duration,
        'max_samples': max_samples,
        'detectors': 'opencv_hog_people+haar_faces',
        'refined_segments': 0,
        'status': 'skipped',
    }

    if cv2 is None:
        entity_meta['status'] = 'opencv_missing'
        return scenes, entity_meta

    refined: List[Dict[str, Any]] = []
    for base in scenes:
        start = float(base.get('start', 0.0) or 0.0)
        end = float(base.get('end', start) or start)
        if end <= start:
            refined.append(base)
            continue
        samples = _sample_entity_states(path, start, end, sample_rate, max_samples)
        entity_segments = _entity_segments(samples, start, end, min_duration)
        if not entity_segments:
            base.setdefault('entity', {'has_person': False, 'has_face': False})
            refined.append(base)
            continue
        if len(entity_segments) > 1:
            entity_meta['refined_segments'] += len(entity_segments) - 1
        for seg_idx, seg in enumerate(entity_segments):
            new_scene = dict(base)
            new_scene['start'] = seg['start']
            new_scene['end'] = seg['end']
            new_scene['duration'] = seg['duration']
            new_scene['entity'] = seg['entity']
            new_scene['parent_index'] = base.get('index')
            new_scene['strategy'] = 'entity_refine'
            new_scene['sub_index'] = seg_idx
            refined.append(new_scene)
    
    # Re-index all scenes sequentially after refinement
    for new_idx, scene in enumerate(refined):
        scene['index'] = new_idx

    entity_meta['scene_count'] = len(refined)
    entity_meta['status'] = 'ok'
    return refined, entity_meta


def video_scene_detect(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get('source_path')
    if not isinstance(path, str) or not os.path.isfile(path):
        return {
            'scenes': _fallback_single_scene(None),
            'scene_meta': {
                'status': 'missing_file',
                'reason': 'source_path not found',
            },
        }
    params = _load_params(cfg, item)
    try:
        detection = _detect_with_scenedetect(path, params['threshold'], params['min_scene_len_sec'])
        scenes = detection.get('scenes', [])
        if not scenes:
            scenes = _fallback_single_scene(detection.get('duration'))
            status = 'fallback_single_scene'
        else:
            status = 'ok'
        error_msg = None
    except Exception as exc:
        scenes = _fallback_single_scene(None)
        status = 'error'
        error_msg = str(exc)

    entity_meta = {'status': 'disabled'}
    # CRITICAL: Respect the config setting - default to FALSE to avoid scene over-segmentation
    if params.get('entity_refine', False) and scenes:
        refined_scenes, entity_meta = _refine_scenes_with_entities(path, scenes, params)
        scenes = refined_scenes

    max_scenes = params['max_scenes']
    if max_scenes and len(scenes) > max_scenes:
        scenes = scenes[:max_scenes]

    meta = {
        'status': status,
        'engine': 'scenedetect',
        'threshold': params['threshold'],
        'min_scene_len_sec': params['min_scene_len_sec'],
        'scene_count': len(scenes),
    }
    if error_msg:
        meta['error'] = error_msg
    if entity_meta.get('status') != 'disabled':
        meta['entity_refine'] = entity_meta
    return {
        'scenes': scenes,
        'scene_meta': meta,
    }
