"""
WSL2 Audio Bridge Step - Replaces legacy audio steps with WSL2-accelerated versions

This module provides drop-in replacements for:
- audio_diarize
- audio_transcribe  
- audio_emotion

All processing is offloaded to WSL2 with GPU acceleration.
"""

import logging
import math
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
    if result.get("transcription_error"):
        transcription_status = "error"
    if transcription_status == "success" and transcript:
        transcription = {
            "status": "ok",
            "reason": "transcript_emitted",
            "character_count": len(transcript),
        }
    elif transcription_status == "success":
        transcription = {
            # Process success without words is not evidence of absent speech.
            # Match the scene classifier and leave acceptance visibly incomplete.
            "status": "skipped",
            "reason": "worker_success_empty_transcript",
            "transcript_outcome": "unclassified",
            "raw_status": transcription_status,
        }
        evidence = result.get("speech_detection")
        if isinstance(evidence, dict):
            duration = evidence.get("input_duration_seconds")
            speech = evidence.get("speech_duration_seconds")
            valid = (evidence.get("status") == "completed" and evidence.get("method") == "silero_vad"
                     and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                             for v in (duration, speech)) and duration > 0 and 0 <= speech <= duration)
            if valid and not result.get("transcription_error"):
                transcription.update({
                    "status": "not_applicable" if speech == 0 else "skipped",
                    "reason": "no_speech_detected" if speech == 0 else "speech_detected_without_words",
                    "transcript_outcome": "no_speech" if speech == 0 else "no_intelligible_speech",
                    "speech_detection": dict(evidence),
                })
        quality = result.get("transcription_quality")
        if isinstance(quality, dict) and quality.get("status") == "completed":
            threshold = quality.get("threshold")
            rejected = quality.get("rejected_segments")
            if (quality.get("rule") == "whisper_no_speech_threshold"
                    and (quality.get("scope") != "per_source_region"
                         or quality.get("whole_input_no_speech_supported") is True)
                    and isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
                    and math.isfinite(threshold) and 0 <= threshold <= 1
                    and quality.get("accepted_segment_count") == 0
                    and isinstance(rejected, list) and rejected
                    and quality.get("decoded_segment_count") == len(rejected)
                    and all(isinstance(s, dict) and isinstance(s.get("no_speech_probability"), (int, float))
                            and not isinstance(s.get("no_speech_probability"), bool)
                            and threshold < s["no_speech_probability"] <= 1 for s in rejected)):
                transcription.update({"status": "not_applicable", "reason": "no_speech_detected",
                    "transcript_outcome": "no_speech", "basis": "whisper_no_speech_probability",
                    "transcription_quality": dict(quality)})
    else:
        transcription = _failed_component_outcome(
            "transcription",
            transcription_status,
            result.get("transcription_error"),
            result.get("transcription_note"),
        )

    diarization_status = str(result.get("diarization_status") or "").lower()
    diarization_segments = result.get("diarization")
    if (diarization_status == "not_applicable" and result.get("diarization_note") == "no_speech_detected"
            and transcription.get("transcript_outcome") == "no_speech"
            and not result.get("diarization_error") and not diarization_segments
            and not result.get("speakers") and not result.get("speaker_count")
            and not result.get("speaker_voice_signatures")):
        diarization = {"status": "not_applicable", "reason": "no_speech_detected", "raw_status": diarization_status}
    elif diarization_status == "success" and isinstance(diarization_segments, list) and diarization_segments:
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
    if (emotion_status == "not_applicable" and result.get("emotion_note") == "no_speech_detected"
            and transcription.get("transcript_outcome") == "no_speech"
            and not result.get("emotion_error") and not emotion_label and not result.get("emotion_scores")):
        acoustic_emotion = {"status": "not_applicable", "reason": "no_speech_detected", "raw_status": emotion_status}
    elif (emotion_status == "insufficient_evidence"
          and ((result.get("emotion_input") or {}).get("phrase_selection") or {}).get("policy") == "complete_observed_phrases_v1"
          and not ((result.get("emotion_input") or {}).get("phrase_selection") or {}).get("selected")
          and not result.get("emotion_error") and not emotion_label and not result.get("emotion_scores")):
        acoustic_emotion = {"status": "not_applicable", "reason": "no_complete_supported_phrase",
                            "raw_status": emotion_status, "quality_status": "insufficient_evidence"}
    elif (emotion_status == "insufficient_evidence"
          and (result.get("emotion_input") or {}).get("policy") in {"clear_speech_only_v1", "clear_speech_only_v2"}
          and not (result.get("emotion_input") or {}).get("selected")
          and not emotion_label and not result.get("emotion_scores")):
        acoustic_emotion = {"status": "not_applicable", "reason": "insufficient_clear_speech", "raw_status": emotion_status}
    elif (emotion_status == "success" and result.get("emotion_segments")
          and (result.get("emotion_input") or {}).get("policy") in {"clear_speech_only_v1", "clear_speech_only_v2"}
          and not emotion_label and not result.get("emotion_scores")):
        acoustic_emotion = {"status": "ok", "reason": "speech_segment_estimates", "count": len(result["emotion_segments"])}
        if any(s.get("interpretation_status") == "uncertain" for s in result["emotion_segments"]):
            acoustic_emotion.update(reason="uncertain_complete_phrase_estimates", quality_status="uncertain")
    elif emotion_status == "success" and emotion_label and emotion_label.lower() != "unknown":
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
    if embeddings_status == "retired":
        wav2vec2 = {
            "status": "error" if embeddings or embedding_dim else "skipped",
            "reason": "retired_status_with_embedding" if embeddings or embedding_dim else "whole_scene_vector_retired",
            "raw_status": "retired",
        }
    elif (
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
    if kwargs.get('recording_audio') is not None:
        from steps.audio.recording_ingestion import scene_result
        return scene_result(kwargs['recording_audio'], kwargs['scene_id'])
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


def _transcription_projection(result: dict, *, engine: str) -> dict:
    """One evidence projection for unified, local and compatibility callers."""
    text = str(result.get('transcription') or '')
    outcome = _build_wsl_capability_outcomes(result)['transcription']
    alignment = result.get('word_alignment') or {}
    words = alignment.get('words') or []
    segments = result.get('segments') or (result.get('word_timestamps') if not alignment else []) or []
    error = result.get('transcription_error') or result.get('error')
    failed = bool(error) or result.get('transcription_status') == 'error'
    meta = {key: result.get(key) for key in ('transcription_context', 'transcription_decoding',
        'transcription_quality', 'transcription_timing', 'speech_detection', 'language')}
    # Speaker merging replaces display segments with attributed word turns.
    # Preserve whole native phrases separately; their bounds must not be lent
    # to those smaller turns or lost when attribution is materialized.
    meta['phrase_observations'] = [{'text': str(segment.get('text') or ''),
        **segment['phrase_timing'], 'source_segment_index': index}
        for index, segment in enumerate(segments) if isinstance(segment, dict)
        and isinstance(segment.get('phrase_timing'), dict)]
    meta.update(status='partial' if failed and text else 'error' if failed else result.get('transcription_status', 'success'),
        engine=engine, device=result.get('device'), model=result.get('whisper_model') or result.get('model'),
        reason='transcript_available_with_region_errors' if failed and text else outcome['reason'], error=error,
        word_alignment=result.get('word_alignment'), segments=segments, segment_count=len(segments),
        outcome_basis=outcome.get('basis', 'silero_vad' if outcome.get('transcript_outcome') == 'no_speech' else None))
    return {'status': 'partial' if failed and text else 'error' if failed else 'success',
        'error': error, 'transcript': text, 'full_text': text, 'segments': segments,
        'word_timestamps': words, 'words': words, 'language': result.get('language'),
        'language_probability': result.get('language_probability'),
        'transcript_outcome': 'partial' if failed and text else ('transcript_available' if outcome['status']=='ok'
            else outcome.get('transcript_outcome', 'runtime_failure')),
        'transcript_outcome_reason': meta['reason'], 'transcript_meta': meta}


def audio_transcribe_wsl2(audio_path: str, **kwargs) -> dict:
    """
    GPU-accelerated transcription via WSL2 (Faster Whisper)
    
    Args:
        audio_path: Path to audio file
        **kwargs: Additional parameters (model, language, etc.)
        
    Returns:
        dict with transcript and word-level timestamps
    """
    if kwargs.get('recording_audio') is not None:
        from steps.audio.recording_ingestion import scene_result
        return scene_result(kwargs['recording_audio'], kwargs['scene_id'])
    logger.info(f"[WSL2] Running GPU-accelerated transcription: {audio_path}")
    kwargs.setdefault('transcription_temperature', 0.)
    raw = _request_audio_worker(audio_path, **kwargs)
    result = {**raw, **_transcription_projection(raw, engine='wsl_unified')}
    # Policy/transport failure is still failure even if an old worker emitted words.
    if raw.get('status') == 'error': result['status'] = 'error'
    keys = ('status', 'error', 'transcript', 'full_text', 'segments', 'words', 'word_timestamps',
            'transcript_meta', 'transcript_outcome', 'transcript_outcome_reason', 'language',
            'language_probability', 'duration', 'bridge_runtime_probe', 'bridge_error_reason',
            'bridge_error_details', 'wsl_returncode')
    return {key: result[key] for key in keys if key in result}


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
    if kwargs.get('recording_audio') is not None:
        from steps.audio.recording_ingestion import scene_result
        return scene_result(kwargs['recording_audio'], kwargs['scene_id'])
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


def _bound_diarization_to_clip(segments: list, duration: float | None) -> list:
    """Intersect model turns with the caller's clip, preserving adjusted times."""
    if duration is None:
        return segments
    clip_end = float(duration)
    if not math.isfinite(clip_end) or clip_end <= 0:
        raise ValueError("Diarization clip duration must be finite and positive")
    bounded = []
    for segment in segments:
        start, end = float(segment['start']), float(segment['end'])
        if not (math.isfinite(start) and math.isfinite(end)) or end <= start:
            raise ValueError("Diarization turn has invalid timestamps")
        clipped_start, clipped_end = max(0.0, start), min(clip_end, end)
        if clipped_end <= clipped_start:
            raise ValueError("Diarization turn does not overlap the caller's clip")
        turn = dict(segment)
        if (clipped_start, clipped_end) != (start, end):
            turn.update(start=clipped_start, end=clipped_end)
            turn['timing_adjustment'] = {
                'reason': 'caller_clip_bounds',
                'original_start': start,
                'original_end': end,
                'clip_duration': clip_end,
            }
            logger.warning("Bounded diarization turn [%s, %s] to [%s, %s]",
                           start, end, clipped_start, clipped_end)
        bounded.append(turn)
    return bounded


def unified_transcription_options(cfg: dict) -> dict:
    """One projection for direct video, standalone and step-dispatch callers."""
    from scripts.config_schema import AudioTranscriptionConfig
    raw = (cfg.get('audio') or {}).get('transcribe') or {}
    # Legacy callers also carry local-backend keys here. Validate the settings
    # owned by this projection without changing those callers' routing policy.
    transcription = AudioTranscriptionConfig.model_validate(
        {key: raw[key] for key in ('vocabulary', 'temperature') if key in raw})
    options = {'transcription_temperature': transcription.temperature}
    if transcription.vocabulary is not None:
        options['transcription_vocabulary'] = transcription.vocabulary
    return options


def _request_audio_worker(audio_path, duration=None, **kwargs):
    bridge = WSL2AudioBridge()

    # Dynamic timeout based on duration
    # ~2-3 seconds per second of audio (transcription + diarization + emotion)
    if duration:
        timeout = max(600, int(duration * 3) + 120)  # At least 10 min, or 3x duration + 2min buffer
    else:
        timeout = kwargs.get('timeout', 1800)  # Default 30 min

    vocabulary = kwargs.get('transcription_vocabulary')
    options = {'transcription_vocabulary': vocabulary} if vocabulary is not None else {}
    temperature = kwargs.get('transcription_temperature')
    if temperature is not None:
        options['transcription_temperature'] = temperature
    result = bridge.process_audio(audio_path, timeout=timeout, audio_duration=duration, **options)

    # Old workers accept extra positional arguments without applying them. Do
    # not report an explicitly requested policy as applied without its receipt.
    decoding = result.get('transcription_decoding') or {}
    if (result.get('status') == 'success' and temperature is not None
            and (decoding.get('policy') != 'single_temperature_v1'
                 or decoding.get('temperature') != temperature
                 or (decoding.get('source_regions') or {}).get('policy') != 'source_audio_v2')):
        result = {**result, 'status': 'error',
                  'error': 'Worker did not confirm the requested transcription coverage and decoding policy; synchronize the worker before use.',
                  'transcription_status': 'error',
                  'transcription_error': 'transcription_policy_unconfirmed',
                  'bridge_error_reason': 'transcription_policy_unconfirmed'}

    return result


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
        duration: Caller clip duration in seconds (for timing bounds and timeout)
        **kwargs: Additional parameters
        
    Returns:
        dict with ALL audio data unified
    """
    if kwargs.get('recording_audio') is not None:
        from steps.audio.recording_ingestion import scene_result
        return scene_result(kwargs['recording_audio'], scene_id)
    logger.info(f"[WSL2] Running UNIFIED GPU-accelerated audio processing: {audio_path}")
    
    result = _request_audio_worker(audio_path, duration=duration, **kwargs)

    if result.get('status') == 'success':
        transcript = result.get('transcription', '')
        word_count = len(transcript.split()) if transcript else 0
        speaker_count = result.get('speaker_count', 0)
        emotion = result.get('emotion', 'unknown')
        segments = result.get('segments', []) or result.get('word_timestamps', [])
        # Legacy workers called whole segments words; never claim word alignment
        # from that field unless the worker supplies the explicit alignment receipt.
        alignment = result.get('word_alignment')
        word_timestamps = (alignment or {}).get('words', [])
        diarization = _bound_diarization_to_clip(result.get('diarization', []), duration)
        capability_outcomes = _build_wsl_capability_outcomes(result)
        transcription = capability_outcomes['transcription']
        transcript_outcome = ('transcript_available' if transcription['status'] == 'ok'
                              else transcription.get('transcript_outcome', 'runtime_failure'))
        
        logger.info(f"[WSL2] Unified processing complete - {word_count} words, {speaker_count} speakers, emotion: {emotion}")
        
        # Return unified structure that matches entity extractor expectations
        return {
            **_transcription_projection(result, engine='wsl_unified'),

            # Diarization
            'speakers': result.get('speakers', []),
            'speaker_count': speaker_count,
            'diarization': diarization,
            'speaker_segments': diarization,
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
            'emotion_segments': result.get('emotion_segments', []),
            'emotion_input': result.get('emotion_input'),
            'sound_events': result.get('sound_events', []),
            'sound_event_meta': result.get('sound_event_meta'),
            
            # Features
            'energy': result.get('energy'),
            'duration': result.get('duration_seconds'),
            
            # Embeddings
            'embeddings': result.get('embeddings', []),
            'embedding_dim': result.get('embedding_dim', 0 if result.get('embeddings_status') == 'retired' else 768),
            'embeddings_status': result.get('embeddings_status'),
            'embeddings_error': result.get('embeddings_error'),
            'embeddings_note': result.get('embeddings_note'),
            'speaker_voice_signatures': result.get('speaker_voice_signatures', []),
            'speaker_voice_signature_meta': result.get('speaker_voice_signature_meta', {}),
            'speaker_change_review': result.get('speaker_change_review', {}),
            'wsl_capability_outcomes': capability_outcomes,
            
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
            **_transcription_projection(result, engine='wsl_unified'),
            'error': error_msg,
            'wsl2_unified': True,
            'status': 'error',
            'bridge_error_reason': result.get('bridge_error_reason'),
            'bridge_error_details': result.get('bridge_error_details'),
            'bridge_env_warnings': result.get('bridge_env_warnings', []),
            'bridge_runtime_probe': result.get('bridge_runtime_probe', {}),
            'stderr_warnings': result.get('stderr_warnings', []),
            'wsl_returncode': result.get('wsl_returncode'),
            'wsl_capability_outcomes': _build_wsl_capability_outcomes(result),
        }
