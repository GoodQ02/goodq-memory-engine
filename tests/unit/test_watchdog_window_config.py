"""Configured window settings survive the ordinary Watchdog video caller."""
from pathlib import Path

import pytest

from steps.common.config_loader import load_configs, validate_config_mapping


def test_ordinary_watchdog_passes_validated_windows_to_runner(tmp_path, monkeypatch):
    from cli import watchdog, run_ingestion

    cfg = load_configs({}, include_local=False)
    cfg.update(progressive_chunk_size=30.0, progressive_chunk_overlap=0.0)
    cfg['paths']['processing'] = str(tmp_path/'processing')
    cfg['paths']['log_dir'] = str(tmp_path/'logs')
    cfg = validate_config_mapping(cfg)
    source = tmp_path/'selected.mp4'
    source.write_bytes(b'controlled source; runner intercepted before media compute')
    instance = object.__new__(watchdog.WatchdogProcessor)
    instance._cfg_base = cfg
    instance.processing_dir = Path(cfg['paths']['processing'])
    instance.control_agent_status = 'disabled'
    instance.control_agent_reason = 'test'
    observed = {}

    class ReachedRunner(BaseException):
        pass

    def capture(**kwargs):
        observed.update(kwargs)
        raise ReachedRunner

    monkeypatch.setattr(run_ingestion, 'run_with_config', capture)
    with pytest.raises(ReachedRunner):
        instance.ingest_video(source, 'window-config-run')
    assert observed['chunk_size'] == 30.0
    assert observed['chunk_overlap'] == 0.0
    assert observed['cfg']['run']['id'] == 'window-config-run'


@pytest.mark.parametrize('size,overlap', [(0,0),(-1,0),(30,-1),(30,30),(30,31),(float('inf'),0),(30,float('nan'))])
def test_invalid_window_settings_rejected(size, overlap):
    cfg = load_configs({}, include_local=False)
    cfg.update(progressive_chunk_size=size, progressive_chunk_overlap=overlap)
    with pytest.raises(ValueError):
        validate_config_mapping(cfg)


def test_existing_window_defaults_unchanged():
    cfg = load_configs({}, include_local=False)
    assert (cfg['progressive_chunk_size'], cfg['progressive_chunk_overlap']) == (300.0, 10.0)
