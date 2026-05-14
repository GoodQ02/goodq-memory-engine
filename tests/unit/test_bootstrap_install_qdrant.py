from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_qdrant_installer_env_uses_canonical_runtime_paths(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    ctx = bootstrap_install.BootstrapContext(
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
        enable_wsl_audio=False,
        wsl_distro="Ubuntu-22.04",
        profile=bootstrap_install.CapabilityProfile(
            profile="BASELINE",
            gpu_available=False,
            wsl_available=False,
            nvidia_detail="none",
            wsl_detail="none",
        ),
        install_step_envs=True,
        prefetch_models=True,
    )

    monkeypatch.setattr(
        bootstrap_install,
        "resolve_qdrant_runtime_paths",
        lambda conda_exe, repo_root: (r"C:\GoodQ_Data\qdrant_storage", r"C:\GoodQ_Data\logs"),
    )

    env = bootstrap_install._qdrant_installer_env(ctx)

    assert env["CONDA_EXE"] == r"C:\Miniconda3\Scripts\conda.exe"
    assert env["GOODQ_CONDA_ENV"] == "goodq_core"
    assert env["QDRANT_STORAGE_PATH"] == r"C:\GoodQ_Data\qdrant_storage"
    assert env["GOODQ_LOG_DIR"] == r"C:\GoodQ_Data\logs"


def test_qdrant_lifecycle_state_distinguishes_pending_installed_and_running():
    from scripts import bootstrap_install

    assert bootstrap_install._qdrant_lifecycle_state(True, {"exists": "false"}) == "QDRANT_RUNNING"
    assert bootstrap_install._qdrant_lifecycle_state(False, {"exists": "true"}) == "QDRANT_INSTALLED"
    assert bootstrap_install._qdrant_lifecycle_state(False, {"exists": "false"}) == "QDRANT_PENDING_ADMIN"


def test_qdrant_service_alignment_detects_stale_storage_and_logs():
    from scripts import bootstrap_install

    issues = bootstrap_install._qdrant_service_alignment_issues(
        {
            "exists": "true",
            "app_environment_extra": "QDRANT__STORAGE__STORAGE_PATH=<OLD_ROOT>\\qdrant_storage",
            "app_stdout": "<OLD_ROOT>\\logs\\qdrant_stdout.log",
            "app_stderr": "<OLD_ROOT>\\logs\\qdrant_stderr.log",
        },
        "<GOODQ_DATA_ROOT>\\qdrant_storage",
        "<GOODQ_DATA_ROOT>\\logs",
    )

    assert any("storage path" in issue for issue in issues)
    assert any("stdout log" in issue for issue in issues)
    assert any("stderr log" in issue for issue in issues)
    assert any("telemetry disabled flag" in issue for issue in issues)


def test_qdrant_service_alignment_accepts_current_storage_logs_and_telemetry():
    from scripts import bootstrap_install

    issues = bootstrap_install._qdrant_service_alignment_issues(
        {
            "exists": "true",
            "app_environment_extra": (
                "QDRANT__STORAGE__STORAGE_PATH=<GOODQ_DATA_ROOT>\\qdrant_storage;;"
                "QDRANT__TELEMETRY_DISABLED=true"
            ),
            "app_stdout": "<GOODQ_DATA_ROOT>\\logs\\qdrant_stdout.log",
            "app_stderr": "<GOODQ_DATA_ROOT>\\logs\\qdrant_stderr.log",
        },
        "<GOODQ_DATA_ROOT>\\qdrant_storage",
        "<GOODQ_DATA_ROOT>\\logs",
    )

    assert issues == []


def test_ensure_qdrant_ready_repairs_reachable_stale_service_when_assume_yes(monkeypatch, tmp_path):
    from scripts import bootstrap_install

    ctx = bootstrap_install.BootstrapContext(
        repo_root=tmp_path,
        conda_exe=Path("<CONDA_EXE>"),
        launcher_bat=tmp_path / "LAUNCH_GOODQ.bat",
        environment_yml=tmp_path / "environment.yml",
        env_local_template=tmp_path / ".env.local.template",
        config_local_example=tmp_path / "configs" / "config.local.example.yaml",
        bootstrap_verify=tmp_path / "scripts" / "bootstrap_verify.py",
        qdrant_service_installer=tmp_path / "scripts" / "qdrant" / "INSTALL_QDRANT_SERVICE.bat",
        qdrant_start_bat=tmp_path / "scripts" / "qdrant" / "START_QDRANT.bat",
        data_root=Path("<GOODQ_DATA_ROOT>"),
        enable_gpu=False,
        enable_wsl_audio=False,
        wsl_distro="Ubuntu-22.04",
        profile=bootstrap_install.CapabilityProfile(
            profile="BASELINE",
            gpu_available=False,
            wsl_available=False,
            nvidia_detail="none",
            wsl_detail="none",
        ),
        install_step_envs=True,
        prefetch_models=True,
    )
    ctx.qdrant_service_installer.parent.mkdir(parents=True, exist_ok=True)
    ctx.qdrant_service_installer.write_text("@echo off\n", encoding="utf-8")
    (tmp_path / "vendor" / "qdrant").mkdir(parents=True, exist_ok=True)
    (tmp_path / "vendor" / "qdrant" / "qdrant.exe").write_text("", encoding="utf-8")
    (tmp_path / "vendor" / "qdrant" / "config.yaml").write_text("service: {}\n", encoding="utf-8")

    messages: list[str] = []
    installer_calls: list[dict[str, str]] = []

    monkeypatch.setattr(bootstrap_install, "_print", lambda msg: messages.append(msg))
    monkeypatch.setattr(bootstrap_install, "resolve_qdrant_url", lambda conda_exe, repo_root: "http://127.0.0.1:6333")
    monkeypatch.setattr(bootstrap_install, "check_qdrant", lambda url: (True, f"reachable at {url}"))
    monkeypatch.setattr(
        bootstrap_install,
        "inspect_windows_service",
        lambda name: {
            "exists": "true",
            "status": "Running",
            "start_mode": "Auto",
            "app_environment_extra": "QDRANT__STORAGE__STORAGE_PATH=<OLD_ROOT>\\qdrant_storage",
            "app_stdout": "<OLD_ROOT>\\logs\\qdrant_stdout.log",
            "app_stderr": "<OLD_ROOT>\\logs\\qdrant_stderr.log",
        },
    )
    monkeypatch.setattr(
        bootstrap_install,
        "resolve_qdrant_runtime_paths",
        lambda conda_exe, repo_root: ("<GOODQ_DATA_ROOT>\\qdrant_storage", "<GOODQ_DATA_ROOT>\\logs"),
    )
    monkeypatch.setattr(bootstrap_install, "_is_admin", lambda: True)
    monkeypatch.setattr(bootstrap_install, "_wait_for_qdrant", lambda url: (True, f"reachable at {url}"))

    def fake_installer(installer, env):
        installer_calls.append(env)
        return subprocess.CompletedProcess([str(installer)], 0, "", "")

    monkeypatch.setattr(bootstrap_install, "_run_qdrant_service_installer", fake_installer)

    assert bootstrap_install.ensure_qdrant_ready(ctx, assume_yes=True) is True

    assert installer_calls
    assert installer_calls[0]["QDRANT_STORAGE_PATH"] == "<GOODQ_DATA_ROOT>\\qdrant_storage"
    assert installer_calls[0]["GOODQ_LOG_DIR"] == "<GOODQ_DATA_ROOT>\\logs"
    assert any("QDRANT_RUNNING_BUT_STALE_CONFIG" in message for message in messages)


def test_run_emits_heartbeat_for_silent_subprocess(monkeypatch):
    from scripts import bootstrap_install

    messages: list[str] = []
    monkeypatch.setattr(bootstrap_install, "_print", lambda msg: messages.append(msg))

    completed = bootstrap_install._run(
        [sys.executable, "-c", "import time; time.sleep(2.2)"],
        heartbeat_label="Silent installer phase",
        heartbeat_interval=1,
    )

    assert completed.returncode == 0
    assert any("[HEARTBEAT] Silent installer phase" in message for message in messages)


def test_bootstrap_models_heartbeat_status_reads_progress_and_flags_stale(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    progress_path = tmp_path / "bootstrap_models_progress.json"
    report_path = tmp_path / "bootstrap_models_report.json"
    progress_path.write_text(
        """{
  "status": "in_progress",
  "current_model": "openai/whisper-large-v3",
  "current_index": 8,
  "total_assets": 16,
  "current_attempt": 1,
  "completed_count": 7,
  "last_event": "model_started",
  "last_progress_at": 100.0
}""",
        encoding="utf-8",
    )
    monkeypatch.setenv("GOODQ_MODEL_STALL_TIMEOUT_SEC", "60")
    monkeypatch.setattr(bootstrap_install.time, "time", lambda: 250.0)

    status = bootstrap_install._bootstrap_models_heartbeat_status(progress_path, report_path)

    assert "current_model=openai/whisper-large-v3" in status
    assert "asset=8/16" in status
    assert "completed=7" in status
    assert "last_progress_age=2m30s stale=yes" in status


def test_run_emits_heartbeat_status_hint(monkeypatch):
    from scripts import bootstrap_install

    messages: list[str] = []
    monkeypatch.setattr(bootstrap_install, "_print", lambda msg: messages.append(msg))

    completed = bootstrap_install._run(
        [sys.executable, "-c", "import time; time.sleep(2.2)"],
        heartbeat_label="Model prefetch",
        heartbeat_interval=1,
        heartbeat_status_fn=lambda: "current_model=openai/whisper-large-v3 last_progress_age=45s",
    )

    assert completed.returncode == 0
    assert any("current_model=openai/whisper-large-v3" in message for message in messages)


def test_validate_step_env_reports_allowed_pip_check_warning_as_non_blocking(monkeypatch, tmp_path):
    from scripts import bootstrap_install

    messages: list[str] = []
    monkeypatch.setattr(bootstrap_install, "_print", lambda msg: messages.append(msg))

    spec = bootstrap_install.StepEnvSpec(
        "goodq_face_embed",
        "envs/face_embed/requirements.txt",
        "envs/locks/face_embed.lock.txt",
        "face detection and embeddings",
        ("face_recognition",),
        allowed_pip_check_warnings=(
            "facenet-pytorch 2.6.0 has requirement torch<2.3.0,>=2.2.0",
        ),
    )

    def fake_run(cmd, **kwargs):
        rendered = " ".join(str(part) for part in cmd)
        if "python -m pip check" in rendered:
            return subprocess.CompletedProcess(
                cmd,
                1,
                "facenet-pytorch 2.6.0 has requirement torch<2.3.0,>=2.2.0, but you have torch 2.5.1+cu121.",
                "",
            )
        if "python -c" in rendered:
            return subprocess.CompletedProcess(cmd, 0, "ok\n", "")
        raise AssertionError(f"unexpected command: {rendered}")

    monkeypatch.setattr(bootstrap_install, "_run", fake_run)

    issues = bootstrap_install._validate_step_env(
        Path(r"C:\Miniconda3\Scripts\conda.exe"),
        tmp_path,
        spec,
    )

    assert issues == []
    assert any("accepted non-blocking dependency notice" in message for message in messages)


def test_write_env_local_sets_require_gpu_from_context(tmp_path: Path):
    from scripts import bootstrap_install

    env_path = tmp_path / ".env.local"
    template_path = tmp_path / ".env.local.template"
    template_path.write_text("# GoodQ local overrides\n", encoding="utf-8")

    ctx = bootstrap_install.BootstrapContext(
        repo_root=tmp_path,
        conda_exe=Path(r"C:\Miniconda3\Scripts\conda.exe"),
        launcher_bat=tmp_path / "LAUNCH_GOODQ.bat",
        environment_yml=tmp_path / "environment.gpu.yml",
        env_local_template=template_path,
        config_local_example=tmp_path / "configs" / "config.local.example.yaml",
        bootstrap_verify=tmp_path / "scripts" / "bootstrap_verify.py",
        qdrant_service_installer=tmp_path / "scripts" / "qdrant" / "INSTALL_QDRANT_SERVICE.bat",
        qdrant_start_bat=tmp_path / "scripts" / "qdrant" / "START_QDRANT.bat",
        data_root=Path(r"C:\GoodQ_Data"),
        enable_gpu=True,
        enable_wsl_audio=False,
        wsl_distro="Ubuntu-22.04",
        profile=bootstrap_install.CapabilityProfile(
            profile="GPU_ENHANCED",
            gpu_available=True,
            wsl_available=False,
            nvidia_detail="gpu present",
            wsl_detail="none",
        ),
        install_step_envs=True,
        prefetch_models=True,
    )

    bootstrap_install.write_env_local(env_path, template_path, ctx)
    written = env_path.read_text(encoding="utf-8")

    assert "GOODQ_REQUIRE_GPU=1" in written


def test_has_core_torch_stack_conflict_detects_gpu_cpuonly(monkeypatch):
    from scripts import bootstrap_install

    payload = json.dumps(
        [
            {"name": "cpuonly", "version": "2.0", "channel": "pytorch"},
            {"name": "pytorch", "version": "2.5.1", "channel": "pytorch"},
        ]
    )

    monkeypatch.setattr(
        bootstrap_install,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, payload, ""),
    )

    has_conflict, detail = bootstrap_install._has_core_torch_stack_conflict(
        Path(r"C:\Miniconda3\Scripts\conda.exe"),
        require_gpu=True,
    )

    assert has_conflict is True
    assert "cpuonly" in detail
