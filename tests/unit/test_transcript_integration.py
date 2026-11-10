"""Production boundary regressions for transcript provenance integration."""
import copy
import hashlib
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from steps.common import transcript_authority as authority
from scripts.ucf.ucf_ledger import UCFLedgerClient


@pytest.fixture
def producer(tmp_path):
    root = tmp_path / 'epoch-test'
    (root / 'ucf').mkdir(parents=True)
    cfg = {'paths': {'db_dir': str(root)}}
    video = 'a' * 64
    sid = hashlib.sha256(f'scene{video}|0.000|1.000|'.encode()).hexdigest()
    ledger = UCFLedgerClient(str(root / 'ucf/ucf_ledger.db'))
    ledger.init_schema()
    ledger.register_media(video, 'test.mp4', 1, 30, 320, 240)
    scene = {'video_id': video, 'scene_id': sid, 'start': 0, 'end': 1,
             'transcript_outcome': 'transcript_available',
             'transcript_outcome_reason': 'transcript_or_segments_present',
             'audio': {'full_text': 'Hello'}}
    yield cfg, scene, ledger
    ledger.conn.close()


@pytest.mark.parametrize('existing', [False, True])
def test_retired_authority_cannot_insert_or_replay(producer, existing):
    cfg, scene, ledger = producer
    if existing:
        authority.emit(scene, scene['video_id'], 'run-1', cfg)
    fid = ledger.log_frame(video_hash=scene['video_id'], epoch_id='epoch-test',
                           run_id='run-1', t_start=0, t_end=1, modality='audio',
                           worker_name='fixture', model_tag='test',
                           source_artifact_id=scene['scene_id'])
    ev = {'kind': 'scene_retirement', 'version': 1, 'video_hash': scene['video_id'],
          'epoch_id': 'epoch-test', 'scene_id': scene['scene_id'],
          'aliases': [scene['scene_id']], 'frame_ids': [fid],
          'start': 0, 'end': 1, 'vectors': []}
    ledger.log_status_transition('staged', 'superseded', 'fixture',
        video_hash=scene['video_id'], epoch_id='epoch-test',
        scope='scene_retirement:' + scene['scene_id'], evidence=ev, frame_ids=[fid])
    before = ledger.conn.execute('SELECT * FROM context_frames').fetchall()
    with pytest.raises(ValueError, match='retired'):
        authority.emit(scene, scene['video_id'], 'run-1', cfg)
    assert ledger.conn.execute('SELECT * FROM context_frames').fetchall() == before


def test_authority_cas_promotion_and_text_validation(producer):
    from steps.common import transcript_binding as binding
    cfg, scene, ledger = producer
    record = authority.emit(scene, scene['video_id'], 'run-1', cfg)
    assert authority.emit(scene, scene['video_id'], 'run-1', cfg) == record
    with pytest.raises(ValueError, match='stale'):
        authority.emit(scene, scene['video_id'], 'run-2', cfg)
    next_record = authority.emit(scene, scene['video_id'], 'run-2', cfg, authority.sha(record))
    assert binding.validate(next_record, next_record, 'changed')['status'] == 'unverified'
    ledger.conn.execute("UPDATE context_frames SET promotion_status='promoted'")
    ledger.conn.commit()
    assert authority.lookup(scene['video_id'], scene['scene_id'], cfg) == next_record
    with pytest.raises(ValueError, match='ambiguous or corrupt'):
        authority.emit(scene, scene['video_id'], 'run-2', cfg)


@pytest.mark.parametrize('endpoint', ['text', 'visual', 'multimodal'])
def test_http_projects_once_per_timeline_and_refreshes_next_request(producer, monkeypatch, endpoint):
    search = importlib.import_module('api.routes.search')
    cfg, scene, _ = producer
    record = authority.emit(scene, scene['video_id'], 'run-1', cfg)
    timeline = {'video_id': scene['video_id'], 'segments': [{
        'scene_id': scene['scene_id'], 'start': 0, 'end': 1,
        'full_transcript': 'Hello', 'transcript_outcome_evidence': {'status': 'bound', **record}}]}

    class Loader:
        duplicate = False
        calls = 0
        def list_processed_videos(self):
            return [str(i) for i in range(100)]
        def load_temporal_index(self, key):
            self.calls += 1
            return copy.deepcopy(timeline if key == '0' or (self.duplicate and key == '1')
                                 else {'video_id': key, 'segments': []})
        def get_video_metadata(self, key):
            return {}

    loader = Loader()
    results = [{'score': .5, 'modality': 'text', 'payload': {
        **{k: record[k] for k in ('video_id', 'scene_id', 'run_id', 'epoch_id')},
        'text': 'Hello'}} for _ in range(10)]

    class Engine:
        weight_text = .5
        weight_visual = .3
        weight_audio = .2

        def _reset_search_diagnostics(self):
            pass

        def search_text(self, *args, **kwargs):
            return copy.deepcopy(results)

        search_visual = search_text
        search_multimodal = search_text

    monkeypatch.setattr(search, '_config', cfg)
    monkeypatch.setattr(search, 'get_data_loader', lambda: loader)
    monkeypatch.setattr(search, 'get_search_engine', lambda: Engine())
    monkeypatch.setattr(search, '_search_audio_vector_proof', lambda *args: {})
    app = FastAPI()
    app.include_router(search.router)
    with TestClient(app) as client:
        def request():
            if endpoint == 'multimodal':
                return client.post('/api/search/multimodal', json={'query': 'hello', 'top_k': 10, 'modalities': ['text']})
            return client.get('/api/search/' + endpoint, params={'q': 'hello', 'top_k': 10})

        first = request()
        assert first.status_code == 200, first.text
        rows = first.json()['results']
        assert len(rows) == 10 and all(r['score'] == .5 for r in rows)
        assert all(r['transcript_outcome_evidence']['status'] == 'bound' for r in rows)
        assert loader.calls == 100
        loader.duplicate = True
        second = request()
        assert second.status_code == 200, second.text
        assert loader.calls == 200
        assert all(r['transcript_outcome_evidence']['reason'] == 'source_missing_or_ambiguous'
                   for r in second.json()['results'])
