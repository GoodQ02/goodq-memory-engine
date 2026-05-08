from __future__ import annotations

import json
import os
import re
import sys
import types
from argparse import Namespace
from pathlib import Path


def test_transient_download_error_classifier():
    from scripts import bootstrap_models

    assert bootstrap_models._is_transient_download_error("Read timed out while downloading")
    assert bootstrap_models._is_transient_download_error("HTTP 503 Server Error")
    assert not bootstrap_models._is_transient_download_error("401 Client Error: Unauthorized")


def test_resolve_auth_tokens_uses_hf_hub_alias(monkeypatch):
    from scripts import bootstrap_models

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
    monkeypatch.setenv("HF_HUB_TOKEN", "hf_test_alias_token")
    monkeypatch.delenv("PYANNOTE_TOKEN", raising=False)

    auth = bootstrap_models.resolve_auth_tokens({})

    assert auth["hf_present"] is True
    assert auth["hf_source"] == "HF_HUB_TOKEN"
    assert auth["pyannote_present"] is True
    assert auth["pyannote_source"] == "HF_HUB_TOKEN"
    assert auth["hf_token"] == "hf_test_alias_token"
    assert auth["pyannote_token"] == "hf_test_alias_token"


def test_resolve_auth_tokens_ignores_placeholder_values(monkeypatch):
    from scripts import bootstrap_models

    monkeypatch.setenv("HF_TOKEN", "your_huggingface_token_here")
    monkeypatch.delenv("HF_HUB_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
    monkeypatch.setenv("PYANNOTE_TOKEN", "your_pyannote_token_here")

    auth = bootstrap_models.resolve_auth_tokens({})

    assert auth["hf_present"] is False
    assert auth["pyannote_present"] is False
    assert auth["hf_token"] is None
    assert auth["pyannote_token"] is None


def test_resolve_auth_tokens_prefers_env_file_over_ambient_env(monkeypatch):
    from scripts import bootstrap_models

    monkeypatch.setenv("HF_TOKEN", "hf_ambient_shell_token")
    monkeypatch.setenv("HF_HUB_TOKEN", "hf_ambient_alias_token")
    monkeypatch.setenv("PYANNOTE_TOKEN", "py_ambient_shell_token")

    auth = bootstrap_models.resolve_auth_tokens(
        {
            "HF_TOKEN": "hf_file_token",
            "PYANNOTE_TOKEN": "py_file_token",
        }
    )

    assert auth["hf_present"] is True
    assert auth["pyannote_present"] is True
    assert auth["hf_source"] == "HF_TOKEN"
    assert auth["pyannote_source"] == "PYANNOTE_TOKEN"
    assert auth["hf_token"] == "hf_file_token"
    assert auth["pyannote_token"] == "py_file_token"
    assert os.environ["HF_TOKEN"] == "hf_file_token"
    assert os.environ["HF_HUB_TOKEN"] == "hf_file_token"
    assert os.environ["PYANNOTE_TOKEN"] == "py_file_token"


def test_resolve_auth_tokens_env_file_placeholder_blocks_ambient_alias(monkeypatch):
    from scripts import bootstrap_models

    monkeypatch.setenv("HF_HUB_TOKEN", "hf_real_ambient_alias")

    auth = bootstrap_models.resolve_auth_tokens(
        {
            "HF_TOKEN": "your_huggingface_token_here",
        }
    )

    assert auth["hf_present"] is False
    assert auth["hf_token"] is None


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


def test_snapshot_writes_main_ref_for_pinned_revision(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_models

    pinned_revision = "84fd25912480287da0247647c3d2b4853cb3ee5d"

    def fake_snapshot_download(**kwargs):
        snapshot_dir = (
            tmp_path
            / "hub"
            / "models--pyannote--speaker-diarization-3.1"
            / "snapshots"
            / pinned_revision
        )
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "config.yaml").write_text("pipeline: test\n", encoding="utf-8")
        return str(snapshot_dir)

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=fake_snapshot_download))

    result = bootstrap_models.snapshot(
        "pyannote/speaker-diarization-3.1",
        revision=pinned_revision,
        models_root=tmp_path,
        retries=1,
        progress_label="1/1",
    )

    assert result["status"] == "ok"
    ref_path = tmp_path / "hub" / "models--pyannote--speaker-diarization-3.1" / "refs" / "main"
    assert ref_path.read_text(encoding="utf-8") == pinned_revision
    assert ref_path.read_bytes() == pinned_revision.encode("utf-8")


def test_main_writes_incremental_progress_and_partial_report(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_models

    report_path = tmp_path / "logs" / "bootstrap_models_report.json"
    progress_path = tmp_path / "logs" / "bootstrap_models_progress.json"
    models_root = tmp_path / "models"
    registry = {
        "huggingface_models": {
            "first": {"repo_id": "org/model-one", "revision": "rev-one"},
            "second": {"repo_id": "org/model-two", "revision": "rev-two"},
        }
    }

    snapshot_calls = {"count": 0}

    def fake_snapshot(model_id, auth_token=None, revision=None, **kwargs):
        snapshot_calls["count"] += 1
        live_progress = json.loads(progress_path.read_text(encoding="utf-8"))
        if snapshot_calls["count"] == 1:
            assert live_progress["current_model"] == "org/model-one"
            assert live_progress["current_index"] == 1
        else:
            partial_report = json.loads(report_path.read_text(encoding="utf-8"))
            assert partial_report["completed_count"] == 1
            assert partial_report["results"][0]["model"] == "org/model-one"
        if kwargs.get("progress_cb"):
            kwargs["progress_cb"](current_attempt=1, last_event="fake_snapshot_ready")
        return {
            "model": model_id,
            "status": "ok",
            "path": str(models_root / model_id.replace("/", "--")),
            "attempts": "1",
        }

    def fake_yolo(**kwargs):
        live_progress = json.loads(progress_path.read_text(encoding="utf-8"))
        assert live_progress["current_model"] == "yolov8n.pt"
        return {"asset": "yolov8n.pt", "status": "ok", "path": str(models_root / "yolo" / "yolov8n.pt"), "attempts": "1"}

    monkeypatch.setattr(bootstrap_models, "parse_args", lambda: Namespace(report_path=str(report_path), progress_path=str(progress_path), retries=1))
    monkeypatch.setattr(bootstrap_models, "load_registry", lambda repo_root: registry)
    monkeypatch.setattr(bootstrap_models, "resolve_models_root", lambda: models_root)
    monkeypatch.setattr(bootstrap_models, "ensure_env", lambda path: None)
    monkeypatch.setattr(
        bootstrap_models,
        "resolve_auth_tokens",
        lambda: {
            "hf_token": None,
            "hf_source": None,
            "pyannote_token": None,
            "pyannote_source": None,
            "hf_present": False,
            "pyannote_present": False,
        },
    )
    monkeypatch.setattr(bootstrap_models, "load_dotenv", None)
    monkeypatch.setattr(bootstrap_models, "snapshot", fake_snapshot)
    monkeypatch.setattr(bootstrap_models, "download_yolo_n", fake_yolo)

    bootstrap_models.main()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert report["status"] == "complete"
    assert report["completed_count"] == 3
    assert len(report["results"]) == 3
    assert progress["status"] == "complete"
    assert progress["completed_count"] == 3
    assert progress["current_model"] is None
    assert progress["last_event"] == "bootstrap_complete"


def test_main_persists_partial_report_on_keyboard_interrupt(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_models

    report_path = tmp_path / "logs" / "bootstrap_models_report.json"
    progress_path = tmp_path / "logs" / "bootstrap_models_progress.json"
    models_root = tmp_path / "models"
    registry = {
        "huggingface_models": {
            "first": {"repo_id": "org/model-one", "revision": "rev-one"},
            "second": {"repo_id": "org/model-two", "revision": "rev-two"},
        }
    }

    snapshot_calls = {"count": 0}

    def fake_snapshot(model_id, auth_token=None, revision=None, **kwargs):
        snapshot_calls["count"] += 1
        if snapshot_calls["count"] == 1:
            return {
                "model": model_id,
                "status": "ok",
                "path": str(models_root / model_id.replace("/", "--")),
                "attempts": "1",
            }
        raise KeyboardInterrupt()

    monkeypatch.setattr(bootstrap_models, "parse_args", lambda: Namespace(report_path=str(report_path), progress_path=str(progress_path), retries=1))
    monkeypatch.setattr(bootstrap_models, "load_registry", lambda repo_root: registry)
    monkeypatch.setattr(bootstrap_models, "resolve_models_root", lambda: models_root)
    monkeypatch.setattr(bootstrap_models, "ensure_env", lambda path: None)
    monkeypatch.setattr(
        bootstrap_models,
        "resolve_auth_tokens",
        lambda: {
            "hf_token": None,
            "hf_source": None,
            "pyannote_token": None,
            "pyannote_source": None,
            "hf_present": False,
            "pyannote_present": False,
        },
    )
    monkeypatch.setattr(bootstrap_models, "load_dotenv", None)
    monkeypatch.setattr(bootstrap_models, "snapshot", fake_snapshot)

    try:
        bootstrap_models.main()
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("expected KeyboardInterrupt")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert report["status"] == "interrupted"
    assert report["completed_count"] == 1
    assert report["current_model"] == "org/model-two"
    assert progress["status"] == "interrupted"
    assert progress["completed_count"] == 1
    assert progress["current_model"] == "org/model-two"
    assert progress["last_event"] == "keyboard_interrupt"
