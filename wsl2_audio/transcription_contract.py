"""Shared source-time transcription policy; imports no Torch or diarization runtime."""
from __future__ import annotations
import math
import re
from typing import Any
import numpy as np
try:
    from . import model_cache
except ImportError:
    import model_cache

def _recover_word_timing(segments, alternative_segments, *, method="whisper_no_vad_retry"):
    """Recover only unique, bounded word matches from an independent no-VAD pass.

    Never replace primary text or claim human-verified timing. Ambiguity stays
    unavailable; neighboring aligned words constrain the candidate interval.
    """
    normalized = lambda text: re.sub(r"[^\w']", "", str(text).lower())
    words = [(word, segment) for segment in segments for word in segment.get("words", [])]
    alternatives = [word for segment in alternative_segments for word in segment.get("words", [])]
    recovered = 0
    for index, (word, segment) in enumerate(words):
        if word.get("timing_status") != "invalid_model_alignment":
            continue
        low = next((w["end"] for w, _ in reversed(words[:index]) if w.get("end") is not None), segment["start"])
        high = next((w["start"] for w, _ in words[index+1:] if w.get("start") is not None), segment["end"])
        candidates = [w for w in alternatives if normalized(w.get("text")) == normalized(word.get("text"))
                      and w.get("start") is not None and w.get("end") is not None
                      and low <= w["start"] < w["end"] <= high
                      and .1 <= w["end"]-w["start"] <= 2
                      and w.get("probability", 0) >= .8]
        if len(candidates) == 1:
            candidate = candidates[0]
            word.update(start=candidate["start"], end=candidate["end"], timing_status="recovered_model_alignment",
                        timing_method=method, timing_review_status="unreviewed",
                        recovery_probability=candidate["probability"])
            segment["start"] = min(segment["start"], word["start"])
            segment["end"] = max(segment["end"], word["end"])
            recovered += 1
    return {"method": method, "recovered_words": recovered, "review_status": "unreviewed"}


def _bound_transcript_segments_to_audio(
    raw_segments: Any,
    *,
    duration_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep transcript timestamps within the waveform actually processed.

    Faster-Whisper can occasionally emit a trailing timestamp beyond the input
    chunk. The canonical scene contract cannot claim speech beyond the audio
    file, so retain only overlapping text and make every correction observable.
    """
    duration = max(0.0, float(duration_seconds))
    normalized: list[dict[str, Any]] = []
    clipped_count = 0
    dropped_count = 0

    for raw in raw_segments if isinstance(raw_segments, list) else []:
        try:
            start = float(getattr(raw, "start"))
            end = float(getattr(raw, "end"))
        except (AttributeError, TypeError, ValueError):
            dropped_count += 1
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            dropped_count += 1
            continue

        bounded_start = min(duration, max(0.0, start))
        bounded_end = min(duration, max(0.0, end))
        if bounded_end <= bounded_start:
            dropped_count += 1
            continue
        if bounded_start != start or bounded_end != end:
            clipped_count += 1
        normalized.append({
            "start": bounded_start,
            "end": bounded_end,
            "text": str(getattr(raw, "text", "")).strip(),
            "confidence": (getattr(raw, "avg_logprob", None) if isinstance(getattr(raw, "avg_logprob", None), (int, float))
                           and math.isfinite(raw.avg_logprob) else None),
        })
        if isinstance(getattr(raw, 'phrase_timing', None), dict):
            normalized[-1]['phrase_timing'] = raw.phrase_timing
        for source_key, target_key in (("no_speech_prob", "no_speech_probability"),
                                       ("compression_ratio", "compression_ratio"),
                                       ("temperature", "temperature")):
            value = getattr(raw, source_key, None)
            if isinstance(value, (int, float)) and math.isfinite(value):
                normalized[-1][target_key] = value
        if getattr(raw, "words", None) is not None:
            words = []
            for word in raw.words:
                entry = {"text": str(getattr(word, "word", "")).strip()}
                start, end = getattr(word, "start", None), getattr(word, "end", None)
                valid = all(isinstance(t, (int, float)) and not isinstance(t, bool)
                            and math.isfinite(t) for t in (start, end))
                if valid and 0 <= start < end <= duration:
                    entry.update(start=start, end=end, timing_status="aligned")
                else:
                    # Retain the decoded word without inventing a playable time.
                    entry.update(start=None, end=None, timing_status="invalid_model_alignment",
                                 raw_start=start if isinstance(start, (int, float)) and math.isfinite(start) else None,
                                 raw_end=end if isinstance(end, (int, float)) and math.isfinite(end) else None)
                probability = getattr(word, "probability", None)
                if (isinstance(probability, (int, float)) and not isinstance(probability, bool)
                        and math.isfinite(probability) and 0 <= probability <= 1):
                    entry["probability"] = probability
                words.append(entry)
            normalized[-1]["words"] = words

    return normalized, {
        "status": "bounded" if clipped_count or dropped_count else "within_audio_bounds",
        "input_duration_seconds": duration,
        "clipped_segment_count": clipped_count,
        "dropped_segment_count": dropped_count,
    }


def _filter_no_speech_segments(
    segments: list[dict], threshold: Any, *, log_prob_threshold: Any = None,
) -> tuple[list[dict], dict]:
    """Reconcile no-speech scores with decoder and spoken-word confidence.

    A high no-speech score alone cannot veto confident dialogue. Honor the
    decoder's confidence exception when the words also meet its configured
    cutoff: decoder scores include non-word tokens and can mask weak words in
    sound-only hallucinations. Missing scores cannot establish speech absence.
    Mixed dialogue and all disputed candidates remain reviewable.
    """
    if (not isinstance(threshold, (int, float)) or isinstance(threshold, bool)
            or not math.isfinite(threshold) or not 0 <= threshold <= 1):
        return segments, {"status": "unavailable", "reason": "no_speech_threshold_missing"}
    valid_cutoff = (isinstance(log_prob_threshold, (int, float)) and not isinstance(log_prob_threshold, bool)
                    and math.isfinite(log_prob_threshold) and log_prob_threshold <= 0)
    accepted, rejected, uncertain, decisions = [], [], [], []
    for index, segment in enumerate(segments):
        probability = segment.get("no_speech_probability")
        if (isinstance(probability, (int, float)) and not isinstance(probability, bool)
                and math.isfinite(probability) and threshold < probability <= 1):
            uncertain.append(segment)
            confidence = segment.get("confidence")
            words = segment.get("words")
            probabilities = [w.get("probability") if isinstance(w, dict) else None
                             for w in words] if isinstance(words, list) else []
            valid_scores = (
                isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and math.isfinite(confidence)
                and confidence <= 0 and bool(probabilities)
                and all(isinstance(p, (int, float)) and not isinstance(p, bool)
                        and math.isfinite(p) and 0 <= p <= 1 for p in probabilities)
            )
            word_probability = None
            if valid_scores:
                word_probability = (math.exp(sum(math.log(p) for p in probabilities) / len(probabilities))
                                    if all(p > 0 for p in probabilities) else 0.0)
            reject = bool(valid_cutoff and valid_scores and (
                confidence <= log_prob_threshold or word_probability <= math.exp(log_prob_threshold)))
            decisions.append({"segment_index": index, "word_geometric_mean_probability": word_probability,
                              "decision": "reject" if reject else "retain",
                              "reason": "insufficient_confidence" if reject else (
                                  "decoder_and_words_support_text" if valid_cutoff and valid_scores else "confidence_evidence_unavailable")})
            (rejected if reject else accepted).append(segment)
        else:
            accepted.append(segment)
    # Mixed evidence establishes speech in the scene. Do not erase potentially
    # quiet dialogue merely because individual windows have conflicting scores.
    if accepted:
        accepted, rejected = segments, []
    else:
        uncertain = []
    return accepted, {
        "status": "completed", "rule": "whisper_no_speech_threshold", "threshold": threshold,
        "decoded_segment_count": len(segments), "accepted_segment_count": len(accepted),
        "sampled_segment_count": sum(
            isinstance(segment.get("temperature"), (int, float))
            and not isinstance(segment.get("temperature"), bool)
            and math.isfinite(segment["temperature"]) and segment["temperature"] > 0
            for segment in segments
        ),
        "rejected_segments": rejected,
        "uncertain_segments": uncertain,
        "confidence_override": {
            "method": "decoder_and_geometric_word_probability",
            "log_prob_threshold": log_prob_threshold if valid_cutoff else None,
            "segments": decisions,
        },
    }


def _normalize_transcription_vocabulary(value):
    """Validate explicit vocabulary; never derive identity or a forced transcript."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError("Transcription vocabulary must be a list of at most 32 terms")
    words, seen = [], set()
    for word in value:
        if not isinstance(word, str) or not word.strip() or len(word) > 64 or not all(c.isprintable() for c in word):
            raise ValueError("Transcription vocabulary terms must be printable, nonempty strings of at most 64 characters")
        word = word.strip()
        if word.casefold() not in seen:
            words.append(word)
            seen.add(word.casefold())
    return words


def _source_speech_regions(audio):
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    # Explicit verified settings: older packages otherwise default to a different
    # minimum speech duration. Model/version differences remain in the receipt.
    return get_speech_timestamps(audio, VadOptions(threshold=.5, min_speech_duration_ms=0,
        max_speech_duration_s=30, min_silence_duration_ms=2000, speech_pad_ms=400))


def _recognition_source_regions(audio):
    """Preserve every nonzero sample, splitting only literal digital silence.

    A 200 ms run of exact zero may delimit inputs; quantized zero crossings and
    quiet speech may not. Keep half the zero gap (up to 400 ms) on each side.
    Continuous recordings use the decoder's native bounded windows, not VAD cuts.
    """
    nonzero = np.flatnonzero(audio != 0)
    if not len(nonzero):
        return []
    starts, ends = [max(0, int(nonzero[0])-6400)], []
    for index in np.flatnonzero(np.diff(nonzero) > 3200):
        left, right = int(nonzero[index])+1, int(nonzero[index+1])
        padding = min(6400, (right-left)//2)
        ends.append(left+padding)
        starts.append(right-padding)
    ends.append(min(len(audio), int(nonzero[-1])+1+6400))
    return [{'start': start, 'end': end} for start, end in zip(starts, ends)]


def _native_phrase_timing(raw, tokenizer, model, duration):
    """Record pre-alignment decoder bounds; never infer them from word times.

    In 1.0.3 Segment.seek is the advanced cursor. Derive the encoder origin from
    the paired native timestamp tokens instead, and verify both ends. This is a
    model estimate, not evidence of accurate boundaries or a pure speaker.
    """
    result = {'status': 'unavailable', 'method': 'whisper_native_timestamp_tokens_v1',
              'review_status': 'unreviewed', 'timebase': 'input_audio_seconds',
              'independent_of_word_alignment': True, 'text': str(raw.text).strip()}
    tokens = list(getattr(raw, 'tokens', None) or [])
    begin, precision = tokenizer.timestamp_begin, model.time_precision
    start, end = raw.start, raw.end
    if (len(tokens) < 3 or not all(isinstance(t, int) for t in tokens)
            or not begin <= tokens[0] < tokens[-1] <= begin+1500
            or any(t >= begin for t in tokens[1:-1])):
        return {**result, 'reason': 'paired_native_timestamps_unavailable'}
    if tokenizer.decode(tokens).strip() != result['text']:
        return {**result, 'reason': 'native_text_evidence_mismatch'}
    if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end)):
        return {**result, 'reason': 'native_bounds_outside_input'}
    origin = start-(tokens[0]-begin)*precision
    frame_seconds = model.feature_extractor.hop_length/model.feature_extractor.sampling_rate
    seek = round(origin/frame_seconds)
    if (seek < 0 or abs(origin-seek*frame_seconds) > 1e-6
            or abs(end-(origin+(tokens[-1]-begin)*precision)) > 1e-6):
        return {**result, 'reason': 'native_clock_inconsistent'}
    window_end = min(duration, origin+model.feature_extractor.nb_max_frames*frame_seconds)
    if not 0 <= origin < window_end:
        return {**result, 'reason': 'native_clock_outside_input'}
    result.update(decoder_window={'start': origin, 'end': window_end}, encoder_seek_frames=seek)
    if not 0 <= start < end <= duration:
        # A valid encoder origin can still support word alignment. It does not
        # turn an out-of-input native phrase bound into a usable envelope.
        return {**result, 'reason': 'native_bounds_outside_input', 'raw_start': start, 'raw_end': end}
    result.update(start=start, end=end, timestamp_resolution_seconds=precision,
                  decoder_window={'start': origin, 'end': window_end},
                  timestamp_tokens=[tokens[0], tokens[-1]], encoder_seek_frames=seek,
                  status='model_estimated', boundary_status='unresolved')
    if start <= origin or end >= window_end:
        result['reason'] = 'native_phrase_touches_decode_boundary'
    elif not re.search(r'[.!?][\"\'\u2019\u201d]*$', result['text']):
        result['reason'] = 'native_phrase_not_closed'
    else:
        result['boundary_status'] = 'model_estimated_complete_phrase'
    return result


def _align_after_decoding(model, audio, raw_segments, language):
    """Align fixed decoded tokens on source audio without a second ASR pass.

    The installed APIs differ in batching. Only the two qualified API shapes
    are used; unsupported versions fail visibly to unavailable word evidence.
    The aligner's rewritten segment bounds never replace native phrase bounds.
    """
    from types import SimpleNamespace
    from importlib.metadata import version
    receipt = {'method': 'whisper_postdecode_alignment_v1', 'status': 'unavailable',
               'recognition_feedback': False, 'second_asr_pass': False, 'groups': []}
    copied = [SimpleNamespace(**(vars(raw) if hasattr(raw, '__dict__') else raw._asdict()))
              for raw in raw_segments]
    if not all(callable(getattr(model, name, None)) for name in
               ('feature_extractor', 'encode', 'add_word_timestamps')) or not hasattr(model, 'hf_tokenizer'):
        for raw in copied:
            raw.phrase_timing = {'status': 'unavailable', 'reason': 'native_decoder_evidence_unavailable'}
        return copied, receipt
    from faster_whisper.tokenizer import Tokenizer
    from faster_whisper.audio import pad_or_trim
    tokenizer = Tokenizer(model.hf_tokenizer, model.model.is_multilingual, task='transcribe', language=language)
    groups = {}
    installed = version('faster-whisper')
    for raw in copied:
        raw.phrase_timing = _native_phrase_timing(raw, tokenizer, model, len(audio)/16000)
        raw.words = None
        seek = raw.phrase_timing.get('encoder_seek_frames')
        # 1.2.1 exposes the original feature cursor even for unpaired native
        # delimiters. That supports word alignment, never complete-phrase claims.
        if seek is None and installed == '1.2.1':
            seek = getattr(raw, 'seek', None)
        if isinstance(seek, int) and 0 <= seek < len(audio)/model.feature_extractor.hop_length:
            groups.setdefault(seek, []).append(raw)
    receipt['package_version'] = installed
    if installed not in ('1.0.3', '1.2.1'):
        receipt['reason'] = 'alignment_api_version_unqualified'
        return copied, receipt
    try:
        features = model.feature_extractor(audio) if groups else None
    except Exception as exc:
        receipt['error'] = model_cache.redact_sensitive_info(str(exc))
        return copied, receipt
    last_speech_timestamp = 0.
    for seek, group in groups.items():
        row = {'encoder_seek_frames': seek, 'status': 'error'}
        receipt['groups'].append(row)
        try:
            padding = model.feature_extractor.nb_max_frames if installed == '1.0.3' else 1
            frames = min(model.feature_extractor.nb_max_frames, features.shape[-1]-padding-seek)
            if frames <= 0:
                raise ValueError('Native alignment window has no source frames')
            encoded = model.encode(pad_or_trim(features[:, seek:seek+frames], model.feature_extractor.nb_max_frames))
            aligned = [{'seek': seek, 'start': s.start, 'end': s.end, 'tokens': list(s.tokens)} for s in group]
            # Work on copies: library DTW heuristics mutate start/end in place.
            model.add_word_timestamps([aligned] if installed == '1.2.1' else aligned,
                tokenizer, encoded, frames, '\"\'“¿([{-', '\"\'.。,，!！?？:：”)]}、',
                last_speech_timestamp)
            for raw, item in zip(group, aligned):
                normalize = lambda value: re.sub(r'\s+', ' ', value).strip()
                if normalize(''.join(w['word'] for w in item.get('words', []))) != normalize(raw.text):
                    raise ValueError('Word alignment text does not match decoded segment')
            for raw, item in zip(group, aligned):
                raw.words = [SimpleNamespace(**word) for word in item.get('words', [])]
            last_speech_timestamp = max((w.end for raw in group for w in raw.words), default=last_speech_timestamp)
            row['status'] = 'completed'
        except Exception as exc:
            row['error'] = model_cache.redact_sensitive_info(str(exc))
    receipt['segments'] = [{'index': i, 'status': 'available' if raw.words else 'unavailable',
        'reason': None if raw.words else ('decoder_origin_unavailable'
            if not any(raw is s for group in groups.values() for s in group) else 'alignment_failed_or_empty')}
        for i, raw in enumerate(copied)]
    available = sum(bool(raw.words) for raw in copied)
    receipt['status'] = ('completed' if copied and available==len(copied) else 'partial'
                         if available else 'unavailable' if copied else 'not_applicable_no_decoded_text')
    return copied, receipt


def _transcribe_source_regions(model, audio, *, language, beam_size, temperature,
                               context_options, coverage, region_detector=None, partial_segments=None):
    """Decode original signal once; VAD measures presence but never cuts speech.

    Empty output, rejection, decoder-quality warnings and failure remain explicit.
    Processing every region does not establish that every spoken word was found.
    Only language detection uses the same bounded concatenated speech context as
    the old decoder. Word alignment follows decoding and cannot move its cursor.
    """
    from types import SimpleNamespace
    duration = len(audio) / 16000
    coverage.update(policy="source_audio_v2", status="running", timebase="input_audio_seconds", sample_rate=16000,
                    recognition_accuracy="unverified", detected_region_count=0,
                    attempted_region_count=0, completed_region_count=0, regions_without_text=0,
                    regions=[], vad_regions=[], recognition_region_count=0,
                    partition={'method': 'literal_zero_gaps', 'minimum_gap_seconds': .2, 'maximum_context_seconds': .4},
                    language_detection_scope="configured" if language else "first_30_seconds_of_detected_speech")
    accepted, qualities, first_info = partial_segments if partial_segments is not None else [], [], None
    timing = {"status": "within_audio_bounds", "input_duration_seconds": duration,
              "clipped_segment_count": 0, "dropped_segment_count": 0,
              "word_alignment": {'method': 'whisper_postdecode_alignment_v1', 'regions': [],
                                 'recognition_feedback': False, 'second_asr_pass': False}}
    current = None
    probability = None
    retry_options = None
    try:
        vad_regions = (region_detector or _source_speech_regions)(audio)
        previous_end = 0
        for region in vad_regions:
            start, end = region.get('start'), region.get('end')
            if (not all(isinstance(v, (int, np.integer)) and not isinstance(v, bool) for v in (start, end))
                    or not 0 <= previous_end <= start < end <= len(audio) or end-start > 30*16000):
                raise ValueError("Invalid transcription source region")
            coverage['vad_regions'].append({'start': start/16000, 'end': end/16000,
                'sample_start': int(start), 'sample_end': int(end)})
            previous_end = end
        regions = _recognition_source_regions(audio) if vad_regions else []
        coverage['recognition_region_count'] = len(regions)
        coverage['detected_region_count'] = len(vad_regions)
        coverage['nonzero_samples_total'] = int(np.count_nonzero(audio))
        coverage['nonzero_samples_delivered'] = 0
        coverage['input_samples_excluded_by_partition'] = len(audio)-sum(r['end']-r['start'] for r in regions)
        coverage['source_signal_preserved'] = bool(vad_regions) and sum(np.count_nonzero(audio[r['start']:r['end']]) for r in regions)==np.count_nonzero(audio)
        for index, region in enumerate(regions):
            start, end = region['start'], region['end']
            coverage['regions'].append({'index': index, 'sample_start': int(start), 'sample_end': int(end),
                'start': start/16000, 'end': end/16000, 'outcome': 'not_attempted', 'quality_flags': []})
        if language is None and vad_regions:
            # Bound allocation as well as model context to 30 seconds of speech.
            parts, remaining = [], 30*16000
            for region in vad_regions:
                part = audio[region['start']:min(region['end'], region['start']+remaining)]
                parts.append(part); remaining -= len(part)
                if not remaining: break
            context = np.concatenate(parts)
            if callable(getattr(model, 'detect_language', None)):
                language, probability, _ = model.detect_language(audio=context)
                coverage['language_detection_api'] = 'detect_language'
            else:
                # Faster-Whisper 1.0.3 computes language in transcribe's metadata
                # before returning its lazy decoder. Do not consume that generator:
                # the concatenated context is used only for language detection.
                _, detection = model.transcribe(context, language=None, beam_size=beam_size,
                    temperature=temperature, vad_filter=False, word_timestamps=False,
                    condition_on_previous_text=False)
                language, probability = detection.language, detection.language_probability
                coverage['language_detection_api'] = 'lazy_transcribe_metadata'
        elif language is not None:
            probability = 1. if regions else None  # Provenance helper hides configured certainty.
        for region, current in zip(regions, coverage['regions']):
            crop = audio[region['start']:region['end']]
            offset = region['start']/16000
            coverage['attempted_region_count'] += 1
            coverage['nonzero_samples_delivered'] += int(np.count_nonzero(crop))
            raw, region_info = model.transcribe(crop, language=language, beam_size=beam_size,
                temperature=temperature, vad_filter=False, word_timestamps=False,
                condition_on_previous_text=False, **context_options)
            collected, decode_error = [], None
            try:
                for item in raw:
                    collected.append(item)
            except Exception as exc:
                decode_error = exc
            try:
                raw, alignment = _align_after_decoding(model, crop, collected, language)
            except Exception as exc:
                # Recognition is already complete. Optional alignment failure
                # cannot erase its text or imply usable phrase/word evidence.
                raw = [SimpleNamespace(**(vars(s) if hasattr(s, '__dict__') else s._asdict())) for s in collected]
                for s in raw:
                    s.words = None
                    s.phrase_timing = {'status': 'unavailable', 'reason': 'alignment_setup_failed'}
                alignment = {'method': 'whisper_postdecode_alignment_v1', 'status': 'unavailable',
                    'recognition_feedback': False, 'second_asr_pass': False,
                    'error': model_cache.redact_sensitive_info(str(exc))}
            timing['word_alignment']['regions'].append({'source_region_index': current['index'], **alignment})
            if collected and alignment['status'] != 'completed':
                current['quality_flags'].append('word_alignment_unavailable')
            normalized, region_timing = _bound_transcript_segments_to_audio(raw, duration_seconds=len(crop)/16000)
            current['unplaced_segments'] = []
            for item in raw:
                start, end = getattr(item, 'start', None), getattr(item, 'end', None)
                finite = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (start, end))
                if not finite or min(len(crop)/16000, end) <= max(0., start):
                    current['unplaced_segments'].append({'text': str(getattr(item, 'text', '')).strip(),
                        'raw_start': start+offset if finite else None, 'raw_end': end+offset if finite else None})
            current['unplaced_segment_count'] = len(current['unplaced_segments'])
            if current['unplaced_segment_count']:
                current['quality_flags'].append('invalid_segment_timing')
            first_info = first_info or region_info
            options = getattr(region_info, 'transcription_options', None)
            for segment in normalized:
                segment['start'] += offset; segment['end'] += offset
                segment['source_region_index'] = current['index']
                phrase = segment.get('phrase_timing') or {}
                for bounds in (phrase, phrase.get('decoder_window') or {}):
                    for key in ('start', 'end', 'raw_start', 'raw_end'):
                        if isinstance(bounds.get(key), (int, float)): bounds[key] += offset
                for word in segment.get('words', []):
                    for key in ('start', 'end', 'raw_start', 'raw_end'):
                        if isinstance(word.get(key), (int, float)): word[key] += offset
                for field, option, flag, above in (
                        ('compression_ratio', 'compression_ratio_threshold', 'compression_ratio_threshold_exceeded', True),
                        ('confidence', 'log_prob_threshold', 'log_probability_below_threshold', False)):
                    value, cutoff = segment.get(field), getattr(options, option, None)
                    if (isinstance(value, (int, float)) and isinstance(cutoff, (int, float))
                            and math.isfinite(value) and math.isfinite(cutoff)
                            and (value > cutoff if above else value < cutoff)):
                        current['quality_flags'].append(flag)
                if any(w.get('timing_status') == 'invalid_model_alignment' for w in segment.get('words', [])):
                    current['quality_flags'].append('invalid_word_timing')
            selected, quality = _filter_no_speech_segments(normalized,
                getattr(options, 'no_speech_threshold', None), log_prob_threshold=getattr(options, 'log_prob_threshold', None))
            quality['source_region_index'] = current['index']
            qualities.append(quality); accepted.extend(selected)
            current.update(outcome='text_returned' if any(s.get('text') for s in selected) else (
                'text_with_unavailable_timing' if current['unplaced_segments'] else (
                    'rejected_no_speech_candidate' if quality.get('rejected_segments') else 'no_text_returned')),
                decoded_segment_count=len(normalized), accepted_segment_count=len(selected),
                quality_flags=sorted(set(current['quality_flags'])))
            if decode_error is not None:
                current['partial_segment_count'] = len(selected)
                raise decode_error
            coverage['completed_region_count'] += 1
            coverage['regions_without_text'] += current['outcome'] != 'text_returned'
            for key in ('clipped_segment_count', 'dropped_segment_count'):
                timing[key] += region_timing[key]
        coverage['status'] = 'completed' if vad_regions else 'not_applicable_no_detected_speech'
    except Exception as exc:
        coverage['status'] = 'error'
        coverage['error'] = model_cache.redact_sensitive_info(str(exc))
        if current is not None:
            current['outcome'] = 'error'
            current['error'] = coverage['error']
        raise
    quality = dict(qualities[0]) if qualities else {'status': 'completed', 'rule': 'whisper_no_speech_threshold', 'threshold': None}
    quality.pop('confidence_override', None)  # Decisions belong to their recorded region.
    quality.pop('source_region_index', None)
    quality['scope'] = 'per_source_region'
    quality['whole_input_no_speech_supported'] = bool(regions) and all(
        row['outcome'] == 'rejected_no_speech_candidate' and not row['unplaced_segments']
        for row in coverage['regions'])
    if any(q.get('status') != 'completed' for q in qualities): quality['status'] = 'unavailable'
    for key in ('decoded_segment_count', 'accepted_segment_count', 'sampled_segment_count'):
        quality[key] = sum(q.get(key, 0) for q in qualities)
    for key in ('rejected_segments', 'uncertain_segments'):
        quality[key] = [s for q in qualities for s in q.get(key, [])]
    quality['region_results'] = qualities
    if timing['clipped_segment_count'] or timing['dropped_segment_count']: timing['status'] = 'bounded'
    info = SimpleNamespace(language=language, language_probability=probability, duration=duration,
        duration_after_vad=sum((r['end']-r['start'])/16000 for r in vad_regions),
        transcription_options=getattr(first_info, 'transcription_options', None), timing_retry_options=retry_options)
    return accepted, info, timing, quality


def _transcription_temperature(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("transcription temperature must be a finite number from 0 to 1; fallback schedules are unsupported")
    return float(value)


def _resolved_transcription_options(info):
    from dataclasses import asdict, is_dataclass
    options = getattr(info, 'transcription_options', None)
    if is_dataclass(options):
        return asdict(options)
    return options._asdict() if hasattr(options, '_asdict') else None


def transcribe_file(model, path, *, temperature=0., vocabulary=None, language=None,
                    beam_size=5, offset=0., engine="faster-whisper"):
    """Run the shared source-region policy for a retained transcription caller.

    Keep partial words and failed/unattempted region receipts on decoder failure.
    No diarization turn or fixed caller chunk may remove source audio here.
    """
    from faster_whisper.audio import decode_audio
    temperature = _transcription_temperature(temperature)
    vocabulary = _normalize_transcription_vocabulary(vocabulary)
    if not isinstance(offset, (int, float)) or not math.isfinite(offset) or offset < 0:
        raise ValueError("Invalid transcription source offset")
    requested_language = str(language or '').strip()
    requested_language = None if requested_language.lower() in ('', 'auto', 'detect', 'none') else requested_language
    coverage, partial = {}, []
    result = {'status': 'error', 'transcription_status': 'error', 'transcription': '',
        'segments': partial, 'engine': engine, 'transcription_context': {
            'status': 'applied' if vocabulary else 'not_supplied', 'source': 'request_config',
            'kind': 'vocabulary_hints', 'words': vocabulary, 'identity_claim': False},
        'transcription_decoding': {'policy': 'single_temperature_v1', 'temperature': temperature,
            'sampling_enabled': temperature > 0, 'temperature_fallback': False,
            'source': 'request_config', 'beam_size': beam_size, 'primary': None,
            'source_regions': coverage, 'timing_retry': None}}
    try:
        audio = decode_audio(str(path), sampling_rate=16000)
        if audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
            raise ValueError('Audio must decode to finite, nonempty mono samples')
        result['duration_seconds'] = len(audio)/16000
        segments, info, timing, quality = _transcribe_source_regions(model, audio,
            language=requested_language, beam_size=beam_size, temperature=temperature,
            context_options={'hotwords': ', '.join(vocabulary)} if vocabulary else {},
            coverage=coverage, partial_segments=partial)
        result.update(status='success', transcription_status='success', segments=segments,
            transcription_timing=timing, transcription_quality=quality, language=info.language)
        result['transcription_decoding'].update(primary=_resolved_transcription_options(info),
            language=_transcription_language_evidence(info, requested_language), timing_retry=info.timing_retry_options)
        result['language_probability'] = result['transcription_decoding']['language']['detection_probability']
        result['speech_detection'] = {'status': 'completed', 'method': 'silero_vad',
            'input_duration_seconds': info.duration, 'speech_duration_seconds': info.duration_after_vad}
    except Exception as exc:
        error = model_cache.redact_sensitive_info(str(exc))
        result.update(error=error, transcription_error=error)
        coverage.update(status='error', error=error)
    if offset:
        # Segment words also appear in quality receipts: shift shared objects once.
        seen = set()
        def shift(value):
            if not isinstance(value, (dict, list)) or id(value) in seen: return
            seen.add(id(value))
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ('start', 'end', 'raw_start', 'raw_end') and isinstance(item, (int, float)):
                        value[key] = item+offset
                    elif key in ('sample_start', 'sample_end') and isinstance(item, int):
                        value[key] = item+round(offset*16000)
                    else: shift(item)
            else:
                for item in value: shift(item)
        shift(result)
        coverage.update(timebase='source_audio_seconds', source_offset_seconds=offset)
    result['transcription'] = ' '.join(s['text'].strip() for s in result['segments'] if s.get('text'))
    result['word_timestamps'] = [w for s in result['segments'] for w in s.get('words', [])]
    result['word_alignment'] = {'method': 'whisper_cross_attention_dtw' if engine=='faster-whisper' else 'unavailable',
        'status': 'available' if result['word_timestamps'] else 'no_word_alignment',
        'timebase': 'source_audio_seconds' if offset else 'input_audio_seconds',
        'review_status': 'unreviewed', 'words': result['word_timestamps']}
    return result


def _transcription_language_evidence(info, requested_language):
    """A configured language's synthetic 1.0 is not detection confidence."""
    probability = getattr(info, "language_probability", None)
    valid_probability = (isinstance(probability, (int, float)) and not isinstance(probability, bool)
                         and math.isfinite(probability) and 0 <= probability <= 1)
    speech_seconds = getattr(info, "duration_after_vad", None)
    no_speech = (isinstance(speech_seconds, (int, float)) and not isinstance(speech_seconds, bool)
                 and speech_seconds == 0)
    configured = requested_language is not None
    status = ("not_applicable_no_detected_speech" if no_speech else
              "configured_not_detected" if configured else
              "model_estimate_unreviewed" if valid_probability else "language_evidence_unavailable")
    return {"mode": "configured" if configured else "automatic", "status": status,
            "requested_language": requested_language, "reported_language": getattr(info, "language", None),
            "detection_probability": float(probability) if valid_probability and not configured and not no_speech else None,
            "score_kind": "uncalibrated_model_probability" if not configured and not no_speech else "not_applicable",
            "code_switching_qualified": False}
