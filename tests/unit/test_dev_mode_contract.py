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


def test_dev_on_reports_real_service_transitions_through_the_operator_dashboard():
    dev_on = (REPO_ROOT / "dev_on.bat").read_text(encoding="utf-8").lower()

    assert "dev_mode_dashboard.ps1" in dev_on
    assert "pwsh -noprofile" in dev_on
    assert "-event start" in dev_on
    assert "-node config -state ready" in dev_on
    assert '-node "wsl audio" -state ready' in dev_on
    assert "-node vllm -state ready" in dev_on
    assert "-node qdrant -state ready" in dev_on
    assert "-node api -state ready" in dev_on
    assert "-node watchdog -state ready" in dev_on
    assert "-event final -state ready" in dev_on
    assert "if /i not \"%goodq_no_pause%\"==\"1\" pause" in dev_on
    assert "watchdog_launch_log" in dev_on
    assert "api_launch_log" in dev_on
    assert "addseconds(60)" in dev_on
    assert "addseconds(15)" in dev_on


def test_dev_off_reports_release_and_the_intentional_qdrant_retention():
    dev_off = (REPO_ROOT / "dev_off.bat").read_text(encoding="utf-8").lower()

    assert "dev_mode_dashboard.ps1" in dev_off
    assert "pwsh -noprofile" in dev_off
    assert "-event start" in dev_off
    assert "-node vllm -state released" in dev_off
    assert '-node "wsl audio" -state released' in dev_off
    assert "-node api -state released" in dev_off
    assert "-node watchdog -state released" in dev_off
    assert "-node qdrant -state retained" in dev_off
    assert "nvidia-smi" in dev_off
    assert '-node "nvidia-smi" -state check' in dev_off
    assert "-event final -state ready" in dev_off
    assert "if /i not \"%goodq_no_pause%\"==\"1\" pause" in dev_off


def test_vllm_launcher_waits_for_the_advertised_speed_endpoint_not_only_systemd():
    launcher = (REPO_ROOT / "scripts" / "start_vllm_servers.bat").read_text(encoding="utf-8").lower()

    assert "reusing existing wsl keepalive anchor" in launcher
    assert "get-ciminstance win32_process" in launcher
    assert 'start "goodq wsl keepalive" /min wsl -d %goodq_wsl_distro%' in launcher
    assert "http://127.0.0.1:38005/v1/models" in launcher
    assert "addseconds(90)" in launcher
    assert "vllm speed endpoint did not become ready" in launcher


def test_vllm_stop_launcher_clears_the_windows_side_keepalive_client():
    launcher = (REPO_ROOT / "scripts" / "stop_vllm_servers.bat").read_text(encoding="utf-8").lower()

    assert "get-ciminstance win32_process" in launcher
    assert "goodq-vllm-keepalive" in launcher
    assert "exit /b 0" in launcher
