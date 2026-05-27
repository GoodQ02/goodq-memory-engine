"""
GPU-Accelerated Scene Detection using PyTorch
Replaces CPU-bound PySceneDetect with GPU-accelerated frame difference detection
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
import torch
import torch.nn.functional as F
import cv2
import numpy as np


def detect_scenes_gpu(
    video_path: str,
    threshold: float = 30.0,
    min_scene_len_sec: float = 300.0,
    batch_size: int = 32
) -> Dict[str, Any]:
    """
    GPU-accelerated scene detection using frame difference analysis
    
    Args:
        video_path: Path to video file
        threshold: Scene change threshold (0-100, higher = fewer scenes)
        min_scene_len_sec: Minimum scene length in seconds
        batch_size: Number of frames to process in parallel on GPU
    
    Returns:
        Dict with 'scenes' list and 'duration' float
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[SCENE-GPU] Using device: {device}")
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    min_scene_frames = max(1, int(fps * min_scene_len_sec))
    
    print(f"[SCENE-GPU] Video: {total_frames} frames @ {fps:.2f} fps = {duration:.2f}s")
    print(f"[SCENE-GPU] Min scene length: {min_scene_len_sec}s = {min_scene_frames} frames")
    
    # Process frames in batches
    scene_cuts = []
    prev_frame = None
    frame_idx = 0
    frames_buffer = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Resize for faster processing (maintain aspect ratio)
        h, w = frame.shape[:2]
        scale = 320.0 / max(w, h)
        if scale < 1.0:
            new_w, new_h = int(w * scale), int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h))
        
        # Convert to grayscale and normalize
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames_buffer.append(gray)
        
        # Process batch when full
        if len(frames_buffer) >= batch_size or frame_idx == total_frames - 1:
            if frames_buffer:
                # Convert to torch tensors
                frames_tensor = torch.stack([
                    torch.from_numpy(f).float() / 255.0 
                    for f in frames_buffer
                ]).to(device)
                
                # Compute frame differences (GPU accelerated and vectorized)
                if prev_frame is not None:
                    prev_tensor = torch.from_numpy(prev_frame).float().to(device) / 255.0
                    combined = torch.cat([prev_tensor.unsqueeze(0), frames_tensor], dim=0)
                    diffs_tensor = torch.mean(torch.abs(combined[1:] - combined[:-1]), dim=(1, 2)) * 100.0
                else:
                    # First batch of the video - compute differences within the batch
                    if len(frames_tensor) > 1:
                        diffs_tensor = torch.mean(torch.abs(frames_tensor[1:] - frames_tensor[:-1]), dim=(1, 2)) * 100.0
                        diffs_tensor = torch.cat([torch.tensor([0.0], device=device), diffs_tensor])
                    else:
                        diffs_tensor = torch.tensor([0.0], device=device)
                
                # Single GPU-to-CPU sync per batch
                diffs = diffs_tensor.cpu().tolist()
                
                for i in range(len(diffs)):
                    diff = diffs[i]
                    
                    # Check for scene cut
                    if diff > threshold:
                        # Enforce minimum scene length
                        if not scene_cuts or (frame_idx - len(frames_buffer) + i - scene_cuts[-1]) >= min_scene_frames:
                            scene_cuts.append(frame_idx - len(frames_buffer) + i)
                            print(f"[SCENE-GPU] Scene cut at frame {frame_idx - len(frames_buffer) + i} (diff={diff:.1f})")
            
            # Update prev_frame to last frame in batch
            if frames_buffer:
                prev_frame = frames_buffer[-1].copy()
            frames_buffer.clear()
        
        frame_idx += 1
        
        # Progress update every 5 seconds
        if frame_idx % int(fps * 5) == 0:
            progress = (frame_idx / total_frames) * 100
            print(f"[SCENE-GPU] Progress: {progress:.1f}% ({frame_idx}/{total_frames} frames)")
    
    cap.release()
    
    # Convert frame indices to time-based scenes
    scenes = []
    scene_starts = [0] + scene_cuts
    scene_ends = scene_cuts + [total_frames]
    
    for idx, (start_frame, end_frame) in enumerate(zip(scene_starts, scene_ends)):
        start_sec = start_frame / fps if fps > 0 else 0
        end_sec = end_frame / fps if fps > 0 else duration
        
        scenes.append({
            'index': idx,
            'start': round(start_sec, 3),
            'end': round(end_sec, 3),
            'duration': round(end_sec - start_sec, 3),
            'confidence': 1.0,
            'strategy': 'gpu_accelerated'
        })
    
    print(f"[SCENE-GPU] Detected {len(scenes)} scenes")
    
    return {
        'scenes': scenes,
        'duration': duration
    }


def detect_scenes_gpu_advanced(
    video_path: str,
    threshold: float = 30.0,
    min_scene_len_sec: float = 300.0,
    use_histogram: bool = True
) -> Dict[str, Any]:
    """
    Advanced GPU scene detection using histogram comparison
    More accurate but slightly slower than basic frame difference
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[SCENE-GPU-ADV] Using device: {device}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    min_scene_frames = max(1, int(fps * min_scene_len_sec))
    
    print(f"[SCENE-GPU-ADV] Video: {total_frames} frames @ {fps:.2f} fps")
    
    scene_cuts = []
    prev_hist = None
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Resize for performance
        h, w = frame.shape[:2]
        scale = 320.0 / max(w, h)
        if scale < 1.0:
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        
        # Compute color histogram on GPU
        frame_tensor = torch.from_numpy(frame).float().to(device)
        
        # Compute histogram for each channel
        hist_r = torch.histc(frame_tensor[:,:,2], bins=256, min=0, max=255)
        hist_g = torch.histc(frame_tensor[:,:,1], bins=256, min=0, max=255)
        hist_b = torch.histc(frame_tensor[:,:,0], bins=256, min=0, max=255)
        
        # Normalize histograms
        hist_r = hist_r / torch.sum(hist_r)
        hist_g = hist_g / torch.sum(hist_g)
        hist_b = hist_b / torch.sum(hist_b)
        
        current_hist = torch.cat([hist_r, hist_g, hist_b])
        
        if prev_hist is not None:
            # Compute histogram difference (Chi-square distance)
            diff = torch.sum((current_hist - prev_hist) ** 2).item() * 10000.0
            
            # Detect scene change
            if diff > threshold:
                if not scene_cuts or (frame_idx - scene_cuts[-1]) >= min_scene_frames:
                    scene_cuts.append(frame_idx)
                    print(f"[SCENE-GPU-ADV] Scene cut at frame {frame_idx} (diff={diff:.1f})")
        
        prev_hist = current_hist
        frame_idx += 1
        
        if frame_idx % int(fps * 5) == 0:
            progress = (frame_idx / total_frames) * 100
            print(f"[SCENE-GPU-ADV] Progress: {progress:.1f}%")
    
    cap.release()
    
    # Convert to time-based scenes
    scenes = []
    scene_starts = [0] + scene_cuts
    scene_ends = scene_cuts + [total_frames]
    
    for idx, (start_frame, end_frame) in enumerate(zip(scene_starts, scene_ends)):
        start_sec = start_frame / fps if fps > 0 else 0
        end_sec = end_frame / fps if fps > 0 else duration
        
        scenes.append({
            'index': idx,
            'start': round(start_sec, 3),
            'end': round(end_sec, 3),
            'duration': round(end_sec - start_sec, 3),
            'confidence': 1.0,
            'strategy': 'gpu_histogram'
        })
    
    print(f"[SCENE-GPU-ADV] Detected {len(scenes)} scenes")
    
    return {
        'scenes': scenes,
        'duration': duration
    }
