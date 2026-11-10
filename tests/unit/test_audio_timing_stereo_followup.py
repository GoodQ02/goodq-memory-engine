from array import array
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from tests.unit.test_audio_engine_recording import ffmpeg
from tests.unit.test_audio_engine_recording_call import verify_test_assets
from tests.unit.test_audio_engine_recognition import Model, segment
from tests.unit import test_audio_lossless_phrase_repair as caller_fixture
from wsl2_audio import recognition, transcription_contract
from wsl2_audio.source_clock import SampleSpan
from wsl2_audio.evidence_contract import validate_evidence
from wsl2_audio.eligibility import select_inputs


@pytest.mark.parametrize('rate', [16000,44100,48000])
def test_ordered_raw_word_boundaries_share_one_quantized_sample_without_losing_words(monkeypatch, rate):
    raw = segment(start=0,end=1)
    boundary = .38400000000000007
    raw.words = [SimpleNamespace(word='Yay',start=.2,end=boundary,probability=.9),
                 SimpleNamespace(word='Joe!',start=boundary,end=.6,probability=.9)]
    monkeypatch.setattr(transcription_contract, '_align_after_decoding',
                        lambda model,audio,segments,language:(segments,{'status':'completed'}))
    monkeypatch.setattr(recognition, '_speech_activity',
                        lambda audio,r,c:{'status':'ok','spans':[vars(c)],'assessed_spans':[vars(c)]})
    model = Model([raw])
    result = recognition.recognize_window(model,array('d',[.001]*rate),rate,SampleSpan(rate,2*rate),language='en')
    left,right = result['utterances'][0]['words']
    assert left['timing'] == right['timing'] == 'supported'
    assert left['span']['end'] == right['span']['start']
    assert result['raw_segments'][0]['words'][0]['end'] == result['raw_segments'][0]['words'][1]['start'] == boundary
    assert recognition.complete_word_span('Yay Joe!', [left,right]) is not None
    assert len(model.calls) == 1


def test_real_raw_overlap_is_not_repaired_as_rounding(monkeypatch):
    raw = segment(start=0,end=1)
    raw.words = [SimpleNamespace(word='Yay',start=.2,end=.38400000000000007,probability=.9),
                 SimpleNamespace(word='Joe!',start=.384,end=.6,probability=.9)]
    monkeypatch.setattr(transcription_contract, '_align_after_decoding',
                        lambda model,audio,segments,language:(segments,{'status':'completed'}))
    monkeypatch.setattr(recognition, '_speech_activity',
                        lambda audio,r,c:{'status':'ok','spans':[vars(c)],'assessed_spans':[vars(c)]})
    result = recognition.recognize_window(Model([raw]),array('d',[.001]*48000),48000,SampleSpan(0,48000),language='en')
    assert result['utterances'][0]['words'][1]['reason'] == 'word_alignment_order_conflict'


def stereo_caller(tmp_path, ffmpeg, monkeypatch, *, differing_tail=False, veto=False):
    write = caller_fixture.write_pcm
    def write_channels(path, samples, **kwargs):
        first = np.round(10000*np.sin(np.arange(32000)*.13)).astype(int)
        second = first.copy()
        second[2000:4000] += 2000  # Whole native block fails; final phrase can still be identical.
        if differing_tail:
            second[21000:21500] += 2000
        return write(path, np.stack([first,second],axis=1).ravel().tolist(),channels=2)
    monkeypatch.setattr(caller_fixture,'write_pcm',write_channels)
    def change(_, observations):
        if veto:
            observations['acoustic_events']['events'] = [{'id':'other-channel-cry','channel':1,
                'span':{'start':21000,'end':22000},'label':'crying','status':'observed'}]
    return caller_fixture.caller(tmp_path,ffmpeg,monkeypatch,change,channels=2)


def test_pcm_proven_phrase_reconciles_after_parent_failure_through_consumers(tmp_path, ffmpeg, monkeypatch):
    result, consumed, recognizer = stereo_caller(tmp_path,ffmpeg,monkeypatch)
    assert not result.get('channel_reconciliation')
    assert len(result['phrase_channel_reconciliation']['groups']) == 1
    assert len(result['utterances']) == 3
    tail = next(u for u in result['utterances'] if u['text']=='All done.')
    assert tail['source_channels'] == [0,1]
    assert tail in select_inputs(result,'vocal_delivery')
    assert consumed['transcript'].count('All done.') == 1
    assert len(recognizer.calls) == 2
    assert result['vocal_delivery'][0]['utterance_id'] == tail['id']
    assert validate_evidence(result) == result


@pytest.mark.parametrize('differing_tail,veto', [(True,False),(False,True)])
def test_phrase_proof_never_relaxes_pcm_limits_or_other_channel_veto(tmp_path, ffmpeg, monkeypatch, differing_tail, veto):
    result, _, _ = stereo_caller(tmp_path,ffmpeg,monkeypatch,differing_tail=differing_tail,veto=veto)
    tails = [u for u in result['utterances'] if u['text']=='All done.']
    assert len(tails) == (2 if differing_tail else 1)
    assert all(u not in select_inputs(result,'voice_sample') for u in tails)
    if veto:
        assert 'sound_event_crying' in tails[0]['eligibility']['voice_sample']['reasons']


@pytest.mark.parametrize('mutation', ['drop_record','drop_member','word','proof','score','original_overlap','channel'])
def test_phrase_reconciliation_provenance_cannot_be_forged(tmp_path, ffmpeg, monkeypatch, mutation):
    result, _, _ = stereo_caller(tmp_path,ffmpeg,monkeypatch)
    group = result['phrase_channel_reconciliation']['groups'][0]
    tail = next(u for u in result['utterances'] if u['text']=='All done.')
    if mutation == 'drop_record': result.pop('phrase_channel_reconciliation')
    elif mutation == 'drop_member': group['members'].pop()
    elif mutation == 'word': group['members'][1]['words'][0]['text']='invented'
    elif mutation == 'proof': group['proofs'][0]['span']['start']+=1
    elif mutation == 'score': tail['quality']['avg_logprob']=0
    elif mutation == 'original_overlap': result['phrase_channel_reconciliation']['original_overlap']=[]
    else: tail['source_channels']=[0]
    with pytest.raises(ValueError):
        validate_evidence(result)


@pytest.mark.parametrize('edge', ['start','end'])
def test_complete_outer_refinement_keeps_margin_contamination(tmp_path, ffmpeg, monkeypatch, edge):
    def change(_, observations):
        span = {'start':1100,'end':1400} if edge=='start' else {'start':26600,'end':26900}
        observations['acoustic_events']['events']=[{'id':'margin','label':'crying','status':'observed','channel':0,'span':span}]
    result, _, _ = caller_fixture.caller(tmp_path,ffmpeg,monkeypatch,change)
    unit = result['utterances'][0 if edge=='start' else -1]
    assert unit['span'][edge] == (1000 if edge=='start' else 27000)
    assert 'sound_event_crying' in unit['eligibility']['voice_sample']['reasons']


def test_previous_v4_envelopes_keep_their_original_outer_edges(tmp_path, ffmpeg, monkeypatch):
    from wsl2_audio import phrase_resolution as phrases
    from wsl2_audio.enrichment import attach_observations
    result, _, _ = caller_fixture.caller(tmp_path,ffmpeg,monkeypatch)
    parent = result['phrase_resolution']['parents'][0]['native']
    observations = result['enrichment_observations']
    proposal = phrases._proposal(parent,observations['phrase_activity'],result,method=phrases.COALESCED_METHOD)
    units = phrases._children(parent,proposal,result,method=phrases.COALESCED_METHOD)
    plans = phrases._envelope_plans(units,observations,result,complete_alignment=True,phrase_edges=True,internal_edges=True)
    for unit in units:
        if unit['id'] in plans:
            unit['envelope_source']={'method':phrases.ACTIVITY_EDGE_METHOD,'original_span':deepcopy(unit['span'])}
            unit['span']=plans[unit['id']]
            unit['quality']['speech_coverage']=phrases._envelope_coverage(unit,result)
    result['utterances']=units
    result['vocal_delivery']=[]
    result['phrase_resolution']['envelope_method']=phrases.ACTIVITY_EDGE_METHOD
    result=attach_observations(result,observations)
    assert result['utterances'][-1]['span']=={'start':19000,'end':27000}
    assert validate_evidence(result)==result
