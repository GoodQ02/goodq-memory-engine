from __future__ import annotations

import sys
import types

from steps.audio_transcribe import step


def test_windows_cpu_model_load_uses_bounded_ctranslate_threads(monkeypatch):
    captured: dict[str, object] = {}

    class FakeWhisperModel:
        def __init__(self, model_id: str, **kwargs: object) -> None:
            captured["model_id"] = model_id
            captured.update(kwargs)

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    monkeypatch.setattr(step.os, "name", "nt")
    monkeypatch.setattr(
        step,
        "get_audio_gpu_optimizer",
        lambda: (_ for _ in ()).throw(AssertionError("CPU path must not create GPU optimizer")),
    )
    step._FW_CACHE.clear()

    step._load_fw_model("cached-model", "cpu", "int8")

    assert captured["model_id"] == "cached-model"
    assert captured["device"] == "cpu"
    assert captured["num_workers"] == 1
    assert captured["cpu_threads"] == 4
