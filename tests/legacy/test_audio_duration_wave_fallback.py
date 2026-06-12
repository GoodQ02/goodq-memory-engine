from __future__ import annotations

import wave
from pathlib import Path

from steps.audio_transcribe.step import _audio_duration


def test_audio_duration_uses_wave_fallback(tmp_path: Path):
    wav_path = tmp_path / "sample.wav"
    sample_rate = 16000
    duration_sec = 1.25
    total_frames = int(sample_rate * duration_sec)

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * total_frames)

    measured = _audio_duration(str(wav_path))
    assert measured is not None
    assert abs(measured - duration_sec) < 0.01
