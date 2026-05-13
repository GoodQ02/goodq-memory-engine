from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np

from steps.face_embed import step as face_step


def test_face_recognition_stack_available_requires_models(monkeypatch):
    def _fake_find_spec(name: str):
        if name == "face_recognition":
            return object()
        if name == "face_recognition_models":
            return None
        return object()

    monkeypatch.setattr(face_step.importlib.util, "find_spec", _fake_find_spec)

    assert face_step._face_recognition_stack_available() is False


def test_face_recognition_stack_available_false_when_models_import_breaks(monkeypatch):
    monkeypatch.setattr(face_step.importlib.util, "find_spec", lambda _name: object())

    def _fake_import_module(name: str):
        if name == "face_recognition_models":
            raise ModuleNotFoundError("No module named 'pkg_resources'")
        return object()

    monkeypatch.setattr(face_step.importlib, "import_module", _fake_import_module)

    assert face_step._face_recognition_stack_available() is False


def test_face_embed_falls_back_to_facenet_when_dlib_stack_missing(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake")

    monkeypatch.setattr(face_step, "_face_recognition_stack_available", lambda: False)
    monkeypatch.setattr(face_step, "setup_step_gpu", lambda _step: {"device": "cpu", "memory_fraction": 0.0})

    fake_torch = types.ModuleType("torch")

    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_torch.no_grad = lambda: _NoGrad()

    class _FakeImage:
        def convert(self, _mode):
            return self

        def crop(self, _box):
            return self

        def resize(self, _size):
            return self

    fake_pil_image = types.SimpleNamespace(open=lambda _path: _FakeImage())
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = fake_pil_image

    class _FakeTensor:
        def unsqueeze(self, _dim):
            return self

        def to(self, _device):
            return self

    class _FakeToTensor:
        def __call__(self, _img):
            return _FakeTensor()

    fake_transforms = types.SimpleNamespace(ToTensor=lambda: _FakeToTensor())
    fake_torchvision = types.ModuleType("torchvision")
    fake_torchvision.transforms = fake_transforms

    class _FakeMTCNN:
        def __init__(self, *args, **kwargs):
            pass

        def detect(self, _img):
            return np.array([[1, 2, 3, 4]], dtype=float), None

    class _FakeEmbedding:
        def cpu(self):
            return self

        def numpy(self):
            return np.array([[0.1, 0.2, 0.3]], dtype=float)

    class _FakeResnet:
        def eval(self):
            return self

        def to(self, _device):
            return self

        def __call__(self, _tensor):
            return _FakeEmbedding()

    fake_facenet = types.ModuleType("facenet_pytorch")
    fake_facenet.MTCNN = _FakeMTCNN
    fake_facenet.InceptionResnetV1 = lambda *args, **kwargs: _FakeResnet()

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "torchvision", fake_torchvision)
    monkeypatch.setitem(sys.modules, "facenet_pytorch", fake_facenet)

    result = face_step.face_embed({"source_path": str(image_path)}, {})

    assert result["faces_meta"]["status"] == "ok"
    assert result["faces_meta"]["engine"] == "facenet-pytorch"
    assert len(result["faces"]) == 1
