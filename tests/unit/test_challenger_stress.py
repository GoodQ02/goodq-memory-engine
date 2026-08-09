from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Ensure repo root is in path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def test_resolve_wsl_distro_stress_encodings(monkeypatch, tmp_path):
    """Stress test the WSL distro resolution decoding under weird outputs and encodings."""
    from api.routes import runtime
    
    db_path = tmp_path / "memory.db"
    monkeypatch.delenv("GOODQ_WSL_DISTRO", raising=False)
    monkeypatch.setitem(runtime._HOST_CFG, "wsl_distro", "auto")
    
    # Mock subprocess.run to simulate various outputs
    def make_fake_run(stdout_bytes):
        def _fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout=stdout_bytes, stderr=b"")
        return _fake_run

    # Test 1: Null-byte polluted UTF-16-LE
    monkeypatch.setattr(runtime.subprocess, "run", make_fake_run(
        "Ubuntu-22.04\x00\r\x00\n\x00GoodQ_Audio_Distro\x00\r\x00\n\x00".encode("utf-16-le")
    ))
    assert runtime._resolve_wsl_distro() == "GoodQ_Audio_Distro"

    # Test 2: Standard UTF-8 with windows line endings
    monkeypatch.setattr(runtime.subprocess, "run", make_fake_run(
        b"LegacyUbuntu\r\nUbuntu-20.04\r\n"
    ))
    assert runtime._resolve_wsl_distro() == "LegacyUbuntu"

    # Test 3: Empty output
    monkeypatch.setattr(runtime.subprocess, "run", make_fake_run(b""))
    assert runtime._resolve_wsl_distro() == "Ubuntu"

    # Test 4: Exception raised (e.g. FileNotFoundError when wsl is missing)
    def err_run(*args, **kwargs):
        raise FileNotFoundError("wsl.exe not found")
    monkeypatch.setattr(runtime.subprocess, "run", err_run)
    assert runtime._resolve_wsl_distro() == "Ubuntu"

    # Test 5: TimeoutExpired exception
    def timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args, timeout=1.0)
    monkeypatch.setattr(runtime.subprocess, "run", timeout_run)
    assert runtime._resolve_wsl_distro() == "Ubuntu"

def test_bootstrap_models_report_has_no_retired_object_detector_mapping(monkeypatch, tmp_path):
    """Bootstrap covers Hugging Face models only; sealed detectors are installer assets."""
    from scripts import bootstrap_models
    
    # We will invoke _build_report with simulated results
    results = [
        {"repo_id": "laion/clap-htsat-unfused", "status": "ok"},
    ]
    
    # Mock lookup_model to see what gets requested
    looked_up = []
    
    def fake_lookup(repo_id_or_key):
        looked_up.append(repo_id_or_key)
        return repo_id_or_key, {
            "tier_scope": ["cpu_only"],
            "gated": False,
            "requires_token": False,
            "failure_behavior": "FATAL_HALT"
        }
    
    # We mock steps.common.model_provisioner.lookup_model in the module namespace
    import steps.common.model_provisioner
    monkeypatch.setattr(steps.common.model_provisioner, "lookup_model", fake_lookup)
    
    report = bootstrap_models._build_report(
        models_root=tmp_path,
        registry_loaded=True,
        pinned_models_count=1,
        retries=1,
        auth={"hf_token": None, "hf_source": None, "pyannote_token": None, "pyannote_source": None, "hf_present": False, "pyannote_present": False},
        results=results,
        status="complete",
        progress_path=tmp_path / "progress.json"
    )
    
    assert looked_up == ["laion/clap-htsat-unfused"]
    
def test_bootstrap_verify_detect_goodq_audio_distro(monkeypatch):
    """Verify bootstrap_verify._detect_wsl_distro finds GoodQ_Audio_Distro."""
    from scripts import bootstrap_verify
    
    monkeypatch.setattr(
        bootstrap_verify.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args,
            0,
            stdout="Ubuntu-20.04\nGoodQ_Audio_Distro\n",
            stderr="",
        ),
    )
    
    success, chosen, distros = bootstrap_verify._detect_wsl_distro()
    assert success is True
    assert chosen == "GoodQ_Audio_Distro"
    assert "GoodQ_Audio_Distro" in distros
