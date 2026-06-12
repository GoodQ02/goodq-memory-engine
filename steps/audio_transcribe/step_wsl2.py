"""
Audio transcription compatibility step.

This legacy step surface now delegates to the canonical unified WSL bridge.

.. deprecated:: transitional facade
   This module is a deprecated/transitional facade. Use the canonical unified
   WSL bridge instead.
"""

from __future__ import annotations
from typing import Any, Dict
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from wsl2_audio.audio_bridge import transcribe_wsl2

logger = logging.getLogger(__name__)


def audio_transcribe(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transcribe audio using WSL2-accelerated Whisper
    
    This delegates transcription to the canonical unified WSL bridge.
    
    .. deprecated:: transitional facade
       This function is deprecated. Use the canonical unified WSL bridge instead.
    
    Args:
        item: Item dict containing 'path' or 'audio_path'
        cfg: Configuration dict
        
    Returns:
        Dict with 'transcript' and 'transcript_segments'
    """
    import warnings
    warnings.warn(
        "audio_transcribe is deprecated and will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )
    audio_path = item.get("audio_path") or item.get("path")
    if not audio_path:
        logger.warning("No audio_path found in item")
        return {"transcript": "", "transcript_segments": []}
    
    if not os.path.isfile(audio_path):
        logger.warning(f"Audio file not found: {audio_path}")
        return {"transcript": "", "transcript_segments": []}

    run_cfg = cfg.get("run") if isinstance(cfg, dict) else None
    run_id = run_cfg.get("id") if isinstance(run_cfg, dict) else None

    logger.info(f"[TRANSCRIBE WSL2] Processing: {os.path.basename(audio_path)}")
    
    # Get transcription parameters from config
    audio_cfg = cfg.get("audio", {})
    transcribe_cfg = audio_cfg.get("transcribe", {})
    
    language = transcribe_cfg.get("language")  # None = auto-detect
    beam_size = transcribe_cfg.get("beam_size", 5)
    task = transcribe_cfg.get("task", "transcribe")  # or "translate"
    timeout = transcribe_cfg.get("timeout", 3600)  # 1 hour default
    
    # Submit to WSL2
    try:
        result = transcribe_wsl2(
            audio_path,
            language=language,
            task=task,
            beam_size=beam_size,
            timeout=timeout,
            run_id=run_id,
        )
        
        if result.get('status') == 'success':
            # Extract data in expected format
            transcript = result.get('full_text', '')
            segments = result.get('transcription', [])
            
            # Convert to expected format
            formatted_segments = []
            for seg in segments:
                formatted_segments.append({
                    "start": seg['start'],
                    "end": seg['end'],
                    "text": seg['text'],
                    "words": seg.get('words', [])
                })
            
            info = result.get('info', {})
            logger.info(f"[TRANSCRIBE WSL2] Complete: {info.get('duration', 0):.1f}s audio")
            logger.info(f"[TRANSCRIBE WSL2] RTF: {info.get('rtf', 0):.2f}x")
            logger.info(f"[TRANSCRIBE WSL2] Language: {info.get('language', 'unknown')}")
            
            return {
                "transcript": transcript,
                "transcript_segments": formatted_segments,
                "language": info.get('language'),
                "language_probability": info.get('language_probability'),
                "rtf": info.get('rtf')
            }
        else:
            # Handle error
            error = result.get('error', 'Unknown error')
            logger.error(f"[TRANSCRIBE WSL2] Failed: {error}")
            return {
                "transcript": "",
                "transcript_segments": [],
                "error": error
            }
    
    except Exception as e:
        logger.error(f"[TRANSCRIBE WSL2] Exception: {e}")
        return {
            "transcript": "",
            "transcript_segments": [],
            "error": str(e)
        }


# For backward compatibility
def run(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy entry point.
    
    .. deprecated:: transitional facade
       This function is deprecated. Use audio_transcribe or the canonical unified WSL bridge instead.
    """
    import warnings
    warnings.warn(
        "run is deprecated and will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )
    return audio_transcribe(item, cfg)

