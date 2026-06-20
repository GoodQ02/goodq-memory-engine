"""
Shared Voice Activity Detection (VAD) Preprocessor

Uses Silero VAD to filter silence and non-speech audio before processing.
This dramatically reduces processing time and improves accuracy.
"""

import torch
import torchaudio
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import time


_VAD_MODEL = None


def get_vad_model():
    """Load and cache Silero VAD model"""
    global _VAD_MODEL
    if _VAD_MODEL is None:
        try:
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
            _VAD_MODEL = (model, utils)
            print("[VAD] Silero VAD model loaded successfully")
        except Exception as e:
            print(f"[VAD] ERROR loading Silero VAD: {e}")
            raise
    return _VAD_MODEL


def preprocess_audio_with_vad(
    audio_path: str,
    threshold: float = 0.5,
    min_speech_duration_ms: int = 400,
    min_silence_duration_ms: int = 200,
    merge_gap_seconds: float = 1.0,
    extract_to_file: bool = True,
    output_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """
    Preprocess audio using Silero VAD to extract speech/sound regions.
    
    Args:
        audio_path: Path to input audio file
        threshold: VAD threshold (0.3-0.7, higher = stricter)
        min_speech_duration_ms: Minimum speech segment duration
        min_silence_duration_ms: Minimum silence duration to split
        merge_gap_seconds: Merge segments with gaps smaller than this
        extract_to_file: If True, save filtered audio to file
        output_path: Optional output path (auto-generated if None)
    
    Returns:
        Tuple of (filtered_audio_path, vad_segments)
        Returns (None, None) if VAD fails or finds no speech
    """
    try:
        start_time = time.time()
        
        # Load VAD model
        model, utils = get_vad_model()
        get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks = utils
        
        # Read audio
        wav = read_audio(audio_path, sampling_rate=16000)
        
        # Get speech timestamps
        speech_timestamps = get_speech_timestamps(
            wav,
            model,
            sampling_rate=16000,
            threshold=threshold,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            return_seconds=False  # Returns samples
        )
        
        if not speech_timestamps:
            print(f"[VAD] No speech detected in {audio_path}")
            return None, None
        
        # Merge nearby segments
        merged_segments = []
        merge_gap_samples = int(merge_gap_seconds * 16000)
        
        current_seg = speech_timestamps[0].copy()
        for seg in speech_timestamps[1:]:
            if seg['start'] - current_seg['end'] <= merge_gap_samples:
                # Merge
                current_seg['end'] = seg['end']
            else:
                merged_segments.append(current_seg)
                current_seg = seg.copy()
        merged_segments.append(current_seg)
        
        # Calculate statistics
        total_speech_samples = sum(seg['end'] - seg['start'] for seg in merged_segments)
        total_samples = len(wav)
        speech_ratio = total_speech_samples / total_samples if total_samples > 0 else 0
        
        print(f"[VAD] Found {len(merged_segments)} speech segments")
        print(f"[VAD] Speech ratio: {speech_ratio*100:.1f}%")
        print(f"[VAD] Processing time: {time.time() - start_time:.2f}s")
        
        # Extract to file if requested
        filtered_path = None
        if extract_to_file:
            if output_path is None:
                output_path = str(Path(tempfile.gettempdir()) / f"vad_{Path(audio_path).stem}.wav")
            
            # Collect and save speech chunks
            speech_audio = collect_chunks(merged_segments, wav)
            save_audio(output_path, speech_audio, sampling_rate=16000)
            filtered_path = output_path
            print(f"[VAD] Saved filtered audio: {filtered_path}")
        
        # Convert segments to seconds for easy use
        segments_seconds = [
            {
                'start': seg['start'] / 16000,
                'end': seg['end'] / 16000,
                'duration': (seg['end'] - seg['start']) / 16000
            }
            for seg in merged_segments
        ]
        
        return filtered_path, segments_seconds
        
    except Exception as e:
        print(f"[VAD] ERROR during preprocessing: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def calculate_time_savings(original_duration: float, vad_segments: List[Dict]) -> Dict:
    """Calculate time savings from VAD preprocessing"""
    if not vad_segments:
        return {
            'original_duration': original_duration,
            'speech_duration': 0,
            'time_saved': original_duration,
            'reduction_percent': 100.0
        }
    
    speech_duration = sum(seg['duration'] for seg in vad_segments)
    time_saved = original_duration - speech_duration
    reduction_percent = (time_saved / original_duration * 100) if original_duration > 0 else 0
    
    return {
        'original_duration': original_duration,
        'speech_duration': speech_duration,
        'time_saved': time_saved,
        'reduction_percent': reduction_percent
    }
