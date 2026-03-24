from __future__ import annotations

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
