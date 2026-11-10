"""Exercise the inbox caller with dispatch disabled and disposable persisted evidence."""
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import cli.watchdog as watchdog
from steps.common import progress_tracker as progress
from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg


@pytest.fixture
def retained(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, 'CONTROL_AGENT_AVAILABLE', False)
    monkeypatch.setattr(progress._tracker, 'progress_file', tmp_path / 'progress.json')
    monkeypatch.setattr(progress._tracker, 'current_state', {'status': 'idle'})
    cfg = _watchdog_cfg(tmp_path)
    proc = watchdog.WatchdogProcessor(cfg)
    source = proc.watch_dir / 'clip.mp4'
    source.write_bytes(b'retained-source')
    digest = watchdog.FileState(source).compute_hash()
    folder = proc.processing_dir / source.stem
    (folder / 'video').mkdir(parents=True)
    index = {'video_hash': digest, 'phase6_complete': True, 'total_scenes': 1,
             'segments': [{'scene_id': 'scene-1'}]}
    (folder / 'temporal_index.json').write_text(json.dumps(index))
    manifest = {'video_id': digest, 'phase6_complete': True, 'phase6_status': 'complete',
                'phase6_vector_commit': {'enabled': True, 'qdrant_ok': True},
                'scenes': [{'scene_id': 'scene-1', 'clip_id': 'c', 'dino_id': 'd', 'qdrant_ok': True}]}
    (folder / 'video/scene_manifest.json').write_text(json.dumps(manifest))
    ledger = Path(cfg['paths']['db_dir']) / 'ucf/ucf_ledger.db'
    ledger.parent.mkdir()
    with sqlite3.connect(ledger) as db:
        db.execute('CREATE TABLE context_frames(video_hash TEXT,worker_name TEXT)')
        db.execute('INSERT INTO context_frames VALUES(?,?)', (digest, 'video_scene_detect'))
    def forbidden(*args, **kwargs):
        pytest.fail('The reconciliation caller must not dispatch ingestion')
    monkeypatch.setattr(watchdog.WatchdogProcessor, 'process_file', forbidden)
    monkeypatch.setattr(watchdog.FileState, 'is_stable', lambda self: True)
    return proc, cfg, source, digest, folder


def scan(proc, monkeypatch):
    monkeypatch.setattr(watchdog, 'time', SimpleNamespace(time=time.time, sleep=lambda _: proc.shutdown.set()))
    proc.monitor_loop()


def test_missing_registry_reconciles_once_without_dispatch(retained, monkeypatch):
    proc, cfg, source, digest, _ = retained
    scan(proc, monkeypatch)
    assert proc.registry.is_processed(digest)
    assert proc.queue.empty() and not source.exists()
    assert progress.get_state()['status'] == 'completed'
    restarted = watchdog.WatchdogProcessor(cfg)
    scan(restarted, monkeypatch)
    assert restarted.queue.empty()
    assert len(list(proc.processed_dir.iterdir())) == 1


def test_retained_completion_preserves_earlier_request_failure(retained, monkeypatch):
    proc, cfg, source, digest, _ = retained
    proc.registry.mark_failed(digest, 'earlier-request__clip.mp4', 'prior failure', run_id='prior')
    prior = dict(proc.registry.processed[digest])
    scan(proc, monkeypatch)
    restarted = watchdog.WatchdogProcessor(cfg)
    latest = restarted.registry.processed[digest]
    assert latest['status'] == 'success' and latest['original_name'] == source.name
    assert latest['previous_attempts'] == [prior]
    assert not source.exists() and proc.queue.empty()


@pytest.mark.parametrize('invalid', ['wrong_source', 'missing_manifest', 'missing_ledger'])
def test_stale_registry_success_cannot_override_persistence(retained, monkeypatch, invalid):
    proc, cfg, source, digest, folder = retained
    proc.registry.mark_processed(digest, source.name)
    if invalid == 'wrong_source':
        path = folder / 'temporal_index.json'
        data = json.loads(path.read_text()); data['video_hash'] = 'different-source'
        path.write_text(json.dumps(data))
    elif invalid == 'missing_manifest':
        (folder / 'video/scene_manifest.json').unlink()
    else:
        (Path(cfg['paths']['db_dir']) / 'ucf/ucf_ledger.db').unlink()
    scan(proc, monkeypatch)
    assert proc.registry.processed[digest]['status'] == 'failed'
    assert progress.get_state()['status'] == 'failed'
    assert proc.queue.qsize() == 1 and source.exists()
    assert not list(proc.processed_dir.iterdir())
    proc.shutdown.clear(); scan(proc, monkeypatch)
    assert proc.queue.qsize() == 1


@pytest.mark.parametrize('boundary', ['before_move', 'after_move', 'registry_write'])
def test_finalization_restart_preserves_one_source_and_truthful_status(retained, monkeypatch, boundary):
    proc, cfg, source, digest, _ = retained
    original_move = watchdog.safe_move_file
    original_write = watchdog.atomic_write_json
    class Crash(BaseException):
        pass
    def interrupted_move(src, dst):
        if boundary == 'before_move':
            raise OSError('move denied')
        result = original_move(src, dst)
        if boundary == 'after_move':
            raise Crash()
        return result
    def failed_write(path, value):
        if value.get(digest, {}).get('status') == 'success':
            raise OSError('registry write denied')
        return original_write(path, value)
    with monkeypatch.context() as fault:
        fault.setattr(watchdog, 'safe_move_file', interrupted_move)
        if boundary == 'registry_write':
            fault.setattr(watchdog, 'atomic_write_json', failed_write)
        if boundary == 'after_move':
            with pytest.raises(Crash): scan(proc, fault)
        else:
            scan(proc, fault)
        assert progress.get_state()['status'] != 'completed'
    saved = json.loads(proc.state_file.read_text())
    assert saved[digest]['status'] == 'finalizing'
    assert proc.registry.processed[digest]['status'] == 'finalizing'
    restarted = watchdog.WatchdogProcessor(cfg)
    scan(restarted, monkeypatch)
    assert restarted.registry.is_processed(digest) and restarted.queue.empty()
    assert progress.get_state()['status'] == 'completed'
    assert not source.exists()
    assert [p.read_bytes() for p in restarted.processed_dir.iterdir()] == [b'retained-source']


def test_pending_registry_must_be_durable_before_source_movement(retained, monkeypatch):
    proc, _, source, _, _ = retained
    def denied(*args): raise OSError('registry unavailable')
    monkeypatch.setattr(watchdog, 'atomic_write_json', denied)
    scan(proc, monkeypatch)
    assert source.exists() and proc.queue.empty()
    assert not list(proc.processed_dir.iterdir())
    assert progress.get_state()['status'] == 'failed'


def test_unrecoverable_pending_entry_does_not_dispatch_or_block_other_inbox_files(retained, monkeypatch):
    proc, cfg, source, digest, folder = retained
    proc.registry.processed[digest] = {'original_name': source.name, 'status': 'finalizing',
                                     'finalization': {'target_name': 'PROCESSED_clip.mp4'}}
    proc.registry.save()
    (folder / 'video/scene_manifest.json').unlink()
    other = proc.watch_dir / 'other.mp4'; other.write_bytes(b'new unrelated input')
    restarted = watchdog.WatchdogProcessor(cfg)
    scan(restarted, monkeypatch)
    assert restarted.queue.qsize() == 1
    assert restarted.queue.get()[0] == other
    assert restarted.registry.processed[digest]['status'] == 'finalizing'
    assert source.exists() and not list(proc.processed_dir.iterdir())
    assert progress.get_state()['status'] == 'failed'


def test_destination_collision_preserves_other_content(retained, monkeypatch):
    proc, _, source, digest, _ = retained
    neighbor = proc.processed_dir / ('PROCESSED_' + source.name)
    neighbor.write_bytes(b'other-source')
    scan(proc, monkeypatch)
    assert neighbor.read_bytes() == b'other-source'
    assert (proc.processed_dir / 'PROCESSED_clip_1.mp4').read_bytes() == b'retained-source'
    assert proc.registry.is_processed(digest)
