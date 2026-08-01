"""Regression contracts for the Windows Dev On/Dev Off pair."""

from pathlib import Path

import pytest

from steps.common import config_loader


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_strict_config_validation_rejects_retired_local_overlay_keys():
    config = config_loader.load_configs({})
    config["progressive_chunk_size"] = 300.0

    with pytest.raises(ValueError, match="progressive_chunk_size"):
        config_loader.validate_config_mapping(config)


def test_windows_dev_mode_launchers_delegate_vllm_to_canonical_controls():
    dev_on = (REPO_ROOT / "dev_on.bat").read_text(encoding="utf-8").lower()
    dev_off = (REPO_ROOT / "dev_off.bat").read_text(encoding="utf-8").lower()

    assert 'call "%~dp0scripts\\start_vllm_servers.bat"' in dev_on
    assert 'call "%~dp0scripts\\stop_vllm_servers.bat"' in dev_off
    assert "validate_config_mapping" in dev_on
    assert "wsl --shutdown" in dev_off
