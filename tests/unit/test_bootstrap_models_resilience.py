from __future__ import annotations

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


def test_snapshot_retries_transient_failure(monkeypatch, tmp_path: Path):
    from scripts import bootstrap_models

    attempts = {"count": 0}

    def fake_snapshot_download(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("Read timed out")
        return str(tmp_path / "hub" / "models--laion--clap-htsat-unfused" / "snapshots" / "abc123")

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
