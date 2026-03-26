from __future__ import annotations

import sys
import types
from pathlib import Path


def test_check_required_model_cache_distinguishes_recoverable_and_missing(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_verify

    registry_path = tmp_path / "configs" / "model_registry.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        """
huggingface_models:
  clap:
    repo_id: laion/clap-htsat-unfused
    required: true
  clip:
    repo_id: openai/clip-vit-base-patch16
    required: true
""".strip(),
        encoding="utf-8",
    )

    models_root = tmp_path / "models"
    recoverable_repo = models_root / "hub" / "models--laion--clap-htsat-unfused"
    recoverable_repo.mkdir(parents=True, exist_ok=True)
    (recoverable_repo / "config.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(bootstrap_verify, "REPO_ROOT", tmp_path)
    monkeypatch.setitem(
        sys.modules,
        "yaml",
        types.SimpleNamespace(
            safe_load=lambda text: {
                "huggingface_models": {
                    "clap": {"repo_id": "laion/clap-htsat-unfused", "required": True},
                    "clip": {"repo_id": "openai/clip-vit-base-patch16", "required": True},
                }
            }
        ),
    )

    results = bootstrap_verify._check_required_model_cache({"paths": {"models_cache": str(models_root)}})
    details = {result.name: result.detail for result in results}

    assert "recoverable noncanonical cache present for laion/clap-htsat-unfused" in details["model_cache:clap"]
    assert "missing cache for openai/clip-vit-base-patch16" in details["model_cache:clip"]


def test_env_or_file_prefers_project_env_over_ambient_env(monkeypatch):
    from scripts import bootstrap_verify

    monkeypatch.setattr(bootstrap_verify, "_ENV_FILE_VALUES", {"GOODQ_WSL_DISTRO": "Ubuntu-22.04"})
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu")

    assert bootstrap_verify._env_or_file("GOODQ_WSL_DISTRO") == "Ubuntu-22.04"


def test_check_wsl_audio_workspace_warns_when_abi_is_degraded(monkeypatch):
    from scripts import bootstrap_verify

    monkeypatch.setattr(
        bootstrap_verify,
        "_ENV_FILE_VALUES",
        {
            "GOODQ_REQUIRE_WSL_AUDIO": "1",
            "GOODQ_WSL_DISTRO": "Ubuntu-22.04",
            "GOODQ_WSL_USER": "goodq",
            "GOODQ_WSL_WORKSPACE": "/home/goodq/goodq_audio",
        },
    )
    monkeypatch.setattr(
        bootstrap_verify,
        "probe_wsl_audio_runtime",
        lambda distro, workspace: {
            "workspace_ready": True,
            "runtime_ready": True,
            "abi_ready": False,
            "detail": "transcription runtime ready; torchvision ABI unavailable (diarization may be degraded)",
        },
    )

    results = bootstrap_verify._check_wsl_audio_workspace()

    assert len(results) == 1
    assert results[0].status == "warn"
    assert "transcription-ready" in results[0].detail


def test_check_torch_cuda_runtime_fails_when_gpu_profile_uses_cpu_only_torch(monkeypatch):
    from scripts import bootstrap_verify

    monkeypatch.setattr(
        bootstrap_verify,
        "_ENV_FILE_VALUES",
        {
            "GOODQ_HOST_PROFILE": "GPU_ENHANCED",
            "GOODQ_REQUIRE_GPU": "1",
        },
    )
    monkeypatch.setitem(
        sys.modules,
        "torch",
        types.SimpleNamespace(
            __version__="2.5.1",
            version=types.SimpleNamespace(cuda=None),
            cuda=types.SimpleNamespace(is_available=lambda: False, device_count=lambda: 0),
        ),
    )

    results = bootstrap_verify._check_torch_cuda_runtime()

    assert len(results) == 1
    assert results[0].status == "fail"
    assert "CPU-only" in results[0].detail
