from __future__ import annotations

import importlib
import sys
import types
from contextlib import nullcontext


def _load_image_caption_module():
    return importlib.import_module("steps.image_caption.step")


def _load_object_detect_module():
    return importlib.import_module("steps.object_detect.step")


def test_image_caption_reports_diagnostics_on_python_error(monkeypatch, tmp_path, capsys):
    module = _load_image_caption_module()

    image_path = tmp_path / "scene_0010.jpg"
    image_path.write_bytes(b"fake")

    class _FakePixels:
        shape = (1, 3, 384, 384)

    class _FakeBatch(dict):
        def __init__(self):
            super().__init__({"pixel_values": _FakePixels()})

        def to(self, _device):
            return self

    class _FakeProc:
        def __call__(self, **_kwargs):
            return _FakeBatch()

        def decode(self, *_args, **_kwargs):
            return "unused"

    class _FakeModel:
        def generate(self, **_kwargs):
            raise RuntimeError("synthetic caption failure")

    class _FakeImage:
        size = (640, 360)

        def convert(self, _mode):
            return self

    torch_mod = types.ModuleType("torch")
    torch_mod.float16 = "float16"
    torch_mod.no_grad = lambda: nullcontext()
    torch_mod.amp = types.SimpleNamespace(autocast=lambda **_kwargs: nullcontext())
    torch_mod.cuda = types.SimpleNamespace(
        is_available=lambda: True,
        memory_allocated=lambda: 1024 * 1024,
        memory_reserved=lambda: 2 * 1024 * 1024,
        max_memory_allocated=lambda: 3 * 1024 * 1024,
    )

    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = types.SimpleNamespace(open=lambda _path: _FakeImage())

    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setattr(module, "_load_blip", lambda: False)
    monkeypatch.setattr(module, "_BLIP", {"model": _FakeModel(), "proc": _FakeProc(), "device": "cuda"})
    monkeypatch.setattr(module.GPUManager, "clear_cache", lambda: None)

    result = module.image_caption({"source_path": str(image_path)}, {})
    caption_meta = result["caption_meta"]

    assert caption_meta["status"] == "error"
    assert caption_meta["exc_type"] == "RuntimeError"
    stderr = capsys.readouterr().err
    assert '"event": "image_caption_diagnostics"' in stderr
    assert '"stage": "before_inference"' in stderr


def test_object_detect_reports_diagnostics_on_python_error(monkeypatch, tmp_path, capsys):
    module = _load_object_detect_module()

    image_path = tmp_path / "scene_0013.jpg"
    image_path.write_bytes(b"fake")

    class _FakeImage:
        size = (576, 432)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    torch_mod = types.ModuleType("torch")
    torch_mod.cuda = types.SimpleNamespace(
        is_available=lambda: True,
        memory_allocated=lambda: 1024 * 1024,
        memory_reserved=lambda: 2 * 1024 * 1024,
        max_memory_allocated=lambda: 3 * 1024 * 1024,
    )

    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = types.SimpleNamespace(open=lambda _path: _FakeImage())

    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setattr(module, "_load_yolo", lambda _cfg: False)
    monkeypatch.setattr(module, "_YOLO", object())
    monkeypatch.setattr(module, "_YOLO_DEVICE", "cuda")
    monkeypatch.setattr(module, "_run_yolo", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic detect failure")))
    monkeypatch.setattr(module.GPUManager, "clear_cache", lambda: None)

    result = module.object_detect({"source_path": str(image_path)}, {})
    detect_meta = result["detect_meta"]

    assert detect_meta["status"] == "error"
    assert detect_meta["exc_type"] == "RuntimeError"
    stderr = capsys.readouterr().err
    assert '"event": "object_detect_diagnostics"' in stderr
    assert '"stage": "before_inference"' in stderr
