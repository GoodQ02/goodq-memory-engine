"""
Voice Activity Detection (VAD) preprocessor for audio diarization.
Uses Silero VAD to filter out silence and non-speech before diarization.
This dramatically reduces processing time and improves diarization accuracy.
"""
from __future__ import annotations
import os
import tempfile
from typing import List, Dict, Any, Optional, Tuple
import torch
import torchaudio
import numpy as np


_VAD_MODEL = None
_VAD_UTILS = None


def _load_vad_model():
    """Load and cache Silero VAD model"""
    global _VAD_MODEL, _VAD_UTILS
    
    if _VAD_MODEL is not None:
        return _VAD_MODEL, _VAD_UTILS
    
    try:
        print("[VAD] Loading Silero VAD model...")
        from steps.common.model_provisioner import ensure_model_cached
        
        try:
            from steps.common.config_loader import load_configs
            offline_mode = load_configs({}).get("verification", {}).get("offline_mode", False)
        except Exception:
            offline_mode = False

        provision_result = ensure_model_cached("silero_vad", offline=offline_mode)
        if provision_result.status in ("offline_missing", "gated_unauthorized", "failed"):
            raise OSError(f"Failed to provision Silero VAD model: {provision_result.error or 'reason unknown'}")
            
        local_model_path = provision_result.local_path

        model, utils = torch.hub.load(
            repo_or_dir=local_model_path,
            model='silero_vad',
            source='local',
            force_reload=False,
            onnx=False
        )
        
        (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
        
        _VAD_MODEL = model
        _VAD_UTILS = {
            'get_speech_timestamps': get_speech_timestamps,
            'save_audio': save_audio,
            'read_audio': read_audio,
            'VADIterator': VADIterator,
            'collect_chunks': collect_chunks,
        }
        
        print("[VAD] [SYMBOL] Model loaded successfully")
        return model, _VAD_UTILS
        
    except Exception as e:
        print(f"[VAD] ERROR: Failed to load model: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None, None


def detect_speech_segments(
    audio_path: str,
    threshold: float = 0.5,
    min_speech_duration_ms: int = 400,
    min_silence_duration_ms: int = 200,
    sampling_rate: int = 16000,
) -> Optional[List[Dict[str, float]]]:
    """
    Detect speech segments in audio file using Silero VAD.
    
    Args:
        audio_path: Path to audio file
        threshold: Speech detection threshold (0.0-1.0). Higher = more strict.
                  0.5 is good default. Raise to 0.6-0.7 to ignore faint noise.
        min_speech_duration_ms: Minimum speech segment duration in ms
        min_silence_duration_ms: Minimum silence duration between segments in ms
        sampling_rate: Target sampling rate (VAD works at 16kHz)
    
    Returns:
        List of speech segments with 'start' and 'end' times in seconds,
        or None if VAD is not available or fails.
    """
    model, utils = _load_vad_model()
    if model is None or utils is None:
        print("[VAD] WARN: VAD not available, skipping pre-filtering")
        return None
    
    try:
        print(f"[VAD] Analyzing audio: {os.path.basename(audio_path)}")
        print(f"[VAD] Threshold: {threshold}, Min speech: {min_speech_duration_ms}ms, Min silence: {min_silence_duration_ms}ms")
        
        # Read audio
        read_audio = utils['read_audio']
        get_speech_timestamps = utils['get_speech_timestamps']
        
        wav = read_audio(audio_path, sampling_rate=sampling_rate)
        
        # Get speech timestamps
        speech_timestamps = get_speech_timestamps(
            wav,
            model,
            sampling_rate=sampling_rate,
            threshold=threshold,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            return_seconds=False  # Returns sample indices
        )
        
        if not speech_timestamps:
            print("[VAD] WARN: No speech detected in audio")
            return []
        
        # Convert sample indices to seconds
        segments = []
        for ts in speech_timestamps:
            start_sec = ts['start'] / sampling_rate
            end_sec = ts['end'] / sampling_rate
            duration_sec = end_sec - start_sec
            
            segments.append({
                'start': start_sec,
                'end': end_sec,
                'duration': duration_sec,
            })
        
        total_speech_duration = sum(seg['duration'] for seg in segments)
        total_audio_duration = len(wav) / sampling_rate
        speech_ratio = total_speech_duration / total_audio_duration if total_audio_duration > 0 else 0
        
        print(f"[VAD] [SYMBOL] Found {len(segments)} speech segments")
        print(f"[VAD] Total speech: {total_speech_duration/60:.1f}min of {total_audio_duration/60:.1f}min ({speech_ratio*100:.1f}%)")
        
        return segments
        
    except Exception as e:
        print(f"[VAD] ERROR: Failed to detect speech: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None


def extract_speech_only_audio(
    audio_path: str,
    output_path: str,
    speech_segments: List[Dict[str, float]],
    sampling_rate: int = 16000,
    padding_ms: int = 100,
) -> bool:
    """
    Extract only speech segments from audio and save to file.
    
    Args:
        audio_path: Path to input audio file
        output_path: Path to save speech-only audio
        speech_segments: List of speech segments from detect_speech_segments()
        sampling_rate: Sampling rate (16kHz for diarization)
        padding_ms: Padding around speech segments in milliseconds
    
    Returns:
        True if successful, False otherwise
    """
    model, utils = _load_vad_model()
    if model is None or utils is None:
        print("[VAD] WARN: VAD not available, cannot extract speech-only audio")
        return False
    
    try:
        read_audio = utils['read_audio']
        save_audio = utils['save_audio']
        
        # Read full audio
        wav = read_audio(audio_path, sampling_rate=sampling_rate)
        
        # Convert segments to sample indices with padding
        padding_samples = int(padding_ms * sampling_rate / 1000)
        speech_timestamps = []
        
        for seg in speech_segments:
            start_sample = max(0, int(seg['start'] * sampling_rate) - padding_samples)
            end_sample = min(len(wav), int(seg['end'] * sampling_rate) + padding_samples)
            speech_timestamps.append({
                'start': start_sample,
                'end': end_sample,
            })
        
        # Collect and concatenate speech chunks
        collect_chunks = utils['collect_chunks']
        speech_audio = collect_chunks(speech_timestamps, wav)
        
        # Save to file
        save_audio(output_path, speech_audio, sampling_rate=sampling_rate)
        
        # Verify output
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            print("[VAD] ERROR: Failed to save speech-only audio (empty file)")
            return False
        
        output_duration = len(speech_audio) / sampling_rate
        print(f"[VAD] [SYMBOL] Saved speech-only audio: {output_duration/60:.1f}min ({os.path.getsize(output_path)/(1024*1024):.1f}MB)")
        
        return True
        
    except Exception as e:
        print(f"[VAD] ERROR: Failed to extract speech-only audio: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False


def merge_adjacent_segments(
    segments: List[Dict[str, float]],
    max_gap_seconds: float = 1.0,
) -> List[Dict[str, float]]:
    """
    Merge speech segments that are close together to reduce fragmentation.
    
    Args:
        segments: List of speech segments
        max_gap_seconds: Maximum gap between segments to merge (seconds)
    
    Returns:
        Merged list of segments
    """
    if not segments:
        return []
    
    # Sort by start time
    sorted_segments = sorted(segments, key=lambda x: x['start'])
    
    merged = [sorted_segments[0].copy()]
    
    for seg in sorted_segments[1:]:
        last = merged[-1]
        gap = seg['start'] - last['end']
        
        if gap <= max_gap_seconds:
            # Merge with previous segment
            last['end'] = seg['end']
            last['duration'] = last['end'] - last['start']
        else:
            # Add as new segment
            merged.append(seg.copy())
    
    print(f"[VAD] Merged {len(segments)} segments → {len(merged)} segments (max gap: {max_gap_seconds}s)")
    
    return merged


def preprocess_audio_with_vad(
    audio_path: str,
    threshold: float = 0.5,
    min_speech_duration_ms: int = 400,
    min_silence_duration_ms: int = 200,
    merge_gap_seconds: float = 1.0,
    extract_to_file: bool = True,
) -> Tuple[Optional[str], Optional[List[Dict[str, float]]]]:
    """
    Full VAD preprocessing pipeline.
    
    Args:
        audio_path: Path to input audio
        threshold: Speech detection threshold (0.5 is good default)
        min_speech_duration_ms: Minimum speech segment duration
        min_silence_duration_ms: Minimum silence duration
        merge_gap_seconds: Maximum gap to merge adjacent segments
        extract_to_file: If True, extract speech-only audio to temp file
    
    Returns:
        Tuple of (speech_only_audio_path, speech_segments).
        If VAD fails or is disabled, returns (None, None).
    """
    print(f"[VAD] Preprocessing audio: {os.path.basename(audio_path)}")
    
    # Detect speech segments
    segments = detect_speech_segments(
        audio_path,
        threshold=threshold,
        min_speech_duration_ms=min_speech_duration_ms,
        min_silence_duration_ms=min_silence_duration_ms,
    )
    
    if segments is None:
        # VAD not available
        return None, None
    
    if not segments:
        # No speech detected
        print("[VAD] WARN: No speech detected, returning empty")
        return None, []
    
    # Merge adjacent segments to reduce fragmentation
    merged_segments = merge_adjacent_segments(segments, max_gap_seconds=merge_gap_seconds)
    
    if not extract_to_file:
        return None, merged_segments
    
    # Extract speech-only audio to temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_path = temp_file.name
    temp_file.close()
    
    success = extract_speech_only_audio(audio_path, temp_path, merged_segments)
    
    if not success:
        try:
            os.remove(temp_path)
        except Exception as e:
            # Swallowing removal error of temp_path as cleanup is on best-effort basis
            print(f"[VAD] Warning: Failed to remove temporary file {temp_path}: {e}")
        return None, merged_segments
    
    return temp_path, merged_segments


def calculate_time_savings(
    original_duration: float,
    speech_segments: List[Dict[str, float]],
) -> Dict[str, Any]:
    """
    Calculate time savings from VAD preprocessing.
    
    Args:
        original_duration: Original audio duration in seconds
        speech_segments: Speech segments from VAD
    
    Returns:
        Dictionary with savings metrics
    """
    if not speech_segments:
        return {
            'original_duration': original_duration,
            'speech_duration': 0.0,
            'time_saved': original_duration,
            'reduction_percent': 100.0,
        }
    
    speech_duration = sum(seg['duration'] for seg in speech_segments)
    time_saved = original_duration - speech_duration
    reduction_percent = (time_saved / original_duration * 100) if original_duration > 0 else 0
    
    return {
        'original_duration': original_duration,
        'speech_duration': speech_duration,
        'time_saved': time_saved,
        'reduction_percent': reduction_percent,
        'segment_count': len(speech_segments),
    }
