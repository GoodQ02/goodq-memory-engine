#!/usr/bin/env python3
"""
Comprehensive VAD Implementation Across All Audio Steps

This script implements Silero VAD preprocessing for ALL audio processing steps
to eliminate wasted GPU cycles on silence and background noise.

Steps to update:
1. audio_diarize - DONE ✓
2. audio_transcribe - DONE (uses Whisper's VAD) ✓  
3. audio_emotion - NEEDS VAD
4. audio_embed_clap - NEEDS VAD
5. audio_music_events - NEEDS VAD
6. audio_time_hints - NEEDS VAD (if applicable)

Strategy:
- Create a shared VAD preprocessor module
- Each step imports and uses it before processing
- VAD segments are cached to avoid re-computation
- Progress tracking for VAD preprocessing
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_vad_implementation():
    """Check which audio steps have VAD implemented"""
    steps_dir = project_root / "steps"
    audio_steps = [
        "audio_diarize",
        "audio_transcribe",
        "audio_emotion",
        "audio_embed_clap",
        "audio_music_events",
        "audio_time_hints",
    ]
    
    print("=" * 80)
    print("VAD Implementation Status Check")
    print("=" * 80)
    print()
    
    results = {}
    for step_name in audio_steps:
        step_dir = steps_dir / step_name
        step_file = step_dir / "step.py"
        
        if not step_file.exists():
            results[step_name] = "MISSING"
            continue
            
        content = step_file.read_text()
        has_vad = ("vad" in content.lower() or "silero" in content.lower())
        results[step_name] = "✓ HAS VAD" if has_vad else "✗ NEEDS VAD"
    
    for step_name, status in results.items():
        print(f"  {step_name:25s} {status}")
    
    print()
    print("=" * 80)
    return results


def create_shared_vad_module():
    """Create a shared VAD preprocessing module for all audio steps"""
    
    vad_module_path = project_root / "steps" / "common" / "vad_preprocessor.py"
    
    # Check if already exists
    if vad_module_path.exists():
        print(f"✓ VAD module already exists: {vad_module_path}")
        return True
    
    vad_code = '''"""
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
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
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
'''
    
    print(f"Creating shared VAD module: {vad_module_path}")
    vad_module_path.write_text(vad_code)
    print("✓ VAD module created successfully")
    return True


def implement_vad_in_step(step_name: str):
    """Implement VAD preprocessing in a specific audio step"""
    
    step_file = project_root / "steps" / step_name / "step.py"
    if not step_file.exists():
        print(f"✗ Step file not found: {step_file}")
        return False
    
    content = step_file.read_text()
    
    # Check if already has VAD
    if "vad" in content.lower() or "silero" in content.lower():
        print(f"  {step_name}: Already has VAD, skipping")
        return True
    
    print(f"  {step_name}: Implementing VAD preprocessing...")
    
    # Implementation depends on step - create a backup first
    backup_file = step_file.with_suffix('.py.backup_pre_vad')
    backup_file.write_text(content)
    print(f"    ✓ Backup created: {backup_file.name}")
    
    # TODO: Add VAD implementation based on step type
    print(f"    ! Manual implementation required for {step_name}")
    print(f"      Add VAD preprocessing before main processing:")
    print(f"      from steps.common.vad_preprocessor import preprocess_audio_with_vad")
    
    return True


def main():
    print()
    print("=" * 80)
    print("GoodQ4All - Comprehensive VAD Implementation")
    print("=" * 80)
    print()
    
    # Step 1: Check current status
    print("Step 1: Checking current VAD implementation status...")
    results = check_vad_implementation()
    print()
    
    # Step 2: Create shared VAD module
    print("Step 2: Creating shared VAD preprocessor module...")
    create_shared_vad_module()
    print()
    
    # Step 3: Implement VAD in steps that need it
    print("Step 3: Implementing VAD in audio steps...")
    steps_needing_vad = [
        step for step, status in results.items()
        if "NEEDS VAD" in status
    ]
    
    if not steps_needing_vad:
        print("  ✓ All audio steps already have VAD!")
    else:
        for step_name in steps_needing_vad:
            implement_vad_in_step(step_name)
    
    print()
    print("=" * 80)
    print("VAD Implementation Plan Complete")
    print("=" * 80)
    print()
    print("Next Steps:")
    print("  1. Review the backup files created")
    print("  2. Manually add VAD preprocessing to steps that need it")
    print("  3. Test each step with VAD enabled")
    print("  4. Monitor GPU usage and processing time improvements")
    print()


if __name__ == "__main__":
    main()
