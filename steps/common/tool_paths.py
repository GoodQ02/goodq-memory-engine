from __future__ import annotations
import os
from typing import Any, Dict, Optional


def cfg_get(cfg: Dict[str, Any], path: str, default: Optional[str] = None) -> Optional[str]:
    cur: Any = cfg
    for key in path.split('.'):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur if isinstance(cur, str) else default


def resolve_piper(cfg: Dict[str, Any]) -> (Optional[str], Optional[str], Optional[str]):
    # Prefer explicit tts config, fallback to tools section
    exe = cfg_get(cfg, 'config.tts.piper_exe') or cfg_get(cfg, 'config.tools.piper_exe')
    voice = cfg_get(cfg, 'config.tts.voice_path') or cfg_get(cfg, 'config.tools.piper_voice')
    out_dir = cfg_get(cfg, 'config.tts.out_dir') or (os.path.dirname(exe) if exe else None)
    return exe, voice, out_dir


def resolve_tesseract(cfg: Dict[str, Any]) -> Optional[str]:
    return cfg_get(cfg, 'config.tools.tesseract_exe')


def resolve_ffmpeg(cfg: Dict[str, Any]) -> Optional[str]:
    return cfg_get(cfg, 'config.tools.ffmpeg_exe')

