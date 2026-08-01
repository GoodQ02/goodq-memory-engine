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


def test_dev_off_keeps_loopback_qdrant_available_for_fast_dev_return():
    dev_off = (REPO_ROOT / "dev_off.bat").read_text(encoding="utf-8").lower()

    assert 'net stop "goodq_qdrant"' not in dev_off
    assert "qdrant remains available" in dev_off


def test_dev_on_enables_retrieval_encoder_prewarm_for_its_api_process():
    dev_on = (REPO_ROOT / "dev_on.bat").read_text(encoding="utf-8").lower()

    assert "goodq_prewarm_retrieval_models=1" in dev_on


def test_vllm_launcher_waits_for_the_advertised_speed_endpoint_not_only_systemd():
    launcher = (REPO_ROOT / "scripts" / "start_vllm_servers.bat").read_text(encoding="utf-8").lower()

    assert "http://127.0.0.1:38005/v1/models" in launcher
    assert "addseconds(90)" in launcher
    assert "vllm speed endpoint did not become ready" in launcher
