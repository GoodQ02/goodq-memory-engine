from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _ctx(tmp_path: Path):
    from scripts import bootstrap_install

    return bootstrap_install.BootstrapContext(
        repo_root=tmp_path,
        conda_exe=Path(r"C:\Miniconda3\Scripts\conda.exe"),
        launcher_bat=tmp_path / "LAUNCH_GOODQ.bat",
        environment_yml=tmp_path / "environment.yml",
        env_local_template=tmp_path / ".env.local.template",
        config_local_example=tmp_path / "configs" / "config.local.example.yaml",
        bootstrap_verify=tmp_path / "scripts" / "bootstrap_verify.py",
        qdrant_service_installer=tmp_path / "scripts" / "qdrant" / "INSTALL_QDRANT_SERVICE.bat",
        qdrant_start_bat=tmp_path / "scripts" / "qdrant" / "START_QDRANT.bat",
        data_root=Path(r"C:\GoodQ_Data"),
        enable_gpu=False,
        enable_wsl_audio=True,
        wsl_distro="Ubuntu-22.04",
        profile=bootstrap_install.CapabilityProfile(
            profile="BASELINE",
            gpu_available=False,
            wsl_available=True,
            nvidia_detail="none",
            wsl_detail="installed distros: Ubuntu-22.04",
        ),
        install_step_envs=True,
        prefetch_models=True,
    )


def test_collect_context_preserves_explicit_wsl_request_when_wsl_missing(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    monkeypatch.setattr(bootstrap_install, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(bootstrap_install, "detect_conda", lambda: Path(r"C:\Miniconda3\Scripts\conda.exe"))
    monkeypatch.setattr(bootstrap_install, "detect_python", lambda: (True, "3.13"))
    monkeypatch.setattr(bootstrap_install, "detect_gpu", lambda: (False, "none"))
    monkeypatch.setattr(bootstrap_install, "detect_wsl", lambda: (False, "wsl not found", "Ubuntu-22.04"))
    monkeypatch.setattr(bootstrap_install, "prompt_text", lambda prompt, default, assume_yes: default)
    monkeypatch.setattr(bootstrap_install, "prompt_bool", lambda prompt, default, assume_yes: default)

    args = argparse.Namespace(
        data_root=None,
        wsl_distro=None,
        enable_gpu=False,
        enable_wsl_audio=True,
        prefetch_models=False,
        yes=True,
        inspect_only=False,
        verify_only=False,
        no_launch=True,
    )

    ctx = bootstrap_install.collect_context(args)

    assert ctx.enable_wsl_audio is True
    assert ctx.profile.wsl_available is False
    assert ctx.wsl_distro == "Ubuntu-22.04"


def test_write_env_local_only_enables_wsl_after_workspace_is_resolved(tmp_path: Path):
    from scripts import bootstrap_install

    ctx = _ctx(tmp_path)
    template = tmp_path / ".env.local.template"
    env_local = tmp_path / ".env.local"
    template.write_text("# template\n", encoding="utf-8")

    bootstrap_install.write_env_local(env_local, template, ctx)
    initial = env_local.read_text(encoding="utf-8")
    assert "GOODQ_REQUIRE_WSL_AUDIO=0" in initial
    assert "GOODQ_WSL_USER=auto" in initial
    assert "GOODQ_WSL_WORKSPACE=auto" in initial

    ctx.wsl_user = "goodq"
    ctx.wsl_workspace = "/home/goodq/goodq_audio"
    bootstrap_install.write_env_local(env_local, template, ctx)
    updated = env_local.read_text(encoding="utf-8")
    assert "GOODQ_REQUIRE_WSL_AUDIO=1" in updated
    assert "GOODQ_WSL_USER=goodq" in updated
    assert "GOODQ_WSL_WORKSPACE=/home/goodq/goodq_audio" in updated


def test_wsl_audio_env_values_share_model_cache_and_tokens(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    ctx = _ctx(tmp_path)
    (tmp_path / ".env.local").write_text(
        "HF_TOKEN=hf_secret\nPYANNOTE_TOKEN=py_secret\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrap_install, "resolve_models_cache_root", lambda conda_exe, repo_root: Path(r"C:\models"))

    values = bootstrap_install._wsl_audio_env_values(
        ctx,
        bootstrap_install.WslAudioContext(
            distro="Ubuntu-22.04",
            user="goodq",
            home="/home/goodq",
            workspace="/home/goodq/goodq_audio",
            windows_workspace=Path(r"\\wsl$\Ubuntu-22.04\home\goodq\goodq_audio"),
        ),
    )

    assert values["HF_TOKEN"] == "hf_secret"
    assert values["PYANNOTE_TOKEN"] == "py_secret"
    assert values["HF_HOME"] == "/mnt/c/models"
    assert values["TORCH_HOME"] == "/mnt/c/models"
    assert values["HUGGINGFACE_HUB_CACHE"] == "/mnt/c/models/hub"


def test_resolve_wsl_python_prefers_venv(monkeypatch):
    from steps.audio_transcribe import step

    def fake_run(cmd, **kwargs):
        candidate = cmd[-1]
        return subprocess.CompletedProcess(cmd, 0 if candidate.endswith("/venv/bin/python") else 1, "", "")

    monkeypatch.setattr(step.subprocess, "run", fake_run)

    resolved = step._resolve_wsl_python("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert resolved == "/home/goodq/goodq_audio/venv/bin/python"


def test_resolve_wsl_python_falls_back_to_legacy_env(monkeypatch):
    from steps.audio_transcribe import step

    def fake_run(cmd, **kwargs):
        candidate = cmd[-1]
        return subprocess.CompletedProcess(cmd, 0 if candidate.endswith("/env/bin/python") else 1, "", "")

    monkeypatch.setattr(step.subprocess, "run", fake_run)

    resolved = step._resolve_wsl_python("Ubuntu-22.04", "/home/goodq/goodq_audio")

    assert resolved == "/home/goodq/goodq_audio/env/bin/python"
