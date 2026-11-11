"""
WSL2 Audio Bridge Step - Replaces legacy audio steps with WSL2-accelerated versions

This module provides drop-in replacements for:
- audio_diarize
- audio_transcribe  
- audio_emotion

All processing is offloaded to WSL2 with GPU acceleration.
"""

from collections import Counter
import logging
import math
import re
import sys
from pathlib import Path

# Add scripts to path for bridge import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'scripts'))

from wsl2_audio_bridge import WSL2AudioBridge

logger = logging.getLogger(__name__)

_WORD_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_VOCAB_STOPWORDS = frozenset({"a", "an", "the", "of", "in", "on", "at", "to", "and", "or"})
_STOCK_HALLUCINATION_PHRASES = frozenset({
    "thank you for watching",
    "thanks for watching",
    "thank you so much for watching",
    "please subscribe",
    "like and subscribe",
    "subtitles by the amara org community",
})


def _normalize_vocabulary_terms(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    words: list[str] = []
    seen: set[str] = set()
    for item in value[:32]:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or len(cleaned) > 64 or not cleaned.isprintable():
            continue
        folded = cleaned.casefold()
        if folded not in seen:
            words.append(cleaned)
            seen.add(folded)
    return words


def _apply_post_filter_vocabulary_context(result: dict, vocabulary: object) -> dict:
    if not isinstance(result, dict):
        return result
    normalized = _normalize_vocabulary_terms(vocabulary)
    if not normalized:
        return result
    return {
        **result,
        "transcription_context": {
            "status": "gated_post_filter_only",
            "source": "request_config",
            "kind": "vocabulary_hints",
            "words": normalized,
            "identity_claim": False,
        },
    }


def _extract_confidence_override_map(segments: list[dict], quality: object) -> dict[int, dict]:
    if not isinstance(quality, dict):
        return {}
    decisions_by_seg: dict[int, dict] = {}
    direct = (quality.get("confidence_override") or {}).get("segments")
    if isinstance(direct, list):
        for dec in direct:
            if isinstance(dec, dict) and isinstance(dec.get("segment_index"), int):
                decisions_by_seg[dec["segment_index"]] = dec

    region_results = quality.get("region_results")
    if not isinstance(region_results, list) or not region_results:
        return decisions_by_seg

    has_region_ids = any(isinstance(seg.get("source_region_index"), int) for seg in segments)
    region_seg_indices: dict[int, list[int]] = {}
    if has_region_ids:
        for global_idx, seg in enumerate(segments):
            sri = seg.get("source_region_index")
            if isinstance(sri, int):
                region_seg_indices.setdefault(sri, []).append(global_idx)

    offset = 0
    for rr in region_results:
        if not isinstance(rr, dict):
            continue
        co_segs = ((rr.get("confidence_override") or {}).get("segments"))
        sri = rr.get("source_region_index")
        if isinstance(co_segs, list):
            for dec in co_segs:
                if not isinstance(dec, dict) or not isinstance(dec.get("segment_index"), int):
                    continue
                local_idx = dec["segment_index"]
                if has_region_ids and isinstance(sri, int):
                    mapped = region_seg_indices.get(sri) or []
                    if 0 <= local_idx < len(mapped):
                        decisions_by_seg[mapped[local_idx]] = dec
                else:
                    global_idx = offset + local_idx
                    if 0 <= global_idx < len(segments):
                        decisions_by_seg[global_idx] = dec
        acc = rr.get("accepted_segment_count")
        if isinstance(acc, int) and acc > 0:
            offset += acc
    return decisions_by_seg


def _segment_word_probabilities(segment: dict) -> list[float]:
    words = segment.get("words")
    if not isinstance(words, list):
        return []
    probs: list[float] = []
    for word in words:
        if not isinstance(word, dict):
            continue
        prob = word.get("probability")
        if isinstance(prob, (int, float)) and not isinstance(prob, bool) and math.isfinite(prob) and 0.0 <= float(prob) <= 1.0:
            probs.append(float(prob))
    return probs


def _trim_trailing_vocabulary_loop(segment: dict, vocab_tokens: set[str]) -> tuple[dict, int]:
    text = str(segment.get("text") or "")
    matches = list(_WORD_TOKEN_RE.finditer(text))
    tokens = [m.group(0).lower() for m in matches]
    if len(tokens) < 7 or tokens[-1] not in vocab_tokens:
        return segment, 0
    tail_token = tokens[-1]
    tail_run = 0
    for tok in reversed(tokens):
        if tok == tail_token:
            tail_run += 1
        else:
            break
    if tail_run < 6:
        return segment, 0

    drop_count = tail_run - 1
    keep_match = matches[len(matches) - tail_run]
    trimmed_text = text[: keep_match.end()].rstrip()
    updated = dict(segment)
    updated["text"] = trimmed_text
    if isinstance(updated.get("phrase_timing"), dict):
        updated["phrase_timing"] = {**updated["phrase_timing"], "text": trimmed_text}

    words = segment.get("words")
    if isinstance(words, list) and len(words) >= tail_run:
        word_tail = 0
        for word in reversed(words):
            if not isinstance(word, dict):
                break
            wtoks = [t.lower() for t in _WORD_TOKEN_RE.findall(str(word.get("text") or word.get("word") or ""))]
            if wtoks == [tail_token]:
                word_tail += 1
            else:
                break
        if word_tail >= tail_run:
            kept_words = [dict(w) if isinstance(w, dict) else w for w in words[: len(words) - drop_count]]
            updated["words"] = kept_words
            if kept_words and isinstance(kept_words[-1], dict):
                last_end = kept_words[-1].get("end")
                seg_start = updated.get("start")
                if (
                    isinstance(last_end, (int, float))
                    and not isinstance(last_end, bool)
                    and math.isfinite(last_end)
                    and isinstance(seg_start, (int, float))
                    and float(last_end) > float(seg_start)
                ):
                    updated["end"] = float(last_end)
    return updated, drop_count


def _sanitize_transcription_result(result: dict, *, fallback_vocabulary: object = None) -> dict:
    """Filter Whisper hotword prompt-echoes and runaway low-SNR hallucinations at the bridge boundary."""
    if not isinstance(result, dict) or isinstance(result.get("prompt_echo_filter"), dict):
        return result
    if str(result.get("transcription_status") or "").lower() != "success" or result.get("transcription_error"):
        return result
    segments = result.get("segments")
    if not isinstance(segments, list) or not segments or not all(isinstance(s, dict) for s in segments):
        return result

    ctx = result.get("transcription_context")
    ctx_words = ctx.get("words") if isinstance(ctx, dict) else None
    vocab_terms = _normalize_vocabulary_terms(ctx_words if ctx_words else fallback_vocabulary)
    vocab_tokens = {
        tok.lower()
        for term in vocab_terms
        for tok in _WORD_TOKEN_RE.findall(term)
    } - _VOCAB_STOPWORDS

    co_map = _extract_confidence_override_map(segments, result.get("transcription_quality"))
    kept_segments: list[dict] = []
    old_to_new_index: dict[int, int] = {}
    dropped_indices: set[int] = set()
    filtered_records: list[dict] = []
    trimmed_segment_count = 0

    for idx, seg in enumerate(segments):
        text = str(seg.get("text") or "").strip()
        tokens = [t.lower() for t in _WORD_TOKEN_RE.findall(text)]
        pt = seg.get("phrase_timing") if isinstance(seg.get("phrase_timing"), dict) else {}
        pt_status = str(pt.get("status") or "").lower()
        pt_reason = str(pt.get("reason") or "")

        co_entry = co_map.get(idx) or {}
        co_rejected = co_entry.get("decision") == "reject"
        co_gmean = co_entry.get("word_geometric_mean_probability")
        probs = _segment_word_probabilities(seg)
        gmean_prob: float | None = None
        if isinstance(co_gmean, (int, float)) and not isinstance(co_gmean, bool) and math.isfinite(co_gmean):
            gmean_prob = float(co_gmean)
        elif probs:
            gmean_prob = (
                math.exp(sum(math.log(p) for p in probs) / len(probs))
                if all(p > 0.0 for p in probs)
                else 0.0
            )
        min_prob = min(probs) if probs else None

        drop_reason: str | None = None
        if pt_reason == "paired_native_timestamps_unavailable":
            compact = re.sub(r"\s+", "", text.lower())
            periodic_compact = len(compact) >= 48 and (
                len(set(compact)) <= 3
                or any(
                    compact.count(compact[:k]) * k >= 0.75 * len(compact)
                    for k in range(1, min(16, len(compact) // 4 + 1))
                )
            )
            top4_loop = len(tokens) >= 20 and (
                sum(count for _, count in Counter(tokens).most_common(4)) / len(tokens) >= 0.75
            )
            if periodic_compact or top4_loop:
                drop_reason = "unterminated_decoder_loop"

        if drop_reason is None and tokens:
            norm_phrase = " ".join(tokens)
            if norm_phrase in _STOCK_HALLUCINATION_PHRASES and (
                co_rejected
                or pt_status == "unavailable"
                or (gmean_prob is not None and gmean_prob < 0.35)
            ):
                drop_reason = "stock_boilerplate_hallucination"

        if drop_reason is None and vocab_tokens and len(tokens) >= 4:
            vocab_hits = [t for t in tokens if t in vocab_tokens]
            vocab_ratio = len(vocab_hits) / len(tokens)
            distinct_vocab = len(set(vocab_hits))
            if vocab_ratio >= 0.80:
                low_confidence = (
                    co_rejected
                    or pt_status == "unavailable"
                    or (gmean_prob is not None and gmean_prob < 0.35)
                    or (min_prob is not None and min_prob < 0.02 and len(tokens) >= 6)
                )
                roster_or_loop = (
                    (distinct_vocab >= 3 and "," in text)
                    or (len(tokens) >= 6 and (len(vocab_hits) - distinct_vocab) >= 2)
                )
                if low_confidence or roster_or_loop:
                    drop_reason = "vocabulary_prompt_echo"

        if drop_reason is None and vocab_tokens and 1 <= len(tokens) <= 3:
            if (
                all(t in vocab_tokens for t in tokens)
                and (co_rejected or pt_status == "unavailable")
                and (gmean_prob is None or gmean_prob < 0.15)
            ):
                drop_reason = "vocabulary_short_ghost"

        if drop_reason is not None:
            dropped_indices.add(idx)
            filtered_records.append({
                "segment_index": idx,
                "reason": drop_reason,
                "text": text,
                "start": seg.get("start"),
                "end": seg.get("end"),
                "word_geometric_mean_probability": gmean_prob,
            })
            continue

        candidate = dict(seg)
        if vocab_tokens:
            candidate, trimmed_tokens = _trim_trailing_vocabulary_loop(candidate, vocab_tokens)
            if trimmed_tokens > 0:
                trimmed_segment_count += 1
        old_to_new_index[idx] = len(kept_segments)
        kept_segments.append(candidate)

    if not filtered_records and trimmed_segment_count == 0:
        return result

    sanitized = dict(result)
    sanitized["segments"] = kept_segments
    sanitized["transcription"] = " ".join(
        str(s.get("text") or "").strip()
        for s in kept_segments
        if str(s.get("text") or "").strip()
    )

    if any(isinstance(s.get("words"), list) for s in segments):
        rebuilt_words = [
            dict(w) if isinstance(w, dict) else w
            for s in kept_segments
            for w in (s.get("words") or [])
        ]
    else:
        existing_alignment = result.get("word_alignment")
        existing_words = existing_alignment.get("words") if isinstance(existing_alignment, dict) else None
        if not kept_segments or not isinstance(existing_words, list):
            rebuilt_words = []
        else:
            rebuilt_words = []
            for w in existing_words:
                if not isinstance(w, dict):
                    continue
                ws, we = w.get("start"), w.get("end")
                if all(isinstance(v, (int, float)) and math.isfinite(v) for v in (ws, we)):
                    in_kept = any(
                        isinstance(ks.get("start"), (int, float))
                        and isinstance(ks.get("end"), (int, float))
                        and float(we) > float(ks["start"])
                        and float(ws) < float(ks["end"])
                        for ks in kept_segments
                    )
                    in_dropped = any(
                        isinstance(segments[d_idx].get("start"), (int, float))
                        and isinstance(segments[d_idx].get("end"), (int, float))
                        and float(ws) >= float(segments[d_idx]["start"]) - 1e-3
                        and float(we) <= float(segments[d_idx]["end"]) + 1e-3
                        for d_idx in dropped_indices
                    )
                    if in_dropped and not in_kept:
                        continue
                rebuilt_words.append(dict(w))

    if "word_timestamps" in sanitized or isinstance(sanitized.get("word_alignment"), dict):
        sanitized["word_timestamps"] = rebuilt_words
    if isinstance(sanitized.get("word_alignment"), dict):
        sanitized["word_alignment"] = {
            **sanitized["word_alignment"],
            "words": rebuilt_words,
            "status": "available" if rebuilt_words else "no_word_alignment",
        }

    emotion_segments = sanitized.get("emotion_segments")
    if dropped_indices and isinstance(emotion_segments, list) and emotion_segments:
        kept_emotions: list[dict] = []
        for es in emotion_segments:
            if not isinstance(es, dict):
                continue
            ssi = es.get("source_segment_index")
            if isinstance(ssi, int) and ssi in dropped_indices:
                continue
            updated_es = dict(es)
            if isinstance(ssi, int) and ssi in old_to_new_index:
                updated_es["source_segment_index"] = old_to_new_index[ssi]
            kept_emotions.append(updated_es)
        sanitized["emotion_segments"] = kept_emotions
        if (
            not kept_emotions
            and str(sanitized.get("emotion_status") or "").lower() == "success"
            and not str(sanitized.get("emotion") or "").strip()
        ):
            sanitized["emotion_status"] = "insufficient_evidence"
            sanitized["emotion_note"] = "no_complete_supported_phrase"
            emo_input = sanitized.get("emotion_input")
            if isinstance(emo_input, dict):
                updated_input = {**emo_input, "selected": []}
                if isinstance(emo_input.get("phrase_selection"), dict):
                    updated_input["phrase_selection"] = {
                        **emo_input["phrase_selection"],
                        "selected": [],
                    }
                sanitized["emotion_input"] = updated_input

    sanitized["prompt_echo_filter"] = {
        "policy": "bridge_prompt_echo_filter_v1",
        "input_segment_count": len(segments),
        "kept_segment_count": len(kept_segments),
        "filtered_segment_count": len(filtered_records),
        "trimmed_segment_count": trimmed_segment_count,
        "filtered_segments": filtered_records,
        "raw_transcription": str(result.get("transcription") or ""),
    }
    return sanitized


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
        prompt_echo_filter = result.get("prompt_echo_filter")
        if isinstance(prompt_echo_filter, dict) and int(prompt_echo_filter.get("filtered_segment_count") or 0) > 0:
            transcription.update({
                "status": "skipped",
                "reason": "vocabulary_prompt_echo_filtered",
                "transcript_outcome": "low_confidence",
                "prompt_echo_filter": {
                    key: prompt_echo_filter[key]
                    for key in ("policy", "input_segment_count", "kept_segment_count", "filtered_segment_count")
                    if key in prompt_echo_filter
                },
            })
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
    elif (diarization_status == "completed_no_speakers"
          and not diarization_segments and not result.get("diarization_error")
          and emotion_status == "error"
          and result.get("emotion_error") == "speech_selection_unavailable"
          and not emotion_label and not result.get("emotion_scores")
          and not result.get("emotion_segments")):
        acoustic_emotion = {
            "status": "not_applicable",
            "reason": "no_diarized_speakers",
            "raw_status": emotion_status,
        }
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
    result = _sanitize_transcription_result(result)
    text = str(result.get('transcription') or '')
    outcome = _build_wsl_capability_outcomes(result)['transcription']
    alignment = result.get('word_alignment') or {}
    words = alignment.get('words') or []
    segments = result.get('segments') or (result.get('word_timestamps') if not alignment else []) or []
    error = result.get('transcription_error') or result.get('error')
    failed = bool(error) or result.get('transcription_status') == 'error'
    meta = {key: result.get(key) for key in ('transcription_context', 'transcription_decoding',
        'transcription_quality', 'transcription_timing', 'speech_detection', 'language')}
    if isinstance(result.get('prompt_echo_filter'), dict):
        meta['prompt_echo_filter'] = result['prompt_echo_filter']
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
    sanitized = _sanitize_transcription_result(
        raw,
        fallback_vocabulary=kwargs.get('post_filter_vocabulary') or kwargs.get('transcription_vocabulary'),
    )
    result = {**sanitized, **_transcription_projection(sanitized, engine='wsl_unified')}
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
        {key: raw[key] for key in ('vocabulary', 'vocabulary_mode', 'temperature') if key in raw})
    options: dict = {'transcription_temperature': transcription.temperature}
    if transcription.vocabulary is not None:
        if transcription.vocabulary_mode == 'post_filter_only':
            options['post_filter_vocabulary'] = transcription.vocabulary
        else:
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
    post_filter_vocabulary = kwargs.get('post_filter_vocabulary')
    options = {'transcription_vocabulary': vocabulary} if vocabulary is not None else {}
    temperature = kwargs.get('transcription_temperature')
    if temperature is not None:
        options['transcription_temperature'] = temperature
    result = bridge.process_audio(audio_path, timeout=timeout, audio_duration=duration, **options)
    if post_filter_vocabulary is not None and vocabulary is None and isinstance(result, dict):
        result = _apply_post_filter_vocabulary_context(result, post_filter_vocabulary)

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
    
    raw = _request_audio_worker(audio_path, duration=duration, **kwargs)
    result = _sanitize_transcription_result(
        raw,
        fallback_vocabulary=kwargs.get('post_filter_vocabulary') or kwargs.get('transcription_vocabulary'),
    )

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
        no_speaker_emotion_na = (
            capability_outcomes.get('acoustic_emotion', {}).get('status') == 'not_applicable'
            and capability_outcomes.get('acoustic_emotion', {}).get('reason') == 'no_diarized_speakers'
        )
        raw_svs_meta = result.get('speaker_voice_signature_meta', {})
        if (
            isinstance(raw_svs_meta, dict)
            and str(result.get('diarization_status') or '').lower() == 'completed_no_speakers'
            and not diarization
            and not result.get('diarization_error')
            and raw_svs_meta.get('reason') == 'diarization_unavailable'
        ):
            svs_meta = {**raw_svs_meta, 'status': 'not_applicable', 'reason': 'completed_no_speakers'}
        else:
            svs_meta = raw_svs_meta

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
            'emotion': None if no_speaker_emotion_na else emotion,
            'emotion_scores': result.get('emotion_scores', {}),
            'audio_emotion': None if no_speaker_emotion_na else emotion,  # Duplicate for compatibility
            'emotion_status': 'not_applicable' if no_speaker_emotion_na else result.get('emotion_status'),
            'emotion_error': None if no_speaker_emotion_na else result.get('emotion_error'),
            'emotion_note': 'no_diarized_speakers' if no_speaker_emotion_na else result.get('emotion_note'),
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
            'speaker_voice_signature_meta': svs_meta,
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
