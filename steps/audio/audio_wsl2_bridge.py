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


def _failed_component_outcome(
    component: str,
    raw_status: object,
    error: object,
    note: object,
) -> dict:
    normalized = str(raw_status or "missing").strip().lower()
    if normalized in {"skipped", "unavailable"}:
        return {
            "status": "skipped",
            "reason": str(note or f"{component}_{normalized}"),
            "raw_status": normalized,
        }
    return {
        "status": "error",
        "reason": str(note or f"{component}_{normalized}"),
        "raw_status": normalized,
        "error": str(error or note or f"{component} status is {normalized}"),
    }


def _build_wsl_capability_outcomes(result: dict) -> dict:
    transcript = str(result.get("transcription") or "").strip()
    transcription_status = str(result.get("transcription_status") or "").lower()
    if transcription_status == "success" and transcript:
        transcription = {
            "status": "ok",
            "reason": "transcript_emitted",
            "character_count": len(transcript),
        }
    elif transcription_status == "success":
        transcription = {
            "status": "not_applicable",
            "reason": "no_text",
            "raw_status": transcription_status,
        }
    else:
        transcription = _failed_component_outcome(
            "transcription",
            transcription_status,
            result.get("transcription_error"),
            result.get("transcription_note"),
        )

    diarization_status = str(result.get("diarization_status") or "").lower()
    diarization_segments = result.get("diarization")
    if diarization_status == "success" and isinstance(diarization_segments, list) and diarization_segments:
        diarization = {
            "status": "ok",
            "reason": "speaker_tracks_emitted",
            "segment_count": len(diarization_segments),
        }
    elif diarization_status == "completed_no_speakers":
        diarization = {
            "status": "not_applicable",
            "reason": "content_appropriate_empty",
            "raw_status": diarization_status,
        }
    elif diarization_status == "success":
        diarization = {
            "status": "error",
            "reason": "successful_status_without_speaker_tracks",
            "raw_status": diarization_status,
            "error": "diarization reported success without speaker tracks",
        }
    else:
        diarization = _failed_component_outcome(
            "diarization",
            diarization_status,
            result.get("diarization_error"),
            result.get("diarization_note"),
        )

    emotion_status = str(result.get("emotion_status") or "").lower()
    emotion_label = str(result.get("emotion") or "").strip()
    if emotion_status == "success" and emotion_label and emotion_label.lower() != "unknown":
        acoustic_emotion = {
            "status": "ok",
            "reason": "emotion_emitted",
            "label": emotion_label,
        }
    elif emotion_status == "success":
        acoustic_emotion = {
            "status": "error",
            "reason": "successful_status_without_emotion",
            "raw_status": emotion_status,
            "error": "acoustic emotion reported success without a label",
        }
    else:
        acoustic_emotion = _failed_component_outcome(
            "acoustic_emotion",
            emotion_status,
            result.get("emotion_error"),
            result.get("emotion_note"),
        )

    embeddings_status = str(result.get("embeddings_status") or "").lower()
    embeddings = result.get("embeddings")
    embedding_dim = result.get("embedding_dim")
    if (
        embeddings_status == "success"
        and isinstance(embeddings, list)
        and bool(embeddings)
        and isinstance(embedding_dim, int)
        and not isinstance(embedding_dim, bool)
        and embedding_dim == len(embeddings)
    ):
        wav2vec2 = {
            "status": "ok",
            "reason": "embedding_emitted",
            "embedding_dim": embedding_dim,
        }
    elif embeddings_status == "success":
        wav2vec2 = {
            "status": "error",
            "reason": "successful_status_without_embedding",
            "raw_status": embeddings_status,
            "error": "Wav2Vec2 reported success without a dimensionally valid embedding",
        }
    else:
        wav2vec2 = _failed_component_outcome(
            "wav2vec2",
            embeddings_status,
            result.get("embeddings_error"),
            result.get("embeddings_note"),
        )

    clap_meta = result.get("clap_meta")
    clap_persisted = (
        isinstance(clap_meta, dict)
        and clap_meta.get("status") == "ok"
        and clap_meta.get("component") == "audio_embed_clap"
        and isinstance(clap_meta.get("embedding_id"), str)
        and bool(clap_meta.get("embedding_id", "").strip())
        and clap_meta.get("qdrant_committed") is True
        and isinstance(clap_meta.get("qdrant_collection"), str)
        and bool(clap_meta.get("qdrant_collection", "").strip())
    )
    if str(result.get("status") or "").strip().lower() != "success":
        clap_handoff = {
            "status": "error",
            "reason": "wsl_composite_failed_before_clap_handoff",
            "required_step": "audio_embed_clap",
            "error": str(result.get("error") or "WSL composite processing failed"),
        }
    else:
        clap_handoff = {
            "status": "ok",
            "reason": (
                "canonical_clap_already_persisted"
                if clap_persisted
                else "canonical_clap_required"
            ),
            "required_step": "audio_embed_clap",
        }
    return {
        "transcription": transcription,
        "diarization": diarization,
        "acoustic_emotion": acoustic_emotion,
        "wav2vec2": wav2vec2,
        "clap_handoff": clap_handoff,
    }


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
        # process_audio.py returns 'transcription', not 'full_text'
        transcript = result.get('transcription', '') or result.get('full_text', '')
        word_count = len(transcript.split()) if transcript else 0
        logger.info(f"[WSL2] Transcription complete - {word_count} words")
        return {
            'transcript': transcript,
            'full_text': transcript,
            'segments': result.get('segments', []) or result.get('word_timestamps', []),
            'words': result.get('words', []) or result.get('word_timestamps', [])
        }
    else:
        error_msg = result.get('error', 'Unknown error')
        logger.error(f"[WSL2] Transcription failed: {error_msg}")
        return {'error': error_msg, 'transcript': '', 'full_text': ''}


def audio_emotion_wsl2(audio_path: str, **kwargs) -> dict:
    """
    GPU-accelerated emotion detection via WSL2
    
    NOTE: This function is DEPRECATED. Emotion detection is now handled
    by the unified process_audio.py script in WSL2.
    
    Args:
        audio_path: Path to audio file
        **kwargs: Additional parameters
        
    Returns:
        dict with emotion labels and confidence scores
    """
    logger.debug("[WSL2] Emotion detection handled by unified audio processor")
    
    # Emotion detection now handled by process_audio.py
    return {
        'status': 'success',
        'emotions': {},
        'note': 'Handled by unified WSL2 audio processor'
    }


# Provide backwards-compatible function names
audio_diarize = audio_diarize_wsl2
audio_transcribe = audio_transcribe_wsl2
audio_emotion = audio_emotion_wsl2


def audio_unified_wsl2(audio_path: str, scene_id: str = None, duration: float = None, **kwargs) -> dict:
    """
    UNIFIED WSL2 Audio Processing - Single call for ALL audio intelligence
    
    Replaces the old multi-step audio chain with ONE GPU-accelerated WSL2 call
    that returns:
    - Transcription + word timestamps
    - Speaker diarization (if HF token available)
    - Emotion classification
    - Audio features (energy, volume, etc.)
    - Wav2Vec2 embeddings (768-dim)
    
    Args:
        audio_path: Path to audio file
        scene_id: Scene identifier for output organization
        duration: Audio duration in seconds (for dynamic timeout)
        **kwargs: Additional parameters
        
    Returns:
        dict with ALL audio data unified
    """
    logger.info(f"[WSL2] Running UNIFIED GPU-accelerated audio processing: {audio_path}")
    
    bridge = WSL2AudioBridge()
    
    # Dynamic timeout based on duration
    # ~2-3 seconds per second of audio (transcription + diarization + emotion)
    if duration:
        timeout = max(600, int(duration * 3) + 120)  # At least 10 min, or 3x duration + 2min buffer
    else:
        timeout = kwargs.get('timeout', 1800)  # Default 30 min
    
    result = bridge.process_audio(audio_path, timeout=timeout, audio_duration=duration)
    
    if result.get('status') == 'success':
        transcript = result.get('transcription', '')
        word_count = len(transcript.split()) if transcript else 0
        speaker_count = result.get('speaker_count', 0)
        emotion = result.get('emotion', 'unknown')
        word_timestamps = result.get('word_timestamps', []) or result.get('segments', [])
        
        logger.info(f"[WSL2] Unified processing complete - {word_count} words, {speaker_count} speakers, emotion: {emotion}")
        
        # Return unified structure that matches entity extractor expectations
        return {
            'status': 'success',
            # Transcription
            'transcript': transcript,
            'full_text': transcript,
            'segments': word_timestamps,
            'word_timestamps': word_timestamps,
            'language': result.get('language'),
            'language_probability': result.get('language_probability'),
            'transcript_meta': {
                'status': result.get('transcription_status', 'success'),
                'engine': 'wsl_unified',
                'device': result.get('device'),
                'language': result.get('language'),
            },
            
            # Diarization
            'speakers': result.get('speakers', []),
            'speaker_count': speaker_count,
            'diarization': result.get('diarization', []),
            'speaker_segments': result.get('diarization', []),
            'diarization_status': result.get('diarization_status'),
            'diarization_error': result.get('diarization_error'),
            'diarization_note': result.get('diarization_note'),
            
            # Emotion
            'emotion': emotion,
            'emotion_scores': result.get('emotion_scores', {}),
            'audio_emotion': emotion,  # Duplicate for compatibility
            'emotion_status': result.get('emotion_status'),
            'emotion_error': result.get('emotion_error'),
            'emotion_note': result.get('emotion_note'),
            
            # Features
            'energy': result.get('energy'),
            'duration': result.get('duration_seconds'),
            
            # Embeddings
            'embeddings': result.get('embeddings', []),
            'embedding_dim': result.get('embedding_dim', 768),
            'embeddings_status': result.get('embeddings_status'),
            'embeddings_error': result.get('embeddings_error'),
            'embeddings_note': result.get('embeddings_note'),
            'speaker_voice_signatures': result.get('speaker_voice_signatures', []),
            'speaker_voice_signature_meta': result.get('speaker_voice_signature_meta', {}),
            'wsl_capability_outcomes': _build_wsl_capability_outcomes(result),
            
            # Status
            'wsl2_unified': True,
            'gpu_used': result.get('device') == 'cuda',
            'gpu_name': result.get('gpu_name'),
            'bridge_env_warnings': result.get('bridge_env_warnings', []),
            'bridge_runtime_probe': result.get('bridge_runtime_probe', {}),
            'stderr_warnings': result.get('stderr_warnings', []),
        }
    else:
        error_msg = result.get('error', 'Unknown error')
        logger.error(f"[WSL2] Unified processing failed: {error_msg}")
        return {
            'error': error_msg,
            'transcript': '',
            'full_text': '',
            'wsl2_unified': True,
            'status': 'error',
            'bridge_error_reason': result.get('bridge_error_reason'),
            'bridge_error_details': result.get('bridge_error_details'),
            'bridge_env_warnings': result.get('bridge_env_warnings', []),
            'bridge_runtime_probe': result.get('bridge_runtime_probe', {}),
            'stderr_warnings': result.get('stderr_warnings', []),
            'wsl_returncode': result.get('wsl_returncode'),
            'transcript_meta': {
                'status': 'error',
                'engine': 'wsl_unified',
                'error': error_msg,
            },
            'wsl_capability_outcomes': _build_wsl_capability_outcomes(result),
        }
