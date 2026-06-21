from __future__ import annotations

import os
import sys
import pytest
import time
import threading
from pathlib import Path
from typing import Any, Dict

# Add repo root to path for imports
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

# Ensure vendor dir is in sys.path
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists() and str(_VENDOR_DIR) not in sys.path:
    sys.path.append(str(_VENDOR_DIR))

from steps.common.model_provisioner import (
    ensure_model_cached,
    resolve_models_root,
    resolve_hf_token,
    verify_snapshot_files,
    ModelProvisionResult
)
from scripts.login_hf import update_env_local
from scripts.utils.banned_token_lint import redact_token


def test_cached_model(tmp_path, monkeypatch):
    """Test that existing local snapshots are correctly returned as cached."""
    # Setup mock snapshot directory
    repo_id = "Salesforce/blip-image-captioning-base"
    repo_cache_dir = tmp_path / "hub" / f"models--Salesforce--blip-image-captioning-base"
    snapshots_dir = repo_cache_dir / "snapshots"
    revision_dir = snapshots_dir / "mock_revision_123"
    revision_dir.mkdir(parents=True, exist_ok=True)
    
    # Write mock model files
    (revision_dir / "config.json").write_text("{}", encoding="utf-8")
    (revision_dir / "pytorch_model.bin").write_bytes(b"\x00")
    
    # Mock resolve_models_root to return our temp path
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    # Run cache check
    res = ensure_model_cached("blip_caption", revision="mock_revision_123")
    
    assert res.status == "cached"
    assert res.repo_id == repo_id
    assert res.revision == "mock_revision_123"
    assert Path(res.local_path) == revision_dir.absolute()
    assert "pytorch_model.bin" in res.files_checked


def test_missing_online_model(tmp_path, monkeypatch):
    """Test that online downloads are triggered and cached when missing."""
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("GOODQ_OFFLINE", raising=False)
    repo_id = "Salesforce/blip-image-captioning-base"
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    download_calls = []
    
    def mock_snapshot_download(repo_id, cache_dir, revision, token, local_files_only):
        download_calls.append(repo_id)
        # Simulate successful download by creating target files
        resolved_dir = Path(cache_dir) / f"models--Salesforce--blip-image-captioning-base" / "snapshots" / "mock_revision_abc"
        resolved_dir.mkdir(parents=True, exist_ok=True)
        (resolved_dir / "config.json").write_text("{}", encoding="utf-8")
        (resolved_dir / "model.safetensors").write_bytes(b"\x00")
        return str(resolved_dir)
        
    monkeypatch.setattr("huggingface_hub.snapshot_download", mock_snapshot_download)
    
    res = ensure_model_cached("blip_caption", revision="mock_revision_abc", offline=False)
    
    assert res.status == "downloaded"
    assert res.repo_id == repo_id
    assert res.revision == "mock_revision_abc"
    assert len(download_calls) == 1
    assert "model.safetensors" in res.files_checked


def test_missing_offline_model(tmp_path, monkeypatch):
    """Test that missing required models fail and optional models skip in offline mode."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    # Required model fails
    res_req = ensure_model_cached("blip_caption", offline=True)
    assert res_req.status == "offline_missing"
    assert res_req.required is True
    
    # Optional model fails but shows optional status
    res_opt = ensure_model_cached("vit_gpt2_caption", offline=True)
    assert res_opt.status == "offline_missing"
    assert res_opt.required is False


def test_gated_unauthorized_model(tmp_path, monkeypatch):
    """Test that gated models fail with gated_unauthorized when token is missing/invalid."""
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("GOODQ_OFFLINE", raising=False)
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    monkeypatch.setattr("steps.common.model_provisioner.resolve_hf_token", lambda repo_id=None: None)
    
    # 1. Gated with missing token
    res = ensure_model_cached("pyannote_diarization", offline=False)
    assert res.status == "gated_unauthorized"
    
    # 2. Gated with invalid token raising auth error
    monkeypatch.setattr("steps.common.model_provisioner.resolve_hf_token", lambda repo_id=None: "invalid_token")
    
    def mock_snapshot_download_fail(*args, **kwargs):
        raise OSError("401 Unauthorized: Access to this gated repo is forbidden.")
        
    monkeypatch.setattr("huggingface_hub.snapshot_download", mock_snapshot_download_fail)
    
    res = ensure_model_cached("pyannote_diarization", offline=False)
    assert res.status == "gated_unauthorized"
    assert "gated" in res.error.lower()


def test_env_local_merge_behavior(tmp_path):
    """Test that writing HF token to .env.local preserves existing environment keys."""
    env_file = tmp_path / ".env.local"
    env_file.write_text("DB_PATH=L:/database.db\nEXISTING_KEY=123\n", encoding="utf-8")
    
    # Write token
    update_env_local(env_file, "hf_testtoken12345")
    
    content = env_file.read_text(encoding="utf-8")
    assert "DB_PATH=L:/database.db" in content
    assert "EXISTING_KEY=123" in content
    assert "HF_TOKEN=hf_testtoken12345" in content
    assert "PYANNOTE_TOKEN=hf_testtoken12345" in content


def test_invalid_token_redaction():
    """Verify that sensitive Hugging Face tokens are redacted for logging safety."""
    raw_token = "hf_1234567890abcdef1234567890abcdef12"
    redacted = redact_token(raw_token)
    assert redacted == "hf_12...def12"
    assert raw_token not in redacted


def test_clap_bin_and_safetensors_acceptance(tmp_path, monkeypatch):
    """Verify that CLAP cache validation accepts either .bin or .safetensors weights."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    repo_cache_dir = tmp_path / "hub" / "models--laion--clap-htsat-unfused"
    snapshots_dir = repo_cache_dir / "snapshots" / "clap_rev"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Safe config, missing weights
    (snapshots_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshots_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    res = ensure_model_cached("clap_audio", revision="clap_rev", offline=True)
    assert res.status == "offline_missing"
    
    # 2. Add pytorch_model.bin
    bin_file = snapshots_dir / "pytorch_model.bin"
    bin_file.write_bytes(b"\x00")
    res = ensure_model_cached("clap_audio", revision="clap_rev", offline=True)
    assert res.status == "cached"
    assert "pytorch_model.bin" in res.files_checked
    
    # 3. Swap for model.safetensors
    bin_file.unlink()
    (snapshots_dir / "model.safetensors").write_bytes(b"\x00")
    res = ensure_model_cached("clap_audio", revision="clap_rev", offline=True)
    assert res.status == "cached"
    assert "model.safetensors" in res.files_checked


def test_blip_local_loading(tmp_path, monkeypatch):
    """Test that the BLIP captioning loader works with our model provisioner."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    from steps.common.model_provisioner import lookup_model
    repo_id, metadata = lookup_model("blip_caption")
    rev = metadata.get("revision") or "blip_rev"
    
    # Setup mock local snapshot directory
    repo_cache_dir = tmp_path / "hub" / "models--Salesforce--blip-image-captioning-base"
    snapshots_dir = repo_cache_dir / "snapshots" / rev
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshots_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (snapshots_dir / "model.safetensors").write_bytes(b"\x00")
    
    # Write refs/main
    refs_dir = repo_cache_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "main").write_text(rev, encoding="utf-8")

    # Mock HF loader classes
    class MockBlipProcessor:
        @classmethod
        def from_pretrained(cls, path, local_files_only):
            assert local_files_only is True
            assert rev in str(path)
            return "mock_processor"
            
    class MockBlipGeneration:
        @classmethod
        def from_pretrained(cls, path, local_files_only):
            assert local_files_only is True
            assert rev in str(path)
            # Create a mock model class
            class MockModel:
                def to(self, device):
                    return self
                def eval(self):
                    return self
            return MockModel()
            
    # Mock system configuration and imports
    monkeypatch.setattr("steps.image_caption.step.setup_step_gpu", lambda name: {"device": "cpu", "memory_fraction": 0.0})
    
    import sys
    import types
    transformers_mock = types.ModuleType("transformers")
    transformers_mock.BlipProcessor = MockBlipProcessor
    transformers_mock.BlipForConditionalGeneration = MockBlipGeneration
    monkeypatch.setitem(sys.modules, "transformers", transformers_mock)
    
    # Mock config loader to enable offline mode
    import steps.common.config_loader
    monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda *args: {"verification": {"offline_mode": True}})
    
    from steps.image_caption.step import _load_blip, _BLIP
    # Clear existing cached model
    _BLIP.update({"model": None, "proc": None, "device": "cpu"})
    
    success = _load_blip()
    assert success is True
    assert _BLIP["proc"] == "mock_processor"
    assert _BLIP["model"] is not None


def test_concurrent_provisioning_lock_behavior(tmp_path, monkeypatch):
    """Test that locks prevent multiple workers from running downloads concurrently."""
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("GOODQ_OFFLINE", raising=False)
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    barrier = threading.Barrier(2)
    thread_logs = []
    
    def mock_snapshot_download(repo_id, cache_dir, revision, token, local_files_only):
        thread_logs.append(f"start:{threading.current_thread().name}")
        # Wait for the other thread to wait on the lock
        time.sleep(0.3)
        resolved_dir = Path(cache_dir) / f"models--laion--clap-htsat-unfused" / "snapshots" / "clap_concurrent"
        resolved_dir.mkdir(parents=True, exist_ok=True)
        (snapshots_dir := resolved_dir).mkdir(parents=True, exist_ok=True)
        (snapshots_dir / "config.json").write_text("{}", encoding="utf-8")
        (snapshots_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")
        (snapshots_dir / "pytorch_model.bin").write_bytes(b"\x00")
        
        thread_logs.append(f"end:{threading.current_thread().name}")
        return str(resolved_dir)
        
    monkeypatch.setattr("huggingface_hub.snapshot_download", mock_snapshot_download)
    
    def worker():
        barrier.wait()
        ensure_model_cached("clap_audio", revision="clap_concurrent", offline=False)
        
    t1 = threading.Thread(target=worker, name="Worker1")
    t2 = threading.Thread(target=worker, name="Worker2")
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # Due to locking:
    # Worker1 must start and end before Worker2 starts download (or vice versa)
    # The order of logs must not have overlapping starts/ends, i.e.,
    # start:T1, end:T1, then the second one retrieves from cache and does NOT call download!
    # So we should see exactly one "start" and "end" log call!
    start_calls = [log for log in thread_logs if log.startswith("start:")]
    end_calls = [log for log in thread_logs if log.startswith("end:")]
    
    assert len(start_calls) == 1
    assert len(end_calls) == 1


def test_model_provision_result_token_redaction():
    """Verify that ModelProvisionResult.__post_init__ automatically redacts tokens from errors."""
    res = ModelProvisionResult(
        status="failed",
        repo_id="test/repo",
        revision="main",
        local_path=None,
        gated=True,
        required=True,
        elapsed_seconds=1.0,
        error="Invalid token hf_1234567890abcdef1234567890abcdef12 detected."
    )
    assert "hf_1234567890abcdef1234567890abcdef12" not in res.error
    assert "hf_***" in res.error


def test_global_offline_environment_flags(tmp_path, monkeypatch):
    """Verify that global offline environment flags are respected."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    monkeypatch.setenv("GOODQ_OFFLINE", "1")
    
    res = ensure_model_cached("blip_caption", offline=False)
    assert res.status == "offline_missing"
    assert "Offline mode" in res.error

    monkeypatch.delenv("GOODQ_OFFLINE")
    monkeypatch.setenv("HF_HUB_OFFLINE", "true")
    res2 = ensure_model_cached("blip_caption", offline=False)
    assert res2.status == "offline_missing"
    assert "Offline mode" in res2.error


def test_download_logging_redaction(tmp_path, monkeypatch):
    """Verify that download events are logged and tokens in log files are redacted."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    
    # Run a cached check which will trigger log_download_event
    repo_cache_dir = tmp_path / "hub" / "models--Salesforce--blip-image-captioning-base"
    snapshots_dir = repo_cache_dir / "snapshots" / "blip_rev"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshots_dir / "pytorch_model.bin").write_bytes(b"\x00")
    
    ensure_model_cached("blip_caption", revision="blip_rev")
    
    # Check log file
    log_file = tmp_path.parent / "logs" / "model_downloads.log"
    assert log_file.is_file()
    
    # Write a test log event with a token and check it's redacted
    from steps.common.model_provisioner import log_download_event
    log_download_event("User attempted login with token hf_1234567890abcdef1234567890abcdef12", "test_model")
    
    content = log_file.read_text(encoding="utf-8")
    assert "hf_1234567890abcdef1234567890abcdef12" not in content
    assert "hf_***" in content


def test_new_models_provisioning(tmp_path, monkeypatch):
    """Verify caching checks for newly registered models: emotion_classify_model, sentiment_model, and silero_vad."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)

    # 1. Silero VAD
    vad_cache_dir = tmp_path / "hub" / "models--snakers4--silero-vad"
    vad_snapshots = vad_cache_dir / "snapshots" / "vad_rev"
    vad_snapshots.mkdir(parents=True, exist_ok=True)
    # VAD accepts .pt or .onnx files
    (vad_snapshots / "model.pt").write_bytes(b"\x00")
    res_vad = ensure_model_cached("silero_vad", revision="vad_rev", offline=True)
    assert res_vad.status == "cached"
    assert "model.pt" in res_vad.files_checked

    # 2. Emotion Classify Model
    emo_cache_dir = tmp_path / "hub" / "models--cardiffnlp--twitter-roberta-base-emotion-multilabel-latest"
    emo_snapshots = emo_cache_dir / "snapshots" / "emo_rev"
    emo_snapshots.mkdir(parents=True, exist_ok=True)
    (emo_snapshots / "config.json").write_text("{}", encoding="utf-8")
    (emo_snapshots / "model.safetensors").write_bytes(b"\x00")
    res_emo = ensure_model_cached("emotion_classify_model", revision="emo_rev", offline=True)
    assert res_emo.status == "cached"
    assert "model.safetensors" in res_emo.files_checked

    # 3. Sentiment Model
    sent_cache_dir = tmp_path / "hub" / "models--distilbert-base-uncased-finetuned-sst-2-english"
    sent_snapshots = sent_cache_dir / "snapshots" / "sent_rev"
    sent_snapshots.mkdir(parents=True, exist_ok=True)
    (sent_snapshots / "config.json").write_text("{}", encoding="utf-8")
    (sent_snapshots / "pytorch_model.bin").write_bytes(b"\x00")
    res_sent = ensure_model_cached("sentiment_model", revision="sent_rev", offline=True)
    assert res_sent.status == "cached"
    assert "pytorch_model.bin" in res_sent.files_checked


def test_external_models_caching(tmp_path, monkeypatch):
    """Verify caching check for external models: yolo_v8n and facenet_vggface2."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)

    # 1. yolo_v8n
    yolo_file = tmp_path / "yolo" / "yolov8n.pt"
    yolo_file.parent.mkdir(parents=True, exist_ok=True)
    yolo_file.write_bytes(b"\x00" * 2000)
    res_yolo = ensure_model_cached("yolo_v8n", offline=True)
    assert res_yolo.status == "cached"
    assert "yolov8n.pt" in res_yolo.files_checked
    assert Path(res_yolo.local_path) == yolo_file.absolute()

    # 2. facenet_vggface2
    facenet_file = tmp_path / "checkpoints" / "20180402-114759-vggface2.pt"
    facenet_file.parent.mkdir(parents=True, exist_ok=True)
    facenet_file.write_bytes(b"\x00" * 2000)
    res_face = ensure_model_cached("facenet_vggface2", offline=True)
    assert res_face.status == "cached"
    assert "20180402-114759-vggface2.pt" in res_face.files_checked
    assert Path(res_face.local_path) == facenet_file.absolute()


def test_external_models_offline_missing(tmp_path, monkeypatch):
    """Verify offline missing behavior for external models."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)

    res = ensure_model_cached("yolo_v8n", offline=True)
    assert res.status == "offline_missing"
    assert "yolo_v8n" in res.error


def test_external_models_online_download(tmp_path, monkeypatch):
    """Verify online download behavior for external models."""
    monkeypatch.setattr("steps.common.model_provisioner.resolve_models_root", lambda: tmp_path)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("GOODQ_OFFLINE", raising=False)

    download_calls = []

    class MockResponse:
        def __init__(self):
            self.data = b"\x00" * 2000
        def read(self, amt=None):
            if amt is None:
                d = self.data
                self.data = b""
                return d
            else:
                d = self.data[:amt]
                self.data = self.data[amt:]
                return d
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        download_calls.append(url)
        return MockResponse()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    res = ensure_model_cached("yolo_v8n", offline=False)
    assert res.status == "downloaded"
    assert "yolov8n.pt" in res.files_checked
    assert len(download_calls) == 1
    assert "yolov8n.pt" in download_calls[0]

