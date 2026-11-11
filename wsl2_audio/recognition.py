"""Pinned local Faster-Whisper adapter for fixed recording windows.

Recognition never consumes VAD crops. Fixed decoded text is aligned afterward;
native envelopes, word timing, speech evidence and completeness stay separate.
"""

from fractions import Fraction
from copy import deepcopy
import hashlib
from importlib.metadata import version
import math
from pathlib import Path
import platform
import re

from wsl2_audio.recording_audio import _json_bytes, _sha_file
from wsl2_audio.source_clock import SampleSpan


DECODE_OPTIONS = {
    'beam_size': 5, 'best_of': 5, 'patience': 1.0, 'length_penalty': 1.0,
    'repetition_penalty': 1.0, 'no_repeat_ngram_size': 0, 'temperature': 0.0,
    'compression_ratio_threshold': 2.4, 'log_prob_threshold': -1.0, 'no_speech_threshold': .6,
    'condition_on_previous_text': False, 'prompt_reset_on_temperature': .5,
    'initial_prompt': None, 'prefix': None, 'suppress_blank': True, 'suppress_tokens': [-1],
    'without_timestamps': False, 'max_initial_timestamp': 1.0, 'word_timestamps': False,
    'vad_filter': False, 'multilingual': False, 'clip_timestamps': '0',
    'hallucination_silence_threshold': None, 'language_detection_threshold': .5,
    # None uses the pinned decoder's total context limit, including its prompt.
    'language_detection_segments': 1, 'max_new_tokens': None, 'hotwords': None,
}


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _source_span(start, end, source_rate, context):
    if _number(start) is None or _number(end) is None or not 0 <= start < end:
        return None
    left, right = Fraction(str(start))*source_rate, Fraction(str(end))*source_rate
    if right > context.end-context.start:
        return None
    return {'start': context.start + math.floor(left), 'end': context.start + math.ceil(right)}


def _model_audio(samples, source_rate, context):
    import numpy as np
    from scipy.signal import resample_poly

    if len(samples) != context.end-context.start or source_rate <= 0:
        raise ValueError('Recognition input does not match its source window')
    source = np.asarray(samples, dtype=np.float64)
    if not np.all(np.isfinite(source)):
        raise ValueError('Nonfinite source audio')
    divisor = math.gcd(source_rate, 16000)
    converted = (source if source_rate == 16000 else
                 resample_poly(source, 16000//divisor, source_rate//divisor,
                               window=('kaiser', 5.0), padtype='constant', cval=0))
    with np.errstate(over='ignore', under='ignore'):
        audio = converted.astype(np.float32)
    if not np.all(np.isfinite(audio)) or np.any((converted != 0) & (audio == 0)):
        raise ValueError('Model precision cannot preserve this source signal')
    return source, audio, {'source_rate': source_rate, 'target_rate': 16000, 'up': 16000//divisor,
                           'down': source_rate//divisor, 'output_samples': len(audio),
                           'method': 'identity' if source_rate == 16000 else 'scipy_resample_poly_kaiser5',
                           'dtype': 'float32', 'channel_mix': False}


def _speech_activity(audio, source_rate, context):
    from wsl2_audio import transcription_contract as contract

    try:
        vad = contract._source_speech_regions(audio)
        previous, spans = 0, []
        for region in vad:
            start, end = int(region['start']), int(region['end'])
            if not 0 <= previous <= start < end <= len(audio):
                raise ValueError('Invalid source speech activity interval')
            previous = end
            # Only resampling geometry is bounded here: the final target sample
            # may cover a fractional source-sample interval. Never round through
            # floating seconds and turn that legitimate interval into None.
            left = context.start + start*source_rate//16000
            right = min(context.end, context.start + (end*source_rate+15999)//16000)
            if left < right:
                spans.append({'start': left, 'end': right})
        return {'status': 'ok', 'assessed_spans': [vars(context)], 'spans': spans}
    except Exception as exc:
        return {'status': 'error', 'reason': 'speech_activity_failed',
                'error': contract.model_cache.redact_sensitive_info(str(exc)), 'assessed_spans': [], 'spans': []}


def _apply_speech_activity(observation, activity):
    observation['speech_activity'] = activity
    for utterance in observation['utterances']:
        start, end = utterance['span']['start'], utterance['span']['end']
        utterance['quality']['speech_coverage'] = (
            min(1., sum(max(0, min(end, span['end'])-max(start, span['start']))
                        for span in activity['spans'])/(end-start)) if activity['status'] == 'ok' else None)
    return observation


def refresh_speech_activity(observation, samples, source_rate, context):
    """Recover a failed detector on the identical window without running ASR."""
    _, audio, _ = _model_audio(samples, source_rate, context)
    updated = deepcopy(observation)
    updated.setdefault('speech_activity_recovery', []).append(deepcopy(observation['speech_activity']))
    return _apply_speech_activity(updated, _speech_activity(audio, source_rate, context))


def transcription_context(profile):
    """Explicit spelling context, never derived from a reference or speaker identity."""
    from wsl2_audio.transcription_contract import _normalize_transcription_vocabulary
    terms = _normalize_transcription_vocabulary(profile.get('vocabulary'))
    return ({'vocabulary': terms, 'basis': 'explicit_profile_vocabulary', 'identity_claim': False}
            if terms else None)


def complete_word_span(text, words):
    """Locate the entire fixed text, never just the surviving aligned fragment."""
    compact = lambda value: re.sub(r'\s+', '', value)
    if (not words or any(w.get('timing') != 'supported' or not w.get('span') for w in words)
            or compact(''.join(w['text'] for w in words)) != compact(text)):
        return None
    if any(a['span']['end'] > b['span']['start'] for a, b in zip(words, words[1:])):
        return None
    return {'start': words[0]['span']['start'], 'end': words[-1]['span']['end']}


def recognize_window(model, samples, source_rate, context: SampleSpan, *, language, vocabulary=None):
    import numpy as np
    from wsl2_audio import transcription_contract as contract

    terms = contract._normalize_transcription_vocabulary(vocabulary)
    options = dict(DECODE_OPTIONS, hotwords=', '.join(terms) if terms else None)
    source, audio, transform = _model_audio(samples, source_rate, context)
    result = {'status': 'ok', 'utterances': [], 'raw_segments': [], 'unplaced_hypotheses': [],
              'assessed_spans': [{'start': context.start, 'end': context.end}],
              'transform': transform,
              'decoding': dict(options, language=language)}
    collected, info = [], None
    try:
        generated, info = model.transcribe(audio, language=language, **options)
        for raw in generated:
            collected.append(raw)
    except Exception as exc:
        result.update(status='partial' if collected else 'error',
                      reason='recognition_failed', error=contract.model_cache.redact_sensitive_info(str(exc)))
    detected_language = getattr(info, 'language', None)
    try:
        aligned, alignment = contract._align_after_decoding(model, audio, collected, detected_language)
    except Exception as exc:
        aligned, alignment = collected, {'status': 'unavailable', 'reason': 'alignment_failed',
                                        'error': contract.model_cache.redact_sensitive_info(str(exc))}
    result['alignment'] = alignment
    for index, raw in enumerate(aligned):
        original = collected[index]
        start, end = getattr(original, 'start', None), getattr(original, 'end', None)
        text = str(getattr(original, 'text', '')).strip()
        raw_record = {'text': text, 'start': _number(start), 'end': _number(end),
                      'avg_logprob': _number(getattr(original, 'avg_logprob', None)),
                      'no_speech_probability': _number(getattr(original, 'no_speech_prob', None)),
                      'temperature': _number(getattr(original, 'temperature', None)),
                      'native_phrase_timing': getattr(raw, 'phrase_timing', None), 'words': []}
        result['raw_segments'].append(raw_record)
        span = _source_span(start, end, source_rate, context)
        if not text:
            continue
        quality = {key: raw_record[key] for key in ('avg_logprob', 'no_speech_probability')}
        quality['speech_coverage'] = None
        native_span = dict(span) if span else None
        words, previous_end, previous_raw_end = [], context.start, None
        for word in getattr(raw, 'words', None) or []:
            word_text = str(getattr(word, 'word', '')).strip()
            if not word_text:
                continue
            raw_start, raw_end = getattr(word, 'start', None), getattr(word, 'end', None)
            raw_record['words'].append({'text': word_text, 'start': _number(raw_start), 'end': _number(raw_end),
                                        'probability': _number(getattr(word, 'probability', None))})
            interval = _source_span(raw_start, raw_end, source_rate, context)
            reason = 'invalid_word_alignment'
            if interval and interval['start'] < previous_end:
                # Outward floor/ceil conversion can share a boundary sample even
                # when raw timestamps are ordered. That sample already belongs
                # to the previous word. Never repair a genuine raw-time overlap.
                if previous_raw_end is not None and raw_start >= previous_raw_end and previous_end < interval['end']:
                    interval['start'] = previous_end
                else:
                    interval, reason = None, 'word_alignment_order_conflict'
            if interval and not np.any(source[interval['start']-context.start:interval['end']-context.start] != 0):
                interval, reason = None, 'word_on_digital_silence'
            words.append({'text': word_text, 'span': interval, 'timing': 'supported' if interval else 'unavailable',
                          **({} if interval else {'reason': reason})})
            if interval:
                previous_end = interval['end']
                previous_raw_end = raw_end
                if span:
                    span = {'start': min(span['start'], interval['start']),
                            'end': max(span['end'], interval['end'])}
        alignment_source = None
        if native_span is None:
            span = complete_word_span(text, words)
            if span is None or not context.start < span['start'] < span['end'] < context.end:
                result['unplaced_hypotheses'].append({'text': text, 'reason': 'native_envelope_outside_input', 'raw_index': index})
                continue
            alignment_source = {'method': 'complete_aligned_text_v1',
                                'reason': 'native_envelope_outside_input'}
        result['utterances'].append({
            'text': text, 'span': span, 'words': words, 'quality': quality,
            **({'native_span': native_span} if native_span and native_span != span else {}),
            **({'alignment_source': alignment_source} if alignment_source else {}),
            'language': {'value': detected_language if language is None else None,
                         'status': 'observed' if language is None and detected_language else 'unresolved',
                         'configured': language, 'detection_probability': _number(getattr(info, 'language_probability', None)) if language is None else None},
            'completeness': 'unresolved',
            'boundary_evidence': {'status': 'unresolved',
                                  'method': 'complete_aligned_text_v1' if alignment_source else
                                            'native_and_aligned_word_enclosure' if native_span != span else 'native_decoder_envelope',
                                  'reason': 'acoustic_completeness_not_established'},
            'speaker': {'status': 'unresolved', 'id': None}, 'raw_index': index,
        })
    if result['status'] != 'ok':
        result['assessed_spans'] = [row['span'] for row in result['utterances']]
    return _apply_speech_activity(result, _speech_activity(audio, source_rate, context))


def verify_recognizer(profile):
    """Check pinned runtime and actual asset bytes even on a result-cache hit."""
    transcription_context(profile)
    import faster_whisper.vad
    expected = profile['runtime_packages']
    required = {'faster-whisper': '1.2.1', 'ctranslate2': '4.8.4', 'numpy': '2.2.6', 'scipy': '1.15.3'}
    if expected != required or any(version(name) != value for name, value in expected.items()):
        raise ValueError('Recognizer runtime differs from the pinned candidate')
    spec, vad_spec = profile['recognizer'], profile['speech_activity_model']
    model_dir = Path(spec['path']).resolve(strict=True)
    if (not {'model.bin', 'config.json', 'tokenizer.json'} <= set(spec['files'])
            or not {'vocabulary.txt', 'vocabulary.json'}.intersection(spec['files'])):
        raise ValueError('Incomplete local recognizer asset manifest')
    actual = {}
    for relative, digest in sorted(spec['files'].items()):
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid model asset name')
        actual[relative] = _sha_file(model_dir/path)
        if actual[relative] != digest:
            raise ValueError('Recognizer asset hash mismatch')
    if hashlib.sha256(_json_bytes(actual)).hexdigest() != spec['sha256']:
        raise ValueError('Recognizer asset manifest hash mismatch')
    vad_path = Path(vad_spec['path']).resolve(strict=True)
    expected_vad = (Path(faster_whisper.vad.__file__).parent/'assets'/'silero_vad_v6.onnx').resolve()
    if vad_path != expected_vad or _sha_file(vad_path) != vad_spec['sha256']:
        raise ValueError('Speech activity asset differs from the pinned package asset')
    device, compute_type = profile.get('device'), profile.get('compute_type')
    valid_device = ((device == 'cpu' and compute_type == 'int8')
                    or (device == 'cuda' and compute_type in ('float16', 'int8_float16', 'float32', 'int8')))
    if not valid_device:
        raise ValueError('Unsupported recognizer device/compute_type; no automatic device fallback')
    if device == 'cuda':
        import ctranslate2
        if ctranslate2.get_cuda_device_count() < 1:
            raise ValueError('CUDA recognizer profile requested but CUDA runtime is unavailable; no automatic device fallback')
    models = [{key: item[key] for key in ('id', 'revision', 'sha256')} for item in (spec, vad_spec)]
    runtime = {'python': platform.python_version(), 'packages': expected, 'device': device,
               'compute_type': compute_type, 'cpu_threads': 4, 'model_loading': 'local_files_only'}
    return {'models': models, 'runtime': runtime, 'model_path': str(model_dir)}


class FasterWhisperRecognizer:
    def __init__(self, profile, verified=None):
        from faster_whisper import WhisperModel

        context = transcription_context(profile)
        self.vocabulary = context['vocabulary'] if context else None
        verified = verified or verify_recognizer(profile)
        self.models, self.runtime = verified['models'], verified['runtime']
        model_dir = verified['model_path']
        device = self.runtime.get('device', 'cpu')
        compute_type = self.runtime.get('compute_type', 'int8')
        self.model = WhisperModel(str(model_dir), device=device, compute_type=compute_type, cpu_threads=4,
                                  num_workers=1, local_files_only=True)

    def observe(self, samples, sample_rate, context, language):
        return recognize_window(self.model, samples, sample_rate, context, language=language,
                                vocabulary=self.vocabulary)

    def close(self):
        self.model = None
        if self.runtime.get('device') == 'cuda':
            import gc
            gc.collect()


def load_recognizer(profile, verified=None):
    return FasterWhisperRecognizer(profile, verified)
