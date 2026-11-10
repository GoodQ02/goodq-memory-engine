from copy import deepcopy

import pytest

from tests.unit.test_audio_engine_enrichment import inputs
from wsl2_audio.enrichment import attach_observations
from wsl2_audio.eligibility import select_inputs
from wsl2_audio.evidence_contract import validate_evidence


def block():
    evidence, observations = inputs()
    u = evidence['utterances'][0]
    u.update(text='Wait here. Is this clear? Next part.', span={'start': 1000, 'end': 23000})
    u['words'] = [dict(text=text, span={'start': a, 'end': b}, timing='supported')
                  if a is not None else dict(text=text, span=None, timing='unavailable', reason='invalid_word_alignment')
                  for text, a, b in [('Wait', 2000, 2500), ('here.', 2500, 4000),
                                     ('Is', 5000, 6000), ('this', 6000, 7000), ('clear?', None, None),
                                     ('Next', 16000, 18000), ('part.', 18000, 21000)]]
    evidence['window_observations'] = [{'channel': 0, 'speech_activity': {'status': 'ok',
        'spans': [{'start': 1000, 'end': 24000}]}}]
    observations['phrase_activity']['regions'] = [{'span': {'start': a, 'end': b}, 'channel': 0}
        for a, b in [(1800, 4000), (5500, 12000), (17000, 24000)]]
    observations['speaker_activity']['tracks'] = [
        {'span': {'start': 1500, 'end': 12000}, 'channel': 0, 'speaker': 's0'},
        {'span': {'start': 15000, 'end': 23000}, 'channel': 0, 'speaker': 's1'}]
    observations['overlap']['single_activity'] = [{'span': {'start': 1000, 'end': 24000}, 'channel': 0}]
    return evidence, observations


def resolved(evidence, observations):
    from wsl2_audio.phrase_resolution import resolve_phrases
    result = resolve_phrases(evidence, observations)
    return attach_observations(result, observations)


def test_independent_complete_question_keeps_untimed_ending_and_neighboring_text():
    evidence, observations = block()
    before = deepcopy(evidence)
    result = resolved(evidence, observations)
    assert [u['text'] for u in result['utterances']] == ['Wait here.', 'Is this clear?', 'Next part.']
    question = result['utterances'][1]
    assert question['span'] == {'start': 4500, 'end': 14000}
    assert question['words'][-1]['span'] is None
    assert question['completeness'] == 'complete'
    assert question in select_inputs(result, 'vocal_delivery')
    assert result['utterances'][-1]['completeness'] == 'unresolved'
    assert [w for u in result['utterances'] for w in u['words']] == before['utterances'][0]['words']
    assert evidence == before


@pytest.mark.parametrize('reason', ['no_pause', 'missing_observer', 'text_mismatch', 'unanchored_phrase',
                                  'conflicting_hypotheses', 'another_channel', 'unassessed_gap'])
def test_no_sentence_slicing_without_all_text_and_independent_gap_support(reason):
    from wsl2_audio.phrase_resolution import resolve_phrases
    evidence, observations = block()
    u = evidence['utterances'][0]
    if reason == 'no_pause':
        observations['phrase_activity']['regions'] = [{'span': {'start': 1800, 'end': 24000}, 'channel': 0}]
    elif reason == 'missing_observer':
        observations['phrase_activity']['status'] = 'unavailable'
    elif reason == 'text_mismatch':
        u['text'] = 'Extra word. '+u['text']
    elif reason == 'unanchored_phrase':
        for word in u['words'][2:5]:
            word.update(span=None, timing='unavailable', reason='invalid_word_alignment')
    elif reason == 'conflicting_hypotheses':
        u['resolution'] = 'conflicting_hypotheses'
    elif reason == 'another_channel':
        for row in observations['phrase_activity']['regions']:
            row['channel'] = 1
    else:
        observations['phrase_activity']['channel_assessed_spans']['0'] = [{'start': 16000, 'end': 32000}]
    result = resolve_phrases(evidence, observations)
    assert result['utterances'] == evidence['utterances']


def test_child_recalculates_coverage_instead_of_inheriting_whole_block_score():
    evidence, observations = block()
    evidence['window_observations'][0]['speech_activity']['spans'] = [{'start': 1000, 'end': 4500}]
    result = resolved(evidence, observations)
    assert result['utterances'][1]['quality']['speech_coverage'] == 0
    assert result['utterances'][1] not in select_inputs(result, 'vocal_delivery')


def test_overlapping_or_contextually_contaminated_complete_question_is_still_withheld():
    evidence, observations = block()
    observations['overlap']['intervals'] = [{'span': {'start': 6500, 'end': 7000}, 'status': 'observed'}]
    observations['acoustic_events']['events'] = [{'id': 'wide-laugh', 'label': 'laughter', 'status': 'observed',
        'span': {'start': 0, 'end': 20000}, 'channel': 0, 'scope': 'recording_window',
        'boundary_precision': 'analysis_window'}]
    result = resolved(evidence, observations)
    question = result['utterances'][1]
    assert question['completeness'] == 'complete'
    assert question not in select_inputs(result, 'vocal_delivery')
    assert question not in select_inputs(result, 'voice_sample')
    assert 'overlap_observed' in question['eligibility']['vocal_delivery']['reasons']
    assert 'sound_event_context_laughter_unresolved' in question['eligibility']['vocal_delivery']['reasons']


@pytest.mark.parametrize('tamper', ['drop_child', 'change_word', 'change_text', 'move_seam', 'invent_boundary'])
def test_persisted_phrase_partition_cannot_lose_text_or_invent_boundaries(tamper):
    evidence, observations = block()
    result = resolved(evidence, observations)
    if tamper == 'drop_child':
        result['utterances'].pop()
    elif tamper == 'change_word':
        result['utterances'][1]['words'][-1]['text'] = 'different?'
    elif tamper == 'change_text':
        result['utterances'][1]['text'] = 'Different words?'
    elif tamper == 'move_seam':
        result['utterances'][1]['span']['start'] += 1
    else:
        result['phrase_resolution']['parents'][0]['seams'][0]['sample'] += 1
    with pytest.raises(ValueError, match='[Pp]hrase'):
        validate_evidence(result)
