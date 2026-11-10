from copy import deepcopy

import pytest

from wsl2_audio.recording_engine import resolve_observations
from wsl2_audio.source_clock import SourceClock
from tests.unit.test_audio_engine_recording_call import ffmpeg, verify_test_assets


def observation(window_id, start, end, text='Yay', speaker=None, context=(0, 32000)):
    return {'source_sha256': 'a' * 64, 'window_id': window_id, 'channel': 0,
            'context': {'start': context[0], 'end': context[1]},
            'utterances': [{'text': text, 'span': {'start': start, 'end': end}, 'words': [],
                            'completeness': 'unresolved', 'language': {'status': 'unresolved', 'value': None},
                            'speaker': speaker or {'status': 'unresolved', 'id': None}}]}


def test_repeated_words_at_distinct_times_are_separate_occurrences():
    rows = [observation('w0', 1000, 2000), observation('w1', 10000, 11000)]
    result = resolve_observations(rows, SourceClock(16000, 32000))
    assert len(result['utterances']) == 2
    assert len({u['id'] for u in result['utterances']}) == 2


def test_same_source_occurrence_in_shared_context_is_resolved_once_and_order_is_stable():
    rows = [observation('w0', 10000, 15000), observation('w1', 10000, 15000, context=(8000, 32000))]
    before = deepcopy(rows)
    result = resolve_observations(rows, SourceClock(16000, 32000))
    assert len(result['utterances']) == 1
    assert len(result['utterances'][0]['observation_ids']) == 2
    assert result == resolve_observations(list(reversed(rows)), SourceClock(16000, 32000))
    assert rows == before


def test_conflicting_words_are_not_overwritten_by_a_preferred_window():
    rows = [observation('w0', 10000, 15000, 'Yay Joe'), observation('w1', 10000, 15000, 'Hey Jo')]
    result = resolve_observations(rows, SourceClock(16000, 32000))
    assert {u['text'] for u in result['utterances']} == {'Yay Joe', 'Hey Jo'}
    assert all(u['resolution'] == 'conflicting_hypotheses' for u in result['utterances'])


def english_pair(left,right):
    rows=[observation('w0',10000,15000,left),observation('w1',10000,15000,right)]
    for row in rows: row['utterances'][0]['language']['configured']='en'
    return rows


@pytest.mark.parametrize('left,right',[
    ('Today is May 18th, 1988. Yay! Joe is almost 7 months old today.',
     'Today is May 18, 1988. Yay! Joe is almost seven months old today.'),
    ('There are six children.','There are 6 children!'),
    ('Come here, Joe!','Come here Joe.'),
])
def test_surface_equivalent_occurrence_keeps_one_original_text_and_both_observations(left,right):
    rows=english_pair(left,right)
    result=resolve_observations(rows,SourceClock(16000,32000))
    assert len(result['utterances'])==1
    u=result['utterances'][0]
    assert u['text'] in (left,right)
    assert u['resolution']=='matching_source_observations'
    assert set(v['text'] for v in u['text_resolution']['variants'])=={left,right}
    assert result==resolve_observations(list(reversed(rows)),SourceClock(16000,32000))


@pytest.mark.parametrize('left,right',[
    ('Joe is seven months old.','Joe is eight months old.'),('Yay Joe!','Yay Jose!'),
    ('I can go.','I cannot go.'),('Joe is almost seven.','Joe is seven.'),
    ('The 18th person.','The 18 person.'),('It is -1.5 degrees.','It is 1.5 degrees.'),
    ('One two.','12.'),('It is 1.5.','It is 15.'),('It is .5.','It is 5.'),
    ('It is 0.7.','It is 07.'),('It is ,5.','It is 5.'),('...','!!!'),
])
def test_meaningful_window_disagreements_stay_unresolved(left,right):
    result=resolve_observations(english_pair(left,right),SourceClock(16000,32000))
    assert len(result['utterances'])==2
    assert all(u['resolution']=='conflicting_hypotheses' for u in result['utterances'])


def test_english_number_rules_are_not_applied_to_unresolved_language():
    rows=[observation('w0',10000,15000,'seven'),observation('w1',10000,15000,'7')]
    assert len(resolve_observations(rows,SourceClock(16000,32000))['utterances'])==2


@pytest.mark.parametrize('texts,admitted',[
    (('Joe is seven months old.','Joe is 7 months old.'),True),
    (('It is .5 degrees.','It is 5 degrees.'),False),
])
def test_recording_caller_preserves_numeric_meaning_through_the_shared_gate(tmp_path,ffmpeg,monkeypatch,texts,admitted):
    from tests.unit.test_audio_engine_recording_call import make_request,profile,Recognizer
    from wsl2_audio import recording_engine as engine
    class SpeechRecognizer(Recognizer):
        def observe(self,*args):
            result=super().observe(*args)
            row=english_pair(*texts)[len(self.calls)-1]['utterances'][0]
            row['span']={'start':14000,'end':18000}
            row['quality']={'avg_logprob':-.2,'no_speech_probability':.01,'speech_coverage':1.}
            result['utterances']=[row]
            return result
    model=SpeechRecognizer()
    monkeypatch.setattr(engine,'load_recognizer',lambda *args:model)
    result=engine.analyze_recording(make_request(tmp_path,ffmpeg,count=32000),profile(),tmp_path/'out')
    assert len(model.calls)==2 and len(result['utterances'])==(1 if admitted else 2)
    assert all((u['eligibility']['transcript']['status']=='eligible')==admitted for u in result['utterances'])
    assert all(u['eligibility']['voice_sample']['status']!='eligible' for u in result['utterances'])


def test_equivalent_words_do_not_merge_two_possible_occurrences_in_one_window():
    rows=english_pair('Yay Joe!','Yay Joe.')
    other=deepcopy(rows[1]['utterances'][0])
    other['span']={'start':10200,'end':15200}
    rows[1]['utterances'].append(other)
    result=resolve_observations(rows,SourceClock(16000,32000))
    assert len(result['utterances'])==3
    assert all(u['resolution']=='conflicting_hypotheses' for u in result['utterances'])


def test_cross_window_speaker_disagreement_does_not_force_identity_or_purity():
    rows = [observation('w0', 10000, 15000, speaker={'status': 'single', 'id': 'w0:s0', 'purity': 'supported_single'}),
            observation('w1', 10000, 15000, speaker={'status': 'single', 'id': 'w1:s1', 'purity': 'supported_single'})]
    result = resolve_observations(rows, SourceClock(16000, 32000))
    assert len(result['utterances']) == 1
    assert result['utterances'][0]['speaker']['status'] == 'unresolved'
    assert result['overlap'][0]['status'] == 'unresolved'


def test_same_text_on_different_channels_is_not_assumed_to_be_one_voice():
    rows = [observation('w0:c0', 10000, 15000), observation('w0:c1', 10000, 15000)]
    rows[1]['channel'] = 1
    result = resolve_observations(rows, SourceClock(16000, 32000))
    assert len(result['utterances']) == 2
    assert result['overlap'][0]['status'] == 'unresolved'


@pytest.mark.parametrize('case', ['different_source', 'outside_context', 'duplicate_window'])
def test_invalid_window_provenance_is_not_repaired(case):
    rows = [observation('w0', 1000, 2000), observation('w1', 10000, 15000)]
    if case == 'different_source':
        rows[1]['source_sha256'] = 'b' * 64
    elif case == 'outside_context':
        rows[1]['context'] = {'start': 12000, 'end': 32000}
    else:
        rows[1]['window_id'] = 'w0'
    with pytest.raises(ValueError):
        resolve_observations(rows, SourceClock(16000, 32000))
