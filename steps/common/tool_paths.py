from __future__ import annotations
import os
import logging
import shutil
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)
_IMAGEIO_FFMPEG_FALLBACK_WARNED = False

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
    global _IMAGEIO_FFMPEG_FALLBACK_WARNED
    configured = cfg_get(cfg, 'config.tools.ffmpeg_exe')
    if configured:
        # Cross-host guard: reject Windows launchers on non-Windows hosts.
        if os.name != 'nt' and configured.lower().endswith(('.exe', '.bat', '.cmd')):
            logger.warning(
                "tool_paths fallback: rejecting_windows_ffmpeg_launcher_on_non_windows ffmpeg_exe=%s",
                configured,
            )
        elif os.path.isfile(configured):
            return configured
    # Fallback: use ffmpeg on PATH if available
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # Python-package fallback: imageio-ffmpeg bundles a platform-appropriate binary.
    try:
        import imageio_ffmpeg

        bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled_ffmpeg and os.path.isfile(bundled_ffmpeg):
            if not _IMAGEIO_FFMPEG_FALLBACK_WARNED:
                logger.warning(
                    "tool_paths fallback: using_imageio_ffmpeg_binary ffmpeg_exe=%s",
                    bundled_ffmpeg,
                )
                _IMAGEIO_FFMPEG_FALLBACK_WARNED = True
            return bundled_ffmpeg
    except Exception as e:
        logger.debug(
            "tool_paths debug: imageio_ffmpeg_unavailable operation=%s exc_type=%s exc=%s",
            "resolve_ffmpeg",
            type(e).__name__,
            e,
        )
    return None


def resolve_conda() -> str:
    """
    Resolve the full path to conda executable.
    
    Uses centralized Python path configuration.
    
    Returns:
        Full path to conda.exe or conda.bat
    """
    from configs.python_paths import get_conda_exe
    
    conda_exe = get_conda_exe()
    if conda_exe and conda_exe.exists():
        conda_exe_str = str(conda_exe)
        # Cross-host guard: do not return Windows launchers on non-Windows hosts.
        if os.name != 'nt' and conda_exe_str.lower().endswith(('.exe', '.bat', '.cmd')):
            path_conda = shutil.which('conda')
            if path_conda:
                logger.warning(
                    "tool_paths fallback: rejecting_windows_conda_launcher_on_non_windows conda_exe=%s using=%s",
                    conda_exe_str,
                    path_conda,
                )
                return path_conda
            logger.warning(
                "tool_paths fallback: rejecting_windows_conda_launcher_on_non_windows conda_exe=%s using=conda",
                conda_exe_str,
            )
            return 'conda'
        return conda_exe_str
    
    # Fallback to 'conda' and hope it's in PATH
    return 'conda'
