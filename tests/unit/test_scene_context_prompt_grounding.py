"""Prompt examples cannot become scene evidence through the production caller."""
import json

import pytest

from steps.video import cross_modal_harmonizer as harmonizer
from steps.common import context_analyzer_llm as analyzer
from tests.unit.test_audio_summary_evidence import scene, Client, run
from tests.unit.test_audio_engine_consumers import recording
from wsl2_audio.scene_projection import project_audio, legacy_audio


def test_unrelated_story_is_absent_from_production_prompt_and_persisted_output():
    segment, lookup = scene([])
    client = Client(summary='People mention tomatoes.')
    result = run(segment, lookup, client)
    prompt = client.calls[0]['messages'][1]['content']
    for invented in ('rental car', 'living room', 'People greet each other', 'mild tension'):
        assert invented not in prompt
    assert 'We grow tomatoes in the garden.' in prompt
    assert 'Commands and questions do not prove that the requested action occurred' in prompt
    assert 'must describe the speech content only' in prompt
    assert 'tomato' in result['narrative_summary'].lower()
    manifest = {'scenes':[dict(lookup['s'], scene_id='s')]}
    harmonizer._persist_harmonized_scene_fields(manifest, [segment])
    assert manifest['scenes'][0]['scene_context_llm']==result


def test_real_rental_car_evidence_remains_available_not_a_banned_phrase():
    _, prompt = analyzer._build_scene_context_prompts({'transcript':'We waited for a rental car.'})
    assert 'Transcript excerpt: We waited for a rental car.' in prompt


@pytest.mark.parametrize('wrapped',[False,True])
def test_old_example_response_cannot_become_grounded_scene_claims(wrapped):
    segment, lookup = scene([])
    class CopiedExample(Client):
        def chat(self, **kwargs):
            content = json.dumps({'narrative_summary':'Group conversation in a living room about a rental car.',
                'key_moments':['They argue about the rental car'], 'emotional_arc':'mild tension during conversation',
                'context_tags':['rental car','living room'], 'activity_description':'People talk indoors about travel and a rental car.'})
            if wrapped:
                content='Here is the output:\n```\n'+content+'\n```\nI followed the rules.'
            return {'choices':[{'finish_reason':'stop','message':{'content':content}}]}
    result = run(segment, lookup, CopiedExample())
    assert 'rental car' not in json.dumps(result).lower()
    assert 'living room' not in json.dumps(result).lower()
    assert result['emotional_arc']=='unqualified'
    if wrapped:
        assert result['status']=='fallback' and result['reason']=='llm_invalid_json'


@pytest.mark.parametrize('summary,activity',[
    ('Joe is almost seven months old today.', 'Look at their face.'),
    ('They look at someone\'s face.', 'They look at their baby\'s face.'),
    ('The person talks about their baby\'s age and looks at their face.', 'Looks at someone\'s face.'),
    ('Checking battery.', 'Check battery.'),
    ('Speaker says Joe is nine months old today.', 'Speaker mentions their baby Joe.'),
])
def test_recording_claims_use_supported_speech_through_persisted_caller(summary,activity):
    evidence = recording()
    # Retain the fixture's valid source geometry while supplying a complete
    # recognized phrase; this is synthetic contract evidence, not a human label.
    phrase = 'Look at their face. Joe is almost seven months old today. Oh, the battery is almost dead.'
    evidence['utterances'][0]['text'] = phrase
    projection = project_audio(evidence, [{'scene_id':'s','start':0.,'end':2.}])['s']
    audio = legacy_audio(projection)
    segment = dict(audio, scene_id='s', start=0., end=2., content_state='signal', full_transcript=audio['transcript'])
    lookup = {'s':{'scene_id':'s','index':0,'audio':audio}}
    class Quotes(Client):
        def chat(self, **kwargs):
            return {'choices':[{'message':{'content':json.dumps({
                'narrative_summary':summary,
                'activity_description':activity,
                'key_moments':['Look at their face.'], 'emotional_arc':'happy','context_tags':[]})}}]}
    harmonizer._apply_scene_context_llm([segment],lookup,{'llm':{'features':{'scene_context_analysis':True}}},llm_client=Quotes())
    manifest = {'scenes':[lookup['s']]}
    harmonizer._persist_harmonized_scene_fields(manifest,[segment])
    result = manifest['scenes'][0]['scene_context_llm']
    for key in ('narrative_summary','activity_description'):
        assert result[key].startswith('Transcript: "') and result[key].endswith('"')
        assert result[key][13:-1] in phrase
        assert result['claim_provenance'][key]['qualification']=='unverified_model_transcript'
    assert result['key_moments']==['Transcript: "Look at their face."']
    assert result['emotion_qualification']['status']=='unqualified'
    assert segment['audio_evidence']==projection


@pytest.mark.parametrize('phrase,claim', [
    ('Joe is not six months old today.', 'Speaker says Joe is six months old today.'),
    ('Joe hit Pat.', 'Speaker says Pat hit Joe.'),
])
def test_speech_framing_does_not_license_changed_meaning_in_persisted_summary(phrase, claim):
    evidence = recording()
    evidence['utterances'][0]['text'] = phrase
    projection = project_audio(evidence, [{'scene_id':'s','start':0.,'end':2.}])['s']
    audio = legacy_audio(projection)
    segment = dict(audio, scene_id='s', start=0., end=2., content_state='signal', full_transcript=audio['transcript'])
    lookup = {'s':{'scene_id':'s','index':0,'audio':audio}}

    class Reversed(Client):
        def chat(self, **kwargs):
            return {'choices':[{'message':{'content':json.dumps({
                'narrative_summary':claim, 'activity_description':claim,
                'key_moments':[claim], 'emotional_arc':'unqualified', 'context_tags':[]})}}]}

    harmonizer._apply_scene_context_llm([segment], lookup,
        {'llm':{'features':{'scene_context_analysis':True}}}, llm_client=Reversed())
    manifest = {'scenes':[lookup['s']]}
    harmonizer._persist_harmonized_scene_fields(manifest, [segment])
    result = manifest['scenes'][0]['scene_context_llm']
    quote = f'Transcript: "{phrase}"'
    assert result['narrative_summary'] == result['activity_description'] == quote
    assert result['key_moments'] == [quote]
    assert result['claim_provenance']['narrative_summary']['qualification'] == 'unverified_model_transcript'
