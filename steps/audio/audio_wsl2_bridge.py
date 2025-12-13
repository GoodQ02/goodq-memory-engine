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

# Add scripts to path for bridge import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'scripts'))

from wsl2_audio_bridge import WSL2AudioBridge

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
    
    # Get audio duration for dynamic timeout if available
    audio_duration = kwargs.get('duration', None)
    timeout = kwargs.get('timeout', None)
    
    result = bridge.process_audio(audio_path, timeout=timeout, audio_duration=audio_duration)
    
    if result.get('status') == 'success':
        logger.info(f"[WSL2] Diarization complete")
        # Extract diarization data from result
        return {
            'speakers': result.get('speakers', []),
            'speaker_segments': result.get('speaker_segments', [])
        }
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
    result = bridge.process_audio(audio_path, timeout=kwargs.get('timeout', 3600))
    
    if result.get('status') == 'success':
        transcript = result.get('full_text', '')
        word_count = len(transcript.split())
        logger.info(f"[WSL2] Transcription complete - {word_count} words")
        return {
            'transcript': transcript,
            'full_text': transcript,
            'segments': result.get('segments', []),
            'words': result.get('words', [])
        }
    else:
        error_msg = result.get('error', 'Unknown error')
        logger.error(f"[WSL2] Transcription failed: {error_msg}")
        return {'error': error_msg, 'transcript': '', 'full_text': ''}


def audio_emotion_wsl2(audio_path: str, **kwargs) -> dict:
    """
    GPU-accelerated emotion detection via WSL2
    
    Note: Emotion detection not yet implemented in WSL2 stack
    Returns placeholder for now
    
    Args:
        audio_path: Path to audio file
        **kwargs: Additional parameters
        
    Returns:
        dict with emotion labels and confidence scores
    """
    logger.warning(f"[WSL2] Emotion detection not yet implemented - returning placeholder")
    
    # TODO: Implement emotion detection in WSL2 stack
    return {
        'status': 'success',
        'emotions': {},
        'note': 'Emotion detection not yet implemented in WSL2 stack'
    }


# Provide backwards-compatible function names
audio_diarize = audio_diarize_wsl2
audio_transcribe = audio_transcribe_wsl2
audio_emotion = audio_emotion_wsl2
