from copy import deepcopy

import pytest

from tests.unit.test_audio_engine_evidence import evidence
from wsl2_audio.eligibility import POLICY, assess_eligibility, select_inputs


def candidate():
    result = evidence()
    result['eligibility_policy'] = deepcopy(POLICY)
    result['stages']['speech_activity'] = {'status': 'ok', 'model_id': 'fixture-model'}
    utterance = result['utterances'][0]
    utterance['quality'] = {'avg_logprob': -.2, 'no_speech_probability': .05, 'speech_coverage': .95}
    utterance['boundary_evidence'] = {'status': 'supported', 'method': 'independent_boundary_control'}
    utterance['speaker']['purity'] = 'supported_single'
    return result, utterance


def apply(result, utterance):
    utterance['eligibility'] = assess_eligibility(utterance, result, POLICY)
    return utterance['eligibility']


def test_complete_clear_phrase_does_not_require_individual_word_times():
    result, utterance = candidate()
    utterance['words'] = [{'text': 'Yay Joe', 'span': None, 'timing': 'unavailable', 'reason': 'alignment_failed'}]
    before = deepcopy(utterance)
    actual = assess_eligibility(utterance, result, POLICY)
    assert all(decision['status'] == 'eligible' for decision in actual.values())
    assert utterance == before


@pytest.mark.parametrize('case', ['overlap', 'crying', 'cheering', 'mixed_label', 'unresolved_overlap', 'group_cheer'])
def test_known_mixtures_cannot_reach_either_individual_consumer(case):
    result, utterance = candidate()
    if case in ('overlap', 'unresolved_overlap'):
        result['overlap'] = [{'span': {'start': 8000, 'end': 12000},
                              'status': 'observed' if case == 'overlap' else 'unresolved'}]
    elif case in ('crying', 'cheering'):
        result['sound_events'] = [{'id': 'event', 'label': case, 'status': 'observed',
                                   'span': {'start': 8000, 'end': 12000}}]
    elif case == 'mixed_label':
        utterance['speaker']['status'] = 'mixed'
    else:
        utterance['kind'] = 'group_cheer'
    decisions = apply(result, utterance)
    assert decisions['transcript']['status'] == 'eligible'
    assert select_inputs(result, 'vocal_delivery') == []
    assert select_inputs(result, 'voice_sample') == []
    assert utterance['text'] == 'Yay Joe'


@pytest.mark.parametrize('case', ['missing_overlap', 'single_label_only', 'punctuation_only', 'fragment', 'low_speech_support'])
def test_uncertainty_remains_explicit_and_cannot_certify_a_single_voice(case):
    result, utterance = candidate()
    if case == 'missing_overlap':
        result['stages']['overlap'] = {'status': 'unavailable', 'reason': 'not_installed'}
    elif case == 'single_label_only':
        del utterance['speaker']['purity']
    elif case == 'punctuation_only':
        utterance['text'] = 'Yay Joe!'
        del utterance['boundary_evidence']
    elif case == 'fragment':
        utterance['completeness'] = 'incomplete'
    else:
        utterance['quality']['speech_coverage'] = .2
    decisions = apply(result, utterance)
    for purpose in ('vocal_delivery', 'voice_sample'):
        assert decisions[purpose]['status'] != 'eligible'
        assert decisions[purpose]['reasons']


def test_loudness_and_missing_emotion_model_do_not_reject_clear_speech():
    result, utterance = candidate()
    utterance['loudness'] = 1.0
    result['stages']['emotion'] = {'status': 'unavailable', 'reason': 'model_not_selected'}
    assert apply(result, utterance)['vocal_delivery']['status'] == 'eligible'


def test_later_detector_failure_does_not_discard_earlier_assessed_phrase():
    result, utterance = candidate()
    result['stages']['overlap'] = {'status': 'partial', 'reason': 'later_window_failed',
                                   'model_id': 'fixture-model',
                                   'assessed_spans': [{'start': 0, 'end': 20000}]}
    assert apply(result, utterance)['voice_sample']['status'] == 'eligible'
    result['stages']['overlap']['assessed_spans'][0]['end'] = 19999
    assert apply(result, utterance)['voice_sample']['status'] == 'unresolved'


def test_digital_silence_cannot_become_transcript_or_individual_input():
    result, utterance = candidate()
    result['coverage'][0]['status'] = 'digital_silence'
    decisions = apply(result, utterance)
    assert all(item['status'] == 'ineligible' for item in decisions.values())


def test_conflicting_hypotheses_are_retained_but_not_treated_as_a_confirmed_transcript():
    result, utterance = candidate()
    utterance['resolution'] = 'conflicting_hypotheses'
    assert apply(result, utterance)['transcript']['status'] == 'unresolved'


def test_a_forged_eligibility_result_is_rejected_at_publication_and_selection():
    from wsl2_audio.evidence_contract import validate_evidence

    result, utterance = candidate()
    del utterance['speaker']['purity']
    with pytest.raises(ValueError, match='eligibility'):
        validate_evidence(result)
    with pytest.raises(ValueError, match='eligibility'):
        select_inputs(result, 'voice_sample')


def test_unknown_policy_does_not_silently_use_new_defaults():
    result, utterance = candidate()
    with pytest.raises(ValueError, match='policy'):
        assess_eligibility(utterance, result, {'id': 'unknown'})
