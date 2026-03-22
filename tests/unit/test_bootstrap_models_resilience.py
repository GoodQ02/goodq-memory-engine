from __future__ import annotations

import sys
import types
from pathlib import Path


def test_transient_download_error_classifier():
    from scripts import bootstrap_models

    assert bootstrap_models._is_transient_download_error("Read timed out while downloading")
    assert bootstrap_models._is_transient_download_error("HTTP 503 Server Error")
    assert not bootstrap_models._is_transient_download_error("401 Client Error: Unauthorized")


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
