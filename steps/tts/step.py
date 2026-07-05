"""
Deprecated Text-To-Speech (TTS) Step Module
===========================================

This module is formally DEPRECATED.

Callers should instead make direct text-to-speech service calls to:
- Local LAN Piper instance
- ElevenLabs API

TODO: Remove this module completely once config keys are fully migrated
and no longer mandatory.
"""

import warnings
from typing import Dict, Any, Optional

# Formal deprecation notice on module import
warnings.warn(
    "The steps.tts.step module is deprecated. Use direct LAN Piper or ElevenLabs service calls instead.",
    DeprecationWarning,
    stacklevel=2
)


def run_tts(text: str, cfg: Dict[str, Any]) -> Optional[str]:
    """
    Deprecated placeholder runner for TTS step.
    
    Args:
        text: Text to synthesize.
        cfg: Configuration dictionary.
        
    Returns:
        None, pointing callers to LAN Piper / ElevenLabs services.
    """
    warnings.warn(
        "run_tts is deprecated. Use direct LAN Piper or ElevenLabs service calls instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return None
