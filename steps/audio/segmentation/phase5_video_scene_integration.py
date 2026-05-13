"""
Phase 5: Video Scene Detection Integration
Integrates lightweight per-chunk video scene detection with audio segmentation
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import os
import json
from pathlib import Path

try:
    import cv2
    import torch
    import numpy as np
except ImportError:
    cv2 = None
    torch = None
    np = None


def detect_scenes_for_chunk(
    video_path: str,
    chunk_start: float,
    chunk_end: float,
    threshold: float = 30.0,
    min_scene_len_sec: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Lightweight scene detection for a specific video chunk
    Aligns with audio segment boundaries
    
    Args:
        video_path: Path to source video file
        chunk_start: Start time in seconds
        chunk_end: End time in seconds
        threshold: Scene change sensitivity (higher = fewer scenes)
        min_scene_len_sec: Minimum scene length in seconds
        
    Returns:
        List of scene dictionaries with start/end/confidence
    """
    if cv2 is None or torch is None:
        print("[SCENE-CHUNK] OpenCV or PyTorch not available, skipping")
        return [{
            'start': chunk_start,
            'end': chunk_end,
            'duration': chunk_end - chunk_start,
            'confidence': 0.5,
            'strategy': 'fallback_full_chunk'
        }]
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[SCENE-CHUNK] Failed to open video: {video_path}")
        return [{
            'start': chunk_start,
            'end': chunk_end,
            'duration': chunk_end - chunk_start,
            'confidence': 0.5,
            'strategy': 'fallback_video_error'
        }]
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # fallback
    
    start_frame = int(chunk_start * fps)
    end_frame = int(chunk_end * fps)
    min_scene_frames = max(1, int(fps * min_scene_len_sec))
    
    # Seek to chunk start
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    scene_cuts = []
    prev_frame = None
    current_frame_idx = start_frame
    
    print(f"[SCENE-CHUNK] Processing frames {start_frame} to {end_frame} ({chunk_end - chunk_start:.1f}s)")
    
    while current_frame_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Resize for performance
        h, w = frame.shape[:2]
        scale = 320.0 / max(w, h)
        if scale < 1.0:
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if prev_frame is not None:
            # Compute frame difference on GPU
            current_tensor = torch.from_numpy(gray).float().to(device) / 255.0
            prev_tensor = torch.from_numpy(prev_frame).float().to(device) / 255.0
            
            diff = torch.mean(torch.abs(current_tensor - prev_tensor)).item() * 100.0
            
            # Scene cut detection
            if diff > threshold:
                # Enforce minimum scene length
                if not scene_cuts or (current_frame_idx - scene_cuts[-1]) >= min_scene_frames:
                    scene_cuts.append(current_frame_idx)
                    print(f"[SCENE-CHUNK] Scene cut at frame {current_frame_idx} (diff={diff:.1f})")
        
        prev_frame = gray.copy()
        current_frame_idx += 1
    
    cap.release()
    
    # Convert frame indices to time-based scenes
    scenes = []
    scene_starts = [start_frame] + scene_cuts
    scene_ends = scene_cuts + [end_frame]
    
    for start_f, end_f in zip(scene_starts, scene_ends):
        start_sec = start_f / fps
        end_sec = end_f / fps
        
        scenes.append({
            'start': round(start_sec, 3),
            'end': round(end_sec, 3),
            'duration': round(end_sec - start_sec, 3),
            'confidence': 1.0,
            'strategy': 'gpu_chunk_detect'
        })
    
    print(f"[SCENE-CHUNK] Detected {len(scenes)} scenes in chunk")
    
    return scenes


def align_scenes_with_audio_segments(
    audio_segments: List[Dict[str, Any]],
    video_scenes: List[Dict[str, Any]],
    alignment_tolerance: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Harmonize video scene boundaries with audio segment boundaries
    Prefers audio segment boundaries as primary segmentation
    
    Args:
        audio_segments: Audio segments from phased segmentation
        video_scenes: Video scenes from scene detection
        alignment_tolerance: Time tolerance for boundary alignment (seconds)
        
    Returns:
        Unified segment list with both audio and visual metadata
    """
    unified_segments = []
    
    for audio_seg in audio_segments:
        audio_start = audio_seg['start']
        audio_end = audio_seg['end']
        
        # Find overlapping video scenes
        overlapping_scenes = []
        for scene in video_scenes:
            scene_start = scene['start']
            scene_end = scene['end']
            
            # Check for overlap
            if not (scene_end <= audio_start or scene_start >= audio_end):
                overlapping_scenes.append(scene)
        
        # Create unified segment
        unified_seg = audio_seg.copy()
        unified_seg['video_scenes'] = overlapping_scenes
        unified_seg['scene_count'] = len(overlapping_scenes)
        
        # Check if scene boundary aligns with segment boundary
        scene_aligned_start = False
        scene_aligned_end = False
        
        for scene in video_scenes:
            if abs(scene['start'] - audio_start) <= alignment_tolerance:
                scene_aligned_start = True
            if abs(scene['end'] - audio_end) <= alignment_tolerance:
                scene_aligned_end = True
        
        unified_seg['scene_aligned'] = scene_aligned_start or scene_aligned_end
        
        unified_segments.append(unified_seg)
    
    return unified_segments


def process_video_chunks_with_scenes(
    video_path: str,
    audio_segments: List[Dict[str, Any]],
    output_dir: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main Phase 5 processing: detect scenes for each audio chunk
    
    Args:
        video_path: Path to source video
        audio_segments: Segments from Phase 3 (smart chunk builder)
        output_dir: Output directory for scene metadata
        config: Configuration dictionary
        
    Returns:
        Complete segmentation manifest with audio + video data
    """
    print("[PHASE5] Starting video scene detection for audio chunks")
    
    scene_threshold = config.get('scene_threshold', 30.0)
    min_scene_len = config.get('min_scene_len_sec', 2.0)
    
    all_video_scenes = []
    
    # Process each audio segment
    for idx, segment in enumerate(audio_segments):
        start = segment['start']
        end = segment['end']
        
        print(f"[PHASE5] Processing chunk {idx+1}/{len(audio_segments)}: {start:.1f}s - {end:.1f}s")
        
        # Detect scenes in this chunk
        chunk_scenes = detect_scenes_for_chunk(
            video_path,
            start,
            end,
            threshold=scene_threshold,
            min_scene_len_sec=min_scene_len
        )
        
        all_video_scenes.extend(chunk_scenes)
    
    # Align scenes with audio segments
    unified_segments = align_scenes_with_audio_segments(
        audio_segments,
        all_video_scenes,
        alignment_tolerance=0.5
    )
    
    video_id = Path(video_path).stem if video_path else "unknown_video"

    # Save scene detection results
    scenes_output = os.path.join(output_dir, 'video_scenes.json')
    scene_manifest_path = os.path.join(output_dir, 'scene_manifest.json')
    os.makedirs(output_dir, exist_ok=True)

    indexed_scenes = []
    for idx, scene in enumerate(all_video_scenes):
        indexed_scene = dict(scene)
        indexed_scene.setdefault('scene_id', f"scene_{idx:04d}")
        indexed_scene.setdefault('index', idx)
        indexed_scenes.append(indexed_scene)

    with open(scenes_output, 'w', encoding='utf-8') as f:
        json.dump({
            'total_scenes': len(all_video_scenes),
            'scenes': all_video_scenes,
            'aligned_segments': unified_segments
        }, f, indent=2)

    with open(scene_manifest_path, 'w', encoding='utf-8') as f:
        json.dump(
            {
                'video_id': video_id,
                'video_path': video_path,
                'phase5_complete': True,
                'total_scenes': len(indexed_scenes),
                'scenes': indexed_scenes,
                'aligned_segments': unified_segments,
            },
            f,
            indent=2,
        )
    
    print(f"[PHASE5] Detected {len(all_video_scenes)} video scenes across {len(audio_segments)} audio chunks")
    print(f"[PHASE5] Scene data saved to: {scenes_output}")
    
    return {
        'video_scenes': indexed_scenes,
        'scene_manifest_path': scene_manifest_path,
        'video_scenes_path': scenes_output,
        'unified_segments': unified_segments,
        'total_scenes': len(indexed_scenes),
        'total_chunks': len(audio_segments)
    }


def upgrade_analysis_for_legacy_scene_detect() -> Dict[str, Any]:
    """
    Analysis report for upgrading the legacy video_scene_detect environment
    
    CURRENT STATE:
    - goodq_video_scene_detect uses Torch 2.7.1+cu118 (CUDA 11.8)
    - Main pipeline uses Torch 2.5.1+cu121 (CUDA 12.1)
    - CUDA mismatch causes context conflicts
    
    RECOMMENDATION:
    - Phase 5 uses goodq_core (Torch 2.5.1+cu121) for chunk-level detection
    - Legacy scene detect can remain for full-video processing
    - Eventual migration: upgrade goodq_video_scene_detect to cu121
    
    SAFE UPGRADE PATH:
    1. Validate Phase 5 chunk detection works well
    2. Test full-video detection in goodq_core
    3. Deprecate goodq_video_scene_detect if redundant
    4. OR upgrade it to match cu121 if needed for specialized use
    """
    return {
        'current_issue': {
            'environment': 'goodq_video_scene_detect',
            'torch_version': '2.7.1+cu118',
            'cuda_version': '11.8',
            'conflict': 'CUDA version mismatch with main pipeline (12.1)'
        },
        'phase5_solution': {
            'environment': 'goodq_core',
            'torch_version': '2.5.1+cu121',
            'cuda_version': '12.1',
            'strategy': 'Chunk-level detection aligned with audio segments'
        },
        'upgrade_options': [
            {
                'option': 'Deprecate legacy scene detect',
                'rationale': 'Phase 5 handles all scene detection needs',
                'risk': 'Low - if Phase 5 proves sufficient',
                'steps': [
                    'Validate Phase 5 on real videos',
                    'Compare quality vs legacy detector',
                    'Remove goodq_video_scene_detect if redundant'
                ]
            },
            {
                'option': 'Upgrade legacy to cu121',
                'rationale': 'Keep specialized full-video detector',
                'risk': 'Medium - requires env rebuild',
                'steps': [
                    'Create goodq_video_scene_detect_v2 with cu121',
                    'Install torch==2.5.1+cu121',
                    'Migrate step routing',
                    'Test and deprecate old env'
                ]
            },
            {
                'option': 'Hybrid approach',
                'rationale': 'Use Phase 5 for chunks, legacy for archival',
                'risk': 'Low - keeps both isolated',
                'steps': [
                    'Default to Phase 5 for new ingestion',
                    'Keep legacy for special cases',
                    'Document use cases clearly'
                ]
            }
        ],
        'recommendation': 'Start with Phase 5 validation, then decide based on quality results'
    }


if __name__ == '__main__':
    # Example usage
    print("Phase 5: Video Scene Integration Module")
    print("=" * 60)
    
    analysis = upgrade_analysis_for_legacy_scene_detect()
    print("\nLegacy Scene Detect Upgrade Analysis:")
    print(json.dumps(analysis, indent=2))
