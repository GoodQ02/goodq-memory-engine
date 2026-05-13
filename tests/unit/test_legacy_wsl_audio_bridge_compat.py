from __future__ import annotations

import importlib


def test_legacy_bridge_transcribe_delegates_to_canonical(monkeypatch):
    mod = importlib.import_module("wsl2_audio.audio_bridge")

    class StubBridge(mod.WSL2AudioBridge):
        def process_audio(self, audio_path, timeout=None):
            assert audio_path == "sample.wav"
            assert timeout == 123
            return {
                "status": "success",
                "transcription": "hello world",
                "segments": [{"start": 0.0, "end": 1.0, "text": "hello world"}],
                "word_timestamps": [{"start": 0.0, "end": 0.5, "text": "hello"}],
                "language": "en",
                "language_probability": 0.99,
                "duration_seconds": 1.0,
                "speaker_count": 1,
            }

    monkeypatch.setattr(mod, "_bridge", StubBridge())

    result = mod.transcribe_wsl2("sample.wav", timeout=123, run_id="run-1")

    assert result["status"] == "success"
    assert result["full_text"] == "hello world"
    assert result["info"]["language"] == "en"
    assert result["run_id"] == "run-1"


def test_legacy_bridge_service_check_aliases_runtime_readiness(monkeypatch):
    mod = importlib.import_module("wsl2_audio.audio_bridge")

    class StubBridge(mod.WSL2AudioBridge):
        def check_status(self):
            return True

    bridge = StubBridge()
    assert bridge._is_wsl_service_running() is True
