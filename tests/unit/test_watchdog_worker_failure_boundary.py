"""A failed worker must not complete the standalone image pipeline."""
import json
from pathlib import Path
import subprocess
import types

import pytest

from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg


@pytest.mark.parametrize("raw", [b'null', b'[]', b'{"source_path":"must-not-replace-source","clip_meta":{"status":"error","error":"fixture model failed"}}'])
def test_watchdog_rejects_failed_transport_before_completion(tmp_path, monkeypatch, raw):
    from cli import watchdog, run_ingestion, standalone_persistence
    from steps.common import conda_runner, tool_paths, progress_tracker

    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    processor = watchdog.WatchdogProcessor(_watchdog_cfg(tmp_path))
    source = tmp_path / 'source.png'
    from PIL import Image
    Image.new('RGB', (4, 4)).save(source)
    completed, published, failures = [], [], []
    tracker = types.SimpleNamespace(set_total_steps=lambda *a: None,
                                    update_step=lambda *a: None,
                                    complete_step=completed.append)
    monkeypatch.setattr(progress_tracker, 'get_tracker', lambda: tracker)
    monkeypatch.setattr(progress_tracker, 'add_error', lambda *a: None)
    # Locked model computations are fixtures; the failing CLIP Conda adapter is real.
    monkeypatch.setattr(run_ingestion, '_run_step', lambda *a, **kw: {})
    monkeypatch.setattr(conda_runner, '_resolve_models_root', lambda: str(tmp_path/'models'))
    monkeypatch.setattr(tool_paths, 'resolve_conda', lambda: 'fixture-conda')
    monkeypatch.setattr(standalone_persistence, 'persist_result', lambda *a: published.append(a))
    preserve = standalone_persistence.preserve_failure

    def retain_failure(item, error):
        preserve(item, error)
        saved = json.loads((Path(item['source_path']).parent/'failed_result.json').read_text(encoding='utf-8'))
        assert saved['item']['source_path'] == item['source_path']
        assert 'clip_meta' not in item, 'Failure retention must not mutate the caller aggregate'
        if isinstance(json.loads(raw), dict):
            assert saved['item']['clip_meta']['error'] == 'fixture model failed'
            assert saved['item']['worker_results']['image_embed_clip'] == json.loads(raw)
        failures.append(str(error))

    monkeypatch.setattr(standalone_persistence, 'preserve_failure', retain_failure)

    def transport(cmd, **kw):
        step = cmd[cmd.index('--step') + 1]
        Path(cmd[cmd.index('--out') + 1]).write_bytes(raw if step == 'image_embed_clip' else b'{}')
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(conda_runner.subprocess, 'run', transport)
    with pytest.raises(conda_runner.StepExecutionError):
        processor.ingest_image(source, 'worker-boundary-fixture')
    assert 'image_embed_clip' not in completed and 'persist_result' not in completed
    assert not published
    assert failures
