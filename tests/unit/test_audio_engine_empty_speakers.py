"""Empty model observations are completion, never proof of clean speech."""
from types import SimpleNamespace

import numpy as np
import pytest

from wsl2_audio.enrichment_models import RecordingObservers
from wsl2_audio.source_clock import SampleSpan


class Window:
    start, duration, step = 0., .1, .1

    def __getitem__(self, index):
        start = self.start + index*self.step
        return SimpleNamespace(start=start, end=start+self.duration)


def observer():
    result = object.__new__(RecordingObservers)
    result.rate, result.count, result.duration = 16000, 32000, 2.
    result.full = SampleSpan(0, result.count)
    result._audio = lambda channel: np.ones(result.count, dtype=np.float32)
    return result


class EmptyPipeline:
    _segmentation = SimpleNamespace(model=SimpleNamespace(receptive_field=Window()))

    def __init__(self, fault=None):
        self.fault = fault

    def reconstruct(self, *args):
        pytest.fail('zero-speaker early return must not reconstruct or cluster')

    def __call__(self, audio, hook=None):
        windows = Window()
        windows.duration = 2.
        segmentation = SimpleNamespace(data=np.zeros((1, 20, 3)), sliding_window=windows)
        count = SimpleNamespace(data=np.zeros((20, 1)), sliding_window=Window())
        if self.fault == 'nonfinite_count':
            count.data[0, 0] = np.nan
        elif self.fault == 'positive_count':
            count.data[0, 0] = 1
        elif self.fault == 'nonfinite_segmentation':
            segmentation.data[0, 0, 0] = np.nan
        elif self.fault == 'active_segmentation':
            segmentation.data[0, 0, 0] = 1
        elif self.fault == 'short_count':
            count.data = count.data[:2]
        elif self.fault == 'short_segmentation':
            segmentation.data = segmentation.data[:, :2]
        if hook:
            if self.fault != 'missing_segmentation':
                hook('segmentation', segmentation, file=audio)
            if self.fault != 'missing_count':
                hook('speaker_counting', count, file=audio)
        tracks = [(SimpleNamespace(start=.2, end=.5), None, 'unexpected')] if self.fault == 'nonempty_annotation' else []
        return SimpleNamespace(speaker_diarization=SimpleNamespace(itertracks=lambda **kwargs: iter(tracks)))


def test_valid_zero_speaker_early_return_retains_completed_observation():
    pipeline = EmptyPipeline()
    row = observer()._speaker_activity(0, pipeline, None, {})
    assert row['status'] == 'ok' and row['assessed_spans'] == [{'start': 0, 'end': 32000}]
    assert row['tracks'] == row['flags'] == row['local_overlap'] == []
    assert row['raw_review']['reason'] == 'completed_no_speakers'
    assert row['raw_local_overlap']['status'] == 'ok'
    assert 'reconstruct' not in vars(pipeline)


@pytest.mark.parametrize('fault', ['missing_count', 'missing_segmentation', 'nonfinite_count',
    'positive_count', 'nonfinite_segmentation', 'active_segmentation', 'short_count',
    'short_segmentation', 'nonempty_annotation'])
def test_empty_annotation_without_valid_full_activity_evidence_stays_unavailable(fault):
    pipeline = EmptyPipeline(fault)
    with pytest.raises(ValueError, match='Local activity/reconstruction evidence missing'):
        observer()._speaker_activity(0, pipeline, None, {})
    assert 'reconstruct' not in vars(pipeline)


def overlap_tools(fault=None, mixed=False):
    import torch

    class Batch(dict):
        @property
        def attention_mask(self):
            return self['attention_mask']

        def to(self, *args, **kwargs):
            return self

    class Extractor:
        feature_extractor = SimpleNamespace(hop_length=160, sampling_rate=16000)

        def __call__(self, audio, **kwargs):
            mask = torch.ones((1, 200), dtype=torch.bool)
            if fault == 'empty_mask':
                mask[:] = False
            elif fault == 'truncated_mask':
                mask[:, 100:] = False
            elif fault == 'mask_gap':
                mask[:, 50] = False
            elif fault == 'nonfinite_mask':
                mask = mask.float()
                mask[:, 0] = float('nan')
            return Batch(attention_mask=mask)

    class Model:
        def __call__(self, **kwargs):
            logits = torch.full((1, 200, 4), -10.)
            logits[:, :, 0] = 10.
            if mixed:
                logits[:, 50:100, 1] = 10.
            if fault == 'nonfinite_logits':
                logits[:, 0, 0] = float('nan')
            return SimpleNamespace(logits=logits)
    return Model(), Extractor()


@pytest.mark.parametrize('primary_status', ['error', 'unavailable', None])
@pytest.mark.parametrize('mixed', [False, True])
def test_nemotron_completion_is_independent_of_primary_speaker_failure(primary_status, mixed):
    model, extractor = overlap_tools(mixed=mixed)
    prior = {'speaker_activity': {'channels': {'0': {'status': primary_status}}}}
    row = observer()._overlap(0, model, extractor, prior)
    assert row['status'] == 'ok'
    assert row['assessed_spans'] == [{'start': 0, 'end': 32000}]
    assert bool(row['intervals']) == mixed
    assert row['primary_activity_status'] == primary_status
    # A working second detector cannot supply the missing primary evidence.
    from tests.unit.test_audio_engine_enrichment import inputs
    from wsl2_audio.enrichment import attach_observations
    from wsl2_audio.eligibility import select_inputs
    evidence, observations = inputs()
    observations['speaker_activity'].update(status='unavailable', assessed_spans=[],
        channel_assessed_spans={'0': []}, tracks=[], reason='injected_primary_failure')
    observations['overlap'].update(row)
    result = attach_observations(evidence, observations)
    assert result['utterances'][0]['text'] == 'Yay Joe'
    assert not select_inputs(result, 'voice_sample')
    assert not select_inputs(result, 'vocal_delivery')


@pytest.mark.parametrize('fault', ['empty_mask', 'truncated_mask', 'mask_gap', 'nonfinite_mask', 'nonfinite_logits'])
def test_incomplete_or_invalid_nemotron_output_cannot_claim_full_assessment(fault):
    model, extractor = overlap_tools(fault)
    with pytest.raises(ValueError):
        observer()._overlap(0, model, extractor, {'speaker_activity': {'channels': {'0': {'status': 'ok'}}}})


def test_complete_input_assessment_does_not_extend_positive_frames_over_terminal_remainder():
    model, extractor = overlap_tools()
    item = observer()
    item.count = 32048
    item.duration = item.count/item.rate
    item.full = SampleSpan(0, item.count)
    row = item._overlap(0, model, extractor, {})
    assert row['assessed_spans'] == [{'start': 0, 'end': 32048}]
    assert row['single_activity'][-1]['span']['end'] == 32000


def test_local_overlap_remains_an_exclusion_when_nemotron_disagrees():
    model, extractor = overlap_tools()
    local = {'span': {'start': 8000, 'end': 12000}, 'channel': 0, 'status': 'observed', 'detector': 'local_segmentation'}
    row = observer()._overlap(0, model, extractor, {'speaker_activity': {
        'channels': {'0': {'status': 'ok'}}, 'local_overlap': [local]}})
    assert row['intervals'] == [local]
    from tests.unit.test_audio_engine_enrichment import inputs
    from wsl2_audio.enrichment import attach_observations
    from wsl2_audio.eligibility import select_inputs
    evidence, observations = inputs()
    observations['overlap'].update(row)
    result = attach_observations(evidence, observations)
    assert not select_inputs(result, 'voice_sample') and not select_inputs(result, 'vocal_delivery')


def test_completed_empty_primary_does_not_admit_a_second_detectors_single_voice_guess():
    from tests.unit.test_audio_engine_enrichment import inputs
    from wsl2_audio.enrichment import attach_observations
    from wsl2_audio.eligibility import select_inputs
    evidence, observations = inputs()
    observations['speaker_activity']['tracks'] = []
    result = attach_observations(evidence, observations)
    assert result['utterances'][0]['speaker']['status'] == 'unresolved'
    assert not select_inputs(result, 'voice_sample') and not select_inputs(result, 'vocal_delivery')
