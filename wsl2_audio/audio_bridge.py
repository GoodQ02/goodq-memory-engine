"""
Legacy compatibility facade for WSL audio helpers.

This module preserves the older import surface used by a few compatibility
steps, but delegates all runtime work to the canonical unified WSL bridge in
``scripts.wsl2_audio_bridge``.

.. deprecated:: transitional facade
   This module is deprecated.
"""

from __future__ import annotations

import warnings
warnings.warn(
    "wsl2_audio/audio_bridge.py is deprecated.",
    DeprecationWarning,
    stacklevel=1,
)


from typing import Any, Dict, Optional

from scripts.wsl2_audio_bridge import WSL2AudioBridge as _CanonicalWSL2AudioBridge


def _attach_run_id(payload: Dict[str, Any], run_id: Optional[str]) -> Dict[str, Any]:
    if run_id and "run_id" not in payload:
        payload["run_id"] = run_id
    return payload


def _as_error_payload(error: str, *, run_id: Optional[str]) -> Dict[str, Any]:
    return _attach_run_id({"status": "error", "error": error}, run_id)


def _to_transcribe_payload(result: Dict[str, Any], *, run_id: Optional[str]) -> Dict[str, Any]:
    if result.get("status") != "success":
        return _as_error_payload(str(result.get("error") or "Unknown error"), run_id=run_id)

    transcript = result.get("transcription", "") or result.get("full_text", "")
    segments = result.get("segments", []) or result.get("word_timestamps", [])
    payload = {
        "status": "success",
        "full_text": transcript,
        "transcription": segments,
        "info": {
            "language": result.get("language", "unknown"),
            "language_probability": result.get("language_probability", 0.0),
            "duration": result.get("duration_seconds", 0.0),
            "speakers_detected": result.get("speaker_count", 0),
            "rtf": result.get("rtf", 0.0),
        },
        "segments": segments,
        "word_timestamps": result.get("word_timestamps", []),
    }
    return _attach_run_id(payload, run_id)


def _to_combined_payload(result: Dict[str, Any], *, run_id: Optional[str]) -> Dict[str, Any]:
    if result.get("status") != "success":
        return _as_error_payload(str(result.get("error") or "Unknown error"), run_id=run_id)

    transcript = result.get("transcription", "") or result.get("full_text", "")
    segments = result.get("segments", []) or result.get("word_timestamps", [])
    payload = {
        "status": "success",
        "full_text": transcript,
        "transcription": segments,
        "diarization": result.get("diarization", []),
        "speaker_count": result.get("speaker_count", 0),
        "speakers": result.get("speakers", []),
        "info": {
            "language": result.get("language", "unknown"),
            "language_probability": result.get("language_probability", 0.0),
            "duration": result.get("duration_seconds", 0.0),
            "speakers_detected": result.get("speaker_count", 0),
            "rtf": result.get("rtf", 0.0),
        },
    }
    return _attach_run_id(payload, run_id)


class WSL2AudioBridge(_CanonicalWSL2AudioBridge):
    """
    Backward-compatible bridge surface.

    The legacy API exposed ``transcribe`` / ``diarize`` / ``transcribe_and_diarize``
    and a private ``_is_wsl_service_running`` helper. Those methods now translate
    onto the canonical unified ``process_audio`` bridge.

    .. deprecated:: transitional facade
       This class is deprecated.
    """

    def _is_wsl_service_running(self) -> bool:
        # Compatibility alias for older callers and tests.
        return self.check_status()

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        timeout: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        _ = (language, task, beam_size)
        return _to_transcribe_payload(
            self.process_audio(audio_path, timeout=timeout),
            run_id=run_id,
        )

    def transcribe_and_diarize(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        timeout: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        _ = (language, task, beam_size)
        return _to_combined_payload(
            self.process_audio(audio_path, timeout=timeout),
            run_id=run_id,
        )


_bridge: Optional[WSL2AudioBridge] = None


def get_bridge() -> WSL2AudioBridge:
    global _bridge
    if _bridge is None:
        _bridge = WSL2AudioBridge()
    return _bridge


def transcribe_wsl2(audio_path: str, **kwargs: Any) -> Dict[str, Any]:
    """Transcribe audio using legacy bridge.

    .. deprecated:: transitional facade
       This function is deprecated. Use canonical WSL2AudioBridge or step runner instead.
    """
    warnings.warn(
        "transcribe_wsl2 is deprecated and will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_bridge().transcribe(audio_path, **kwargs)


def transcribe_and_diarize_wsl2(audio_path: str, **kwargs: Any) -> Dict[str, Any]:
    """Transcribe and diarize audio using legacy bridge.

    .. deprecated:: transitional facade
       This function is deprecated. Use canonical WSL2AudioBridge or step runner instead.
    """
    warnings.warn(
        "transcribe_and_diarize_wsl2 is deprecated and will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_bridge().transcribe_and_diarize(audio_path, **kwargs)
