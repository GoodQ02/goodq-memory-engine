"""
Phase 2: Pyannote Segmentation (GPU-accelerated speech activity detection)

Uses pyannote.audio segmentation model to:
- Detect speech activity at high resolution
- Identify overlapped speech
- Detect speaker change boundaries
- Generate timestamped labels for downstream diarization

This runs on GPU but is lightweight compared to full diarization.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import torch

logger = logging.getLogger(__name__)


def run_pyannote_segmentation(
    audio_path: str,
    vad_segments: List[Dict[str, Any]],
    output_dir: str,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Run Pyannote segmentation model on audio file.
    
    Args:
        audio_path: Path to normalized WAV file (16kHz mono)
        vad_segments: Output from Phase 1 VAD segmentation
        output_dir: Directory to store segmentation results
        config: Optional configuration overrides
        
    Returns:
        Dictionary containing:
        - segments: List of refined segments with pyannote labels
        - speaker_changes: List of detected speaker change timestamps
        - overlap_regions: List of overlapped speech regions
        - manifest_path: Path to saved JSON manifest
    """
    
    # Default configuration
    default_config = {
        'model': 'pyannote/segmentation-3.0',
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'min_duration_on': 0.3,  # Min speech duration (seconds)
        'min_duration_off': 0.3,  # Min silence duration (seconds)
        'overlap_threshold': 0.5,  # Overlap detection threshold
        'speaker_change_threshold': 0.5,  # Speaker change threshold
    }
    
    if config:
        default_config.update(config)
    cfg = default_config
    
    logger.info(f"Starting Pyannote segmentation on {audio_path}")
    logger.info(f"Device: {cfg['device']}")
    logger.info(f"Model: {cfg['model']}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Import pyannote (lazy import to avoid loading if not needed)
        from pyannote.audio import Model
        from pyannote.audio.pipelines import SpeakerSegmentation
        
        # Load model
        logger.info("Loading Pyannote segmentation model...")
        model = Model.from_pretrained(cfg['model'])
        
        # Create segmentation pipeline
        segmentation = SpeakerSegmentation(
            segmentation=model,
            device=torch.device(cfg['device'])
        )
        
        # Process audio file
        logger.info("Running segmentation inference...")
        from pyannote.audio import Audio
        audio = Audio(sample_rate=16000, mono=True)
        waveform, sample_rate = audio(audio_path)
        
        # Get segmentation output
        seg_output = segmentation({"waveform": waveform, "sample_rate": sample_rate})
        
        # Parse results
        refined_segments = []
        speaker_changes = []
        overlap_regions = []
        
        segment_id = 0
        for turn, _, speaker in seg_output.itertracks(yield_label=True):
            start = turn.start
            end = turn.end
            duration = end - start
            
            # Check for overlap with VAD segments
            vad_overlap = False
            for vad_seg in vad_segments:
                if not (end < vad_seg['start'] or start > vad_seg['end']):
                    vad_overlap = True
                    break
            
            # Detect speaker changes (consecutive segments with different speakers)
            if refined_segments and refined_segments[-1].get('speaker') != speaker:
                speaker_changes.append({
                    'timestamp': start,
                    'prev_speaker': refined_segments[-1].get('speaker'),
                    'next_speaker': speaker
                })
            
            segment = {
                'id': segment_id,
                'start': float(start),
                'end': float(end),
                'duration': float(duration),
                'speaker': speaker if speaker else f"SPEAKER_{segment_id}",
                'vad_confirmed': vad_overlap,
                'pyannote_confidence': 1.0,  # Pyannote doesn't provide confidence directly
            }
            
            refined_segments.append(segment)
            segment_id += 1
        
        # Detect overlapped speech regions
        # (Simplified: look for temporal overlaps in segments)
        for i, seg1 in enumerate(refined_segments):
            for seg2 in refined_segments[i+1:]:
                if seg1['end'] > seg2['start'] and seg1['start'] < seg2['end']:
                    overlap_regions.append({
                        'start': max(seg1['start'], seg2['start']),
                        'end': min(seg1['end'], seg2['end']),
                        'speakers': [seg1['speaker'], seg2['speaker']]
                    })
        
        # Create result manifest
        result = {
            'audio_path': audio_path,
            'model': cfg['model'],
            'device': cfg['device'],
            'num_segments': len(refined_segments),
            'segments': refined_segments,
            'speaker_changes': speaker_changes,
            'overlap_regions': overlap_regions,
            'total_speech_duration': sum(s['duration'] for s in refined_segments),
        }
        
        # Save manifest
        manifest_path = os.path.join(output_dir, 'pyannote_segmentation.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Pyannote segmentation complete: {len(refined_segments)} segments")
        logger.info(f"Speaker changes detected: {len(speaker_changes)}")
        logger.info(f"Overlap regions detected: {len(overlap_regions)}")
        logger.info(f"Manifest saved to: {manifest_path}")
        
        result['manifest_path'] = manifest_path
        return result
        
    except ImportError as e:
        logger.error(f"Pyannote.audio not available: {e}")
        logger.error("Install with: pip install pyannote.audio")
        
        # Fallback: return VAD segments as-is with warning
        logger.warning("Falling back to VAD-only segmentation")
        fallback_result = {
            'audio_path': audio_path,
            'model': 'FALLBACK_VAD_ONLY',
            'device': 'N/A',
            'num_segments': len(vad_segments),
            'segments': vad_segments,
            'speaker_changes': [],
            'overlap_regions': [],
            'total_speech_duration': sum(s['duration'] for s in vad_segments),
            'warning': 'Pyannote not available, using VAD segments only'
        }
        
        manifest_path = os.path.join(output_dir, 'pyannote_segmentation.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(fallback_result, f, indent=2, ensure_ascii=False)
        
        fallback_result['manifest_path'] = manifest_path
        return fallback_result
        
    except Exception as e:
        logger.error(f"Pyannote segmentation failed: {e}", exc_info=True)
        raise


def merge_vad_and_pyannote(
    vad_segments: List[Dict[str, Any]],
    pyannote_segments: List[Dict[str, Any]],
    merge_strategy: str = 'pyannote_priority'
) -> List[Dict[str, Any]]:
    """
    Merge VAD and Pyannote segments into unified timeline.
    
    Args:
        vad_segments: WebRTC VAD segments
        pyannote_segments: Pyannote refined segments
        merge_strategy: 'pyannote_priority' | 'vad_priority' | 'intersection'
        
    Returns:
        Merged segment list
    """
    
    if merge_strategy == 'pyannote_priority':
        # Use Pyannote segments, validate against VAD
        merged = []
        for pseg in pyannote_segments:
            vad_support = any(
                not (pseg['end'] < vseg['start'] or pseg['start'] > vseg['end'])
                for vseg in vad_segments
            )
            merged.append({
                **pseg,
                'vad_confirmed': vad_support
            })
        return merged
    
    elif merge_strategy == 'vad_priority':
        # Use VAD segments, enrich with Pyannote speaker info
        merged = []
        for vseg in vad_segments:
            # Find overlapping Pyannote segment
            speaker = None
            for pseg in pyannote_segments:
                if not (vseg['end'] < pseg['start'] or vseg['start'] > pseg['end']):
                    speaker = pseg.get('speaker')
                    break
            
            merged.append({
                **vseg,
                'speaker': speaker,
                'pyannote_confirmed': speaker is not None
            })
        return merged
    
    elif merge_strategy == 'intersection':
        # Only keep segments confirmed by BOTH VAD and Pyannote
        merged = []
        for pseg in pyannote_segments:
            for vseg in vad_segments:
                # Check for overlap
                if not (pseg['end'] < vseg['start'] or pseg['start'] > vseg['end']):
                    # Compute intersection
                    start = max(pseg['start'], vseg['start'])
                    end = min(pseg['end'], vseg['end'])
                    
                    merged.append({
                        'start': start,
                        'end': end,
                        'duration': end - start,
                        'speaker': pseg.get('speaker'),
                        'vad_confidence': vseg.get('confidence', 1.0),
                        'pyannote_confirmed': True,
                        'vad_confirmed': True
                    })
        return merged
    
    else:
        raise ValueError(f"Unknown merge strategy: {merge_strategy}")


if __name__ == '__main__':
    # Test/demo mode
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python phase2_pyannote.py <audio.wav> <output_dir> [vad_manifest.json]")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    output_dir = sys.argv[2]
    vad_manifest = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Load VAD segments if provided
    vad_segments = []
    if vad_manifest and os.path.exists(vad_manifest):
        with open(vad_manifest, 'r') as f:
            vad_data = json.load(f)
            vad_segments = vad_data.get('segments', [])
    
    # Run segmentation
    logging.basicConfig(level=logging.INFO)
    result = run_pyannote_segmentation(audio_path, vad_segments, output_dir)
    
    print(f"\n✓ Pyannote segmentation complete")
    print(f"  Segments: {result['num_segments']}")
    print(f"  Speaker changes: {len(result['speaker_changes'])}")
    print(f"  Overlaps: {len(result['overlap_regions'])}")
    print(f"  Manifest: {result['manifest_path']}")
