"""Signal-level absence and frame limits must precede sound-model inference."""
import sys
from types import SimpleNamespace

import pytest
import torch

from wsl2_audio import acoustic_events as audio


@pytest.fixture
def classifier(monkeypatch):
    calls = {'loads': 0, 'samples': []}

    class Extractor:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            calls['loads'] += 1
            return cls()

        def __call__(self, samples, **kwargs):
            calls['samples'].append(len(samples))
            if len(samples) < 400:
                raise AssertionError('Kaldi requires a complete 25 ms frame')
            return {'input_values': torch.tensor([1.])}

    class Model:
        config = SimpleNamespace(id2label={0: 'Music', 1: 'Speech'})

        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            calls['loads'] += 1
            return cls()

        def to(self, *args): return self
        def eval(self): return self
        def __call__(self, **kwargs):
            return SimpleNamespace(logits=torch.tensor([[0., -5.]]))

    monkeypatch.setitem(sys.modules, 'transformers', SimpleNamespace(
        ASTFeatureExtractor=Extractor, ASTForAudioClassification=Model))
    monkeypatch.setitem(sys.modules, 'torchaudio', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'faster_whisper.vad', SimpleNamespace(
        VadOptions=lambda **kwargs: kwargs, get_speech_timestamps=lambda *a, **k: []))
    return calls


def detect(waveform):
    return audio.detect_sound_events(waveform, 16000, cache_dir=None, device='cpu')


def test_digital_silence_has_observed_absence_without_loading_a_classifier(classifier):
    events, meta = detect(torch.zeros(1, 80000))
    assert not events
    assert classifier == {'loads': 0, 'samples': []}
    assert meta['status'] == 'success'
    assert meta['windows'][0]['analysis_status'] == 'not_applicable_digital_silence'
    assert meta['windows'][0]['speech_score'] == 0.


def test_silent_windows_do_not_extend_an_event_through_a_zero_tail(classifier):
    waveform = torch.zeros(1, 240000)
    waveform[:, :16000] = 1e-10  # Quiet nonzero samples are not digital silence.
    events, meta = detect(waveform)
    assert classifier['samples'] == [160000]
    assert events[0]['label'] == 'music' and events[0]['end'] == 10.
    assert all(w['analysis_status'] == 'not_applicable_digital_silence' for w in meta['windows'][1:])


@pytest.mark.parametrize('tail', [1, 399])
def test_subframe_trailing_window_cannot_discard_preceding_evidence(classifier, tail):
    waveform = torch.ones(1, 80000 + tail) * 1e-10
    events, meta = detect(waveform)
    assert classifier['samples'] == [80000 + tail]
    assert events and meta['status'] == 'success'
    assert meta['skipped_windows'] == [{'start': 5., 'end': len(waveform[0])/16000,
        'reason': 'subframe_tail_already_covered'}]


@pytest.mark.parametrize('samples', [1, 399])
def test_uncovered_short_nonzero_input_is_unavailable_not_silence(classifier, samples):
    events, meta = detect(torch.ones(1, samples) * 1e-10)
    assert not events and meta['status'] == 'unavailable'
    assert classifier == {'loads': 0, 'samples': []}
    assert meta['windows'][0]['analysis_status'] == 'unavailable_insufficient_samples'
    assert meta['windows'][0]['speech_score'] is None


def test_quiet_full_frame_still_reaches_the_classifier(classifier):
    events, meta = detect(torch.ones(1, 400) * 1e-10)
    assert events and meta['status'] == 'success'
    assert classifier['samples'] == [400]


def test_opposite_channels_cannot_be_reported_as_original_silence(classifier):
    waveform = torch.stack((torch.ones(80000), -torch.ones(80000)))
    with pytest.raises(ValueError, match='downmix'):
        detect(waveform)
    assert not classifier['samples']
