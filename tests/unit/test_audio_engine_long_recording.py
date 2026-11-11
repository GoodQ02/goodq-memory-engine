import numpy as np
import pytest

from wsl2_audio.enrichment_models import RecordingObservers


def recording(tmp_path, samples, rate=16000):
    samples = np.asarray(samples, dtype='<f8')
    if samples.ndim == 1:
        samples = samples[:, None]
    path = tmp_path / 'source.f64le'
    path.write_bytes(samples.tobytes())
    return {'source': {'sample_rate': rate, 'sample_count': len(samples),
        'channels': samples.shape[1], 'origin_num': 0, 'origin_den': 1,
        'pcm_sha256': 'a'*64}, 'pcm': {'path': str(path)}}


def test_explicit_long_profile_reaches_observer_with_bounded_reads(tmp_path, monkeypatch):
    from wsl2_audio import enrichment_models
    count, rate = 30100, 100
    r = recording(tmp_path, np.ones(count)*.1, rate)
    calls = []
    original = enrichment_models.read_channel
    def bounded(r, span, channel):
        calls.append(span.end-span.start)
        assert span.end-span.start <= 32*rate
        return original(r, span, channel)
    monkeypatch.setattr(enrichment_models, 'read_channel', bounded)
    profile = {'enrichment': {'device': 'cpu', 'recording_policy': {
        'id': 'bounded_recording_v1', 'max_duration_seconds': 3600}}}
    observer = RecordingObservers(profile, {'source': r['source']}, r)
    assert observer.duration == 301 and observer.long_recording
    assert observer._audio(0).shape == (301*16000,)
    assert max(calls) <= 32*rate


def test_short_default_profile_remains_bounded(tmp_path):
    r = recording(tmp_path, np.ones(30100), 100)
    with pytest.raises(ValueError, match='300 seconds'):
        RecordingObservers({'enrichment': {'device': 'cpu'}}, {'source': r['source']}, r)


@pytest.mark.parametrize('rate', [16000, 44100, 48000])
def test_file_backed_resampling_matches_whole_signal_at_joins_and_tail(tmp_path, rate):
    from wsl2_audio.bounded_audio import model_channel
    from wsl2_audio.recognition import _model_audio
    from wsl2_audio.source_clock import SampleSpan
    count = rate*3+137
    signal = np.sin(np.arange(count)*.017)*.2
    r = recording(tmp_path, np.column_stack([signal, -signal]), rate)
    calls = []
    from wsl2_audio.recording_audio import read_channel
    def reader(r, span, channel):
        calls.append(span.end-span.start)
        return read_channel(r, span, channel)
    mapped, silent = model_channel(r, 1, reader=reader, read_seconds=1)
    expected = _model_audio(-signal, rate, SampleSpan(0, count))[1]
    assert isinstance(mapped, np.memmap) and not silent
    np.testing.assert_array_equal(mapped, expected)
    assert max(calls) <= 3*rate
    def no_read(*args):
        pytest.fail('matching model-audio cache decoded again')
    cached, _ = model_channel(r, 1, reader=no_read, read_seconds=1)
    np.testing.assert_array_equal(cached, mapped)


def test_changed_model_audio_cache_fails_visibly(tmp_path):
    from wsl2_audio.bounded_audio import model_channel
    r = recording(tmp_path, np.ones(16000)*.1)
    mapped, _ = model_channel(r, 0)
    path = mapped.filename
    del mapped
    with open(path, 'r+b') as f:
        f.write(b'xxxx')
    with pytest.raises(ValueError, match='checkpoint'):
        model_channel(r, 0)


def observer_for_windows(tmp_path):
    from wsl2_audio.source_clock import SampleSpan
    r = recording(tmp_path, np.ones(3010), 10)
    observer = object.__new__(RecordingObservers)
    observer.rate, observer.count, observer.duration = 10, 3010, 301.
    observer.full = SampleSpan(0, 3010)
    observer.recording, observer.evidence, observer.profile = r, {'source': r['source']}, {}
    observer._audio = lambda channel, span: np.zeros(span.end-span.start)
    return observer


def test_boundary_regions_rejoin_and_partial_resume_reuses_successful_windows(tmp_path, monkeypatch):
    observer = observer_for_windows(tmp_path)
    calls = []
    def region(self, channel, model, extractor, prior):
        calls.append(self.count)
        if len(calls) == 2:
            raise RuntimeError('one interrupted window')
        return {'status': 'ok', 'regions': [{'span': {'start': 0, 'end': self.count}, 'channel': channel}]}
    monkeypatch.setattr(RecordingObservers, '_phrase_activity', region)
    first = observer._bounded_activity('phrase_activity', 0, None, None, {})
    assert first['status'] == 'partial'
    assert first['assessed_spans'] == [{'start': 0, 'end': 600}, {'start': 1200, 'end': 3010}]
    assert len(calls) == 6
    resumed = observer._bounded_activity('phrase_activity', 0, None, None, {})
    assert len(calls) == 7
    assert resumed['status'] == 'ok'
    assert resumed['regions'] == [{'span': {'start': 0, 'end': 3010}, 'channel': 0}]
    assert resumed['assessed_spans'] == [{'start': 0, 'end': 3010}]
    assert observer._bounded_activity('phrase_activity', 0, None, None, {}) == resumed
    assert len(calls) == 7


def test_context_overlap_is_retained_outside_core_and_primary_exclusions_survive(tmp_path, monkeypatch):
    observer = observer_for_windows(tmp_path)
    def overlap(self, channel, *args):
        return {'status': 'ok', 'intervals': [{'span': {'start': 0, 'end': 20}, 'channel': channel,
                                              'detector': 'nemotron3'}],
                'single_activity': [{'span': {'start': 0, 'end': self.count}, 'channel': channel}]}
    monkeypatch.setattr(RecordingObservers, '_overlap', overlap)
    local = {'span': {'start': 900, 'end': 910}, 'channel': 0, 'detector': 'local_segmentation'}
    result = observer._bounded_activity('overlap', 0, None, None, {'speaker_activity': {'local_overlap': [local]}})
    assert any(r['span'] == {'start': 550, 'end': 570} for r in result['intervals'])
    assert local in result['intervals']
    assert result['single_activity'] == [{'span': {'start': 0, 'end': 3010}, 'channel': 0}]


@pytest.mark.parametrize('policy', [{'id': 'other', 'max_duration_seconds': 3600},
                                  {'id': 'bounded_recording_v1', 'max_duration_seconds': 99999},
                                  {'id': 'bounded_recording_v1', 'max_duration_seconds': True},
                                  {'id': 'bounded_recording_v2', 'max_duration_seconds': 28801}])
def test_unqualified_resource_policy_is_rejected_before_reads(tmp_path, policy):
    r = recording(tmp_path, np.ones(10), 10)
    with pytest.raises(ValueError, match='policy'):
        RecordingObservers({'enrichment': {'device': 'cpu', 'recording_policy': policy}}, {'source': r['source']}, r)


def test_over_60_minute_recording_policy_v2_streams_bounded_reads_and_caps_batches(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    import torch
    from wsl2_audio import enrichment_models, process_audio

    # 2-hour recording (7200s) at test sample rate 10 Hz -> 72,000 samples
    count, rate = 72000, 10
    r = recording(tmp_path, np.ones(count) * .1, rate)
    calls = []
    original = enrichment_models.read_channel

    def bounded(rec, span, channel):
        calls.append(span.end - span.start)
        assert span.end - span.start <= 32 * rate
        return original(rec, span, channel)

    monkeypatch.setattr(enrichment_models, 'read_channel', bounded)
    profile = {'enrichment': {
        'device': 'cpu',
        'recording_policy': {'id': 'bounded_recording_v2', 'max_duration_seconds': 28800},
        'models': {'speaker_activity': {'id': 'fixture-pyannote', 'path': str(tmp_path)}},
    }}
    observer = RecordingObservers(profile, {'source': r['source']}, r)
    assert observer.duration == 7200 and observer.long_recording
    assert max(calls) <= 32 * rate

    class FakePipeline:
        segmentation_batch_size = 32
        embedding_batch_size = 32
        device_used = None

        def to(self, dev):
            self.device_used = str(dev)
            return self

    fake_pipeline = FakePipeline()
    monkeypatch.setitem(sys.modules, 'pyannote.audio', SimpleNamespace(
        Pipeline=SimpleNamespace(from_pretrained=lambda path: fake_pipeline)))

    class Annotation:
        def itertracks(self, **kwargs):
            return iter([])

    def fake_diarize(pipeline, audio, *, overlap_evidence, observe_empty):
        overlap_evidence.update(status='ok', intervals=[])
        return Annotation(), {'status': 'ok', 'flags': []}

    monkeypatch.setattr(process_audio, '_diarize_with_review', fake_diarize)
    res = observer.observe('speaker_activity', {})
    assert res['status'] == 'ok'
    assert fake_pipeline.segmentation_batch_size == 16
    assert fake_pipeline.embedding_batch_size == 16
    assert res['channels']['0']['continuity']['segmentation_batch_size'] == 16
    assert res['channels']['0']['continuity']['embedding_batch_size'] == 16


def test_cuda_enrichment_fails_hard_without_gpu_and_places_models_on_cuda_when_available(tmp_path, monkeypatch):
    import torch

    r = recording(tmp_path, np.ones(1600) * .1, 1600)
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    with pytest.raises(ValueError, match='no automatic device fallback'):
        RecordingObservers({'enrichment': {'device': 'cuda'}}, {'source': r['source']}, r)

    emptied = []
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.cuda, 'empty_cache', lambda: emptied.append(True))
    observer = RecordingObservers({
        'enrichment': {'device': 'cuda', 'models': {'vocal_delivery': {'id': 'emo', 'path': 'fixture'}}}},
        {'source': r['source']}, r)
    assert observer.device == 'cuda'

    from transformers import Wav2Vec2FeatureExtractor
    from wsl2_audio import process_audio
    from types import SimpleNamespace

    seen_devices = []

    class FakeEmoModel:
        config = SimpleNamespace(id2label={0: 'neutral', 1: 'happy'})

        def to(self, dev):
            seen_devices.append(('model', str(dev)))
            return self

        def __call__(self, **kwargs):
            return SimpleNamespace(logits=torch.tensor([[.2, .8]]))

    class FakeInputs(dict):
        def to(self, dev):
            seen_devices.append(('inputs', str(dev)))
            return self

    monkeypatch.setattr(process_audio, '_load_trained_wav2vec', lambda *a, **kw: (FakeEmoModel(), {'strict': True}))
    monkeypatch.setattr(Wav2Vec2FeatureExtractor, 'from_pretrained',
                        lambda *a, **kw: lambda *args, **kwargs: FakeInputs(input_values=torch.ones((1, 1600))))
    out = observer.vocal_delivery([{'id': 'u1', 'channel': 0, 'span': {'start': 0, 'end': 1600}}])
    assert out['results'][0]['label'] == 'happy'
    assert ('model', 'cuda') in seen_devices
    assert ('inputs', 'cuda') in seen_devices
    assert emptied
