"""Source-time coverage must not collapse repeated speech or invent completion."""
from types import SimpleNamespace as NS

import numpy as np
import pytest


def segment(text='hello', start=.1, end=.4, **kwargs):
    return NS(start=0., end=.5, text=text, avg_logprob=-.1,
              no_speech_prob=.01, compression_ratio=1.,
              words=[NS(word=text, start=start, end=end, probability=.95)], **kwargs)


def info():
    return NS(language='en', language_probability=1., transcription_options=NS(
        no_speech_threshold=.6, log_prob_threshold=-1., compression_ratio_threshold=2.4))


def run(monkeypatch, regions, model, *, audio=None, language='en', hints=None):
    from wsl2_audio import process_audio as worker
    monkeypatch.setattr(worker, '_source_speech_regions', lambda _: regions)
    # These tests isolate region receipts. The signal-preserving partition is
    # exercised without stubbing in test_source_audio_phrase_timing.py.
    monkeypatch.setattr('wsl2_audio.transcription_contract._recognition_source_regions', lambda _: regions)
    coverage = {}
    result = worker._transcribe_source_regions(model, np.zeros(180*16000, dtype=np.float32) if audio is None else audio,
        language=language, beam_size=5, temperature=0., context_options=hints or {}, coverage=coverage)
    return result, coverage


def test_seven_identical_utterances_retain_seven_original_positions(monkeypatch):
    offsets = [2, 28, 55, 82, 110, 140, 177]
    regions = [{'start': x*16000, 'end': (x+1)*16000} for x in offsets]
    audio = np.zeros(180*16000, dtype=np.float32)
    for r in regions: audio[r['start']:r['end']] = 1
    calls = []
    class Model:
        def transcribe(self, crop, **kwargs):
            assert len(crop) == 16000 and np.all(crop == 1)
            assert kwargs['vad_filter'] is False and kwargs['condition_on_previous_text'] is False
            assert kwargs['temperature'] == 0.
            calls.append(kwargs)
            return iter([segment()]), info()
    (segments, detected, timing, quality), coverage = run(monkeypatch, regions, Model(), audio=audio)
    assert len(calls) == len(segments) == 7
    assert [s['words'][0]['start'] for s in segments] == [x+.1 for x in offsets]
    assert [s['source_region_index'] for s in segments] == list(range(7))
    assert coverage['completed_region_count'] == coverage['detected_region_count'] == 7
    assert coverage['recognition_accuracy'] == 'unverified'
    assert detected.duration_after_vad == 7 and quality['accepted_segment_count'] == 7


def test_empty_region_is_observable_and_does_not_claim_absent_speech(monkeypatch):
    class Model:
        def transcribe(self, crop, **kwargs): return iter([]), info()
    (_, detected, _, _), coverage = run(monkeypatch, [{'start': 32000, 'end': 48000}], Model())
    assert detected.duration_after_vad == 1
    assert coverage['regions'][0]['outcome'] == 'no_text_returned'
    assert coverage['regions_without_text'] == 1
    assert coverage['status'] == 'completed'


def test_region_failure_cannot_be_reported_as_complete(monkeypatch):
    from wsl2_audio import process_audio as worker
    monkeypatch.setattr(worker, '_source_speech_regions', lambda _: [
        {'start': i*16000, 'end': (i+1)*16000} for i in range(3)])
    monkeypatch.setattr('wsl2_audio.transcription_contract._recognition_source_regions',
                        worker._source_speech_regions)
    class Model:
        calls = 0
        def transcribe(self, crop, **kwargs):
            self.calls += 1
            if self.calls == 2: raise RuntimeError('decoder failed')
            return iter([segment()]), info()
    coverage = {}
    with pytest.raises(RuntimeError, match='decoder failed'):
        worker._transcribe_source_regions(Model(), np.zeros(48000, dtype=np.float32),
            language='en', beam_size=5, temperature=0., context_options={}, coverage=coverage)
    assert coverage['status'] == 'error'
    assert [r['outcome'] for r in coverage['regions']] == ['text_returned', 'error', 'not_attempted']
    assert coverage['completed_region_count'] == 1


def test_silence_does_not_run_asr_or_language_detection(monkeypatch):
    (segments, detected, _, _), coverage = run(monkeypatch, [], object(), language=None)
    assert segments == [] and detected.duration_after_vad == 0
    assert detected.language_probability is None
    assert coverage['status'] == 'not_applicable_no_detected_speech'


def test_unrelated_clear_region_cannot_resurrect_rejected_noise_text(monkeypatch):
    class Model:
        calls = 0
        def transcribe(self, crop, **kwargs):
            self.calls += 1
            s = segment('noise' if self.calls == 2 else 'hello')
            if self.calls == 2:
                s.no_speech_prob = .99; s.avg_logprob = -2; s.words[0].probability = .01
            return iter([s]), info()
    (segments, _, _, quality), coverage = run(monkeypatch,
        [{'start': 0, 'end': 16000}, {'start': 48000, 'end': 64000}], Model())
    assert [s['text'] for s in segments] == ['hello']
    assert quality['rejected_segments'][0]['text'] == 'noise'
    assert quality['rejected_segments'][0]['source_region_index'] == 1
    assert coverage['regions'][1]['outcome'] == 'rejected_no_speech_candidate'


def test_word_outside_its_region_cannot_borrow_time_from_later_audio(monkeypatch):
    class Model:
        def transcribe(self, crop, **kwargs): return iter([segment(end=1.5)]), info()
    (segments, _, _, _), coverage = run(monkeypatch, [{'start': 32000, 'end': 48000}], Model())
    word = segments[0]['words'][0]
    assert word['start'] is None and word['end'] is None
    assert word['raw_start'] == 2.1 and word['raw_end'] == 3.5
    assert 'invalid_word_timing' in coverage['regions'][0]['quality_flags']


@pytest.mark.parametrize('regions', [[{'start': -1, 'end': 10}], [{'start': 10, 'end': 10}],
    [{'start': 0, 'end': 16001}], [{'start': 100, 'end': 300}, {'start': 200, 'end': 400}]])
def test_invalid_source_regions_fail_before_inference(monkeypatch, regions):
    with pytest.raises(ValueError, match='source region'):
        run(monkeypatch, regions, object(), audio=np.zeros(16000, dtype=np.float32))


def test_automatic_language_is_detected_once_and_not_replaced_by_forced_one(monkeypatch):
    class Model:
        detections = 0
        def detect_language(self, *, audio):
            self.detections += 1
            assert len(audio) == 32000
            return 'en', .44, [('en', .44)]
        def transcribe(self, crop, **kwargs):
            assert kwargs['language'] == 'en'
            return iter([segment()]), info()
    model = Model()
    (_, detected, _, _), coverage = run(monkeypatch,
        [{'start': 0, 'end': 16000}, {'start': 48000, 'end': 64000}], model, language=None)
    assert model.detections == 1 and detected.language_probability == .44
    assert coverage['language_detection_scope'] == 'first_30_seconds_of_detected_speech'


def test_decoder_quality_failure_is_visible_without_erasing_words(monkeypatch):
    class Model:
        def transcribe(self, crop, **kwargs):
            s = segment(); s.compression_ratio = 3.; s.avg_logprob = -1.5
            return iter([s]), info()
    (segments, _, _, _), coverage = run(monkeypatch, [{'start': 0, 'end': 16000}], Model())
    assert segments[0]['text'] == 'hello'
    assert set(coverage['regions'][0]['quality_flags']) >= {'compression_ratio_threshold_exceeded', 'log_probability_below_threshold'}


def test_invalid_word_timing_does_not_trigger_another_recognition_pass(monkeypatch):
    class Model:
        calls = []
        def transcribe(self, crop, **kwargs):
            self.calls.append(kwargs)
            return iter([segment(start=.3 if kwargs.get('hotwords') else .1, end=.3)]), info()
    model = Model()
    (segments, _, timing, _), coverage = run(monkeypatch, [{'start': 32000, 'end': 48000}], model,
        hints={'hotwords': 'hello'})
    assert len(model.calls) == 1 and model.calls[0]['hotwords'] == 'hello'
    assert all(c['vad_filter'] is False for c in model.calls)
    assert segments[0]['words'][0]['start'] is None
    assert segments[0]['words'][0]['timing_status'] == 'invalid_model_alignment'
    assert timing['word_alignment']['second_asr_pass'] is False


def test_unplaceable_segment_is_retained_as_uncertain_evidence(monkeypatch):
    class Model:
        def transcribe(self, crop, **kwargs):
            s = segment('yay'); s.start = s.end = .2
            return iter([s]), info()
    (segments, _, _, _), coverage = run(monkeypatch, [{'start': 32000, 'end': 48000}], Model())
    assert segments == []
    row = coverage['regions'][0]
    assert row['outcome'] == 'text_with_unavailable_timing'
    assert row['unplaced_segments'] == [{'text': 'yay', 'raw_start': 2.2, 'raw_end': 2.2}]


def test_lazy_audio_proxy_exposes_resampling_functional_api(monkeypatch):
    from wsl2_audio import process_audio as worker
    api = object()
    proxy = worker._LazyTorchaudio()
    monkeypatch.setattr(proxy, '_module', lambda: NS(functional=api))
    assert proxy.functional is api


@pytest.mark.parametrize('second', ['empty', 'unplaced', 'rejected'])
def test_whole_input_absence_requires_every_source_region_to_be_resolved(monkeypatch, second):
    from steps.audio.audio_wsl2_bridge import _build_wsl_capability_outcomes
    class Model:
        calls = 0
        def transcribe(self, crop, **kwargs):
            self.calls += 1
            s = segment('candidate'); s.no_speech_prob = .99; s.avg_logprob = -2.
            s.words[0].probability = .01
            if self.calls == 2:
                if second == 'empty': return iter([]), info()
                if second == 'unplaced': s.start = s.end = .2
            return iter([s]), info()
    (segments, _, _, quality), coverage = run(monkeypatch, [
        {'start': 0, 'end': 16000}, {'start': 32000, 'end': 48000}], Model())
    assert not segments
    assert quality.get('whole_input_no_speech_supported') is (second == 'rejected')
    outcomes = _build_wsl_capability_outcomes({'transcription_status': 'success',
        'transcription': '', 'transcription_quality': quality})
    assert (outcomes['transcription']['reason'] == 'no_speech_detected') is (second == 'rejected')


def test_mixed_valid_and_unplaceable_text_has_a_visible_warning(monkeypatch):
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    class Model:
        def transcribe(self, crop, **kwargs):
            invalid = segment('yay'); invalid.start = invalid.end = .2
            return iter([segment('hello'), invalid]), info()
    (_, _, _, _), coverage = run(monkeypatch, [{'start': 0, 'end': 16000}], Model())
    row = coverage['regions'][0]
    assert row['outcome'] == 'text_returned'
    assert row.get('unplaced_segment_count') == 1
    assert 'invalid_segment_timing' in row['quality_flags']
    _, prompt = _build_scene_context_prompts({'transcript': 'hello', 'transcription_coverage': coverage})
    assert '"warning_region_count": 1' in prompt
    assert '"unplaced_segment_count": 1' in prompt


def test_failed_real_bridge_projection_retains_region_coverage(monkeypatch):
    from steps.audio import audio_wsl2_bridge as bridge
    evidence = {'source_regions': {'policy': 'source_regions_v1', 'status': 'error',
        'detected_region_count': 3, 'completed_region_count': 1, 'regions': [{'index': 1, 'outcome': 'error'}]}}
    class Runner:
        def process_audio(self, *args, **kwargs):
            return {'status': 'error', 'error': 'decoder failed', 'transcription_decoding': evidence,
                'transcription_status': 'error', 'transcription': 'hello',
                'segments': [{'start': .1, 'end': .4, 'text': 'hello'}],
                'word_alignment': {'timebase': 'input_audio_seconds', 'words': [
                    {'start': .1, 'end': .4, 'text': 'hello', 'timing_status': 'aligned'}]}}
    monkeypatch.setattr(bridge, 'WSL2AudioBridge', Runner)
    result = bridge.audio_unified_wsl2('fixture.wav')
    assert result['status'] == 'error'
    assert result['transcript_meta']['transcription_decoding'] == evidence
    assert result['transcript'] == 'hello'
    assert result['word_timestamps'][0]['start'] == .1
    assert result['transcript_meta']['status'] == 'partial'
    assert result['transcript_outcome'] == 'partial'
