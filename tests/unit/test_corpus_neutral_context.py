"""Corpus-neutral evidence must survive production context and search callers."""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from steps.video import cross_modal_harmonizer as harmonizer
from tests.unit.test_audio_summary_evidence import Client, run, scene


@pytest.mark.parametrize('transcript,forbidden', [
    ('Mr. Pocatillo brought the seedlings today.', 'Steve'),
    ('A claw was printed on the invitation.', 'deformed hand'),
    ('We discussed a counter offer yesterday.', 'business deal'),
])
def test_context_caller_never_expands_source_words(transcript, forbidden):
    segment, lookup = scene([])
    segment['full_transcript'] = transcript
    client = Client(summary='Conversation.')
    result = run(segment, lookup, client)
    manifest = {'scenes': [dict(deepcopy(lookup['s']), scene_id='s')]}
    harmonizer._persist_harmonized_scene_fields(manifest, [segment])
    assert forbidden.casefold() not in json.dumps(client.calls).casefold()
    assert forbidden.casefold() not in json.dumps(result).casefold()
    assert manifest['scenes'][0]['scene_context_llm'] == result
    assert segment['full_transcript'] == transcript


@pytest.mark.parametrize('topic', ['lunch', 'baby', 'glove compartment', 'blue backpack', 'solar observatory'])
def test_context_caller_keeps_explicit_topics_without_a_corpus_allowlist(topic):
    segment, lookup = scene([])
    segment['full_transcript'] = f'We are talking about the {topic} today.'
    client = Client(summary=f'Conversation about {topic}.')
    client.tags = [topic]
    result = run(segment, lookup, client)
    assert topic in result['context_tags']
    assert result['claim_provenance']['tag_sources'][topic]['scope'] == 'spoken_mention'
    assert result['claim_provenance']['tag_sources'][topic]['establishes_visible_presence'] is False


@pytest.mark.parametrize('query,phrase', [
    ('complaint', 'what woman is coming in'),
    ('complaint', 'no one has any interest'),
    ('awkward', "you're back"),
    ('Maya complaint', 'what woman is coming in'),
    ('Maya complaint', 'no one has any interest'),
    ('Maya awkward', "you're back"),
])
def test_search_api_rewards_query_evidence_without_scripted_phrase_bonuses(tmp_path, monkeypatch, query, phrase):
    from api.main import app
    from api.routes import search
    from api.utils.loaders import DataLoader
    from retrieval.multimodal_search import MultimodalSearchEngine
    import numpy as np

    engine = MultimodalSearchEngine({'paths': {'db_path': str(tmp_path / 'memory.db')}})
    preview = ['Maya says: A visitor arrives.']
    class VectorStore:
        def query(self, vector, top_k, **kwargs):
            return [{'id': 'point', 'score': .8,
                     'payload': {'video_id': 'v', 'scene_id': 's', 'text_preview': preview[0]}}]
    monkeypatch.setattr(engine, '_get_qdrant_client', lambda *a: VectorStore())
    monkeypatch.setattr(engine, 'encode_text_query', lambda q: np.ones(3))
    monkeypatch.setattr(engine, 'search_fts', lambda *a, **kw: [])
    monkeypatch.setattr(search, '_search_engine', engine)
    monkeypatch.setattr(search, '_config', {'identity_search': {'enabled': False}})
    monkeypatch.setattr(search, '_data_loader', DataLoader(processing_root=str(tmp_path / 'processing')))
    client = TestClient(app, client=('127.0.0.1', 50000))
    baseline = client.get('/api/search/text', params={'q': query} )
    preview[0] = 'Maya says: ' + phrase
    actual = client.get('/api/search/text', params={'q': query})
    assert baseline.status_code == actual.status_code == 200
    assert actual.json()['results'][0]['score'] == baseline.json()['results'][0]['score']
    preview[0] = 'Maya says: ' + query
    supported = client.get('/api/search/text', params={'q': query})
    assert supported.status_code == 200
    assert supported.json()['results'][0]['score'] > baseline.json()['results'][0]['score']


@pytest.mark.parametrize('full,partial', [('Jerry Seinfeld', 'Jerry'), ('Rosa Martinez', 'Rosa')])
def test_full_name_reduction_is_reported_without_person_specific_exceptions(full, partial):
    segment = {'scene_id': 's', 'full_transcript': f'{full} is waiting outside.',
               'mentioned_people': [{'text': partial, 'type': 'PERSON'}]}
    result = harmonizer._segment_transcript_entity_projection(segment)
    assert result['normalization_applied'] is False
    assert [r['category'] for r in result['disagreements']] == ['transcript_full_name_reduced_to_partial_entity']


@pytest.mark.parametrize('candidate,transcript,expected', [
    ('pen', 'Open the cabinet.', False),
    ('Rosa Martinez', 'Rosa spoke to Alex Martinez.', False),
    ('solar observatory', 'Visit the SOLAR   observatory.', True),
    ('sing songy quality', 'It has a sing-songy quality.', False),
])
def test_topic_grounding_requires_contiguous_source_words(candidate, transcript, expected):
    from steps.common.context_analyzer_llm import _is_transcript_grounded_topic_candidate
    assert _is_transcript_grounded_topic_candidate(candidate, transcript) is expected
