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
