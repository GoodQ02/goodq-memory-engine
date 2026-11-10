from copy import deepcopy

import pytest

from tests.unit.test_audio_engine_enrichment import inputs
from tests.unit.test_audio_engine_recording_call import ffmpeg, verify_test_assets
from wsl2_audio.eligibility import select_inputs
from wsl2_audio.enrichment import attach_observations
from wsl2_audio.evidence_contract import validate_evidence
from wsl2_audio.phrase_resolution import resolve_phrases


def sample():
    evidence, observations = inputs()
    u = evidence['utterances'][0]
    u.update(native_span={'start': 1000, 'end': 16000}, span={'start': 1000, 'end': 18000},
             observation_ids=['w0:c0:0'])
    u['words'] = [{'text': 'Yay', 'span': {'start': 2000, 'end': 9000}, 'timing': 'supported'},
                  {'text': 'Joe', 'span': {'start': 9000, 'end': 18000}, 'timing': 'supported'}]
    evidence['window_observations'] = [{'window_id': 'w0:c0', 'channel': 0,
        'context': {'start': 0, 'end': 32000},
        'speech_activity': {'status': 'ok', 'spans': [{'start': 1000, 'end': 22000}]}}]
    observations['phrase_activity']['regions'][0]['span'] = {'start': 2000, 'end': 21000}
    observations['speaker_activity']['tracks'][0]['span'] = {'start': 1500, 'end': 22000}
    observations['overlap']['single_activity'][0]['span'] = {'start': 1000, 'end': 22000}
    observations['acoustic_events']['speech_intervals'][0]['span'] = {'start': 1000, 'end': 22000}
    return evidence, observations


def test_native_word_disagreement_uses_observed_whole_activity_without_timestamp_padding():
    evidence, observations = sample()
    before = deepcopy(evidence)
    result = attach_observations(resolve_phrases(evidence, observations), observations)
    u = result['utterances'][0]
    assert u['span'] == {'start': 1000, 'end': 22000}
    assert u['native_span'] == before['utterances'][0]['native_span']
    assert u['words'] == before['utterances'][0]['words']
    assert u in select_inputs(result, 'vocal_delivery') and u in select_inputs(result, 'voice_sample')
    assert evidence == before


def coarse_sample():
    evidence,observations=sample()
    u=evidence['utterances'][0]
    u.pop('native_span')
    u['span']={'start':0,'end':30000}
    u['quality']['speech_coverage']=.7
    evidence['window_observations'][0]['speech_activity']['spans']=[{'start':1000,'end':22000}]
    return evidence,observations


def test_coarse_native_silence_does_not_dilute_complete_supported_phrase():
    evidence,observations=coarse_sample()
    result=attach_observations(resolve_phrases(evidence,observations),observations)
    u=result['utterances'][0]
    assert u['span']=={'start':1500,'end':22000}
    assert u['words']==evidence['utterances'][0]['words']
    assert u['quality']['speech_coverage']==1
    assert u in select_inputs(result,'voice_sample')
    assert u['envelope_source']['original_span']=={'start':0,'end':30000}


@pytest.mark.parametrize('reason',['missing_word','unavailable_word','overlap_tail','crying_tail','speaker_flag','edge'])
def test_tightening_never_discards_uncertain_words_or_contaminating_context(reason):
    evidence,observations=coarse_sample()
    u=evidence['utterances'][0]
    if reason=='missing_word': u['words'].pop()
    elif reason=='unavailable_word': u['words'][0].update(span=None,timing='unavailable',reason='invalid_word_alignment')
    elif reason=='overlap_tail': observations['overlap']['intervals']=[{'span':{'start':23000,'end':25000},'channel':0,'status':'observed'}]
    elif reason=='crying_tail': observations['acoustic_events']['events']=[{'id':'cry','label':'crying','span':{'start':23000,'end':25000},'channel':0,'status':'observed'}]
    elif reason=='speaker_flag': observations['speaker_activity']['flags']=[{'span':{'start':23000,'end':25000},'channel':0}]
    else: observations['phrase_activity']['regions'][0]['span']['end']=32000
    assert resolve_phrases(evidence,observations)['utterances'][0]['span']==u['span']


@pytest.mark.parametrize('change',['move','drop_word','drop_marker'])
def test_stored_tightened_envelope_is_reproduced_not_trusted(change):
    evidence,observations=coarse_sample()
    result=attach_observations(resolve_phrases(evidence,observations),observations)
    u=result['utterances'][0]
    if change=='move': u['span']['start']+=1
    elif change=='drop_word': u['words'].pop()
    else: result['phrase_resolution'].pop('envelope_method')
    with pytest.raises(ValueError,match='[Ee]nvelope'):
        validate_evidence(result)


def test_prior_envelope_version_keeps_its_original_resolution_semantics():
    from wsl2_audio.phrase_resolution import ENVELOPE_METHOD, METHOD
    evidence,observations=sample()
    result=attach_observations(resolve_phrases(evidence,observations),observations)
    result['phrase_resolution'].pop('envelope_method')
    result['phrase_resolution']['method'] = METHOD
    result['utterances'][0]['envelope_source']['method']=ENVELOPE_METHOD
    assert validate_evidence(result)==result


@pytest.mark.parametrize('case', ['neighbor', 'input_edge', 'unassessed', 'source_edge',
                                  'no_word_disagreement', 'conflicting_text'])
def test_envelope_does_not_expand_across_ambiguous_or_unassessed_boundaries(case):
    evidence, observations = sample()
    u = evidence['utterances'][0]
    if case == 'neighbor':
        neighbor = deepcopy(u)
        neighbor.update(id='neighbor', span={'start': 20000, 'end': 30000}, text='Someone else', words=[])
        evidence['utterances'].append(neighbor)
    elif case == 'input_edge':
        evidence['window_observations'][0]['context']['end'] = 21000
    elif case == 'unassessed':
        observations['speaker_activity']['channel_assessed_spans']['0'] = [{'start': 0, 'end': 20000}]
    elif case == 'source_edge':
        observations['phrase_activity']['regions'][0]['span']['end'] = 32000
    elif case == 'no_word_disagreement':
        u['native_span'] = deepcopy(u['span'])
    else:
        u['resolution'] = 'conflicting_hypotheses'
    resolved = resolve_phrases(evidence, observations)
    assert resolved['utterances'][0]['span'] == u['span']


@pytest.mark.parametrize('veto', ['overlap', 'crying', 'second_voice'])
def test_complete_expanded_phrase_still_obeys_individual_speech_gate(veto):
    evidence, observations = sample()
    tail = {'start': 19000, 'end': 21000}
    if veto == 'overlap':
        observations['overlap']['intervals'] = [{'span': tail, 'channel': 0, 'status': 'observed'}]
    elif veto == 'crying':
        observations['acoustic_events']['events'] = [{'id': 'cry', 'label': 'crying', 'span': tail,
                                                     'channel': 0, 'status': 'observed'}]
    else:
        observations['speaker_activity']['tracks'].append({'span': tail, 'channel': 0, 'speaker': 'other'})
    result = attach_observations(resolve_phrases(evidence, observations), observations)
    assert not select_inputs(result, 'vocal_delivery') and not select_inputs(result, 'voice_sample')
    assert result['utterances'][0]['text'] == 'Yay Joe'


def test_stored_envelope_cannot_claim_unobserved_extension():
    evidence, observations = sample()
    result = attach_observations(resolve_phrases(evidence, observations), observations)
    assert result['utterances'][0]['span']['end'] == 22000
    result['utterances'][0]['span']['end'] += 100
    with pytest.raises(ValueError, match='[Ee]nvelope'):
        validate_evidence(result)


def test_stored_envelope_cannot_drop_its_resolution_provenance():
    evidence, observations = sample()
    result = attach_observations(resolve_phrases(evidence, observations), observations)
    result.pop('phrase_resolution')
    with pytest.raises(ValueError, match='provenance'):
        validate_evidence(result)


@pytest.mark.parametrize('mutation', ['missing_marker', 'false_original_span'])
def test_stored_envelope_original_must_match_native_and_aligned_word_evidence(mutation):
    evidence, observations = sample()
    result = attach_observations(resolve_phrases(evidence, observations), observations)
    unit = result['utterances'][0]
    if mutation == 'missing_marker':
        unit.pop('envelope_source')
    else:
        unit['envelope_source']['original_span']['end'] = 17000
    with pytest.raises(ValueError, match='[Ee]nvelope'):
        validate_evidence(result)


def test_aligned_enclosure_collision_with_same_window_neighbor_stays_unresolved():
    from wsl2_audio.recording_engine import resolve_observations
    from wsl2_audio.source_clock import SourceClock

    evidence, observations = sample()
    first = evidence['utterances'][0]
    neighbor = deepcopy(first)
    neighbor.update(text='Next sentence', span={'start': 17000, 'end': 30000}, words=[])
    neighbor.pop('native_span')
    result = resolve_observations([{'window_id': 'w0:c0', 'channel': 0,
        'source_sha256': 'a'*64, 'context': {'start': 0, 'end': 32000},
        'utterances': [first, neighbor]}], SourceClock(16000, 32000))
    assert [u['text'] for u in result['utterances']] == ['Yay Joe', 'Next sentence']
    assert result['overlap'] == [{'span': {'start': 17000, 'end': 18000}, 'channel': 0,
        'status': 'unresolved', 'reason': 'aligned_envelope_collision'}]
    evidence.update(result)
    enriched = attach_observations(resolve_phrases(evidence, observations), observations)
    assert not select_inputs(enriched, 'vocal_delivery') and not select_inputs(enriched, 'voice_sample')


def test_recording_caller_uses_the_whole_supported_phrase_for_both_consumers(tmp_path, ffmpeg, monkeypatch):
    from tests.unit.test_audio_engine_enrichment_call import Observers, setup_call
    from tests.unit.test_audio_engine_recording_call import Recognizer
    from wsl2_audio import enrichment_models, recording_engine

    class BoundaryRecognizer(Recognizer):
        def observe(self, *args):
            result = super().observe(*args)
            evidence, _ = sample()
            unit = deepcopy(evidence['utterances'][0])
            for key in ('id', 'eligibility', 'channel', 'observation_ids'):
                unit.pop(key, None)
            result['utterances'] = [unit]
            result['speech_activity']['spans'] = [{'start': 1000, 'end': 22000}]
            return result

    class BoundaryObservers(Observers):
        def observe(self, name, prior):
            self.calls.append(name)
            return deepcopy(sample()[1][name])

    recognizer = BoundaryRecognizer()
    req, profile = setup_call(tmp_path, ffmpeg, monkeypatch, recognizer)
    monkeypatch.setattr(enrichment_models, 'RecordingObservers', BoundaryObservers)
    result = recording_engine.analyze_recording(req, profile, tmp_path/'out')
    unit = result['utterances'][0]
    assert unit['span'] == {'start': 1000, 'end': 22000}
    assert result['vocal_delivery'][0]['span'] == unit['span']
    assert result['voice_sample_candidates'] == [unit['id']]
    assert len(recognizer.calls) == 1
    Observers.calls.clear()
    assert recording_engine.analyze_recording(req, profile, tmp_path/'out') == result
    assert not Observers.calls and len(recognizer.calls) == 1
