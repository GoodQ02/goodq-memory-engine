from __future__ import annotations

import wave
from pathlib import Path

from steps.audio_transcribe.step import audio_transcribe


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
