"""New review observer boundaries, without audio/model inference."""
import types
import numpy as np
import pytest
from wsl2_audio.process_audio import _diarize_with_review


@pytest.mark.parametrize('case', ['clean', 'overlap', 'different_cluster', 'no_return', 'raises'])
def test_review_observer_preserves_caller_and_rejects_non_candidates(case):
    data = np.zeros((1, 9, 3))
    data[0, :3, 0] = 1
    data[0, 3:6, 1] = 1
    data[0, 6:, 0] = 1
    hard = np.zeros((1, 3), dtype=int)
    if case == 'clean':
        data[:] = 0
        data[0, :, 0] = 1
    elif case == 'overlap':
        data[0, 3:6, 0] = 1
    elif case == 'different_cluster':
        hard[0, 1] = 1
    elif case == 'no_return':
        data[0, 6:, 0] = 0
        data[0, 6:, 2] = 1
    sentinel = object()
    class Pipeline:
        _segmentation = types.SimpleNamespace(model=types.SimpleNamespace(
            receptive_field=types.SimpleNamespace(start=0, duration=.1, step=.1)))
        def reconstruct(self, segments, clusters, count):
            if case == 'raises':
                raise RuntimeError('original reconstruction failed')
            return sentinel
        def __call__(self, audio):
            return self.reconstruct(types.SimpleNamespace(data=data, sliding_window=[
                types.SimpleNamespace(start=0, end=.9)]), hard, None)
    pipeline = Pipeline()
    audio = {'waveform': np.zeros((1, 900)), 'sample_rate': 1000}
    if case == 'raises':
        with pytest.raises(RuntimeError, match='original reconstruction failed'):
            _diarize_with_review(pipeline, audio)
    else:
        output, review = _diarize_with_review(pipeline, audio)
        assert output is sentinel
        assert review['status'] == 'ok' and review['flags'] == []
    assert 'reconstruct' not in vars(pipeline)


def test_review_observer_reports_unsupported_pipeline_without_changing_output():
    sentinel = object()
    output, review = _diarize_with_review(lambda audio: sentinel, {})
    assert output is sentinel
    assert review['status'] == 'unavailable'
    assert review['flags'] == []


@pytest.mark.parametrize('cluster', [0, -2])
def test_local_overlap_survives_single_global_label_and_count_averaging(cluster):
    from wsl2_audio import process_audio as worker
    data = np.zeros((2, 10, 3))
    data[:, :, 0] = 1
    data[1, 3:5, 1] = 1  # Only one window observes the second simultaneous voice.
    original = data.copy()
    hard = np.full((2, 3), cluster, dtype=int)
    frames = types.SimpleNamespace(start=0, duration=.1, step=.1)
    segments = types.SimpleNamespace(data=data, sliding_window=[
        types.SimpleNamespace(start=0, end=1), types.SimpleNamespace(start=.2, end=1.2)])
    evidence = {}
    sentinel = object()
    class Pipeline:
        _segmentation = types.SimpleNamespace(model=types.SimpleNamespace(receptive_field=frames))
        def reconstruct(self, segmentations, clusters, count):
            assert np.array_equal(segmentations.data, original)
            assert np.array_equal(clusters, hard)
            return sentinel
        def __call__(self, audio):
            # Regular and exclusive reconstruction use the same local observations.
            self.reconstruct(segments, hard, np.ones((10, 1)))
            return self.reconstruct(segments, hard, np.ones((10, 1)))
    pipeline = Pipeline()
    output, review = worker._diarize_with_review(pipeline,
        {'waveform': np.zeros((1, 1200)), 'sample_rate': 1000}, overlap_evidence=evidence)
    assert output is sentinel and 'reconstruct' not in vars(pipeline)
    assert evidence['status'] == 'ok'
    assert len(evidence['intervals']) == len(evidence['observations']) == 1
    assert evidence['intervals'][0] == pytest.approx({'start': .5, 'end': .7})
    assert evidence['identity_claim'] is False
    assert review['flags'] == []  # Existing review rule remains separate.


@pytest.mark.parametrize('value', [.7, float('nan'), float('inf')])
def test_local_overlap_rejects_unqualified_or_invalid_frame_values(value):
    from wsl2_audio.process_audio import _local_overlap_evidence
    segments = types.SimpleNamespace(data=np.array([[[1., value]]]),
        sliding_window=[types.SimpleNamespace(start=0, end=1)])
    frames = types.SimpleNamespace(start=0, duration=.1, step=.1)
    with pytest.raises(ValueError, match='binary'):
        _local_overlap_evidence(segments, frames, 1.)


def test_local_overlap_clips_padded_tail_without_inventing_overlap_before_audio():
    from wsl2_audio.process_audio import _local_overlap_evidence
    segments = types.SimpleNamespace(data=np.ones((1, 10, 2)),
        sliding_window=[types.SimpleNamespace(start=0, end=1)])
    result = _local_overlap_evidence(segments,
        types.SimpleNamespace(start=0, duration=.1, step=.1), .65)
    assert result['intervals'] == [{'start': 0., 'end': .65}]


def test_empty_local_segmentation_cannot_claim_an_overlap_free_observation():
    from wsl2_audio.process_audio import _local_overlap_evidence
    with pytest.raises(ValueError, match='binary'):
        _local_overlap_evidence(types.SimpleNamespace(data=np.zeros((0, 10, 3))),
            types.SimpleNamespace(start=0, duration=.1, step=.1), 1.)
