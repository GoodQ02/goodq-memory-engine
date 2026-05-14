from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from scripts import bootstrap_install


def _completed(cmd: list[str], returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def test_conda_tos_view_command_targets_required_channels():
    cmd = bootstrap_install._conda_tos_view_command(Path("conda"))

    assert cmd[:5] == ["conda", "tos", "view", "--override-channels", "--json"]
    assert cmd.count("--channel") == len(bootstrap_install.CONDA_TOS_CHANNELS)
    for channel in bootstrap_install.CONDA_TOS_CHANNELS:
        assert channel in cmd


def test_conda_tos_view_detects_unaccepted_channel():
    payload = {
        "channels": [
            {"channel": bootstrap_install.CONDA_TOS_CHANNELS[0], "tos_accepted": True},
            {"channel": bootstrap_install.CONDA_TOS_CHANNELS[1], "tos_accepted": False},
        ]
    }

    assert bootstrap_install._conda_tos_acceptance_needed(json.dumps(payload)) is True


def test_conda_tos_view_detects_channel_keyed_payload():
    payload = {
        bootstrap_install.CONDA_TOS_CHANNELS[0]: {"tos_accepted": True},
        bootstrap_install.CONDA_TOS_CHANNELS[1]: {"tos_accepted": True},
        bootstrap_install.CONDA_TOS_CHANNELS[2]: {"tos_accepted": False},
    }

    assert bootstrap_install._conda_tos_acceptance_needed(json.dumps(payload)) is True


def test_conda_tos_preflight_accepts_before_package_install(monkeypatch):
    fake_stdout = io.StringIO()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if cmd[1:3] == ["tos", "view"]:
            return _completed(cmd, stdout=json.dumps({"channels": [{"tos_accepted": False}]}))
        if cmd[1:3] == ["tos", "accept"]:
            return _completed(cmd)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(bootstrap_install.sys, "stdout", fake_stdout)
    monkeypatch.setattr(bootstrap_install, "_run", fake_run)

    bootstrap_install.preflight_conda_tos(Path("conda"), assume_yes=True)

    assert calls[0] == bootstrap_install._conda_tos_view_command(Path("conda"))
    assert calls[1:] == bootstrap_install._conda_tos_commands(Path("conda"))
    assert "paused for operator consent" in fake_stdout.getvalue()


def test_conda_tos_preflight_inconclusive_falls_back_without_failing(monkeypatch):
    fake_stdout = io.StringIO()
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return _completed(cmd, returncode=1, stderr="conda tos view is unavailable")

    monkeypatch.setattr(bootstrap_install.sys, "stdout", fake_stdout)
    monkeypatch.setattr(bootstrap_install, "_run", fake_run)

    bootstrap_install.preflight_conda_tos(Path("conda"), assume_yes=False)

    assert calls == [bootstrap_install._conda_tos_view_command(Path("conda"))]
    assert "preflight was inconclusive" in fake_stdout.getvalue()


def test_bootstrap_main_runs_conda_tos_preflight_before_environment_creation(tmp_path, monkeypatch):
    environment_yml = tmp_path / "environment.yml"
    launcher_bat = tmp_path / "launch.bat"
    environment_yml.write_text("name: goodq_core\n", encoding="utf-8")
    launcher_bat.write_text("@echo off\n", encoding="utf-8")
    events: list[str] = []
    profile = bootstrap_install.CapabilityProfile(
        profile="BASELINE",
        gpu_available=False,
        wsl_available=False,
        nvidia_detail="not checked",
        wsl_detail="not checked",
    )
    ctx = bootstrap_install.BootstrapContext(
        repo_root=tmp_path,
        conda_exe=Path("conda"),
        launcher_bat=launcher_bat,
        environment_yml=environment_yml,
        env_local_template=tmp_path / ".env.local.template",
        config_local_example=tmp_path / "config.local.example.yaml",
        bootstrap_verify=tmp_path / "bootstrap_validate.bat",
        qdrant_service_installer=tmp_path / "INSTALL_QDRANT_SERVICE.bat",
        qdrant_start_bat=tmp_path / "start_qdrant.bat",
        data_root=tmp_path / "data",
        enable_gpu=False,
        enable_wsl_audio=False,
        wsl_distro="Ubuntu",
        profile=profile,
        install_step_envs=False,
        prefetch_models=False,
    )

    monkeypatch.setattr(bootstrap_install, "_is_windows", lambda: True)
    monkeypatch.setattr(
        bootstrap_install,
        "parse_args",
        lambda: SimpleNamespace(inspect_only=False, verify_only=False, yes=True, no_launch=True),
    )
    monkeypatch.setattr(bootstrap_install, "collect_context", lambda _args: ctx)
    monkeypatch.setattr(bootstrap_install, "print_inspection", lambda _ctx: None)
    monkeypatch.setattr(bootstrap_install, "preflight_conda_tos", lambda *_args, **_kwargs: events.append("preflight"))
    monkeypatch.setattr(bootstrap_install, "ensure_conda_env", lambda *_args, **_kwargs: events.append("env"))
    monkeypatch.setattr(bootstrap_install, "ensure_supported_step_envs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "prepare_local_files", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "ensure_model_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "ensure_wsl_audio_ready", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(bootstrap_install, "ensure_ffmpeg_ready", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "ensure_qdrant_ready", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(bootstrap_install, "verify_runtime", lambda *_args, **_kwargs: 0)

    assert bootstrap_install.main() == 0
    assert events[:2] == ["preflight", "env"]
