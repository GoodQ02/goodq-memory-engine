"""
WSL2 Audio Bridge Step - Replaces legacy audio steps with WSL2-accelerated versions

This module provides drop-in replacements for:
- audio_diarize
- audio_transcribe  
- audio_emotion

All processing is offloaded to WSL2 with GPU acceleration.
"""

import logging
import sys
from pathlib import Path

# Add wsl2_audio to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'wsl2_audio'))

from audio_bridge import WSL2AudioBridge

logger = logging.getLogger(__name__)


def audio_diarize_wsl2(audio_path: str, **kwargs) -> dict:
    """
    GPU-accelerated speaker diarization via WSL2
    
    Args:
        audio_path: Path to audio file
        **kwargs: Additional parameters
        
    Returns:
        dict with speaker segments and timestamps
    """
    logger.info(f"[WSL2] Running GPU-accelerated diarization: {audio_path}")
    
    bridge = WSL2AudioBridge()
    
    job_spec = {
        'task': 'diarize',
        'audio_path': str(audio_path),
        'params': kwargs
    }
    
    result = bridge.submit_job(job_spec)
    
    if result.get('status') == 'success':
        logger.info(f"[WSL2] Diarization complete - {len(result.get('speakers', []))} speakers found")
        return result
    else:
        error_msg = result.get('error', 'Unknown error')
        logger.error(f"[WSL2] Diarization failed: {error_msg}")
        return {'error': error_msg, 'speakers': []}


def audio_transcribe_wsl2(audio_path: str, **kwargs) -> dict:
    """
    GPU-accelerated transcription via WSL2 (Faster Whisper)
    
    Args:
        audio_path: Path to audio file
        **kwargs: Additional parameters (model, language, etc.)
        
    Returns:
        dict with transcript and word-level timestamps
    """
    logger.info(f"[WSL2] Running GPU-accelerated transcription: {audio_path}")
    
    bridge = WSL2AudioBridge()
    
    job_spec = {
        'task': 'transcribe',
        'audio_path': str(audio_path),
        'params': {
            'model': kwargs.get('model', 'large-v3'),
            'language': kwargs.get('language', 'en'),
            **kwargs
        }
    }
    
    result = bridge.submit_job(job_spec)
    
    if result.get('status') == 'success':
        transcript = result.get('transcript', '')
        word_count = len(transcript.split())
        logger.info(f"[WSL2] Transcription complete - {word_count} words")
        return result
    else:
        error_msg = result.get('error', 'Unknown error')
        logger.error(f"[WSL2] Transcription failed: {error_msg}")
        return {'error': error_msg, 'transcript': ''}


def audio_emotion_wsl2(audio_path: str, **kwargs) -> dict:
    """
    GPU-accelerated emotion detection via WSL2
    
    Args:
        audio_path: Path to audio file
        **kwargs: Additional parameters
        
    Returns:
        dict with emotion labels and confidence scores
    """
    logger.info(f"[WSL2] Running GPU-accelerated emotion detection: {audio_path}")
    
    bridge = WSL2AudioBridge()
    
    job_spec = {
        'task': 'emotion',
        'audio_path': str(audio_path),
        'params': kwargs
    }
    
    result = bridge.submit_job(job_spec)
    
    if result.get('status') == 'success':
        emotions = result.get('emotions', {})
        logger.info(f"[WSL2] Emotion detection complete - {len(emotions)} segments")
        return result
    else:
        error_msg = result.get('error', 'Unknown error')
        logger.error(f"[WSL2] Emotion detection failed: {error_msg}")
        return {'error': error_msg, 'emotions': {}}


# Provide backwards-compatible function names
audio_diarize = audio_diarize_wsl2
audio_transcribe = audio_transcribe_wsl2
audio_emotion = audio_emotion_wsl2
