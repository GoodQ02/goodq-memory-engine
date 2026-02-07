from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

import steps.audio_diarize.step as diarize_step


class _DummyOptimizer:
    def configure_for_diarization(self, _duration_minutes):
        return SimpleNamespace(memory_fraction=0.5)

    def warmup_gpu(self) -> None:
        return None

    def print_memory_stats(self) -> None:
        return None


class _FakePipeline:
    def __init__(self, *, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.to_calls: list[object] = []

    def to(self, device_obj: object) -> None:
        self.to_calls.append(device_obj)
        if self.fail_with is not None:
            raise self.fail_with


def _install_fake_pyannote(monkeypatch: pytest.MonkeyPatch, pipeline: _FakePipeline) -> None:
    pyannote_mod = types.ModuleType("pyannote")
    pyannote_audio_mod = types.ModuleType("pyannote.audio")

    class _PipelineLoader:
        @staticmethod
        def from_pretrained(_model_id, use_auth_token=None):
            return pipeline

    pyannote_audio_mod.Pipeline = _PipelineLoader
    monkeypatch.setitem(sys.modules, "pyannote", pyannote_mod)
    monkeypatch.setitem(sys.modules, "pyannote.audio", pyannote_audio_mod)


def _install_fake_torch(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    device_calls: list[str] = []
    torch_mod = types.ModuleType("torch")

    def _device(name: str) -> str:
        device_calls.append(name)
        return f"device:{name}"

    torch_mod.device = _device
    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    return device_calls


def _prepare_module_state(monkeypatch: pytest.MonkeyPatch) -> None:
    diarize_step._PIPELINES.clear()
    diarize_step._MODEL_WARMED_UP = True
    monkeypatch.setattr(diarize_step, "get_audio_gpu_optimizer", lambda: _DummyOptimizer())


def test_load_pipeline_cuda_path_imports_torch_and_moves_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_module_state(monkeypatch)
    fake_pipeline = _FakePipeline()
    _install_fake_pyannote(monkeypatch, fake_pipeline)
    device_calls = _install_fake_torch(monkeypatch)

    loaded = diarize_step._load_pipeline("fake-model", "cuda", "token")

    assert loaded is fake_pipeline
    assert device_calls == ["cuda"]
    assert fake_pipeline.to_calls == ["device:cuda"]


def test_load_pipeline_known_cuda_error_falls_back_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_module_state(monkeypatch)
    fake_pipeline = _FakePipeline(fail_with=RuntimeError("cuda unavailable"))
    _install_fake_pyannote(monkeypatch, fake_pipeline)
    _install_fake_torch(monkeypatch)

    loaded = diarize_step._load_pipeline("fake-model", "cuda", "token")

    assert loaded is fake_pipeline
    assert len(fake_pipeline.to_calls) == 1


def test_load_pipeline_unexpected_cuda_error_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_module_state(monkeypatch)
    fake_pipeline = _FakePipeline(fail_with=KeyError("unexpected"))
    _install_fake_pyannote(monkeypatch, fake_pipeline)
    _install_fake_torch(monkeypatch)

    with pytest.raises(KeyError, match="unexpected"):
        diarize_step._load_pipeline("fake-model", "cuda", "token")
