"""
Phase 6: Scene Frame Extractor
Extracts representative frames from video scenes for embedding generation.
Supports keyframe, uniform sampling, and middle-frame strategies.
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import os
import json
import logging
import subprocess
import tempfile
import numpy as np
from pathlib import Path

from steps.common.tool_paths import resolve_ffmpeg

logger = logging.getLogger(__name__)


def _is_reusable_frame(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False


def extract_frame_at_timestamp(
    video_path: str,
    timestamp: float,
    output_path: str,
    ffmpeg_exe: str,
    width: int = 224,
    height: int = 224,
    cap: Optional[Any] = None
) -> bool:
    """
    Extract a single frame at specified timestamp using OpenCV or FFmpeg fallback.
    
    Args:
        video_path: Path to source video
        timestamp: Time in seconds
        output_path: Where to save the frame
        width: Frame width for resize
        height: Frame height for resize
        cap: Optional pre-opened cv2.VideoCapture instance
        
    Returns:
        True if extraction succeeded
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if _is_reusable_frame(output_path):
            logger.info("scene_frame_extractor reuse existing frame output=%s timestamp=%s", output_path, timestamp)
            return True

        # Try OpenCV first
        use_opencv = True
        local_cap = None
        active_cap = None
        if cap is not None:
            active_cap = cap
        else:
            try:
                import cv2
                local_cap = cv2.VideoCapture(video_path)
                active_cap = local_cap
            except Exception:
                use_opencv = False

        if use_opencv and active_cap is not None and active_cap.isOpened():
            try:
                import cv2
                # Hardening: Cap timestamp to video duration if available to prevent out-of-bounds seeks
                fps = active_cap.get(cv2.CAP_PROP_FPS)
                total_frames = active_cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if fps > 0 and total_frames > 0:
                    video_duration = total_frames / fps
                    if timestamp >= video_duration:
                        timestamp = max(0.0, video_duration - 0.05)

                # Seek to timestamp in milliseconds
                active_cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
                ret, frame = active_cap.read()
                if ret and frame is not None:
                    # Resize frame
                    resized = cv2.resize(frame, (width, height))
                    # Save frame
                    cv2.imwrite(output_path, resized)
                    logger.debug("scene_frame_extractor OpenCV extraction succeeded output=%s timestamp=%s", output_path, timestamp)
                    return True
                else:
                    logger.warning("OpenCV read failed at timestamp=%s; falling back to FFmpeg", timestamp)
            except Exception as cv_err:
                logger.warning("OpenCV extraction error at timestamp=%s: %s; falling back to FFmpeg", timestamp, cv_err)
            finally:
                if local_cap is not None:
                    local_cap.release()

        # Fallback to FFmpeg subprocess
        suffix = Path(output_path).suffix or ".jpg"
        temp_handle = tempfile.NamedTemporaryFile(
            prefix="frame_extract_",
            suffix=suffix,
            dir=os.path.dirname(output_path) or None,
            delete=False,
        )
        temp_path = temp_handle.name
        temp_handle.close()
        
        cmd = [
            ffmpeg_exe,
            '-ss', str(timestamp),
            '-i', video_path,
            '-vframes', '1',
            '-vf', f'scale={width}:{height}',
            '-y',
            temp_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and _is_reusable_frame(temp_path):
            os.replace(temp_path, output_path)
            return True
        else:
            logger.warning(f"FFmpeg frame extraction failed at {timestamp}s: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Frame extraction error at {timestamp}s: {e}")
        return False
    finally:
        temp_path_value = locals().get("temp_path")
        if isinstance(temp_path_value, str) and os.path.exists(temp_path_value):
            try:
                os.remove(temp_path_value)
            except OSError:
                pass


def extract_frames_uniform(
    video_path: str,
    start: float,
    end: float,
    num_frames: int,
    output_dir: str,
    scene_id: int,
    ffmpeg_exe: str,
    cap: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Extract uniformly spaced frames from a scene.
    
    Args:
        video_path: Path to source video
        start: Scene start time in seconds
        end: Scene end time in seconds
        num_frames: Number of frames to extract
        output_dir: Directory for frame outputs
        scene_id: Scene identifier
        ffmpeg_exe: Path to FFmpeg executable
        cap: Optional pre-opened cv2.VideoCapture instance
        
    Returns:
        List of frame metadata dicts
    """
    duration = end - start
    if num_frames < 1:
        return []

    # Zero/negative-duration scenes can occur from upstream detection edge cases.
    # Keep extraction deterministic by sampling a single frame at scene start.
    if duration <= 0:
        try:
            fallback_ts = max(float(start), 0.0)
        except Exception:
            fallback_ts = 0.0
        logger.warning(
            "scene_frame_extractor fallback operation=%s scene_id=%s start=%s end=%s reason=%s timestamp=%s",
            "extract_frames_uniform",
            scene_id,
            start,
            end,
            "non_positive_duration",
            fallback_ts,
        )
        timestamps = [fallback_ts]
    elif num_frames == 1:
        timestamps = [start + duration / 2.0]
    else:
        timestamps = [start + (duration * i / (num_frames - 1)) for i in range(num_frames)]
    
    frames = []
    for idx, ts in enumerate(timestamps):
        frame_filename = f"scene_{scene_id:04d}_frame_{idx:02d}.jpg"
        frame_path = os.path.join(output_dir, frame_filename)
        
        if extract_frame_at_timestamp(video_path, ts, frame_path, ffmpeg_exe, cap=cap):
            frames.append({
                'frame_id': idx,
                'timestamp': ts,
                'path': frame_path,
                'extraction_method': 'uniform'
            })
    
    return frames


def extract_frames_middle(
    video_path: str,
    start: float,
    end: float,
    output_dir: str,
    scene_id: int,
    ffmpeg_exe: str,
    cap: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Extract the middle frame from a scene (fallback strategy).
    
    Args:
        video_path: Path to source video
        start: Scene start time
        end: Scene end time
        output_dir: Output directory
        scene_id: Scene identifier
        ffmpeg_exe: Path to FFmpeg executable
        cap: Optional pre-opened cv2.VideoCapture instance
        
    Returns:
        List with single frame metadata
    """
    middle = (start + end) / 2.0
    frame_filename = f"scene_{scene_id:04d}_middle.jpg"
    frame_path = os.path.join(output_dir, frame_filename)
    
    if extract_frame_at_timestamp(video_path, middle, frame_path, ffmpeg_exe, cap=cap):
        return [{
            'frame_id': 0,
            'timestamp': middle,
            'path': frame_path,
            'extraction_method': 'middle'
        }]
    
    return []


def extract_keyframe_candidates(
    video_path: str,
    start: float,
    end: float,
    output_dir: str,
    scene_id: int,
    ffmpeg_exe: str,
    max_frames: int = 5,
    cap: Optional[Any] = None,
    cfg: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Extract keyframe candidates using advanced Shannon-entropy, Laplacian-variance, or motion-peaks.
    Falls back to uniform sampling if candidate evaluation fails.
    
    Args:
        video_path: Path to source video
        start: Scene start time
        end: Scene end time
        output_dir: Output directory
        scene_id: Scene identifier
        ffmpeg_exe: Path to FFmpeg executable
        max_frames: Maximum frames to extract
        cap: Optional pre-opened cv2.VideoCapture instance
        cfg: Optional configuration dictionary
        
    Returns:
        List of frame metadata
    """
    if cap is None:
        try:
            import cv2
            cap_local = cv2.VideoCapture(video_path)
            if cap_local.isOpened():
                use_cap = cap_local
            else:
                use_cap = None
        except Exception:
            use_cap = None
    else:
        cap_local = None
        use_cap = cap

    if use_cap is None:
        logger.warning("Keyframe extraction fallback to uniform: no VideoCapture context available")
        return extract_frames_uniform(video_path, start, end, max_frames, output_dir, scene_id, ffmpeg_exe, cap=cap)

    try:
        import cv2
    except ImportError:
        if cap_local is not None:
            cap_local.release()
        return extract_frames_uniform(video_path, start, end, max_frames, output_dir, scene_id, ffmpeg_exe, cap=cap)

    # Read configuration
    phase6_cfg = cfg.get('phase6', {}) if isinstance(cfg, dict) else {}
    selection_mode = phase6_cfg.get('keyframe_selection_mode', 'entropy') # entropy | motion_peaks | sharpness
    
    duration = end - start
    if duration <= 0:
        if cap_local is not None:
            cap_local.release()
        return extract_frames_uniform(video_path, start, end, max_frames, output_dir, scene_id, ffmpeg_exe, cap=cap)
        
    num_candidates = max(max_frames * 3, 10)
    candidate_ts = [start + (duration * i / (num_candidates - 1)) for i in range(num_candidates)]
    
    # Hardening: Retrieve video duration to prevent out-of-bound seeking
    video_duration = None
    try:
        fps = use_cap.get(cv2.CAP_PROP_FPS)
        total_frames = use_cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps > 0 and total_frames > 0:
            video_duration = total_frames / fps
    except Exception:
        pass

    candidates = []
    prev_frame_gray = None
    evaluated_timestamps = set()
    
    for ts in candidate_ts:
        if video_duration is not None and ts >= video_duration:
            ts = max(0.0, video_duration - 0.05)
            
        # Skip duplicate timestamps resulting from capping to avoid redundant seeks
        ts_rounded = round(ts, 3)
        if ts_rounded in evaluated_timestamps:
            continue
        evaluated_timestamps.add(ts_rounded)

        use_cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
        ret, frame = use_cap.read()
        if not ret or frame is None:
            continue
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate scores
        score = 0.0
        if selection_mode == 'entropy':
            # Calculate Shannon Entropy
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = hist / hist.sum()
            score = float(-np.sum(hist * np.log2(hist + 1e-7)))
        elif selection_mode == 'sharpness':
            # Calculate Laplacian variance
            score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        elif selection_mode == 'motion_peaks':
            # Calculate mean absolute difference from previous frame
            if prev_frame_gray is not None:
                score = float(np.mean(np.abs(gray.astype(np.int16) - prev_frame_gray.astype(np.int16))))
            else:
                score = 0.0
            prev_frame_gray = gray
        else:
            # Default to entropy
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = hist / hist.sum()
            score = float(-np.sum(hist * np.log2(hist + 1e-7)))
            
        candidates.append({'timestamp': ts, 'score': score, 'frame': frame})
        
    if cap_local is not None:
        cap_local.release()
        
    if not candidates:
        logger.warning("Keyframe extraction found no valid candidate frames, falling back to uniform")
        return extract_frames_uniform(video_path, start, end, max_frames, output_dir, scene_id, ffmpeg_exe, cap=cap)
        
    # Sort candidates by score descending
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # Select max_frames ensuring a minimum temporal separation to avoid clustering
    selected_candidates = []
    min_separation = max(0.5, duration / (max_frames * 2)) # at least 0.5s or proportional
    
    for cand in candidates:
        if len(selected_candidates) >= max_frames:
            break
        # Check separation from already selected
        too_close = False
        for sel in selected_candidates:
            if abs(cand['timestamp'] - sel['timestamp']) < min_separation:
                too_close = True
                break
        if not too_close:
            selected_candidates.append(cand)
            
    # If we couldn't get enough separated frames, fill up with the highest score remaining
    if len(selected_candidates) < max_frames:
        for cand in candidates:
            if len(selected_candidates) >= max_frames:
                break
            if cand not in selected_candidates:
                selected_candidates.append(cand)
                
    # Sort selected candidates by timestamp to keep chronological order
    selected_candidates.sort(key=lambda x: x['timestamp'])
    
    # Save the selected frames
    frames = []
    for idx, cand in enumerate(selected_candidates):
        frame_filename = f"scene_{scene_id:04d}_frame_{idx:02d}.jpg"
        frame_path = os.path.join(output_dir, frame_filename)
        
        # Resize to 224x224 (default visual embedding size)
        resized = cv2.resize(cand['frame'], (224, 224))
        cv2.imwrite(frame_path, resized)
        
        frames.append({
            'frame_id': idx,
            'timestamp': cand['timestamp'],
            'path': frame_path,
            'extraction_method': f'keyframe_{selection_mode}',
            'selection_score': cand['score']
        })
        
    return frames


def extract_scene_frames(
    video_path: str,
    scenes: List[Dict[str, Any]],
    output_base_dir: str,
    strategy: str = 'uniform',
    frames_per_scene: int = 3,
    cfg: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main entry point for scene frame extraction.
    
    Args:
        video_path: Path to source video file
        scenes: List of scene dicts with 'start' and 'end' times
        output_base_dir: Base directory for frame storage
        strategy: Extraction strategy ('uniform', 'keyframe', 'middle')
        frames_per_scene: Number of frames to extract per scene
        cfg: Optional configuration dict
        
    Returns:
        Dictionary mapping scene IDs to frame metadata
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return {}
    
    # Create frames directory
    frames_dir = os.path.join(output_base_dir, 'frames')
    os.makedirs(frames_dir, exist_ok=True)

    cfg_for_tools: Dict[str, Any] = cfg if isinstance(cfg, dict) else {}
    if not cfg_for_tools:
        try:
            from steps.common.config_loader import load_configs
            loaded = load_configs()
            if isinstance(loaded, dict):
                cfg_for_tools = loaded
        except Exception:
            cfg_for_tools = {}
    ffmpeg_exe = resolve_ffmpeg(cfg_for_tools)
    if ffmpeg_exe is None:
        raise RuntimeError("FFmpeg not resolved")
    
    # Open shared cv2 VideoCapture context for fast seeking in Python
    cap = None
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            cap = None
            logger.warning("[SCENE-FRAME] OpenCV could not open video; falling back to FFmpeg process extraction")
        else:
            logger.info("[SCENE-FRAME] Using OpenCV-native frame extraction")
    except Exception as e:
        cap = None
        logger.warning(f"[SCENE-FRAME] OpenCV import/open failed: {e}; using FFmpeg process extraction")

    try:
        scene_frames = {}
        total_extracted = 0
        
        for scene_idx, scene in enumerate(scenes):
            scene_id = scene.get('id', scene.get('scene_id', 0))
            start = scene.get('start', 0.0)
            end = scene.get('end', start + 1.0)

            logger.info(f"Extracting frames for scene {scene_id}: {start:.2f}s - {end:.2f}s")

            # scene_id may be a string (e.g., a hash); filenames expect an int id.
            scene_id_for_filename = scene.get('index', scene_id)
            try:
                scene_id_for_filename = int(scene_id_for_filename)
            except (TypeError, ValueError):
                scene_id_for_filename = scene_idx
            
            # Select extraction strategy
            if strategy == 'middle':
                frames = extract_frames_middle(video_path, start, end, frames_dir, scene_id_for_filename, ffmpeg_exe, cap=cap)
            elif strategy == 'keyframe':
                frames = extract_keyframe_candidates(video_path, start, end, frames_dir, scene_id_for_filename, ffmpeg_exe, frames_per_scene, cap=cap, cfg=cfg)
            else:  # uniform (default)
                frames = extract_frames_uniform(video_path, start, end, frames_per_scene, frames_dir, scene_id_for_filename, ffmpeg_exe, cap=cap)
            
            if frames:
                scene_frames[scene_id] = frames
                total_extracted += len(frames)
                logger.info(f"  [SYMBOL] Extracted {len(frames)} frames")
            else:
                logger.warning(f"  [SYMBOL] No frames extracted for scene {scene_id}")
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
    
    logger.info(f"Total frames extracted: {total_extracted} from {len(scenes)} scenes")
    
    # Save frame manifest
    manifest_path = os.path.join(output_base_dir, 'frame_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump({
            'video_path': video_path,
            'extraction_strategy': strategy,
            'frames_per_scene': frames_per_scene,
            'total_scenes': len(scenes),
            'total_frames': total_extracted,
            'scene_frames': scene_frames
        }, f, indent=2)
    
    logger.info(f"Frame manifest saved: {manifest_path}")
    
    return scene_frames
