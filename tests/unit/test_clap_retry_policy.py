"""CLAP policy fault injection without models, GPU work or persisted stores."""
from contextlib import nullcontext
import sys
import types
from unittest.mock import Mock

import numpy as np
import pytest


@pytest.fixture
def worker(monkeypatch, tmp_path):
    monkeypatch.delenv("GOODQ_REQUIRE_GPU", raising=False)
    monkeypatch.setenv("GOODQ_NO_AUTO_GPU", "1")
    from steps.audio_embed_clap import step
    monkeypatch.setattr(step, "_CLAP", {"model": None, "proc": None, "device": "cpu", "model_dir": None})
    monkeypatch.setattr(step, "clear_cache", Mock())
    monkeypatch.setattr(step, "_inspect_audio_input", lambda _: None)
    monkeypatch.setattr(step, "_torchaudio_preflight", lambda: True)
    path = tmp_path / "scene.wav"
    path.write_bytes(b"isolated fixture; audio decoding is stubbed")
    return step, {"source_path": str(path)}


@pytest.mark.parametrize("required", [False, True])
def test_model_load_retry_honors_gpu_policy(worker, monkeypatch, required):
    step, item = worker
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", str(int(required)))
    monkeypatch.setattr(step, "_preferred_device", lambda: "cuda")
    load = Mock(return_value=(False, "CUDA out of memory"))
    monkeypatch.setattr(step, "_load", load)
    result = step.audio_embed_clap(item, {})
    assert result["clap_meta"]["status"] == "error"
    assert [c.args[0] for c in load.call_args_list] == (["cuda"] if required else ["cuda", "cpu"])


@pytest.mark.parametrize("cached", [False, True])
def test_forced_cpu_is_rejected_before_model_access(worker, monkeypatch, cached):
    step, item = worker
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.setenv("GOODQ_CLAP_FORCE_CPU", "1")
    model = Mock()
    if cached:
        step._CLAP["model"] = model
    # A rejected target must not even access model assets.
    monkeypatch.setattr(step, "_configure_model_env", Mock(side_effect=AssertionError("model access")))
    result = step.audio_embed_clap(item, {})
    assert result["clap_meta"]["status"] == "error"
    assert "GPU-required" in result["clap_meta"]["error"]
    model.to.assert_not_called()


def test_required_gpu_does_not_downgrade_when_cuda_disappears(worker, monkeypatch, tmp_path):
    step, _ = worker
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", "1")
    monkeypatch.setattr(step, "_configure_model_env", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "steps.common.model_provisioner", types.SimpleNamespace(
        ensure_model_cached=lambda *a, **kw: types.SimpleNamespace(status="ready", local_path=str(tmp_path)),
        resolve_models_root=lambda: tmp_path))
    monkeypatch.setitem(sys.modules, "steps.common.config_loader", types.SimpleNamespace(load_configs=lambda _: {}))
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False)))
    model, extractor = Mock(), Mock()
    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(ClapModel=model, AutoFeatureExtractor=extractor))
    ok, error = step._load("cuda")
    assert not ok and "CUDA is unavailable" in error
    model.from_pretrained.assert_not_called()
    extractor.from_pretrained.assert_not_called()


@pytest.mark.parametrize("required", [False, True])
def test_chunk_retry_preserves_required_policy_and_allowed_remaining_chunks(worker, monkeypatch, required):
    step, item = worker
    monkeypatch.setenv("GOODQ_REQUIRE_GPU", str(int(required)))
    monkeypatch.setattr(step, "_preferred_device", lambda: "cuda")
    loads, inferences = [], []
    def load(device):
        loads.append(device)
        step._CLAP["device"] = device
        return True, None
    monkeypatch.setattr(step, "_load", load)
    class Features:
        def to(self, device):
            inferences.append(device)
            if device == "cuda": raise RuntimeError("CUDA out of memory")
            return self
    class Embedding:
        def detach(self): return self
        def cpu(self): return self
        def mean(self, **kw): return self
        def numpy(self): return np.ones((1, 3), dtype="float32")
    step._CLAP.update(model=types.SimpleNamespace(get_audio_features=lambda **kw: Embedding()),
                      proc=lambda **kw: {"input_features": Features()})
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(no_grad=nullcontext, cat=lambda chunks, **kw: chunks[0]))
    monkeypatch.setitem(sys.modules, "librosa", types.SimpleNamespace(load=lambda *a, **kw: (np.ones(20), 48000)))
    monkeypatch.setitem(sys.modules, "soundfile", types.SimpleNamespace(info=lambda _: types.SimpleNamespace(frames=18, samplerate=1)))
    monkeypatch.setitem(sys.modules, "faiss", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "steps.text_embed.step", types.SimpleNamespace(_content_fingerprint=lambda _: "unused"))
    monkeypatch.setitem(sys.modules, "steps.common.memory_commit_events", types.SimpleNamespace(
        MemoryCommitEvent=lambda **kw: kw, emit_memory_commit_event=lambda *a: None, utc_now_iso=lambda: "test"))
    result = step.audio_embed_clap(item, {"vad_enabled": False})
    if required:
        assert result["clap_meta"]["status"] == "error"
        assert "CUDA out of memory" in result["clap_meta"]["error"]
        assert loads == ["cuda"]
        assert inferences == ["cuda"]
    else:
        assert result["clap_meta"]["status"] == "no_index_path"
        assert loads == ["cuda", "cpu"]
        assert inferences == ["cuda", "cpu", "cpu", "cpu"]
