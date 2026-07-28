from __future__ import annotations

from pathlib import Path


def test_pyannote_pipeline_cache_accepts_its_config_plus_cached_dependencies(monkeypatch, tmp_path: Path):
    """The 3.1 pipeline repo is config-only; weights live in its child repos."""
    from wsl2_audio import model_cache

    monkeypatch.setenv("GOODQ_MODEL_CACHE_ROOT", str(tmp_path))
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)

    def artifact(repo_id: str, name: str) -> None:
        target = tmp_path / "hub" / f"models--{repo_id.replace('/', '--')}" / "snapshots" / "revision" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("cached", encoding="utf-8")

    artifact("pyannote/speaker-diarization-3.1", "config.yaml")
    artifact("pyannote/segmentation-3.0", "pytorch_model.bin")
    artifact("pyannote/wespeaker-voxceleb-resnet34-LM", "pytorch_model.bin")

    assert model_cache.check_pyannote_cache("pyannote/speaker-diarization-3.1")


def test_hf_cache_recognizes_a_snapshot_symlink_by_its_snapshot_filename(monkeypatch, tmp_path: Path):
    from wsl2_audio import model_cache

    monkeypatch.setenv("GOODQ_MODEL_CACHE_ROOT", str(tmp_path))
    repo = tmp_path / "hub" / "models--pyannote--segmentation-3.0"
    blob = repo / "blobs" / "content-addressed-blob"
    blob.parent.mkdir(parents=True)
    blob.write_text("weights", encoding="utf-8")
    snapshot = repo / "snapshots" / "revision"
    snapshot.mkdir(parents=True)
    (snapshot / "pytorch_model.bin").symlink_to(blob)

    assert model_cache.check_hf_model_cache("pyannote/segmentation-3.0")


def test_model_registry_contains_wsl_diarization_repo_chain():
    import yaml

    from scripts.wsl_audio_preflight import _DIARIZATION_REPOS

    registry_path = Path(__file__).resolve().parents[2] / "configs" / "model_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    models = registry.get("huggingface_models", {}) or {}
    repo_ids = {
        str(model_info.get("repo_id") or "").strip()
        for model_info in models.values()
        if isinstance(model_info, dict)
    }

    assert set(_DIARIZATION_REPOS).issubset(repo_ids)
    assert "pyannote/speaker-diarization" not in repo_ids
    assert "pyannote/segmentation" not in repo_ids


def test_model_registry_contains_wsl_embedding_cache_gate_repo():
    import yaml

    registry_path = Path(__file__).resolve().parents[2] / "configs" / "model_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    models = registry.get("huggingface_models", {}) or {}
    repo_ids = {
        str(model_info.get("repo_id") or "").strip()
        for model_info in models.values()
        if isinstance(model_info, dict)
    }

    assert "facebook/wav2vec2-base-960h" in repo_ids


def test_wav2vec_signature_model_uses_an_immutable_registry_revision():
    import yaml

    registry_path = Path(__file__).resolve().parents[2] / "configs" / "model_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    model = registry["huggingface_models"]["wav2vec2_base_960h"]

    assert model["revision"] != "main"
    assert len(model["revision"]) == 40


def test_bootstrap_fallback_contains_wsl_diarization_repo_chain():
    from scripts import bootstrap_models
    from scripts.wsl_audio_preflight import _DIARIZATION_REPOS

    wanted = set(bootstrap_models.build_wanted_models(None))

    assert set(_DIARIZATION_REPOS).issubset(wanted)
    assert "pyannote/speaker-diarization" not in wanted


def test_bootstrap_fallback_contains_wsl_embedding_cache_gate_repo():
    from scripts import bootstrap_models

    wanted = set(bootstrap_models.build_wanted_models(None))

    assert "facebook/wav2vec2-base-960h" in wanted


def test_cache_readiness_inventory_contains_wsl_diarization_repo_chain():
    from scripts import cache_readiness_check
    from scripts.wsl_audio_preflight import _DIARIZATION_REPOS

    inventory = set(cache_readiness_check.MODEL_SNAPSHOTS)

    assert set(_DIARIZATION_REPOS).issubset(inventory)
    assert "pyannote/speaker-diarization@2.1" not in inventory


def test_cache_readiness_inventory_contains_wsl_embedding_cache_gate_repo():
    from scripts import cache_readiness_check

    inventory = set(cache_readiness_check.MODEL_SNAPSHOTS)

    assert "facebook/wav2vec2-base-960h" in inventory


def test_system_readiness_targets_active_wsl_diarization_repo_chain():
    from scripts import system_readiness_check
    from scripts.wsl_audio_preflight import _DIARIZATION_REPOS

    assert tuple(system_readiness_check.WSL_DIARIZATION_MODEL_REPOS) == tuple(_DIARIZATION_REPOS)


def test_system_readiness_targets_wsl_audio_cache_gate_repos():
    from scripts import system_readiness_check
    from scripts.wsl_audio_preflight import WSL_AUDIO_REQUIRED_CACHE_REPOS

    assert tuple(system_readiness_check.WSL_AUDIO_REQUIRED_CACHE_REPOS) == tuple(WSL_AUDIO_REQUIRED_CACHE_REPOS)


def test_phase2_segmentation_defaults_use_active_pyannote_model():
    import yaml

    from scripts.config_schema import Phase2Config

    config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    assert cfg["segmentation"]["phase2"]["model"] == "pyannote/segmentation-3.0"
    assert Phase2Config().model == "pyannote/segmentation-3.0"
