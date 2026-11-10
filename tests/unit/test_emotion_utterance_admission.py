"""Decoder blocks must not determine the unit of individual emotion scoring."""
import copy
from types import SimpleNamespace

import pytest

from wsl2_audio import acoustic_events as audio


def evidence():
    words = [
        {'text': 'Hello!', 'start': 1., 'end': 2., 'probability': .99},
        {'text': 'How', 'start': 3., 'end': 3.4, 'probability': .99},
        {'text': 'are', 'start': 3.4, 'end': 3.7, 'probability': .99},
        {'text': 'you?', 'start': None, 'end': None, 'probability': .99},
        {'text': 'Welcome', 'start': 5., 'end': 5.5, 'probability': .99},
        {'text': 'home.', 'start': 5.5, 'end': 6., 'probability': .99},
    ]
    text = 'Hello! How are you? Welcome home.'
    native = {'start': .8, 'end': 6.2, 'text': text, 'status': 'model_estimated',
              'method': 'whisper_native_timestamp_tokens_v1',
              'boundary_status': 'model_estimated_complete_phrase',
              'independent_of_word_alignment': True}
    return {'segments': [{'text': text, 'words': words, 'phrase_timing': native}],
            'word_timestamps': words, 'diarization_status': 'success',
            'diarization': [{'start': .8, 'end': 2.2, 'speaker': 'A'},
                            {'start': 2.8, 'end': 4.2, 'speaker': 'B'},
                            {'start': 4.8, 'end': 6.2, 'speaker': 'A'}],
            'overlap_detection': {'status': 'ok', 'intervals': []},
            'additional_overlap_detection': {'status': 'ok', 'intervals': []}}


def test_decoder_block_withholds_only_the_utterance_with_missing_word_timing():
    raw = evidence()
    before = copy.deepcopy(raw)
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert [(r['text'], r['start'], r['end'], r['speaker']) for r in candidates] == [
        ('Hello!', 1., 2., 'A'), ('Welcome home.', 5., 6., 'A')]
    assert [(r['text'], r['reason']) for r in rejected] == [
        ('How are you?', 'phrase_word_timing_unavailable')]
    for row in candidates + rejected:
        assert row['timing_basis'] == 'complete_word_alignment'
        assert row['native_boundary_evidence'] == raw['segments'][0]['phrase_timing']
        assert 'boundary_evidence' not in row  # Parent bounds never become child bounds.
    assert raw == before


@pytest.mark.parametrize('key', ['overlap_detection', 'additional_overlap_detection'])
def test_a_mixed_utterance_is_not_chopped_into_accepted_words(key):
    raw = evidence()
    raw[key]['intervals'] = [{'start': 5.6, 'end': 5.8}]
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert [r['text'] for r in candidates] == ['Hello!']
    mixed = next(r for r in rejected if r['text'] == 'Welcome home.')
    assert 'overlap' in mixed['reason'] and mixed['start'] == 5. and mixed['end'] == 6.


@pytest.mark.parametrize('fault', ['missing_word', 'changed_text', 'empty_words'])
def test_subutterances_require_the_complete_matching_word_sequence(fault):
    raw = evidence()
    if fault == 'missing_word': raw['segments'][0]['words'] = raw['word_timestamps'][:-1]
    if fault == 'changed_text': raw['word_timestamps'][-1]['text'] = 'away.'
    if fault == 'empty_words': raw['segments'][0]['words'] = []
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert not candidates and rejected[0]['reason'] == 'phrase_word_evidence_mismatch'


def test_subutterance_bounds_cannot_escape_the_native_envelope():
    raw = evidence()
    raw['word_timestamps'][0]['start'] = .5
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert [r['text'] for r in candidates] == ['Welcome home.']
    assert next(r for r in rejected if r['text'] == 'Hello!')['reason'] == 'phrase_word_bounds_outside_native_envelope'


def test_two_utterances_cannot_claim_the_same_word_audio():
    raw = evidence()
    raw['word_timestamps'][0]['end'] = 3.1
    raw['word_timestamps'][3].update(start=3.7, end=4.)
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert [r['text'] for r in candidates] == ['Welcome home.']
    assert all(r['reason'] == 'utterance_word_timing_conflict' for r in rejected)


def test_disjoint_utterances_cannot_reverse_the_transcript_clock():
    raw = evidence()
    raw['word_timestamps'][0].update(start=5., end=6.)
    raw['word_timestamps'][4].update(start=1., end=1.5)
    raw['word_timestamps'][5].update(start=1.5, end=2.)
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert not candidates
    assert {r['reason'] for r in rejected} == {'utterance_word_timing_conflict', 'phrase_word_timing_unavailable'}


def test_utterance_selection_precedes_acoustic_admission_and_keeps_voice_gate(monkeypatch):
    raw = evidence()
    original_voice, _ = audio.select_speech_intervals(raw,
        [{'start': 0., 'end': 7., 'speech_score': 1., 'excluded_labels': []}], 7.)
    captured = []
    def detect(*args, speech_intervals, emotion_phrases, **kwargs):
        captured.extend(emotion_phrases)
        window = lambda r: {**r, 'speech_score': .95, 'vad_speech_coverage': 1., 'excluded_labels': []}
        return [], {'speech_presence': {'status': 'success', 'regions': [
            {'start': 1., 'end': 2.}, {'start': 5., 'end': 6.}]},
            'speech_windows': [window(r) for r in speech_intervals],
            'phrase_windows': [{**window(r), 'excluded_labels': ['crying'] if r['start'] == 5. else []}
                               for r in emotion_phrases]}
    monkeypatch.setattr(audio, 'detect_sound_events', detect)
    result = audio.prepare_inputs(SimpleNamespace(shape=(1, 112000)), 16000, raw, cache_dir=None, device='cpu')
    assert [r['text'] for r in captured] == ['Hello!', 'Welcome home.']
    assert [r['text'] for r in result['emotion_input']['phrase_selection']['selected']] == ['Hello!']
    assert [(r['start'], r['end']) for r in result['emotion_input']['selected']] == [
        (r['start'], r['end']) for r in original_voice]


def test_native_text_contradiction_still_blocks_every_utterance():
    raw = evidence()
    raw['segments'][0]['phrase_timing']['text'] = 'Unrelated.'
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert not candidates and rejected[0]['reason'] == 'phrase_text_evidence_mismatch'


@pytest.mark.parametrize('text', [
    'Please call Dr. Smith.', 'The U.S. is large.', 'I... I am scared.',
    'Please ask Prof. Smith.', 'J. Smith is here.', 'It is approx. noon.',
    'Please call "Dr." Smith.', 'Please call \u201cDr.\u201d Smith.',
    'It is Jan. 1.', 'Please ask Gov. Smith.', 'I have an appt. tomorrow.',
])
def test_ambiguous_punctuation_cannot_release_a_prefix_of_a_mixed_sentence(text):
    words = [{'text': word, 'start': 1. + i * .5, 'end': 1.5 + i * .5, 'probability': .99}
             for i, word in enumerate(text.split())]
    end = words[-1]['end']
    raw = evidence()
    raw['segments'][0].update(text=text, words=words)
    raw['segments'][0]['phrase_timing'].update(text=text, start=.8, end=end + .2)
    raw['word_timestamps'] = words
    raw['diarization'] = [{'start': 0., 'end': end + .3, 'speaker': 'A'}]
    raw['overlap_detection']['intervals'] = [{'start': end - .2, 'end': end - .1}]
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert not candidates
    assert len(rejected) == 1 and rejected[0]['text'] == text
    assert rejected[0]['reason'] == 'local_overlap_in_phrase'
    assert rejected[0]['timing_basis'] == 'native_decoder_envelope'


def test_periods_stay_inside_a_complete_unit_until_a_stronger_boundary():
    raw = evidence()
    raw['word_timestamps'][0]['text'] = 'Hello.'
    text = 'Hello. How are you? Welcome home.'
    raw['segments'][0]['text'] = raw['segments'][0]['phrase_timing']['text'] = text
    candidates, rejected = audio.emotion_phrase_candidates(raw, 7.)
    assert [r['text'] for r in candidates] == ['Welcome home.']
    assert [(r['text'], r['reason']) for r in rejected] == [
        ('Hello. How are you?', 'phrase_word_timing_unavailable')]
