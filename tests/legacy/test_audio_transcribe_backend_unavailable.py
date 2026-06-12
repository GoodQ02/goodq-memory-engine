from __future__ import annotations

import sys
import types
import wave
from pathlib import Path

from steps.audio_transcribe.step import _detect_transcription_device, audio_transcribe


def test_audio_transcribe_returns_model_unavailable_without_chunk_loop(
    monkeypatch, tmp_path: Path
):
    wav_path = tmp_path / "sample.wav"
    sample_rate = 16000
    total_frames = sample_rate
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * total_frames)

    monkeypatch.setattr("steps.audio_transcribe.step.require_wsl_audio", lambda: False)
    monkeypatch.setattr("steps.audio_transcribe.step.is_baseline", lambda: True)
    monkeypatch.setattr("steps.audio_transcribe.step.require_gpu", lambda: False)
    monkeypatch.setattr("steps.audio_transcribe.step._audio_duration", lambda _path: 1.0)
    monkeypatch.setattr(
        "steps.audio_transcribe.step._build_chunks",
        lambda *_args, **_kwargs: [{"start": 0.0, "end": 1.0, "speaker": None}],
    )
    monkeypatch.setattr("steps.audio_transcribe.step._load_fw_model", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "steps.audio_transcribe.step._slice_to_wav",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("chunk loop should not execute")),
    )

    result = audio_transcribe(
        {"source_path": str(wav_path)},
        {"audio": {"transcribe": {"use_wsl2": False}}},
    )

    assert result["transcript"] is None
    assert result["transcript_meta"]["status"] == "model_unavailable"
    assert result["transcript_meta"]["device"] == "none"
    assert result["transcript_meta"]["attempted_device"] == "cpu"
    assert result["transcript_meta"]["device_probe"] == "profile:baseline_cpu_safe"


def test_detect_transcription_device_baseline_prefers_cpu(monkeypatch):
    monkeypatch.setattr("steps.audio_transcribe.step.is_baseline", lambda: True)
    monkeypatch.setattr("steps.audio_transcribe.step.require_gpu", lambda: False)

    device, probe = _detect_transcription_device()

    assert device == "cpu"
    assert probe == "profile:baseline_cpu_safe"


def test_detect_transcription_device_non_baseline_allows_ctranslate2_probe(monkeypatch):
    monkeypatch.setattr("steps.audio_transcribe.step.is_baseline", lambda: False)
    monkeypatch.setattr("steps.audio_transcribe.step.require_gpu", lambda: False)

    fake_torch = types.ModuleType("torch")

    class _FakeCuda:
        @staticmethod
        def is_available():
            return False

    fake_torch.cuda = _FakeCuda()
    fake_torch.__version__ = "fake"

    fake_ctranslate2 = types.ModuleType("ctranslate2")
    fake_ctranslate2.__version__ = "fake"
    fake_ctranslate2.get_cuda_device_count = lambda: 1

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)

    device, probe = _detect_transcription_device()

    assert device == "cuda"
    assert probe == "ctranslate2:fake"
