"""Caller filters must survive real SQLite lexical retrieval and hybrid fusion."""
import json
import sqlite3

import numpy as np
import pytest

from retrieval.multimodal_search import MultimodalSearchEngine
from scripts.ucf.ucf_ledger import UCFLedgerClient
from steps.common.memory import _connect
from steps.common import transcript_authority


@pytest.fixture(params=[True, False], ids=['sqlite-match', 'sqlite-like'])
def lexical_engine(tmp_path, monkeypatch, request):
    root = tmp_path / 'scope-epoch'
    root.mkdir()
    (root / 'ucf').mkdir()
    cfg = {'paths': {'db_dir': str(root), 'db_path': str(root / 'memory.db')}}
    ledger = UCFLedgerClient(str(root / 'ucf/ucf_ledger.db'))
    ledger.init_schema()
    ledger.register_media('video-a', 'fixture.wav', 1, 30, 320, 240)
    conn = _connect(cfg['paths']['db_path'])
    for sid, bound in [('bound', True), ('legacy', False)]:
        scene = {'video_id': 'video-a', 'scene_id': sid, 'start': 0, 'end': 1,
                 'transcript_outcome': 'transcript_available',
                 'transcript_outcome_reason': 'transcript_or_segments_present',
                 'audio': {'full_text': 'meeting tomorrow'}}
        if bound:
            scene['transcript_outcome_evidence'] = transcript_authority.emit(scene, 'video-a', 'current-run', cfg)
        conn.execute('INSERT INTO scenes(id,video_hash,start,end,meta,created_at) VALUES (?,?,?,?,?,?)',
                     (sid, 'video-a', 0, 1, json.dumps(scene), '2026-11-03'))
        conn.execute('INSERT INTO scene_text_fts(scene_id,video_hash,content_type,text) VALUES (?,?,?,?)',
                     (sid, 'video-a', 'transcript', 'meeting tomorrow'))
    conn.commit()
    conn.close()
    ledger.close()
    engine = MultimodalSearchEngine(cfg)
    monkeypatch.setattr(engine, 'encode_text_query', lambda _: np.zeros(384))
    monkeypatch.setattr(engine, '_is_fts5_available', lambda _: request.param)
    return engine


def search(engine, condition=None):
    return engine.search_text('meeting', payload_filter=condition, retrieval_context='system.healthcheck')


@pytest.mark.parametrize('key,value', [('video_hash', 'other-video'), ('run_id', 'wrong-run'), ('epoch_id', 'wrong-epoch')])
def test_wrong_scope_cannot_leak_through_sqlite(lexical_engine, key, value):
    assert len(search(lexical_engine)) == 2
    assert search(lexical_engine, {'must': [{'key': key, 'match': {'value': value}}]}) == []


def test_verified_scope_survives_and_missing_provenance_does_not_match(lexical_engine):
    result = search(lexical_engine, {'must': [{'key': 'run_id', 'match': {'value': 'current-run'}}]})
    assert [r['id'] for r in result] == ['bound']
    assert result[0]['payload']['epoch_id'] == 'scope-epoch'
    assert len(search(lexical_engine)) == 2


def test_boolean_filters_do_not_invert_unsupported_predicates(lexical_engine):
    selected = {'must': {'key': 'video_hash', 'match': {'value': 'video-a'}},
                'should': [{'key': 'scene_id', 'match': {'value': 'bound'}}],
                'must_not': [{'key': 'run_id', 'match': {'value': 'wrong-run'}}]}
    assert [r['id'] for r in search(lexical_engine, selected)] == ['bound']
    assert search(lexical_engine, {'must_not': [{'is_empty': {'key': 'run_id'}}]}) == []
    assert lexical_engine._last_search_diagnostics['text_lexical']['reason'] == 'unsupported_lexical_payload_filter'
    assert len(search(lexical_engine)) == 2
    assert 'text_lexical' not in lexical_engine._last_search_diagnostics


def test_filtered_fallback_reaches_eligible_rows_after_candidate_limit(lexical_engine):
    with sqlite3.connect(lexical_engine.db_path) as conn:
        # Keep both MATCH relevance and LIKE insertion order ahead of the target.
        conn.execute('DELETE FROM scene_text_fts')
        for n in range(25):
            sid = f'excluded-{n}'
            conn.execute('INSERT INTO scenes(id,video_hash,start,end,meta,created_at) VALUES (?,?,?,?,?,?)',
                         (sid, 'other-video', 0, 1, '{}', '2026-11-03'))
            conn.execute('INSERT INTO scene_text_fts(scene_id,video_hash,content_type,text) VALUES (?,?,?,?)',
                         (sid, 'other-video', 'transcript', 'meeting'))
        conn.execute('INSERT INTO scene_text_fts(scene_id,video_hash,content_type,text) VALUES (?,?,?,?)',
                     ('bound', 'video-a', 'transcript', 'meeting tomorrow'))
    result = search(lexical_engine, {'must': [{'key': 'run_id', 'match': {'value': 'current-run'}}]})
    assert [r['id'] for r in result] == ['bound']


def test_single_condition_shape_reaches_semantic_and_lexical_callers(lexical_engine, monkeypatch):
    calls = []
    class Client:
        def query(self, vector, top_k, **options):
            calls.append(options['payload_filter'])
            return []
    monkeypatch.setattr(lexical_engine, 'encode_text_query', lambda _: np.ones(384))
    monkeypatch.setattr(lexical_engine, '_get_qdrant_client', lambda _: Client())
    condition = {'must': {'key': 'run_id', 'match': {'value': 'current-run'}}}
    assert [r['id'] for r in search(lexical_engine, condition)] == ['bound']
    assert calls and calls[0]['must'][0] == condition['must']
    assert isinstance(condition['must'], dict), 'Caller filter was mutated'


def test_advanced_vector_filter_does_not_admit_unfiltered_lexical_hits(lexical_engine, monkeypatch):
    class Client:
        def query(self, vector, top_k, **options):
            assert options['payload_filter']['must'][0]['range'] == {'gte': 0}
            return [{'id': 'vector-point', 'score': .9,
                     'payload': {'scene_id': 'bound', 'video_hash': 'video-a'}}]
    monkeypatch.setattr(lexical_engine, 'encode_text_query', lambda _: np.ones(384))
    monkeypatch.setattr(lexical_engine, '_get_qdrant_client', lambda _: Client())
    result = search(lexical_engine, {'must': [{'key': 'start', 'range': {'gte': 0}}]})
    assert [r['id'] for r in result] == ['vector-point']
    assert lexical_engine._last_search_diagnostics['text_lexical']['status'] == 'unavailable'
