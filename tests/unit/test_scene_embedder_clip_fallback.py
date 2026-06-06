from __future__ import annotations

import sys
import types


def test_clip_loader_falls_back_when_safetensors_weights_are_unavailable(monkeypatch):
    import steps.video.scene_embedder as scene_embedder

    scene_embedder._MODELS["clip"] = {"model": None, "processor": None, "device": "cpu"}
    monkeypatch.setattr(scene_embedder, "_resolve_model_device", lambda _step_name: "cpu")

    calls = []

    class _FakeProcessor:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            assert model_id in ("openai/clip-vit-base-patch16", "openai/clip-vit-large-patch14")
            return object()

    class _FakeModel:
        @classmethod
        def from_pretrained(cls, model_id, **kwargs):
            assert model_id in ("openai/clip-vit-base-patch16", "openai/clip-vit-large-patch14")
            calls.append(kwargs)
            if kwargs.get("use_safetensors"):
                raise OSError("safetensors missing")
            return cls()

        def to(self, device):
            self.device = device
            return self

        def eval(self):
            self.evaluated = True
            return self

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.CLIPModel = _FakeModel
    fake_transformers.CLIPProcessor = _FakeProcessor
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", types.ModuleType("torch"))

    try:
        scene_embedder._load_clip_model()

        cleaned_calls = [{k: v for k, v in c.items() if k != "revision"} for c in calls]
        assert cleaned_calls == [{"use_safetensors": True}, {}]
        assert scene_embedder._MODELS["clip"]["model"] is not None
        assert scene_embedder._MODELS["clip"]["device"] == "cpu"
    finally:
        scene_embedder._MODELS["clip"] = {"model": None, "processor": None, "device": "cpu"}
        package = sys.modules.get("steps.video")
        if package is not None and getattr(package, "scene_embedder", None) is scene_embedder:
            delattr(package, "scene_embedder")
        sys.modules.pop("steps.video.scene_embedder", None)
