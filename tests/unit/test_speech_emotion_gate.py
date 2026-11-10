import pytest

from wsl2_audio.acoustic_events import select_speech_intervals


def mixed_phrase_evidence():
    """A missed mixture can look like an adjacent A/B change within one phrase."""
    words = [{'start': .2, 'end': .7, 'text': "Don't", 'probability': .95},
             {'start': .7, 'end': 1.2, 'text': 'forget', 'probability': .95},
             {'start': 1.2, 'end': 1.7, 'text': 'a', 'probability': .95},
             {'start': 1.7, 'end': 2.2, 'text': 'jacket.', 'probability': .95}]
    return {'word_timestamps': words, 'segments': [{'words': words}],
            'diarization_status': 'success', 'diarization': [
                {'start': 0, 'end': 1.2, 'speaker': 'A'},
                {'start': 1.2, 'end': 2.5, 'speaker': 'B'}]}


def test_multi_speaker_phrase_cannot_supply_apparently_exclusive_word_samples(monkeypatch):
    import copy
    from types import SimpleNamespace
    from wsl2_audio import acoustic_events as audio

    raw = mixed_phrase_evidence()
    original = copy.deepcopy(raw)
    event = {'start': 0, 'end': 3, 'label': 'crying'}
    observed = {}

    def detect(*args, speech_intervals, emotion_phrases, **kwargs):
        observed.update(voice=speech_intervals, emotion=emotion_phrases)
        return [event], {'speech_presence': {'status': 'success', 'regions': []}}

    monkeypatch.setattr(audio, 'detect_sound_events', detect)
    result = audio.prepare_inputs(SimpleNamespace(shape=(1, 48000)), 16000, raw,
                                  cache_dir='unused', device='cpu')
    # Veto precedes acoustic assessment and both downstream inference callers.
    assert observed == {'voice': [], 'emotion': []}
    assert result['emotion_input']['selected'] == []
    assert result['emotion_input']['phrase_selection']['selected'] == []
    assert {r['reason'] for r in result['emotion_input']['rejected']} == {'phrase_speakers_unresolved'}
    exclusion = result['emotion_input']['speaker_purity']['excluded_phrases'][0]
    assert exclusion['speaker_candidates'] == ['A', 'B']
    assert exclusion['overlap_observed'] is False  # Never invent a detected overlap.
    assert result['sound_events'] == [event] and raw == original


@pytest.mark.parametrize('long_phrase', [False, True])
def test_purity_veto_does_not_depend_on_emotion_duration_or_word_confidence(long_phrase):
    raw = mixed_phrase_evidence()
    if long_phrase:
        for word in raw['word_timestamps']:
            word['start'] *= 4
            word['end'] *= 4
        for turn in raw['diarization']:
            turn['start'] *= 4
            turn['end'] *= 4
    raw['word_timestamps'][1]['probability'] = .1
    selected, rejected = select_speech_intervals(raw, [
        {'start': 0, 'end': 10, 'speech_score': 1., 'excluded_labels': []}], 10)
    assert selected == []
    assert any(r['reason'] == 'phrase_speakers_unresolved' for r in rejected)


@pytest.mark.parametrize('separate_segments', [False, True])
def test_separate_single_speaker_phrases_survive_a_turn_change(separate_segments):
    raw = mixed_phrase_evidence()
    raw['word_timestamps'][1]['text'] = 'forget.'
    if separate_segments:
        raw['segments'] = [{'words': raw['word_timestamps'][:2]}, {'words': raw['word_timestamps'][2:]}]
    selected, rejected = select_speech_intervals(raw, [
        {'start': 0, 'end': 3, 'speech_score': 1., 'excluded_labels': []}], 3)
    assert [(s['start'], s['end'], s['speaker']) for s in selected] == [(.2, 1.2, 'A'), (1.2, 2.2, 'B')]
    assert not rejected


def test_second_transcript_row_cannot_rescue_audio_inside_a_mixed_phrase():
    from wsl2_audio import acoustic_events as audio
    raw = mixed_phrase_evidence()
    # A competing segmentation presents the prefix as a single-speaker phrase.
    prefix = [dict(raw['word_timestamps'][0], text="Don't.")]
    raw['segments'].append({'words': prefix})
    raw['word_timestamps'] = raw['word_timestamps'] + prefix
    candidates, rejected = audio.emotion_phrase_candidates(raw, 3)
    assert candidates == []
    assert len(rejected) == 2
    assert {p['reason'] for p in rejected} == {'phrase_speakers_unresolved'}
    selected, _ = select_speech_intervals(raw, [
        {'start': 0, 'end': 3, 'speech_score': 1., 'excluded_labels': []}], 3)
    assert selected == []


def test_local_overlap_with_one_global_speaker_blocks_whole_phrase(monkeypatch):
    import copy
    from types import SimpleNamespace
    from wsl2_audio import acoustic_events as audio
    raw = mixed_phrase_evidence()
    for turn in raw['diarization']: turn['speaker'] = 'A'
    raw['overlap_detection'] = {'status': 'ok', 'policy': 'local_segmentation_overlap_v1',
        'intervals': [{'start': .85, 'end': 1.0}], 'identity_claim': False}
    original = copy.deepcopy(raw)
    seen = []
    def detector(*args, speech_intervals, emotion_phrases, **kwargs):
        seen.extend(speech_intervals + emotion_phrases)
        return [{'label': 'crying'}], {'speech_presence': {'status': 'success', 'regions': []}}
    monkeypatch.setattr(audio, 'detect_sound_events', detector)
    output = audio.prepare_inputs(SimpleNamespace(shape=(1, 48000)), 16000, raw,
                                  cache_dir='unused', device='cpu')
    assert not seen and not output['emotion_input']['selected']
    phrase = output['emotion_input']['phrase_selection']['rejected'][0]
    assert phrase['reason'] == 'local_overlap_in_phrase'
    assert phrase['overlap_intervals'] == raw['overlap_detection']['intervals']
    assert 'speaker' not in phrase
    assert output['emotion_input']['speaker_purity']['local_overlap'] == raw['overlap_detection']
    assert output['sound_events'] == [{'label': 'crying'}] and raw == original


@pytest.mark.parametrize('status', ['unavailable', 'error'])
def test_failed_overlap_observation_withholds_individual_inference_not_words(status):
    from wsl2_audio import acoustic_events as audio
    raw = mixed_phrase_evidence()
    for turn in raw['diarization']: turn['speaker'] = 'A'
    raw['overlap_detection'] = {'status': status, 'intervals': []}
    selected, rejected = select_speech_intervals(raw, [
        {'start': 0, 'end': 3, 'speech_score': 1., 'excluded_labels': []}], 3)
    assert not selected and all(r['reason'] == 'overlap_detection_unavailable' for r in rejected)
    selected, rejected = audio.emotion_phrase_candidates(raw, 3)
    assert not selected and rejected[0]['reason'] == 'overlap_detection_unavailable'
    assert len(raw['word_timestamps']) == 4


def test_additional_detector_vetoes_single_label_phrase_without_replacing_local_evidence(monkeypatch):
    import copy
    from types import SimpleNamespace
    from wsl2_audio import acoustic_events as audio
    raw = mixed_phrase_evidence()
    for turn in raw['diarization']: turn['speaker'] = 'A'
    raw['overlap_detection'] = {'status': 'ok', 'intervals': []}
    raw['additional_overlap_detection'] = {'status': 'ok', 'policy': 'nemotron3_overlap_exclusion_v1',
        'intervals': [{'start': 1., 'end': 1.4}], 'identity_claim': False}
    original = copy.deepcopy(raw)
    seen = []
    def events(*args, speech_intervals, emotion_phrases, **kwargs):
        seen.extend(speech_intervals + emotion_phrases)
        return [{'label': 'crying'}], {'speech_presence': {'status': 'success', 'regions': []}}
    monkeypatch.setattr(audio, 'detect_sound_events', events)
    output = audio.prepare_inputs(SimpleNamespace(shape=(1, 48000)), 16000, raw, cache_dir='unused', device='cpu')
    gate = output['emotion_input']
    assert not seen and not gate['selected'] and not gate['phrase_selection']['selected']
    rejected = gate['phrase_selection']['rejected'][0]
    assert rejected['reason'] == 'additional_overlap_in_phrase' and 'speaker' not in rejected
    assert rejected['additional_overlap_intervals'] == raw['additional_overlap_detection']['intervals']
    assert gate['speaker_purity']['local_overlap'] == raw['overlap_detection']
    assert gate['speaker_purity']['additional_overlap'] == raw['additional_overlap_detection']
    assert output['sound_events'] == [{'label': 'crying'}] and raw == original


@pytest.mark.parametrize('observation', [
    {'status': 'error', 'intervals': []}, {'status': 'unavailable', 'intervals': []},
    {'status': 'ok', 'intervals': [{'start': 1., 'end': 4.}]},
    {'status': 'ok', 'intervals': [{'start': float('nan'), 'end': 1.}]},
    {'status': 'ok'}, {'status': 'ok', 'intervals': [None]},
])
def test_invalid_additional_detector_cannot_restore_individual_inference(observation):
    from wsl2_audio import acoustic_events as audio
    raw = mixed_phrase_evidence()
    for turn in raw['diarization']: turn['speaker'] = 'A'
    raw['overlap_detection'] = {'status': 'ok', 'intervals': []}
    raw['additional_overlap_detection'] = observation
    selected, rejected = select_speech_intervals(raw, [{'start': 0, 'end': 3, 'speech_score': 1., 'excluded_labels': []}], 3)
    assert not selected and {r['reason'] for r in rejected} == {'overlap_detection_unavailable'}
    selected, rejected = audio.emotion_phrase_candidates(raw, 3)
    assert not selected and rejected[0]['reason'] == 'overlap_detection_unavailable'


@pytest.mark.parametrize('detector', ['overlap_detection', 'additional_overlap_detection'])
def test_voice_word_join_cannot_bridge_detected_overlap_in_a_gap(detector):
    raw = {'diarization_status': 'success', 'diarization': [{'start': 0, 'end': 2, 'speaker': 'A'}],
           'word_timestamps': [{'start': .1, 'end': .6, 'text': 'one', 'probability': .95},
                               {'start': .8, 'end': 1.3, 'text': 'two', 'probability': .95}],
           detector: {'status': 'ok', 'intervals': [{'start': .65, 'end': .75}]}}
    selected, _ = select_speech_intervals(raw, [{'start': 0, 'end': 2, 'speech_score': 1., 'excluded_labels': []}], 2)
    assert [(r['start'], r['end']) for r in selected] == [(.1, .6), (.8, 1.3)]


def test_empty_additional_overlap_retains_clean_speech_and_cannot_clear_crying():
    from wsl2_audio import acoustic_events as audio
    raw = mixed_phrase_evidence()
    for turn in raw['diarization']: turn['speaker'] = 'A'
    raw['additional_overlap_detection'] = {'status': 'ok', 'intervals': []}
    clean = [{'start': 0, 'end': 3, 'speech_score': 1., 'excluded_labels': []}]
    selected, rejected = select_speech_intervals(raw, clean, 3)
    assert selected and not rejected
    phrases, rejected = audio.emotion_phrase_candidates(raw, 3)
    assert phrases and not rejected
    selected, rejected = select_speech_intervals(raw, [{**clean[0], 'excluded_labels': ['crying']}], 3)
    assert not selected and {r['reason'] for r in rejected} == {'non_speech_or_uncertain_audio'}


def evidence():
    words = [{'start': i, 'end': i + .8, 'text': 'word', 'probability': .95} for i in range(8)]
    return {'word_timestamps': words, 'diarization_status': 'success',
            'diarization': [{'start': 0, 'end': 8, 'speaker': 'S0'}]}


def test_crying_overlapping_speech_is_excluded_without_discarding_the_event():
    windows = [{'start': 0, 'end': 4, 'speech_score': .9, 'excluded_labels': []},
               {'start': 4, 'end': 8, 'speech_score': .9, 'excluded_labels': ['crying']}]
    selected, rejected = select_speech_intervals(evidence(), windows, 8)
    assert selected and all(s['end'] <= 4 for s in selected)
    assert any(r['reason'] == 'non_speech_or_uncertain_audio' for r in rejected)
    assert windows[1]['excluded_labels'] == ['crying']


@pytest.mark.parametrize('failure', ['missing_detection', 'missing_speaker', 'low_word_confidence', 'overlapping_speakers', 'uncertain_sound'])
def test_uncertain_inputs_never_feed_emotion(failure):
    raw = evidence()
    windows = [{'start': 0, 'end': 8, 'speech_score': .9, 'excluded_labels': []}]
    if failure == 'missing_detection':
        windows = []
    if failure == 'missing_speaker':
        raw['diarization'] = []
    if failure == 'overlapping_speakers':
        raw['diarization'].append({'start': 0, 'end': 8, 'speaker': 'S1'})
    if failure == 'low_word_confidence':
        for word in raw['word_timestamps']:
            word['probability'] = .2
    if failure == 'uncertain_sound':
        windows[0]['speech_score'] = .2
    selected, _ = select_speech_intervals(raw, windows, 8)
    assert selected == []


def test_segments_are_short_and_speaker_specific_and_do_not_bridge_exclusions():
    raw = evidence()
    raw['diarization'] = [{'start': 0, 'end': 4, 'speaker': 'S0'}, {'start': 4, 'end': 8, 'speaker': 'S1'}]
    selected, _ = select_speech_intervals(raw, [{'start': 0, 'end': 8, 'speech_score': .9, 'excluded_labels': []}], 8)
    assert {s['speaker'] for s in selected} == {'S0', 'S1'}
    assert all(s['end'] - s['start'] <= 6 for s in selected)
    assert all(s['end'] <= 4 if s['speaker'] == 'S0' else s['start'] >= 4 for s in selected)


def test_rejected_word_breaks_an_otherwise_joinable_interval():
    raw = evidence()
    raw['word_timestamps'] = [
        {'start': 0, 'end': .6, 'text': 'yes', 'probability': .95},
        {'start': .6, 'end': .7, 'text': '?', 'probability': .1},
        {'start': .7, 'end': 1.3, 'text': 'hello', 'probability': .95}]
    selected, _ = select_speech_intervals(raw, [{'start': 0, 'end': 8, 'speech_score': .9, 'excluded_labels': []}], 8)
    assert len(selected) == 2
    assert selected[0]["end"] <= .6 and selected[1]["start"] >= .7


def test_partial_speaker_boundary_retains_supported_audio_without_retiming_words():
    """Frozen MOSS clean-B failure: dropping Don't leaves a misleading AST crop."""
    import copy

    raw = {'diarization_status': 'success',
           'diarization': [{'start': .48, 'end': 1.65, 'speaker': 'S01'}],
           'word_timestamps': [
               {'text': "Don't", 'start': 0, 'end': .86, 'probability': .86},
               {'text': 'forget', 'start': .86, 'end': 1.04, 'probability': .90},
               {'text': 'a', 'start': 1.04, 'end': 1.32, 'probability': .99},
               {'text': 'jacket.', 'start': 1.32, 'end': 1.54, 'probability': .99}]}
    original = copy.deepcopy(raw)
    selected, rejected = select_speech_intervals(
        raw, [{'start': 0, 'end': 2.5025, 'speech_score': .9, 'excluded_labels': []}], 2.5025)
    assert [(s['start'], s['end'], s['word_count']) for s in selected] == [(.48, 1.54, 4)]
    assert selected[0]['timing_adjustments'] == [{
        'word_start': 0., 'word_end': .86, 'selected_start': .48, 'selected_end': .86,
        'method': 'word_speaker_intersection', 'review_status': 'unreviewed'}]
    assert not rejected
    assert raw == original


def test_adjacent_same_speaker_turns_cover_a_word_without_an_artificial_boundary():
    raw = {'diarization_status': 'success', 'word_timestamps': [
        {'text': 'hello', 'start': .2, 'end': 1.2, 'probability': .95}],
        'diarization': [{'start': 0, 'end': .5, 'speaker': 'S0'},
                        {'start': .5, 'end': 1.5, 'speaker': 'S0'}]}
    selected, rejected = select_speech_intervals(
        raw, [{'start': 0, 'end': 2, 'speech_score': .9, 'excluded_labels': []}], 2)
    assert [(s['start'], s['end']) for s in selected] == [(.2, 1.2)]
    assert not rejected


@pytest.mark.parametrize('tracks', [
    [{'start': 0, 'end': .5, 'speaker': 'S1'}, {'start': .48, 'end': 1.5, 'speaker': 'S0'}],
    [{'start': 0, 'end': .3, 'speaker': 'S0'}, {'start': .6, 'end': 1.5, 'speaker': 'S0'}],
])
def test_intersection_never_rescues_competing_speakers_or_a_hole_inside_a_word(tracks):
    raw = {'diarization_status': 'success', 'word_timestamps': [
        {'text': 'hello', 'start': 0, 'end': 1.2, 'probability': .95}], 'diarization': tracks}
    selected, rejected = select_speech_intervals(
        raw, [{'start': 0, 'end': 2, 'speech_score': .9, 'excluded_labels': []}], 2)
    assert not selected
    assert rejected[0]['reason'] == 'missing_or_overlapping_speakers'


def test_separate_words_do_not_join_across_unobserved_speaker_time():
    raw = {'diarization_status': 'success', 'word_timestamps': [
        {'text': 'hello', 'start': 0, 'end': .5, 'probability': .95},
        {'text': 'there', 'start': .7, 'end': 1.2, 'probability': .95}],
        'diarization': [{'start': 0, 'end': .5, 'speaker': 'S0'},
                        {'start': .7, 'end': 1.2, 'speaker': 'S0'}]}
    selected, _ = select_speech_intervals(
        raw, [{'start': 0, 'end': 2, 'speech_score': .9, 'excluded_labels': []}], 2)
    assert [(s['start'], s['end']) for s in selected] == [(0., .5), (.7, 1.2)]


def test_coarse_overlapping_phrases_cannot_claim_a_precisely_isolated_prefix():
    raw = {'diarization_status': 'success', 'word_timestamps': [
        {'text': "Don't", 'start': 18.26, 'end': 18.82, 'probability': .95}],
        'diarization': [{'start': 18.45, 'end': 19.23, 'speaker': 'S01'},
                        {'start': 19.08, 'end': 20.13, 'speaker': 'S02'}],
        'diarization_timing': {'boundary_precision': 'phrase'}}
    selected, rejected = select_speech_intervals(
        raw, [{'start': 0, 'end': 22, 'speech_score': .9, 'excluded_labels': []}], 22)
    assert not selected
    assert rejected[0]['reason'] == 'overlapping_phrase_timing_unresolved'


@pytest.mark.parametrize('coverage,ast_score,excluded,presence_status,accepted', [
    (.95, .05, [], 'success', True),
    (.8, .05, [], 'success', True),
    (.79, .05, [], 'success', False),
    (None, .05, [], 'success', False),
    (float('nan'), .05, [], 'success', False),
    (.1, .728, [], 'success', True),  # Known angry speech missed by VAD.
    (.95, .95, [], 'error', False),
    (.95, .95, ['crying'], 'success', False),
    (.95, .95, ['music'], 'success', False),
])
def test_actual_admission_keeps_independent_speech_evidence_and_sound_exclusions(
        monkeypatch, coverage, ast_score, excluded, presence_status, accepted):
    from types import SimpleNamespace
    from wsl2_audio import acoustic_events

    raw = {'diarization_status': 'success', 'word_timestamps': [
        {'text': 'hello', 'start': .2, 'end': 1.2, 'probability': .95}],
        'diarization': [{'start': 0, 'end': 2, 'speaker': 'S0'}]}
    def detector(*args, speech_intervals, **kwargs):
        assert [(s['start'], s['end']) for s in speech_intervals] == [(.2, 1.2)]
        return [], {'speech_presence': {'status': presence_status}, 'speech_windows': [
            {'start': .2, 'end': 1.2, 'speech_score': ast_score,
             'vad_speech_coverage': coverage, 'excluded_labels': excluded}]}
    monkeypatch.setattr(acoustic_events, 'detect_sound_events', detector)
    result = acoustic_events.prepare_inputs(SimpleNamespace(shape=(1, 32000)), 16000, raw,
                                            cache_dir='unused', device='cpu')
    assert bool(result['emotion_input']['selected']) is accepted
    assert result['emotion_input']['policy'] == 'clear_speech_only_v2'
    if accepted:
        basis = result['emotion_input']['selected'][0]['speech_presence_basis']
        assert ('audioset_speech' in basis) is (ast_score >= .5)
        assert ('silero_vad' in basis) is (coverage >= .8)


@pytest.mark.parametrize('target_excluded,context_excluded,supported,accepted', [
    (['music'], [], True, True),
    (['music'], ['crying'], True, False),
    (['music'], ['music'], True, False),
    (['music'], [], False, False),
    (['crying'], [], True, False),
])
def test_context_only_resolves_music_dispute_and_never_changes_selected_audio(
        monkeypatch, target_excluded, context_excluded, supported, accepted):
    from types import SimpleNamespace
    from wsl2_audio import acoustic_events
    raw = {'diarization_status': 'success', 'word_timestamps': [
        {'text': 'hello', 'start': .5, 'end': 1.5, 'probability': .95}],
        'diarization': [{'start': .3, 'end': 1.7, 'speaker': 'S0'}]}
    window = {'start': .5, 'end': 1.5, 'speech_score': .499, 'vad_speech_coverage': .93,
              'excluded_labels': target_excluded, 'context_check': {
                  'start': 0, 'end': 2, 'speech_score': .73, 'excluded_labels': context_excluded,
                  'status': 'assessed', 'speaker_support_checked': supported}}
    monkeypatch.setattr(acoustic_events, 'detect_sound_events', lambda *a, **kw: (
        [], {'speech_presence': {'status': 'success'}, 'speech_windows': [window]}))
    result = acoustic_events.prepare_inputs(SimpleNamespace(shape=(1, 32000)), 16000, raw,
                                            cache_dir='unused', device='cpu')
    selected = result['emotion_input']['selected']
    assert bool(selected) is accepted
    assert window['excluded_labels'] == target_excluded
    if accepted:
        assert (selected[0]['start'], selected[0]['end']) == (.5, 1.5)
        assert selected[0]['acoustic_context']['target_disagreement'] == 'music_only_not_corroborated'


@pytest.mark.parametrize('policy', ['clear_speech_only_v1', 'clear_speech_only_v2'])
def test_speech_policy_never_promotes_a_legacy_scene_emotion(policy):
    from steps.video.cross_modal_harmonizer import _resolve_audio_emotion
    assert _resolve_audio_emotion({'emotion_input': {'policy': policy},
                                  'emotion': 'sad', 'emotion_scores': {'sad': .9}}) == (None, {})


@pytest.mark.parametrize('has_speech', [False, True])
@pytest.mark.parametrize('policy', ['clear_speech_only_v1', 'clear_speech_only_v2'])
def test_sound_and_speech_evidence_survive_harmonizer_and_real_http_routes(tmp_path, monkeypatch, has_speech, policy):
    import json
    from pathlib import Path
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from steps.video.cross_modal_harmonizer import run_cross_modal_harmonization
    from steps.audio.audio_wsl2_bridge import _build_wsl_capability_outcomes
    from api.routes import scenes, timeline
    from api.utils.loaders import DataLoader

    event = {'label': 'crying', 'start': 2, 'end': 4, 'status': 'model_detected'}
    selection = [{'start': 0, 'end': 1.8, 'speaker': 'S0'}] if has_speech else []
    estimates = [{**selection[0], 'label': 'neutral', 'scores': {'neutral': .8}, 'review_status': 'unreviewed'}] if has_speech else []
    audio = {'status': 'success', 'full_text': 'hello there', 'emotion': None, 'emotion_scores': {},
             'emotion_status': 'success' if has_speech else 'insufficient_evidence',
             'emotion_input': {'policy': policy, 'status': 'ready' if has_speech else 'insufficient_evidence', 'selected': selection},
             'sound_events': [event], 'sound_event_meta': {'status': 'success'}, 'emotion_segments': estimates}
    outcome = _build_wsl_capability_outcomes(audio)['acoustic_emotion']
    assert outcome['status'] == ('ok' if has_speech else 'not_applicable')
    processing = tmp_path/'processing'
    video = processing/'clip'/'video'
    video.mkdir(parents=True)
    manifest = video/'scene_manifest.json'
    manifest.write_text(json.dumps({'video_id': 'clip', 'scenes': [
        {'id': 's0', 'scene_id': 's0', 'index': 0, 'start': 0, 'end': 4, 'duration': 4, 'audio': audio}]}))
    cfg = {'ingestion_isolation': True, 'features': {'enable_llm_refinement': False, 'enable_scene_context_llm': False},
           'paths': {'processing': str(processing), 'processing_dir': str(processing), 'log_dir': str(tmp_path/'logs')}}
    result = run_cross_modal_harmonization({'scene_manifest_path': str(manifest), 'video_id': 'clip'}, cfg)
    persisted = json.loads(Path(result['temporal_index_path']).read_text())['segments'][0]
    assert persisted['sound_events'] == [event]
    assert persisted['emotion_segments'] == estimates
    assert persisted['audio_emotion'] is None and persisted['audio_emotion_scores'] == {}
    loader = DataLoader(processing_root=str(processing))
    monkeypatch.setattr(scenes, 'get_data_loader', lambda: loader)
    monkeypatch.setattr(timeline, 'get_data_loader', lambda: loader)
    app = FastAPI()
    app.include_router(scenes.router)
    app.include_router(timeline.router)
    with TestClient(app) as client:
        response = client.get('/api/videos/clip/scenes/s0')
        assert response.status_code == 200, response.text
        assert response.json()['sound_events'] == [event]
        assert response.json()['emotion_segments'] == estimates
        response = client.get('/api/videos/clip/timeline/full')
        assert response.status_code == 200, response.text
        assert response.json()['segments'][0]['sound_events'] == [event]
