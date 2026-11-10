from types import SimpleNamespace

import numpy as np
import pytest

from wsl2_audio.enrichment_models import RecordingObservers
from wsl2_audio.source_clock import SampleSpan


@pytest.mark.parametrize('rate,count', [(48000, 48001), (44100, 44101), (44100, 101), (16000, 16000)])
def test_frame_endpoint_mapping_keeps_the_exact_final_source_sample(rate, count):
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = rate, count, count/rate
    assert observer._span(0., count/rate) == {'start': 0, 'end': count}


def test_frame_slack_does_not_admit_arbitrary_out_of_source_timestamps():
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = 16000, 16000, 1.
    with pytest.raises(ValueError, match='outside'):
        observer._span(0., 1.1, frame_slack=.02)


@pytest.mark.parametrize('rate,count', [(48000, 48001), (44100, 44101)])
def test_terminal_vad_observation_maps_back_to_exact_source_end(monkeypatch, rate, count):
    from faster_whisper import vad
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = rate, count, count/rate
    observer.full = SampleSpan(0, count)
    audio = np.ones((count*16000+rate-1)//rate, dtype=np.float32)
    observer._audio = lambda channel: audio
    monkeypatch.setattr(vad, 'get_speech_timestamps', lambda *args, **kwargs: [{'start': 0, 'end': len(audio)}])
    result = observer._phrase_activity(0, None, None, {})
    assert result['status'] == 'ok'
    assert result['regions'] == [{'span': {'start': 0, 'end': count}, 'channel': 0}]


def test_padded_diarizer_intervals_retain_raw_bounds_and_only_project_existing_source(monkeypatch):
    from wsl2_audio import process_audio
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = 16000, 38400, 2.4
    observer.full = SampleSpan(0, 38400)
    observer._audio = lambda channel: np.ones(38400, dtype=np.float32)
    class Annotation:
        def itertracks(self, **kwargs):
            return iter([(SimpleNamespace(start=.35, end=2.42721875), None, 's0'),
                         (SimpleNamespace(start=2.6, end=3.), None, 's1')])
    def diarize(pipeline, audio, *, overlap_evidence, observe_empty):
        assert observe_empty is True
        overlap_evidence.update(status='ok', intervals=[])
        return Annotation(), {'status': 'ok', 'flags': []}
    monkeypatch.setattr(process_audio, '_diarize_with_review', diarize)
    result = observer._speaker_activity(0, None, None, {})
    assert result['tracks'] == [{'span': {'start': 5600, 'end': 38400}, 'channel': 0,
        'speaker': 's0', 'raw_seconds': [.35, 2.42721875], 'precision': 'model_frame', 'source_censored': True}]
    assert len(result['raw_tracks']) == 2


def test_short_nonzero_audio_is_unavailable_not_music_or_speech():
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = 16000, 300, 300/16000
    observer.full = SampleSpan(0, 300)
    observer.evidence = {'source': {'sha256': 'a'*64}, 'utterances': []}
    observer.signal = [np.ones(300, dtype=np.float64)]
    def not_called(*args, **kwargs):
        pytest.fail('acoustic model called without one usable analysis frame')
    result = observer._acoustic_events(0, not_called, ['Speech']+[f'other{i}' for i in range(446)], {})
    assert not result['events'] and not result['assessed_spans']
    assert result['windows'][0]['reason'] == 'insufficient_samples_for_acoustic_frame'


def test_subthreshold_event_scores_are_retained_without_promoting_them_to_events():
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = 16000, 32000, 2.
    observer.full = SampleSpan(0, 32000)
    observer.evidence = {'source': {'sha256': 'a'*64}, 'utterances': []}
    observer.signal = [np.ones(32000, dtype=np.float64)]
    class Model:
        def run(self, *args):
            scores = np.zeros((1,250,447), dtype=np.float32)
            scores[0,:,:4] = [.002, .001, .85, .7]
            return [scores]
    names = ['Singing', 'Laughter', 'Music', 'Speech']+[f'other{i}' for i in range(443)]
    result = observer._acoustic_events(0, Model(), names, {})
    window = result['windows'][0]
    assert 0 < window['frame_scores'][0][result['frame_labels'].index('Singing')] < .1
    assert 0 < window['frame_scores'][0][result['frame_labels'].index('Laughter')] < .1
    assert result['threshold'] == .5
    assert {event['label'] for event in result['events']} == {'music'}


def test_resampling_preringing_cannot_establish_an_event_over_silent_source_samples():
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = 48000, 4800, .1
    observer.full = SampleSpan(0, 4800)
    observer.evidence = {'source': {'sha256': 'a'*64}}
    source = np.zeros(4800, dtype=np.float64)
    source[1921] = .5
    observer.signal = [source]
    assert not source[:1920].any()
    assert observer._audio(0)[:640].any()  # The resampling filter rings into the preceding frame.

    class Model:
        def run(self, *args):
            scores = np.zeros((1, 250, 447), dtype=np.float32)
            scores[0, :2, :2] = .9
            return [scores]

    result = observer._acoustic_events(0, Model(), ['Laughter', 'Speech']+[f'other{i}' for i in range(445)], {})
    assert result['status'] == 'ok'
    assert result['windows'][0]['frame_scores'][0][0] > .5  # Raw model evidence is retained.
    assert [r['span'] for r in result['events']] == [{'start': 1920, 'end': 3840}]
    assert result['speech_intervals'] == [{'span': {'start': 1920, 'end': 3840}, 'channel': 0}]


@pytest.mark.parametrize('failed_call', [2, 4])
def test_later_acoustic_window_failure_preserves_earlier_events(failed_call):
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = 16000, 480000, 30.
    observer.full = SampleSpan(0, 480000)
    observer.evidence = {'source': {'sha256': 'a'*64},
                        'utterances': [{'id': 'u', 'channel': 0, 'span': {'start': 2000, 'end': 32000}}]}
    observer.signal = [np.ones(480000, dtype=np.float64)]
    class Model:
        calls = 0
        def run(self, *args):
            self.calls += 1
            if self.calls == failed_call:
                raise RuntimeError('injected later acoustic failure')
            scores = np.zeros((1,250,447), dtype=np.float32)
            scores[0,:,0] = .9
            return [scores]
    result = observer._acoustic_events(0, Model(), ['Crying, sobbing', 'Speech']+[f'other{i}' for i in range(445)], {})
    assert result['status'] == 'partial'
    assert result['events'][0]['label'] == 'crying'
    assert result['assessed_spans'][0]['start'] == 0
    assert result['failures']


def test_vocal_failure_preserves_another_successful_complete_input(monkeypatch):
    import torch
    from transformers import Wav2Vec2FeatureExtractor
    from wsl2_audio import process_audio

    class Model:
        config = SimpleNamespace(id2label={0: 'neutral', 1: 'happy'})
        calls = 0
        def __call__(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError('injected second phrase failure')
            return SimpleNamespace(logits=torch.tensor([[.1, .9]]))
    monkeypatch.setattr(process_audio, '_load_trained_wav2vec', lambda *a, **kw: (Model(), {'strict': True}))
    monkeypatch.setattr(Wav2Vec2FeatureExtractor, 'from_pretrained',
                        lambda *a, **kw: lambda *args, **kwargs: {'input_values': torch.ones((1, 16000))})
    observer = object.__new__(RecordingObservers)
    observer.spec = lambda name: {'path': 'test-only', 'id': 'test-emotion'}
    observer._audio = lambda *args: np.ones(16000, dtype=np.float32)
    rows = [{'id': name, 'channel': 0, 'span': {'start': 0, 'end': 16000}} for name in ('first', 'second')]
    result = observer.vocal_delivery(rows)
    assert [r['utterance_id'] for r in result['results']] == ['first']
    assert [r['utterance_id'] for r in result['errors']] == ['second']
    assert result['results'][0]['status'] == 'uncertain'
