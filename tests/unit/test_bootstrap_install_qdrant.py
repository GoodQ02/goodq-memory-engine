from __future__ import annotations

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
