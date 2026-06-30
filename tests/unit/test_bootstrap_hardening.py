import os
import json
import pytest
from pathlib import Path
from scripts.bootstrap_models import resolve_active_scopes, _build_report
from steps.common.model_provisioner import lookup_model

def test_resolve_active_scopes_default(tmp_path, monkeypatch):
    # Unset env vars
    monkeypatch.delenv("GOODQ_DATA_ROOT", raising=False)
    monkeypatch.delenv("GOODQ_DEV_MODE", raising=False)
    monkeypatch.delenv("GOODQ_DEV_PYTHON", raising=False)
    
    scopes = resolve_active_scopes(tmp_path)
    assert "baseline" in scopes
    assert "cpu_only" in scopes
    assert "gpu_enhanced" in scopes
    assert "wsl_audio" not in scopes

def test_resolve_active_scopes_from_receipt(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    receipt_path = data_dir / "install_receipt.json"
    
    receipt_data = {
        "baseline_status": "ok",
        "cpu_status": "ok",
        "gpu_enhanced_status": "installed",
        "wsl_status": "installed"
    }
    receipt_path.write_text(json.dumps(receipt_data), encoding="utf-8")
    
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(data_dir))
    scopes = resolve_active_scopes(tmp_path)
    
    assert "baseline" in scopes
    assert "cpu_only" in scopes
    assert "gpu_enhanced" in scopes
    assert "wsl_audio" in scopes

def test_build_report_counts():
    results = [
        {"repo_id": "sentence-transformers/all-MiniLM-L6-v2", "status": "success", "elapsed": 0.5},
        {"repo_id": "laion/clap-htsat-unfused", "status": "error", "error": "connection failed", "elapsed": 0.2},
        {"repo_id": "pyannote/speaker-diarization-3.1", "status": "error", "error": "gated skip", "elapsed": 0.1}
    ]
    
    # In baseline scope, clap_audio and pyannote are optional or inactive. Only sentence-transformer is active.
    report = _build_report(
        models_root=Path("."),
        registry_loaded=True,
        pinned_models_count=1,
        retries=3,
        auth={"hf_present": False, "hf_source": None, "pyannote_present": False, "pyannote_source": None},
        results=results,
        status="complete",
        progress_path=Path("."),
        active_scopes=["baseline"]
    )
    
    # check keys
    assert report["total_assets"] == 3
    assert report["success_count"] == 1
    assert report["error_count"] == 2
    assert report["final_status"] == "partial"  # since no required fatal failures for baseline
    assert "laion/clap-htsat-unfused" in report["failed_optional_assets"]
    assert "pyannote/speaker-diarization-3.1" in report["failed_optional_assets"]
    assert len(report["failed_required_assets"]) == 0
