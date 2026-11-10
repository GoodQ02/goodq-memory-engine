"""Missing phrase-edge timing must not make its remaining words voice evidence."""
import copy
from types import SimpleNamespace

import pytest

from wsl2_audio import acoustic_events as audio


def evidence():
    words = [{'start': .2, 'end': .7, 'text': "Don't", 'probability': .95},
             {'start': .7, 'end': 1.2, 'text': 'forget', 'probability': .95},
             {'start': 1.2, 'end': 1.7, 'text': 'a', 'probability': .95},
             {'start': 1.7, 'end': 2.2, 'text': 'jacket.', 'probability': .95}]
    return {'segments': [{'words': words}], 'word_timestamps': words,
            'diarization_status': 'success', 'diarization': [
                {'start': 0, 'end': 1.2, 'speaker': 'A'},
                {'start': 1.2, 'end': 2.5, 'speaker': 'B'}]}


@pytest.mark.parametrize('edge', ['first', 'last', 'both'])
@pytest.mark.parametrize('timing', [None, -1, float('nan')])
def test_unresolved_phrase_edges_cannot_release_mixed_speech_fragments(monkeypatch, edge, timing):
    raw = evidence()
    if edge in ('first', 'both'):
        raw['word_timestamps'][0]['start'] = timing
    if edge in ('last', 'both'):
        raw['word_timestamps'][-1]['end'] = timing
    before = copy.deepcopy(raw)
    seen = {}

    def detect(*args, speech_intervals, emotion_phrases, **kwargs):
        seen.update(voice=speech_intervals, emotion=emotion_phrases)
        return [{'label': 'crying', 'start': 2.6, 'end': 3.}], {
            'speech_presence': {'status': 'success', 'regions': []}}

    monkeypatch.setattr(audio, 'detect_sound_events', detect)
    result = audio.prepare_inputs(SimpleNamespace(shape=(1, 48000)), 16000, raw,
                                  cache_dir=None, device='cpu')
    assert seen == {'voice': [], 'emotion': []}
    assert result['emotion_input']['selected'] == []
    assert result['emotion_input']['phrase_selection']['selected'] == []
    assert result['sound_events'][0]['label'] == 'crying'
    assert raw == before


def test_missing_edge_withholds_a_fragment_even_if_remaining_words_have_one_label():
    raw = evidence()
    raw['word_timestamps'][0]['start'] = None
    raw['diarization'] = [{'start': 0, 'end': .7, 'speaker': 'A'},
                          {'start': .7, 'end': 3., 'speaker': 'B'}]
    selected, rejected = audio.select_speech_intervals(raw, [
        {'start': 0, 'end': 3, 'speech_score': 1., 'excluded_labels': []}], 3)
    assert not selected
    assert any(r['reason'] == 'phrase_boundary_timing_unavailable' for r in rejected)


def test_unresolved_phrase_does_not_exclude_a_separate_complete_phrase():
    raw = evidence()
    raw['word_timestamps'][0]['start'] = None
    clear = [{'text': 'Hello.', 'start': 2.6, 'end': 3.3, 'probability': .95}]
    raw['segments'].append({'words': clear})
    raw['word_timestamps'] = raw['word_timestamps'] + clear
    raw['diarization'].append({'start': 2.5, 'end': 3.5, 'speaker': 'B'})
    selected, _ = audio.select_speech_intervals(raw, [
        {'start': 0, 'end': 4, 'speech_score': 1., 'excluded_labels': []}], 4)
    assert [(s['start'], s['end'], s['speaker']) for s in selected] == [(2.6, 3.3, 'B')]


def test_incomplete_exclusion_does_not_claim_recovered_phrase_boundaries():
    raw = evidence()
    raw['word_timestamps'][0]['start'] = None
    row = audio.speaker_purity_exclusions(raw, 3)[0]
    assert row['boundary_status'] == 'unresolved'
    assert row['exclusion_scope'] == 'observed_word_audio_only'
    assert (row['start'], row['end']) == (.7, 2.2)
    assert raw['word_timestamps'][0]['start'] is None
