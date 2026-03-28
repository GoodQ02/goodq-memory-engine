from __future__ import annotations

import types
from pathlib import Path

import torch


def test_process_audio_uses_waveform_dict_for_diarization(monkeypatch, tmp_path: Path):
    from wsl2_audio import process_audio as mod

    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"wav")
    output_dir = tmp_path / "out"

    waveform = torch.zeros((1, 16000))
    captured = {}

    class _FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            info = types.SimpleNamespace(language="en", language_probability=1.0)
            return iter(()), info

    class _FakeAnnotation:
        def itertracks(self, yield_label=False):
            yield (types.SimpleNamespace(start=0.0, end=1.0), "track_0", "speaker_0")

    class _FakePipeline:
        def to(self, device):
            captured["device"] = str(device)

        def __call__(self, audio_input):
            captured["audio_input"] = audio_input
            return _FakeAnnotation()

    class _FakePipelineFactory:
        @staticmethod
        def from_pretrained(model_name, token=None):
            captured["model_name"] = model_name
            captured["token"] = token
            return _FakePipeline()

    monkeypatch.setattr(mod, "_load_runtime_config", lambda: {
        "gpu": {"device": "cpu", "compute_type": "int8", "memory_fraction": 0.8},
        "models": {"whisper": "medium", "diarization": "pyannote/speaker-diarization-3.1"},
        "diarization": {"enabled": True},
        "processing": {"language": "en", "beam_size": 5},
        "_sources": [],
    })
    monkeypatch.setattr(mod, "require_gpu", lambda: False)
    monkeypatch.setattr(mod, "resolve_wsl_gpu_config", lambda cfg: dict(cfg))
    monkeypatch.setattr(mod.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(mod.torchaudio, "load", lambda _: (waveform.clone(), 16000))
    monkeypatch.setattr(mod, "WhisperModel", _FakeWhisperModel)
    monkeypatch.setattr(mod, "DIARIZATION_AVAILABLE", True)
    monkeypatch.setattr(mod, "DiarizationPipeline", _FakePipelineFactory, raising=False)
    monkeypatch.setattr(mod, "TRANSFORMERS_AVAILABLE", False)
    monkeypatch.setattr(mod, "clear_gpu_memory", lambda: None)
    monkeypatch.setenv("HF_TOKEN", "test-token")

    result = mod.process_audio(str(audio_file), str(output_dir))

    assert result["status"] == "success"
    assert result["device"] == "cpu"
    assert result["diarization_status"] == "success"
    assert result["speaker_count"] == 1
    assert captured["model_name"] == "pyannote/speaker-diarization-3.1"
    assert captured["token"] == "test-token"
    assert isinstance(captured["audio_input"], dict)
    assert captured["audio_input"]["sample_rate"] == 16000
    assert torch.equal(captured["audio_input"]["waveform"], waveform)
