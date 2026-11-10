import copy
from types import SimpleNamespace

import pytest

from wsl2_audio import acoustic_events as audio


def evidence():
    words = [{'text': 'Please', 'start': .2, 'end': .6, 'probability': .95},
             {'text': 'come', 'start': .6, 'end': .9, 'probability': .4},
             {'text': 'here.', 'start': .9, 'end': 1.5, 'probability': .96}]
    return {'word_timestamps': words, 'segments': [{'start': .2, 'end': 1.5,
        'text': 'Please come here.', 'words': words}], 'diarization_status': 'success',
        'diarization': [{'start': 0, 'end': 2, 'speaker': 'A'}]}


def metadata(regions=None, excluded=None):
    return {'speech_presence': {'status': 'success', 'regions': regions if regions is not None else [{'start': .2, 'end': 1.5}]},
            'phrase_windows': [{'start': .2, 'end': 1.5, 'speech_score': .9,
                                'vad_speech_coverage': 1., 'excluded_labels': excluded or []}]}


def test_low_confidence_internal_word_never_creates_a_fragment():
    raw = evidence()
    before = copy.deepcopy(raw)
    old, _ = audio.select_speech_intervals(raw, [{'start': 0, 'end': 2, 'speech_score': .9, 'excluded_labels': []}], 2)
    assert [(s['start'], s['end']) for s in old] == [(.2, .6), (.9, 1.5)]
    phrases, rejected = audio.emotion_phrase_candidates(raw, 2)
    selected = audio.select_complete_emotion_phrases(phrases, rejected, metadata(), raw, 2)['selected']
    assert [(s['start'], s['end'], s['text']) for s in selected] == [(.2, 1.5, 'Please come here.')]
    assert selected[0]['uncertain_transcript_words'] == ['come']
    assert raw == before


@pytest.mark.parametrize('change,reason', [
    ('overlap', 'phrase_speakers_unresolved'),
    ('missing_boundary', 'phrase_word_timing_unavailable'),
    ('stale_words', 'phrase_word_evidence_mismatch'),
    ('long', 'phrase_duration_outside_limits'),
    ('coarse_overlap', 'overlapping_phrase_timing_unresolved'),
])
def test_incomplete_or_unresolved_phrase_is_withheld_whole(change, reason):
    raw = evidence()
    if change == 'overlap': raw['diarization'].append({'start': .65, 'end': .8, 'speaker': 'B'})
    if change == 'missing_boundary': raw['word_timestamps'][0]['start'] = None
    if change == 'stale_words': raw['word_timestamps'] = raw['word_timestamps'][1:]
    if change == 'long':
        raw['word_timestamps'][-1]['end'] = 8
        raw['diarization'][0]['end'] = 9
    if change == 'coarse_overlap':
        raw['diarization_timing'] = {'boundary_precision':'phrase'}
        raw['diarization'].append({'start': 1.6, 'end': 2, 'speaker':'B'})
    candidates, rejected = audio.emotion_phrase_candidates(raw, 10)
    assert not candidates and rejected[0]['reason'] == reason


def test_weak_recognition_at_phrase_edges_does_not_claim_broken_alignment():
    raw = evidence()
    raw['word_timestamps'][0]['probability'] = .01
    raw['word_timestamps'][-1]['probability'] = .3
    original = copy.deepcopy(raw)
    candidates, rejected = audio.emotion_phrase_candidates(raw, 2)
    result = audio.select_complete_emotion_phrases(candidates, rejected, metadata(), raw, 2)
    phrase = result['selected'][0]
    assert (phrase['start'], phrase['end'], phrase['text']) == (.2, 1.5, 'Please come here.')
    assert phrase['uncertain_transcript_words'] == ['Please', 'come', 'here.']
    assert 'transcript_words_uncertain' in audio.emotion_uncertainty(phrase)['uncertainty_reasons']
    assert raw == original


def test_weak_edge_recognition_does_not_hide_the_independent_overlap_blocker():
    raw = evidence()
    raw['word_timestamps'][0]['probability'] = .01
    raw['diarization'].append({'start': 0., 'end': .7, 'speaker': 'B'})
    candidates, rejected = audio.emotion_phrase_candidates(raw, 2)
    assert not candidates
    phrase = rejected[0]
    assert phrase['reason'] == 'phrase_speakers_unresolved'
    assert phrase['uncertain_transcript_words'] == ['Please', 'come']
    assert phrase['speaker_candidates'] == ['A','B']
    assert phrase['overlap_intervals'] == [{'start':.2,'end':.7,'speakers':['A','B'],'review_status':'unreviewed'}]
    assert (phrase['start'],phrase['end']) == (.2,1.5)


def test_speaker_onset_does_not_cut_a_word_but_unknown_voiced_audio_stays_blocked():
    raw = evidence()
    raw['diarization'][0]['start'] = .5
    candidates, rejected = audio.emotion_phrase_candidates(raw, 2)
    # A leading region without detected speech can remain; no timestamp is rewritten.
    selected = audio.select_complete_emotion_phrases(candidates, rejected,
        metadata(regions=[{'start': .5, 'end': 1.5}]), raw, 2)['selected']
    assert selected[0]['start'] == .2
    result = audio.select_complete_emotion_phrases(candidates, rejected, metadata(), raw, 2)
    assert not result['selected'] and result['rejected'][0]['reason'] == 'phrase_speaker_boundary_unresolved'


@pytest.mark.parametrize('excluded', [['crying'], ['screaming'], ['laughter'], ['music']])
def test_whole_phrase_acoustic_exclusions_stay_effective(excluded):
    raw = evidence()
    candidates, rejected = audio.emotion_phrase_candidates(raw, 2)
    result = audio.select_complete_emotion_phrases(candidates, rejected, metadata(excluded=excluded), raw, 2)
    assert not result['selected']
    assert result['rejected'][0]['reason'] == 'phrase_acoustics_uncertain_or_non_speech'


def test_missing_phrase_evidence_never_falls_back_to_scoring_word_runs():
    raw = evidence()
    del raw['segments']
    candidates, rejected = audio.emotion_phrase_candidates(raw, 2)
    assert not candidates and rejected == [{'reason': 'phrase_boundaries_unavailable'}]


def test_prepare_inputs_keeps_voice_selection_and_emotion_phrase_selection_distinct(monkeypatch):
    raw = evidence()
    captured = []
    def detect(*args, speech_intervals, emotion_phrases, **kwargs):
        captured.extend(emotion_phrases)
        meta = metadata()
        meta['speech_windows'] = [{**s, 'speech_score': .9, 'vad_speech_coverage': 1., 'excluded_labels': []} for s in speech_intervals]
        return [{'label':'crying','start':1.6,'end':2}], meta
    monkeypatch.setattr(audio, 'detect_sound_events', detect)
    result = audio.prepare_inputs(SimpleNamespace(shape=(1, 32000)), 16000, raw, cache_dir=None, device='cpu')
    assert len(result['emotion_input']['selected']) == 2  # Existing voice sample gate unchanged.
    assert result['emotion_input']['phrase_selection']['selected'][0]['text'] == 'Please come here.'
    assert len(captured) == 1 and result['sound_events'][0]['label'] == 'crying'


def test_uncertainty_does_not_turn_a_large_score_into_qualified_accuracy():
    status = audio.emotion_uncertainty({'scores': {'happy': .999}, 'uncertain_transcript_words':['come']})
    assert status['interpretation_status'] == 'uncertain'
    assert 'model_accuracy_not_qualified' in status['uncertainty_reasons']
    assert 'transcript_words_uncertain' in status['uncertainty_reasons']


def test_summary_and_capability_carry_phrase_uncertainty(monkeypatch):
    from steps.common.context_analyzer_llm import _build_scene_context_prompts
    from steps.audio.audio_wsl2_bridge import _build_wsl_capability_outcomes
    from steps.video import cross_modal_harmonizer as harmonizer
    selection = {'policy':'complete_observed_phrases_v1', 'status':'insufficient_evidence', 'selected':[],
                 'rejected':[{'text':'Yay!', 'reason':'phrase_speakers_unresolved'}]}
    record = {'emotion_input':{'policy':'clear_speech_only_v2', 'status':'ready', 'selected':[{'start':0,'end':1}],
                              'phrase_selection':selection, 'speaker_purity': {'local_overlap': {
                                  'status':'ok', 'identity_claim':False, 'policy':'local_segmentation_overlap_v1',
                                  'intervals':[{'start':.5,'end':.7}]}}}, 'emotion_status':'insufficient_evidence'}
    outcome = _build_wsl_capability_outcomes(record)['acoustic_emotion']
    assert outcome['reason'] == 'no_complete_supported_phrase' and outcome['status'] == 'not_applicable'
    record['emotion_segments'] = [{'label':'disgust','scores':{'disgust':.9}, **audio.emotion_uncertainty({})}]
    record.update(scene_id='s', start=0, end=2, content_state='signal', full_transcript='Yay!')
    captured = []
    monkeypatch.setattr(harmonizer, 'analyze_scene_context_llm', lambda meta, cfg, **kw: captured.append(meta))
    harmonizer._apply_scene_context_llm([record], {'s':{'index':0,'audio':{}}},
        {'llm':{'features':{'scene_context_analysis':True}}})
    assert len(captured) == 1
    _, prompt = _build_scene_context_prompts(captured[0])
    assert 'phrase_speakers_unresolved' in prompt and 'model_accuracy_not_qualified' in prompt
    assert 'does not mean no audible speech' in prompt
    assert 'local_segmentation_overlap_v1' in prompt and '"identity_claim": false' in prompt
    assert '"intervals": [{"start": 0.5, "end": 0.7}]' in prompt
