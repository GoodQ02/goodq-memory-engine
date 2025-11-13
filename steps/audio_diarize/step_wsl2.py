"""
Audio Diarization Step - WSL2 Accelerated Version

This version offloads diarization to WSL2 for better GPU utilization
and VAD preprocessing.
"""

from __future__ import annotations
from typing import Any, Dict, List
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from wsl2_audio.audio_bridge import transcribe_and_diarize_wsl2

logger = logging.getLogger(__name__)


def audio_diarize(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform speaker diarization using WSL2-accelerated PyAnnote
    
    This offloads both transcription and diarization to the WSL2 audio service
    which uses VAD preprocessing and full GPU acceleration.
    
    Args:
        item: Item dict containing 'path' or 'audio_path'
        cfg: Configuration dict
        
    Returns:
        Dict with diarization segments and speaker info
    """
    audio_path = item.get("audio_path") or item.get("path")
    if not audio_path:
        logger.warning("No audio_path found in item")
        return {"diarization": [], "speakers": []}
    
    if not os.path.isfile(audio_path):
        logger.warning(f"Audio file not found: {audio_path}")
        return {"diarization": [], "speakers": []}
    
    logger.info(f"[DIARIZE WSL2] Processing: {os.path.basename(audio_path)}")
    
    # Get parameters from config
    audio_cfg = cfg.get("audio", {})
    transcribe_cfg = audio_cfg.get("transcribe", {})
    diarize_cfg = audio_cfg.get("diarize", {})
    
    language = transcribe_cfg.get("language")
    beam_size = transcribe_cfg.get("beam_size", 5)
    timeout = diarize_cfg.get("timeout", 7200)  # 2 hours default (diarization is slower)
    
    # Submit to WSL2 for both transcription and diarization
    try:
        result = transcribe_and_diarize_wsl2(
            audio_path,
            language=language,
            beam_size=beam_size,
            timeout=timeout
        )
        
        if result.get('status') == 'success':
            # Extract diarization data
            diarization = result.get('diarization', [])
            speaker_count = result.get('speaker_count', 0)
            transcription = result.get('transcription', [])
            
            # Merge transcription with diarization
            merged_segments = _merge_transcription_diarization(transcription, diarization)
            
            # Extract unique speakers
            speakers = _extract_speakers(diarization)
            
            logger.info(f"[DIARIZE WSL2] Complete: {speaker_count} speakers, {len(diarization)} segments")
            
            return {
                "diarization": merged_segments,
                "speakers": speakers,
                "speaker_count": speaker_count,
                "transcript": result.get('full_text', ''),
                "transcript_segments": transcription
            }
        else:
            # Handle error
            error = result.get('error', 'Unknown error')
            logger.error(f"[DIARIZE WSL2] Failed: {error}")
            return {
                "diarization": [],
                "speakers": [],
                "error": error
            }
    
    except Exception as e:
        logger.error(f"[DIARIZE WSL2] Exception: {e}")
        return {
            "diarization": [],
            "speakers": [],
            "error": str(e)
        }


def _merge_transcription_diarization(
    transcription: List[Dict],
    diarization: List[Dict]
) -> List[Dict]:
    """
    Merge transcription segments with speaker diarization
    
    Args:
        transcription: List of transcript segments with timestamps
        diarization: List of speaker segments with timestamps
        
    Returns:
        List of merged segments with speaker labels
    """
    merged = []
    
    for trans_seg in transcription:
        trans_start = trans_seg['start']
        trans_end = trans_seg['end']
        trans_mid = (trans_start + trans_end) / 2
        
        # Find overlapping speaker
        speaker = "UNKNOWN"
        max_overlap = 0
        
        for diar_seg in diarization:
            diar_start = diar_seg['start']
            diar_end = diar_seg['end']
            
            # Calculate overlap
            overlap_start = max(trans_start, diar_start)
            overlap_end = min(trans_end, diar_end)
            overlap = max(0, overlap_end - overlap_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                speaker = diar_seg['speaker']
        
        merged.append({
            "start": trans_start,
            "end": trans_end,
            "text": trans_seg['text'],
            "speaker": speaker,
            "words": trans_seg.get('words', [])
        })
    
    return merged


def _extract_speakers(diarization: List[Dict]) -> List[Dict]:
    """
    Extract unique speaker information
    
    Args:
        diarization: List of diarization segments
        
    Returns:
        List of speaker dicts with statistics
    """
    speakers_data = {}
    
    for seg in diarization:
        speaker = seg['speaker']
        duration = seg['duration']
        
        if speaker not in speakers_data:
            speakers_data[speaker] = {
                "speaker_id": speaker,
                "total_duration": 0,
                "segment_count": 0
            }
        
        speakers_data[speaker]['total_duration'] += duration
        speakers_data[speaker]['segment_count'] += 1
    
    # Convert to list and sort by total duration
    speakers = list(speakers_data.values())
    speakers.sort(key=lambda x: x['total_duration'], reverse=True)
    
    return speakers


# For backward compatibility
def run(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy entry point"""
    return audio_diarize(item, cfg)
