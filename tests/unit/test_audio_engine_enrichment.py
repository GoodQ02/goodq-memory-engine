from copy import deepcopy

import pytest

from tests.unit.test_audio_engine_eligibility import candidate
from wsl2_audio.eligibility import assess_eligibility, POLICY, select_inputs
from wsl2_audio.enrichment import attach_observations, select_voice_groups
from wsl2_audio.evidence_contract import validate_evidence


def inputs():
    evidence, utterance = candidate()
    evidence['source']['channels'] = 1
    utterance.update(channel=0, completeness='unresolved',
                     speaker={'status': 'unresolved', 'id': None})
    utterance['boundary_evidence'] = {'status': 'unresolved'}
    utterance['eligibility'] = assess_eligibility(utterance, evidence, POLICY)
    span = {'start': 2000, 'end': 18000}
    full = {'start': 0, 'end': 32000}
    observations = {}
    for stage in ('speaker_activity', 'overlap', 'acoustic_events', 'phrase_activity'):
        observations[stage] = {'status': 'ok', 'model_id': 'fixture-model',
                               'assessed_spans': [full], 'channel_assessed_spans': {'0': [full]}}
    observations['speaker_activity']['tracks'] = [{'span': span, 'channel': 0, 'speaker': 'speaker0'}]
    observations['speaker_activity']['flags'] = []
    observations['overlap'].update(intervals=[], single_activity=[{'span': span, 'channel': 0}])
    observations['phrase_activity']['regions'] = [{'span': span, 'channel': 0}]
    observations['acoustic_events'].update(events=[], method='efficientsed_frames_v1', threshold=.5,
        speech_intervals=[{'span': deepcopy(span), 'channel': 0}])
    return evidence, observations


def test_complete_clear_speech_is_admitted_with_unavailable_word_time_and_unchanged_text():
    evidence, observations = inputs()
    before = deepcopy(evidence)
    result = attach_observations(evidence, observations)
    utterance = result['utterances'][0]
    assert utterance['completeness'] == 'complete'
    assert utterance['words'] == before['utterances'][0]['words']
    assert utterance['span'] == before['utterances'][0]['span']
    assert utterance['speaker']['purity'] == 'supported_single'
    assert select_inputs(result, 'vocal_delivery') == [utterance]
    assert select_inputs(result, 'voice_sample') == [utterance]
    assert evidence == before


@pytest.mark.parametrize('mode', ['nemotron_overlap', 'two_speakers', 'collapsed_return', 'crying', 'singing', 'laughter'])
def test_mixture_or_vocal_event_cannot_enter_individual_models(mode):
    evidence, observations = inputs()
    span = {'start': 5000, 'end': 12000}
    if mode == 'nemotron_overlap':
        observations['overlap']['intervals'] = [{'span': span, 'channel': 0, 'status': 'observed'}]
    elif mode == 'two_speakers':
        observations['speaker_activity']['tracks'].append({'span': span, 'channel': 0, 'speaker': 'speaker1'})
    elif mode == 'collapsed_return':
        observations['speaker_activity']['flags'] = [{'span': span, 'channel': 0}]
    else:
        observations['acoustic_events']['events'] = [{'id': 'event1', 'span': span,
            'label': mode, 'channel': 0, 'status': 'observed', 'boundary_precision': 'analysis_window'}]
    result = attach_observations(evidence, observations)
    assert result['utterances'][0]['text'] == 'Yay Joe'
    assert select_inputs(result, 'vocal_delivery') == []
    assert select_inputs(result, 'voice_sample') == []


@pytest.mark.parametrize('mode', ['vad_outside', 'speaker_outside', 'source_edge', 'no_positive_second_detector',
                                  'missing_acoustic', 'non_speech', 'wrong_activity_channel'])
def test_uncertain_edges_and_missing_or_disagreeing_evidence_do_not_release_surviving_fragment(mode):
    evidence, observations = inputs()
    if mode == 'vad_outside':
        observations['phrase_activity']['regions'][0]['span']['end'] = 25000
    elif mode == 'speaker_outside':
        observations['speaker_activity']['tracks'][0]['span']['start'] = 0
    elif mode == 'source_edge':
        evidence['utterances'][0]['span']['start'] = 0
        observations['phrase_activity']['regions'][0]['span']['start'] = 0
    elif mode == 'no_positive_second_detector':
        observations['overlap']['single_activity'] = []
    elif mode == 'missing_acoustic':
        observations['acoustic_events'] = {'status': 'unavailable', 'reason': 'injected_missing_model'}
    elif mode == 'non_speech':
        observations['acoustic_events']['speech_intervals'] = []
    else:
        observations['acoustic_events']['speech_intervals'][0]['channel'] = 1
    original = deepcopy(evidence['utterances'][0])
    result = attach_observations(evidence, observations)
    assert not select_inputs(result, 'vocal_delivery')
    assert result['utterances'][0]['span'] == original['span']
    assert result['utterances'][0]['words'] == original['words']


def test_independent_crying_event_survives_recognition_failure():
    evidence, observations = inputs()
    evidence['utterances'] = []
    evidence['coverage'][0]['status'] = 'error'
    evidence['stages']['recognition'] = {'status': 'error', 'reason': 'recognizer_failed'}
    observations['acoustic_events']['events'] = [{'id': 'cry', 'label': 'crying', 'status': 'observed',
        'span': {'start': 1000, 'end': 20000}, 'channel': 0}]
    result = attach_observations(evidence, observations)
    assert validate_evidence(result)['sound_events'][0]['label'] == 'crying'
    assert result['stages']['recognition']['status'] == 'error'


def test_missing_sound_assessment_cannot_certify_an_observed_event():
    evidence, observations = inputs()
    result = attach_observations(evidence, observations)
    result['sound_events'] = [{'id': 'fake', 'label': 'crying', 'status': 'observed',
                              'span': {'start': 21000, 'end': 25000}, 'channel': 0}]
    result['stages']['acoustic_events'] = {'status': 'unavailable', 'reason': 'missing'}
    with pytest.raises(ValueError):
        validate_evidence(result)


def test_voice_selection_respects_scene_ownership_diversity_and_full_utterances():
    evidence, observations = inputs()
    result = attach_observations(evidence, observations)
    # Positive source-bound utterances in two different owning scenes must not pool.
    result['source']['sample_count'] = 160000
    for row in result['coverage']:
        row['span']['end'] = 160000
    for stage in result['stages'].values():
        if stage.get('status') == 'ok':
            stage['assessed_spans'] = [{'start': 0, 'end': 160000}]
            stage.pop('channel_assessed_spans', None)
    original = deepcopy(result['utterances'][0])
    result['utterances'] = []
    for i in range(3):
        u = deepcopy(original)
        u.update(id='u'+str(i), span={'start': i*48000, 'end': i*48000+32000}, words=[])
        u['boundary_evidence']['regions'] = [{'span': deepcopy(u['span']), 'channel': 0}]
        result['utterances'].append(u)
    owners = {'u0': 'scene-A', 'u1': 'scene-B', 'u2': 'scene-A'}
    selected = select_voice_groups(result, owners)
    assert len(selected) == 1
    assert selected[0]['scene_id'] == 'scene-A'
    assert selected[0]['utterance_ids'] == ['u0', 'u2']
    assert selected[0]['source_samples'] == 64000
    assert select_voice_groups(result, {}) == []


def test_long_silent_phrase_margins_do_not_satisfy_voiced_signature_minimum():
    evidence, observations = inputs()
    result = attach_observations(evidence, observations)
    result['source']['sample_count'] = 160000
    result['coverage'][0]['span']['end'] = 160000
    for stage in result['stages'].values():
        if stage.get('status') == 'ok':
            stage['assessed_spans'] = [{'start': 0, 'end': 160000}]
            stage.pop('channel_assessed_spans', None)
    first = result['utterances'][0]
    first.update(span={'start': 0, 'end': 70000}, words=[])
    second = deepcopy(first)
    second.update(id='u2', span={'start': 80000, 'end': 150000})
    second['boundary_evidence']['regions'] = [{'span': {'start': 82000, 'end': 98000}, 'channel': 0}]
    result['utterances'].append(second)
    assert select_voice_groups(result, {'u1': 'scene', 'u2': 'scene'}) == []
