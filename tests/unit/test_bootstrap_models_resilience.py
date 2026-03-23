from __future__ import annotations

import re
import sys
import types
from pathlib import Path


def test_transient_download_error_classifier():
    from scripts import bootstrap_models

    assert bootstrap_models._is_transient_download_error("Read timed out while downloading")
    assert bootstrap_models._is_transient_download_error("HTTP 503 Server Error")
    assert not bootstrap_models._is_transient_download_error("401 Client Error: Unauthorized")


def test_resolve_auth_tokens_uses_hf_hub_alias(monkeypatch):
    from scripts import bootstrap_models

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HF_HUB_TOKEN", "hf_test_alias_token")
    monkeypatch.delenv("PYANNOTE_TOKEN", raising=False)

    auth = bootstrap_models.resolve_auth_tokens()

    assert auth["hf_present"] is True
    assert auth["hf_source"] == "HF_HUB_TOKEN"
    assert auth["pyannote_present"] is True
    assert auth["pyannote_source"] == "HF_HUB_TOKEN"
    assert auth["hf_token"] == "hf_test_alias_token"
    assert auth["pyannote_token"] == "hf_test_alias_token"


def test_resolve_auth_tokens_ignores_placeholder_values(monkeypatch):
    from scripts import bootstrap_models

    monkeypatch.setenv("HF_TOKEN", "your_huggingface_token_here")
    monkeypatch.setenv("PYANNOTE_TOKEN", "your_pyannote_token_here")

    auth = bootstrap_models.resolve_auth_tokens()

    assert auth["hf_present"] is False
    assert auth["pyannote_present"] is False
    assert auth["hf_token"] is None
    assert auth["pyannote_token"] is None


def test_build_wanted_models_uses_registry_repo_ids():
    from scripts import bootstrap_models

    registry = {
        "huggingface_models": {
            "pyannote_diarization": {
                "repo_id": "pyannote/speaker-diarization",
                "revision": "25bcc7e3631933a02af5ee39379797d704aee3f8",
            },
            "pyannote_segmentation": {
                "repo_id": "pyannote/segmentation",
                "revision": "660b9e20307a2b0cdb400d0f80aadc04a701fc54",
            },
        }
    }

    wanted = bootstrap_models.build_wanted_models(registry)

    assert wanted == ["pyannote/speaker-diarization", "pyannote/segmentation"]
    assert all("@" not in model_id for model_id in wanted)


def test_model_registry_revisions_do_not_use_placeholder_hashes():
    import yaml

    registry_path = Path(__file__).resolve().parents[2] / "configs" / "model_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    huggingface_models = registry.get("huggingface_models", {})

    for model_key, model_info in huggingface_models.items():
        if not isinstance(model_info, dict):
            continue
        revision = str(model_info.get("revision") or "").strip()
        if not revision:
            continue
        assert not re.fullmatch(r"(.)\1{39}", revision), f"{model_key} uses a placeholder revision: {revision}"


def test_snapshot_retries_transient_failure(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_models

    attempts = {"count": 0}
    recorded_kwargs = {}

    def fake_snapshot_download(**kwargs):
        attempts["count"] += 1
        recorded_kwargs.update(kwargs)
        if attempts["count"] == 1:
            raise RuntimeError("Read timed out")
        snapshot_dir = tmp_path / "hub" / "models--laion--clap-htsat-unfused" / "snapshots" / "abc123"
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "config.json").write_text("{}", encoding="utf-8")
        return str(snapshot_dir)

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=fake_snapshot_download))
    monkeypatch.setattr(bootstrap_models, "_retry_pause", lambda attempt: None)

    result = bootstrap_models.snapshot(
        "laion/clap-htsat-unfused",
        models_root=tmp_path,
        retries=2,
        progress_label="1/1",
    )

    assert result["status"] == "ok"
    assert result["attempts"] == "2"
    assert attempts["count"] == 2
    assert recorded_kwargs["cache_dir"] == str(tmp_path / "hub")
    assert "local_dir" not in recorded_kwargs


def test_snapshot_stops_on_non_transient_failure(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_models

    attempts = {"count": 0}

    def fake_snapshot_download(**kwargs):
        attempts["count"] += 1
        raise RuntimeError("401 Client Error: Unauthorized")

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=fake_snapshot_download))
    monkeypatch.setattr(bootstrap_models, "_retry_pause", lambda attempt: None)

    result = bootstrap_models.snapshot(
        "pyannote/speaker-diarization",
        models_root=tmp_path,
        retries=4,
        progress_label="1/1",
    )

    assert result["status"] == "error"
    assert result["attempts"] == "1"
    assert attempts["count"] == 1


def test_snapshot_reports_error_when_cache_layout_is_not_runtime_compatible(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_models

    def fake_snapshot_download(**kwargs):
        flat_dir = tmp_path / "hub" / "models--laion--clap-htsat-unfused"
        flat_dir.mkdir(parents=True)
        (flat_dir / "config.json").write_text("{}", encoding="utf-8")
        return str(flat_dir)

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=fake_snapshot_download))

    result = bootstrap_models.snapshot(
        "laion/clap-htsat-unfused",
        models_root=tmp_path,
        retries=1,
        progress_label="1/1",
    )

    assert result["status"] == "error"
    assert "cache layout incomplete" in result["error"]
