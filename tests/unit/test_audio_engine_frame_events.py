import json

import numpy as np
import pytest

from tests.unit.test_audio_engine_enrichment import inputs
from wsl2_audio.eligibility import select_inputs
from wsl2_audio.enrichment import attach_observations
from wsl2_audio.source_clock import SampleSpan


def test_clear_phrase_uses_positive_frame_support_without_a_crop_classifier():
    evidence, observations = inputs()
    acoustic = observations['acoustic_events']
    acoustic.pop('phrases', None)
    acoustic.update(method='efficientsed_frames_v1', threshold=.5,
                    speech_intervals=[{'span':{'start':2000,'end':18000},'channel':0}])
    result = attach_observations(evidence,observations)
    assert select_inputs(result,'vocal_delivery') == result['utterances']
    assert select_inputs(result,'voice_sample') == result['utterances']


@pytest.mark.parametrize('rate,count',[(16000,1),(16000,38400),(44100,44101),(44101,100003),(48000,480001)])
def test_frame_mapping_reaches_exact_source_end_without_padded_claims(rate,count):
    from wsl2_audio.frame_events import windows, valid_frames
    for span in windows(count,rate):
        frames=valid_frames(span,rate)
        assert frames[0].start==span.start and frames[-1].end==span.end
        assert all(span.start<=f.start<f.end<=span.end for f in frames)
        assert all(a.end>=b.start for a,b in zip(frames,frames[1:]))


def labels():
    return ['Laughter','Female speech, woman speaking','Male singing','Baby cry, infant cry']+[f'other{i}' for i in range(443)]


class Session:
    calls=0
    def run(self,names,inputs):
        self.calls+=1
        scores=np.zeros((1,250,447),dtype=np.float32)
        scores[0,5:8,0]=.7
        scores[0,:60,1]=.8
        scores[0,60:,0]=.99
        return [scores]


def test_localized_events_exclude_padding_and_retain_speech_descendant_support():
    from wsl2_audio.frame_events import observe_frames
    result=observe_frames(Session(),labels(),lambda span:np.ones(span.end-span.start,dtype=np.float32),
                          16000,38400,0,'a'*64)
    assert result['events'][0]['span']=={'start':3200,'end':5120}
    assert result['speech_intervals']==[{'span':{'start':0,'end':38400},'channel':0}]
    assert len(result['events'])==1
    json.dumps(result)


def test_digital_zero_never_calls_the_model_or_invents_events():
    from wsl2_audio.frame_events import observe_frames
    model=Session()
    result=observe_frames(model,labels(),lambda span:np.zeros(span.end-span.start,dtype=np.float32),
                          16000,38400,0,'a'*64)
    assert model.calls==0 and not result['events'] and not result['speech_intervals']
    assert result['status']=='ok' and result['windows'][0]['reason']=='digital_silence'


def test_failure_in_later_window_keeps_earlier_events_and_marks_partial_coverage():
    from wsl2_audio.frame_events import observe_frames
    class Partial(Session):
        def run(self,*args):
            if self.calls:
                raise RuntimeError('injected failure')
            return super().run(*args)
    result=observe_frames(Partial(),labels(),lambda span:np.ones(span.end-span.start,dtype=np.float32),
                          16000,192000,0,'a'*64)
    assert result['status']=='partial' and result['events'] and result['failures']
    assert result['assessed_spans']==[{'start':0,'end':80000}]


def test_fixed_event_context_is_not_selected_from_transcript_or_vad_boundaries():
    from wsl2_audio.frame_events import windows
    spans=list(windows(909168,16000))
    assert [(s.start,s.end) for s in spans[:3]]==[(0,80000),(40000,120000),(80000,160000)]
    assert spans[-1].end==909168 and spans[-2].end<909168


def test_failed_window_serialization_does_not_publish_unassessed_positive_events():
    from wsl2_audio.frame_events import observe_frames
    class Unserializable(np.ndarray):
        def tolist(self):
            raise RuntimeError('injected observation serialization failure')
    class Broken(Session):
        def run(self,*args):
            return [super().run(*args)[0].view(Unserializable)]
    result=observe_frames(Broken(),labels(),lambda span:np.ones(span.end-span.start,dtype=np.float32),
                          16000,38400,0,'a'*64)
    assert result['failures'] and not result['assessed_spans']
    assert not result['events'] and not result['speech_intervals']


@pytest.mark.parametrize('bad',['nan','range','shape'])
def test_bad_model_output_fails_visibly_instead_of_reporting_no_events(bad):
    from wsl2_audio.frame_events import observe_frames
    class Bad(Session):
        def run(self,*args):
            data=super().run(*args)[0]
            if bad=='nan': data[0,0,0]=np.nan
            elif bad=='range': data[0,0,0]=1.1
            else: data=data[:,:-1]
            return [data]
    result=observe_frames(Bad(),labels(),lambda span:np.ones(span.end-span.start,dtype=np.float32),
                          16000,16000,0,'a'*64)
    assert result['status']=='partial' and not result['assessed_spans']
    assert result['failures'] and not result['events']


def test_v2_consensus_rejects_boundary_window_false_positive_and_preserves_v1_and_speech_support():
    from wsl2_audio.frame_events import (
        ANALYSIS_POLICY,
        ANALYSIS_POLICY_V2,
        METHOD,
        METHOD_V2,
        observe_frames,
    )

    class BoundaryDisagreementSession:
        def __init__(self):
            self.window_index = 0

        def run(self, names, inputs):
            idx = self.window_index
            self.window_index += 1
            scores = np.zeros((1, 250, 447), dtype=np.float32)
            scores[0, :125, 1] = .8
            if idx == 1:  # [2.5s, 7.5s]: centered window sees speech only (0.37 < 0.5)
                scores[0, 93:110, 0] = .37
            elif idx == 2:  # [5.0s, 10.0s]: boundary-cut false positive at 6.24-6.88s + real laugh at 9.2-10.0s
                scores[0, 31:45, 0] = .66
                scores[0, 105:125, 0] = .75
            elif idx == 3:  # [7.5s, 12.0s]: confirms real laugh at 9.2-11.2s
                scores[0, 42:93, 0] = .82
            return [scores]

    audio = lambda span: np.ones(span.end - span.start, dtype=np.float32) * .1
    v1 = observe_frames(BoundaryDisagreementSession(), labels(), audio, 16000, 192000, 0, 'a' * 64)
    v2 = observe_frames(BoundaryDisagreementSession(), labels(), audio, 16000, 192000, 0, 'a' * 64,
                        policy=ANALYSIS_POLICY_V2)
    assert v1['method'] == METHOD and v1['analysis_policy'] == ANALYSIS_POLICY
    assert v2['method'] == METHOD_V2 and v2['analysis_policy'] == ANALYSIS_POLICY_V2
    assert len(v1['events']) == 2
    assert v1['events'][0]['span'] == {'start': 99840, 'end': 108800}
    assert len(v2['events']) == 1
    assert v2['events'][0]['span'] == {'start': 147200, 'end': 179520}
    assert v2['speech_intervals'] == v1['speech_intervals']

    evidence, observations = inputs()
    acoustic = observations['acoustic_events']
    acoustic.pop('phrases', None)
    acoustic.update(method=METHOD_V2, analysis_policy=dict(ANALYSIS_POLICY_V2), threshold=.5,
                    events=[], speech_intervals=[{'span': {'start': 2000, 'end': 18000}, 'channel': 0}])
    attached = attach_observations(evidence, observations)
    assert select_inputs(attached, 'vocal_delivery') == attached['utterances']
    assert select_inputs(attached, 'voice_sample') == attached['utterances']


def test_v2_partial_window_failure_keeps_single_assessed_events():
    from wsl2_audio.frame_events import ANALYSIS_POLICY_V2, observe_frames

    class Partial(Session):
        def run(self, *args):
            if self.calls:
                raise RuntimeError('injected failure')
            return super().run(*args)

    result = observe_frames(Partial(), labels(), lambda span: np.ones(span.end - span.start, dtype=np.float32),
                            16000, 192000, 0, 'a' * 64, policy=ANALYSIS_POLICY_V2)
    assert result['status'] == 'partial' and result['events'] and result['failures']
    assert result['assessed_spans'] == [{'start': 0, 'end': 80000}]
