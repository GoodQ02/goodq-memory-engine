from __future__ import annotations

import importlib
import sys
import types
from contextlib import nullcontext


def _load_module():
    return importlib.import_module("steps.image_embed_dino.step")


def test_resolve_device_honors_force_cpu(monkeypatch):
    module = _load_module()

    monkeypatch.setenv("GOODQ_DINO_FORCE_CPU", "1")

    assert module._resolve_device("cuda") == "cpu"
    assert module._resolve_device("cpu") == "cpu"


def test_amp_enabled_respects_device_and_override(monkeypatch):
    module = _load_module()

    monkeypatch.delenv("GOODQ_DINO_DISABLE_AMP", raising=False)
    assert module._amp_enabled("cpu") is False
    assert module._amp_enabled("cuda") is True

    monkeypatch.setenv("GOODQ_DINO_DISABLE_AMP", "1")
    assert module._amp_enabled("cuda") is False


def test_image_embed_dino_reports_diagnostics_on_python_error(monkeypatch, tmp_path):
    module = _load_module()

    image_path = tmp_path / "scene_0006.jpg"
    image_path.write_bytes(b"fake")

    class _FakePixels:
        shape = (1, 3, 224, 224)

    class _FakeBatch(dict):
        def __init__(self):
            super().__init__({"pixel_values": _FakePixels()})

        def to(self, _device):
            return self

    class _FakeProc:
        def __call__(self, **_kwargs):
            return _FakeBatch()

    class _FakeModel:
        def __call__(self, **_kwargs):
            raise RuntimeError("synthetic dino failure")

    class _FakeImage:
        size = (576, 432)

        def convert(self, _mode):
            return self

    torch_mod = types.ModuleType("torch")
    torch_mod.float16 = "float16"
    torch_mod.inference_mode = lambda: nullcontext()
    torch_mod.amp = types.SimpleNamespace(autocast=lambda **_kwargs: nullcontext())
    torch_mod.cuda = types.SimpleNamespace(
        is_available=lambda: True,
        memory_allocated=lambda: 1024 * 1024,
        memory_reserved=lambda: 2 * 1024 * 1024,
        max_memory_allocated=lambda: 3 * 1024 * 1024,
    )

    numpy_mod = types.ModuleType("numpy")
    numpy_mod.errstate = lambda **_kwargs: nullcontext()

    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = types.SimpleNamespace(open=lambda _path: _FakeImage())

    text_embed_mod = types.ModuleType("steps.text_embed.step")
    text_embed_mod._content_fingerprint = lambda _item: "deadbeef"

    faiss_mod = types.ModuleType("faiss")

    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    monkeypatch.setitem(sys.modules, "numpy", numpy_mod)
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setitem(sys.modules, "steps.text_embed.step", text_embed_mod)
    monkeypatch.setitem(sys.modules, "faiss", faiss_mod)

    monkeypatch.setattr(module, "_load", lambda: False)
    monkeypatch.setattr(module, "_DINO", {"model": _FakeModel(), "proc": _FakeProc(), "device": "cuda"})

    result = module.image_embed_dino(
        {"source_path": str(image_path)},
        {"paths": {"faiss_dino_path": str(tmp_path / "dino.index")}},
    )
    dino_meta = result["dino_meta"]

    assert dino_meta["status"] == "error"
    assert dino_meta["exc_type"] == "RuntimeError"
    assert dino_meta["device"] == "cuda"
    assert dino_meta["image_size"] == [576, 432]
    assert dino_meta["tensor_shape"] == [1, 3, 224, 224]
    assert dino_meta["amp_enabled"] is True
    assert dino_meta["gpu_memory_before"]["available"] is True
    assert dino_meta["gpu_memory_before"]["allocated_mb"] == 1.0
