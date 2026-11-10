import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.identity_resolver import IdentityResolver
from scripts.ucf.ucf_ledger import UCFLedgerClient
from steps.common.memory import _make_id


def _fixture(tmp_path):
    epoch = tmp_path / 'epoch_disposable_identity'
    (epoch / 'ucf').mkdir(parents=True)
    roster = epoch / 'family_roster.yaml'
    roster.write_text('identities:\n- id: dad\n  display_name: Dad\n', encoding='utf-8')
    kg = epoch / 'knowledge_graph.db'
    target = _make_id('scene', ['source', '0.000', '10.000'])
    neighbor = _make_id('scene', ['source', '10.000', '20.000'])
    with sqlite3.connect(kg) as db:
        db.executescript('CREATE TABLE nodes(id INTEGER PRIMARY KEY,node_type TEXT,name TEXT,properties TEXT);'
                        'CREATE TABLE edges(source_id INTEGER,target_id INTEGER,edge_type TEXT);')
        db.executemany('INSERT INTO nodes VALUES(?,?,?,?)', [
            (1, 'Person', 'dad', '{}'), (2, 'scene', target, '{}'),
            (3, 'scene', neighbor, '{}'), (4, 'video', 'source', '{}')])
        db.executemany('INSERT INTO edges VALUES(?,?,?)', [
            (1, 2, 'person_appears_in_scene'), (1, 3, 'person_mentioned_in_scene'),
            (4, 2, 'video_contains_scene'), (4, 3, 'video_contains_scene')])
    ledger = epoch / 'ucf/ucf_ledger.db'
    client = UCFLedgerClient(str(ledger))
    client.init_schema()
    client.conn.close()
    evidence = {'kind': 'scene_retirement', 'version': 1, 'epoch_id': epoch.name,
                'video_hash': 'source', 'scene_id': target, 'aliases': [target],
                'frame_ids': [1], 'start': 0., 'end': 10., 'vectors': []}
    return epoch, roster, kg, ledger, target, neighbor, evidence


def _retire(ledger, evidence):
    with sqlite3.connect(ledger) as db:
        UCFLedgerClient.insert_status_transition(db, old_status='promoted', new_status='superseded',
            tool_name='supersede_ucf_frames', video_hash='source', epoch_id=evidence['epoch_id'],
            scope='scene_retirement:' + evidence['scene_id'], evidence=evidence, frame_ids=[1])


def test_cached_person_search_excludes_committed_retirement_before_kg_delivery(tmp_path):
    epoch, roster, kg, ledger, target, neighbor, evidence = _fixture(tmp_path)
    resolver = IdentityResolver(str(roster), str(kg), enabled=True)
    assert set(resolver.get_identity_scene_evidence('Dad')) == {target, neighbor}
    assert resolver.get_scenes_for_person('dad') == {target, neighbor}
    _retire(ledger, evidence)
    assert set(resolver.get_identity_scene_evidence('Dad')) == {neighbor}
    assert resolver.get_scenes_for_person('dad') == {neighbor}


@pytest.mark.parametrize('route,key', [('scene-evidence', 'scene_refs'), ('scene-context', 'scenes')])
def test_identity_http_readers_exclude_retirement_before_kg_delivery(tmp_path, monkeypatch, route, key):
    from api.routes import identity
    epoch, roster, kg, ledger, target, neighbor, evidence = _fixture(tmp_path)
    monkeypatch.setenv('GOODQ_IDENTITY_PATH', str(epoch))
    monkeypatch.setattr(identity, '_CFG', {'epoch_id': epoch.name,
        'paths': {'db_path': str(epoch / 'memory.db'), 'db_dir': str(epoch)},
        'identity_search': {'roster_path': str(roster), 'kg_db_path': str(kg)}})
    app = FastAPI()
    app.include_router(identity.router)
    _retire(ledger, evidence)
    with TestClient(app) as client:
        response = client.get('/api/identity/' + route, params={'subjects': 'Dad', 'limit': 10})
    assert response.status_code == 200, response.text
    assert {row['scene_id'] for row in response.json()[key]} == {neighbor}


def test_corrupt_retirement_does_not_become_cached_identity_success(tmp_path):
    epoch, roster, kg, ledger, target, neighbor, evidence = _fixture(tmp_path)
    resolver = IdentityResolver(str(roster), str(kg), enabled=True)
    assert resolver.get_identity_scene_evidence('Dad')
    evidence['aliases'] = []
    _retire(ledger, evidence)
    with pytest.raises(ValueError, match='Corrupt scene retirement'):
        resolver.get_identity_scene_evidence('Dad')
