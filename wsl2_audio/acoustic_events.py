"""Offline sound evidence and conservative, speaker-bound emotion input selection.

AudioSet scores are model estimates. Window bounds are exclusion regions, not
precise event onset annotations. Failed/unknown evidence never permits scoring.
"""
from __future__ import annotations

import math
import re

MODEL_ID = "MIT/ast-finetuned-audioset-10-10-0.4593"
MODEL_REVISION = "f826b80d28226b62986cc218e5cec390b1096902"
WINDOW_SECONDS = 10.0
HOP_SECONDS = 5.0
EVENT_THRESHOLD = .1
SPEECH_THRESHOLD = .5
MIN_VAD_COVERAGE = .8
MUSIC_CONTEXT_SECONDS = .5
WORD_THRESHOLD = .8
MIN_SPEECH_SECONDS = 0.3
MAX_SPEECH_SECONDS = 6.0
POLICY = "clear_speech_only_v2"
NON_SPEECH_LABELS = {
    "Crying, sobbing": "crying", "Baby cry, infant cry": "crying",
    "Whimper": "whimpering", "Wail, moan": "wailing",
    "Screaming": "screaming", "Shout": "shouting", "Yell": "shouting",
    "Bellow": "shouting", "Whoop": "whooping",
    "Laughter": "laughter", "Baby laughter": "laughter", "Giggle": "laughter",
    "Chuckle, chortle": "laughter", "Belly laugh": "laughter", "Snicker": "laughter",
    "Babbling": "babbling", "Singing": "singing", "Child singing": "singing",
    "Humming": "humming", "Groan": "groaning", "Grunt": "grunting",
    "Sigh": "sighing", "Cough": "coughing", "Sneeze": "sneezing",
    "Gasp": "gasping", "Snoring": "snoring", "Music": "music",
}


def _interval(row, duration):
    start, end = row.get("start"), row.get("end")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
               for x in (start, end)) or not 0 <= start < end <= duration:
        return None
    return float(start), float(end)


def _overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


def _continuous_intersection(span, intervals):
    """Return observed support within a span; never fill a hole or extend it."""
    pieces = sorted((max(span[0], s), min(span[1], e)) for s, e in intervals
                    if _overlap(span, (s, e)))
    if not pieces:
        return None
    start, end = pieces[0]
    for left, right in pieces[1:]:
        if left > end:
            return None
        end = max(end, right)
    return start, end


def _speaker_support(span, tracks, duration):
    intersecting = [t for t in tracks if _interval(t, duration)
                    and _overlap(span, _interval(t, duration))]
    speakers = {t.get("speaker") for t in intersecting}
    if len(speakers) != 1 or not all(isinstance(s, str) and s.strip() for s in speakers):
        return None
    support = _continuous_intersection(span, [_interval(t, duration) for t in intersecting])
    return (next(iter(speakers)), support) if support else None


def _phrase_groups(words, *, endings=r"[.!?]"):
    groups, group = [], []
    for word in words:
        group.append(word)
        if re.search(endings + r"[\"'\u2019\u201d]*$", str(word.get("text") or "").strip()):
            groups.append((group, "terminal_punctuation"))
            group = []
    if group:
        groups.append((group, "transcript_segment_end"))
    return groups


def _local_overlap_observation(result, duration, key="overlap_detection"):
    observation = result.get(key)
    if observation is None:
        return None, []  # Historical records without this observation stay readable.
    if (isinstance(observation, dict) and observation.get("status") == "not_applicable"
            and observation.get("reason") == "no_speech_detected" and not result.get("word_timestamps")):
        return True, []
    if not isinstance(observation, dict) or observation.get("status") != "ok":
        return False, []
    intervals = observation.get("intervals")
    if not isinstance(intervals, list) or any(not isinstance(r, dict) or _interval(r, duration) is None for r in intervals):
        return False, []
    return True, intervals


def _overlap_observations(result, duration):
    local_ready, local = _local_overlap_observation(result, duration)
    additional_ready, additional = _local_overlap_observation(result, duration, "additional_overlap_detection")
    return local_ready is not False and additional_ready is not False, local, additional


def speaker_purity_exclusions(result, duration):
    """A speaker change inside a phrase is not proof that either side is pure.

    Diarization can render a mixture as sequential labels. Withhold the entire
    observed phrase from individual inference without claiming detected overlap.
    This veto is independent of emotion duration limits and token confidence.
    """
    tracks = [t for t in result.get("diarization") or [] if _interval(t, duration)]
    _, local_overlap, additional_overlap = _overlap_observations(result, duration)
    excluded = []
    for index, segment in enumerate(result.get("segments") or []):
        for words, boundary in _phrase_groups(segment.get("words") or []):
            span = _interval({"start": words[0].get("start"), "end": words[-1].get("end")}, duration)
            unresolved_boundary = span is None
            if unresolved_boundary:
                # Missing edges cannot release the remaining phrase as voice
                # samples. This covers observed word audio for exclusion only;
                # it is not a recovered phrase envelope or an admission bound.
                timed_words = [s for w in words if (s := _interval(w, duration))]
                if not timed_words:
                    continue  # Every word already fails individual timing admission.
                span = (min(s[0] for s in timed_words), max(s[1] for s in timed_words))
            active = [t for t in tracks if _overlap(span, _interval(t, duration))]
            speakers = sorted({t["speaker"] for t in active
                               if isinstance(t.get("speaker"), str) and t["speaker"].strip()})
            local = [r for r in local_overlap if _overlap(span, (r["start"], r["end"]))]
            additional = [r for r in additional_overlap if _overlap(span, (r["start"], r["end"]))]
            if not unresolved_boundary and len(speakers) < 2 and not local and not additional:
                continue
            exclusion = {"start": span[0], "end": span[1], "source_segment_index": index,
                "boundary_source": boundary, "speaker_candidates": speakers,
                "reason": ("phrase_speakers_unresolved" if len(speakers) >= 2 else
                           "local_overlap_in_phrase" if local else
                           "additional_overlap_in_phrase" if additional else "phrase_boundary_timing_unavailable"),
                "local_overlap_intervals": local, "review_status": "unreviewed",
                "additional_overlap_intervals": additional,
                "overlap_observed": bool(local or additional) or any(a.get("speaker") in speakers and b.get("speaker") in speakers
                    and a["speaker"] != b["speaker"] and _overlap(_interval(a, duration), _interval(b, duration))
                    for i, a in enumerate(active) for b in active[i+1:])}
            if unresolved_boundary:
                exclusion.update(boundary_status="unresolved", exclusion_scope="observed_word_audio_only")
            excluded.append(exclusion)
    return excluded


def select_speech_intervals(result, windows, duration, *, purity_exclusions=None):
    """Select reliable word audio inside continuous, exclusive speaker support.

    Original word/turn timestamps remain untouched. Boundary disagreement may
    shrink selected audio, but cannot extend a turn or rescue competing speakers.
    """
    tracks = result.get("diarization") or []
    words = result.get("word_timestamps") or []
    overlap_ready, local_overlap, additional_overlap = _overlap_observations(result, duration)
    if purity_exclusions is None:
        purity_exclusions = speaker_purity_exclusions(result, duration)
    # Generated phrase bounds are not frame-level overlap boundaries. Do not
    # claim an isolated prefix/suffix of a phrase already known to overlap.
    uncertain_turns = []
    if (result.get("diarization_timing") or {}).get("boundary_precision") == "phrase":
        valid_tracks = [t for t in tracks if _interval(t, duration)]
        uncertain_turns = [_interval(t, duration) for t in valid_tracks if any(
            other.get("speaker") != t.get("speaker")
            and _overlap(_interval(t, duration), _interval(other, duration)) for other in valid_tracks)]
    selected, rejected = [], []
    can_join = False
    for word in sorted(words, key=lambda w: w.get("start") if isinstance(w.get("start"), (int, float)) else -1):
        span = _interval(word, duration)
        probability = word.get("probability")
        reason = None
        adjustment = None
        speaker = None
        if (span is None or not str(word.get("text") or "").strip()
                or not isinstance(probability, (int, float)) or isinstance(probability, bool)
                or not math.isfinite(probability) or not WORD_THRESHOLD <= probability <= 1):
            reason = "unreliable_word_alignment"
        if reason is None and any(_overlap(span, turn) for turn in uncertain_turns):
            reason = "overlapping_phrase_timing_unresolved"
        if reason is None and overlap_ready is False:
            reason = "overlap_detection_unavailable"
        if reason is None:
            exclusion = next((p for p in purity_exclusions if _overlap(span, (p["start"], p["end"]))), None)
            if exclusion:
                reason = exclusion["reason"]
            elif any(_overlap(span, (p["start"], p["end"])) for p in local_overlap):
                reason = "local_overlap_detected"
            elif any(_overlap(span, (p["start"], p["end"])) for p in additional_overlap):
                reason = "additional_overlap_detected"
        if reason is None:
            support = _speaker_support(span, tracks, duration)
            if result.get("diarization_status") != "success" or support is None:
                reason = "missing_or_overlapping_speakers"
            else:
                speaker, selected_span = support
                if selected_span != span:
                    adjustment = {"word_start": span[0], "word_end": span[1],
                                  "selected_start": selected_span[0], "selected_end": selected_span[1],
                                  "method": "word_speaker_intersection", "review_status": "unreviewed"}
                span = selected_span
        covering = []
        if reason is None:
            intersecting = [w for w in windows if _interval(w, duration) and _overlap(span, _interval(w, duration))]
            # A partial or missing acoustic assessment cannot clear the word.
            covering = [w for w in intersecting if w["start"] <= span[0] and w["end"] >= span[1]]
            if (not covering or any(w.get("excluded_labels") or
                    not isinstance(w.get("speech_score"), (int, float)) or
                    not SPEECH_THRESHOLD <= w["speech_score"] <= 1 for w in intersecting)):
                reason = "non_speech_or_uncertain_audio"
        if reason:
            rejected.append({"start": word.get("start"), "end": word.get("end"), "reason": reason})
            can_join = False
            continue
        start, end = span
        previous = selected[-1] if selected else None
        gap = (previous["end"], start) if previous else None
        unsafe_gap = gap and gap[0] < gap[1] and any(
            _interval(w, duration) and _overlap(gap, _interval(w, duration))
            and (w.get("excluded_labels") or w.get("speech_score", 0) < SPEECH_THRESHOLD) for w in windows)
        if gap and gap[0] < gap[1] and any(_overlap(gap, (r["start"], r["end"]))
                                          for r in local_overlap + additional_overlap):
            unsafe_gap = True
        # Missing speaker/acoustic observations are not silent, safe gaps.
        gap_supported = not gap or gap[0] == gap[1] or (
            gap[0] < gap[1] and _speaker_support(gap, tracks, duration) == (speaker, gap)
            and _continuous_intersection(gap, [_interval(w, duration) for w in windows
                                               if _interval(w, duration)]) == gap)
        if (can_join and previous and previous["speaker"] == speaker and 0 <= start - previous["end"] <= .35
                and end - previous["start"] <= MAX_SPEECH_SECONDS and not unsafe_gap and gap_supported):
            previous["end"] = end
            previous["word_count"] += 1
        else:
            selected.append({"start": start, "end": end, "speaker": speaker, "word_count": 1})
        if adjustment:
            selected[-1].setdefault("timing_adjustments", []).append(adjustment)
        can_join = True
    kept = []
    for segment in selected:
        if MIN_SPEECH_SECONDS <= segment["end"] - segment["start"] <= MAX_SPEECH_SECONDS:
            kept.append(segment)
        else:
            rejected.append({**segment, "reason": "insufficient_contiguous_speech"})
    return kept, rejected


def emotion_phrase_candidates(result, duration, *, purity_exclusions=None):
    """Keep entire observed transcript phrases; never manufacture one from accepted words."""
    candidates, rejected = [], []
    tracks = result.get("diarization") or []
    segments = result.get("segments") or []
    overlap_ready, local_overlap, additional_overlap = _overlap_observations(result, duration)
    if purity_exclusions is None:
        purity_exclusions = speaker_purity_exclusions(result, duration)
    if not segments and result.get("word_timestamps"):
        return [], [{"reason": "phrase_boundaries_unavailable"}]
    for segment_index, segment in enumerate(segments):
        words = segment.get("words") or []
        native = segment.get('phrase_timing')
        native_unresolved = None
        if isinstance(native, dict):
            reason = None
            if 'text' in native and native.get('text') != str(segment.get('text') or '').strip():
                reason = 'phrase_text_evidence_mismatch'
            elif any(key in native for key in ('start', 'end')) and _interval(native, duration) is None:
                reason = 'native_phrase_bounds_invalid'
            elif (native.get('status') != 'model_estimated'
                    or native.get('boundary_status') != 'model_estimated_complete_phrase'
                    or native.get('independent_of_word_alignment') is not True
                    or native.get('method') != 'whisper_native_timestamp_tokens_v1'
                    or native.get('text') != str(segment.get('text') or '').strip()
                    or _interval(native, duration) is None):
                reason = 'native_phrase_boundaries_unavailable'
            if reason:
                # Retain the already-supported complete-word path when the
                # native producer has no usable envelope. This never rescues a
                # contradictory native clock/text/bound or a failed speech gate.
                if reason == 'native_phrase_boundaries_unavailable' and native.get('reason') in {'native_phrase_touches_decode_boundary', 'native_phrase_not_closed',
                        'paired_native_timestamps_unavailable', 'native_decoder_evidence_unavailable'}:
                    native_unresolved, native = native, None
                else:
                    rejected.append({'start': native.get('start'), 'end': native.get('end'),
                        'text': segment.get('text'), 'reason': reason, 'source_segment_index': segment_index,
                        'boundary_detail': native.get('reason'), 'boundary_status': 'unresolved'})
                    continue
        native_context, conflicting_units = None, set()
        if native:
            text_groups = _phrase_groups([{'text': token} for token in native['text'].split()], endings=r'[!?]')
            if len(text_groups) > 1:
                # A decoder timestamp pair can enclose several utterances.
                # Only question/exclamation endings split native blocks here;
                # periods/ellipses need stronger evidence than punctuation alone.
                # Choose their units before any speaker/acoustic admission;
                # never split a rejected phrase to salvage its accepted words.
                groups = _phrase_groups(words, endings=r'[!?]')
                text_key = lambda group: re.sub(r'\s+', '', ''.join(str(w.get('text') or '') for w in group))
                if (len(groups) != len(text_groups) or any(text_key(a) != text_key(b)
                        for (a, _), (b, _) in zip(groups, text_groups))):
                    rejected.append({'start': native['start'], 'end': native['end'],
                        'text': native['text'], 'source_segment_index': segment_index,
                        'reason': 'phrase_word_evidence_mismatch', 'boundary_status': 'unresolved'})
                    continue
                native_context, native = native, None
                unit_spans = [_interval({'start': group[0].get('start'), 'end': group[-1].get('end')}, duration)
                              for group, _ in groups]
                conflicting_units = {i for i, span in enumerate(unit_spans) if span and any(
                    other and (span[1] > other[0] if i < j else other[1] > span[0])
                    for j, other in enumerate(unit_spans) if i != j)}
            else:
                groups = [(words, 'native_decoder_segment')]
        elif not words:
            if str(segment.get("text") or "").strip():
                rejected.append({"start": segment.get("start"), "end": segment.get("end"),
                                 "text": segment.get("text"), "reason": "phrase_word_timing_unavailable"})
            continue
        else:
            groups = _phrase_groups(words)  # Historical evidence stays readable.
        for utterance_index, (phrase_words, boundary) in enumerate(groups):
            row = {"start": native['start'] if native else phrase_words[0].get("start"),
                   "end": native['end'] if native else phrase_words[-1].get("end"),
                   "text": native['text'] if native else " ".join(str(w.get("text") or "").strip() for w in phrase_words),
                   "word_count": len(phrase_words), "source_segment_index": segment_index,
                   "boundary_source": boundary, "boundary_status": "model_estimated_complete_phrase"}
            row['timing_basis'] = 'native_decoder_envelope' if native else 'complete_word_alignment'
            if native_unresolved:
                row['native_boundary_evidence'] = native_unresolved
            if native_context:
                row['native_boundary_evidence'] = native_context
                row['source_utterance_index'] = utterance_index
            # Whisper token likelihood measures recognition, not timestamp
            # accuracy. Preserve that uncertainty for every word, including the
            # edges; it cannot manufacture a hole in otherwise timed speech.
            row["uncertain_transcript_words"] = [w.get("text") for w in phrase_words
                if not isinstance(w.get("probability"), (int, float)) or isinstance(w.get("probability"), bool)
                or not math.isfinite(w["probability"]) or not WORD_THRESHOLD <= w["probability"] <= 1]
            spans = [_interval(w, duration) for w in phrase_words]
            reason = None
            if native:
                row['word_timing_status'] = ('unavailable_or_uncertain' if not spans or any(s is None for s in spans)
                    or any(a[1] > b[0] for a, b in zip(spans, spans[1:]) if a and b) else 'model_estimated')
                row['boundary_evidence'] = native
            if not native and (any(s is None for s in spans) or any(not str(w.get("text") or "").strip() for w in phrase_words)
                    or any(a[1] > b[0] for a, b in zip(spans, spans[1:]) if a and b)):
                reason = "phrase_word_timing_unavailable"
            elif utterance_index in conflicting_units:
                reason = 'utterance_word_timing_conflict'
            elif native_context and (row['start'] < native_context['start'] or row['end'] > native_context['end']):
                reason = 'phrase_word_bounds_outside_native_envelope'
            elif not MIN_SPEECH_SECONDS <= row["end"] - row["start"] <= MAX_SPEECH_SECONDS:
                reason = "phrase_duration_outside_limits"
            elif not native and any(w not in (result.get("word_timestamps") or []) for w in phrase_words):
                reason = "phrase_word_evidence_mismatch"
            elif overlap_ready is False:
                reason = "overlap_detection_unavailable"
            else:
                span = (row["start"], row["end"])
                support = _speaker_support(span, tracks, duration)
                if result.get("diarization_status") != "success" or support is None:
                    reason = "phrase_speakers_unresolved"
                    active = [t for t in tracks if _interval(t, duration)
                              and _overlap(span, _interval(t, duration))]
                    row["speaker_candidates"] = sorted({t["speaker"] for t in active
                        if isinstance(t.get("speaker"), str) and t["speaker"].strip()})
                    row["overlap_intervals"] = sorted([
                        {"start": max(span[0], a["start"], b["start"]),
                         "end": min(span[1], a["end"], b["end"]),
                         "speakers": sorted([a["speaker"], b["speaker"]]),
                         "review_status": "unreviewed"}
                        for i, a in enumerate(active) for b in active[i+1:]
                        if isinstance(a.get("speaker"), str) and isinstance(b.get("speaker"), str)
                        and a["speaker"].strip() and b["speaker"].strip() and a["speaker"] != b["speaker"]
                        and _overlap(_interval(a, duration), _interval(b, duration))],
                        key=lambda t: (t["start"], t["end"], t["speakers"]))
                elif (result.get("diarization_timing") or {}).get("boundary_precision") == "phrase" and any(
                    _interval(t, duration) and _overlap(span, _interval(t, duration)) and any(
                        _interval(other, duration) and other.get("speaker") != t.get("speaker")
                        and _overlap(_interval(t, duration), _interval(other, duration)) for other in tracks)
                    for t in tracks):
                    reason = "overlapping_phrase_timing_unresolved"
                else:
                    row["speaker"] = support[0]
                    # Native bounds may cover audio outside the word envelope.
                    # Both overlap detectors must veto that whole interval too.
                    local = [p for p in local_overlap if _overlap(span, (p['start'], p['end']))]
                    additional = [p for p in additional_overlap if _overlap(span, (p['start'], p['end']))]
                    if local or additional:
                        reason = 'local_overlap_in_phrase' if local else 'additional_overlap_in_phrase'
                        row.pop('speaker')
                        row['overlap_intervals'] = local
                        row['additional_overlap_intervals'] = additional
                    # Also honor an ambiguous phrase in another transcript row
                    # covering this audio; a second segmentation cannot rescue it.
                    exclusion = next((p for p in purity_exclusions if _overlap(span, (p["start"], p["end"]))
                        and not (native and p.get('source_segment_index') == segment_index
                            and p.get('reason') == 'phrase_boundary_timing_unavailable'
                            and len(p.get('speaker_candidates', [])) <= 1
                            and not p.get('local_overlap_intervals') and not p.get('additional_overlap_intervals'))), None)
                    if exclusion:
                        reason = exclusion["reason"]
                        row.pop("speaker", None)
                        row["speaker_candidates"] = exclusion["speaker_candidates"]
                        row["overlap_intervals"] = exclusion.get("local_overlap_intervals", [])
                        row["additional_overlap_intervals"] = exclusion.get("additional_overlap_intervals", [])
            (rejected if reason else candidates).append({**row, "reason": reason} if reason else row)
    return candidates, rejected


def _acoustic_basis(window, meta):
    if window and str(window.get("analysis_status", "")).startswith("unavailable"):
        return False, [], False
    coverage = window.get("vad_speech_coverage") if window else None
    ast_score = window.get("speech_score") if window else None
    sources = []
    if (isinstance(coverage, (int, float)) and not isinstance(coverage, bool)
            and math.isfinite(coverage) and MIN_VAD_COVERAGE <= coverage <= 1):
        sources.append("silero_vad")
    if (isinstance(ast_score, (int, float)) and not isinstance(ast_score, bool)
            and math.isfinite(ast_score) and SPEECH_THRESHOLD <= ast_score <= 1):
        sources.append("audioset_speech")
    context = (window or {}).get("context_check") or {}
    score = context.get("speech_score")
    corroborated = (window and window["excluded_labels"] == ["music"] and "silero_vad" in sources
        and context.get("status") == "assessed" and context.get("speaker_support_checked") is True
        and context.get("excluded_labels") == [] and isinstance(score, (int, float)) and not isinstance(score, bool)
        and math.isfinite(score) and SPEECH_THRESHOLD <= score <= 1)
    accepted = bool(window and (not window["excluded_labels"] or corroborated)
        and (meta.get("speech_presence") or {}).get("status") == "success" and sources)
    return accepted, sources, corroborated


def select_complete_emotion_phrases(candidates, rejected, meta, result, duration):
    selected, withheld = [], list(rejected)
    for candidate in candidates:
        span = (candidate["start"], candidate["end"])
        window = next((w for w in meta.get("phrase_windows", [])
                       if abs(w["start"]-span[0]) < .001 and abs(w["end"]-span[1]) < .001), None)
        accepted, sources, corroborated = _acoustic_basis(window, meta)
        regions = (meta.get("speech_presence") or {}).get("regions")
        reason = None
        if not accepted:
            reason = "phrase_acoustics_uncertain_or_non_speech"
        elif not isinstance(regions, list) or any(_interval(s, duration) is None for s in regions):
            reason = "phrase_speech_presence_unavailable"
        else:
            # Unobserved silence may surround a word. Every observed speech sample
            # still needs the same exclusive speaker; never trim an unsupported word.
            speech = [(max(span[0], s["start"]), min(span[1], s["end"])) for s in regions
                      if _overlap(span, (s["start"], s["end"]))]
            support = speech or [span]
            if any(_speaker_support(s, result.get("diarization") or [], duration)
                   != (candidate["speaker"], s) for s in support):
                reason = "phrase_speaker_boundary_unresolved"
        if reason:
            withheld.append({**candidate, "reason": reason})
        else:
            row = {**candidate, "speech_presence_basis": sources}
            if corroborated:
                row["acoustic_context"] = {**window["context_check"], "review_status": "unreviewed",
                                           "target_disagreement": "music_only_not_corroborated"}
            selected.append(row)
    return {"policy": "complete_observed_phrases_v1", "status": "ready" if selected else "insufficient_evidence",
            "selected": selected, "rejected": withheld,
            "selected_seconds": sum(s["end"]-s["start"] for s in selected),
            "boundary_qualification": "model_estimated_not_human_verified"}


def emotion_uncertainty(segment):
    """Execution success is not accuracy qualification; do not invent a score cutoff."""
    reasons = ["model_accuracy_not_qualified", "uncalibrated_model_scores", "phrase_boundaries_unreviewed"]
    if segment.get("uncertain_transcript_words"):
        reasons.append("transcript_words_uncertain")
    return {"interpretation_status": "uncertain", "uncertainty_reasons": reasons,
            "model_qualification": "unqualified", "score_kind": "uncalibrated_softmax"}


def detect_sound_events(waveform, sample_rate, *, cache_dir, device, speech_intervals=None, speaker_tracks=None,
                        emotion_phrases=None):
    import torch
    import torchaudio
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    model = extractor = None
    try:
        if not waveform.numel() or not torch.isfinite(waveform).all():
            raise ValueError("Empty or non-finite acoustic input")
        audio = waveform.detach().cpu().mean(dim=0)
        if not torch.count_nonzero(audio) and torch.count_nonzero(waveform):
            raise ValueError("Mono downmix cancelled nonzero source channels")
        if sample_rate != 16000:
            audio = torchaudio.functional.resample(audio, sample_rate, 16000)
        # Detect speech once on the original waveform. VAD and AudioSet Speech
        # have distinct failure modes; keep both observations, not a blended score.
        vad_options = VadOptions(threshold=SPEECH_THRESHOLD, min_silence_duration_ms=100,
                                 speech_pad_ms=0)
        digital_silence = not bool(torch.count_nonzero(audio))
        speech_regions = [] if digital_silence else get_speech_timestamps(audio.numpy(), vad_options=vad_options)
        presence = {"status": "success", "method": "exact_zero_samples" if digital_silence else "silero_vad",
                    "timebase": "input_audio_seconds",
                    "threshold": SPEECH_THRESHOLD, "min_silence_duration_ms": 100, "speech_pad_ms": 0,
                    "regions": [{"start": s["start"] / 16000, "end": s["end"] / 16000}
                                for s in speech_regions]}
        assessments = {}
        def assess(start, end):
            nonlocal model, extractor
            if (start, end) in assessments:
                return dict(assessments[start, end])
            crop = audio[start:end]
            row = {"start": start / 16000, "end": end / 16000,
                   "speech_score": None, "speech_score_kind": "uncalibrated_audioset_sigmoid",
                   "vad_speech_coverage": max((max(0, min(end, s["end"]) - max(start, s["start"]))
                                              / (end - start) for s in speech_regions), default=0),
                   "excluded_labels": [], "event_scores": {}}
            if not crop.numel():
                raise ValueError("Empty acoustic analysis window")
            if not torch.count_nonzero(crop):
                row.update(analysis_status="not_applicable_digital_silence", speech_score=0.,
                           speech_score_kind="exact_zero_samples")
            elif crop.numel() < 400:  # Kaldi's 25 ms frame at 16 kHz.
                row["analysis_status"] = "unavailable_insufficient_samples"
            else:
                row["analysis_status"] = "assessed"
            if row["analysis_status"] != "assessed":
                assessments[start, end] = row
                return dict(row)
            if model is None:
                from transformers import ASTFeatureExtractor, ASTForAudioClassification
                extractor = ASTFeatureExtractor.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                                                               cache_dir=cache_dir, local_files_only=True)
                model = ASTForAudioClassification.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                    cache_dir=cache_dir, local_files_only=True).to(device).eval()
            inputs = extractor(crop.numpy(), sampling_rate=16000, return_tensors="pt")
            with torch.inference_mode():
                scores = model(**{k: v.to(device) for k, v in inputs.items()}).logits[0].sigmoid().cpu()
            if not torch.isfinite(scores).all():
                raise ValueError("Non-finite sound event scores")
            by_label = {model.config.id2label[i]: float(value) for i, value in enumerate(scores)}
            detected = {label: score for label, score in by_label.items()
                        if label in NON_SPEECH_LABELS and score >= EVENT_THRESHOLD}
            row.update(speech_score=by_label.get("Speech", 0),
                       excluded_labels=sorted({NON_SPEECH_LABELS[label] for label in detected}),
                       event_scores=detected)
            assessments[start, end] = row
            return dict(row)
        windows, events, skipped_windows = [], [], []
        for start in range(0, audio.numel(), int(HOP_SECONDS * 16000)):
            end = min(audio.numel(), start + int(WINDOW_SECONDS * 16000))
            if end-start < 400 and windows and windows[-1]["end"] >= end/16000:
                skipped_windows.append({"start": start/16000, "end": end/16000,
                                        "reason": "subframe_tail_already_covered"})
                continue
            row = assess(start, end)
            detected = row["event_scores"]
            windows.append(row)
            for label in row["excluded_labels"]:
                score = max(v for k, v in detected.items() if NON_SPEECH_LABELS[k] == label)
                previous = next((e for e in reversed(events) if e["label"] == label and e["end"] >= row["start"]), None)
                if previous:
                    previous["end"] = max(previous["end"], row["end"])
                    previous["score"] = max(previous["score"], score)
                else:
                    events.append({"label": label, "start": row["start"], "end": row["end"],
                                   "score": score, "status": "model_detected", "speaker": None,
                                   "boundary_precision": "analysis_window", "score_kind": "uncalibrated_sigmoid"})
        speech_windows = []
        duration = audio.numel() / 16000
        for candidate in list(speech_intervals or []) + list(emotion_phrases or []):
            row = assess(round(candidate["start"]*16000), round(candidate["end"]*16000))
            # Short crops can invent Music. Resolve only that specific dispute,
            # once, with real nearby context; vocal exclusions never get a retry.
            if row["excluded_labels"] == ["music"] and row["vad_speech_coverage"] >= MIN_VAD_COVERAGE:
                left = max(0., candidate["start"] - MUSIC_CONTEXT_SECONDS)
                right = min(duration, candidate["end"] + MUSIC_CONTEXT_SECONDS)
                for turn in speaker_tracks or []:
                    if not _interval(turn, duration) or turn.get("speaker") == candidate["speaker"]:
                        continue
                    if turn["end"] <= candidate["start"]:
                        left = max(left, turn["end"])
                    elif turn["start"] >= candidate["end"]:
                        right = min(right, turn["start"])
                    else:
                        left = right  # Competing speaker inside the target.
                        break
                supported = left < right and all(
                    _speaker_support((max(left, s["start"]), min(right, s["end"])),
                                     speaker_tracks or [], duration)
                    == (candidate["speaker"], (max(left, s["start"]), min(right, s["end"])))
                    for s in presence["regions"] if _overlap((left, right), (s["start"], s["end"])))
                if supported and (left < candidate["start"] or right > candidate["end"]):
                    row["context_check"] = {**assess(round(left*16000), round(right*16000)),
                        "status": "assessed", "speaker_support_checked": True,
                        "purpose": "corroborate_music_only_dispute", "padding_limit_seconds": MUSIC_CONTEXT_SECONDS}
                else:
                    row["context_check"] = {"status": "unavailable", "reason": "unresolved_context_speaker_support"}
            speech_windows.append(row)
        split = len(speech_intervals or [])
        unavailable = sum(str(w.get("analysis_status", "")).startswith("unavailable") for w in assessments.values())
        status = "unavailable" if unavailable == len(assessments) else "partial" if unavailable else "success"
        return events, {"speech_windows": speech_windows[:split], "phrase_windows": speech_windows[split:],
                        "speech_presence": presence,
                        "status": status, "model": MODEL_ID, "revision": MODEL_REVISION,
                        "model_executed": model is not None, "skipped_windows": skipped_windows,
                        "timebase": "input_audio_seconds", "window_seconds": WINDOW_SECONDS,
                        "hop_seconds": HOP_SECONDS, "event_threshold": EVENT_THRESHOLD, "windows": windows}
    finally:
        del model
        if device == "cuda":
            torch.cuda.empty_cache()


def prepare_inputs(waveform, sample_rate, result, *, cache_dir, device):
    duration = waveform.shape[-1] / sample_rate
    # Construct speaker-bound candidates first. Coarse event windows are retained
    # as observations, never used as exact speech masks.
    exclusions = speaker_purity_exclusions(result, duration)
    candidates, rejected = select_speech_intervals(result, [
        {"start": 0, "end": duration, "speech_score": 1., "excluded_labels": []}], duration,
        purity_exclusions=exclusions)
    phrases, phrase_rejected = emotion_phrase_candidates(result, duration, purity_exclusions=exclusions)
    events, meta = detect_sound_events(waveform, sample_rate, cache_dir=cache_dir,
                                     device=device, speech_intervals=candidates,
                                     speaker_tracks=result.get("diarization") or [], emotion_phrases=phrases)
    selected = []
    for candidate in candidates:
        window = next((w for w in meta.get("speech_windows", [])
                       if abs(w["start"]-candidate["start"]) < .001
                       and abs(w["end"]-candidate["end"]) < .001), None)
        accepted, speech_sources, music_not_corroborated = _acoustic_basis(window, meta)
        if accepted:
            admitted = {**candidate, "speech_presence_basis": speech_sources}
            if music_not_corroborated:
                admitted["acoustic_context"] = {**window["context_check"], "review_status": "unreviewed",
                    "target_disagreement": "music_only_not_corroborated"}
            selected.append(admitted)
        else:
            rejected.append({**candidate, "reason": "non_speech_or_uncertain_phrase"})
    return {"sound_events": events, "sound_event_meta": meta, "emotion_segments": [],
            "emotion_input": {"status": ("unavailable" if not _overlap_observations(result, duration)[0]
                                           else "ready" if selected else "insufficient_evidence"),
                              "policy": POLICY, "timebase": "input_audio_seconds",
                              "selected": selected, "rejected": rejected,
                              "speaker_purity": {"policy": "multi_speaker_phrase_veto_v1",
                                  "excluded_phrases": exclusions,
                                  "qualification": "conservative_exclusion_not_speech_purity_certification",
                                  "local_overlap": result.get("overlap_detection"),
                                  "additional_overlap": result.get("additional_overlap_detection")},
                              "phrase_selection": select_complete_emotion_phrases(
                                  phrases, phrase_rejected, meta, result, duration),
                              "selected_seconds": sum(s["end"] - s["start"] for s in selected),
                              "assessment_scope": "exact_candidate_phrase", "word_threshold": WORD_THRESHOLD, "speech_threshold": SPEECH_THRESHOLD,
                              "speech_presence_method": "silero_vad_or_audioset_speech", "minimum_vad_coverage": MIN_VAD_COVERAGE,
                              "vad_coverage_scope": "single_contiguous_speech_region",
                              "minimum_segment_seconds": MIN_SPEECH_SECONDS,
                              "maximum_segment_seconds": MAX_SPEECH_SECONDS}}
