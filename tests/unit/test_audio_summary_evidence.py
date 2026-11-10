"""Audio evidence must keep recognition, timing and scene-mood authority separate."""
import copy
import json

import pytest

from steps.common import context_analyzer_llm as analyzer
from steps.video import cross_modal_harmonizer as harmonizer


def scene(flags, *, outcome='text_returned', status='completed', caption=''):
    coverage = {'policy': 'source_audio_v2', 'status': status, 'recognition_accuracy': 'unverified',
        'regions': [{'index': 0, 'start': 0., 'end': 12., 'outcome': outcome, 'quality_flags': flags}]}
    segment = {'scene_id': 's', 'start': 0., 'end': 12., 'content_state': 'signal',
        'full_transcript': 'We grow tomatoes in the garden.',
        'transcript_meta': {'transcription_decoding': {'source_regions': coverage}},
        'emotion_input': {'policy': 'clear_speech_only_v2', 'status': 'insufficient_evidence'},
        'emotion_segments': []}
    lookup = {'s': {'index': 0, 'audio': {}, 'caption': caption}}
    return segment, lookup


class Client:
    last_model_used = None
    last_provider_used = 'fixture'

    def __init__(self, mode='success', *, summary='People mention tomatoes.', mood='sad scene mood'):
        self.mode, self.summary, self.mood = mode, summary, mood
        self.calls = []
        self.tags = ['vacation'] if 'vacation' in summary else []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        raw = {'narrative_summary': self.summary, 'activity_description': self.summary,
               'key_moments': [self.summary], 'emotional_arc': self.mood,
               'context_tags': self.tags}
        return {'choices': [{'finish_reason': 'length' if self.mode == 'truncated' else 'stop',
            'message': {'content': 'invalid json' if self.mode == 'malformed' else json.dumps(raw)}}]}


def run(segment, lookup, client):
    original = copy.deepcopy(segment)
    result = harmonizer._apply_scene_context_llm([segment], lookup,
        {'llm': {'features': {'scene_context_analysis': True}}}, llm_client=client)
    assert result['evaluated_count'] == 1
    for key in ('full_transcript', 'transcript_meta', 'emotion_input', 'emotion_segments'):
        assert segment.get(key) == original.get(key)
    return segment['scene_context_llm']


@pytest.mark.parametrize('flag', ['invalid_word_timing', 'word_alignment_unavailable'])
def test_timing_only_failure_keeps_words_for_semantic_analysis_and_persists_caution(flag):
    segment, lookup = scene([flag]);client = Client()
    result = run(segment, lookup, client)
    assert 'tomato' in result['narrative_summary'].lower()
    details = result['transcription_evidence']
    assert details['text_status'] == 'available_model_estimate'
    assert details['recognition_accuracy'] == 'unverified'
    assert details['timing_warnings'] == [flag]
    assert result['transcription_coverage_uncertain'] is True
    assert 'timing' in result['narrative_summary'].lower()
    assert 'recognition is uncertain' not in result['narrative_summary'].lower()
    prompt = client.calls[0]['messages'][1]['content']
    assert 'available_model_estimate' in prompt and flag in prompt
    assert result['emotional_arc'] == 'unqualified'


@pytest.mark.parametrize('flag', ['compression_ratio_threshold_exceeded', 'log_probability_below_threshold',
                                 'unknown_new_warning', 'invalid_segment_timing'])
@pytest.mark.parametrize('caption', ['', 'A person opens a wooden door.'])
def test_real_recognition_warnings_cannot_be_bypassed_by_adversarial_model_prose(flag, caption):
    segment, lookup = scene(['invalid_word_timing', flag], caption=caption)
    segment['full_transcript'] = 'We went on a vacation.'
    result = run(segment, lookup, Client(summary='A conversation about vacation.'))
    assert 'vacation' not in json.dumps(result).lower()
    assert result['transcription_evidence']['text_status'] == 'withheld_recognition_uncertainty'
    assert result['transcription_coverage_uncertain'] is True
    assert result['emotional_arc'] == 'unqualified'


@pytest.mark.parametrize('mode', ['unavailable', 'malformed', 'truncated'])
def test_summary_failures_preserve_independent_visual_evidence_and_audio_limits(mode):
    segment, lookup = scene(['compression_ratio_threshold_exceeded'], caption='A person opens a wooden door.')
    client = None if mode == 'unavailable' else Client(mode)
    result = run(segment, lookup, client)
    assert result['status'] == 'fallback'
    assert 'wooden door' in result['narrative_summary']
    assert result['claim_provenance']['narrative_summary']['depends_on'] == ['image_caption']
    assert result['transcription_coverage_uncertain'] is True
    assert result['transcription_evidence']['text_status'] == 'withheld_recognition_uncertainty'


@pytest.mark.parametrize('mode', ['success', 'unavailable'])
def test_unqualified_individual_emotion_never_becomes_scene_mood(mode):
    segment, lookup = scene([])
    segment['emotion_segments'] = [{'label': 'sad', 'interpretation_status': 'uncertain',
        'model_qualification': 'unqualified', 'review_status': 'unreviewed'}]
    result = run(segment, lookup, Client() if mode == 'success' else None)
    assert result['emotional_arc'] == 'unqualified'
    assert result['emotion_qualification']['scope'] == 'whole_scene'
    assert result['emotion_qualification']['status'] == 'unqualified'


def test_missing_emotion_is_not_neutral_even_when_text_is_available():
    segment, lookup = scene([])
    result = run(segment, lookup, None)
    assert result['emotional_arc'] == 'unqualified'


@pytest.mark.parametrize('outcome,status', [('no_text_returned', 'completed'), ('error', 'error')])
def test_missing_or_failed_recognition_is_not_released_by_a_timing_warning(outcome, status):
    segment, lookup = scene(['invalid_word_timing'], outcome=outcome, status=status)
    result = run(segment, lookup, Client())
    assert result['transcription_evidence']['text_status'] == 'withheld_recognition_uncertainty'
    assert 'tomato' not in result['narrative_summary'].lower()


def test_independently_grounded_visual_model_output_survives_a_real_asr_warning():
    caption = 'A person opens a wooden door.'
    segment, lookup = scene(['compression_ratio_threshold_exceeded'], caption=caption)
    result = run(segment, lookup, Client(summary=caption))
    assert caption in result['narrative_summary']
    assert result['claim_provenance']['narrative_summary']['depends_on'] == ['image_caption']


@pytest.mark.parametrize('channel,value', [
    ('sound_events', [{'label': 'crying', 'start': 0., 'end': 1.}]),
    ('text_emotion_ranking', [{'label': 'sad', 'score': .99}]),
    ('sentiment', {'label': 'NEGATIVE', 'score': .99}),
])
def test_other_audio_evidence_cannot_establish_whole_scene_mood(channel, value):
    segment, lookup = scene([])
    segment.update(full_transcript='', transcript_meta={}, emotion_segments=[])
    segment.pop('emotion_input')
    segment[channel] = value
    # Ensure the production caller evaluates a sound/text-analysis-only record.
    lookup['s']['caption'] = 'A person opens a wooden door.'
    result = run(segment, lookup, Client(summary=lookup['s']['caption']))
    assert result['emotional_arc'] == 'unqualified'
    assert result['emotion_qualification']['scope'] == 'whole_scene'


@pytest.mark.parametrize('variant', ['clean', 'empty_regions', 'contradictory_absence'])
def test_long_transcript_heuristic_cannot_bypass_coverage_qualification(variant):
    segment, lookup = scene([])
    segment['full_transcript'] = 'We grow tomatoes in the garden near the wooden fence.'
    segment.pop('emotion_input');segment.pop('emotion_segments')
    coverage = segment['transcript_meta']['transcription_decoding']['source_regions']
    if variant == 'empty_regions': coverage['regions'] = []
    if variant == 'contradictory_absence': coverage.update(status='not_applicable_no_detected_speech', regions=[])
    result = run(segment, lookup, None)
    assert result['transcription_evidence']['text_status'] == (
        'available_model_estimate' if variant == 'clean' else 'withheld_recognition_uncertainty')
    assert result['emotional_arc'] == 'unqualified'
    if variant != 'clean': assert 'tomato' not in json.dumps(result).lower()


@pytest.mark.parametrize('independent', [False, True])
def test_transcript_derived_cues_are_not_independent_support_for_warned_words(independent):
    from steps.audio_music_events.step import audio_music_events
    segment, lookup = scene(['compression_ratio_threshold_exceeded'], caption='A person opens a wooden door.')
    segment['full_transcript'] = 'We are singing for Christmas here today.'
    segment.update(audio_music_events({'transcript': segment['full_transcript']}, {}))
    assert segment['music_events']
    if independent: segment['ocr_text'] = 'Christmas'
    client = Client(summary=lookup['s']['caption']);client.tags = ['christmas']
    result = run(segment, lookup, client)
    tags = result['context_tags'] + result['primary_tags'] + result['contextual_tags']
    assert ('christmas' in tags) is independent
    assert segment['music_events']  # Raw cue evidence stays retained in either case.


@pytest.mark.parametrize('caption,ocr,claim,forbidden', [
    ('A person carries a vacuum.', '', 'A conversation about vacation.', 'vacation'),
    ('', 'The year is 1988.', 'The year is 1999.', '1999'),
    ('', 'Christmas', 'A conversation about Christmas.', 'conversation'),
    ('A furnished living room.', '', 'Living room conversation.', 'conversation'),
])
def test_restricted_summary_preserves_exact_independent_evidence_and_its_modality(caption, ocr, claim, forbidden):
    segment, lookup = scene(['compression_ratio_threshold_exceeded'], caption=caption)
    segment['full_transcript'] = claim
    segment['ocr_text'] = ocr
    result = run(segment, lookup, Client(summary=claim))
    assert forbidden not in json.dumps(result).lower()
    assert (caption or ocr) in result['narrative_summary']
    assert result['claim_provenance']['narrative_summary']['depends_on'] == (
        ['image_caption'] if caption else ['image_ocr'])
    if ocr: assert 'Visible text:' in result['narrative_summary']


@pytest.mark.parametrize('client', [None, Client(summary='A conversation about vacation.')])
def test_timing_only_warning_cannot_erase_dialogue_when_no_topic_can_be_extracted(client):
    segment, lookup = scene(['invalid_word_timing'])
    segment['full_transcript'] = 'Look at them. Look over here. What is this?'
    result = run(segment, lookup, client)
    assert 'Spoken or dialogue evidence present.' in result['narrative_summary']
    assert 'Speech timing is uncertain' in result['narrative_summary']


@pytest.mark.parametrize('speech', ['clear', 'crying', 'silence'])
def test_unrelated_summary_topic_cannot_be_created_from_clear_speech_or_speech_absence(speech):
    segment, lookup = scene([])
    if speech != 'clear':
        segment['full_transcript'] = ''
        segment['transcript_meta']['transcription_decoding']['source_regions'].update(
            status='not_applicable_no_detected_speech', regions=[])
        segment['sound_events'] = [{'label': speech, 'start': 0., 'end': 12., 'score': .9}]
    result = run(segment, lookup, Client(summary='A conversation about vacation.'))
    assert 'vacation' not in json.dumps(result).lower()
    assert result['transcription_evidence']['text_status'] == (
        'available_model_estimate' if speech == 'clear' else 'no_text')
    if speech != 'clear':
        assert not result.get('transcription_coverage_uncertain')
        assert 'recognition is uncertain' not in result['narrative_summary'].lower()


@pytest.mark.parametrize('mode', ['unavailable', 'malformed', 'truncated'])
@pytest.mark.parametrize('visual', ['caption', 'ocr'])
def test_no_speech_fallback_keeps_independent_observations(mode, visual):
    segment, lookup = scene([], status='not_applicable_no_detected_speech')
    segment['full_transcript'] = ''
    segment['transcript_meta']['transcription_decoding']['source_regions']['regions'] = []
    segment['sound_events'] = [{'label': 'crying', 'start': 0., 'end': 12.}]
    evidence = 'A person opens a wooden door.' if visual == 'caption' else 'The year is 1988.'
    if visual == 'caption': lookup['s']['caption'] = evidence
    else: segment['ocr_text'] = evidence
    result = run(segment, lookup, None if mode == 'unavailable' else Client(mode))
    assert evidence in result['narrative_summary']
    assert result['transcription_evidence']['text_status'] == 'no_text'
    assert not result.get('transcription_coverage_uncertain')
