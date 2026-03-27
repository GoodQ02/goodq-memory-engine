from __future__ import annotations

import builtins
import importlib
import sys
import types

import pytest


_MISSING = object()


class _FakeCuda:
    def __init__(self, available: bool):
        self._available = available

    def is_available(self) -> bool:
        return self._available


def _make_fake_torch(cuda_available: bool) -> types.ModuleType:
    module = types.ModuleType("torch")
    module.cuda = _FakeCuda(cuda_available)
    return module


@pytest.fixture(autouse=True)
def _restore_scene_embedder_import_state():
    steps_video_pkg = importlib.import_module("steps.video")
    original_module = sys.modules.get("steps.video.scene_embedder")
    original_attr = getattr(steps_video_pkg, "scene_embedder", _MISSING)
    try:
        yield
    finally:
        if original_module is not None:
            sys.modules["steps.video.scene_embedder"] = original_module
        else:
            sys.modules.pop("steps.video.scene_embedder", None)

        if original_attr is _MISSING:
            if hasattr(steps_video_pkg, "scene_embedder"):
                delattr(steps_video_pkg, "scene_embedder")
        else:
            setattr(steps_video_pkg, "scene_embedder", original_attr)


def test_resolve_model_device_falls_back_to_cpu_when_gpu_manager_raises(monkeypatch):
    scene_embedder = importlib.import_module("steps.video.scene_embedder")

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "steps.common.gpu_config":
            raise RuntimeError("simulated_gpu_manager_failure")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    monkeypatch.setitem(sys.modules, "torch", _make_fake_torch(cuda_available=False))

    device = scene_embedder._resolve_model_device("scene_embedder_clip")

    assert device == "cpu"


def test_load_clip_model_uses_cpu_when_gpu_manager_import_fails(monkeypatch):
    scene_embedder = importlib.import_module("steps.video.scene_embedder")
    scene_embedder._MODELS["clip"] = {"model": None, "processor": None, "device": "cpu"}

    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "steps.common.gpu_config":
            raise RuntimeError("simulated_gpu_manager_failure")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    monkeypatch.setitem(sys.modules, "torch", _make_fake_torch(cuda_available=False))

    transformers = types.ModuleType("transformers")

    class _FakeProcessor:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return cls()

    class _FakeModel:
        def __init__(self):
            self.device = None

        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return cls()

        def to(self, device):
            self.device = device
            return self

        def eval(self):
            return self

    transformers.CLIPProcessor = _FakeProcessor
    transformers.CLIPModel = _FakeModel
    monkeypatch.setitem(sys.modules, "transformers", transformers)

    scene_embedder._load_clip_model()

    assert scene_embedder._MODELS["clip"]["model"] is not None
    assert scene_embedder._MODELS["clip"]["processor"] is not None
    assert scene_embedder._MODELS["clip"]["device"] == "cpu"
