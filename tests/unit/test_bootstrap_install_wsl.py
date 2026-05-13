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
    monkeypatch.setenv("HF_TOKEN", "hf_ambient_shell_token")
    monkeypatch.setenv("PYANNOTE_TOKEN", "py_ambient_shell_token")
    monkeypatch.setattr(bootstrap_install, "resolve_models_cache_root", lambda conda_exe, repo_root: Path(r"C:\models"))

    values = bootstrap_install._wsl_audio_env_values(
        ctx,
        bootstrap_install.WslAudioContext(
            distro="Ubuntu-22.04",
            user="goodq",
            home="/home/goodq",
            workspace="/home/goodq/goodq_audio",
            windows_workspace=Path("wsl_workspace_placeholder"),
        ),
    )

    assert values["HF_TOKEN"] == "hf_secret"
    assert values["PYANNOTE_TOKEN"] == "py_secret"
    assert values["HF_HOME"] == "/mnt/c/models"
    assert values["TORCH_HOME"] == "/mnt/c/models"
    assert values["HUGGINGFACE_HUB_CACHE"] == "/mnt/c/models/hub"


def test_sync_wsl_audio_assets_normalizes_shell_line_endings(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    ctx = _ctx(tmp_path)
    source_setup = tmp_path / "wsl2_audio" / "setup_wsl2_audio.sh"
    source_service = tmp_path / "scripts" / "wsl" / "install_audio_service.sh"
    source_setup.parent.mkdir(parents=True, exist_ok=True)
    source_service.parent.mkdir(parents=True, exist_ok=True)
    source_setup.write_bytes(b"#!/bin/bash\r\necho setup\r\n")
    source_service.write_bytes(b"#!/bin/bash\r\necho service\r\n")

    staged_workspace = tmp_path / "wsl_stage"
    wsl_ctx = bootstrap_install.WslAudioContext(
        distro="Ubuntu-22.04",
        user="goodq",
        home="/home/goodq",
        workspace="/home/goodq/goodq_audio",
        windows_workspace=staged_workspace,
    )

    seen_scripts: list[str] = []

    def fake_run_wsl_bash(_wsl_ctx, script, **kwargs):
        seen_scripts.append(script)
        return subprocess.CompletedProcess(["wsl"], 0, "", "")

    monkeypatch.setattr(bootstrap_install, "_run_wsl_bash", fake_run_wsl_bash)
    monkeypatch.setattr(
        bootstrap_install,
        "WSL_AUDIO_ASSET_RELATIVE_PATHS",
        [
            "wsl2_audio/setup_wsl2_audio.sh",
            "scripts/wsl/install_audio_service.sh",
        ],
    )

    bootstrap_install._sync_wsl_audio_assets(ctx, wsl_ctx)

    staged_setup = staged_workspace / "setup_wsl2_audio.sh"
    staged_service = staged_workspace / "install_audio_service.sh"
    assert b"\r" not in staged_setup.read_bytes()
    assert b"\r" not in staged_service.read_bytes()
    assert staged_setup.read_bytes().startswith(b"#!/bin/bash\n")
    assert staged_service.read_bytes().startswith(b"#!/bin/bash\n")
    assert seen_scripts
    assert "chmod +x" in seen_scripts[0]


def test_wsl_audio_setup_scripts_pin_validated_torch_trio() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    shell_content = (repo_root / "wsl2_audio/setup_wsl2_audio.sh").read_text(encoding="utf-8")
    quick_content = (repo_root / "scripts/wsl2_quick_install.sh").read_text(encoding="utf-8")

    for marker in (
        "TORCH_VERSION='2.5.1+cu121'",
        "TORCHVISION_VERSION='0.20.1+cu121'",
        "TORCHAUDIO_VERSION='2.5.1+cu121'",
    ):
        assert marker in shell_content
        assert marker in quick_content

    for command_marker in (
        '"torch==${TORCH_VERSION}"',
        '"torchvision==${TORCHVISION_VERSION}"',
        '"torchaudio==${TORCHAUDIO_VERSION}"',
    ):
        assert command_marker in shell_content
        assert command_marker in quick_content


def test_wsl_audio_installers_use_bootstrap_constraints_and_post_install_validation() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    bootstrap_content = (repo_root / "scripts/bootstrap_install.py").read_text(encoding="utf-8")
    shell_content = (repo_root / "wsl2_audio/setup_wsl2_audio.sh").read_text(encoding="utf-8")
    quick_content = (repo_root / "scripts/wsl2_quick_install.sh").read_text(encoding="utf-8")
    setup_py_content = (repo_root / "scripts/setup_wsl2_audio.py").read_text(encoding="utf-8")
    fast_py_content = (repo_root / "scripts/setup_wsl2_audio_fast.py").read_text(encoding="utf-8")
    userspace_py_content = (repo_root / "scripts/setup_wsl2_audio_userspace.py").read_text(encoding="utf-8")

    assert "wsl2_audio/requirements-bootstrap-constraints.txt" in bootstrap_content

    for content in (
        shell_content,
        quick_content,
        setup_py_content,
        fast_py_content,
        userspace_py_content,
    ):
        assert "requirements-bootstrap-constraints.txt" in content
        assert "pip check" in content

    for content in (
        shell_content,
        quick_content,
        setup_py_content,
        fast_py_content,
        userspace_py_content,
    ):
        assert "torchvision.ops import nms" in content


def test_wsl_bootstrap_constraints_match_python310_cu121_lane() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    constraints_path = repo_root / "wsl2_audio" / "requirements-bootstrap-constraints.txt"
    constraints = constraints_path.read_text(encoding="utf-8").splitlines()

    pinned = {
        line.split("==", 1)[0]: line.split("==", 1)[1]
        for line in constraints
        if "==" in line and not line.strip().startswith("#")
    }

    assert pinned["torch"] == "2.5.1+cu121"
    assert pinned["torchvision"] == "0.20.1+cu121"
    assert pinned["torchaudio"] == "2.5.1+cu121"
    assert pinned["pyannote.audio"] == "3.3.2"
    assert pinned["huggingface-hub"] == "0.35.3"
    assert pinned["transformers"] == "4.43.3"
    assert pinned["tokenizers"] == "0.19.1"
    assert pinned["safetensors"] == "0.7.0"
    assert pinned["numpy"] == "2.2.6"
    assert pinned["scipy"] == "1.15.3"

    assert "pyannote.audio==4.0.3" not in constraints
    assert "huggingface-hub==1.13.0" not in constraints
    assert "numpy==2.3.5" not in constraints
    assert "scipy==1.16.3" not in constraints


def test_wsl_audio_installers_include_qualified_wav2vec_enrichment_lane() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    shell_content = (repo_root / "wsl2_audio/setup_wsl2_audio.sh").read_text(encoding="utf-8")
    quick_content = (repo_root / "scripts/wsl2_quick_install.sh").read_text(encoding="utf-8")

    for package in ("transformers", "tokenizers", "safetensors"):
        assert package in shell_content
        assert package in quick_content


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


def test_ensure_wsl_audio_ready_skips_service_install_when_sudo_password_required(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    ctx = _ctx(tmp_path)
    wsl_ctx = bootstrap_install.WslAudioContext(
        distro="Ubuntu-22.04",
        user="goodq",
        home="/home/goodq",
        workspace="/home/goodq/goodq_audio",
        windows_workspace=tmp_path / "wsl_stage",
    )

    seen_scripts: list[str] = []
    messages: list[str] = []

    def fake_run_wsl_bash(_wsl_ctx, script, **kwargs):
        seen_scripts.append(script)
        if script == "test -d /run/systemd/system":
            return subprocess.CompletedProcess(["wsl"], 0, "", "")
        if script == "sudo -n true":
            return subprocess.CompletedProcess(["wsl"], 1, "", "sudo: a password is required")
        return subprocess.CompletedProcess(["wsl"], 0, "", "")

    monkeypatch.setattr(bootstrap_install, "_resolve_wsl_audio_context", lambda _ctx: wsl_ctx)
    monkeypatch.setattr(bootstrap_install, "_run_wsl_bash", fake_run_wsl_bash)
    monkeypatch.setattr(bootstrap_install, "_sync_wsl_audio_assets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "_write_wsl_audio_env_file", lambda *_args, **_kwargs: tmp_path / ".goodq_env")
    monkeypatch.setattr(bootstrap_install, "_probe_wsl_audio_workspace_ready", lambda *_args, **_kwargs: (True, "ready"))
    monkeypatch.setattr(bootstrap_install, "resolve_models_cache_root", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "_print", messages.append)

    ready = bootstrap_install.ensure_wsl_audio_ready(ctx, assume_yes=True)

    assert ready is True
    assert not any("install_audio_service.sh" in script for script in seen_scripts)
    joined = "\n".join(messages)
    assert "PENDING_SUDO" in joined
    assert "sudo: a password is required" in joined
    assert "bash ./install_audio_service.sh" in joined


def test_ensure_wsl_audio_ready_installs_service_when_passwordless_sudo_available(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    ctx = _ctx(tmp_path)
    wsl_ctx = bootstrap_install.WslAudioContext(
        distro="Ubuntu-22.04",
        user="goodq",
        home="/home/goodq",
        workspace="/home/goodq/goodq_audio",
        windows_workspace=tmp_path / "wsl_stage",
    )

    seen_scripts: list[str] = []
    messages: list[str] = []

    def fake_run_wsl_bash(_wsl_ctx, script, **kwargs):
        seen_scripts.append(script)
        return subprocess.CompletedProcess(["wsl"], 0, "", "")

    monkeypatch.setattr(bootstrap_install, "_resolve_wsl_audio_context", lambda _ctx: wsl_ctx)
    monkeypatch.setattr(bootstrap_install, "_run_wsl_bash", fake_run_wsl_bash)
    monkeypatch.setattr(bootstrap_install, "_sync_wsl_audio_assets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "_write_wsl_audio_env_file", lambda *_args, **_kwargs: tmp_path / ".goodq_env")
    monkeypatch.setattr(bootstrap_install, "_probe_wsl_audio_workspace_ready", lambda *_args, **_kwargs: (True, "ready"))
    monkeypatch.setattr(bootstrap_install, "resolve_models_cache_root", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "_print", messages.append)

    ready = bootstrap_install.ensure_wsl_audio_ready(ctx, assume_yes=True)

    assert ready is True
    assert any("sudo -n true" == script for script in seen_scripts)
    assert any("install_audio_service.sh" in script for script in seen_scripts)
    assert "RUNNING" in "\n".join(messages)


def test_probe_wsl_audio_workspace_ready_requires_abi(monkeypatch):
    from scripts import bootstrap_install

    monkeypatch.setattr(
        bootstrap_install,
        "probe_wsl_audio_runtime",
        lambda *_args, **_kwargs: {
            "runtime_ready": True,
            "abi_ready": False,
            "detail": "transcription runtime ready; torchvision ABI unavailable (diarization may be degraded)",
        },
    )

    ready, detail = bootstrap_install._probe_wsl_audio_workspace_ready(
        bootstrap_install.WslAudioContext(
            distro="Ubuntu-22.04",
            user="goodq",
            home="/home/goodq",
            workspace="/home/goodq/goodq_audio",
            windows_workspace=Path("wsl_workspace_placeholder"),
        )
    )

    assert ready is False
    assert "torchvision ABI unavailable" in detail


def test_probe_wsl_audio_workspace_ready_requires_diarization(monkeypatch):
    from scripts import bootstrap_install

    monkeypatch.setattr(
        bootstrap_install,
        "probe_wsl_audio_runtime",
        lambda *_args, **_kwargs: {
            "runtime_ready": True,
            "abi_ready": True,
            "diarization_ready": False,
            "detail": "transcription runtime ready; process_audio import ready; diarization unavailable",
            "diarization_detail": "Pipeline.from_pretrained() got an unexpected keyword argument 'token'",
        },
    )

    ready, detail = bootstrap_install._probe_wsl_audio_workspace_ready(
        bootstrap_install.WslAudioContext(
            distro="Ubuntu-22.04",
            user="goodq",
            home="/home/goodq",
            workspace="/home/goodq/goodq_audio",
            windows_workspace=Path("wsl_workspace_placeholder"),
        )
    )

    assert ready is False
    assert "diarization unavailable" in detail


def test_probe_wsl_audio_workspace_ready_allows_missing_diarization_token(monkeypatch):
    from scripts import bootstrap_install

    monkeypatch.setattr(
        bootstrap_install,
        "probe_wsl_audio_runtime",
        lambda *_args, **_kwargs: {
            "runtime_ready": True,
            "abi_ready": True,
            "diarization_ready": False,
            "detail": "transcription runtime ready; process_audio import ready; diarization unavailable",
            "diarization_detail": "pyannote importable but no HuggingFace token available",
        },
    )

    ready, detail = bootstrap_install._probe_wsl_audio_workspace_ready(
        bootstrap_install.WslAudioContext(
            distro="Ubuntu-22.04",
            user="goodq",
            home="/home/goodq",
            workspace="/home/goodq/goodq_audio",
            windows_workspace=Path("wsl_workspace_placeholder"),
        )
    )

    assert ready is True
    assert "diarization unavailable" in detail


def test_ensure_wsl_audio_ready_preauths_sudo_before_heartbeat_setup(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    ctx = _ctx(tmp_path)
    wsl_ctx = bootstrap_install.WslAudioContext(
        distro="Ubuntu-22.04",
        user="goodq",
        home="/home/goodq",
        workspace="/home/goodq/goodq_audio",
        windows_workspace=tmp_path / "wsl_stage",
    )

    probe_results = iter([(False, "diarization unavailable"), (True, "ready")])
    events: list[str] = []

    def fake_run_wsl_bash(_wsl_ctx, script, **kwargs):
        if "setup_wsl2_audio.sh" in script:
            events.append(f"setup:{kwargs.get('heartbeat_label')}")
        if script == "test -d /run/systemd/system":
            return subprocess.CompletedProcess(["wsl"], 1, "", "")
        return subprocess.CompletedProcess(["wsl"], 0, "", "")

    def fake_preauth(_wsl_ctx):
        events.append("preauth")
        return True, "sudo credentials cached"

    monkeypatch.setattr(bootstrap_install, "_resolve_wsl_audio_context", lambda _ctx: wsl_ctx)
    monkeypatch.setattr(bootstrap_install, "_run_wsl_bash", fake_run_wsl_bash)
    monkeypatch.setattr(bootstrap_install, "_sync_wsl_audio_assets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bootstrap_install, "_write_wsl_audio_env_file", lambda *_args, **_kwargs: tmp_path / ".goodq_env")
    monkeypatch.setattr(bootstrap_install, "_probe_wsl_audio_workspace_ready", lambda *_args, **_kwargs: next(probe_results))
    monkeypatch.setattr(bootstrap_install, "_wsl_interactive_sudo_preauth", fake_preauth)
    monkeypatch.setattr(bootstrap_install, "resolve_models_cache_root", lambda *_args, **_kwargs: None)

    ready = bootstrap_install.ensure_wsl_audio_ready(ctx, assume_yes=True)

    assert ready is True
    assert events == ["preauth", "setup:WSL audio bootstrap"]


def test_wsl_interactive_sudo_preauth_uses_interactive_runner(monkeypatch):
    from scripts import bootstrap_install

    class TtyStdin:
        @staticmethod
        def isatty():
            return True

    wsl_ctx = bootstrap_install.WslAudioContext(
        distro="Ubuntu-22.04",
        user="goodq",
        home="/home/goodq",
        workspace="/home/goodq/goodq_audio",
        windows_workspace=Path("wsl_workspace_placeholder"),
    )
    seen_scripts: list[str] = []
    messages: list[str] = []

    def fake_interactive(_wsl_ctx, script):
        seen_scripts.append(script)
        return subprocess.CompletedProcess(["wsl"], 0, "", "")

    monkeypatch.setattr(bootstrap_install.sys, "stdin", TtyStdin())
    monkeypatch.setattr(bootstrap_install, "_run_wsl_bash_interactive", fake_interactive)
    monkeypatch.setattr(bootstrap_install, "_print", messages.append)

    ready, detail = bootstrap_install._wsl_interactive_sudo_preauth(wsl_ctx)

    assert ready is True
    assert detail == "sudo credentials cached"
    assert seen_scripts == ["sudo -v"]
    assert "If WSL asks for sudo" in "\n".join(messages)
