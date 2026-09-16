from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest


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


def test_validate_step_env_reports_pip_check_failure_as_blocking(monkeypatch, tmp_path):
    from scripts import bootstrap_install

    messages: list[str] = []
    monkeypatch.setattr(bootstrap_install, "_print", lambda msg: messages.append(msg))

    spec = bootstrap_install.StepEnvSpec(
        "goodq_face_embed",
        "envs/face_embed/requirements.txt",
        "envs/locks/face_embed.lock.txt",
        "face detection and embeddings",
        ("face_recognition",),
    )

    def fake_run(cmd, **kwargs):
        rendered = " ".join(str(part) for part in cmd)
        if "python -m pip check" in rendered:
            return subprocess.CompletedProcess(
                cmd,
                1,
                "broken dependency closure",
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

    assert issues == ["pip check failed for goodq_face_embed: broken dependency closure"]


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


@pytest.fixture
def bootstrap_profile_host(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_install

    for name in ("environment.yml", "environment.gpu.yml", "LAUNCH_GOODQ.bat"):
        (tmp_path / name).write_text("fixture\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap_install, "_is_windows", lambda: True)
    monkeypatch.setattr(bootstrap_install, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(bootstrap_install, "detect_conda", lambda: tmp_path / "conda.exe")
    monkeypatch.setattr(bootstrap_install, "detect_python", lambda: (True, "3.10"))
    monkeypatch.setattr(bootstrap_install, "detect_gpu", lambda: (True, "GPU present"))
    monkeypatch.setattr(bootstrap_install, "detect_wsl", lambda: (False, "none", "Ubuntu"))
    args = Namespace(
        yes=True, inspect_only=False, verify_only=False, no_launch=True,
        data_root=str(tmp_path / "data"), enable_gpu=None,
        enable_wsl_audio=False, prefetch_models=False, wsl_distro=None,
    )
    return bootstrap_install, args, tmp_path


@pytest.mark.parametrize(
    ("settings", "wanted_spec"),
    [
        ("", "environment.yml"),
        ("GOODQ_HOST_PROFILE=BASELINE\nGOODQ_REQUIRE_GPU=0\n", "environment.yml"),
        ("GOODQ_HOST_PROFILE=GPU_ENHANCED\nGOODQ_REQUIRE_GPU=1\n", "environment.gpu.yml"),
        ("GOODQ_REQUIRE_GPU=1\n", "environment.gpu.yml"),
    ],
)
def test_unattended_bootstrap_preserves_existing_gpu_selection(
    bootstrap_profile_host, settings, wanted_spec,
):
    bootstrap, args, root = bootstrap_profile_host
    if settings:
        (root / ".env.local").write_text(settings, encoding="utf-8")

    ctx = bootstrap.collect_context(args)

    assert ctx.environment_yml == root / wanted_spec
    assert ctx.enable_gpu is (wanted_spec == "environment.gpu.yml")
    if settings:
        assert (root / ".env.local").read_text(encoding="utf-8") == settings


@pytest.mark.parametrize("existing_gpu", [False, True])
def test_bootstrap_rejects_profile_change_that_preserved_config_would_undo(
    bootstrap_profile_host, existing_gpu,
):
    bootstrap, args, root = bootstrap_profile_host
    profile = "GPU_ENHANCED" if existing_gpu else "BASELINE"
    (root / ".env.local").write_text(
        f"GOODQ_HOST_PROFILE={profile}\nGOODQ_REQUIRE_GPU={int(existing_gpu)}\n",
        encoding="utf-8",
    )
    args.enable_gpu = not existing_gpu

    with pytest.raises(RuntimeError, match="preserved.*env.local"):
        bootstrap.collect_context(args)


@pytest.mark.parametrize("managed_header", ["", "# Bootstrap-managed defaults\n"])
def test_bootstrap_cannot_downgrade_preserved_gpu_profile_when_gpu_is_unavailable(
    bootstrap_profile_host, monkeypatch, managed_header,
):
    bootstrap, args, root = bootstrap_profile_host
    (root / ".env.local").write_text(
        managed_header + "GOODQ_REQUIRE_GPU=1\n", encoding="utf-8",
    )
    monkeypatch.setattr(bootstrap, "detect_gpu", lambda: (False, "GPU unavailable"))

    with pytest.raises(RuntimeError, match="preserved.*env.local"):
        bootstrap.collect_context(args)


def test_explicit_profile_change_updates_bootstrap_managed_settings(bootstrap_profile_host):
    bootstrap, args, root = bootstrap_profile_host
    env_path = root / ".env.local"
    env_path.write_text(
        "# Bootstrap-managed defaults\nGOODQ_HOST_PROFILE=GPU_ENHANCED\nGOODQ_REQUIRE_GPU=1\n",
        encoding="utf-8",
    )
    args.enable_gpu = False

    ctx = bootstrap.collect_context(args)
    bootstrap.write_env_local(env_path, root / "absent-template", ctx)

    assert ctx.environment_yml == root / "environment.yml"
    assert bootstrap._load_env_file(env_path)["GOODQ_HOST_PROFILE"] == "BASELINE"
    assert bootstrap._load_env_file(env_path)["GOODQ_REQUIRE_GPU"] == "0"


def test_missing_gpu_recipe_cannot_select_baseline(bootstrap_profile_host, monkeypatch, capsys):
    bootstrap, args, root = bootstrap_profile_host
    args.enable_gpu = True
    (root / "environment.gpu.yml").unlink()
    monkeypatch.setattr(bootstrap, "parse_args", lambda: args)
    monkeypatch.setattr(bootstrap, "print_inspection", lambda ctx: None)
    provisions = []
    monkeypatch.setattr(bootstrap, "ensure_conda_env", lambda *a, **kw: provisions.append(a))
    monkeypatch.setattr(bootstrap, "ensure_supported_step_envs", lambda *a, **kw: None)
    monkeypatch.setattr(bootstrap, "prepare_local_files", lambda *a, **kw: None)
    monkeypatch.setattr(bootstrap, "ensure_model_cache", lambda *a, **kw: None)
    monkeypatch.setattr(bootstrap, "ensure_wsl_audio_ready", lambda *a, **kw: True)
    monkeypatch.setattr(bootstrap, "ensure_ffmpeg_ready", lambda *a, **kw: True)
    monkeypatch.setattr(bootstrap, "ensure_qdrant_ready", lambda *a, **kw: True)
    monkeypatch.setattr(bootstrap, "verify_runtime", lambda *a, **kw: 0)

    assert bootstrap.main() == 1
    assert provisions == []
    assert "Missing environment spec" in capsys.readouterr().out


def test_required_verifier_failure_blocks_bootstrap_completion(
    bootstrap_profile_host, monkeypatch, capsys,
):
    bootstrap, args, root = bootstrap_profile_host
    args.verify_only = True
    monkeypatch.setattr(bootstrap, "parse_args", lambda: args)
    monkeypatch.setattr(bootstrap, "print_inspection", lambda ctx: None)
    monkeypatch.setattr(bootstrap, "verify_env_python", lambda *a: (True, "python ready"))
    monkeypatch.setattr(bootstrap, "verify_config_loader", lambda *a: (True, "config loaded"))
    monkeypatch.setattr(bootstrap, "run_bootstrap_verify", lambda *a: (False, "CUDA required but unavailable"))
    monkeypatch.setattr(bootstrap, "resolve_ffmpeg", lambda: (True, "ffmpeg ready"))
    monkeypatch.setattr(bootstrap, "resolve_qdrant_url", lambda *a: "http://127.0.0.1:6333")
    monkeypatch.setattr(bootstrap, "check_qdrant", lambda *a: (True, "reachable"))

    assert bootstrap.main() == 1
    output = capsys.readouterr().out
    assert "CUDA required but unavailable" in output
    assert "Bootstrap complete" not in output


@pytest.mark.parametrize(
    ("stdout", "returncode", "accepted"),
    [
        ('{"overall":"pass"}', 0, True),
        ('{"overall":"warn"}', 0, True),
        ('{"overall":"fail"}', 0, False),
        ('{"overall":"pass"}', 1, False),
        ("", 0, False),
        ("not JSON", 0, False),
        ("[]", 0, False),
        ("{}", 0, False),
        ('{"overall":"unknown"}', 0, False),
    ],
)
def test_bootstrap_accepts_only_usable_terminal_verification_report(
    monkeypatch, tmp_path: Path, stdout, returncode, accepted,
):
    from scripts import bootstrap_install

    monkeypatch.setattr(
        bootstrap_install, "_run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, returncode, stdout, ""),
    )

    ok, detail = bootstrap_install.run_bootstrap_verify(tmp_path / "conda.exe", tmp_path)

    assert ok is accepted
    assert detail
