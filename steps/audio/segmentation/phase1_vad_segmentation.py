"""
Phase 1: WebRTC-VAD Segmentation (CPU-based)
Lightweight voice activity detection to create initial speech/non-speech segments
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import wave
import struct

try:
    import webrtcvad
except ImportError:
    webrtcvad = None


def segment_with_webrtc_vad(
    audio_path: str,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Segment audio using WebRTC VAD
    
    Args:
        audio_path: Path to normalized WAV file (16kHz, 16-bit, mono)
        config: Optional configuration for VAD
        
    Returns:
        List of segments with start/end times and speech flag
    """
    if webrtcvad is None:
        print("[PHASE1-ERROR] webrtcvad not installed, returning full file as single segment")
        return _fallback_full_segment(audio_path)
    
    config = config or {}
    
    # VAD configuration
    aggressiveness = config.get('aggressiveness', 3)  # 0-3
    frame_duration_ms = config.get('frame_duration_ms', 30)  # 10, 20, or 30
    min_speech_duration = config.get('min_speech_duration', 0.3)  # seconds
    min_silence_duration = config.get('min_silence_duration', 0.5)  # seconds
    padding_duration = config.get('padding_duration', 0.1)  # seconds
    
    print(f"[PHASE1] Running WebRTC-VAD on: {audio_path}")
    print(f"[PHASE1] Aggressiveness: {aggressiveness}")
    print(f"[PHASE1] Frame duration: {frame_duration_ms}ms")
    
    # Initialize VAD
    vad = webrtcvad.Vad(aggressiveness)
    
    # Open WAV file
    try:
        with wave.open(audio_path, 'rb') as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            
            # Validate format
            if sample_rate not in [8000, 16000, 32000, 48000]:
                print(f"[PHASE1-ERROR] Invalid sample rate: {sample_rate}. Must be 8000, 16000, 32000, or 48000")
                return _fallback_full_segment(audio_path)
            
            if channels != 1:
                print(f"[PHASE1-ERROR] Invalid channel count: {channels}. Must be mono (1)")
                return _fallback_full_segment(audio_path)
            
            if sample_width != 2:
                print(f"[PHASE1-ERROR] Invalid sample width: {sample_width}. Must be 16-bit (2 bytes)")
                return _fallback_full_segment(audio_path)
            
            # Calculate frame size in bytes
            frame_size = int(sample_rate * frame_duration_ms / 1000)
            frame_bytes = frame_size * sample_width
            
            # Read all frames
            audio_data = wf.readframes(wf.getnframes())
            
    except Exception as e:
        print(f"[PHASE1-ERROR] Failed to read audio file: {e}")
        return _fallback_full_segment(audio_path)
    
    # Process frames
    segments = []
    is_speech = False
    speech_start = None
    speech_frames = []
    silence_frames = 0
    
    num_frames = len(audio_data) // frame_bytes
    min_speech_frames = int(min_speech_duration * sample_rate / frame_size)
    min_silence_frames = int(min_silence_duration * sample_rate / frame_size)
    
    print(f"[PHASE1] Processing {num_frames} frames...")
    
    for i in range(num_frames):
        offset = i * frame_bytes
        frame = audio_data[offset:offset + frame_bytes]
        
        if len(frame) < frame_bytes:
            break
        
        # Check if frame contains speech
        try:
            frame_is_speech = vad.is_speech(frame, sample_rate)
        except Exception:
            frame_is_speech = False
        
        timestamp = i * frame_duration_ms / 1000.0
        
        if frame_is_speech:
            if not is_speech:
                # Speech started
                speech_start = timestamp
                is_speech = True
                silence_frames = 0
            speech_frames.append(i)
        else:
            if is_speech:
                silence_frames += 1
                
                # Check if silence long enough to end segment
                if silence_frames >= min_silence_frames:
                    # Speech ended
                    speech_end = timestamp
                    
                    # Check if segment long enough
                    if len(speech_frames) >= min_speech_frames:
                        segments.append({
                            'start': max(0, speech_start - padding_duration),
                            'end': speech_end + padding_duration,
                            'vad_speech': True
                        })
                    
                    is_speech = False
                    speech_start = None
                    speech_frames = []
                    silence_frames = 0
    
    # Handle final segment
    if is_speech and len(speech_frames) >= min_speech_frames:
        segments.append({
            'start': max(0, speech_start - padding_duration),
            'end': (num_frames * frame_duration_ms / 1000.0) + padding_duration,
            'vad_speech': True
        })
    
    print(f"[PHASE1] Detected {len(segments)} speech segments")
    
    # Fill gaps with non-speech segments
    filled_segments = _fill_gaps(segments, num_frames * frame_duration_ms / 1000.0)
    
    print(f"[PHASE1] Total segments (with silence): {len(filled_segments)}")
    
    return filled_segments


def _fill_gaps(
    speech_segments: List[Dict[str, Any]],
    total_duration: float
) -> List[Dict[str, Any]]:
    """
    Fill gaps between speech segments with non-speech segments
    
    Args:
        speech_segments: List of speech segments
        total_duration: Total audio duration
        
    Returns:
        Combined list with both speech and non-speech segments
    """
    if not speech_segments:
        return [{
            'start': 0.0,
            'end': total_duration,
            'vad_speech': False
        }]
    
    filled = []
    current_time = 0.0
    
    for segment in speech_segments:
        # Add non-speech segment if there's a gap
        if current_time < segment['start']:
            filled.append({
                'start': current_time,
                'end': segment['start'],
                'vad_speech': False
            })
        
        # Add speech segment
        filled.append(segment)
        current_time = segment['end']
    
    # Add final non-speech segment if needed
    if current_time < total_duration:
        filled.append({
            'start': current_time,
            'end': total_duration,
            'vad_speech': False
        })
    
    return filled


def _fallback_full_segment(audio_path: str) -> List[Dict[str, Any]]:
    """
    Fallback: return entire file as single segment
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Single segment spanning entire file
    """
    try:
        with wave.open(audio_path, 'rb') as wf:
            duration = wf.getnframes() / wf.getframerate()
    except Exception:
        duration = 0.0
    
    return [{
        'start': 0.0,
        'end': duration,
        'vad_speech': True,  # Assume speech
        'fallback': True
    }]


if __name__ == '__main__':
    print("Phase 1: WebRTC-VAD Segmentation Module")
    print("=" * 60)
    print("Lightweight CPU-based voice activity detection")
