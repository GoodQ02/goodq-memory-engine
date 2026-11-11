"""Same-time recording events survive the real audio ledger caller and replay."""
from copy import deepcopy
import json
import sqlite3
import pytest

from cli.run_ingestion import _log_audio_to_ucf_ledger
from scripts.ucf.ucf_ledger import UCFLedgerClient
from tests.unit.test_audio_engine_enrichment import inputs
from wsl2_audio.enrichment import attach_observations
from wsl2_audio.scene_projection import project_audio, legacy_audio


def audio_fixture():
    evidence, observations = inputs()
    evidence['source']['channels'] = 2
    other = deepcopy(evidence['utterances'][0])
    other.update(id=other['id']+'-channel1', channel=1)
    evidence['utterances'].append(other)
    for stage in evidence['stages'].values():
        if 'channel_assessed_spans' in stage:
            stage['channel_assessed_spans']['1'] = deepcopy(stage['channel_assessed_spans']['0'])
    for stage in observations.values():
        stage['channel_assessed_spans']['1'] = deepcopy(stage['channel_assessed_spans']['0'])
        for key in ('tracks', 'single_activity', 'regions', 'speech_intervals'):
            if key in stage:
                stage[key] += [dict(deepcopy(row), channel=1) for row in stage[key]]
    evidence = attach_observations(evidence, observations)
    evidence.update(status='ok', quality_qualification='unqualified')
    scene = {'scene_id':'scene', 'start':0., 'end':2.}
    audio = legacy_audio(project_audio(evidence, [scene])['scene'])
    audio['audio_text_embed_meta'] = {'status':'ok', 'embedding_id':'vector',
        'vector_collection':None, 'qdrant_committed':False, 'faiss_id':1}
    return evidence['source']['sha256'], scene, audio


def test_same_time_channels_survive_production_logging_and_replay(tmp_path):
    source, scene, audio = audio_fixture()
    assert len(audio['segments']) == 1
    assert 'unreconciled_channel_alternatives' in audio['segments'][0]
    root = tmp_path/'epoch'; (root/'ucf').mkdir(parents=True)
    db_path = root/'ucf/ucf_ledger.db'
    client = UCFLedgerClient(str(db_path)); client.init_schema()
    client.register_media(source, 'source.wav', 2., 0., 0, 0); client.close()
    cfg = tmp_path/'config.json'
    cfg.write_text(json.dumps({'paths':{'db_dir':str(root)}, 'run':{'id':'test'}}))
    artifacts = tmp_path/'artifacts'; artifacts.mkdir()
    snapshots = []
    for _ in range(2):
        _log_audio_to_ucf_ledger(cfg, source, 'scene', scene, artifacts, audio, strict=True)
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute('SELECT * FROM context_frames ORDER BY frame_id')]
        for worker in ('audio_transcribe', 'speaker_merge'):
            events = [r for r in rows if r['worker_name']==worker]
            assert len(events)==2
            assert len({(r['t_start'],r['t_end']) for r in events})==1
            assert len({r['occurrence_id'] for r in events})==2
        vector, = [r for r in rows if r['worker_name']=='text_embed']
        assert vector['vector_backend']=='faiss' and vector['vector_collection']=='text'
        snapshots.append(rows)
    assert snapshots[0]==snapshots[1]


LEGACY_TABLE = """CREATE TABLE context_frames (
frame_id INTEGER PRIMARY KEY AUTOINCREMENT, video_hash TEXT NOT NULL,
ucf_schema_version TEXT NOT NULL, epoch_id TEXT NOT NULL, run_id TEXT NOT NULL,
t_start REAL NOT NULL, t_end REAL NOT NULL, modality TEXT NOT NULL,
worker_name TEXT NOT NULL, model_tag TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 1,
spatial_region TEXT, spatial_space TEXT NOT NULL DEFAULT 'normalized_yxyx_top_left',
vector_key TEXT, vector_backend TEXT, vector_collection TEXT, vector_dim INTEGER,
vector_model_tag TEXT, source_artifact_id TEXT, raw_ref TEXT,
payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
promotion_status TEXT NOT NULL DEFAULT 'staged', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (video_hash) REFERENCES media_sources(video_hash),
UNIQUE(video_hash, epoch_id, modality, worker_name, t_start, t_end))"""


def legacy_db(path):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE media_sources(video_hash TEXT PRIMARY KEY, file_path TEXT NOT NULL, duration REAL NOT NULL, fps REAL NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        db.execute("INSERT INTO media_sources(video_hash,file_path,duration,fps,width,height) VALUES ('source','source.wav',10,0,0,0)")
        db.execute(LEGACY_TABLE)
        payload = json.dumps({'utterance_id':'utterance1','text':'preserved'})
        db.execute("INSERT INTO context_frames(frame_id,video_hash,ucf_schema_version,epoch_id,run_id,t_start,t_end,modality,worker_name,model_tag,source_artifact_id,payload,payload_hash,promotion_status) VALUES (7,'source','ucf.v0.1','epoch','run',1,2,'text','audio_transcribe','recording_audio_v1','scene',?,'retained-hash','promoted')", (payload,))
        db.execute("UPDATE sqlite_sequence SET seq=99 WHERE name='context_frames'")
        db.execute('CREATE TABLE external_links(frame_id INTEGER REFERENCES context_frames(frame_id))')
        db.execute('INSERT INTO external_links VALUES (7)')
        db.execute('CREATE TABLE changes(frame_id INTEGER)')
        db.execute('CREATE TRIGGER retain_audit AFTER UPDATE ON context_frames BEGIN INSERT INTO changes VALUES (NEW.frame_id); END')
        db.execute('CREATE INDEX custom_scene_index ON context_frames(source_artifact_id)')
        return db.execute('SELECT * FROM context_frames').fetchall()


def test_migration_preserves_frames_references_status_and_backup(tmp_path):
    path=tmp_path/'ledger.db'; before=legacy_db(path)
    client=UCFLedgerClient(str(path)); client.conn.execute('PRAGMA foreign_keys=ON')
    client.init_schema(); client.init_schema()
    assert client.conn.execute('SELECT * FROM context_frames').fetchone()[:-1]==before[0]
    columns=[r[1] for r in client.conn.execute('PRAGMA table_info(context_frames)') if r[1]!='occurrence_id']
    assert client.conn.execute('SELECT '+','.join(columns)+' FROM context_frames').fetchall()==before
    assert client.conn.execute('PRAGMA foreign_keys').fetchone()==(1,)
    assert client.conn.execute('PRAGMA foreign_key_check').fetchall()==[]
    assert client.conn.execute('SELECT * FROM external_links').fetchall()==[(7,)]
    assert client.conn.execute('SELECT * FROM changes').fetchall()==[]
    occurrence=client.conn.execute('SELECT occurrence_id FROM context_frames').fetchone()[0]
    assert occurrence
    from scripts.ucf.ucf_ledger import audio_occurrence_id
    assert occurrence==audio_occurrence_id('source','scene','audio_transcribe',{'utterance_id':'utterance1'})
    args=dict(video_hash='source',epoch_id='epoch',run_id='run2',t_start=1,t_end=2,
        modality='text',worker_name='audio_transcribe',model_tag='recording_audio_v1',
        source_artifact_id='scene',payload={'utterance_id':'utterance1','text':'preserved'})
    assert client.log_frame(**args,occurrence_id=occurrence,promotion_status='promoted')==7
    assert client.conn.execute('SELECT * FROM changes').fetchall()==[(7,)]
    assert client.log_frame(**dict(args,worker_name='legacy'))>99
    # Legacy callers keep timestamp upsert identity and get the actual existing ID.
    legacy=client.log_frame(**dict(args,worker_name='legacy'))
    assert client.log_frame(**dict(args,worker_name='legacy'))==legacy
    backups=list(tmp_path.glob('*.pre-occurrence-v1.*.sqlite')); assert len(backups)==1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute('SELECT * FROM context_frames').fetchall()==before
        assert 'occurrence_id' not in {r[1] for r in backup.execute('PRAGMA table_info(context_frames)')}
    client.close()


def test_migration_failure_rolls_back_original_rows_and_schema(tmp_path):
    path=tmp_path/'ledger.db'; before=legacy_db(path)
    client=UCFLedgerClient(str(path))
    # Malformed candidate identity must not turn into guessed historical data.
    client.conn.execute("UPDATE context_frames SET payload='{}'"); client.conn.commit()
    before=client.conn.execute('SELECT * FROM context_frames').fetchall()
    with pytest.raises(ValueError,match='native utterance ID'):
        client.init_schema()
    assert client.conn.execute('SELECT * FROM context_frames').fetchall()==before
    assert 'occurrence_id' not in {r[1] for r in client.conn.execute('PRAGMA table_info(context_frames)')}
    assert not client.conn.execute("SELECT name FROM sqlite_master WHERE name='context_frames_occurrences'").fetchall()
    assert len(list(tmp_path.glob('*.pre-occurrence-v1.*.sqlite')))==1
    client.close()


def test_migration_failure_after_drop_restores_table_and_indexes(tmp_path):
    path=tmp_path/'ledger.db'; before=legacy_db(path)
    client=UCFLedgerClient(str(path))
    client.conn.set_authorizer(lambda operation,*_: sqlite3.SQLITE_DENY if operation==sqlite3.SQLITE_ALTER_TABLE else sqlite3.SQLITE_OK)
    with pytest.raises(sqlite3.DatabaseError,match='authorized'):
        client.init_schema()
    # Python 3.10's sqlite wrapper does not support None for this callback.
    client.conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
    assert client.conn.execute('SELECT * FROM context_frames').fetchall()==before
    assert client.conn.execute("SELECT name FROM sqlite_master WHERE name IN ('custom_scene_index','retain_audit') ORDER BY name").fetchall()==[('custom_scene_index',),('retain_audit',)]
    assert 'occurrence_id' not in {r[1] for r in client.conn.execute('PRAGMA table_info(context_frames)')}
    client.close()


def test_wsl_unified_same_span_segments_survive_logging_replay_and_reconciliation(tmp_path, monkeypatch):
    source = 'a' * 64
    from scripts.ucf.validate_ucf_epoch import make_scene_hash, run_validation

    scene_start, scene_end = 0.0, 30.0
    scene_id = make_scene_hash(source, scene_start, scene_end)
    scene = {'scene_id': scene_id, 'start': scene_start, 'end': scene_end, 'index': 0}

    epoch_dir = tmp_path / 'epochs' / 'epoch_test_same_span'
    (epoch_dir / 'ucf').mkdir(parents=True)
    proc_video_dir = epoch_dir / 'processing' / 'sample_clip'
    audio_dir = proc_video_dir / 'audio'
    video_dir = proc_video_dir / 'video'
    audio_dir.mkdir(parents=True)
    video_dir.mkdir(parents=True)

    segments = [
        {'start': 10.0, 'end': 14.0, 'text': 'first', 'speaker': 'SPEAKER_00', 'timing_scope': 'containing_segment'},
        {'start': 11.2, 'end': 11.8, 'text': 'interjection', 'speaker': 'SPEAKER_01', 'timing_scope': 'word'},
        {'start': 10.0, 'end': 14.0, 'text': 'continuation', 'speaker': 'SPEAKER_00', 'timing_scope': 'containing_segment'},
        {'start': 10.0, 'end': 14.0, 'text': 'closing', 'speaker': None, 'timing_scope': 'containing_segment'},
    ]
    speaker_turns = [
        {'start': 10.0, 'end': 14.0, 'speaker': 'SPEAKER_00'},
        {'start': 10.0, 'end': 14.0, 'speaker': 'SPEAKER_01'},
    ]
    (audio_dir / f'{scene_id}_raw_transcript.json').write_text(json.dumps(segments), encoding='utf-8')
    (audio_dir / f'{scene_id}_raw_diarization.json').write_text(json.dumps(speaker_turns), encoding='utf-8')
    (video_dir / 'scene_manifest.json').write_text(
        json.dumps({'scenes': [{'index': 0, 'start': scene_start, 'end': scene_end, 'scene_id': scene_id}]}),
        encoding='utf-8',
    )

    db_path = epoch_dir / 'ucf' / 'ucf_ledger.db'
    client = UCFLedgerClient(str(db_path))
    client.init_schema()
    source_file = tmp_path / 'sample_clip.mp4'
    source_file.write_bytes(b'placeholder')
    client.register_media(source, str(source_file), 30.0, 29.97, 720, 480)
    raw_manifest = str((video_dir / 'scene_manifest.json').resolve())
    client.log_frame(
        video_hash=source,
        epoch_id=epoch_dir.name,
        run_id='run_same_span',
        t_start=scene_start,
        t_end=scene_end,
        modality='video',
        worker_name='video_scene_detect',
        model_tag='pyscenedetect',
        confidence=1.0,
        source_artifact_id=scene_id,
        raw_ref=raw_manifest,
        payload={'scene_index': 0, 'duration': 30.0},
        promotion_status='staged',
    )
    client.close()

    cfg_dict = {
        'paths': {
            'data_root': str(tmp_path),
            'db_dir': str(epoch_dir),
            'db_path': str(epoch_dir / 'memory.db'),
            'processing': str(epoch_dir / 'processing'),
            'reports_dir': str(tmp_path / 'reports'),
        },
        'run': {'id': 'run_same_span'},
    }
    cfg_path = tmp_path / 'config.json'
    cfg_path.write_text(json.dumps(cfg_dict), encoding='utf-8')
    monkeypatch.setenv('GOODQ_RUN_ID', 'run_same_span')

    item = {
        'transcript': 'first interjection continuation closing',
        'language': 'en',
        'segments': segments,
        'speaker_segments': speaker_turns,
    }
    for _ in range(2):
        _log_audio_to_ucf_ledger(cfg_path, source, scene_id, scene, audio_dir, item, strict=True)

    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        tx_rows = [dict(r) for r in db.execute("SELECT * FROM context_frames WHERE worker_name='audio_transcribe' ORDER BY frame_id")]
        sp_rows = [dict(r) for r in db.execute("SELECT * FROM context_frames WHERE worker_name='speaker_merge' ORDER BY frame_id")]

    assert len(tx_rows) == 4
    assert len({r['occurrence_id'] for r in tx_rows}) == 4
    assert all(r['occurrence_id'] for r in tx_rows)
    assert [json.loads(r['payload'])['segment_index'] for r in tx_rows] == [0, 1, 2, 3]
    assert len(sp_rows) == 2
    assert len({r['occurrence_id'] for r in sp_rows}) == 2

    rc = run_validation(mode='offline', report_dir=tmp_path / 'reports', config=cfg_dict)
    report = json.loads((tmp_path / 'reports' / 'ucf_validation_report.json').read_text(encoding='utf-8'))
    assert rc == 0, report
    assert report['raw_reconciliation']['status'] == 'passed', report['raw_reconciliation']
